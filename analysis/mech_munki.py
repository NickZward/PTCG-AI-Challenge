#!/usr/bin/env python3
"""Mechanism probe: play <agent> vs <opp> N games; measure the fraction of the agent's
Munkidori-online turns where Munkidori has energy (Adrena-Brain requires a {D} energy).
bono real-ladder target ~90%; our v11 was 53%."""
import sys, os, importlib.util
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]

def run(a_dir, b_dir, n):
    agentA, deckA = load(a_dir, "mA"); agentB, deckB = load(b_dir, "mB")
    online_turns = 0; energized_turns = 0
    for g in range(n):
        obs, sd = cggame.battle_start(list(deckA), list(deckB))
        if obs is None: continue
        seen = {}
        try:
            steps = 0
            while steps < 4000:
                cur = obs.get("current") or {}
                if cur.get("result", -1) not in (None, -1): break
                if obs.get("select") is None: break
                you = cur.get("yourIndex", 0)
                wrapped = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                           "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
                if you == 0:  # our (agent A) turn — sample board once per turn
                    turn = cur.get("turn", 0) or 0
                    pl = (cur.get("players") or [None, None])[0] or {}
                    munki = [x for x in (pl.get("active") or []) + (pl.get("bench") or []) if x and x.get("id") == 112]
                    if munki and turn not in seen:
                        seen[turn] = True
                        online_turns += 1
                        if any(len(m.get("energies") or []) > 0 for m in munki):
                            energized_turns += 1
                    action = agentA(wrapped)
                else:
                    action = agentB(wrapped)
                obs = cggame.battle_select([int(a) for a in action]); steps += 1
        finally:
            cggame.battle_finish()
    return online_turns, energized_turns

if __name__ == "__main__":
    a_dir, b_dir = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    on, en = run(a_dir, b_dir, n)
    print(f"{os.path.basename(a_dir)} vs {os.path.basename(b_dir)} ({n} games): "
          f"Munkidori online {on} turns, energized {en} = {en/max(1,on):.0%}  (bono ~90%, v11 real 53%)")
