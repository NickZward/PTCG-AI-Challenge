#!/usr/bin/env python3
"""Parallel validation of the learned Grimmsnarl (grimm_nn0) vs the best rules (grimmsnarl_v17).

Runs BOTH contestants against the same panel (curriculum + held-out) across CPU cores, plus a
grimm_nn0-vs-v17 head-to-head. T14-adjudicated, alternating seats. Reports per-matchup WR side by
side (so we see exactly where learning helped) + panel-average + the head-to-head verdict.

Usage: validate_nn.py [N_panel=40] [N_head2head=60]   (env GRIMM_NN_SEARCH sets MCTS sims, default 10)
"""
import importlib.util
import os
import random
import sys
from multiprocessing import Pool

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))  # cg engine
from cg import game as cggame

PANEL = [
    ("mlucario",   "my-agent/gauntlet/mlucario"),    # curriculum (trained-against)
    ("crustle",    "my-agent/gauntlet/crustle"),     # curriculum (trained-against)
    ("starmie",    "my-agent/gauntlet/starmie"),     # held-out
    ("archaludon", "my-agent/gauntlet/archaludon"),  # held-out (800s wall)
    ("okidogi",    "my-agent/gauntlet/okidogi"),     # held-out
    ("dragapult",  "my-agent/pool/dragapult_v1"),    # held-out
    ("alakazam20", "my-agent/alakazam_v20"),         # held-out (strong rules Ala)
    ("bc_yushin",  "my-agent/bc_yushin"),            # held-out (BC clone)
    ("bc_bono",    "my-agent/bc_bono"),              # held-out (BC clone of #1)
]
CONTESTANTS = [("grimm_nn0", "my-agent/grimm_nn0"), ("v17", "my-agent/grimmsnarl_v17")]


def load(sub, nm):
    spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, sub, "main.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[nm] = m
    spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(ROOT, sub, "deck.csv")).read().split()]


def play(a0, d0, a1, d1, stop=14):
    obs, _ = cggame.battle_start(list(d0), list(d1))
    if obs is None:
        return -2
    steps, last = 0, None
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            if r not in (None, -1):
                return r
            if obs.get("select") is None:
                return -2
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
            obs = cggame.battle_select([int(a) for a in ag(w)])
            steps += 1
        return -3
    finally:
        cggame.battle_finish()


def worker(args):
    label, dirA, dirB, n, seed0 = args
    aA, dA = load(dirA, "cA")
    aB, dB = load(dirB, "cB")
    w = g = 0
    for i in range(n):
        random.seed(seed0 + i)
        if i % 2 == 0:
            r = play(aA, dA, aB, dB); mine = (r == 0)
        else:
            r = play(aB, dB, aA, dA); mine = (r == 1)
        if r in (0, 1):
            g += 1
            w += mine
    return (label, w, g)


def main():
    n_panel = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    n_hh = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    jobs = []
    for cn, cd in CONTESTANTS:
        for on, od in PANEL:
            jobs.append((f"{cn}|{on}", cd, od, n_panel, (hash(cn + on) % 90000) + 1))
    jobs.append(("HH|grimm_nn0_vs_v17", "my-agent/grimm_nn0", "my-agent/grimmsnarl_v17", n_hh, 4242))
    print(f"validating: {len(jobs)} matchups, N={n_panel}/panel {n_hh}/head-to-head, "
          f"search={os.environ.get('GRIMM_NN_SEARCH','10')}", flush=True)

    with Pool(min(7, os.cpu_count() or 4)) as p:
        res = dict((lbl, (w, g)) for lbl, w, g in p.map(worker, jobs))

    def wr(cn, on):
        w, g = res.get(f"{cn}|{on}", (0, 0))
        return (w / g if g else float("nan")), g

    print("\n=== per-matchup win-rate (grimm_nn0 learned  vs  v17 rules) ===")
    print(f"{'opponent':<12} {'grimm_nn0':>10} {'v17':>8} {'delta':>8}   (n)")
    gn_tot = v_tot = gn_g = v_g = 0.0
    gn_cnt = v_cnt = 0
    for on, _ in PANEL:
        (gwr, gg) = wr("grimm_nn0", on)
        (vwr, vg) = wr("v17", on)
        d = (gwr - vwr) * 100
        tag = "curr" if on in ("mlucario", "crustle") else "held"
        print(f"{on:<12} {gwr*100:>9.1f}% {vwr*100:>7.1f}% {d:>+7.1f}   ({gg}/{vg}) {tag}")
        if gg:
            gn_tot += gwr; gn_cnt += 1
        if vg:
            v_tot += vwr; v_cnt += 1
    print(f"{'AVG':<12} {gn_tot/max(1,gn_cnt)*100:>9.1f}% {v_tot/max(1,v_cnt)*100:>7.1f}% "
          f"{(gn_tot/max(1,gn_cnt)-v_tot/max(1,v_cnt))*100:>+7.1f}")
    hw, hg = res.get("HH|grimm_nn0_vs_v17", (0, 0))
    print(f"\n=== HEAD-TO-HEAD  grimm_nn0 vs v17: {hw}/{hg} = {hw/max(1,hg)*100:.1f}%  "
          f"({'LEARNED beats rules' if hg and hw/hg > 0.5 else 'rules hold'}) ===")


if __name__ == "__main__":
    main()
