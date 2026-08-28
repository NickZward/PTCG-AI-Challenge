#!/usr/bin/env python3
"""STEP 2: Transformer + MCTS agent on the reference template, with OUR determinization.

Differences from the reference mcts_agent:
  - OUR side is determinized deck-aware with seen-card dedup (_unseen): sample the real deck
    minus everything already visible (hand/discard/in-play + attached energy), instead of the
    reference's random.sample(your_deck) which can double-count visible cards.
  - OPPONENT side: deck-aware when opp_deck is known (self-play/training); otherwise a neutral
    fill (Snorlax/energy) exactly like the reference, since a real ladder opponent's deck is hidden.

Exposes:
  determinize_for_search(oc, our_deck, opp_deck=None) -> the 7 search_begin args
  mcts_agent(obs_dict, our_deck, model, opp_deck=None, search_count=...) -> (select, LearnSample)
"""
import json
import os
import math
import random
from collections import Counter

from cg.api import search_begin, search_step, search_end, to_observation_class
import np_common as NN

FILLER_BASIC = 1072   # neutral Basic Pokemon (Snorlax) for unknown opponent deck/active
FILLER_ENERGY = 1     # neutral Basic Energy for unknown opponent hand/prize + our short-fill

# Endgame blend (see create_node): from turn T0 the leaf value ramps toward the concrete prize
# margin, reaching weight W at T1.
# GATE-REJECTED, DEFAULT OFF (2026-07-27). Hypothesis: the search never treats the buzzer as
# terminal, so it trades a live prize lead for advantages the clock never pays out. Measured
# (N=45/pair): blend-on vs blend-off 51.1% (nothing), and through v4 the blend LOST ground
# (46.7% vs the control's 60.0%). Two reasons it cannot help: the encoder already feeds turn/10
# and v4+ value heads are trained on margin-shaped targets, so buzzer awareness is already
# learned (that is what lifted behind-recovery 34%->61%); and at this search depth the prize
# margin is near-identical across root candidates, so the blend shifts every child equally and
# cancels in the argmax. Set PTCG_ENDGAME_W>0 only to re-test with a deeper search.
ENDGAME_W = float(os.environ.get("PTCG_ENDGAME_W", "0.0"))
ENDGAME_T0 = 8
ENDGAME_T1 = 14


# ---------------------------------------------------------------------------
# OPPONENT MODELLING (lever 1)
# On the ladder the opponent's deck is unknown, and the reference determinization fills their
# ENTIRE hidden state with Snorlax + basic energy. Every simulated opponent turn is therefore an
# opponent who cannot evolve, attach, play a supporter or develop a threat — so the search
# systematically evaluates our position as safer than it is and never plays around anything.
# Mid-game we can read their archetype off the cards they have already shown (in play + discard)
# and determinize from that archetype's real 60 instead. Falls back to the old filler whenever
# identification is not confident, so a mis-read early turn cannot make things worse.
ARCH_SIG = {648: 'Grimmsnarl', 743: 'Alakazam', 533: 'Crustle', 345: 'Crustle',
            678: 'M-Lucario', 93: 'Dipplin', 756: 'M-Kangaskhan', 190: 'Archaludon',
            1031: 'M-Starmie', 381: 'Cynthia-Garchomp', 121: 'Dragapult', 401: 'Spidops'}

_HERE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '.'
OPP_DECKS = {}
# SELF-CONTAINED ONLY. A repo-relative fallback used to live here and it silently re-enabled
# opponent modelling in an agent dir whose opp_decks.json had been deleted — which invalidated
# the v10 control arm (both arms ran with the feature on). An agent directory must depend on
# nothing outside itself: presence of its OWN opp_decks.json is the on/off switch.
for _cand in (os.path.join(_HERE_DIR, "opp_decks.json"),
              "/kaggle_simulations/agent/opp_decks.json"):
    try:
        with open(_cand) as _f:
            OPP_DECKS = {k: [int(x) for x in v] for k, v in json.load(_f).items()}
        break
    except Exception:
        continue

IDENT_STATS = Counter()   # instrumentation: fire-rate by outcome (read in tests)


