#!/usr/bin/env python3
"""STEP 2 test: play full games with the Transformer+MCTS agent (untrained model) to prove the
MCTS loop, Search API tree-forking, and both determinization paths run end-to-end without crashing
and always emit legal selections. Not about strength — the model is random-init."""
import os
import random
import sys
import time

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))  # cg-lib
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))

import torch
from cg.game import battle_start, battle_finish, battle_select
from cg.api import to_observation_class
import nn_common as NN
from mcts_agent import mcts_agent

DECK = [int(x) for x in open(os.path.join(ROOT, "my-agent/grimmsnarl_v17/deck.csv")).read().split()]


def random_agent(obs_dict):
    oc = to_observation_class(obs_dict)
    n = len(oc.select.option)
    k = min(oc.select.maxCount, n)
    return random.sample(range(n), k) if n else []


def play_one(seed, opp_known, search_count=6, max_steps=4000):
    """Our MCTS agent (side = seed%2) vs random. opp_known toggles deck-aware vs neutral fill."""
    random.seed(seed)
    torch.manual_seed(seed)
    model = NN.MyModel(128, 2, 256, 1, 1)
    model.eval()
    obs, _ = battle_start(list(DECK), list(DECK))
    our_side = seed % 2
    opp_deck = DECK if opp_known else None
    decisions = 0
    t0 = time.time()
    try:
        for _ in range(max_steps):
            cur = obs["current"]
            if cur.get("result", -1) >= 0:
                break
            if obs.get("select") is None:
                break
            if cur["yourIndex"] == our_side:
                with torch.inference_mode():
                    sel, sample = mcts_agent(obs, DECK, model, opp_deck=opp_deck, search_count=search_count)
                # legality: indices in range, count within [minCount,maxCount]
                sel_obj = obs["select"]
                nopt = len(sel_obj.get("option") or [])
                assert all(0 <= i < nopt for i in sel), f"illegal index in {sel} (n={nopt})"
                decisions += 1
                obs = battle_select([int(x) for x in sel])
            else:
                obs = battle_select(random_agent(obs))
    finally:
        result = obs["current"].get("result", -1)
        battle_finish()
    dt = time.time() - t0
    return result, decisions, dt, our_side


def main():
    print(f"SEARCH default={NN.SEARCH_COUNT}; testing full games with untrained model\n")
    ok = True
    for i, opp_known in enumerate([True, False, True]):
        try:
            result, dec, dt, side = play_one(seed=i + 1, opp_known=opp_known, search_count=6)
            per = dt / max(1, dec)
            print(f"game {i+1}: opp_known={opp_known} side={side} -> result={result} "
                  f"({dec} MCTS decisions, {dt:.1f}s total, {per*1000:.0f}ms/decision)")
        except Exception as e:
            ok = False
            import traceback
            traceback.print_exc()
            print(f"game {i+1}: CRASHED: {e}")
    print("\n" + ("AGENT PLAYS FULL GAMES OK" if ok else "AGENT TEST FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
