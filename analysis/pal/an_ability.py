import pickle,collections,statistics,json
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))

def slot(d,area,idx):
    s=d['me']
    if area==4: return (s['active'][0] if s['active'] else None),'active'
    if area==5:
        return (s['bench'][idx] if idx<len(s['bench']) else None),'bench'
    return None,'?'

use=collections.Counter(); avail=collections.Counter()
attach=collections.Counter()
tealbyturn=collections.defaultdict(lambda:[0,0])
declined=collections.Counter()
for g in G:
    for d in g['decs']:
        if d['seat']!=g['seat']: continue
        chosen_keys={(c.get('area'),c.get('index')) for c in d['chosen'] if c['type']==10}
        for o in d['opts']:
            if o['type']!=10: continue
            p,loc=slot(d,o.get('area'),o.get('index'))
            nm=p['name'] if p else '?'
            avail[(nm,loc)]+=1
            if (o.get('area'),o.get('index')) in chosen_keys:
                use[(nm,loc)]+=1
                if nm=='Teal Mask Ogerpon ex': tealbyturn[d['turn']][0 if loc=='active' else 1]+=1
        # energy attach targets
        for c in d['chosen']:
            if c['type']!=8: continue
            p,loc=slot(d,c.get('inPlayArea'),c.get('inPlayIndex'))
            attach[(p['name'] if p else '?',loc)]+=1
print('=== ABILITY USE (chosen / available-instances) ===')
for k in sorted(set(list(use)+list(avail)),key=lambda k:-avail[k]):
    print('  %-24s %-6s used=%4d  offered=%5d  %.0f%%'%(k[0],k[1],use[k],avail[k],100*use[k]/max(1,avail[k])))
print('\n=== MANUAL ENERGY ATTACH TARGETS (type 8) ===')
tot=sum(attach.values())
for k,n in attach.most_common(): print('  %-24s %-6s %4d (%.0f%%)'%(k[0],k[1],n,100*n/tot))
print('\n=== Teal Dance uses by turn: active vs bench ===')
ta=tb=0
for t in sorted(tealbyturn):
    a,b=tealbyturn[t]; ta+=a; tb+=b
    if t<=16: print('  turn %2d active=%3d bench=%3d  bench%%=%.0f'%(t,a,b,100*b/max(1,a+b)))
print('  TOTAL active=%d bench=%d bench%%=%.0f'%(ta,tb,100*tb/max(1,ta+tb)))
