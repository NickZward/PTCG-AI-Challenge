#!/usr/bin/env python3
"""Unified OUTCOME-based agreement backbone. The replay's action integer is an engine
canonical encoding we can't invert; instead we read what the pro ACTUALLY did from the
game LOGS (resolved effects) and compare to what our pilot's chosen option WOULD do.

Per select-context outcome signals (validated):
  FETCH  (TO_HAND)     : cardIds that reach HAND (type6 toArea=2) in the resolution window
                         vs our deck[opt[pos].index].id.  (per-pick only; multi-pick LOOKING
                         decks like Alakazam attribute at episode level -> lower coverage)
  RM_COUNTER (ctx16)   : our Pokemon healed (type16 putDamageCounter=False, serial) -> 100%
                         immediate.  vs board serial of our chosen option.
  DMG_COUNTER (ctx13)  : opp Pokemon damaged (type16 putDamageCounter=True, serial). Often
                         DEFERRED (low coverage) -> reported but flagged.
  DISCARD (ctx8)       : cardIds to DISCARD (type6 toArea=3) vs our chosen option card ids.
  SWITCH/TO_ACTIVE     : new active (type8 cardIdActive / type6 toArea=4) vs our promoted card.

Compares by the semantic identity (card id set, or board serial set). Reports exact-match
rate + jaccard + coverage (how many decisions had an extractable outcome).

Usage: outcome.py <agent_dir> <replay_folder> <player_substr> [n_games]
"""
import sys, os, json, glob, importlib.util
from collections import defaultdict, Counter
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))

# select-context ids
TO_HAND, DISCARD_C, DMG_COUNTER, RM_COUNTER, SWITCH_C, TO_ACTIVE = 7, 8, 13, 16, 3, 4
FETCH_CTX = {7, 6, 5}          # TO_HAND/TO_FIELD/TO_BENCH deck fetches
AREA_ACTIVE, AREA_BENCH, AREA_HAND, AREA_DISCARD, AREA_DECK = 4, 5, 2, 3, 1

def load(sub):
    n = "cand_" + os.path.basename(sub)
    spec = importlib.util.spec_from_file_location(n, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m)
    return m

def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1

def _card(obj):
    return (obj.get('serial'), obj.get('id')) if isinstance(obj, dict) else (None, None)

def board_at(cur, playerIndex, area, index):
    """Resolve an option's board slot to (serial, cardId)."""
    ps = (cur.get('players') or [None, None])
    if playerIndex is None or playerIndex >= len(ps): return (None, None)
    p = ps[playerIndex] or {}
    if area == AREA_ACTIVE:
        lst = p.get('active') or []
    elif area == AREA_BENCH:
        lst = p.get('bench') or []
    else:
        return (None, None)
    if index is not None and index < len(lst):
        return _card(lst[index])
    return (None, None)

def deck_id(deck, i):
    if i is None or not (0 <= i < len(deck)): return None
    return _card(deck[i])[1]

def window_logs(steps, pi, t, base, max_ahead=10, stop_on_action=True):
    """New log dicts for player pi from t+1 until pi's next action (or max_ahead)."""
    out = []
    b = base
    for t2 in range(t + 1, min(t + max_ahead, len(steps))):
        e2 = steps[t2][pi] if pi < len(steps[t2]) else None
        if not e2: continue
        logs2 = (e2.get('observation') or {}).get('logs') or []
        if len(logs2) > b:
            out.extend(L for L in logs2[b:] if isinstance(L, dict))
            b = len(logs2)
        if stop_on_action and e2.get('action') and t2 > t + 1:
            break
    return out

def pro_outcome(steps, pi, t, sel, cur, new):
    """Semantic outcome of the pro's decision, read from logs. Returns (kind, key) or None."""
    ctx = sel.get('context'); typ = sel.get('type')
    if typ == 1 and ctx in FETCH_CTX and (sel.get('deck')):
        got = tuple(sorted(L.get('cardId') for L in new
                    if L.get('type') == 6 and L.get('toArea') == AREA_HAND and L.get('playerIndex') == pi))
        return ('fetch', got) if got else None
    if typ == 1 and ctx == RM_COUNTER:
        s = tuple(sorted(L.get('serial') for L in new
                  if L.get('type') == 16 and L.get('putDamageCounter') is False))
        return ('rmctr', s) if s else None
    if typ == 1 and ctx == DMG_COUNTER:
        s = tuple(sorted(L.get('serial') for L in new
                  if L.get('type') == 16 and L.get('putDamageCounter') is True))
        return ('dmgctr', s) if s else None
    if typ == 1 and ctx == DISCARD_C:
        got = tuple(sorted(L.get('cardId') for L in new
                    if L.get('type') == 6 and L.get('toArea') == AREA_DISCARD and L.get('playerIndex') == pi))
        return ('discard', got) if got else None
    if typ == 1 and ctx in (SWITCH_C, TO_ACTIVE):
        # new active promoted: type8 (retreat swap) cardIdBench->active, or type6 toArea=ACTIVE
        prom = [L.get('cardIdActive') for L in new if L.get('type') == 8 and L.get('playerIndex') == pi]
        prom += [L.get('cardId') for L in new if L.get('type') == 6 and L.get('toArea') == AREA_ACTIVE and L.get('playerIndex') == pi]
        prom = tuple(sorted(x for x in prom if x is not None))
        return ('switch', prom) if prom else None
    return None

