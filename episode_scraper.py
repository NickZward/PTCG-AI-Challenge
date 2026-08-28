#!/usr/bin/env python3
"""Incremental episode downloader for the PTCG AI Battle Challenge.

Pulls every episode (replay + your agent logs) for all of your submissions,
skipping files you already have. Safe to run as often as you like.

One-time setup (requires your own Kaggle API token — keep it private):
  1. pip3 install kaggle
  2. kaggle.com -> Settings -> API -> "Create New Token" (downloads kaggle.json)
  3. mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json

Usage:
  python3 episode_scraper.py                 # asks which agent, then fetches
  python3 episode_scraper.py --agent 1 --name "Alakazam V20"   # non-interactive
  python3 episode_scraper.py --agent both --name "Alakazam V20" "Grimmsnarl V22"
  python3 episode_scraper.py --extra 86478596 86479141   # also grab specific
                                             # episode IDs (e.g. top players')

You pick which of your two active submissions to scrape:
  1     -> agent 1 (your most recent submission), e.g. "Alakazam V20"
  2     -> agent 2 (the one before it)
  both  -> both of them
Each agent's files land in a folder on your Desktop named after that agent.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

COMPETITION = "pokemon-tcg-ai-battle"
DESKTOP = Path.home() / "Desktop"


def out_dir_for(name):
    """Folder on the Desktop named after the agent (e.g. ~/Desktop/Alakazam V20)."""
    return DESKTOP / name.strip()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def my_submission_ids():
    """Parse submission IDs out of `kaggle competitions submissions`."""
    code, out = run(["kaggle", "competitions", "submissions", "-c", COMPETITION, "--csv"])
    if code != 0:
        sys.exit(f"Could not list submissions — is the kaggle CLI set up?\n{out}")
    ids = re.findall(r"(?m)^(\d{6,}),", out)
    if not ids:  # fallback: any long number per line
        ids = list(dict.fromkeys(re.findall(r"\b(\d{7,9})\b", out)))
    return list(dict.fromkeys(ids))


def episodes_for_submission(sub_id):
    code, out = run(["kaggle", "competitions", "episodes", str(sub_id)])
    if code != 0:
        print(f"  ! could not list episodes for submission {sub_id}: {out.strip()[:200]}")
        return []
    return list(dict.fromkeys(re.findall(r"\b(\d{8,9})\b", out)))


def fetch_episode(ep_id, out_dir):
    got_any = False
    replay = out_dir / f"episode-{ep_id}-replay.json"
    if not replay.exists():
        code, out = run(["kaggle", "competitions", "replay", str(ep_id), "-p", str(out_dir)])
        if code == 0:
            got_any = True
            print(f"  + replay {ep_id}")
        else:
            print(f"  ! replay {ep_id} failed: {out.strip()[:150]}")
    for idx in (0, 1):
        log = out_dir / f"episode-{ep_id}-agent-{idx}-logs.json"
        if not log.exists():
            code, out = run(["kaggle", "competitions", "logs", str(ep_id), str(idx), "-p", str(out_dir)])
            if code == 0:
                got_any = True
                print(f"  + logs   {ep_id} agent {idx}")
            # logs for the opponent's seat aren't downloadable — silently skip
    return got_any


def scrape_agent(sub_id, name, extra=()):
    """Fetch every episode for one submission into ~/Desktop/<name>/."""
    out_dir = out_dir_for(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {name}  (submission {sub_id}) ===")
    print(f"Saving into {out_dir}")

    eps = episodes_for_submission(sub_id)
    print(f"  {len(eps)} episodes")
    all_eps = list(dict.fromkeys(eps + [str(e) for e in extra]))

    new = 0
    for ep in all_eps:
        if fetch_episode(ep, out_dir):
            new += 1
    have = len(list(out_dir.glob("episode-*-replay.json")))
    print(f"  Done: {new} episodes updated, {have} replays total in {out_dir}")


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["1", "2", "both"],
                    help="which of your two active submissions to scrape (1=newest, 2=next, both)")
    ap.add_argument("--name", nargs="*", default=[],
                    help="agent name(s) used to name the Desktop folder(s), "
                         "e.g. --name \"Alakazam V20\"  (give two names with --agent both)")
    ap.add_argument("--extra", nargs="*", default=[], help="additional episode IDs to fetch")
    args = ap.parse_args()

    # newest-first: subs[0] = agent 1, subs[1] = agent 2 (the active pair)
    subs = my_submission_ids()[:2]
    if len(subs) < 2:
        sys.exit(f"Expected 2 active submissions, found {len(subs)}: {subs}")

    choice = args.agent or ask("Which agent do you want to scrape? [1 / 2 / both]: ").lower()
    if choice not in ("1", "2", "both"):
        sys.exit(f"Invalid choice: {choice!r} (expected 1, 2, or both)")

    if choice == "both":
        names = list(args.name)
        while len(names) < 2:
            n = ask(f"Name for agent {len(names) + 1} (submission {subs[len(names)]}): ")
            if not n:
                sys.exit("A name is required for each agent.")
            names.append(n)
        scrape_agent(subs[0], names[0], extra=args.extra)
        scrape_agent(subs[1], names[1], extra=args.extra)
    else:
        idx = 0 if choice == "1" else 1
        name = args.name[0] if args.name else ask(
            f"Name for agent {choice} (submission {subs[idx]}), e.g. Alakazam V20: ")
        if not name:
            sys.exit("A name is required.")
        scrape_agent(subs[idx], name, extra=args.extra)


if __name__ == "__main__":
    main()
