#!/usr/bin/env python3
"""Value-head spread control, torch side (fast). See value_head_spread.py for the argument.

Usage: value_spread_torch.py <ckpt.pth> <deck.csv> <manifest.csv> [--games=N]
"""
import csv
import json
import os
import sys

import numpy as np
import torch

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
pos = [a for a in sys.argv[1:] if not a.startswith("--")]
CKPT, DECKP, MANI = pos[0], pos[1], pos[2]
NG = int(F.get("games", 20))

sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
from cg.api import to_observation_class  # noqa: E402
import nn_common as NN  # noqa: E402

arch = json.load(open(CKPT.replace("_best.pth", "_arch.json")))
m = NN.MyModel(*arch["model"], policy_tanh=arch.get("policy_tanh", False),
               decoder_vocab=int(arch.get("decoder_vocab", NN.decoder_size)))
m.load_state_dict(torch.load(CKPT, map_location="cpu"))
m.eval()
DECK = [int(x) for x in open(DECKP).read().split()]
FEAT = int(arch.get("feat", 1))

vals, wons, pdiffs = [], [], []
rows = list(csv.DictReader(open(MANI)))[:NG]
for rec in rows:
    p = rec["path"]
    if not os.path.exists(p):
        p = p.replace("/Users/nickzwart/Desktop/", ROOT + "/")
        if not os.path.exists(p):
            continue
    d = json.load(open(p))
    seat = int(rec["side"])
    won = int(rec["won"])
    for step in d.get("steps", []):
        ent = step[seat] if seat < len(step) else None
        if not ent or ent.get("status") != "ACTIVE":
            continue
        o = ent.get("observation") or {}
        sel, cur = o.get("select"), o.get("current")
        if not sel or not cur or len(sel.get("option") or []) <= 1:
            continue
        try:
            oc = to_observation_class({"current": cur, "select": sel, "logs": o.get("logs", []),
                                       "step": 0, "search_begin_input": o.get("search_begin_input")})
            acts = NN.enumerate_actions(oc.select, 64)
            with torch.inference_mode():
                v, _ = NN.eval_nn(NN.get_encoder_input(oc, DECK),
                                  NN.get_decoder_input(oc, acts, FEAT), m)
        except Exception:
            continue
        pl = cur.get("players") or [None, None]
        try:
            pd = (6 - len(pl[seat]["prize"])) - (6 - len(pl[1 - seat]["prize"]))
        except Exception:
            pd = 0
        vals.append(float(v))
        wons.append(won)
        pdiffs.append(pd)
    if len(vals) and len(vals) % 500 < 60:
        print(f"  ...{len(vals)} states", flush=True)

v, w, pd = np.array(vals), np.array(wons), np.array(pdiffs)
print(f"\n{os.path.basename(CKPT)} | {os.path.basename(MANI)} | {len(v)} states")
print(f"  value: mean {v.mean():+.4f}  std {v.std():.4f}  min {v.min():+.4f}  max {v.max():+.4f}")
print(f"  games in sample: won={w.mean():.1%}")
if w.min() != w.max():
    print(f"  mean value in WON games {v[w==1].mean():+.4f} vs LOST {v[w==0].mean():+.4f} "
          f"-> separation {v[w==1].mean()-v[w==0].mean():+.4f}")
print("  mean value by CURRENT prize differential:")
for k in sorted(set(pd.tolist())):
    msk = pd == k
    if msk.sum() >= 20:
        print(f"    pdiff {k:+d}: n={int(msk.sum()):5d}  value {v[msk].mean():+.4f}")
