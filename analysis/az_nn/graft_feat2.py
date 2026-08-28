#!/usr/bin/env python3
"""Graft the FEAT-v2 positional candidate block onto an existing (feat-1) checkpoint.

WHY (measured, not assumed): replaying our v6 policy against the #1 player's 449 games shows the
two biggest disagreement buckets are ~41% MODEL BLINDNESS — his pick and ours encode to
byte-identical decoder tokens, so the net could not have told them apart:
    CARD    1377 disagreements, 42.1% blind
    ATTACH   368 disagreements, 40.8% blind
(RETREAT/ATTACK/PLAY are 0% blind = genuine judgement, not fixable by features.)
The reference decoder encodes a candidate as (feature_slot, card_id) with NO board position, so
"attach energy X to Pokemon A" and "...to Pokemon B" are the same token bag. FEAT v2 appends a
36-row positional block (area / host slot / host HP bucket / damaged / energy count / copy index).

v5 tried this and FAILED its gate — but v5 retrained FROM SCRATCH with a bigger net, discarding
the v4->v6 curriculum. This script instead GRAFTS: every trained weight is preserved and only the
36 new embedding rows are freshly initialised, so a low-LR fine-tune teaches the existing policy
to USE the new features rather than relearning the game.

Usage: graft_feat2.py <src_ckpt_name> <dst_ckpt_name>
"""
import json
import os
import sys

import torch

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
import nn_common as NN  # noqa: E402

src, dst = sys.argv[1], sys.argv[2]
AZ = os.path.join(ROOT, "model/az")
arch = json.load(open(os.path.join(AZ, f"{src}_arch.json")))
sd = torch.load(os.path.join(AZ, f"{src}_best.pth"), map_location="cpu")

old_vocab = sd["decoder_bag.weight"].shape[0]
new_vocab = NN.decoder_size_v2
if old_vocab >= new_vocab:
    sys.exit(f"{src} already has a {old_vocab}-row decoder table (>= {new_vocab}); nothing to graft")

w = sd["decoder_bag.weight"]
extra = torch.zeros(new_vocab - old_vocab, w.shape[1], dtype=w.dtype)
# small non-zero init: the block must start near-neutral so grafting does not perturb the policy,
# but not exactly zero or the rows get no gradient signal direction to break symmetry.
extra.normal_(0.0, 0.01)
sd["decoder_bag.weight"] = torch.cat([w, extra], 0)

# sanity: the grafted model must load, and must still reproduce the source policy when the
# positional features are absent (feat=1 input) -- proof the graft is behaviour-preserving.
model = NN.MyModel(*arch["model"], policy_tanh=arch.get("policy_tanh", True),
                   decoder_vocab=new_vocab)
model.load_state_dict(sd)
torch.save(sd, os.path.join(AZ, f"{dst}_best.pth"))
json.dump({"model": arch["model"], "policy_tanh": arch.get("policy_tanh", True),
           "feat": 2, "decoder_vocab": new_vocab},
          open(os.path.join(AZ, f"{dst}_arch.json"), "w"))
print(f"grafted {src} -> {dst}: decoder table {old_vocab} -> {new_vocab} rows "
      f"(+{new_vocab-old_vocab} positional, N(0,0.01) init); all other weights preserved")
