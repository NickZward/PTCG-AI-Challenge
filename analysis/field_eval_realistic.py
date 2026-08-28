#!/usr/bin/env python3
"""REALISTIC-FIELD evaluation — the sharper validator. Scores an agent vs a pool of BC clones
of the top players (sparring partners that play like the real ladder field), not vs our own
pilots. Calibrated against ladder peaks: it recovers the correct ordering (e.g. Ala v13>v15)
that the self-play proxy got backwards. Use it for CLOSE calls where self-play misleads.

Pools (auto by archetype):
  ala   -> bc_majkel, bc_yushin, bc_bono           (the realistic Ala mirror)
  grimm -> bc_tonakaiiii, bc_kazuki, bc_s4nkurero  (the realistic Grimm mirror)

Usage: field_eval_realistic.py <agent_dir> [ala|grimm] [N=100]"""
import sys, os, importlib.util
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
ALA, GRIMM = 743, 648

POOLS = {
    "ala":   ["my-agent/bc_majkel", "my-agent/bc_yushin", "my-agent/bc_bono"],
    "grimm": ["my-agent/bc_tonakaiiii", "my-agent/bc_kazuki", "my-agent/bc_s4nkurero"],
}

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(ROOT, sub, "deck.csv")).read().split()]

def play(a0, d0, a1, d1, stop=14):
    obs, _ = cggame.battle_start(list(d0), list(d1))
    if obs is None: return -2
    steps, last = 0, None
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            if r not in (None, -1): return r
            if obs.get("select") is None: return -2
            turn = cur.get("turn", 0) or 0
            P = cur.get("players")
            if P and P[0] and P[1]:
                last = (6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or []),
                        P[0].get("deckCount") or 0, P[1].get("deckCount") or 0)
            if turn > stop and last is not None:
                p0, p1, dd0, dd1 = last
                return (0 if p0 > p1 else 1) if p0 != p1 else ((0 if dd0 > dd1 else 1) if dd0 != dd1 else -4)
            you = cur.get("yourIndex", 0)
            ag = a0 if you == 0 else a1
            w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                 "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
            obs = cggame.battle_select([int(a) for a in ag(w)]); steps += 1
        return -3
    finally:
        cggame.battle_finish()

def duel(aA, dA, aB, dB, n):
    w = g = 0
    for i in range(n):
        if i % 2 == 0:
            r = play(aA, dA, aB, dB); mine = (r == 0)
        else:
            r = play(aB, dB, aA, dA); mine = (r == 1)
        if r in (0, 1): g += 1; w += mine
    return w, g

def main():
    a_dir = sys.argv[1]
    arch = sys.argv[2] if len(sys.argv) > 2 else "ala"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    agentA, deckA = load(a_dir, "fer_A")
    pool = POOLS[arch]
    print(f"{os.path.basename(a_dir)} vs REALISTIC {arch} pool (N={n} each):")
    tot = 0.0; cnt = 0
    for i, opp in enumerate(pool):
        agentB, deckB = load(opp, f"fer_B{i}")
        w, g = duel(agentA, deckA, agentB, deckB, n)
        wr = w / max(1, g)
        print(f"  vs {os.path.basename(opp):<16} {wr:5.1%}  ({w}-{g-w})")
        tot += wr; cnt += 1
    print(f"  ==> REALISTIC-MIRROR SCORE: {tot/max(1,cnt):.1%}")

if __name__ == "__main__":
    main()
