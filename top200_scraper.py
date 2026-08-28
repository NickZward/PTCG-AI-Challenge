#!/usr/bin/env python3
"""Top-200 episode harvester for the PTCG AI Battle Challenge (v3).

How it works:
  1. Leaderboard (official CLI)          -> top-N team ids + scores
  2. ListEpisodes API (public, no auth)  -> resolves each team's current
     leaderboard submission via a snowball crawl (every response includes a
     `teams[]` array with publicLeaderboardSubmissionId)
  3. ListEpisodes per target submission  -> newest K episode ids
  4. `kaggle competitions replay <id>`   -> official replay download (authed CLI)

Incremental (skips existing files) and rate-limited.

Usage:
  python3 top200_scraper.py                      # top 200 teams, 3 episodes each
  python3 top200_scraper.py --teams 50 --per-team 5
"""

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import requests

COMPETITION = "pokemon-tcg-ai-battle"
OUT_DIR = Path.home() / "Desktop" / "PTCG-AI-Challenge" / "Logs" / "top"
LIST_URL = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"
HEADERS = {"Content-Type": "application/json"}
SLEEP = 2.5          # seconds between ListEpisodes calls
REPLAY_SLEEP = 1.0
BACKOFF = 65         # seconds to wait when rate-limited
MAX_CRAWL_CALLS = 60


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def leaderboard_teams():
    import tempfile
    tmp = tempfile.mkdtemp()
    code, out = run(["kaggle", "competitions", "leaderboard", "-c", COMPETITION,
                     "--download", "-p", tmp])
    if code != 0:
        sys.exit(f"leaderboard download failed — kaggle CLI set up?\n{out}")
    zpath = next(Path(tmp).glob("*.zip"), None)
    if zpath:
        with zipfile.ZipFile(zpath) as z:
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            content = z.read(name).decode("utf-8", "replace")
    else:
        cpath = next(Path(tmp).glob("*.csv"), None)
        if cpath is None:
            sys.exit("no leaderboard file downloaded")
        content = cpath.read_text(encoding="utf-8", errors="replace")
    rows = []
    for row in csv.DictReader(io.StringIO(content)):
        keys = {k.lower(): k for k in row}
        try:
            rows.append((int(row[keys["teamid"]]), row.get(keys.get("teamname", ""), ""),
                         float(row[keys["score"]])))
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda x: -x[2])
    return rows


def my_seed_submissions():
    code, out = run(["kaggle", "competitions", "submissions", "-c", COMPETITION, "--csv"])
    ids = list(dict.fromkeys(re.findall(r"\b(\d{7,9})\b", out))) if code == 0 else []
    return [int(x) for x in ids[:4]]


def list_episodes(submission_id):
    """Returns (episode_ids_newest_first, team_map{teamId:sid}, agent_subs[(score,sid)]).
    Retries with a long backoff when rate-limited (429)."""
    for attempt in range(4):
        r = requests.post(LIST_URL, headers=HEADERS, timeout=30,
                          data=json.dumps({"ids": [], "submissionId": int(submission_id),
                                           "successfulOnly": True, "includeInProgress": False}))
        if r.status_code == 429:
            print(f"    rate-limited; sleeping {BACKOFF}s (attempt {attempt+1}/4)...")
            time.sleep(BACKOFF)
            continue
        break
    r.raise_for_status()
    j = r.json()
    eps = j.get("episodes", []) or j.get("result", {}).get("episodes", [])
    teams = j.get("teams", []) or j.get("result", {}).get("teams", [])
    team_map = {t["id"]: t.get("publicLeaderboardSubmissionId")
                for t in teams if t.get("publicLeaderboardSubmissionId")}
    agent_subs = []
    for e in eps:
        for a in e.get("agents", []):
            if a.get("submissionId") and a.get("updatedScore") is not None:
                agent_subs.append((a["updatedScore"], a["submissionId"]))
    ep_ids = sorted((e["id"] for e in eps if "id" in e), reverse=True)
    return ep_ids, team_map, agent_subs


