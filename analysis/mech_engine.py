#!/usr/bin/env python3
"""Full engine-loop mechanism probe: play <agent> vs <opp> N games; measure the Munkidori
counter-engine metrics that separate bono (5.47 fires/game, 90% energized, 97% of games
energized, 0.39 deaths/game) from our live v12r (1.43 / 43% / 70% / 0.70)."""
import sys, os, importlib.util
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
MUNKI = 112

def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]

def run(a_dir, b_dir, n):
    agentA, deckA = load(a_dir, "meA"); agentB, deckB = load(b_dir, "meB")
    fires = 0; on_t = 0; en_t = 0; games = 0; wins = 0; ever_en = 0; deaths = 0
    for g in range(n):
        obs, sd = cggame.battle_start(list(deckA), list(deckB))
        if obs is None: continue
        games += 1
        seen = {}; was_en = False; prev_serials = {}
        try:
            steps = 0
            while steps < 4000:
                cur = obs.get("current") or {}
                r = cur.get("result", -1)
                if r not in (None, -1):
                    if r == 0: wins += 1
                    break
                sel = obs.get("select")
                if sel is None: break
                you = cur.get("yourIndex", 0)
                w = {"current": cur, "select": sel, "logs": obs.get("logs", []),
                     "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
                if you == 0:
                    if sel.get("type") == 1 and sel.get("context") == 16:
                        fires += 1
                    turn = cur.get("turn", 0) or 0
                    pl = (cur.get("players") or [None, None])[0] or {}
                    munki = {x.get("serial"): len(x.get("energies") or [])
                             for x in (pl.get("active") or []) + (pl.get("bench") or [])
                             if x and x.get("id") == MUNKI}
                    if munki and turn not in seen:
                        seen[turn] = True; on_t += 1
                        if any(v > 0 for v in munki.values()):
                            en_t += 1; was_en = True
                    for s in prev_serials:
                        if s not in munki and prev_serials[s] is not None:
                            deaths += 1
                    prev_serials = dict(munki)
                    action = agentA(w)
                else:
                    action = agentB(w)
                obs = cggame.battle_select([int(a) for a in action]); steps += 1
        finally:
            cggame.battle_finish()
        if was_en: ever_en += 1
    g = max(1, games)
    print(f"{os.path.basename(a_dir):<16} vs {os.path.basename(b_dir):<12} ({games}g): "
          f"WR {wins/g:.0%} | fires {fires/g:.2f}/g | energized {en_t}/{on_t}={en_t/max(1,on_t):.0%} "
          f"| ever-energized {ever_en}/{games} | munki-deaths {deaths/g:.2f}/g")

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 100)