def our_outcome(kind, obs_sel, cur, deck, positions):
    """What our pilot's chosen option positions resolve to, in the same semantic space."""
    opts = obs_sel.get('option') or []
    try:
        if kind == 'fetch':
            return tuple(sorted(deck_id(deck, opts[p].get('index')) for p in positions if 0 <= p < len(opts)))
        if kind in ('rmctr', 'dmgctr'):
            return tuple(sorted(board_at(cur, opts[p].get('playerIndex'), opts[p].get('area'), opts[p].get('index'))[0]
                                for p in positions if 0 <= p < len(opts)))
        if kind in ('discard', 'switch'):
            out = []
            me_i = cur.get('yourIndex', 0)
            hand = ((cur.get('players') or [None, None])[me_i] or {}).get('hand') or []
            for p in positions:
                if not (0 <= p < len(opts)): continue
                op = opts[p]
                s, cid = board_at(cur, op.get('playerIndex'), op.get('area'), op.get('index'))
                if cid is None and op.get('area') == AREA_DECK:
                    cid = deck_id(deck, op.get('index'))
                if cid is None and op.get('area') == AREA_HAND:
                    hi = op.get('index')
                    if hi is not None and hi < len(hand) and isinstance(hand[hi], dict):
                        cid = hand[hi].get('id')
                out.append(cid if kind in ('discard', 'switch') else s)
            return tuple(sorted(x for x in out if x is not None))
    except Exception:
        return None
    return None

def evaluate(agent_dir, folder, psub, n_games):
    mod = load(agent_dir)
    files = sorted(glob.glob(f"{folder}/*.json"))[:n_games]
    stat = defaultdict(lambda: [0, 0, 0, 0.0])  # kind -> [n_decisions, extracted, exact, jaccard]
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
            opts = sel.get('option') or []
            if len(opts) <= 1: continue
            cur = o.get('current') or {}; deck = sel.get('deck') or []
            base = len(o.get('logs') or [])
            new = window_logs(steps, pi, t, base, max_ahead=(12 if sel.get('context') == DMG_COUNTER else 8))
            po = pro_outcome(steps, pi, t, sel, cur, new)
            if po is None: continue
            kind, pro_key = po
            stat[kind][0] += 1
            wrapped = {'current': cur, 'select': sel, 'logs': o.get('logs', []),
                       'step': t, 'remainingOverageTime': 600, 'search_begin_input': o.get('search_begin_input')}
            try:
                positions = [int(x) for x in mod.agent(wrapped)]
            except Exception:
                continue
            our_key = our_outcome(kind, sel, cur, deck, positions)
            if our_key is None: continue
            stat[kind][1] += 1
            pk, ok = Counter(pro_key), Counter(our_key)
            stat[kind][2] += int(pk == ok)
            inter = sum((pk & ok).values()); union = sum((pk | ok).values())
            stat[kind][3] += (inter / union if union else 0.0)
    return stat

if __name__ == "__main__":
    ad, folder, psub = sys.argv[1], sys.argv[2], sys.argv[3]
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 9999
    stat = evaluate(ad, folder, psub, N)
    print(f"\n{os.path.basename(ad)} vs {psub}: OUTCOME agreement (from game logs)")
    print(f"{'outcome':<12}{'decisions':>10}{'extracted':>11}{'exact%':>8}{'jaccard':>9}")
    for k in sorted(stat, key=lambda x: -stat[x][1]):
        n, ne, ex, jac = stat[k]
        flag = "  (deferred-low-cov)" if (n and ne / n < 0.3) else ""
        print(f"  {k:<10}{n:>10}{ne:>11}{ex/max(1,ne):>7.0%}{jac/max(1,ne):>9.2f}{flag}")
