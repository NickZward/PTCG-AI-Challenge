#!/usr/bin/env python3
"""Export a trained torch checkpoint to a numpy .npz for the torch-free Kaggle agent, and
VALIDATE the numpy forward against the torch model on real game decisions before shipping.

Usage: export_numpy.py <ckpt_name> [n_check=300]
Reads  model/az/<ckpt_name>_best.pth + _arch.json; writes model/az/<ckpt_name>_np.npz.
"""
import json
import os
import sys

import numpy as np
import torch

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
import nn_common as NN      # noqa: E402
import np_common as NP      # noqa: E402

name = sys.argv[1]
n_check = int(sys.argv[2]) if len(sys.argv) > 2 else 300
arch = json.load(open(os.path.join(ROOT, "model/az", f"{name}_arch.json")))
dims, ptanh = arch["model"], arch.get("policy_tanh", True)

feat = arch.get("feat", 1)
dvocab = arch.get("decoder_vocab", NN.decoder_size)
model = NN.MyModel(*dims, policy_tanh=ptanh, decoder_vocab=dvocab)
sd = torch.load(os.path.join(ROOT, "model/az", f"{name}_best.pth"), map_location="cpu")
model.load_state_dict(sd)
model.eval()

out = {k: v.float().numpy().astype(np.float16) for k, v in sd.items()}
out["_meta"] = np.asarray(dims + [1 if ptanh else 0], dtype=np.float32)
np_path = os.path.join(ROOT, "model/az", f"{name}_np.npz")
np.savez(np_path, **out)
print(f"exported {np_path} ({os.path.getsize(np_path)/1e6:.0f}MB fp16)")

# ---- validation: play real positions, compare torch vs numpy on every decision ----
npm = NP.NpModel(np_path)
deck = [int(x) for x in open(os.path.join(ROOT, "my-agent/grimmsnarl_v17/deck.csv")).read().split()]
from cg.game import battle_start, battle_select, battle_finish   # noqa: E402
from cg.api import to_observation_class                          # noqa: E402

import random
random.seed(0)
agree = tot = 0
vdiff = pdiff = 0.0
games = 0
while tot < n_check and games < 20:
    games += 1
    obs, _ = battle_start(list(deck), list(deck))
    if obs is None:
        continue
    steps = 0
    try:
        while steps < 400 and tot < n_check:
            cur = obs.get("current") or {}
            if cur.get("result", -1) not in (None, -1) or obs.get("select") is None:
                break
            oc = to_observation_class({"current": cur, "select": obs.get("select"),
                                       "logs": obs.get("logs", []), "step": 0,
                                       "search_begin_input": obs.get("search_begin_input")})
            actions = NN.enumerate_actions(oc.select, 64)
            if len(actions) >= 2:
                sve, svd = NN.get_encoder_input(oc, deck), NN.get_decoder_input(oc, actions, feat)
                with torch.inference_mode():
                    tv, tp = NN.eval_nn(sve, svd, model)
                nv, npo = npm.forward(sve, svd)
                tot += 1
                ti, ni = int(np.argmax(tp)), int(np.argmax(npo))
                if ti == ni:
                    agree += 1
                else:
                    # fp16 rounding can flip which of two BYTE-IDENTICAL candidates wins the
                    # argmax; those have equal fp32 logits and identical game content, so a
                    # flip between them is not a real disagreement.
                    starts = list(svd.offset) + [len(svd.index)]
                    bag = lambda k: (tuple(svd.index[starts[k]:starts[k + 1]]),
                                     tuple(svd.value[starts[k]:starts[k + 1]]))
                    if bag(ti) == bag(ni):
                        agree += 1
                    else:
                        print(f"  real disagreement: torch {ti} ({tp[ti]:.4f}) vs "
                              f"np {ni} ({npo[ni]:.4f}), torch gap {tp[ti]-tp[ni]:.5f}")
                vdiff = max(vdiff, abs(tv - nv))
                pdiff = max(pdiff, float(np.max(np.abs(np.asarray(tp) - np.asarray(npo)))))
            # advance the game with the torch argmax (content of play is irrelevant here)
            sel = actions[int(np.argmax(tp))] if len(actions) >= 2 else (actions[0] if actions else [0])
            obs = battle_select([int(x) for x in sel])
            steps += 1
    finally:
        battle_finish()

print(f"checked {tot} real decisions over {games} games: "
      f"argmax agreement {agree}/{tot} = {agree/max(1,tot):.1%}  "
      f"max |value diff| {vdiff:.4f}  max |logit diff| {pdiff:.4f}")
if tot and agree / tot < 0.995:
    sys.exit("FAIL: numpy port disagrees with torch — do not ship")
print("PASS")
