#!/usr/bin/env python3
"""Log grammar census: enumerate every log `type` the engine emits, its field signature,
and sample values. Foundation for outcome extraction (which log event a decision resolves
to). Also cross-references the SelectContext that immediately precedes each log burst.

Usage: log_census.py <replay_folder> [n_games]
"""
import sys, os, json, glob
from collections import defaultdict, Counter

def main():
    folder = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    files = sorted(glob.glob(f"{folder}/*.json"))[:N]
    type_keys = defaultdict(Counter)      # type -> Counter(frozenset(keys))
    type_count = Counter()
    area_vals = defaultdict(Counter)      # field -> Counter(values) for area-like fields
    type_samples = {}
    for f in files:
        try: d = json.load(open(f))
        except Exception: continue
        seen_len = {}
        for step in d['steps']:
            for pi, e in enumerate(step or []):
                if not e: continue
                logs = (e.get('observation') or {}).get('logs') or []
                # only inspect NEW entries per player to avoid recounting cumulative logs
                prev = seen_len.get(pi, 0)
                for L in logs[prev:]:
                    if not isinstance(L, dict): continue
                    ty = L.get('type')
                    type_count[ty] += 1
                    keys = frozenset(k for k in L.keys() if k != 'type')
                    type_keys[ty][keys] += 1
                    for fld in ('fromArea', 'toArea', 'area'):
                        if fld in L: area_vals[fld][L[fld]] += 1
                    if ty not in type_samples:
                        type_samples[ty] = {k: L.get(k) for k in L}
                seen_len[pi] = max(prev, len(logs))
    print(f"=== LOG TYPE CENSUS ({folder}, {len(files)} games) ===")
    for ty, c in type_count.most_common():
        sig = type_keys[ty].most_common(1)[0][0]
        print(f"  type={ty:<3} count={c:<7} keys={sorted(sig)}")
        print(f"        sample={type_samples.get(ty)}")
    print("\n=== AREA-FIELD VALUE DISTRIBUTIONS ===")
    for fld, c in area_vals.items():
        print(f"  {fld}: {dict(c.most_common())}")

if __name__ == "__main__":
    main()
