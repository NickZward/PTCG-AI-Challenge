#!/usr/bin/env python3
"""Local match harness: pit two submission folders against each other."""
import importlib.util
import json
import os
import sys

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
SCRATCH = os.path.dirname(os.path.abspath(__file__))

# one shared cg module (native lib) — loaded from the dipplin workspace
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame


def load_agent(subdir, modname):
    path = os.path.join(subdir, "main.py")
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    deck = [int(x) for x in open(os.path.join(subdir, "deck.csv")).read().split()]
    return mod.agent, deck


def play(agent0, deck0, agent1, deck1, max_steps=4000):
    obs, sd = cggame.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: errPlayer={sd.errorPlayer} errType={sd.errorType}")
    steps = 0
    try:
        while steps < max_steps:
            cur = obs.get("current") or {}
            result = cur.get("result", -1)
            if result is not None and result != -1:
                return result, steps
            if obs.get("select") is None:
                return -2, steps  # no select & no result: stuck
            you = cur.get("yourIndex", 0)
            agent = agent0 if you == 0 else agent1
            wrapped = {
                "current": obs.get("current"),
                "select": obs.get("select"),
                "logs": obs.get("logs", []),
                "step": steps,
                "remainingOverageTime": 600,
                "search_begin_input": obs.get("search_begin_input"),
            }
            action = agent(wrapped)
            obs = cggame.battle_select([int(a) for a in action])
            steps += 1
        return -3, steps  # step cap
    finally:
        cggame.battle_finish()


def main():
    a_dir, b_dir, n = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10
    agent_a, deck_a = load_agent(a_dir, "agent_a")
    agent_b, deck_b = load_agent(b_dir, "agent_b")
    wins = [0, 0]
    odd = 0
    for g in range(n):
        # alternate seats to cancel first-player advantage
        if g % 2 == 0:
            r, steps = play(agent_a, deck_a, agent_b, deck_b)
            winner = {0: "A", 1: "B"}.get(r, "?")
        else:
            r, steps = play(agent_b, deck_b, agent_a, deck_a)
            winner = {0: "B", 1: "A"}.get(r, "?")
        if winner == "A":
            wins[0] += 1
        elif winner == "B":
            wins[1] += 1
        else:
            odd += 1
        print(f"game {g+1}: winner={winner} (r={r}, {steps} selects)", flush=True)
    print(f"\nRESULT  A={a_dir.split('/')[-1]} {wins[0]}  B={b_dir.split('/')[-1]} {wins[1]}  odd={odd}")


if __name__ == "__main__":
    main()
