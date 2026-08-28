#!/usr/bin/env python3
"""Pack a trained imitation checkpoint into a runnable/uploadable agent directory.

  build_agent_v2.py <ckpt_name> <agent_dir> [--mcts=N] [--np] [--deck=<dir>]

--np  ships the NUMPY inference port (np_common + model_np.npz, produced by export_numpy.py):
      no torch dependency at all. This is the KAGGLE-SAFE build — the sandbox verifiably has
      numpy (az2 ran sklearn/numpy) while torch is unproven there.

KAGGLE QUIRK (cost one failed upload): the sandbox execs main.py with NO __file__ in the
namespace, so file locations must be resolved via try/except with /kaggle_simulations/agent
and cwd fallbacks — the _base() block in the templates below. Never use bare __file__.
"""
import json
import os
import shutil
import sys

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
AZ = os.path.join(ROOT, "analysis/az_nn")

BASE_RESOLVER = '''\
import os, sys

# BLAS THREAD CAP — MUST run before numpy is imported.
# The torch templates below call torch.set_num_threads(1); the numpy ones never had an
# equivalent, so OpenBLAS spun across every core on the tiny [24,128]x[128,512] GEMMs this
# net uses. Measured: 1794 ms wall / 1389 ms CPU per forward at 8 threads vs 32 ms / 5.3 ms
# at 1 — 56x wall, 261x CPU. That exhausted _budgeted_search's 200s/400s wall-clock budget
# inside the FIRST game, silently dropping the agent to search_count=1 (MCTS off) for 94% of
# its decisions, and made every local gate a function of machine load.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")


def _base():
    """Agent dir resolution. Kaggle execs this file WITHOUT __file__ defined, so guard it and
    fall back to the sandbox extraction path, then cwd."""
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    dirs += ["/kaggle_simulations/agent", os.getcwd(), "."]
    for d in dirs:
        if os.path.exists(os.path.join(d, "{probe}")):
            return d
    return "."


_HERE = _base()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
'''

MAIN_NP_ARGMAX = BASE_RESOLVER + '''\
import np_common as NN
from cg.api import to_observation_class

_MODEL = NN.NpModel(os.path.join(_HERE, "model_np.npz"))
_DECK = [int(x) for x in open(os.path.join(_HERE, "deck.csv")).read().split()]


def agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return list(_DECK)
    try:
        actions = NN.enumerate_actions(obs.select, 64)
        if not actions:
            return [0]
        if len(actions) == 1:
            return list(actions[0])
        sv_e = NN.get_encoder_input(obs, _DECK)
        sv_d = NN.get_decoder_input(obs, actions)
        _, pol = _MODEL.forward(sv_e, sv_d)
        return list(actions[max(range(len(pol)), key=lambda i: pol[i])])
    except Exception:
        opts = (obs_dict.get("select") or {}).get("option") or []
        n = (obs.select.minCount if obs.select else 1) or 1
        return list(range(min(n, len(opts)))) if opts else [0]
'''

MAIN_NP_MCTS = BASE_RESOLVER + '''\
import time

import np_common as NN
from mcts_agent import mcts_agent
from cg.api import to_observation_class

_MODEL = NN.NpModel(os.path.join(_HERE, "model_np.npz"))
_DECK = [int(x) for x in open(os.path.join(_HERE, "deck.csv")).read().split()]
SEARCH = {search}
_SPENT = [0.0]   # cumulative wall-clock inside agent() this episode


def _budgeted_search():
    """Degrade search depth as the episode clock builds. One ladder loss (ep88331849) came from
    hitting the episode runTimeout while AHEAD; the search must never be the reason we time out.
    Full depth until 200s total, 10 evals until 400s, argmax-equivalent past that."""
    if _SPENT[0] < 200.0:
        return SEARCH
    if _SPENT[0] < 400.0:
        return min(10, SEARCH)
    return 1


def agent(obs_dict):
    t0 = time.time()
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return list(_DECK)
    try:
        sel, _ = mcts_agent(obs_dict, _DECK, _MODEL, search_count=_budgeted_search())
        return [int(x) for x in sel]
    except Exception:
        opts = (obs_dict.get("select") or {}).get("option") or []
        n = (obs.select.minCount if obs.select else 1) or 1
        return list(range(min(n, len(opts)))) if opts else [0]
    finally:
        _SPENT[0] += time.time() - t0
'''

