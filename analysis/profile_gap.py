#!/usr/bin/env python3
"""Validity-aware gap profiler: the worklist for making a pilot behave like a pro.

For (agent_dir, replay_folder, player_substr) it replays the pro's real decisions,
feeds the same state to OUR pilot, and for every select-context reports:
  - n           : how many non-trivial decisions
  - valid%      : fraction where the pro's action is a valid INDEX into the option list
                  (< n_options). Low valid% => the recorded action is a GLOBAL index,
                  not an option index -> per-decision agreement is MEANINGLESS here and
                  the context needs a log-based learner (e.g. YES_NO/ACTIVATE).
  - agree%      : our agreement on the VALID subset only
  - miss        : addressable misses = valid decisions where we disagree
Ranked by addressable misses among VALID, index-comparable contexts (the worklist),
with INVALID contexts listed separately as "needs log-based eval".

Usage: profile_gap.py <agent_dir> <replay_folder> <player_substr> [n_games]
"""
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
    # per-context: [n, n_valid, n_agree_on_valid]
    ctx = defaultdict(lambda: [0, 0, 0])
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
            st = STYPE.get(sel.get('type'), str(sel.get('type')))
            cx = SCTX.get(sel.get('context'), f"ctx{sel.get('context')}")
            key = f"{st}:{cx}"
            ctx[key][0] += 1
            # validity: are all pro action values valid indices into the option list?
            try: pro = [int(x) for x in act]
            except Exception: continue
            valid = all(0 <= x < len(opts) for x in pro)
            if not valid:
                continue
            ctx[key][1] += 1
            wrapped = {'current': o.get('current'), 'select': sel, 'logs': o.get('logs', []),
                       'step': t, 'remainingOverageTime': 600, 'search_begin_input': o.get('search_begin_input')}
            try: ours = mod.agent(wrapped)
            except Exception: continue
            try: agree = set(int(x) for x in ours) == set(pro)
            except Exception: continue
            ctx[key][2] += int(agree)
    return ctx

if __name__ == "__main__":
    ad, folder, psub = sys.argv[1], sys.argv[2], sys.argv[3]
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 9999
    ctx = evaluate(ad, folder, psub, N)
    valid_rows, invalid_rows = [], []
    tot_n = tot_valid = tot_agree = 0
    for k, (n, nv, na) in ctx.items():
        if n < 20: continue
        vpct = nv / max(1, n)
        tot_n += n; tot_valid += nv; tot_agree += na
        if vpct >= 0.9:
            valid_rows.append((k, n, nv, na, nv - na))
        else:
            invalid_rows.append((k, n, nv, vpct))
    print(f"\n{os.path.basename(ad)} vs {psub}: {tot_agree}/{tot_valid} = "
          f"{tot_agree/max(1,tot_valid):.1%} agreement on {tot_valid} index-valid decisions "
          f"({tot_n} total)")
    print("\n=== WORKLIST: index-valid contexts, ranked by addressable misses ===")
    print(f"{'context':<24}{'n':>7}{'agree%':>8}{'miss':>7}")
    for k, n, nv, na, miss in sorted(valid_rows, key=lambda x: -x[4]):
        print(f"  {k:<22}{n:>7}{na/max(1,nv):>7.0%}{miss:>7}")
    if invalid_rows:
        print("\n=== NEEDS LOG-BASED EVAL (action is a global index, not an option index) ===")
        print(f"{'context':<24}{'n':>7}{'valid%':>8}")
        for k, n, nv, vpct in sorted(invalid_rows, key=lambda x: -x[1]):
            print(f"  {k:<22}{n:>7}{vpct:>7.0%}")
