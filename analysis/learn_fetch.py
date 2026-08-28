#!/usr/bin/env python3
"""Analyze Grimmsnarl fetch disagreements vs bono: for each single-card fetch decision,
compare bono's fetched card (from logs, toArea=HAND) to our pilot's pick, and tabulate the
systematic (bono, ours) disagreement pairs + board context to find the rule gap."""
import sys, os, json, glob, importlib.util
from collections import Counter, defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
CARD = {646:'Impidimp',647:'Morgrem',648:'Grimmsnarl',112:'Munkidori',104:'Froslass',
        860:'Snorunt',1079:'RareCandy',7:'DarkEnergy',1259:'Spikemuth',1197:'Xerosic',
        1086:'Nest?',1152:'?1152',1219:'?1219',1227:'?1227',1161:'?1161',1182:'?1182',
        1231:'?1231',1080:'?1080',1097:'?1097',1122:'?1122'}
def nm(c): return CARD.get(c, str(c))
def load(sub):
    spec = importlib.util.spec_from_file_location("cand", os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1
def deck_id(deck, i):
    if i is None or not (0 <= i < len(deck)): return None
    c = deck[i]; return c.get('id') if isinstance(c, dict) else c

def main():
    ad = sys.argv[1] if len(sys.argv) > 1 else "my-agent/grimmsnarl_v11"
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 192
    mod = load(ad)
    pairs = Counter(); bono_only = Counter(); ours_only = Counter()
    agree = miss = 0
    ctx_by_pair = defaultdict(Counter)
    for f in sorted(glob.glob('Bono/*.json'))[:N]:
        d = json.load(open(f)); pi = pidx(d, 'bono'); steps = d['steps']
        try: mod._TRK.update({"prized": None, "pre_ko": False, "cur_log": [], "pre_log": [], "turn_seen": -1})
        except Exception: pass
        for t, step in enumerate(steps):
            e = step[pi] if pi < len(step) else None
            if not e: continue
            o = e.get('observation') or {}; sel = o.get('select'); act = e.get('action')
            if not sel or not act: continue
            if sel.get('type') != 1 or sel.get('context') != 7: continue
            deck = sel.get('deck') or []; opts = sel.get('option') or []
            if not deck or len(opts) <= 1: continue
            if not all(op.get('area') == 1 for op in opts): continue
            base = len(o.get('logs') or []); b = base; fetched = []
            for t2 in range(t + 1, min(t + 10, len(steps))):
                e2 = steps[t2][pi] if pi < len(steps[t2]) else None
                if not e2: continue
                logs2 = (e2.get('observation') or {}).get('logs') or []
                if len(logs2) > b:
                    fetched += [L.get('cardId') for L in logs2[b:]
                                if isinstance(L, dict) and L.get('type') == 6 and L.get('toArea') == 2 and L.get('playerIndex') == pi]
                    b = len(logs2)
                if e2.get('action') and t2 > t + 1: break
            if len(fetched) != 1: continue          # focus single-card fetches
            pro = fetched[0]
            wrapped = {'current': o.get('current'), 'select': sel, 'logs': o.get('logs', []),
                       'step': t, 'remainingOverageTime': 600, 'search_begin_input': o.get('search_begin_input')}
            try:
                pos = [int(x) for x in mod.agent(wrapped)]
                ours = [deck_id(deck, opts[p].get('index')) for p in pos if 0 <= p < len(opts)]
            except Exception:
                continue
            if len(ours) != 1: continue
            our = ours[0]
            if our == pro:
                agree += 1
            else:
                miss += 1
                pairs[(nm(pro), nm(our))] += 1
                # board context: does bono's card exist in our options (could we have picked it)?
                cur = o.get('current') or {}
                p0 = (cur.get('players') or [None])[pi] or {}
                play = [x.get('id') for x in (p0.get('active') or [])] + [x.get('id') for x in (p0.get('bench') or []) if x]
                key = (nm(pro), nm(our))
                grimm = 'G' if 648 in play else '-'; imp = 'I' if 646 in play else '-'
                ctx_by_pair[key][f"play[{grimm}{imp}] nbench={len([b for b in (p0.get('bench') or []) if b])}"] += 1
    tot = agree + miss
    print(f"single-card fetch: agree {agree}/{tot} = {agree/max(1,tot):.0%}")
    print("\nTOP DISAGREEMENT PAIRS  (bono fetched  ->  we fetched):")
    for (pro, our), c in pairs.most_common(15):
        print(f"  {c:>4}  bono={pro:<11} ours={our}")
    print("\nCONTEXT for top 5 pairs:")
    for (pro, our), c in pairs.most_common(5):
        print(f"  bono={pro} / ours={our}: {dict(ctx_by_pair[(pro,our)].most_common(4))}")

if __name__ == "__main__":
    main()
