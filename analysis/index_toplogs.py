#!/usr/bin/env python3
"""Index the Top_logs corpus (79k top-player replays, 269GB) into one compact JSONL:
per game — episode, day, players, full 60-card decks, archetypes, winner, length.
Everything downstream (meta matrix, top-pilot leaderboards, matchup mining, imitation
corpora) queries this index instead of re-scanning 269GB.

Usage: index_toplogs.py [out.jsonl]   (multiprocess, ~all cores)"""
import sys, os, json, glob
from multiprocessing import Pool
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
SRC = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "Top_logs")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "model/toplogs_index.jsonl")

SIG = {648:'Grimmsnarl',743:'Alakazam',533:'Crustle',345:'Crustle',678:'M-Lucario',
       93:'Dipplin',756:'M-Kangaskhan',190:'Archaludon',1031:'M-Starmie',381:'Cynthia-Garchomp',
       121:'Dragapult',245:'TR-Mewtwo',723:'M-Gengar?',66:'?66'}

def arch(deck):
    from collections import Counter
    c = Counter(deck)
    for cid, label in SIG.items():
        if c.get(cid): return label
    return 'other'

def one(path):
    try:
        d = json.load(open(path))
        info = d.get('info') or {}
        names = info.get('TeamNames') or [None, None]
        rw = d.get('rewards')
        decks = d['steps'][0][0]['visualize'][0]['action']
        day = os.path.basename(os.path.dirname(path))
        ep = int(os.path.basename(path).split('.')[0])
        winner = 0 if rw == [1, -1] else (1 if rw == [-1, 1] else -1)
        return json.dumps({
            'ep': ep, 'day': day, 'names': names, 'winner': winner,
            'arch': [arch(decks[0]), arch(decks[1])],
            'decks': decks, 'n_steps': len(d.get('steps') or []),
        })
    except Exception:
        return None

def main():
    files = sorted(glob.glob(os.path.join(SRC, '*/*.json')))
    print(f"indexing {len(files)} files -> {OUT}", flush=True)
    n = 0
    with Pool(max(2, os.cpu_count() - 2)) as pool, open(OUT, 'w') as f:
        for i, line in enumerate(pool.imap_unordered(one, files, chunksize=16)):
            if line: f.write(line + "\n"); n += 1
            if (i + 1) % 5000 == 0: print(f"  {i+1}/{len(files)} ({n} ok)", flush=True)
    print(f"done: {n}/{len(files)} indexed", flush=True)

if __name__ == "__main__":
    main()
