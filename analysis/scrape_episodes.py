#!/usr/bin/env python3
"""Scrape Kaggle episode replays via the public EpisodeService API.

Usage: scrape_episodes.py <outdir> <ids.json | id1,id2,...>
Writes episode-<id>-replay.json (same shape as the manual dump files).
Rate-limited to ~1 req/0.7s; skips files that already exist.
"""
import json, os, sys, time, urllib.request

URL = "https://www.kaggleusercontent.com/episodes/{eid}.json"

def fetch(eid):
    req = urllib.request.Request(
        URL.format(eid=eid), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def main():
    out, arg = sys.argv[1], sys.argv[2]
    ids = json.load(open(arg)) if arg.endswith(".json") else [int(x) for x in arg.split(",")]
    os.makedirs(out, exist_ok=True)
    ok = skip = fail = 0
    for i, eid in enumerate(ids, 1):
        p = os.path.join(out, f"episode-{eid}-replay.json")
        if os.path.exists(p):
            skip += 1; continue
        try:
            rep = fetch(eid)
            if not rep or "steps" not in rep:
                fail += 1; print(f"  {eid}: empty/invalid", flush=True); continue
            json.dump(rep, open(p, "w"))
            ok += 1
        except Exception as e:
            fail += 1; print(f"  {eid}: {e}", flush=True)
        if i % 10 == 0:
            print(f"  {i}/{len(ids)} (ok {ok})", flush=True)
        time.sleep(0.7)
    print(f"done: {ok} fetched, {skip} skipped, {fail} failed")

if __name__ == "__main__":
    main()
