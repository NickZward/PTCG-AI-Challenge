#!/usr/bin/env python3
"""Manifest of EVERY WINNING SIDE of every game we own — all archetypes, both seats.

For the scaled general-net run: the winner's side of each game is a self-labeling quality
filter (imitate whoever won), and covering all decks gives the net every pilot in the meta —
including the current #1's M-Kangaskhan play and the Crustle/Alakazam sides our Grimm-only
manifests always discarded.

Sources: the day-dump zip (via extract_v2.load_replay's zip fallback) + every replay folder.
Output rows use the extract_v2 manifest schema; my_deck records the winner's archetype.

Usage: build_manifest_allwins.py <out.csv>
"""
import csv
import json
import os
import sys
import zipfile
from collections import Counter

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
ARCH = {648: 'Grimmsnarl', 743: 'Alakazam', 533: 'Crustle', 345: 'Crustle', 678: 'M-Lucario',
        93: 'Dipplin', 756: 'M-Kangaskhan', 190: 'Archaludon', 1031: 'M-Starmie',
        381: 'Cynthia-Garchomp', 121: 'Dragapult', 401: 'Spidops'}

# ladder-proven winrates for the teachers we can name (drives the trainer's quality weighting);
# everyone else gets 0.56 (weight ~0.67 under the quality formula — kept, not crushed)
KNOWN_WR = {'dries @ tufa labs': 0.637, 'flg': 0.652, '__taichicchi__': 0.597,
            'dominic peel': 0.582, 'luca': 0.593, 'liamk': 0.616, 'eggplanck': 0.563,
            'james cox & henry chao': 0.610}
DEFAULT_WR = 0.56

FOLDERS = [f"{ROOT}/flg", "/Users/nickzwart/Desktop/flg_new" if os.path.isdir("/Users/nickzwart/Desktop/flg_new") else f"{ROOT}/flg_new",
           "/Users/nickzwart/Desktop/Dries Tufa Labs", f"{ROOT}/Dries Tufa Labs",
           "/Users/nickzwart/Desktop/LiamK", "/Users/nickzwart/Desktop/James Cox & Henry Chao",
           f"{ROOT}/James Christian", f"{ROOT}/Haggle", "/Users/nickzwart/Desktop/Tonakaiiiii",
           f"{ROOT}/Eggplanck", f"{ROOT}/__Taichicchi__", f"{ROOT}/Dominic Peel", f"{ROOT}/Luca"]


def arch_of(dk):
    c = Counter(dk)
    hits = [(l, c[cid]) for cid, l in ARCH.items() if c.get(cid)]
    return max(hits, key=lambda x: x[1])[0] if hits else 'other'


def rows_from_game(d, path, ep, src):
    tn = d.get('info', {}).get('TeamNames', [])
    rw = d.get('rewards') or [None, None]
    if len(tn) != 2 or rw[0] is None or rw[1] is None or rw[0] == rw[1]:
        return []
    try:
        decks = d['steps'][0][0]['visualize'][0]['action']
        assert isinstance(decks, list) and len(decks) == 2
    except Exception:
        return []
    winner = 0 if rw[0] > rw[1] else 1
    a = [arch_of(decks[0]), arch_of(decks[1])]
    name = tn[winner].strip()
    wr = KNOWN_WR.get(name.lower(), DEFAULT_WR)
    return [dict(episode=ep, path=path, player=name, side=winner, won=1,
                 opp_deck=a[1 - winner], player_winrate=wr, player_games=0,
                 my_deck=a[winner], src=src)]


def main():
    out = sys.argv[1]
    rows = []
    seen = set()

    # ---- day-dump zip: iterate members, write ROOT-relative paths (load_replay resolves) ----
    zp = os.path.join(ROOT, "20260722:23:24.zip")
    z = zipfile.ZipFile(zp)
    members = [n for n in z.namelist() if n.endswith('.json') and '__MACOSX' not in n]
    print(f"zip: {len(members)} replays")
    for i, m in enumerate(members):
        ep = os.path.basename(m).replace('.json', '')
        if ep in seen:
            continue
        try:
            with z.open(m) as f:
                d = json.load(f)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        seen.add(ep)
        rows += rows_from_game(d, os.path.join(ROOT, m), ep, 'dump')
        if (i + 1) % 2000 == 0:
            print(f"  zip {i+1}/{len(members)} -> {len(rows)} winning sides", flush=True)

    # ---- folders ----
    for D in FOLDERS:
        if not os.path.isdir(D):
            continue
        added = 0
        for fn in sorted(os.listdir(D)):
            if not fn.endswith('.json') or 'logs' in fn:
                continue
            ep = fn.replace('-replay.json', '').replace('episode-', '').replace('.json', '').split('(')[0]
            if ep in seen:
                continue
            p = os.path.join(D, fn)
            try:
                d = json.load(open(p))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            seen.add(ep)
            r = rows_from_game(d, p, ep, os.path.basename(D))
            rows += r
            added += len(r)
        print(f"{os.path.basename(D):26s} +{added}")

    cols = ['episode', 'path', 'player', 'side', 'won', 'opp_deck', 'player_winrate',
            'player_games', 'my_deck', 'src']
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    decks = Counter(r['my_deck'] for r in rows)
    print(f"\nDONE: {len(rows)} winning sides -> {out}")
    print("winner-deck mix:", dict(decks.most_common()))


if __name__ == '__main__':
    main()
