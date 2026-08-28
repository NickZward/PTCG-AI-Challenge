#!/usr/bin/env python3
"""Kaggle agent wrapper for the Transformer+MCTS Grimmsnarl (learned).

Loads model.pth + nn_common + mcts_agent from this dir and plays via MCTS. Kaggle-safe: if torch /
weights / sklearn-free deps are unavailable, or any error occurs, it degrades to a legal default
move instead of crashing (so a broken deploy never forfeits on an exception).
Env: GRIMM_NN_SEARCH overrides MCTS simulations/decision (default 10)."""
import os
import sys

# Resolve this agent's directory across normal import AND Kaggle's exec-without-__file__ runtime.
_CANDS = []
try:
    _CANDS.append(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    pass
_CANDS += [os.getcwd(), "/kaggle_simulations/agent"]

AGENT_DIR = None
for _c in _CANDS:
    if _c and os.path.isfile(os.path.join(_c, "deck.csv")) and os.path.isfile(os.path.join(_c, "nn_common.py")):
        AGENT_DIR = _c
        break
if AGENT_DIR is None:
    AGENT_DIR = _CANDS[0] if _CANDS else "."
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

SEARCH_COUNT = int(os.environ.get("GRIMM_NN_SEARCH", "10"))

_OK = False
_MODEL = None
_DECK = None
_MA = None
_torch = None
try:
    import json as _json
    import torch as _torch
    import nn_common as NN
    import mcts_agent as _MA
    _DECK = [int(x) for x in open(os.path.join(AGENT_DIR, "deck.csv")).read().split()]
    _arch_path = os.path.join(AGENT_DIR, "model_arch.json")
    _arch = _json.load(open(_arch_path))["model"] if os.path.isfile(_arch_path) else [128, 2, 256, 1, 1]
    _MODEL = NN.MyModel(*_arch)
    _sd = _torch.load(os.path.join(AGENT_DIR, "model.pth"), map_location="cpu")
    _MODEL.load_state_dict(_sd)
    _MODEL.eval()
    _OK = True
except Exception:
    _OK = False


def _legal_default(obs):
    sel = obs.get("select") or {}
    opts = sel.get("option") or []
    mc = max(sel.get("maxCount", 1) or 1, 1)
    return list(range(min(mc, len(opts)))) if opts else []


def agent(obs):
    if _OK:
        try:
            with _torch.inference_mode():
                sel, _ = _MA.mcts_agent(obs, _DECK, _MODEL, opp_deck=None, search_count=SEARCH_COUNT)
            sel = [int(x) for x in sel]
            nopt = len((obs.get("select") or {}).get("option") or [])
            if sel and all(0 <= i < nopt for i in sel):
                return sel
        except Exception:
            pass
    return _legal_default(obs)
