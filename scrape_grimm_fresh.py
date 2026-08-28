#!/usr/bin/env python3
"""Scrape RECENT games of named top Grimmsnarl pilots (the new-meta teachers).

Same skeleton as scrape_top3_full.py (429 backoff law intact) but: targets are a NAME
list (+ top-N catchall), and only episodes with id >= EP_FLOOR are downloaded — the
new-meta window (Dudunsparce/Meganium era started ~Aug 2, ep ~89.5M).

Usage: scrape_grimm_fresh.py [--probe]
"""
import json, re, subprocess, sys, time
from collections import defaultdict
from pathlib import Path
import requests

sys.path.insert(0, "/Users/nickzwart/Desktop/PTCG-AI-Challenge")
from scrape_top3_full import (COMPETITION, SLEEP, REPLAY_SLEEP, leaderboard_teams,
                              my_seed_submissions, list_episodes_raw, harvest, fetch_replay, run)

TARGET_NAMES = {n.lower() for n in [
    "Raihan Ramadistra", "カントー地方マスター(KantoRegionMaster)", "szlachetny snieg",
    "Sixth Sense", "@kdcyberdude", "palsystem", "那个男人"]}
EP_FLOOR = 89500000          # new-meta window only
PER_TEAM_CAP = 350           # newest first
OUT = Path("/Users/nickzwart/Desktop/PTCG-AI-Challenge/grimm_fresh")

def main():
    probe = "--probe" in sys.argv
    # resolve names -> teamIds from the full leaderboard CSV
    import csv as _csv, io, tempfile, zipfile
    tmp = tempfile.mkdtemp()
    code, out = run(["kaggle", "competitions", "leaderboard", "-c", COMPETITION, "--download", "-p", tmp])
    if code != 0: sys.exit(f"leaderboard failed\n{out}")
    zp = next(Path(tmp).glob("*.zip"), None)
    content = (zipfile.ZipFile(zp).read([n for n in zipfile.ZipFile(zp).namelist() if n.endswith('.csv')][0]).decode('utf-8','replace')
               if zp else next(Path(tmp).glob("*.csv")).read_text('utf-8', errors='replace'))
    targets = {}
    for row in _csv.DictReader(io.StringIO(content)):
        keys = {k.lower(): k for k in row}
        try:
            tid, name = int(row[keys['teamid']]), row.get(keys.get('teamname',''), '')
        except Exception: continue
        if name.strip().lower() in TARGET_NAMES:
            targets[tid] = name.strip()
    print(f"resolved {len(targets)}/{len(TARGET_NAMES)} target teams:")
    for tid, n in targets.items(): print(f"  {n} (team {tid})")

    team_subs = defaultdict(set)
    frontier = my_seed_submissions()
    if not frontier: sys.exit("no seed submissions")
    seen, queue, calls = set(), list(frontier), 0
    while queue and calls < 120:
        sid = queue.pop(0)
        if sid in seen: continue
        seen.add(sid)
        try: j = list_episodes_raw(sid)
        except Exception as ex:
            print(f"  ! crawl {sid}: {ex}"); time.sleep(SLEEP); continue
        calls += 1
        ep_ids, current, pairs, agent_subs = harvest(j)
        for tid, s in list(current.items()) + list(pairs):
            if tid in targets: team_subs[tid].add(s)
        for _, s in sorted(agent_subs, reverse=True):
            if s not in seen: queue.append(s)
        resolved = sum(1 for t in targets if team_subs[t])
        if calls % 10 == 0: print(f"crawl {calls}: {resolved}/{len(targets)} resolved, queue {len(queue)}")
        if resolved == len(targets) and calls >= 25: break
        time.sleep(SLEEP)

    all_eps = defaultdict(set)
    for tid, name in targets.items():
        todo, done = list(team_subs[tid]), set()
        while todo:
            sid = todo.pop(0)
            if sid in done: continue
            done.add(sid)
            try: j = list_episodes_raw(sid)
            except Exception as ex:
                print(f"  ! {name} sub {sid}: {ex}"); time.sleep(SLEEP); continue
            ep_ids, current, pairs, _ = harvest(j)
            fresh = [e for e in ep_ids if e >= EP_FLOOR]
            all_eps[tid].update(fresh)
            for t2, s2 in pairs:
                if t2 == tid and s2 not in done: todo.append(s2)
            print(f"  {name}: sub {sid} -> {len(fresh)} fresh eps (team total {len(all_eps[tid])})")
            time.sleep(SLEEP)

    print("\nFRESH EPISODE TOTALS:")
    for tid, name in targets.items(): print(f"  {name}: {len(all_eps[tid])}")
    if probe: print("--probe: stopping."); return

    for tid, name in targets.items():
        safe = re.sub(r"[^A-Za-z0-9_. -]", "_", name).strip() or f"team{tid}"
        d = OUT / safe; d.mkdir(parents=True, exist_ok=True)
        eps = sorted(all_eps[tid], reverse=True)[:PER_TEAM_CAP]
        new = have = fail = 0
        print(f"\n{name}: downloading {len(eps)} -> {d}", flush=True)
        for i, ep in enumerate(eps):
            res = fetch_replay(ep, d)
            if res == "new": new += 1; time.sleep(REPLAY_SLEEP)
            elif res == "have": have += 1
            else:
                fail += 1; time.sleep(REPLAY_SLEEP)
                if fail >= 40 and new == 0: print("  aborting team: persistent failures"); break
            if (i+1) % 50 == 0: print(f"  {i+1}/{len(eps)} (+{new} new, {fail} fail)", flush=True)
        print(f"  DONE {name}: +{new}, had {have}, fail {fail}", flush=True)
    print("\nAll done.")

if __name__ == "__main__":
    main()
