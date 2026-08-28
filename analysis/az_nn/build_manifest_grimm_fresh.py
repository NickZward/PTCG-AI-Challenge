#!/usr/bin/env python3
"""Manifest for the v19 new-meta fine-tune: WINNING Grimmsnarl sides of the 7 named
teachers from grimm_fresh/ (new-meta window, ep >= 89.5M).

opp_deck tags the NEW archetypes explicitly (Dudunsparce, Meganium) so train_imit_v2's
--boost-opp can weight those slices. Re-runnable mid-scrape (skips unparseable files).

Usage: build_manifest_grimm_fresh.py <out.csv>
"""
import csv, glob, json, os, sys
from collections import Counter

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
ARCH = {648:'Grimmsnarl',743:'Alakazam',533:'Crustle',345:'Crustle',678:'M-Lucario',
        93:'Dipplin',756:'M-Kangaskhan',190:'Archaludon',1031:'M-Starmie',
        381:'Cynthia-Garchomp',121:'Dragapult',401:'Spidops',
        66:'Dudunsparce',306:'Dudunsparce',96:'Meganium',1094:'Meganium'}
# ladder-observed strength of the teachers (drives quality weighting)
WR = {'raihan ramadistra': 0.66, 'カントー地方マスター(kantoregionmaster)': 0.62,
      'szlachetny snieg': 0.60, 'sixth sense': 0.60, '@kdcyberdude': 0.60,
      'palsystem': 0.58, '那个男人': 0.58}

def arch_of(dk):
    c = Counter(dk)
    hits = [(l, c[cid]) for cid, l in ARCH.items() if c.get(cid)]
    return max(hits, key=lambda x: x[1])[0] if hits else 'other'

def main():
    out = sys.argv[1]
    rows, seen = [], set()
    for p in sorted(glob.glob(f"{ROOT}/grimm_fresh/*/*.json")):
        ep = os.path.basename(p).replace('.json', '')
        if ep in seen:
            continue
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        tn = (d.get('info') or {}).get('TeamNames', [])
        rw = d.get('rewards') or [None, None]
        if len(tn) != 2 or rw[0] is None or rw[1] is None or rw[0] == rw[1]:
            continue
        try:
            decks = d['steps'][0][0]['visualize'][0]['action']
            assert isinstance(decks, list) and len(decks) == 2
        except Exception:
            continue
        seen.add(ep)
        w = 0 if rw[0] > rw[1] else 1
        name = tn[w].strip()
        if name.lower() not in WR:
            continue                      # only the teachers' own wins
        if arch_of(decks[w]) != 'Grimmsnarl':
            continue                      # only their Grimm sides
        rows.append(dict(episode=ep, path=p, player=name, side=w, won=1,
                         opp_deck=arch_of(decks[1 - w]), player_winrate=WR[name.lower()],
                         player_games=0, my_deck='Grimmsnarl', src='grimm_fresh'))
    cols = ['episode', 'path', 'player', 'side', 'won', 'opp_deck', 'player_winrate',
            'player_games', 'my_deck', 'src']
    with open(out, 'w', newline='') as f:
        wcsv = csv.DictWriter(f, fieldnames=cols)
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"{len(rows)} winning Grimm teacher-sides -> {out}")
    print("opp mix:", dict(Counter(r['opp_deck'] for r in rows).most_common()))
    print("per teacher:", dict(Counter(r['player'] for r in rows).most_common()))

if __name__ == '__main__':
    main()
