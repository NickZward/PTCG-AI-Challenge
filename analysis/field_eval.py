#!/usr/bin/env python3
"""Meta-weighted field evaluation — the iterate-against-the-field loop's scoreboard.
Plays <agent> vs each proxy opponent, aggregates with JULY ladder meta weights
(model/topjuly_index.jsonl). Local absolutes are inflated (weak proxies) — iterate on
DELTAS between versions and per-matchup ranks, per ptcg-methodology-discipline.

Usage: field_eval.py <agent_dir> [games_per_opp]"""
import sys, os, importlib.util
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame

# (proxy_dir, july_meta_share)
FIELD = [
    ("my-agent/alakazam_v11",      0.290),  # Alakazam — our own strong pilot as proxy
    ("my-agent/grimmsnarl_v14",    0.207),  # the mirror (the live agent)
    ("my-agent/gauntlet/crustle",  0.116),
    ("my-agent/gauntlet/starmie",  0.054),
    ("my-agent/gauntlet/archaludon", 0.051),
    ("my-agent/gauntlet/mlucario", 0.034),
    ("my-agent/pool/dragapult_v1", 0.025),
]

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(ROOT, sub, "deck.csv")).read().split()]

def duel(agentA, deckA, agentB, deckB, n):
    wins = 0; games = 0
    for g in range(n):
        # alternate seats
        a0, d0, a1, d1 = (agentA, deckA, agentB, deckB) if g % 2 == 0 else (agentB, deckB, agentA, deckA)
        obs, sd = cggame.battle_start(list(d0), list(d1))
        if obs is None: continue
        try:
            steps = 0; r = -1
            while steps < 4000:
                cur = obs.get("current") or {}
                r = cur.get("result", -1)
                if r not in (None, -1): break
                if obs.get("select") is None: break
                you = cur.get("yourIndex", 0)
                w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                     "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
                action = (a0 if you == 0 else a1)(w)
                obs = cggame.battle_select([int(x) for x in action]); steps += 1
            if r in (0, 1):
                games += 1
                mywin = (r == 0) if g % 2 == 0 else (r == 1)
                wins += mywin
        finally:
            cggame.battle_finish()
    return wins, games

def main():
    a_dir = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    agentA, deckA = load(a_dir, "fe_A")
    tot_w = sum(w for _, w in FIELD)
    agg = 0.0; rows = []
    for i, (opp, w) in enumerate(FIELD):
        agentB, deckB = load(opp, f"fe_B{i}")
        wins, games = duel(agentA, deckA, agentB, deckB, N)
        wr = wins / max(1, games)
        agg += (w / tot_w) * wr
        rows.append((opp.split('/')[-1], w, wr, wins, games))
    print(f"\n{os.path.basename(a_dir)} — JULY-META-WEIGHTED FIELD SCORE: {agg:.1%}")
    print(f"{'opponent':<16}{'weight':>8}{'WR':>7}{'record':>12}")
    for name, w, wr, wins, games in sorted(rows, key=lambda r: r[2]):
        print(f"  {name:<14}{w:>7.1%}{wr:>7.0%}{f'{wins}-{games-wins}':>12}")

if __name__ == "__main__":
    main()
