#!/usr/bin/env python3
"""For the WITHIN-TURN TRANSPOSITION test: dump the FULL ordered sequence of play-signatures
palsystem actually executed in every (episode, turn), INCLUDING forced single-candidate moves
(which pal_probe.py drops because they are not decisions). Without those the transposition
credit would be understated. No NN involved -> cheap."""
import os, sys, json

os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

AGENT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent/oger_pol"
sys.path.insert(0, AGENT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import np_common as NN  # noqa: E402
from cg.api import to_observation_class  # noqa: E402
from pal_files import palsystem_games  # noqa: E402
import pal_probe_sig as PS  # noqa: E402

G = palsystem_games()
OUT = sys.argv[1]
fo = open(OUT, "w")
n = 0
for ep in sorted(G):
    v = G[ep]
    d = json.load(open(v["path"]))
    pi = v["seat"]
    S = d["steps"]
    for t in range(len(S) - 1):
        e = S[t][pi]
        if e.get("status") != "ACTIVE":
            continue
        o = e.get("observation") or {}
        sel = o.get("select")
        if not sel:
            continue
        opts = sel.get("option") or []
        act = S[t + 1][pi].get("action")
        if not isinstance(act, list) or not act:
            continue
        if not all(isinstance(x, int) and 0 <= x < len(opts) for x in act):
            continue
        wrapped = {"current": o.get("current"), "select": sel, "logs": o.get("logs", []),
                   "step": t, "remainingOverageTime": 600,
                   "search_begin_input": o.get("search_begin_input")}
        try:
            oc = to_observation_class(wrapped)
            if oc.current.yourIndex != pi:
                continue
            ncand = len(NN.enumerate_actions(oc.select, cap=64))
            sig = PS.act_sig(oc, sorted(act), {})
            lab = PS.act_label(oc, sorted(act))
            turn = int(oc.current.turn)
        except Exception:
            continue
        fo.write(json.dumps({"ep": ep, "turn": turn, "t": t, "sig": repr(sig),
                             "lab": lab, "ncand": ncand}) + "\n")
        n += 1
fo.close()
sys.stderr.write("plays=%d\n" % n)
