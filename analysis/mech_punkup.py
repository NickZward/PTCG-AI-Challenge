#!/usr/bin/env python3
"""Punk Up policy probe: play <agent> vs <opp> N games; report max-Darks-ever-stacked on one
Grimmsnarl per game (bono mode: 3) and Punk Up burst sizes (bono: 2-3, never 5)."""
import sys, os, importlib.util
from collections import Counter
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
GRIMM = 648
def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]
def run(a_dir, b_dir, n):
    agentA, deckA = load(a_dir, "pA"); agentB, deckB = load(b_dir, "pB")
    stack_max = Counter(); bursts = Counter(); wins = 0; games = 0
    for g in range(n):
        obs, sd = cggame.battle_start(list(deckA), list(deckB))
        if obs is None: continue
        games += 1; gmax = 0; prev = {}
        try:
            steps = 0
            while steps < 4000:
                cur = obs.get("current") or {}
                r = cur.get("result", -1)
                if r not in (None, -1):
                    if r == 0: wins += 1
                    break
                if obs.get("select") is None: break
                you = cur.get("yourIndex", 0)
                if you == 0:
                    pl = (cur.get("players") or [None, None])[0] or {}
                    m = {}
                    for x in (pl.get("active") or []) + (pl.get("bench") or []):
                        if x: m[x.get("serial")] = (x.get("id"), len(x.get("energies") or []))
                    gains = sum(max(0, en - prev.get(s, (0, 0))[1]) for s, (cid, en) in m.items())
                    if gains >= 2: bursts[gains] += 1
                    for s, (cid, en) in m.items():
                        if cid == GRIMM: gmax = max(gmax, en)
                    prev = m
                w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                     "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
                action = agentA(w) if you == 0 else agentB(w)
                obs = cggame.battle_select([int(a) for a in action]); steps += 1
        finally:
            cggame.battle_finish()
        stack_max[gmax] += 1
    print(f"{os.path.basename(a_dir):<16} vs {os.path.basename(b_dir):<12} ({games}g, WR {wins/max(1,games):.0%}): "
          f"max-stack dist {dict(sorted(stack_max.items()))} | burst sizes {dict(sorted(bursts.items()))}")
run(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 100)
