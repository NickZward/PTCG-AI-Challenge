#!/usr/bin/env python3
"""Parallel knob sweep on the adjudicated field proxy (now calibrated coarse-valid vs ladder
peaks — resolves differences >~3pp; smaller = noise). For each config variant, stamp a
params.json into a temp copy of the agent dir and run field_eval_adj; compare to baseline.

Usage: sweep_knob.py <base_agent_dir> <spec.json> [N=250] [reps=1]
  spec.json = {"variants": [{"label": "...", "params": {"KNOB": val, ...}}, ...]}
Prints each variant's field score (mean over reps), sorted; baseline = empty-params variant."""
import sys, os, json, tempfile, shutil, subprocess, re
from multiprocessing import Pool
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"

def run_one(args):
    base_dir, label, params, N, rep = args
    tmp = tempfile.mkdtemp(prefix="sweep_")
    try:
        shutil.copy(os.path.join(base_dir, "main.py"), os.path.join(tmp, "main.py"))
        shutil.copy(os.path.join(base_dir, "deck.csv"), os.path.join(tmp, "deck.csv"))
        if params:
            json.dump(params, open(os.path.join(tmp, "params.json"), "w"))
        r = subprocess.run(["python3", os.path.join(ROOT, "analysis/field_eval_adj.py"), tmp, str(N)],
                           capture_output=True, text=True, cwd=ROOT, timeout=1200)
        m = re.search(r"FIELD SCORE:\s*([0-9.]+)%", r.stdout)
        return (label, float(m.group(1)) if m else None, rep)
    except Exception as e:
        return (label, None, rep)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    base_dir = sys.argv[1]; spec = json.load(open(sys.argv[2]))
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 250
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    variants = spec["variants"]
    jobs = []
    for v in variants:
        for rep in range(reps):
            jobs.append((base_dir, v["label"], v.get("params", {}), N, rep))
    print(f"Sweeping {len(variants)} variants x {reps} reps @ N={N} on {os.path.basename(base_dir)} ...", flush=True)
    with Pool(6) as p:
        results = p.map(run_one, jobs)
    agg = {}
    for label, score, rep in results:
        agg.setdefault(label, []).append(score)
    rows = []
    for v in variants:
        scores = [s for s in agg.get(v["label"], []) if s is not None]
        mean = sum(scores) / len(scores) if scores else float("nan")
        rows.append((v["label"], mean, scores))
    rows.sort(key=lambda r: -(r[1] if r[1] == r[1] else -999))
    print(f"\n{'variant':<28}{'field%':>8}   runs")
    for label, mean, scores in rows:
        print(f"  {label:<26}{mean:>7.1f}   {['%.1f'%s for s in scores]}")

if __name__ == "__main__":
    main()
