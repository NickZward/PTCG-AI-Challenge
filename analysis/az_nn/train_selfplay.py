#!/usr/bin/env python3
"""Local entry point for self-play training (imports train_core). Same code path as Kaggle.

Usage:
  python3 analysis/az_nn/train_selfplay.py smoke   # 1 iter, tiny — validates the pipeline on CPU
  python3 analysis/az_nn/train_selfplay.py local   # a few iters, still CPU-modest
The real run is on Kaggle GPU via the generated self-contained notebook (build_kaggle.py)."""
import os
import sys

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))  # cg-lib
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))

from train_core import run_training

BASE = {
    "deck_dir": os.path.join(ROOT, "my-agent/grimmsnarl_v17"),
    # curriculum: the decks that gate the low climb per the leaderboard-by-band meta (Crustle/M-Lucario first)
    "curriculum": [
        {"dir": os.path.join(ROOT, "my-agent/gauntlet/mlucario"), "weight": 2},
        {"dir": os.path.join(ROOT, "my-agent/gauntlet/crustle"), "weight": 2},
    ],
    "mirror_weight": 6,          # mirror self-play is the majority signal
    "iterations": 5,
    "games_per_iter": 100,
    "eval_games": 20,
    "search_count": 48,          # #2 deeper search (was 14 — too shallow for good targets)
    "model": (128, 2, 256, 1, 1),
    "lr": 3e-4,
    "batch_size": 128,
    "lambda_td": 0.9,
    "t14_adjudicate": True,
    "stop_turn": 14,
    "warmstart": os.path.join(ROOT, "model/az/grimm_warmstart.pkl"),  # #1 expert warm-start
    "pretrain_epochs": 4,
    "out_dir": os.path.join(ROOT, "model/grimm_nn"),
    "device": None,              # auto (cuda if available)
}

SMOKE = dict(BASE, iterations=1, games_per_iter=6, eval_games=4, search_count=6,
             batch_size=16, pretrain_epochs=1, warmstart="/tmp/ws_test.pkl",
             out_dir=os.path.join(ROOT, "model/grimm_nn_smoke"))

LOCAL = dict(BASE, iterations=2, games_per_iter=30, eval_games=8, search_count=6, batch_size=64)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    cfg = {"smoke": SMOKE, "local": LOCAL, "full": BASE}[mode]
    run_training(cfg)
