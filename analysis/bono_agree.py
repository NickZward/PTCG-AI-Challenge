#!/usr/bin/env python3
"""BONO-AGREEMENT EVALUATOR (faithful, no proxies): for every real decision bono
(#1, our exact Grimmsnarl deck) made across the Bono/ replays, feed the SAME board
state to OUR pilot and check whether we pick bono's move. Reports agreement overall,
per decision-type, and flags the contexts where we differ most from #1 — the real
playstyle gaps. Delta between pilot versions on a context (e.g. Munkidori routing)
VERIFIES a Path C change against expert play instead of noisy proxy win-rate."""
import sys, os, json, glob, importlib.util, random
from collections import defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
BONO = f"{ROOT}/Bono"

# select-type / context names for readable output
STYPE = {0:'MAIN', 1:'CARD', 2:'YESNO', 3:'ATTACK', 4:'COUNT', 5:'ENERGY', 6:'EVOLVE'}
SCTX = {13:'DMG_COUNTER', 14:'DMG_COUNTER_ANY', 15:'DAMAGE', 16:'RM_COUNTER',
        0:'SETUP_ACTIVE', 1:'SETUP_BENCH', 20:'TO_HAND', 21:'TO_FIELD', 30:'SWITCH',
        31:'TO_ACTIVE', 33:'DISCARD', 25:'EFFECT_TGT', 6:'ATTACH_TO', 5:'ATTACH_FROM'}

def load(sub):
    n = "cand_" + sub.split('/')[-1]
    spec = importlib.util.spec_from_file_location(n, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m)
    return m

def bono_idx(d):
    for i, nm in enumerate(d['info']['TeamNames']):
        if 'bono' in nm.lower(): return i
    return 0

def evaluate(sub, n_games, seed=1):
    mod = load(sub)
    files = sorted(glob.glob(f"{BONO}/*.json"))
    random.Random(seed).shuffle(files)
    files = files[:n_games]
    # agree[key] = [n_agree, n_total]; only NON-TRIVIAL decisions (>1 real option)
    by_type = defaultdict(lambda: [0, 0])
    by_ctx = defaultdict(lambda: [0, 0])
    overall = defaultdict(lambda: [0, 0])
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        bi = bono_idx(d)
        # reset our pilot's per-game tracking
        try:
            mod._TRK.update({"prized": None, "pre_ko": False, "cur_log": [], "pre_log": [], "turn_seen": -1})
        except Exception:
            pass
        for t, step in enumerate(d['steps']):
            e = step[bi] if bi < len(step) else None
            if not e:
                continue
            o = e.get('observation') or {}
            sel = o.get('select'); act = e.get('action')
            if not sel or not act:
                continue
            opts = sel.get('option') or []
            if len(opts) <= 1:
                continue                      # trivial/forced — skip
            wrapped = {'current': o.get('current'), 'select': sel, 'logs': o.get('logs', []),
                       'step': t, 'remainingOverageTime': 600,
                       'search_begin_input': o.get('search_begin_input')}
            try:
                ours = mod.agent(wrapped)
            except Exception:
                continue
            try:
                agree = set(int(x) for x in ours) == set(int(x) for x in act)
            except Exception:
                continue
            st = STYPE.get(sel.get('type'), str(sel.get('type')))
            cx = SCTX.get(sel.get('context'), f"ctx{sel.get('context')}")
            for bucket, key in [(by_type, st), (by_ctx, f"{st}:{cx}"), (overall, '_all')]:
                bucket[key][0] += int(agree); bucket[key][1] += 1
        # keep the shared cg engine happy (no battle running here — pure obs replay)
    return overall, by_type, by_ctx

if __name__ == "__main__":
    subs = sys.argv[1].split(',') if len(sys.argv) > 1 else ['grimmsnarl_v10']
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    results = {}
    for s in subs:
        ov, bt, bc = evaluate(f"{ROOT}/my-agent/{s}", N)
        results[s] = (ov, bt, bc)
        print(f"\n===== {s} : agreement with bono ({N} games, non-trivial decisions) =====")
        print(f"  OVERALL: {ov['_all'][0]}/{ov['_all'][1]} = {ov['_all'][0]/max(1,ov['_all'][1]):.1%}")
        print("  by decision TYPE:")
        for k in sorted(bt, key=lambda k: -bt[k][1]):
            a, tot = bt[k]
            if tot >= 15: print(f"    {k:<10} {a}/{tot} = {a/tot:.0%}")
        print("  where we DIFFER most from bono (context, >=20 decisions, lowest agreement):")
        rows = [(k, v[0], v[1]) for k, v in bc.items() if v[1] >= 20]
        for k, a, tot in sorted(rows, key=lambda x: x[1]/x[2])[:8]:
            print(f"    {k:<26} {a}/{tot} = {a/tot:.0%}")
    if len(subs) == 2:
        print(f"\n===== DELTA {subs[1]} vs {subs[0]} by context =====")
        _, _, bc0 = results[subs[0]]; _, _, bc1 = results[subs[1]]
        for k in sorted(set(bc0) | set(bc1)):
            a0, t0 = bc0.get(k, [0, 0]); a1, t1 = bc1.get(k, [0, 0])
            if min(t0, t1) >= 20:
                r0, r1 = a0/t0, a1/t1
                if abs(r1 - r0) >= 0.03:
                    print(f"  {k:<26} {r0:.0%} -> {r1:.0%}  ({r1-r0:+.0%})")
