#!/usr/bin/env python3
"""Instrumented mirror A/B for the Alakazam pilot. WR-proxies can't reproduce the
live 34% mirror, so we gate a fix on MECHANISM: does side A out-set-up / out-prize
side B at the ladder stop? Reports WR + avg prizes@stop + avg Alakazam-in-play turn
(board membership = robust; energy-timing is a known-unreliable replay field so we
report prizes, which are unambiguous).

Usage: mirror_ab.py <A_dir> <B_dir> [games=300] [stop=14]"""
import importlib.util, os, sys
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
ALA = 743

def load(subdir, modname):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(subdir, "main.py"))
    mod = importlib.util.module_from_spec(spec); sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    deck = [int(x) for x in open(os.path.join(subdir, "deck.csv")).read().split()]
    return mod.agent, deck

def ala_in_play(player):
    if not player: return False
    mons = (player.get("active") or []) + (player.get("bench") or [])
    return any(m and m.get("id") == ALA for m in mons)

def play(a0, d0, a1, d1, stop, max_steps=4000):
    obs, sd = cggame.battle_start(list(d0), list(d1))
    if obs is None: raise RuntimeError("battle_start failed")
    steps = 0; last = None
    ala_turn = [None, None]
    try:
        while steps < max_steps:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            turn = cur.get("turn", 0) or 0
            P = cur.get("players")
            if P and P[0] and P[1]:
                last = (6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or []),
                        P[0].get("deckCount") or 0, P[1].get("deckCount") or 0)
                for pi in (0, 1):
                    if ala_turn[pi] is None and ala_in_play(P[pi]): ala_turn[pi] = turn
            if r is not None and r != -1:
                p = last or (0, 0, 0, 0)
                return r, p[0], p[1], ala_turn
            if obs.get("select") is None:
                p = last or (0, 0, 0, 0)
                return -2, p[0], p[1], ala_turn
            if turn > stop and last is not None:
                p0, p1, dd0, dd1 = last
                if p0 != p1: res = 0 if p0 > p1 else 1
                elif dd0 != dd1: res = 0 if dd0 > dd1 else 1
                else: res = -4
                return res, p0, p1, ala_turn
            you = cur.get("yourIndex", 0)
            agent = a0 if you == 0 else a1
            wrapped = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                       "step": steps, "remainingOverageTime": 600,
                       "search_begin_input": obs.get("search_begin_input")}
            action = agent(wrapped)
            obs = cggame.battle_select([int(a) for a in action]); steps += 1
        p = last or (0, 0, 0, 0)
        return -3, p[0], p[1], ala_turn
    finally:
        cggame.battle_finish()

def main():
    a_dir, b_dir = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    stop = int(sys.argv[4]) if len(sys.argv) > 4 else 14
    agent_a, deck_a = load(a_dir, "ab_a")
    agent_b, deck_b = load(b_dir, "ab_b")
    wins = [0, 0]; odd = 0
    przA = przB = 0.0; nprz = 0
    alaA = []; alaB = []
    for g in range(n):
        # alternate seats; track which seat is A
        if g % 2 == 0:
            r, p0, p1, at = play(agent_a, deck_a, agent_b, deck_b, stop)
            a_seat = 0
        else:
            r, p0, p1, at = play(agent_b, deck_b, agent_a, deck_a, stop)
            a_seat = 1
        wA = {a_seat: "A", 1 - a_seat: "B"}.get(r, "?")
        if wA == "A": wins[0] += 1
        elif wA == "B": wins[1] += 1
        else: odd += 1
        # prizes/ala-turn by side
        pA, pB = (p0, p1) if a_seat == 0 else (p1, p0)
        przA += pA; przB += pB; nprz += 1
        atA, atB = (at[a_seat], at[1 - a_seat])
        if atA is not None: alaA.append(atA)
        if atB is not None: alaB.append(atB)
    print(f"ADJ  A={a_dir.split('/')[-1]} {wins[0]}  B={b_dir.split('/')[-1]} {wins[1]}  odd={odd}  "
          f"(WR_A={wins[0]/max(1,wins[0]+wins[1]):.1%})")
    print(f"  avg prizes@stop:  A={przA/max(1,nprz):.2f}  B={przB/max(1,nprz):.2f}  (diff {(przA-przB)/max(1,nprz):+.2f})")
    print(f"  avg Alakazam-in-play turn:  A={sum(alaA)/max(1,len(alaA)):.2f}  B={sum(alaB)/max(1,len(alaB)):.2f}"
          f"  (online rate A={len(alaA)/max(1,nprz):.0%} B={len(alaB)/max(1,nprz):.0%})")

if __name__ == "__main__":
    main()
