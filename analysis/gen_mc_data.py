#!/usr/bin/env python3
"""MC value-target data generation (AlphaZero-style). Self-play with the rule pilot; at each
of our MAIN decisions, roll out several CANDIDATE moves to terminal via the engine search API
and label each end-of-OUR-turn state with its true win/loss. This gives (determinized
end-of-turn state -> true MC value) pairs covering good AND bad moves — the coverage a
replay-trained VF lacked, which is why 1-ply search couldn't out-rank the rules.

Usage: gen_mc_data.py <n_games> [k_candidates] [out.npz]"""
import sys, os, importlib.util, random
from collections import Counter
import numpy as np
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v13"))
import bc_features as F
from cg.api import (search_begin, search_step, search_end, to_observation_class, SelectType)
VOCABJ = __import__("json").load(open(os.path.join(ROOT, "my-agent/grimmsnarl_v13/bc_vocab.json")))
VOCAB, CF = VOCABJ["vocab"], VOCABJ["card_feats"]

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m, [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]
P, DECK = load(os.path.join(ROOT, "my-agent/grimmsnarl_v12r"), "gen_pilot")

def rule_dispatch(o):
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

def _unseen(player, in_play_fn, oc):
    """DECK minus the cards we can see for this player (self-play: both play DECK)."""
    pc = Counter(DECK)
    seen = [c.id for c in (player.discard or [])]
    for pk in in_play_fn:
        seen.append(pk.id); seen += [getattr(e, "id", None) for e in (pk.energies or [])]
    for cid in seen:
        if cid is not None and pc.get(cid, 0) > 0: pc[cid] -= 1
    pool = list(pc.elements()); random.shuffle(pool)
    return pool

def determinize(oc):
    """Determinize BOTH sides from DECK (self-play => opp really plays DECK). A realistic opp
    is essential: a placeholder opp deck made rollouts win ~0.72 (brain-dead opp)."""
    me, op = P.me(oc), P.opp(oc)
    # our hidden zones (also subtract our hand, which we can see)
    mine = _unseen(me, P.my_in_play(oc), oc)
    mc = Counter(mine)
    for c in (me.hand or []):
        if mc.get(c.id, 0) > 0: mc[c.id] -= 1
    mine = list(mc.elements()); random.shuffle(mine)
    need = me.deckCount + len(me.prize or []); mine += [5] * max(0, need - len(mine))
    yd = mine[:me.deckCount]; yp = mine[me.deckCount:me.deckCount + len(me.prize or [])]
    # opp hidden zones: opp's in-play is visible (active/bench); build from opp's board
    opp_board = [a for a in (op.active or []) if a] + [b for b in (op.bench or []) if b]
    theirs = _unseen(op, opp_board, oc)
    oneed = op.deckCount + len(op.prize or []) + (op.handCount or 0)
    theirs += [5] * max(0, oneed - len(theirs))
    od = theirs[:op.deckCount]
    opz = theirs[op.deckCount:op.deckCount + len(op.prize or [])]
    oh = theirs[op.deckCount + len(op.prize or []):op.deckCount + len(op.prize or []) + (op.handCount or 0)]
    if not od: od = [5]
    return yd, yp, od, opz, oh

def rollout_candidate(oc, cand):
    """Apply candidate, finish OUR turn with rules -> capture end-of-turn features; then roll
    to terminal -> outcome. Returns (features, outcome) or None."""
    yd, yp, od, opz, oh = determinize(oc)
    try:
        root = search_begin(oc, yd, yp, od, opz, oh, [741])
        s = search_step(root.searchId, [cand]); o = s.observation; d = 0
        while (o.select is not None and o.current.result == -1 and o.current.yourIndex == 0 and d < 40):
            s = search_step(s.searchId, rule_dispatch(o)); o = s.observation; d += 1
        if o.current.result != -1:
            feats = [0.0] * F.N_STATE; outcome = 1.0 if o.current.result == 0 else 0.0
            search_end(); return feats, outcome
        feats = F.state_features(o.current, 0, VOCAB, CF, step=(getattr(o.current, 'turn', 0) or 0))
        while o.current.result == -1 and d < 600:
            if o.select is None: break
            s = search_step(s.searchId, rule_dispatch(o)); o = s.observation; d += 1
        outcome = 1.0 if o.current.result == 0 else 0.0
        search_end(); return feats, outcome
    except Exception:
        try: search_end()
        except Exception: pass
        return None

def main():
    N = int(sys.argv[1]); K = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "model/mc_vf_data.npz")
    X, y = [], []
    for g in range(N):
        obs, sd = cggame.battle_start(list(DECK), list(DECK))
        if obs is None: continue
        try:
            steps = 0
            while steps < 4000:
                cur = obs.get("current") or {}
                if cur.get("result", -1) not in (None, -1): break
                if obs.get("select") is None: break
                you = cur.get("yourIndex", 0)
                w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                     "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
                if you == 0:
                    oc = to_observation_class(w)
                    if (oc.select is not None and oc.select.type == SelectType.MAIN
                            and oc.search_begin_input is not None and len(oc.select.option) > 1
                            and (cur.get("turn", 0) or 0) >= 1):
                        n = len(oc.select.option)
                        rule_c = P._validate(P.choose_main(oc), oc.select)
                        rule_i = rule_c[0] if rule_c else 0
                        cands = {rule_i}
                        others = [i for i in range(n) if i != rule_i]
                        random.shuffle(others)
                        cands.update(others[:max(0, K - 1)])
                        for c in cands:
                            res = rollout_candidate(oc, c)
                            if res: X.append(res[0]); y.append(res[1])
                a = P.agent(w)
                obs = cggame.battle_select([int(x) for x in a]); steps += 1
        finally:
            cggame.battle_finish()
        if (g + 1) % 25 == 0:
            print(f"  game {g+1}/{N}, samples {len(X)}, win-rate {np.mean(y):.2f}", flush=True)
    X = np.array(X, dtype=np.float32); y = np.array(y, dtype=np.float32)
    np.savez_compressed(out, X=X, y=y)
    print(f"saved {len(X)} MC samples (mean value {y.mean():.2f}) -> {out}")

if __name__ == "__main__":
    main()
