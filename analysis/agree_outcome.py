#!/usr/bin/env python3
"""Outcome-based agreement (the faithful method): the replay's action integer is an engine
canonical encoding we can't reliably invert, but the game LOGS record the actual resolved
effect. So we read what the pro ACTUALLY did from logs and compare to what our pilot's
chosen option WOULD do.

This module measures FETCH agreement: a deck-search decision resolves to a DECK->HAND move
logged as {type:6, fromArea:1(DECK), toArea:2(HAND), cardId:X}. Pro's fetched card set =
those cardIds in the new log entries after the decision. Our pilot's fetched set =
deck[ option[pos].index ].id for the positions our pilot picks (verified by probe_fetch.py
to be what the engine actually fetches).

Usage: agree_outcome.py <agent_dir> <replay_folder> <player_substr> [n_games]
"""
import sys, os, json, glob, importlib.util
from collections import defaultdict, Counter
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))

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
    if i is None or not (0 <= i < len(deck)): return None
    c = deck[i]
    return c.get('id') if isinstance(c, dict) else c

def evaluate(agent_dir, folder, psub, n_games):
    mod = load(agent_dir)
    files = sorted(glob.glob(f"{folder}/*.json"))[:n_games]
    # per select-context: [n_decisions, n_with_extractable_outcome, n_exact_match, sum_jaccard]
    stat = defaultdict(lambda: [0, 0, 0, 0.0])
    for f in files:
        try: d = json.load(open(f))
        except Exception: continue
        pi = pidx(d, psub)
        if pi < 0: continue
        try: mod._TRK.update({"prized": None, "pre_ko": False, "cur_log": [], "pre_log": [], "turn_seen": -1})
        except Exception: pass
        steps = d['steps']
        for t, step in enumerate(steps):
            e = step[pi] if pi < len(step) else None
            if not e: continue
            o = e.get('observation') or {}; sel = o.get('select'); act = e.get('action')
            if not sel or not act: continue
            if sel.get('type') not in (1, 7): continue
            deck = sel.get('deck') or []; opts = sel.get('option') or []
            if not deck or len(opts) <= 1: continue
            if not all(op.get('area') == 1 for op in opts): continue
            ctx = sel.get('context')
            cur_logs = o.get('logs') or []
            base = len(cur_logs)
            # pro outcome: cardIds that END IN HAND (toArea=2) in the new logs, gathered
            # across steps until this player's NEXT decision (fetches resolve multi-step,
            # DECK->LOOKING->HAND). type=6 move events, this player's cards.
            fetched = []
            got = False
            for t2 in range(t + 1, min(t + 10, len(steps))):
                e2 = steps[t2][pi] if pi < len(steps[t2]) else None
                if not e2: continue
                logs2 = (e2.get('observation') or {}).get('logs') or []
                if len(logs2) > base:
                    for L in logs2[base:]:
                        if (isinstance(L, dict) and L.get('type') == 6 and L.get('toArea') == 2
                                and L.get('playerIndex') == pi):
                            fetched.append(L.get('cardId'))
                    base = len(logs2)
                    got = True
                # stop once this player faces a new (different) decision
                if e2.get('action') and t2 > t + 1:
                    break
            pro_fetch = Counter(fetched) if got else None
            stat[ctx][0] += 1
            if pro_fetch is None or sum(pro_fetch.values()) == 0:
                continue
            # our pilot's fetched card set
            wrapped = {'current': o.get('current'), 'select': sel, 'logs': cur_logs,
                       'step': t, 'remainingOverageTime': 600, 'search_begin_input': o.get('search_begin_input')}
            try:
                ours = [int(x) for x in mod.agent(wrapped)]
                our_fetch = Counter(deck_id(deck, opts[p].get('index')) for p in ours if 0 <= p < len(opts))
            except Exception:
                continue
            stat[ctx][1] += 1
            exact = (pro_fetch == our_fetch)
            inter = sum((pro_fetch & our_fetch).values())
            union = sum((pro_fetch | our_fetch).values())
            stat[ctx][2] += int(exact)
            stat[ctx][3] += (inter / union if union else 0.0)
    return stat

SCTX = {7:'TO_HAND',6:'TO_FIELD',5:'TO_BENCH',8:'DISCARD',21:'ATTACH_FROM',22:'ATTACH_TO',37:'EVOLVE'}
if __name__ == "__main__":
    ad, folder, psub = sys.argv[1], sys.argv[2], sys.argv[3]
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 9999
    stat = evaluate(ad, folder, psub, N)
    print(f"\n{os.path.basename(ad)} vs {psub}: OUTCOME-based fetch agreement (from game logs)")
    print(f"{'context':<16}{'n':>7}{'extracted':>11}{'exact%':>8}{'jaccard':>9}")
    TA = TN = 0; TJ = 0.0
    for c in sorted(stat, key=lambda x: -stat[x][1]):
        n, ne, ex, jac = stat[c]
        if ne == 0: continue
        TA += ex; TN += ne; TJ += jac
        print(f"  {SCTX.get(c, 'ctx'+str(c)):<14}{n:>7}{ne:>11}{ex/ne:>7.0%}{jac/ne:>9.2f}")
    print(f"  {'TOTAL':<14}{'':>7}{TN:>11}{TA/max(1,TN):>7.0%}{TJ/max(1,TN):>9.2f}")