MAIN_TORCH_ARGMAX = BASE_RESOLVER + '''\
import json
import torch
import nn_common as NN
from cg.api import to_observation_class

torch.set_num_threads(1)
_CFG = json.load(open(os.path.join(_HERE, "model_arch.json")))
_MODEL = NN.MyModel(*_CFG["model"], policy_tanh=_CFG.get("policy_tanh", True))
_MODEL.load_state_dict(torch.load(os.path.join(_HERE, "model.pth"), map_location="cpu"))
_MODEL.eval()
_DECK = [int(x) for x in open(os.path.join(_HERE, "deck.csv")).read().split()]


def agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return list(_DECK)
    try:
        actions = NN.enumerate_actions(obs.select, 64)
        if not actions:
            return [0]
        if len(actions) == 1:
            return list(actions[0])
        sv_e = NN.get_encoder_input(obs, _DECK)
        sv_d = NN.get_decoder_input(obs, actions)
        with torch.inference_mode():
            _, pol = NN.eval_nn(sv_e, sv_d, _MODEL)
        return list(actions[max(range(len(pol)), key=lambda i: pol[i])])
    except Exception:
        opts = (obs_dict.get("select") or {}).get("option") or []
        n = (obs.select.minCount if obs.select else 1) or 1
        return list(range(min(n, len(opts)))) if opts else [0]
'''

MAIN_TORCH_MCTS = BASE_RESOLVER + '''\
import json
import torch
import nn_common as NN
from mcts_agent import mcts_agent
from cg.api import to_observation_class

torch.set_num_threads(1)
_CFG = json.load(open(os.path.join(_HERE, "model_arch.json")))
_MODEL = NN.MyModel(*_CFG["model"], policy_tanh=_CFG.get("policy_tanh", True))
_MODEL.load_state_dict(torch.load(os.path.join(_HERE, "model.pth"), map_location="cpu"))
_MODEL.eval()
_DECK = [int(x) for x in open(os.path.join(_HERE, "deck.csv")).read().split()]
SEARCH = {search}


def agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return list(_DECK)
    try:
        with torch.inference_mode():
            sel, _ = mcts_agent(obs_dict, _DECK, _MODEL, search_count=SEARCH)
        return [int(x) for x in sel]
    except Exception:
        opts = (obs_dict.get("select") or {}).get("option") or []
        n = (obs.select.minCount if obs.select else 1) or 1
        return list(range(min(n, len(opts)))) if opts else [0]
'''


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    F = {a.split("=")[0].lstrip("-"): (a.split("=", 1)[1] if "=" in a else "1")
         for a in sys.argv[1:] if a.startswith("--")}
    ckpt, out = args[0], args[1]
    mcts = int(F.get("mcts", 0))
    use_np = "np" in F
    deck_src = F.get("deck", os.path.join(ROOT, "my-agent/grimmsnarl_v17"))

    os.makedirs(out, exist_ok=True)
    if use_np:
        src = os.path.join(ROOT, "model/az", f"{ckpt}_np.npz")
        if not os.path.exists(src):
            sys.exit(f"missing {src} — run export_numpy.py {ckpt} first")
        shutil.copy(src, os.path.join(out, "model_np.npz"))
        shutil.copy(os.path.join(AZ, "np_common.py"), os.path.join(out, "np_common.py"))
        probe = "model_np.npz"
        if mcts:
            # mcts_agent with the numpy eval backend (identical search, NN=np_common)
            mc = open(os.path.join(AZ, "mcts_agent.py")).read()
            mc = mc.replace("import nn_common as NN", "import np_common as NN")
            open(os.path.join(out, "mcts_agent.py"), "w").write(mc)
            # opponent-archetype decklists for search determinization (lever 1)
            od = os.path.join(ROOT, "model", "opp_decks.json")
            if os.path.exists(od):
                shutil.copy(od, os.path.join(out, "opp_decks.json"))
        tpl = MAIN_NP_MCTS if mcts else MAIN_NP_ARGMAX
    else:
        src_pth = os.path.join(ROOT, "model/az", f"{ckpt}_best.pth")
        src_arch = os.path.join(ROOT, "model/az", f"{ckpt}_arch.json")
        for p in (src_pth, src_arch):
            if not os.path.exists(p):
                sys.exit(f"missing {p}")
        shutil.copy(src_pth, os.path.join(out, "model.pth"))
        shutil.copy(src_arch, os.path.join(out, "model_arch.json"))
        shutil.copy(os.path.join(AZ, "nn_common.py"), os.path.join(out, "nn_common.py"))
        probe = "model.pth"
        if mcts:
            shutil.copy(os.path.join(AZ, "mcts_agent.py"), os.path.join(out, "mcts_agent.py"))
        tpl = MAIN_TORCH_MCTS if mcts else MAIN_TORCH_ARGMAX

    shutil.copy(os.path.join(deck_src, "deck.csv"), os.path.join(out, "deck.csv"))
    cg_dst = os.path.join(out, "cg")
    if os.path.exists(cg_dst):
        shutil.rmtree(cg_dst)
    shutil.copytree(os.path.join(deck_src, "cg"), cg_dst,
                    ignore=shutil.ignore_patterns("__pycache__"))
    # plain replace, not str.format — the templates contain literal python braces
    open(os.path.join(out, "main.py"), "w").write(
        tpl.replace("{search}", str(mcts)).replace("{probe}", probe))
    print(f"built {out}  backend={'numpy' if use_np else 'torch'} "
          f"mcts={mcts or 'off (pure argmax)'}")


if __name__ == "__main__":
    main()
