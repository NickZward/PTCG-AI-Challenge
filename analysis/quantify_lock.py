import json, glob, os
from collections import Counter
rows=json.load(open('/tmp/newest_games.json'))
ATTACKERS={93}  # Dipplin
SUPPORT={90,89}  # Thwackey, Grookey
lock_games=[]
for r in rows:
    if r['mirror']: continue
    d=json.load(open(r['path'])); i=r['me']
    consec=0; maxconsec=0; had_charged_bench_while_stuck=False
    for step in d['steps']:
        e=step[i]; o=e.get('observation') or {}
        cur=o.get('current'); sel=o.get('select')
        if not cur or not sel or sel.get('type')!=0: continue
        act=e.get('action') or []
        if not act: continue
        me=cur['players'][i]
        a=(me.get('active') or [None]); a=a[0] if a and a[0] else None
        if a is None: continue
        aen=len(a.get('energies') or [])
        bench=[b for b in (me.get('bench') or []) if b]
        charged_dip=any(b['id']==93 and len(b.get('energies') or [])>=1 for b in bench)
        # stuck = support active, 0 energy, ended turn (only END/attach picked), charged Dipplin benched
        opts=sel.get('option') or []
        picked_types=[opts[x].get('type') for x in act if isinstance(x,int) and x<len(opts)]
        is_pass=all(pt in (14,7,8) for pt in picked_types) if picked_types else True
        if a['id'] in SUPPORT and aen==0 and charged_dip and is_pass:
            consec+=1; maxconsec=max(maxconsec,consec)
            had_charged_bench_while_stuck=True
        else:
            consec=0
    if maxconsec>=3:
        lock_games.append((r['won'],r['opp_arch'],maxconsec,r['ep']))
print(f"Games with stuck-support-active lock (>=3 consec pass turns, charged Dipplin benched): {len(lock_games)}")
w=sum(1 for g in lock_games if g[0]); l=len(lock_games)-w
print(f"  outcome: {w} won, {l} LOST")
for won,opp,mc,ep in sorted(lock_games,key=lambda x:-x[2]):
    print(f"  {'WON ' if won else 'LOST'} vs {opp:<14} {mc} stuck-turns  ep{ep}")
