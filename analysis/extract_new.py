import json, glob, os
from collections import Counter, defaultdict

sig={648:'Grimmsnarl',743:'Alakazam',121:'Dragapult',533:'Crustle',345:'Crustle',
     678:'M-Lucario',93:'Dipplin',756:'M-Kangaskhan',190:'Archaludon',1031:'Starmie',
     381:'Cynthia-Garchomp',245:'Mewtwo?'}
def arch(d):
    c=Counter(d)
    for cid,l in sig.items():
        if c.get(cid): return l
    return 'other'
def my_deck_name(d):
    c=Counter(d)
    if c.get(93): return 'dipplin'
    if c.get(648): return 'grimmsnarl'
    if c.get(121): return 'dragapult'
    if c.get(743): return 'alakazam'
    return 'other_deck'

CUTOFF=87068934
rows=[]
for p in glob.glob('Logs/auto/*replay.json'):
    ep=int(os.path.basename(p).split('-')[1])
    if ep<=CUTOFF: continue
    try: d=json.load(open(p))
    except: continue
    names=d['info']['TeamNames']
    if 'Kilupy' not in names: continue
    rw=d['rewards']
    if rw not in ([1,-1],[-1,1]): continue
    decks=d['steps'][0][0]['visualize'][0]['action']
    for i in (0,1):
        if names[i]!='Kilupy': continue
        rows.append(dict(ep=ep,me=i,deck=my_deck_name(decks[i]),won=rw[i]==1,
                         opp=names[1-i],opp_arch=arch(decks[1-i]),path=p,
                         mirror=names[0]==names[1]))
rows.sort(key=lambda r:r['ep'])
print(f"{len(rows)} Kilupy games since ep {CUTOFF}"+(f" ({rows[0]['ep']}..{rows[-1]['ep']})" if rows else ""))
rec=defaultdict(lambda:[0,0]); h2h=defaultdict(lambda:[0,0]); nmir=0
for r in rows:
    if r['mirror']: nmir+=1; continue
    rec[r['deck']][1]+=1; rec[r['deck']][0]+=r['won']
    h2h[(r['deck'],r['opp_arch'])][1]+=1; h2h[(r['deck'],r['opp_arch'])][0]+=r['won']
print(f"(excl {nmir} self-mirror rows)\n=== RECORD BY DECK ===")
for k,(w,n) in sorted(rec.items()):
    print(f"  {k}: {w}-{n-w} ({w/n:.0%})")
print("=== MATCHUP DETAIL ===")
for (dk,oa),(w,n) in sorted(h2h.items()):
    print(f"  {dk:>11} vs {oa:<16} {w}-{n-w}")
json.dump(rows,open('/tmp/newest_games.json','w'))
