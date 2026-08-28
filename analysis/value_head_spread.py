#!/usr/bin/env python3
"""Control: how much SIGNAL is in each agent's value head?

mcts_agent ranks root children by their child node's mean value; with the root breadth sweep every
child is visited once, so the value head is the tie-breaker that actually chooses the move. A value
head trained on a corpus where 100% of games are wins has a constant target (+1) and can only emit
noise. This measures the emitted distribution for the working champion (Grimmsnarl v12, corpus
51.5% wins) and the failed Ogerpon imitation (corpus 100% wins) on real replay states.

Usage: value_head_spread.py <agent_dir> <manifest.csv> [player] [--games=N]
"""
import csv
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
pos = [a for a in sys.argv[1:] if not a.startswith("--")]
AGENT_DIR = os.path.join(ROOT, pos[0])
MANIFEST = pos[1] if len(pos) > 1 else os.path.join(ROOT, "oger_pals_manifest.csv")
NGAMES = int(F.get("games", 12))

sys.path.insert(0, AGENT_DIR)
spec = importlib.util.spec_from_file_location("np_common", os.path.join(AGENT_DIR, "np_common.py"))
PNN = importlib.util.module_from_spec(spec)
sys.modules["np_common"] = PNN
spec.loader.exec_module(PNN)
from cg.api import to_observation_class  # noqa: E402

MODEL = PNN.NpModel(os.path.join(AGENT_DIR, "model_np.npz"))
DECK = [int(x) for x in open(os.path.join(AGENT_DIR, "deck.csv")).read().split()]

rows = list(csv.DictReader(open(MANIFEST)))[:NGAMES]
vals, wons, pdiffs = [], [], []
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
            acts = PNN.enumerate_actions(oc.select, 64)
            se = PNN.get_encoder_input(oc, DECK)
            sd = PNN.get_decoder_input(oc, acts)
            v, _ = PNN.eval_nn(se, sd, MODEL)
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

v = np.array(vals)
w = np.array(wons)
pd = np.array(pdiffs)
print(f"{pos[0]}  |  {os.path.basename(MANIFEST)}  |  {len(v)} states from {NGAMES} games")
print(f"  value: mean {v.mean():+.4f}  std {v.std():.4f}  min {v.min():+.4f}  max {v.max():+.4f}  "
      f"range {v.max()-v.min():.4f}")
print(f"  corpus outcome balance in these games: won={w.mean():.1%}")
if w.min() != w.max():
    print(f"  mean value in WON games {v[w==1].mean():+.4f}  vs LOST games {v[w==0].mean():+.4f}  "
          f"-> separation {v[w==1].mean()-v[w==0].mean():+.4f}")
print("  mean value by CURRENT prize differential (a working value head must slope):")
for k in sorted(set(pd.tolist())):
    m = pd == k
    if m.sum() >= 20:
        print(f"    pdiff {k:+d}: n={int(m.sum()):5d}  value {v[m].mean():+.4f}")
