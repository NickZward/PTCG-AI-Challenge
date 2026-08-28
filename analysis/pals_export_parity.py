#!/usr/bin/env python3
"""Does the SHIPPED numpy agent reproduce the TRAINED torch checkpoint?

Bug #2 in this project was a deployment bug (a process-global feat flag), not a modelling bug, and
it was invisible to every fidelity number because training never touches the shipped code path.
This checks the two independently on the SAME palsystem decisions:

  torch  : nn_common.get_encoder_input/get_decoder_input + MyModel(oger_f2pal_best.pth)
  numpy  : my-agent/<dir>/np_common.get_*_input + NpModel(model_np.npz)      [search disabled]

They should produce the SAME argmax on every decision. Any gap is a packaging bug.

Usage: pals_export_parity.py [agent_dir] [--games=N] [--ckpt=...]
"""
import csv
import json
import os
import sys

import numpy as np
import torch

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
AGENT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "my-agent/oger_imit_f2"
AGENT_DIR = os.path.join(ROOT, AGENT)
NGAMES = int(F.get("games", 12))
CKPT = F.get("ckpt", os.path.join(ROOT, "model/az/oger_f2pal_best.pth"))

sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
from cg.api import to_observation_class  # noqa: E402
import nn_common as TNN  # noqa: E402

sys.path.insert(0, AGENT_DIR)
import np_common as PNN  # noqa: E402

arch = json.load(open(CKPT.replace("_best.pth", "_arch.json")))
tmodel = TNN.MyModel(*arch["model"], policy_tanh=arch.get("policy_tanh", False),
                     decoder_vocab=int(arch["decoder_vocab"]))
tmodel.load_state_dict(torch.load(CKPT, map_location="cpu"))
tmodel.eval()
pmodel = PNN.NpModel(os.path.join(AGENT_DIR, "model_np.npz"))
DECK = [int(x) for x in open(os.path.join(AGENT_DIR, "deck.csv")).read().split()]
print(f"agent={AGENT}  np feat={pmodel.feat}  torch feat={arch['feat']}  "
      f"np decoder rows={pmodel.w['decoder_bag.weight'].shape[0]}  torch vocab={arch['decoder_vocab']}",
      flush=True)

rows = list(csv.DictReader(open(os.path.join(ROOT, "oger_pals_manifest.csv"))))[:NGAMES]
n = same = 0
tagree = pagree = 0
enc_mismatch = dec_mismatch = 0
diffs = []
for rec in rows:
    if not os.path.exists(rec["path"]):
        continue
    d = json.load(open(rec["path"]))
    seat = int(rec["side"])
    steps = d["steps"]
    for i, step in enumerate(steps):
        ent = step[seat] if seat < len(step) else None
        if not ent or ent.get("status") != "ACTIVE":
            continue
        o = ent.get("observation") or {}
        sel, cur = o.get("select"), o.get("current")
        nxt = steps[i + 1][seat] if (i + 1 < len(steps) and seat < len(steps[i + 1])) else None
        act = (nxt or {}).get("action")
        if not sel or act is None or not cur:
            continue
        opts = sel.get("option") or []
        if len(opts) <= 1:
            continue
        chosen = {int(x) for x in act if isinstance(x, int) and 0 <= x < len(opts)}
        if not chosen:
            continue
        od = {"current": cur, "select": sel, "logs": o.get("logs", []), "step": 0,
              "search_begin_input": o.get("search_begin_input")}
        try:
            toc = to_observation_class(od)
            tact = TNN.enumerate_actions(toc.select, 64)
            tgt = next((j for j, a in enumerate(tact) if set(a) == chosen), None)
            if tgt is None:
                continue
            te = TNN.get_encoder_input(toc, DECK)
            td = TNN.get_decoder_input(toc, tact, int(arch["feat"]))
            with torch.inference_mode():
                _, tpol = TNN.eval_nn(te, td, tmodel)
            ti = int(np.argmax(tpol[:len(tact)]))

            poc = to_observation_class(od)
            pact = PNN.enumerate_actions(poc.select, 64)
            pe = PNN.get_encoder_input(poc, DECK)
            pd = PNN.get_decoder_input(poc, pact)
            _, ppol = PNN.eval_nn(pe, pd, pmodel)
            pi = int(np.argmax(np.asarray(ppol)[:len(pact)]))
        except Exception as e:
            diffs.append(("exc", type(e).__name__))
            continue
        n += 1
        if (list(te.index), list(te.value), list(te.offset)) != (list(pe.index), list(pe.value), list(pe.offset)):
            enc_mismatch += 1
        if (list(td.index), list(td.value), list(td.offset)) != (list(pd.index), list(pd.value), list(pd.offset)):
            dec_mismatch += 1
        same += (ti == pi)
        tagree += (ti == tgt)
        pagree += (pi == tgt)
        if ti != pi and len(diffs) < 10:
            diffs.append((rec["episode"], i, "torch", ti, "np", pi, "expert", tgt,
                          "maxabs_logit_delta", float(np.max(np.abs(np.asarray(tpol[:len(tact)]) - np.asarray(ppol[:len(pact)]))))))

print(f"\ndecisions compared: {n}")
print(f"encoder sparse-vector mismatches: {enc_mismatch}")
print(f"decoder sparse-vector mismatches: {dec_mismatch}")
print(f"torch argmax == numpy argmax     : {same}/{n} = {same/max(1,n):.2%}")
print(f"torch argmax == palsystem        : {tagree}/{n} = {tagree/max(1,n):.2%}")
print(f"numpy argmax == palsystem        : {pagree}/{n} = {pagree/max(1,n):.2%}")
for x in diffs[:10]:
    print("  ", x)
