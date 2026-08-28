#!/usr/bin/env python3
"""COUNTERFACTUAL LOSS-REPLAY — "replay my losses until I win and learn from them."
For a REAL loss replay, branch from each of OUR decision states via the engine search API and
roll the game to terminal with a CANDIDATE pilot vs a BASELINE pilot on our side. Measures, from
the actual states that beat us, how often each pilot would go on to win. If the candidate wins
markedly more, the fix would have flipped the loss — validated on the REAL states, not a proxy.

Honest caveat: the rollout can't replay the opponent's exact future (our different move changes
their board), so the opponent is played by the pilot on its determinized real deck. This is FAITHFUL
for the MIRROR (opp plays our deck) and approximate otherwise — so run it on mirror losses.

Usage: counterfactual_replay.py <replay.json> <candidate_dir> <baseline_dir> [K=8] [me_name=Kilupy]"""
import sys, os, json, importlib.util, random
from collections import Counter
import numpy as np
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg.api import search_begin, search_step, search_end, to_observation_class, SelectType

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    deck = [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]
    return m, deck

def dispatch(P, o):
    t = o.select.type
    if t == SelectType.MAIN: r = P.choose_main(o)
    elif t in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD): r = P.choose_cards(o)
    elif t == SelectType.YES_NO: r = P.choose_yes_no(o)
    elif t == SelectType.ATTACK: r = P.choose_attack(o)
    elif t == SelectType.COUNT: r = P.choose_count(o)
    elif t == SelectType.EVOLVE: r = P.choose_cards(o)
    elif t == SelectType.ENERGY: r = P.pick_by_priority(o, o.select, P.cfg('ENERGY_DISCARD', []), count=max(o.select.minCount, 1))
    else: r = P.safe_fallback(o.select)
    return P._validate(r, o.select)

def _unseen(deck, seen_ids):
    pc = Counter(deck)
    for cid in seen_ids:
        if cid is not None and pc.get(cid, 0) > 0: pc[cid] -= 1
    pool = list(pc.elements()); random.shuffle(pool); return pool

def determinize(P, oc, my_deck, opp_deck):
    me, op = P.me(oc), P.opp(oc)
    seen = [c.id for c in (me.hand or [])] + [c.id for c in (me.discard or [])]
    for pk in P.my_in_play(oc):
        seen.append(pk.id); seen += [getattr(e, "id", None) for e in (pk.energies or [])]
    mine = _unseen(my_deck, seen)
    need = me.deckCount + len(me.prize or []); mine += [5] * max(0, need - len(mine))
    yd = mine[:me.deckCount]; yp = mine[me.deckCount:me.deckCount + len(me.prize or [])]
    opp_board = [a for a in (op.active or []) if a] + [b for b in (op.bench or []) if b]
    oseen = [c.id for c in (op.discard or [])]
    for pk in opp_board:
        oseen.append(pk.id); oseen += [getattr(e, "id", None) for e in (pk.energies or [])]
    theirs = _unseen(opp_deck, oseen)
    oneed = op.deckCount + len(op.prize or []) + (op.handCount or 0)
    theirs += [5] * max(0, oneed - len(theirs))
    od = theirs[:op.deckCount] or [741]
    opz = theirs[op.deckCount:op.deckCount + len(op.prize or [])]
    oh = theirs[op.deckCount + len(op.prize or []):op.deckCount + len(op.prize or []) + (op.handCount or 0)]
    oa = (op.active or [None])[0]
    return yd, yp, od, opz, oh, [oa.id if oa else 741]

def rollout(P, wrapped, my_deck, opp_deck, me_i):
    """From the real state, roll BOTH sides with pilot P to terminal. Return 1 win / 0 loss / None."""
    oc = to_observation_class(wrapped)
    yd, yp, od, opz, oh, oa = determinize(P, oc, my_deck, opp_deck)
    try:
        s = search_begin(oc, yd, yp, od, opz, oh, oa); o = s.observation; d = 0
        while o.current.result == -1 and d < 800:
            if o.select is None: break
            s = search_step(s.searchId, dispatch(P, o)); o = s.observation; d += 1
        res = o.current.result
        search_end()
        if res == -1: return None
        return 1.0 if res == me_i else 0.0
    except Exception:
        try: search_end()
        except Exception: pass
        return None

def main():
    replay = sys.argv[1]; cand_dir = sys.argv[2]; base_dir = sys.argv[3]
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    me_name = sys.argv[5] if len(sys.argv) > 5 else "Kilupy"
    Pc, cdeck = load(cand_dir, "cf_cand"); Pb, bdeck = load(base_dir, "cf_base")
    d = json.load(open(replay))
    names = d['info']['TeamNames']
    me = next((i for i, n in enumerate(names) if me_name.lower() in n.lower()), 0)
    decks = d['steps'][0][0]['visualize'][0]['action']
    my_deck, opp_deck = decks[me], decks[1 - me]
    print(f"Replay {os.path.basename(replay)} | us={me_name} vs {names[1-me]} | reward={d.get('rewards')}")
    # gather OUR MAIN decision states (turn>=1, real choice)
    states = []
    for t, step in enumerate(d['steps']):
        e = step[me] if me < len(step) else None
        if not e: continue
        o = e.get('observation') or {}; sel = o.get('select')
        if not sel or sel.get('type') != 0: continue
        if len(sel.get('option') or []) <= 1: continue
        cur = o.get('current') or {}
        if (cur.get('turn', 0) or 0) < 1: continue
        wrapped = {"current": cur, "select": sel, "logs": o.get('logs', []), "step": t,
                   "remainingOverageTime": 600, "search_begin_input": o.get('search_begin_input')}
        if wrapped["search_begin_input"] is None: continue
        pl = cur.get('players'); mp = 6 - len(pl[me].get('prize') or []); op = 6 - len(pl[1-me].get('prize') or [])
        dk = pl[me].get('deckCount'); hd = len(pl[me].get('hand') or [])
        states.append((t, cur.get('turn'), mp, op, dk, hd, wrapped))
    print(f"{len(states)} of-our MAIN decision states. Rolling {K} each (cand vs base)...\n")
    print(f"{'turn':>4} {'prz':>5} {'deck':>4} {'hand':>4} | {'cand_win':>8} {'base_win':>8}  {'delta':>6}")
    agg_c, agg_b, nc, nb = 0.0, 0.0, 0, 0
    for (t, turn, mp, op, dk, hd, wrapped) in states:
        cw = [rollout(Pc, wrapped, cdeck, opp_deck, me) for _ in range(K)]
        bw = [rollout(Pb, wrapped, bdeck, opp_deck, me) for _ in range(K)]
        cw = [x for x in cw if x is not None]; bw = [x for x in bw if x is not None]
        if not cw or not bw: continue
        cwr, bwr = np.mean(cw), np.mean(bw)
        agg_c += cwr; agg_b += bwr; nc += 1; nb += 1
        flag = "  <== FIX WINS IT" if cwr - bwr >= 0.34 else ""
        print(f"{turn:>4} {f'{mp}-{op}':>5} {dk:>4} {hd:>4} | {cwr:>8.2f} {bwr:>8.2f}  {cwr-bwr:>+6.2f}{flag}")
    if nc:
        print(f"\nAGGREGATE across the real losing states:  candidate {agg_c/nc:.1%}  vs  baseline {agg_b/nb:.1%}"
              f"  (delta {(agg_c/nc)-(agg_b/nb):+.1%})")

if __name__ == "__main__":
    main()
