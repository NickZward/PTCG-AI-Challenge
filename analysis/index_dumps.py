#!/usr/bin/env python3
"""Fast parallel index over raw replay dumps -> one CSV row per game.

40GB of JSON is far too expensive to re-parse per question, so pay it once and write a
compact index: who played, who won, what archetype each side ran, how long it lasted.
Everything downstream (corpus building, pilot win rates, archetype shares) reads the CSV.

Usage: index_dumps.py <out.csv> <dir> [dir2 ...]
"""
import sys, os, json, csv, glob
from multiprocessing import Pool, cpu_count

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"

# card id -> name, loaded once per worker
_NAMES = {}
def _names():
    if not _NAMES:
        with open(os.path.join(ROOT, "pokemon-tcg-ai-battle/EN_Card_Data.csv")) as f:
            for r in csv.DictReader(f):
                c = r["Card ID"].strip()
                if c and c not in _NAMES:
                    _NAMES[c] = r["Card Name"]
    return _NAMES

# Order matters: specific archetype keys BEFORE generic pivot Basics. Bare "Dunsparce" is a
# generic pivot played by many decks and must never be tested before Alakazam.
SIGS = [
    ("M-Kangaskhan", ("Kangaskhan",)), ("M-Lucario", ("Lucario",)),
    ("M-Starmie", ("Starmie",)), ("Grimmsnarl", ("Grimmsnarl", "Impidimp", "Morgrem")),
    ("Ogerpon", ("Ogerpon",)), ("Hydrapple", ("Hydrapple", "Dipplin", "Applin")),
    ("Meganium", ("Meganium", "Bayleef", "Chikorita")),
    ("Alakazam", ("Alakazam", "Kadabra", "Abra")), ("M-Lopunny", ("Lopunny",)),
    ("M-Froslass", ("Froslass",)), ("Dudunsparce", ("Dudunsparce",)),
    ("Dragapult", ("Dragapult", "Drakloak", "Dreepy")),
    ("Crustle", ("Crustle", "Dwebble")), ("Archaludon", ("Archaludon", "Duraludon")),
    ("Charizard", ("Charizard", "Charmeleon")), ("Gholdengo", ("Gholdengo", "Gimmighoul")),
    ("Garchomp", ("Garchomp", "Gabite", "Gible")),
]

def arch_of(ids, N):
    nm = [N.get(str(c), "") for c in ids]
    for a, keys in SIGS:
        for n in nm:
            if any(k in n for k in keys):
                return a
    return "other"


def one(path):
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception:
        return None
    if not isinstance(d, dict):
        return None   # agent-logs files have a list root
    N = _names()
    info = d.get("info") or {}
    teams = info.get("TeamNames") or []
    if len(teams) < 2:
        return None
    rew = d.get("rewards") or [0, 0]
    try:
        win = 0 if (rew[0] or 0) > (rew[1] or 0) else (1 if (rew[1] or 0) > (rew[0] or 0) else -1)
    except Exception:
        win = -1
    steps = d.get("steps") or []
    seen = [set(), set()]
    turn = 0
    for st in steps:
        try:
            cur = (st[0].get("observation") or {}).get("current") or {}
        except Exception:
            continue
        P = cur.get("players")
        if not P or len(P) < 2:
            continue
        t = cur.get("turn") or 0
        if t > turn:
            turn = t
        for si in (0, 1):
            pl = P[si]
            if not pl:
                continue
            for grp in ("active", "bench"):
                for s in (pl.get(grp) or []):
                    if isinstance(s, dict) and s.get("id") is not None:
                        seen[si].add(s["id"])
                        for pe in (s.get("preEvolution") or []):
                            if isinstance(pe, dict) and pe.get("id") is not None:
                                seen[si].add(pe["id"])
            for c in (pl.get("discard") or []):
                if isinstance(c, dict) and c.get("id") is not None:
                    seen[si].add(c["id"])
    return {
        "path": path, "episode": str(info.get("EpisodeId") or ""),
        "p0": teams[0], "p1": teams[1], "winner": win,
        "a0": arch_of(seen[0], N), "a1": arch_of(seen[1], N), "turns": turn,
    }


def main():
    out = sys.argv[1]
    files = []
    for d in sys.argv[2:]:
        files += sorted(glob.glob(os.path.join(d, "*.json")))
    print(f"indexing {len(files)} files with {max(cpu_count()-2,2)} workers...", flush=True)
    rows = []
    with Pool(max(cpu_count() - 2, 2)) as p:
        for i, r in enumerate(p.imap_unordered(one, files, chunksize=8), 1):
            if r:
                rows.append(r)
            if i % 500 == 0:
                print(f"  {i}/{len(files)}", flush=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path","episode","p0","p1","winner","a0","a1","turns"])
        w.writeheader(); w.writerows(rows)
    print(f"wrote {out}: {len(rows)} games")


if __name__ == "__main__":
    main()
