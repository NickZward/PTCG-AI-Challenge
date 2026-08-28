#!/usr/bin/env python3
"""LADDER-FAITHFUL harness: games are adjudicated the way the real ladder decides them
(discovered empirically over 88 live games, 2026-07-23): games stop early (wall-clock ~turn
13-14); at the stop the PRIZE LEADER wins (83% of endings), deckout = instant loss, ties
break on deck size. The old harness played to completion, over-punishing deck-spending that
the ladder never punishes — gates must score THIS game, not endurance chess.

Usage: harness_adj.py <A_dir> <B_dir> [games] [stop_turn=14]"""
import importlib.util, json, os, sys
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
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

def play(agent0, deck0, agent1, deck1, stop_turn=14, max_steps=4000):
    obs, sd = cggame.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError("battle_start failed")
    steps = 0
    last = None
    try:
        while steps < max_steps:
            cur = obs.get("current") or {}
            result = cur.get("result", -1)
            if result is not None and result != -1:
                return result, steps            # real board result (incl deckout)
            if obs.get("select") is None:
                return -2, steps
            turn = cur.get("turn", 0) or 0
            P = cur.get("players")
            if P and P[0] and P[1]:
                last = (6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or []),
                        P[0].get("deckCount") or 0, P[1].get("deckCount") or 0)
            if turn > stop_turn and last is not None:
                # LADDER ADJUDICATION: prize lead, then deck size, else draw (-4)
                p0, p1, d0, d1 = last
                if p0 != p1: return (0 if p0 > p1 else 1), steps
                if d0 != d1: return (0 if d0 > d1 else 1), steps
                return -4, steps
            you = cur.get("yourIndex", 0)
            agent = agent0 if you == 0 else agent1
            wrapped = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                       "step": steps, "remainingOverageTime": 600,
                       "search_begin_input": obs.get("search_begin_input")}
            action = agent(wrapped)
            obs = cggame.battle_select([int(a) for a in action])
            steps += 1
        return -3, steps
    finally:
        cggame.battle_finish()

def main():
    a_dir, b_dir = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    stop = int(sys.argv[4]) if len(sys.argv) > 4 else 14
    agent_a, deck_a = load_agent(a_dir, "adj_a")
    agent_b, deck_b = load_agent(b_dir, "adj_b")
    wins = [0, 0]; odd = 0
    for g in range(n):
        if g % 2 == 0:
            r, _ = play(agent_a, deck_a, agent_b, deck_b, stop)
            w = {0: "A", 1: "B"}.get(r, "?")
        else:
            r, _ = play(agent_b, deck_b, agent_a, deck_a, stop)
            w = {0: "B", 1: "A"}.get(r, "?")
        if w == "A": wins[0] += 1
        elif w == "B": wins[1] += 1
        else: odd += 1
    print(f"ADJ-RESULT  A={a_dir.split('/')[-1]} {wins[0]}  B={b_dir.split('/')[-1]} {wins[1]}  odd={odd}")

if __name__ == "__main__":
    main()
