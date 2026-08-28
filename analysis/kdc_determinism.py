#!/usr/bin/env python3
"""Is the REAL agent even deterministic on a given observation? mcts_agent re-rolls our hidden
zones (deck/prize) through determinize_for_search before search_begin, so for selects that index
into the DECK (context TO_HAND etc.) the search state's option list refers to a RESHUFFLED deck.
Run each sampled decision 5x and report how often the 5 answers agree, split by context."""
import os, sys, json, random
from collections import defaultdict

os.environ.setdefault("PTCG_STOP", "25"); os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import field_gauntlet as FG
import importlib.util

AGENT, RECS, NS = sys.argv[1], sys.argv[2], int(sys.argv[3])
FG._purge_private(); FG._prime_path(AGENT)
spec = importlib.util.spec_from_file_location("vv", os.path.join(ROOT, AGENT, "main.py"))
mod = importlib.util.module_from_spec(spec); sys.modules["vv"] = mod; spec.loader.exec_module(mod)

recs = [json.loads(l) for l in open(RECS)]
random.seed(11)
sample = random.sample(recs, min(NS, len(recs)))
byfile = defaultdict(list)
for r in sample:
    byfile[r["f"]].append(r)
stat = defaultdict(lambda: [0, 0])
for fn, rs in byfile.items():
    S = json.load(open("/Users/nickzwart/Desktop/kdcyberdude/" + fn))["steps"]
    for r in rs:
        o = S[r["t"]][r["seat"]]["observation"]
        w = {"current": o.get("current"), "select": o.get("select"), "logs": o.get("logs", []),
             "step": r["t"], "remainingOverageTime": 600,
             "search_begin_input": o.get("search_begin_input")}
        outs = set()
        for _ in range(5):
            mod._SPENT[0] = 0.0
            try:
                outs.add(tuple(sorted(int(x) for x in mod.agent(w))))
            except Exception:
                outs.add(("EXC",))
        k = "stype%d/ctx%d" % (r["stype"], r["sctx"])
        stat[k][0] += (len(outs) == 1); stat[k][1] += 1
        stat["ALL"][0] += (len(outs) == 1); stat["ALL"][1] += 1
for k, v in sorted(stat.items(), key=lambda x: -x[1][1])[:15]:
    print("%-16s stable %d/%d = %.1f%%" % (k, v[0], v[1], 100.0 * v[0] / v[1]))
