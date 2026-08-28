import json
from collections import Counter, defaultdict
rows=json.load(open('/tmp/newest_games.json'))

def final_state(d,i):
    st=None
    for s in reversed(d['steps']):
        for half in s:
            if (half.get('observation') or {}).get('current'): st=half['observation']['current']; break
        if st: break
    return st

detail=[]
for r in rows:
    if r['mirror']: continue
    d=json.load(open(r['path'])); i=r['me']
    attacks=0; mains=0; e2=0; max_bench=0; online_turn=None
    for step in d['steps']:
        e=step[i]; o=e.get('observation') or {}
        cur=o.get('current'); sel=o.get('select')
        if not cur: continue
        me=cur['players'][i]
        max_bench=max(max_bench,len([x for x in (me.get('bench') or []) if x]))
        act=e.get('action') or []
        if sel and act and sel.get('type')==0:
            mains+=1
            be=sum(len((x.get('energies') or [])) for x in ([y for y in (me.get('active') or []) if y]+[y for y in (me.get('bench') or []) if y]))
            if be>=2: e2+=1
        if sel and act:
            opts=sel.get('option') or []
            for a2 in act:
                if isinstance(a2,int) and a2<len(opts) and opts[a2].get('type')==13: attacks+=1
    st=final_state(d,i)
    me_f=st['players'][i]; op_f=st['players'][1-i]
    myprz=len(me_f.get('prize') or []); opprz=len(op_f.get('prize') or [])
    mydeck=me_f.get('deckCount') or 0; opdeck=op_f.get('deckCount') or 0
    if r['won']: mode='WIN'
    elif mydeck==0: mode='deckout'
    elif opprz==0: mode='prized-out'
    else: mode='timeout/other'
    detail.append(dict(deck=r['deck'],opp=r['opp_arch'],won=r['won'],mode=mode,
                       mains=mains,atk=attacks,e2=e2,bench=max_bench,
                       przTaken=6-myprz,oppPrzTaken=6-opprz,mydeck=mydeck,opdeck=opdeck,ep=r['ep']))

# loss-mode summary
print("=== LOSS MODES (dipplin) ===")
lm=Counter((x['mode']) for x in detail if x['deck']=='dipplin' and not x['won'])
for k,v in lm.most_common(): print(f"  {k}: {v}")
print("=== DIPPLIN LOSSES DETAIL ===")
for x in sorted([d for d in detail if d['deck']=='dipplin' and not d['won']], key=lambda z:(z['opp'])):
    print(f"  vs {x['opp']:<14} {x['mode']:<12} atk={x['atk']:<3} e2t={x['e2']:<3} bench={x['bench']} przTaken={x['przTaken']} oppTook={x['oppPrzTaken']} deck(me/op)={x['mydeck']}/{x['opdeck']} mains={x['mains']}")
print("=== DIPPLIN WINS (for baseline) avg ===")
wins=[x for x in detail if x['deck']=='dipplin' and x['won']]
import statistics
if wins:
    print(f"  n={len(wins)} atk={statistics.mean(x['atk'] for x in wins):.1f} e2t={statistics.mean(x['e2'] for x in wins):.1f} przTaken={statistics.mean(x['przTaken'] for x in wins):.1f} mains={statistics.mean(x['mains'] for x in wins):.0f}")
json.dump(detail,open('/tmp/loss_detail.json','w'))
