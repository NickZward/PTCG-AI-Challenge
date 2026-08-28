#!/usr/bin/env python3
"""STEP 1: validate the canonical encoder/decoder port (nn_common) against real game states.

Checks, on (a) a fresh battle_start Grimmsnarl state and (b) a real top replay from Logs 07-22:
  - encoder produces exactly num_words_encoder tokens, all indices in [0, encoder_size)
  - decoder produces one token per enumerated action, all indices in [0, decoder_size)
  - MyModel runs and returns value in [-1,1] and a finite policy vector of the right length
Exits non-zero on any failure.
"""
import glob
import json
import os
import random
import sys

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))  # provides cg-lib
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))

import torch
from cg.api import to_observation_class
from cg.game import battle_start, battle_finish, battle_select
import nn_common as NN

REPLAY_DIR = "/Users/nickzwart/Desktop/Logs 07-22"
DECK = [int(x) for x in open(os.path.join(ROOT, "my-agent/grimmsnarl_v17/deck.csv")).read().split()]

fails = []


def check(name, cond, detail=""):
    tag = "OK " if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        fails.append(name)


def validate_state(obs_class, tag, model):
    """obs_class: an Observation (our-side to move, select present with >1 options)."""
    your_deck = list(DECK)
    print(f"\n--- validate: {tag} (turn {obs_class.current.turn}, ctx {obs_class.select.context}, "
          f"{len(obs_class.select.option)} options, maxCount {obs_class.select.maxCount}) ---")

    sv_enc = NN.get_encoder_input(obs_class, your_deck)
    check("encoder token count == 24", len(sv_enc.offset) == NN.num_words_encoder,
          f"got {len(sv_enc.offset)}")
    check("encoder indices >= 0", all(i >= 0 for i in sv_enc.index))
    mx = max(sv_enc.index) if sv_enc.index else -1
    check("encoder max index < encoder_size", mx < NN.encoder_size, f"max {mx} < {NN.encoder_size}")

    actions = NN.enumerate_actions(obs_class.select, cap=64)
    sv_dec = NN.get_decoder_input(obs_class, actions)
    check("decoder token count == #actions", len(sv_dec.offset) == len(actions),
          f"{len(sv_dec.offset)} vs {len(actions)}")
    dmx = max(sv_dec.index) if sv_dec.index else -1
    check("decoder max index < decoder_size", dmx < NN.decoder_size, f"max {dmx} < {NN.decoder_size}")

    with torch.inference_mode():
        value, policy = NN.eval_nn(sv_enc, sv_dec, model)
    check("value is finite & in [-1,1]", (value == value) and -1.0 <= value <= 1.0, f"value={value:.4f}")
    check("policy length == #actions", len(policy) == len(actions), f"{len(policy)} vs {len(actions)}")
    check("policy all finite", all(p == p for p in policy))
    print(f"       value={value:+.4f}  policy[:5]={[round(p,3) for p in policy[:5]]}")


def main():
    print(f"card_count={NN.card_count}  attack_count={NN.attack_count}  "
          f"decoder_size={NN.decoder_size}  encoder_size={NN.encoder_size}")
    torch.manual_seed(0)
    model = NN.MyModel(128, 2, 256, 1, 1)
    model.eval()

    # ---- (a) fresh battle_start, step to a real MAIN decision on our side ----
    random.seed(7)
    obs, _ = battle_start(list(DECK), list(DECK))
    picked = None
    for _ in range(400):
        cur = obs["current"]
        if cur.get("result", -1) not in (None, -1):
            break
        sel = obs.get("select")
        if sel is None:
            break
        opts = sel.get("option") or []
        oc = to_observation_class(obs)
        if sel.get("type") == 0 and len(opts) > 1 and (cur.get("turn") or 0) >= 1:
            picked = oc
            break
        # advance by a legal-ish default (first option, maxCount wide)
        mc = max(sel.get("maxCount", 1), 1)
        obs = battle_select(list(range(min(mc, len(opts)))) if opts else [])
    if picked is not None:
        validate_state(picked, "fresh battle_start MAIN", model)
    else:
        check("found a fresh MAIN decision", False)
    battle_finish()

    # ---- (b) a real top replay: find a step with select present + >1 options ----
    files = sorted(glob.glob(os.path.join(REPLAY_DIR, "*.json")))
    used = False
    for f in files[:40]:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for step in d.get("steps", []):
            for entry in step:
                o = (entry or {}).get("observation") or {}
                sel = o.get("select")
                cur = o.get("current")
                if not sel or not cur:
                    continue
                opts = sel.get("option") or []
                if sel.get("type") == 0 and len(opts) > 1 and (cur.get("turn") or 0) >= 1:
                    oc = to_observation_class(o)
                    # encode from THIS player's perspective using our deck as a stand-in
                    validate_state(oc, f"replay {os.path.basename(f)}", model)
                    used = True
                    break
            if used:
                break
        if used:
            break
    check("found a real replay MAIN decision", used)

    print("\n" + ("ALL CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