def _visible_ids(ps):
    """Every opponent card id we are actually allowed to see: in-play Pokemon (+ their tools and
    attached energy) and the discard pile. Hand/deck/prizes are hidden and excluded."""
    ids = []
    for pk in list(ps.active or []) + list(ps.bench or []):
        if pk is None:
            continue
        ids.append(pk.id)
        for t in (getattr(pk, "tools", None) or []):
            ids.append(getattr(t, "id", None))
        for e in (getattr(pk, "energies", None) or getattr(pk, "energyCards", None) or []):
            ids.append(getattr(e, "id", None))
    for c in (ps.discard or []):
        ids.append(getattr(c, "id", None))
    return [i for i in ids if i is not None]


def identify_opponent(cur, opp_index):
    """Archetype name from the opponent's visible cards, or None when nothing identifies."""
    try:
        counts = Counter(_visible_ids(cur.players[opp_index]))
    except Exception:
        return None
    hits = [(lab, counts[cid]) for cid, lab in ARCH_SIG.items() if counts.get(cid)]
    if not hits:
        return None
    lab = max(hits, key=lambda x: x[1])[0]
    return lab if lab in OPP_DECKS else None


def _unseen(deck, seen):
    """Cards from `deck` not among `seen` (multiset subtraction), shuffled."""
    pc = Counter(deck)
    for cid in seen:
        if cid is not None and pc.get(cid, 0) > 0:
            pc[cid] -= 1
    pool = list(pc.elements())
    random.shuffle(pool)
    return pool


def determinize_for_search(oc, our_deck, opp_deck=None):
    """Build a plausible full hidden state for search_begin from the public observation.

    our side: sample our_deck minus visible cards -> deck + prize (energy-filled if short).
    opp side: opp_deck given -> deck-aware sample; else neutral Snorlax/energy fill.
    Returns (your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active).
    """
    cur = oc.current
    yi = cur.yourIndex
    me = cur.players[yi]
    op = cur.players[1 - yi]

    # ---- our hidden zones (deck-aware, dedup seen) ----
    seen = [c.id for c in (me.hand or [])] + [c.id for c in (me.discard or [])]
    for pk in list(me.active or []) + list(me.bench or []):
        if pk is None:
            continue
        seen.append(pk.id)
        seen += [getattr(e, "id", None) for e in (pk.energies or [])]
    mine = _unseen(our_deck, seen)
    need = me.deckCount + len(me.prize or [])
    mine += [FILLER_ENERGY] * max(0, need - len(mine))
    yd = mine[:me.deckCount]
    yp = mine[me.deckCount:me.deckCount + len(me.prize or [])]

    # ---- opponent hidden zones ----
    opz_len = len(op.prize or [])
    oh_len = op.handCount or 0
    if opp_deck is None and OPP_DECKS:
        # ladder path: infer their archetype and search against that deck instead of Snorlax filler
        arch = identify_opponent(cur, 1 - yi)
        if arch:
            opp_deck = OPP_DECKS[arch]
            IDENT_STATS[arch] += 1
        else:
            IDENT_STATS["unidentified"] += 1
    if opp_deck is not None:
        oseen = [c.id for c in (op.discard or [])]
        for pk in list(op.active or []) + list(op.bench or []):
            if pk is None:
                continue
            oseen.append(pk.id)
            oseen += [getattr(e, "id", None) for e in (pk.energies or [])]
        theirs = _unseen(opp_deck, oseen)
        theirs += [FILLER_ENERGY] * max(0, (op.deckCount + opz_len + oh_len) - len(theirs))
        od = theirs[:op.deckCount] or [FILLER_ENERGY]
        opz = theirs[op.deckCount:op.deckCount + opz_len]
        oh = theirs[op.deckCount + opz_len:op.deckCount + opz_len + oh_len]
    else:
        od = [FILLER_BASIC] * op.deckCount or [FILLER_BASIC]
        opz = [FILLER_ENERGY] * opz_len
        oh = [FILLER_ENERGY] * oh_len

    active = op.active
    oa = [FILLER_BASIC] if (len(active) > 0 and active[0] is None) else []
    return yd, yp, od, opz, oh, oa


