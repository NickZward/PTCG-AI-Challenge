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
        if os.path.exists(os.path.join(d, "model_np.npz")):
            return d
    return "."


_HERE = _base()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import time

import np_common as NN
from mcts_agent import mcts_agent
from cg.api import to_observation_class

_MODEL = NN.NpModel(os.path.join(_HERE, "model_np.npz"))
_DECK = [int(x) for x in open(os.path.join(_HERE, "deck.csv")).read().split()]
SEARCH = 64
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
