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
import math
import random
from collections import Counter

from cg.api import search_begin, search_step, search_end, to_observation_class
import nn_common as NN

FILLER_BASIC = 1072   # neutral Basic Pokemon (Snorlax) for unknown opponent deck/active
FILLER_ENERGY = 1     # neutral Basic Energy for unknown opponent hand/prize + our short-fill


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
    node.value = v
    node.backprop(v)

    total = 0.0
    for i in range(len(policy)):
        p = math.exp(policy[i] * 10.0)
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

    for _ in range(search_count):
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

    # most-visited child = the move
    max_child = None
    max_visit = -1
    min_value = 10.0
    for child in root.children:
        if child.node is not None:
            if max_visit < child.node.visit:
                max_child = child
                max_visit = child.node.visit
            v = child.node.total / child.node.visit
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