# ---------------------------------------------------------------------------
# MCTS (ported from the reference; uses nn_common for encoding + eval)
# ---------------------------------------------------------------------------
class LearnSample:
    def __init__(self, value, policy, sv_enc, sv_dec):
        self.value = value
        self.policy = policy
        self.sv_enc = sv_enc
        self.sv_dec = sv_dec


class Child:
    def __init__(self, select, prob):
        self.node = None
        self.select = select
        self.prob = prob


class Node:
    def __init__(self, parent, state):
        self.value = -2.0
        self.total = 0.0
        self.visit = 0
        self.parent = parent
        self.children = []
        self.state = state

    def backprop(self, value):
        self.total += value
        self.visit += 1
        if self.parent is not None:
            self.parent.backprop(value)


def create_node(parent, search_state, your_index, your_deck, model):
    node = Node(parent, search_state)
    obs = search_state.observation
    state = obs.current
    if state.result >= 0:
        if state.result == 2:
            node.value = 0
        elif state.result == your_index:
            node.value = 1
        else:
            node.value = -1
        node.backprop(node.value)
        return node, None

    actions = NN.enumerate_actions(obs.select, cap=64)
    sv_enc = NN.get_encoder_input(obs, your_deck)
    sv_dec = NN.get_decoder_input(obs, actions)
    value, policy = NN.eval_nn(sv_enc, sv_dec, model)

    v = value
    if state.yourIndex != your_index:
        v = -v

    # ---- ENDGAME / BUZZER AWARENESS -------------------------------------------------------
    # Ladder games are overwhelmingly decided by the clock, not by a knockout: in v4's 54 rated
    # games 42 (78%) ended at the buzzer, 44% of losses were decided by <=1 prize and 3 by an
    # exact prize tie. The value head predicts "do we eventually win", and the search only ever
    # treated a natural KO-out (result >= 0) as terminal — so late in a game it happily explores
    # lines that trade a present prize lead for a future advantage that the buzzer will never pay
    # out. Blend the learned value toward the CONCRETE prize margin as the turn count climbs
    # (deck count as the documented tiebreak when prizes are level). Deliberately a smooth ramp
    # rather than a hard turn-14 terminal: the real cap is a wall-clock/step limit (observed end
    # turns run 9-35, median 12.5), and a hard cap would also over-fit our local turn-14 harness.
    try:
        P = state.players
        mine = 6 - len(P[your_index].prize or [])
        theirs = 6 - len(P[1 - your_index].prize or [])
        margin = (mine - theirs) / 3.0
        if mine == theirs:                       # prize-tied -> deck count breaks it
            dm = (P[your_index].deckCount or 0) - (P[1 - your_index].deckCount or 0)
            margin = 0.15 * (1.0 if dm > 0 else (-1.0 if dm < 0 else 0.0))
        margin = max(-1.0, min(1.0, margin))
        turn = state.turn or 0
        urgency = max(0.0, min(1.0, (turn - ENDGAME_T0) / float(ENDGAME_T1 - ENDGAME_T0)))
        w = ENDGAME_W * urgency
        v = (1.0 - w) * v + w * margin
    except Exception:
        pass

    node.value = v
    node.backprop(v)

    # Priors from the policy head. The reference head is tanh-squashed in [-1,1], so exp(p*10)
    # is a temperature that turns it into a usable distribution. A CE-trained head
    # (policy_tanh=False) already emits raw logits — applying the x10 there would saturate the
    # prior onto a single child and blind the search, so softmax them directly.
    scale = 1.0 if getattr(model, "policy_tanh", True) is False else 10.0
    top = max(policy) if policy else 0.0
    total = 0.0
    for i in range(len(policy)):
        p = math.exp((policy[i] - top) * scale)
        node.children.append(Child(actions[i], p))
        total += p
    for c in node.children:
        c.prob /= total
    return node, LearnSample(value, policy, sv_enc, sv_dec)


