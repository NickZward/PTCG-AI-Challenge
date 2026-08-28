#!/usr/bin/env python3
"""Parallel validation via INDEPENDENT subprocesses (no multiprocessing.Pool — that deadlocks with
torch+ctypes on macOS). Each matchup is a fresh `round_robin.py` process; a thread pool runs ~7 at
once (threads just wait on subprocesses, so they truly parallelize across cores).

Compares grimm_nn0 (learned) vs grimmsnarl_v17 (rules) on the same panel + a head-to-head.
Usage: validate_par.py [N_panel=40] [N_hh=60] [search=6]
"""
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
PANEL = [
    ("bc_crustle",  "my-agent/bc_crustle", "REAL"),      # the honest opponent (v17=42.5%, grimm_az0=52.5%)
    ("bc_majkel",   "my-agent/bc_majkel", "held"),       # Alakazam clone
    ("crustle_bot", "my-agent/gauntlet/crustle", "held"),
]
CONTESTANTS = [("grimm_nnT", "my-agent/grimm_nnT"), ("v17", "my-agent/grimmsnarl_v17")]


def run_pair(job):
    label, cdir, odir, n, search = job
    env = dict(os.environ, GRIMM_NN_SEARCH=str(search))
    try:
        out = subprocess.run([sys.executable, "analysis/round_robin.py", str(n), cdir, odir],
                             cwd=ROOT, capture_output=True, text=True, env=env, timeout=1200).stdout
    except subprocess.TimeoutExpired:
        return label, float("nan")
    # first "vs" line = contestant's WR vs opponent
    m = re.search(r"\bvs\b\s+\S+\s+([0-9.]+)%", out)
    return label, (float(m.group(1)) if m else float("nan"))


def main():
    n_panel = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    n_hh = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    search = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    jobs = []
    for cn, cd in CONTESTANTS:
        for on, od, _ in PANEL:
            jobs.append((f"{cn}|{on}", cd, od, n_panel, search))
    jobs.append(("HH|grimm_vs_v17", "my-agent/grimm_nnT", "my-agent/grimmsnarl_v17", n_hh, search))
    print(f"validating {len(jobs)} matchups, N={n_panel}/panel {n_hh}/hh, search={search} ...", flush=True)

    with ThreadPoolExecutor(max_workers=7) as ex:
        res = dict(ex.map(run_pair, jobs))

    cn0 = CONTESTANTS[0][0]
    print(f"\n=== win-rate: {cn0} (LEARNED) vs v17 (RULES), same opponents ===")
    print(f"{'opponent':<13}{cn0:>10}{'v17':>9}{'delta':>9}  tag")
    gs = vs_ = 0.0
    gc = vc = 0
    for on, _, tag in PANEL:
        g = res.get(f"{cn0}|{on}", float("nan"))
        v = res.get(f"v17|{on}", float("nan"))
        d = g - v
        print(f"{on:<13}{g:>9.1f}%{v:>8.1f}%{d:>+8.1f}  {tag}")
        if g == g:
            gs += g; gc += 1
        if v == v:
            vs_ += v; vc += 1
    print(f"{'AVG':<13}{gs/max(1,gc):>9.1f}%{vs_/max(1,vc):>8.1f}%{(gs/max(1,gc)-vs_/max(1,vc)):>+8.1f}")
    hh = res.get("HH|grimm_vs_v17", float("nan"))
    verdict = "LEARNED BEATS RULES" if hh == hh and hh > 50 else ("rules hold" if hh == hh else "n/a")
    print(f"\nHEAD-TO-HEAD {cn0} vs v17: {hh:.1f}%  => {verdict}")


if __name__ == "__main__":
    main()
