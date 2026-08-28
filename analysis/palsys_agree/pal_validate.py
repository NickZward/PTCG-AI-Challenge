#!/usr/bin/env python3
"""VALIDATION: does the fast policy-argmax path in pal_probe.py reproduce what the REAL deployed
agent (main.py -> mcts_agent, SEARCH=1) returns on the same observation?
Usage: pal_validate.py <agent_dir> <recorded.jsonl> <n_sample>"""
import os, sys, json, random, collections

os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import field_gauntlet as FG
import round_robin as RR  # noqa: F401  (imported for parity with the gauntlet's load path)
import importlib.util
from pal_files import palsystem_games

AGENT, RECS, NS = sys.argv[1], sys.argv[2], int(sys.argv[3])
FG._purge_private(); FG._prime_path(AGENT)
nm = "v_" + os.path.basename(AGENT)
spec = importlib.util.spec_from_file_location(nm, os.path.join(ROOT, AGENT, "main.py"))
mod = importlib.util.module_from_spec(spec); sys.modules[nm] = mod; spec.loader.exec_module(mod)
sys.stderr.write("agent=%s SEARCH=%s mcts_agent from %s\n" %
                 (AGENT, mod.SEARCH, sys.modules["mcts_agent"].__file__))

G = palsystem_games()
recs = [json.loads(l) for l in open(RECS)]
random.seed(7)
sample = random.sample(recs, min(NS, len(recs)))
byep = collections.defaultdict(list)
for r in sample:
    byep[r["ep"]].append(r)

import np_common as NN
from cg.api import to_observation_class

STYPE = {0: 'MAIN', 1: 'CARD', 2: 'ATTACHED', 3: 'CARD_OR_AT', 4: 'ENERGY', 5: 'SKILL',
         6: 'ATTACK', 7: 'EVOLVE', 8: 'COUNT', 9: 'YES_NO', 10: 'SPEC_COND'}
ok = tot = 0
mism = collections.Counter()
for ep, rs in byep.items():
    d = json.load(open(G[ep]["path"]))
    S = d["steps"]
    for r in rs:
        try:
            mod._SPENT[0] = 0.0
        except Exception:
            pass
        e = S[r["t"]][r["seat"]]
        o = e["observation"]
        wrapped = {"current": o.get("current"), "select": o.get("select"), "logs": o.get("logs", []),
                   "step": r["t"], "remainingOverageTime": 600,
                   "search_begin_input": o.get("search_begin_input")}
        tot += 1
        try:
            got = sorted(int(x) for x in mod.agent(wrapped))
        except Exception as ex:
            mism[("EXC", str(ex)[:40])] += 1
            continue
        oc = to_observation_class(wrapped)
        actions = NN.enumerate_actions(oc.select, cap=64)
        want = sorted(actions[r["top"]])
        if got == want:
            ok += 1
        else:
            mism[(STYPE.get(r["stype"], r["stype"]), r["sctx"])] += 1
print("REAL-agent vs fast-policy-argmax: %d/%d = %.2f%%" % (ok, tot, 100.0 * ok / max(1, tot)))
for k, v in mism.most_common(12):
    print("  mismatch %-28s %d" % (str(k), v))
