#!/usr/bin/env python3
"""FULL-HISTORY replay scraper for the top-N leaderboard teams.

Why the old scrapers capped out: listing episodes BY TEAM returns only that team's recent
window (~44), and top200_scraper.py then downloaded just the newest few. But listing BY
SUBMISSION returns that submission's episodes, and a team's full history = the union over ALL
its submissions. This tool:

  1. resolves the top-N teams from the official leaderboard (kaggle CLI),
  2. snowball-crawls ListEpisodes to map teamId -> every submissionId ever observed for it
     (current subs come from `teams[].publicLeaderboardSubmissionId`; historical subs are
     harvested from episode agent rows whenever the response schema ties agents to teams),
  3. lists every discovered submission and unions the episode ids per team,
  4. downloads all missing replays via the authed kaggle CLI into one folder per team.

Incremental (existing files skipped), rate-limited, resumable. Run --probe first: it prints the
response schema and per-team episode counts without downloading anything.

Usage:
  python3 scrape_top3_full.py --probe          # verify schema + counts, no downloads
  python3 scrape_top3_full.py                  # full scrape of top 3
  python3 scrape_top3_full.py --teams 5 --out ~/Desktop/scraped_top
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

COMPETITION = "pokemon-tcg-ai-battle"
LIST_URL = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"
HEADERS = {"Content-Type": "application/json"}
SLEEP = 2.5
REPLAY_SLEEP = 8.0     # replay endpoint is strictly rate-limited; be polite
BACKOFF = 65
MAX_CRAWL_CALLS = 80


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def leaderboard_teams(n):
    import io
    import tempfile
    import zipfile
    tmp = tempfile.mkdtemp()
    code, out = run(["kaggle", "competitions", "leaderboard", "-c", COMPETITION,
                     "--download", "-p", tmp])
    if code != 0:
        sys.exit(f"leaderboard download failed — kaggle CLI configured?\n{out}")
    zpath = next(Path(tmp).glob("*.zip"), None)
    if zpath:
        with zipfile.ZipFile(zpath) as z:
            name = next(x for x in z.namelist() if x.endswith(".csv"))
            content = z.read(name).decode("utf-8", "replace")
    else:
        content = next(Path(tmp).glob("*.csv")).read_text("utf-8", errors="replace")
    rows = []
    for row in csv.DictReader(io.StringIO(content)):
        keys = {k.lower(): k for k in row}
        try:
            rows.append((int(row[keys["teamid"]]), row.get(keys.get("teamname", ""), ""),
                         float(row[keys["score"]])))
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda x: -x[2])
    return rows[:n]


def my_seed_submissions():
    code, out = run(["kaggle", "competitions", "submissions", "-c", COMPETITION, "--csv"])
    ids = list(dict.fromkeys(re.findall(r"\b(\d{7,9})\b", out))) if code == 0 else []
    return [int(x) for x in ids[:4]]


def list_episodes_raw(submission_id):
    for attempt in range(4):
        r = requests.post(LIST_URL, headers=HEADERS, timeout=30,
                          data=json.dumps({"ids": [], "submissionId": int(submission_id),
                                           "successfulOnly": True, "includeInProgress": False}))
        if r.status_code == 429:
            print(f"    rate-limited; sleeping {BACKOFF}s...")
            time.sleep(BACKOFF)
            continue
        break
    r.raise_for_status()
    j = r.json()
    if "result" in j and isinstance(j["result"], dict):
        j = j["result"]
    return j


def harvest(j):
    """From one ListEpisodes response: (episode_ids, current_team_subs {tid:sid},
    team_sub_pairs {(tid,sid)} from agent rows when the schema allows, agent_subs [(score,sid)])."""
    eps = j.get("episodes", []) or []
    teams = j.get("teams", []) or []
    current = {t["id"]: t.get("publicLeaderboardSubmissionId")
               for t in teams if t.get("publicLeaderboardSubmissionId")}
    pairs = set()
    agent_subs = []
    for e in eps:
        for a in e.get("agents", []):
            sid = a.get("submissionId")
            if not sid:
                continue
            if a.get("updatedScore") is not None:
                agent_subs.append((a["updatedScore"], sid))
            # team association: kaggle has used several field names across comps
            tid = a.get("teamId") or a.get("team", {}).get("id") if isinstance(a.get("team"), dict) else a.get("teamId")
            if tid:
                pairs.add((tid, sid))
    ep_ids = [e["id"] for e in eps if "id" in e]
    return ep_ids, current, pairs, agent_subs


def fetch_replay(ep_id, out_dir):
    """Download one replay with 429 BACKOFF-AND-RETRY. The first run of this scraper failed
    catastrophically here: a 429 was recorded as a plain failure with NO sleep, so the loop
    hammered the endpoint through ~5,000 episodes in minutes. Never fail-fast on a rate limit."""
    out = out_dir / f"{ep_id}.json"
    if out.exists():
        return "have"
    for attempt in range(5):
        code, msg = run(["kaggle", "competitions", "replay", str(ep_id), "-p", str(out_dir)])
        if code == 0:
            break
        if "429" in msg or "Too Many Requests" in msg:
            wait = min(120 * (2 ** attempt), 900)
            print(f"    429 on {ep_id}; backing off {wait}s (attempt {attempt+1}/5)", flush=True)
            time.sleep(wait)
            continue
        return f"fail:{msg.strip()[:80]}"
    else:
        return "fail:429-exhausted"
    if not out.exists():
        cand = next(out_dir.glob(f"*{ep_id}*.json"), None)
        if cand and cand != out:
            cand.rename(out)
    return "new" if out.exists() else "fail:missing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", type=int, default=3)
    ap.add_argument("--probe", action="store_true", help="schema + counts only, no downloads")
    ap.add_argument("--out", default=str(Path.home() / "Desktop" / "scraped_top"))
    args = ap.parse_args()
    out_root = Path(args.out)

    lb = leaderboard_teams(args.teams)
    targets = {tid: (i + 1, name, score) for i, (tid, name, score) in enumerate(lb)}
    print("TARGETS:")
    for tid, (rank, name, score) in targets.items():
        print(f"  #{rank} {name} (team {tid}, score {score:.1f})")

    # ---- crawl: resolve current submissions + collect historical (team,sub) pairs ----
    team_subs = defaultdict(set)         # tid -> {sid}
    frontier = my_seed_submissions()
    if not frontier:
        sys.exit("no seed submissions — submit an agent first (needed as crawl entry point)")
    seen = set()
    calls = 0
    schema_shown = False
    queue = list(frontier)
    while queue and calls < MAX_CRAWL_CALLS:
        sid = queue.pop(0)
        if sid in seen:
            continue
        seen.add(sid)
        try:
            j = list_episodes_raw(sid)
        except Exception as ex:
            print(f"  ! crawl {sid}: {ex}")
            time.sleep(SLEEP)
            continue
        calls += 1
        if not schema_shown:
            eps = j.get("episodes") or [{}]
            ag = (eps[0].get("agents") or [{}])[0] if eps else {}
            print(f"\nSCHEMA: episode keys={sorted((eps[0] or {}).keys())[:12]}")
            print(f"        agent keys={sorted(ag.keys())}")
            schema_shown = True
        ep_ids, current, pairs, agent_subs = harvest(j)
        for tid, s in current.items():
            if tid in targets:
                team_subs[tid].add(s)
        for tid, s in pairs:
            if tid in targets:
                team_subs[tid].add(s)
        for _, s in sorted(agent_subs, reverse=True):
            if s not in seen:
                queue.append(s)
        resolved = sum(1 for t in targets if team_subs[t])
        if calls % 10 == 0 or resolved == len(targets):
            print(f"crawl {calls}: {resolved}/{len(targets)} targets have >=1 submission")
        if resolved == len(targets) and calls >= 20:
            break
        time.sleep(SLEEP)

    # ---- expand: list every discovered submission of the targets; agent rows in those
    # responses reveal FURTHER submissions of the same team (they appear in their own games) ----
    all_eps = defaultdict(set)           # tid -> {episode ids}
    for tid, (rank, name, score) in sorted(targets.items(), key=lambda x: x[1][0]):
        todo = list(team_subs[tid])
        done = set()
        while todo:
            sid = todo.pop(0)
            if sid in done:
                continue
            done.add(sid)
            try:
                j = list_episodes_raw(sid)
            except Exception as ex:
                print(f"  ! {name} sub {sid}: {ex}")
                time.sleep(SLEEP)
                continue
            ep_ids, current, pairs, _ = harvest(j)
            all_eps[tid].update(ep_ids)
            for t2, s2 in pairs:
                if t2 == tid and s2 not in done:
                    todo.append(s2)
            print(f"  {name}: sub {sid} -> {len(ep_ids)} eps (team total {len(all_eps[tid])}, "
                  f"subs known {len(done | set(todo))})")
            time.sleep(SLEEP)

    print("\nEPISODE TOTALS:")
    for tid, (rank, name, score) in sorted(targets.items(), key=lambda x: x[1][0]):
        print(f"  #{rank} {name}: {len(all_eps[tid])} episodes across {len(team_subs[tid])}+ submissions")

    if args.probe:
        print("\n--probe: stopping before downloads.")
        return

    # ---- download ----
    for tid, (rank, name, score) in sorted(targets.items(), key=lambda x: x[1][0]):
        safe = re.sub(r"[^A-Za-z0-9_. -]", "_", name).strip() or f"team{tid}"
        d = out_root / safe
        d.mkdir(parents=True, exist_ok=True)
        new = have = fail = 0
        eps = sorted(all_eps[tid], reverse=True)
        print(f"\n#{rank} {name}: downloading {len(eps)} episodes -> {d}")
        for i, ep in enumerate(eps):
            res = fetch_replay(ep, d)
            if res == "new":
                new += 1
                time.sleep(REPLAY_SLEEP)
            elif res == "have":
                have += 1
            else:
                fail += 1
                time.sleep(REPLAY_SLEEP)          # failures pace too — never fast-fail the API
                if fail <= 3:
                    print(f"    {ep}: {res}")
                if fail >= 40 and new == 0:
                    print("    aborting this team: persistent failures"); break
            if (i + 1) % 50 == 0:
                print(f"    {i+1}/{len(eps)}  (+{new} new, {have} had, {fail} failed)")
        print(f"  DONE {name}: +{new} new, {have} already had, {fail} failed")

    print("\nAll done.")


if __name__ == "__main__":
    main()
