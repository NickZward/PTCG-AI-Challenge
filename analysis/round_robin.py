#!/usr/bin/env python3
"""ROUND-ROBIN mini-tournament over a STABLE of agents — the validator that correlates with
Kaggle (per top-team practice: play a stable of learned + public rule-based agents against each
other, rank by score). Each pair plays N games (alternating seats), ladder-adjudicated at T14.
Reports each agent's average win-rate across all opponents + the full matrix. Hold agents out of
training (not out of the tournament) to keep validation honest.

Usage: round_robin.py <N> <agent_dir1> <agent_dir2> ...   (or a @file listing dirs)"""
import sys, os, importlib.util
STOP = int(os.environ.get('PTCG_STOP', '14'))  # audit 2026-07-29: ~20% of REAL ladder games run past T14 (max seen 35); use PTCG_STOP=25 for realistic gates
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame

def load(sub, nm):
    # MODULE ISOLATION (2026-08-12): 'mcts_agent'/'np_common'/'nn_common' are process-global
    # names; the FIRST agent loaded claims the cache slot and every later agent silently runs
    # the first agent's search code (measured: one cell read 78%/34%/0% purely by load order).
    # main.py's own guard ('if _HERE not in sys.path: insert') also skips on RE-load when the
    # dir is present but not first. Purge + prime here so EVERY caller is safe, not just
    # field_gauntlet.
    for _mod in ("mcts_agent", "np_common", "nn_common"):
        sys.modules.pop(_mod, None)
    _p = os.path.join(ROOT, sub)
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)
    spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[nm] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(ROOT, sub, "deck.csv")).read().split()]

def play(a0, d0, a1, d1, stop=None, tempo=None):
    stop = STOP if stop is None else stop
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
                if tempo is not None:
                    pr0, pr1 = P[0].get("prize"), P[1].get("prize")
                    if turn <= 8:
                        if pr0: tempo[0] = max(tempo[0], 6 - len(pr0))
                        if pr1: tempo[1] = max(tempo[1], 6 - len(pr1))
                    if len(tempo) > 2 and tempo[2] is None and pr0 and pr1:
                        if 6 - len(pr0) > 0: tempo[2] = 0
                        elif 6 - len(pr1) > 0: tempo[2] = 1
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
    tA, tB = [], []
    cb = {0: [0, 0], 1: [0, 0]}   # sideletter -> [comeback wins, comeback attempts]
    want_tempo = os.environ.get('PTCG_TEMPO') == '1'
    for i in range(n):
        t = [0, 0, None] if want_tempo else None
        if i % 2 == 0:
            r = play(aA, dA, aB, dB, tempo=t); mine = (r == 0)
            a_seat = 0
        else:
            r = play(aB, dB, aA, dA, tempo=t); mine = (r == 1)
            a_seat = 1
        if t is not None:
            tA.append(t[a_seat]); tB.append(t[1 - a_seat])
            if r in (0, 1) and t[2] is not None:
                for side, seat in ((0, a_seat), (1, 1 - a_seat)):
                    if t[2] != seat:                     # this side CONCEDED the first prize
                        cb[side][1] += 1
                        cb[side][0] += (r == seat)
        if r in (0, 1): g += 1; w += mine
    if want_tempo and tA:
        print(f"    TEMPO prizes-by-T8: A={sum(tA)/len(tA):.2f}  B={sum(tB)/len(tB):.2f}", flush=True)
        print(f"    COMEBACK (win after conceding 1st prize): "
              f"A={cb[0][0]}/{cb[0][1]}  B={cb[1][0]}/{cb[1][1]}", flush=True)
    return w, g

def main():
    N = int(sys.argv[1]); dirs = sys.argv[2:]
    if len(dirs) == 1 and dirs[0].startswith("@"):
        dirs = [l.strip() for l in open(dirs[0][1:]) if l.strip() and not l.startswith("#")]
    names = [os.path.basename(d) for d in dirs]
    agents = [load(d, f"rr_{i}") for i, d in enumerate(dirs)]
    m = len(dirs)
    wr = [[None] * m for _ in range(m)]
    print(f"Round-robin: {m} agents, N={N}/pair, {m*(m-1)//2} pairs...", flush=True)
    for i in range(m):
        for j in range(i + 1, m):
            w, g = duel(agents[i][0], agents[i][1], agents[j][0], agents[j][1], N)
            wri = w / max(1, g); wr[i][j] = wri; wr[j][i] = 1 - wri
            print(f"  {names[i]:>16} vs {names[j]:<16} {wri:5.1%}", flush=True)
    print("\n=== STANDINGS (avg WR across the stable) ===")
    avg = [(names[i], sum(wr[i][j] for j in range(m) if j != i) / (m - 1)) for i in range(m)]
    for nm, a in sorted(avg, key=lambda x: -x[1]):
        print(f"  {nm:<18} {a:5.1%}")

if __name__ == "__main__":
    main()