def fetch_replay_cli(ep_id):
    out = OUT_DIR / f"episode-{ep_id}-replay.json"
    if out.exists():
        return False
    code, msg = run(["kaggle", "competitions", "replay", str(ep_id), "-p", str(OUT_DIR)])
    if code != 0:
        print(f"  ! replay {ep_id} failed: {msg.strip()[:120]}")
        return False
    # normalize filename if the CLI used a different one
    if not out.exists():
        cand = next(OUT_DIR.glob(f"*{ep_id}*.json"), None)
        if cand and cand != out:
            cand.rename(out)
    return out.exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", type=int, default=200)
    ap.add_argument("--per-team", type=int, default=3)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lb = leaderboard_teams()[: args.teams]
    targets = {tid: (i + 1, name, score) for i, (tid, name, score) in enumerate(lb)}
    print(f"Targets: top {len(targets)} teams (scores {lb[0][2]:.0f} .. {lb[-1][2]:.0f})")

    # ---- snowball crawl to resolve teamId -> leaderboard submissionId
    resolved = {}                       # teamId -> submissionId
    ep_cache = {}                       # submissionId -> newest episode ids
    import heapq
    frontier = [(0.0, sid) for sid in my_seed_submissions()]  # (-score, sid)
    if not frontier:
        sys.exit("no seed submissions found — submit at least one agent first")
    heapq.heapify(frontier)
    seen = set()
    calls = 0
    while frontier and calls < MAX_CRAWL_CALLS and len([t for t in targets if t in resolved]) < len(targets):
        _, sid = heapq.heappop(frontier)
        if sid in seen:
            continue
        seen.add(sid)
        try:
            ep_ids, team_map, agent_subs = list_episodes(sid)
        except Exception as ex:
            print(f"  ! crawl {sid}: {ex}")
            time.sleep(SLEEP)
            continue
        calls += 1
        ep_cache[sid] = ep_ids
        resolved.update(team_map)
        # expand toward the highest-rated unexplored submissions first
        for score, sub in agent_subs:
            if sub not in seen:
                heapq.heappush(frontier, (-score, sub))
        hit = len([t for t in targets if t in resolved])
        print(f"crawl {calls}: +{len(team_map)} team mappings ({hit}/{len(targets)} targets resolved)")
        time.sleep(SLEEP)

    # ---- download newest episodes per resolved target team
    index = OUT_DIR / "team_index.csv"
    with open(index, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "team_id", "team_name", "score", "submission_id"])
        for tid, (rank, name, score) in sorted(targets.items(), key=lambda x: x[1][0]):
            w.writerow([rank, tid, name, score, resolved.get(tid, "")])

    got = skipped = 0
    todo = [(rank, name, score, resolved[tid]) for tid, (rank, name, score)
            in sorted(targets.items(), key=lambda x: x[1][0]) if tid in resolved]
    print(f"\nDownloading {args.per_team} newest episodes for {len(todo)} resolved teams...")
    for rank, name, score, sid in todo:
        try:
            ep_ids = ep_cache.get(sid)
            if ep_ids is None:
                ep_ids, tm, _ = list_episodes(sid)
                resolved.update(tm)
                time.sleep(SLEEP)
            fresh = 0
            for ep in ep_ids[: args.per_team]:
                if fetch_replay_cli(ep):
                    fresh += 1
                    got += 1
                    time.sleep(REPLAY_SLEEP)
                else:
                    skipped += 1
            print(f"[#{rank}] {name} ({score:.0f}): {fresh} new")
        except Exception as ex:
            print(f"[#{rank}] {name}: failed ({ex})")

    total = len(list(OUT_DIR.glob("episode-*-replay.json")))
    print(f"\nDone. {got} new replays ({skipped} skipped/existing), {total} total in {OUT_DIR}")


if __name__ == "__main__":
    main()
