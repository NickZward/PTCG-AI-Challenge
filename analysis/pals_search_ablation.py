#!/usr/bin/env python3
"""Does the SEARCH keep or destroy the imitation?

main.py ships SEARCH=32. mcts_agent picks `max(child.visit, child_mean_value)`; with the root
breadth sweep every root child is expanded once, so on any decision with ncand>=~32 the winner is
decided by the VALUE HEAD, not the policy head. This replays palsystem's own decisions through the
SHIPPED agent code at several search depths and measures agreement with him at each.

search_count=1  -> the breadth sweep expands exactly one child (highest prior) = policy argmax.
search_count=32 -> what actually ships.

Usage: pals_search_ablation.py [agent_dir] [--games=N] [--depths=1,4,32]
"""
import csv
import importlib.util
import json
import os
import random
import sys
from collections import Counter, defaultdict

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
AGENT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "my-agent/oger_imit_f2"
AGENT_DIR = os.path.join(ROOT, AGENT)
NGAMES = int(F.get("games", 15))
DEPTHS = [int(x) for x in F.get("depths", "1,32").split(",")]

sys.path.insert(0, AGENT_DIR)
spec = importlib.util.spec_from_file_location("oger_np", os.path.join(AGENT_DIR, "np_common.py"))
PNN = importlib.util.module_from_spec(spec)
sys.modules["np_common"] = PNN
spec.loader.exec_module(PNN)
spec2 = importlib.util.spec_from_file_location("oger_mcts", os.path.join(AGENT_DIR, "mcts_agent.py"))
MC = importlib.util.module_from_spec(spec2)
sys.modules["oger_mcts"] = MC
spec2.loader.exec_module(MC)
from cg.api import to_observation_class  # noqa: E402

MODEL = PNN.NpModel(os.path.join(AGENT_DIR, "model_np.npz"))
DECK = [int(x) for x in open(os.path.join(AGENT_DIR, "deck.csv")).read().split()]
print(f"agent={AGENT} feat={MODEL.feat} depths={DEPTHS} games={NGAMES}", flush=True)

STYPE = {0: 'MAIN', 1: 'CARD', 4: 'ENERGY', 8: 'COUNT', 9: 'YES_NO'}
rows = list(csv.DictReader(open(os.path.join(ROOT, "oger_pals_manifest.csv"))))[:NGAMES]

agree = {d: 0 for d in DEPTHS}
agree_main = {d: 0 for d in DEPTHS}
pol_vs = {d: 0 for d in DEPTHS}          # depth-d pick == pure policy argmax
n = nmain = 0
wide = {d: [0, 0] for d in DEPTHS}       # agreement restricted to ncand > 32
for rec in rows:
    if not os.path.exists(rec["path"]):
        continue
    d = json.load(open(rec["path"]))
    seat = int(rec["side"])
    steps = d["steps"]
    for i, step in enumerate(steps):
        ent = step[seat] if seat < len(step) else None
        if not ent or ent.get("status") != "ACTIVE":
            continue
        o = ent.get("observation") or {}
        sel, cur = o.get("select"), o.get("current")
        nxt = steps[i + 1][seat] if (i + 1 < len(steps) and seat < len(steps[i + 1])) else None
        act = (nxt or {}).get("action")
        if not sel or act is None or not cur:
            continue
        opts = sel.get("option") or []
        if len(opts) <= 1:
            continue
        chosen = {int(x) for x in act if isinstance(x, int) and 0 <= x < len(opts)}
        if not chosen:
            continue
        od = {"current": cur, "select": sel, "logs": o.get("logs", []), "step": 0,
              "search_begin_input": o.get("search_begin_input")}
        try:
            oc = to_observation_class(od)
            acts = PNN.enumerate_actions(oc.select, 64)
            if not any(set(a) == chosen for a in acts):
                continue
            se = PNN.get_encoder_input(oc, DECK)
            sd = PNN.get_decoder_input(oc, acts)
            _, pol = PNN.eval_nn(se, sd, MODEL)
            pol_pick = set(acts[max(range(len(acts)), key=lambda k: pol[k])])
        except Exception:
            continue
        picks = {}
        ok = True
        for dep in DEPTHS:
            random.seed(12345)      # determinize_for_search is stochastic; hold it fixed
            try:
                selidx, _ = MC.mcts_agent(od, DECK, MODEL, search_count=dep)
                picks[dep] = {int(x) for x in selidx}
            except Exception:
                ok = False
                break
        if not ok:
            continue
        n += 1
        stype = int(sel.get("type", -1))
        if stype == 0:
            nmain += 1
        for dep in DEPTHS:
            hit = picks[dep] == chosen
            agree[dep] += hit
            if stype == 0:
                agree_main[dep] += hit
            pol_vs[dep] += (picks[dep] == pol_pick)
            if len(acts) > 32:
                wide[dep][0] += hit
                wide[dep][1] += 1
        if n % 200 == 0:
            print(f"  {n} decisions... " +
                  "  ".join(f"d{dep}:{agree[dep]/n:.1%}" for dep in DEPTHS), flush=True)

print(f"\n{n} decisions ({nmain} MAIN) over {NGAMES} palsystem games\n")
print(f"{'search':>8} {'agree w/ palsystem':>20} {'MAIN':>10} {'== policy argmax':>18} {'ncand>32':>12}")
for dep in DEPTHS:
    w = wide[dep]
    print(f"{dep:>8} {agree[dep]/max(1,n):>19.1%} {agree_main[dep]/max(1,nmain):>10.1%} "
          f"{pol_vs[dep]/max(1,n):>17.1%} {(w[0]/w[1] if w[1] else 0):>11.1%} (n={w[1]})")