def mcts_agent(obs_dict, our_deck, model, opp_deck=None, search_count=None):
    """Pick a move by MCTS. Returns (select_indices, LearnSample-for-training)."""
    if search_count is None:
        search_count = NN.SEARCH_COUNT
    obs = to_observation_class(obs_dict)
    your_index = obs.current.yourIndex
    n_opt = len(obs.select.option)
    max_count = obs.select.maxCount

    def _safe_default():
        k = min(max_count, n_opt)
        return random.sample(range(n_opt), k) if n_opt else []

    # search_begin needs a valid search_begin_input; guard so a rare select-type edge case
    # (or a missing input) degrades to a legal default instead of killing a long training run.
    try:
        yd, yp, od, opz, oh, oa = determinize_for_search(obs, our_deck, opp_deck)
        search_state = search_begin(obs, yd, yp, od, opz, oh, oa)
        root, sample = create_node(None, search_state, your_index, our_deck, model)
    except Exception:
        try:
            search_end()
        except Exception:
            pass
        return _safe_default(), None

    if not root.children:            # terminal or single trivial action
        search_end()
        sel = root.children[0].select if root.children else list(range(obs.select.maxCount))
        return sel, sample

    # ROOT-BREADTH-FIRST sweep (ladder autopsy fix): guarantee every root child one evaluation
    # (best-prior first) before UCB deepening. With few evals a collapsed prior could starve
    # siblings — measured as the ctx=7 first-option collapse (40.2% vs experts' 13.2%). Depth
    # past 1 ply simulates a determinized (guessed) opponent, so breadth at the root is the
    # better spend of the first evals (the Path-C-validated 1-ply value comparison).
    # BUG HISTORY (2026-07-29): this sweep originally called create_node with `your_deck` — a
    # name that does not exist in this scope (the parameter is `our_deck`). The NameError was
    # swallowed by the except and `spent` incremented anyway, so EVERY move burned min(ncand,
    # search_count) evaluations doing nothing, and decisions with ncand >= search_count got no
    # search at all and fell through to the first enumerated action. Measured: 29 instead of 33
    # create_node calls on a 4-candidate move. Never swallow an expansion failure silently again.
    sweep = sorted(range(len(root.children)), key=lambda i: -root.children[i].prob)
    spent = 0
    for i in sweep:
        if spent >= search_count:
            break
        child = root.children[i]
        if child.node is None:
            try:
                child_state = search_step(root.state.searchId, child.select)
                child.node, _ = create_node(root, child_state, your_index, our_deck, model)
            except Exception:
                IDENT_STATS["sweep_expand_error"] += 1
            spent += 1

    for _ in range(max(0, search_count - spent)):
        current = root
        while True:
            best_v = -1e9
            nxt = None
            c = 0.4 * math.sqrt(current.visit)
            for child in current.children:
                visit = 0
                if child.node is None:
                    v = current.total / current.visit
                else:
                    v = child.node.total / child.node.visit
                    visit = child.node.visit
                if current.state.observation.current.yourIndex != your_index:
                    v = -v
                v += c * child.prob / (1 + visit)
                if best_v < v:
                    best_v = v
                    nxt = child
            if nxt is None:
                break
            if nxt.node is None:
                child_state = search_step(current.state.searchId, nxt.select)
                nxt.node, _ = create_node(current, child_state, your_index, our_deck, model)
                break
            current = nxt.node
            if current.state.observation.current.result >= 0:
                current.backprop(current.value)
                break

    # most-visited child = the move; TIES broken by mean value (after a breadth sweep every
    # child can sit at visit==1, and the old strict `<` silently resolved that tie to "first
    # enumerated action" — value and prior ignored)
    max_child = None
    max_visit = -1
    max_key = None
    min_value = 10.0
    for child in root.children:
        if child.node is not None:
            v = child.node.total / child.node.visit
            key = (child.node.visit, v)
            if max_key is None or key > max_key:
                max_child = child
                max_visit = child.node.visit
                max_key = key
            if min_value > v:
                min_value = v

    # training targets: root value + per-child advantage (reference scheme)
    if sample is not None:
        sample.value = root.total / root.visit
        for i in range(len(root.children)):
            child = root.children[i]
            if child.node is None:
                v = min_value - sample.value - 0.03
            else:
                v = child.node.total / child.node.visit - sample.value
            sample.policy[i] = max(-1.0, min(1.0, v))

    search_end()
    if max_child is None:                       # no child expanded (e.g. search_count too low)
        max_child = root.children[0]
    return max_child.select, sample
