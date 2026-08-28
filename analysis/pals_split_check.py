#!/usr/bin/env python3
"""Reproduce the exact train/held-out game splits train_imit_v2.py used for the two Ogerpon
stages, map them back to episode ids, and re-score /tmp/agree_pals.jsonl per split.

Stage 1 = oger_f2_best.pth  trained on model/az/imit_oger_f2.npz   (oger_combined_manifest.csv)
Stage 2 = oger_f2pal_best.pth fine-tuned from stage 1 on model/az/imit_pals_f2.npz (91 pals games)

Both stages use the same deterministic recipe (train_imit_v2.py:242-267): game boundaries from a
turn-counter reset or a change in (won, winrate, oppdeck, pid), then np.random.default_rng(0)
permutation, taking whole games until the held budget (--held, default 5000) is filled.
"""
import csv
import json
import os
from collections import Counter, defaultdict

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
M_TGT, M_NCAND, M_STYPE, M_TURN, M_WON, M_WR, M_OPP, M_MARGIN, M_PID = range(9)


def split(npz_path, nheld, min_wr=0.0):
    z = np.load(npz_path, allow_pickle=True)
    meta = z["meta"]
    keep = np.ones(len(meta), dtype=bool)
    if min_wr > 0:
        keep &= meta[:, M_WR] >= min_wr
    keep &= meta[:, M_NCAND] >= 2
    ids_all = np.nonzero(keep)[0]
    key = np.stack([meta[:, M_WON], meta[:, M_WR], meta[:, M_OPP], meta[:, M_PID]], 1)
    newgame = np.ones(len(meta), dtype=bool)
    newgame[1:] = (meta[1:, M_TURN] < meta[:-1, M_TURN]) | (key[1:] != key[:-1]).any(1)
    gid = np.cumsum(newgame) - 1
    ngames = int(gid[-1]) + 1
    rng = np.random.default_rng(0)
    gperm = rng.permutation(ngames)
    held_g = np.zeros(ngames, dtype=bool)
    counts = np.bincount(gid, minlength=ngames)
    acc = 0
    for g in gperm:
        if acc >= nheld:
            break
        held_g[g] = True
        acc += counts[g]
    return meta, gid, held_g, counts, ids_all


rows = json.load(open("/tmp/agree_pals.jsonl"))
per_ep = defaultdict(int)
order = []
for r in rows:
    if r["ep"] not in per_ep:
        order.append(r["ep"])
    per_ep[r["ep"]] += 1

# ---------------- stage 2 ----------------
meta2, gid2, held2, cnt2, _ = split(os.path.join(ROOT, "model/az/imit_pals_f2.npz"), 5000)
print(f"stage2: {len(meta2)} decisions, {held2.size} games detected, "
      f"{int(held2.sum())} held / {int(cnt2[held2].sum())} decisions")
print(f"harness: {len(rows)} decisions, {len(order)} episodes")
match = (list(cnt2) == [per_ep[e] for e in order])
print(f"npz game sizes == harness per-episode counts: {match}")
if not match:
    print("  npz:", list(cnt2)[:12], "\n  harness:", [per_ep[e] for e in order][:12])

ep_held2 = {order[g] for g in range(len(order)) if held2[g]}
print(f"stage2 HELD episodes ({len(ep_held2)}): {sorted(ep_held2)}")

# ---------------- stage 1 ----------------
meta1, gid1, held1, cnt1, _ = split(os.path.join(ROOT, "model/az/imit_oger_f2.npz"), 5000)
comb = list(csv.DictReader(open(os.path.join(ROOT, "oger_combined_manifest.csv"))))
# extract_v2 groups manifest rows by path (dict insertion order) -> game order
by_path = []
seen = set()
for r in comb:
    if r["path"] not in seen:
        seen.add(r["path"])
        by_path.append(r)
print(f"\nstage1: {len(meta1)} decisions, {held1.size} games detected vs {len(by_path)} manifest paths, "
      f"{int(held1.sum())} held / {int(cnt1[held1].sum())} decisions")
ep_held1 = set()
if held1.size == len(by_path):
    ep_held1 = {by_path[g]["episode"] for g in range(len(by_path)) if held1[g]}
    pal_held1 = {e for e in ep_held1 if e in per_ep}
    print(f"stage1 held-out episodes that are palsystem's: {len(pal_held1)} -> {sorted(pal_held1)}")
else:
    print("  !! game count mismatch, mapping stage1 held-out games to episodes by cumulative size")
    sizes = Counter()
    # fall back: align by walking manifest paths and npz game sizes
    pal_held1 = set()
    print("  (skipped)")

clean = ep_held2 & ep_held1
print(f"\nTRULY CLEAN episodes (held out of BOTH stages): {len(clean)} -> {sorted(clean)}")

# ---------------- re-score ----------------
def score(label, eps):
    sub = [r for r in rows if r["ep"] in eps]
    if not sub:
        print(f"  {label:34s} n=0")
        return
    a = sum(r["agree"] for r in sub)
    t = sum(r["agree"] or r["tie"] for r in sub)
    m = [r for r in sub if r["stype"] == 0]
    am = sum(r["agree"] for r in m)
    print(f"  {label:34s} n={len(sub):5d}  strict {a/len(sub):5.1%}  tie-aware {t/len(sub):5.1%}"
          f"   MAIN strict {am/max(1,len(m)):5.1%} (n={len(m)})")


print("\nAGREEMENT BY LEAKAGE STATUS (ckpt oger_f2pal_best.pth):")
score("ALL 91 pals games", set(per_ep))
score("stage2 TRAIN (fine-tune saw these)", set(per_ep) - ep_held2)
score("stage2 HELD (but stage1 trained)", ep_held2 - ep_held1)
score("CLEAN (held out of both stages)", clean)
