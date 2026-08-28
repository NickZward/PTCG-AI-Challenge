#!/usr/bin/env python3
"""Build manifest rows for a folder of raw Kaggle replay JSONs belonging to one named player.

Emits the same schema as grimm_train_manifest.csv:
    episode,path,player,side,won,opp_deck,player_winrate,player_games
plus two extra columns the old manifest lacked (harmless for the old reader, useful for weighting):
    my_deck      -- archetype the LISTED player actually piloted in that game
    src          -- folder tag

Only rows where the listed player piloted the deck we are training (default Grimmsnarl) are kept;
mirror games are kept once per listed player (both sides only if both are listed players).

Usage:  build_manifest_folders.py out.csv "<dir>=<player>" ["<dir>=<player>" ...]
"""
import csv
import json
import os
import sys
from collections import Counter

# archetype signature card -> label  (same table as analysis/digest.py)
ARCH = {648: 'Grimmsnarl', 743: 'Alakazam', 533: 'Crustle', 345: 'Crustle', 678: 'M-Lucario',
        93: 'Dipplin', 756: 'M-Kangaskhan', 190: 'Archaludon', 1031: 'M-Starmie',
        381: 'Cynthia-Garchomp', 121: 'Dragapult'}

TARGET = 'Grimmsnarl'


def arch_of(deck):
    c = Counter(deck)
    return next((lab for cid, lab in ARCH.items() if c.get(cid)), 'other')


def decks_of(replay):
    """Both players' 60-card lists, from the seat-0 visualize payload."""
    try:
        act = replay['steps'][0][0]['visualize'][0]['action']
        if isinstance(act, list) and len(act) == 2 and isinstance(act[0], list):
            return act[0], act[1]
    except Exception:
        pass
    return None, None


def rows_for_folder(folder, player, wr, games):
    out = []
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith('.json'):
            continue
        path = os.path.join(folder, fn)
        try:
            r = json.load(open(path))
        except Exception:
            continue
        if not isinstance(r, dict):        # agent-logs files are JSON lists — skip them
            continue
        names = (r.get('info') or {}).get('TeamNames') or []
        if len(names) != 2:
            continue
        d0, d1 = decks_of(r)
        if d0 is None:
            continue
        a = [arch_of(d0), arch_of(d1)]
        rw = r.get('rewards') or []
        for seat in (0, 1):
            if names[seat].strip().lower() != player.strip().lower():
                continue
            if a[seat] != TARGET:
                continue
            won = 1 if (len(rw) == 2 and rw[seat] is not None and rw[1 - seat] is not None
                        and rw[seat] > rw[1 - seat]) else 0
            out.append({
                'episode': os.path.splitext(fn)[0],
                'path': path,
                'player': player,
                'side': seat,
                'won': won,
                'opp_deck': a[1 - seat],
                'player_winrate': wr,
                'player_games': games,
                'my_deck': a[seat],
                'src': os.path.basename(folder.rstrip('/')),
            })
    return out


def main():
    out_path = sys.argv[1]
    # player winrate/games carried over from the existing manifest where known
    KNOWN = {}
    old = '/Users/nickzwart/Desktop/grimm_train_manifest.csv'
    if os.path.exists(old):
        for row in csv.DictReader(open(old)):
            KNOWN[row['player']] = (row['player_winrate'], row['player_games'])

    rows = []
    for spec in sys.argv[2:]:
        folder, player = spec.rsplit('=', 1)
        wr, games = KNOWN.get(player, ('', ''))
        rs = rows_for_folder(folder, player, wr, games)
        kept = Counter(r['opp_deck'] for r in rs)
        print(f"{player:20s} {folder}: {len(rs)} {TARGET} rows  opp={dict(kept)}  "
              f"wins={sum(r['won'] for r in rs)}", flush=True)
        rows += rs

    cols = ['episode', 'path', 'player', 'side', 'won', 'opp_deck',
            'player_winrate', 'player_games', 'my_deck', 'src']
    with open(out_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"DONE: {len(rows)} rows -> {out_path}")


if __name__ == '__main__':
    main()
