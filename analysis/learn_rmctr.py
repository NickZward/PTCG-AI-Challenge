#!/usr/bin/env python3
"""Distill bono's RM_COUNTER (Munkidori heal-source) rule: for each multi-option decision,
find bono's actual choice (from the type16 heal log serial) and score candidate rules."""
import json, glob, sys
from collections import Counter
def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1
def board_obj(cur, playerIndex, area, index):
    p = (cur.get('players') or [None, None])[playerIndex] or {}
    lst = p.get('active') if area == 4 else (p.get('bench') if area == 5 else None)
    if lst and index is not None and index < len(lst) and isinstance(lst[index], dict):
        return lst[index]
    return None

MUNKI, GRIMM = 112, 648
def opt_feats(cur, op):
    o = board_obj(cur, op.get('playerIndex'), op.get('area'), op.get('index'))
    if not o: return None
    return {'serial': o.get('serial'), 'id': o.get('id'), 'hp': o.get('hp', 0),
            'maxHp': o.get('maxHp', 0), 'dmg': (o.get('maxHp', 0) - o.get('hp', 0)),
            'active': op.get('area') == 4, 'en': len(o.get('energies') or [])}

RULES = {
 'munki_first (v11)': lambda fs: min(fs, key=lambda x: (x['id'] != MUNKI,)),
 'most_damaged'     : lambda fs: max(fs, key=lambda x: x['dmg']),
 'grimm_first'      : lambda fs: min(fs, key=lambda x: (x['id'] != GRIMM,)),
 'active_first'     : lambda fs: min(fs, key=lambda x: (not x['active'],)),
 'mostdmg_then_ex'  : lambda fs: max(fs, key=lambda x: (x['dmg'], x['id'] == GRIMM)),
 'ex_then_mostdmg'  : lambda fs: max(fs, key=lambda x: (x['id'] == GRIMM, x['dmg'])),
 'lowest_hp'        : lambda fs: min(fs, key=lambda x: x['hp']),
 'munki_unless_grimm_hurt': lambda fs: (max([x for x in fs if x['id']==GRIMM], key=lambda x:x['dmg'])
        if any(x['id']==GRIMM and x['dmg']>=90 for x in fs) else min(fs, key=lambda x:(x['id']!=MUNKI,))),
}

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else 'Bono'
    psub = sys.argv[2] if len(sys.argv) > 2 else 'bono'
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 192
    scores = Counter(); total = 0; choice_dist = Counter()
    for f in sorted(glob.glob(f'{folder}/*.json'))[:N]:
        d = json.load(open(f)); pi = pidx(d, psub); steps = d['steps']
        for t, step in enumerate(steps):
            e = step[pi] if pi < len(step) else None
            if not e: continue
            o = e.get('observation') or {}; sel = o.get('select'); act = e.get('action')
            if not sel or not act: continue
            if not (sel.get('type') == 1 and sel.get('context') == 16): continue
            opts = sel.get('option') or []
            if len(opts) <= 1: continue
            cur = o.get('current') or {}
            base = len(o.get('logs') or []); b = base; healed = []
            for t2 in range(t + 1, min(t + 6, len(steps))):
                e2 = steps[t2][pi] if pi < len(steps[t2]) else None
                if not e2: continue
                logs2 = (e2.get('observation') or {}).get('logs') or []
                if len(logs2) > b:
                    healed += [L.get('serial') for L in logs2[b:]
                               if isinstance(L, dict) and L.get('type') == 16 and L.get('putDamageCounter') is False]
                    b = len(logs2)
                if e2.get('action') and t2 > t + 1: break
            if not healed: continue
            chosen = healed[0]
            fs = [opt_feats(cur, op) for op in opts]; fs = [x for x in fs if x]
            if len(fs) < 2 or chosen not in [x['serial'] for x in fs]: continue
            total += 1
            cobj = next(x for x in fs if x['serial'] == chosen)
            choice_dist[('Munki' if cobj['id']==MUNKI else 'Grimm' if cobj['id']==GRIMM else cobj['id'])] += 1
            for name, rule in RULES.items():
                try:
                    if rule(fs)['serial'] == chosen: scores[name] += 1
                except Exception:
                    pass
    print(f"RM_COUNTER decisions scored: {total}")
    print(f"bono's choice by card: {dict(choice_dist.most_common())}")
    print(f"{'rule':<28}{'agree%':>8}")
    for name, s in sorted(scores.items(), key=lambda x: -x[1]):
        print(f"  {name:<26}{s/max(1,total):>7.0%}")

if __name__ == "__main__":
    main()
