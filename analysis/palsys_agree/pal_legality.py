#!/usr/bin/env python3
"""Validate the off-by-one convention on palsystem's replays BEFORE trusting any agreement
number: is the seat's chosen action stored in the SAME step's entry, or the NEXT one?
Metric = fraction of actions that are a legal selection for the select we scored."""
import os, sys, json, glob

os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

AGENT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent/oger_pol"
sys.path.insert(0, AGENT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import np_common as NN
from cg.api import to_observation_class
from pal_files import palsystem_games

G = palsystem_games()
NG = int(sys.argv[1]) if len(sys.argv) > 1 else 40
c = dict(next_ok=0, next_enum=0, same_ok=0, same_enum=0, n=0)
for ep in sorted(G)[:NG]:
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
        if len(opts) < 2:
            continue
        wrapped = {"current": o.get("current"), "select": sel, "logs": o.get("logs", []),
                   "step": t, "remainingOverageTime": 600,
                   "search_begin_input": o.get("search_begin_input")}
        try:
            oc = to_observation_class(wrapped)
            if oc.current.yourIndex != pi:
                continue
            acts = NN.enumerate_actions(oc.select, cap=64)
        except Exception:
            continue
        keys = set(tuple(sorted(a)) for a in acts)
        c["n"] += 1
        for tag, a in (("next", S[t + 1][pi].get("action")), ("same", e.get("action"))):
            if not isinstance(a, list) or not a:
                continue
            if all(isinstance(x, int) and 0 <= x < len(opts) for x in a):
                c[tag + "_ok"] += 1
                if tuple(sorted(a)) in keys:
                    c[tag + "_enum"] += 1
n = c["n"]
print("decisions scored: %d over %d games" % (n, NG))
for tag in ("next", "same"):
    print("  %-5s-step action: legal-index %5.1f%%   matches an enumerated action %5.1f%%" %
          (tag, 100.0 * c[tag + "_ok"] / n, 100.0 * c[tag + "_enum"] / n))
