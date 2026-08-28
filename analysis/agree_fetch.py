#!/usr/bin/env python3
"""Semantic fetch-agreement: the replay records deck-fetch actions as DECK INDICES, while
our pilot returns OPTION POSITIONS. Comparing them as raw ints (what agree_general does) is
an encoding mismatch. This decodes BOTH sides to the fetched CARD ID set and compares
semantics -> the TRUE fetch-behavior gap.

Scores CARD selects whose options index a populated deck (fetch family). For each decision:
  pro_ids  = { deck[a].id for a in pro_action }           (canonical deck-index -> card)
  our_ids  = { deck[opt[p].index].id for p in our_pick }  (our option-pos -> option.index -> card)
Reports semantic agreement by select-context.

Usage: agree_fetch.py <agent_dir> <replay_folder> <player_substr> [n_games]
"""
import sys, os, json, glob, importlib.util
from collections import defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
SCTX = {7:'TO_HAND',6:'TO_FIELD',5:'TO_BENCH',8:'DISCARD',21:'ATTACH_FROM',22:'ATTACH_TO',
        25:'EFFECT_TGT',37:'EVOLVE',18:'EVOL_FROM',19:'EVOL_TO'}

def load(sub):
    n = "cand_" + os.path.basename(sub)
    spec = importlib.util.spec_from_file_location(n, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m)
    return m

def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1

def deck_id(deck, i):
    if 0 <= i < len(deck):
        c = deck[i]
        return c.get('id') if isinstance(c, dict) else c
    return None

def evaluate(agent_dir, folder, psub, n_games):
    mod = load(agent_dir)
    files = sorted(glob.glob(f"{folder}/*.json"))[:n_games]
    by_ctx = defaultdict(lambda: [0, 0])   # [agree, n]
    raw_ctx = defaultdict(lambda: [0, 0])  # raw-int agreement for comparison
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
            if sel.get('type') not in (1, 7): continue           # CARD / EVOLVE
            deck = sel.get('deck') or []
            opts = sel.get('option') or []
            if len(opts) <= 1 or not deck: continue
            # only clean deck-fetches: options index the deck, pro action is a valid deck index
            if not all(op.get('area') == 1 and op.get('index') is not None for op in opts): continue
            try: pro = [int(x) for x in act]
            except Exception: continue
            if not all(0 <= x < len(deck) for x in pro): continue
            cx = SCTX.get(sel.get('context'), f"ctx{sel.get('context')}")
            pro_ids = tuple(sorted(deck_id(deck, x) for x in pro))
            wrapped = {'current': o.get('current'), 'select': sel, 'logs': o.get('logs', []),
                       'step': t, 'remainingOverageTime': 600, 'search_begin_input': o.get('search_begin_input')}
            try: ours = mod.agent(wrapped)
            except Exception: continue
            try:
                ours_i = [int(x) for x in ours]
                our_ids = tuple(sorted(deck_id(deck, opts[p].get('index')) for p in ours_i if 0 <= p < len(opts)))
            except Exception:
                continue
            agree = (pro_ids == our_ids)
            by_ctx[cx][0] += int(agree); by_ctx[cx][1] += 1
            # raw-int comparison (what the old tool did), for contrast
            raw = (set(pro) == set(ours_i))
            raw_ctx[cx][0] += int(raw); raw_ctx[cx][1] += 1
    return by_ctx, raw_ctx

if __name__ == "__main__":
    ad, folder, psub = sys.argv[1], sys.argv[2], sys.argv[3]
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 9999
    by_ctx, raw_ctx = evaluate(ad, folder, psub, N)
    ta = sum(v[0] for v in by_ctx.values()); tn = sum(v[1] for v in by_ctx.values())
    tr = sum(v[0] for v in raw_ctx.values())
    print(f"\n{os.path.basename(ad)} vs {psub}: SEMANTIC fetch agreement {ta}/{tn} = {ta/max(1,tn):.1%}"
          f"   (raw-int would say {tr/max(1,tn):.1%})")
    print(f"{'context':<16}{'semantic':>10}{'raw-int':>10}{'n':>7}")
    for k in sorted(by_ctx, key=lambda x: -by_ctx[x][1]):
        a, n = by_ctx[k]; r = raw_ctx[k][0]
        print(f"  {k:<14}{a/max(1,n):>9.0%}{r/max(1,n):>10.0%}{n:>7}")
