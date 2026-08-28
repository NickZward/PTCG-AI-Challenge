#!/usr/bin/env python3
"""Meta-weighted field evaluation, LADDER-ADJUDICATED (the fix the handoff flagged:
field_eval.py used the OLD completion harness; verdicts must use adjudication).
Games stop at turn `stop` (default 14); PRIZE LEADER wins, deckout=loss, deck breaks
ties (empirical ladder rule from 88 live games). Absolutes still inflated by weak
proxies — iterate on DELTAS between versions + per-matchup ranks.

Field uses alakazam_v13 (the FAITHFUL hand-hoarder ladder-Ala proxy, per
ptcg-grimm-engine-gap) as the 29%-weight Alakazam cell, not the old v11.

Usage: field_eval_adj.py <agent_dir> [games_per_opp=200] [stop=14]"""
import sys, os, importlib.util
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame

# (proxy_dir, july_meta_share)
FIELD = [
    ("my-agent/alakazam_v13",        0.290),  # faithful hand-hoarder Ala proxy
    ("my-agent/grimmsnarl_v14",      0.207),  # fixed mirror reference (same for all versions)
    ("my-agent/gauntlet/crustle",    0.116),
    ("my-agent/gauntlet/starmie",    0.054),
    ("my-agent/gauntlet/archaludon", 0.051),
    ("my-agent/gauntlet/mlucario",   0.034),
    ("my-agent/pool/dragapult_v1",   0.025),
]

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(ROOT, sub, "deck.csv")).read().split()]

def duel(agentA, deckA, agentB, deckB, n, stop):
    wins = 0; games = 0; draws = 0
    for g in range(n):
        a0, d0, a1, d1 = (agentA, deckA, agentB, deckB) if g % 2 == 0 else (agentB, deckB, agentA, deckA)
        obs, sd = cggame.battle_start(list(d0), list(d1))
        if obs is None: continue
        try:
            steps = 0; res = None; last = None
            while steps < 4000:
                cur = obs.get("current") or {}
                r = cur.get("result", -1)
                if r not in (None, -1): res = r; break
                if obs.get("select") is None: res = -2; break
                turn = cur.get("turn", 0) or 0
                P = cur.get("players")
                if P and P[0] and P[1]:
                    last = (6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or []),
                            P[0].get("deckCount") or 0, P[1].get("deckCount") or 0)
                if turn > stop and last is not None:
                    p0, p1, dd0, dd1 = last
                    if p0 != p1: res = 0 if p0 > p1 else 1
                    elif dd0 != dd1: res = 0 if dd0 > dd1 else 1
                    else: res = -4
                    break
                you = cur.get("yourIndex", 0)
                w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                     "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
                action = (a0 if you == 0 else a1)(w)
                obs = cggame.battle_select([int(x) for x in action]); steps += 1
            if res in (0, 1):
                games += 1
                mywin = (res == 0) if g % 2 == 0 else (res == 1)
                wins += mywin
            elif res == -4:
                draws += 1
        finally:
            cggame.battle_finish()
    return wins, games, draws

def main():
    a_dir = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    stop = int(sys.argv[3]) if len(sys.argv) > 3 else 14
    agentA, deckA = load(a_dir, "fea_A")
    tot_w = sum(w for _, w in FIELD)
    agg = 0.0; rows = []
    for i, (opp, w) in enumerate(FIELD):
        agentB, deckB = load(opp, f"fea_B{i}")
        wins, games, draws = duel(agentA, deckA, agentB, deckB, N, stop)
        wr = wins / max(1, games)
        agg += (w / tot_w) * wr
        rows.append((opp.split('/')[-1], w, wr, wins, games, draws))
    print(f"\n{os.path.basename(a_dir)} — JULY-META ADJUDICATED FIELD SCORE: {agg:.1%}  (stop=T{stop})")
    print(f"{'opponent':<16}{'weight':>8}{'WR':>7}{'record':>12}{'draws':>7}")
    for name, w, wr, wins, games, draws in sorted(rows, key=lambda r: r[2]):
        print(f"  {name:<14}{w:>7.1%}{wr:>7.0%}{f'{wins}-{games-wins}':>12}{draws:>7}")

if __name__ == "__main__":
    main()
