#!/usr/bin/env python3
"""Generalized agreement evaluator: replay a target player's real decisions, feed the
same board state to OUR pilot, measure how often we pick their move. Args:
  agree_general.py <agent_dir> <replay_folder> <player_substr> [n_games]"""
import sys, os, json, glob, importlib.util
from collections import defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
STYPE = {0:'MAIN',1:'CARD',2:'ATTACHED',3:'CARD_OR_AT',4:'ENERGY',6:'ATTACK',7:'EVOLVE',8:'COUNT',9:'YES_NO'}
SCTX = {7:'TO_HAND',8:'DISCARD',13:'DMG_COUNTER',14:'DMG_CTR_ANY',15:'DAMAGE',16:'RM_COUNTER',
        6:'TO_FIELD',5:'TO_BENCH',4:'TO_ACTIVE',3:'SWITCH',39:'DMG_CTR_CNT',40:'RM_CTR_CNT',
        38:'DRAW_CNT',21:'ATTACH_FROM',22:'ATTACH_TO',25:'EFFECT_TGT',37:'EVOLVE',43:'ACTIVATE',
        33:'SWITCH_EN',30:'DISCARD_EN',1:'SETUP_ACT',2:'SETUP_BENCH',35:'ATTACK',18:'EVOL_FROM',19:'EVOL_TO'}
def load(sub):
    n = "cand_" + os.path.basename(sub)
    spec = importlib.util.spec_from_file_location(n, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m)
    return m
def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1
def evaluate(agent_dir, folder, psub, n_games):
    mod = load(agent_dir)
    files = sorted(glob.glob(f"{folder}/*.json"))[:n_games]
    by_type = defaultdict(lambda: [0, 0]); by_ctx = defaultdict(lambda: [0, 0]); overall = [0, 0]
    for f in files:
        try: d = json.load(open(f))
        except Exception: continue
        pi = pidx(d, psub)
        if pi < 0: continue
        try: mod._TRK.update({"prized": None, "pre_ko": False, "cur_log": [], "pre_log": [], "turn_seen": -1})
        except Exception: pass
        for t, step in enumerate(d['steps']):
            e = step[pi] if pi < len(step) else None
            if not e: continue
            o = e.get('observation') or {}; sel = o.get('select'); act = e.get('action')
            if not sel or not act: continue
            opts = sel.get('option') or []
            if len(opts) <= 1: continue
            wrapped = {'current': o.get('current'), 'select': sel, 'logs': o.get('logs', []),
                       'step': t, 'remainingOverageTime': 600, 'search_begin_input': o.get('search_begin_input')}
            try: ours = mod.agent(wrapped)
            except Exception: continue
            try: agree = set(int(x) for x in ours) == set(int(x) for x in act)
            except Exception: continue
            st = STYPE.get(sel.get('type'), str(sel.get('type')))
            cx = SCTX.get(sel.get('context'), f"ctx{sel.get('context')}")
            by_type[st][0] += int(agree); by_type[st][1] += 1
            by_ctx[f"{st}:{cx}"][0] += int(agree); by_ctx[f"{st}:{cx}"][1] += 1
            overall[0] += int(agree); overall[1] += 1
    return overall, by_type, by_ctx
if __name__ == "__main__":
    ad, folder, psub = sys.argv[1], sys.argv[2], sys.argv[3]
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 50
    ov, bt, bc = evaluate(ad, folder, psub, N)
    print(f"\n{os.path.basename(ad)} vs {psub} ({N} games): OVERALL agreement {ov[0]}/{ov[1]} = {ov[0]/max(1,ov[1]):.1%}")
    print(f"{'context':<26}{'agree':>7}{'n':>7}{'miss':>7}")
    rows = [(k, v[0], v[1], v[1]-v[0]) for k, v in bc.items() if v[1] >= 20]
    for k, a, tot, miss in sorted(rows, key=lambda x: -x[3])[:14]:
        print(f"  {k:<26}{a/tot:>6.0%}{tot:>7}{miss:>7}")
