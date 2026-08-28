#!/usr/bin/env python3
"""VALIDATION: does the fast policy-argmax path in kd_probe.py reproduce what the REAL deployed
agent (main.py -> mcts_agent, SEARCH=1) returns on the same observation? Loads the agent through
round_robin.load() with field_gauntlet._purge_private()/_prime_path() exactly as the gauntlet
does, then calls mod.agent() on a random sample of the recorded decisions.

Usage: kd_validate.py <agent_dir> <recorded.jsonl> <n_sample>
"""
import os, sys, json, glob, random

os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import field_gauntlet as FG
import round_robin as RR
import importlib.util

AGENT, RECS, NS = sys.argv[1], sys.argv[2], int(sys.argv[3])

FG._purge_private(); FG._prime_path(AGENT)
nm = "v_" + os.path.basename(AGENT)
spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, AGENT, "main.py"))
mod = importlib.util.module_from_spec(spec); sys.modules[nm] = mod; spec.loader.exec_module(mod)
sys.stderr.write("agent=%s SEARCH=%s mcts_agent from %s\n" %
                 (AGENT, mod.SEARCH, sys.modules["mcts_agent"].__file__))

recs = [json.loads(l) for l in open(RECS)]
random.seed(7)
sample = random.sample(recs, min(NS, len(recs)))
byfile = {}
for r in sample:
    byfile.setdefault(r["f"], []).append(r)

import np_common as NN
from cg.api import to_observation_class

ok = tot = 0
mism = []
for fn, rs in byfile.items():
    d = json.load(open("/Users/nickzwart/Desktop/kdcyberdude/" + fn))
    S = d["steps"]
    for r in rs:
        mod._SPENT[0] = 0.0                       # _reset_budgets equivalent
        e = S[r["t"]][r["seat"]]
        o = e["observation"]
        wrapped = {"current": o.get("current"), "select": o.get("select"), "logs": o.get("logs", []),
                   "step": r["t"], "remainingOverageTime": 600,
                   "search_begin_input": o.get("search_begin_input")}
        try:
            got = sorted(int(x) for x in mod.agent(wrapped))
        except Exception as ex:
            mism.append((fn, r["t"], "EXC", str(ex)[:60])); tot += 1; continue
        oc = to_observation_class(wrapped)
        actions = NN.enumerate_actions(oc.select, cap=64)
        want = sorted(actions[r["top"]])
        tot += 1
        if got == want:
            ok += 1
        else:
            mism.append((fn, r["t"], got, want, r["ncand"], r["stype"], r["sctx"]))
print("REAL-agent vs fast-policy-argmax: %d/%d = %.2f%%" % (ok, tot, 100.0 * ok / max(1, tot)))
for m in mism[:15]:
    print("  MISMATCH", m)
