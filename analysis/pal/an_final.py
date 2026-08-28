import pickle,collections,statistics,json
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))
TG=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/targets.pkl','rb'))
NAMES={int(k):v for k,v in json.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/cardnames.json')).items()}
def slot(d,area,idx):
    s=d['me']
    if area==4: return s['active'][0] if s['active'] else None
    if area==5: return s['bench'][idx] if idx is not None and idx<len(s['bench']) else None

print('===== 1. ENERGY PLACEMENT: manual attach + Teal Dance target, ACTIVE vs BENCH, by turn =====')
rows=[]
for g in G:
    for d in g['decs']:
        if d['seat']!=g['seat']: continue
        ch10={(c.get('area'),c.get('index')) for c in d['chosen'] if c['type']==10}
        for o in d['opts']:
            if o['type']==10 and (o.get('area'),o.get('index')) in ch10:
                p=slot(d,o.get('area'),o.get('index'))
                if p and p['name']=='Teal Mask Ogerpon ex':
                    rows.append((d['turn'],'teal','active' if o.get('area')==4 else 'bench',p['ec'],g['won']))
        for c in d['chosen']:
            if c['type']==8:
                p=slot(d,c.get('inPlayArea'),c.get('inPlayIndex'))
                rows.append((d['turn'],'manual','active' if c.get('inPlayArea')==4 else 'bench',
                             p['ec'] if p else -1,g['won'],p['name'] if p else '?'))
tot=collections.Counter((r[1],r[2]) for r in rows)
print(' all energy placements:',dict(tot))
man=[r for r in rows if r[1]=='manual']
manog=[r for r in man if r[5]=='Teal Mask Ogerpon ex']
print(' manual attaches: %d total, %d (%.0f%%) onto an Ogerpon; of those %.0f%% went to a BENCH Ogerpon'%(
    len(man),len(manog),100*len(manog)/len(man),100*sum(1 for r in manog if r[2]=='bench')/len(manog)))
print(' by turn (Ogerpon-target placements, bench share):')
byt=collections.defaultdict(lambda:[0,0])
for r in rows:
    if r[1]=='teal' or (len(r)>5 and r[5]=='Teal Mask Ogerpon ex'):
        byt[r[0]][0 if r[2]=='active' else 1]+=1
for t in sorted(byt):
    if t>14: continue
    a,b=byt[t]; print('   turn %2d  active=%3d bench=%3d  bench%%=%.0f'%(t,a,b,100*b/max(1,a+b)))
a=sum(v[0] for v in byt.values()); b=sum(v[1] for v in byt.values())
print('   TOTAL   active=%d bench=%d bench%%=%.0f'%(a,b,100*b/(a+b)))

print('\n===== 2. ENERGY SPREAD: how many Ogerpon hold energy simultaneously (his turn starts) =====')
sp=collections.Counter(); mx=collections.Counter()
for g in G:
    seen=set()
    for d in sorted(g['decs'],key=lambda x:x['step']):
        if d['seat']!=g['seat'] or d['turn'] in seen: continue
        seen.add(d['turn'])
        og=[p for p in (d['me']['active'] or [])+(d['me']['bench'] or []) if p and p['name']=='Teal Mask Ogerpon ex']
        if not og: continue
        sp[(d['turn'],sum(1 for p in og if p['ec']>0))]+=1
        mx[(d['turn'],max(p['ec'] for p in og))]+=1
for t in range(3,13):
    c=collections.Counter({k[1]:v for k,v in sp.items() if k[0]==t})
    n=sum(c.values())
    if n: print('  turn %2d n=%3d  #Ogerpon-with-energy dist %s ; mean %.2f'%(t,n,dict(sorted(c.items())),sum(k*v for k,v in c.items())/n))

print('\n===== 3. SPECIES ROLES =====')
A=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/attacks.pkl','rb'))
present=collections.Counter(); everatk=collections.Counter()
for g in G:
    sp_g=set(); atk_g=set()
    for d in g['decs']:
        if d['seat']!=g['seat']: continue
        for p in (d['me']['active'] or [])+(d['me']['bench'] or []):
            if p: sp_g.add(p['name'])
    for a in A:
        if a['ep']==g['ep']: atk_g.add(a['attacker'])
    for s in sp_g:
        present[s]+=1
        if s in atk_g: everatk[s]+=1
print('  species        games-in-play  games-it-attacked  attacks  prizes-scored  attacks/game-present')
for s in sorted(present,key=lambda s:-present[s]):
    at=[a for a in A if a['attacker']==s]
    print('   %-22s %3d          %3d (%3.0f%%)      %4d      %4d          %.2f'%(
        s,present[s],everatk[s],100*everatk[s]/present[s],len(at),sum(a['ko'] for a in at),len(at)/present[s]))

print('\n===== 4. HYDRAPPLE scaling (its attack vs energy cards) =====')
hy=[a for a in A if a['attacker']=='Hydrapple ex']
by=collections.defaultdict(list)
for a in hy: by[a['myEC']].append(a['ko'])
print('  energy cards on Hydrapple when attacking:',dict(sorted(collections.Counter(a['myEC'] for a in hy).items())))
print('  KO rate by energy cards:',{k:'%.0f%%'%(100*sum(1 for x in v if x>0)/len(v)) for k,v in sorted(by.items())})
print('  attacks with 0-1 energy cards: %d/%d (%.0f%%)'%(sum(1 for a in hy if a['myEC']<=1),len(hy),100*sum(1 for a in hy if a['myEC']<=1)/len(hy)))

print('\n===== 5. STRANDED ENERGY vs OUTCOME =====')
per=collections.defaultdict(int)
for l in TG['lost']: per[l['ep']]+=l['ec']
wins=[per.get(g['ep'],0) for g in G if g['won']]; loss=[per.get(g['ep'],0) for g in G if not g['won']]
print('  energy CARDS lost with KOd pokemon per game: WINS mean %.2f (median %d) | LOSSES mean %.2f (median %d)'%(
    statistics.mean(wins),statistics.median(wins),statistics.mean(loss),statistics.median(loss)))
ogl=[l for l in TG['lost'] if l['name']=='Teal Mask Ogerpon ex']
print('  Ogerpon KOd n=%d ; energy cards on it: %s ; mean %.2f'%(len(ogl),dict(sorted(collections.Counter(l['ec'] for l in ogl).items())),statistics.mean(l['ec'] for l in ogl)))
perw=collections.defaultdict(int)
for l in ogl: perw[l['ep']]+=1
print('  Ogerpon lost per game: WINS %.2f | LOSSES %.2f'%(
    statistics.mean([perw.get(g['ep'],0) for g in G if g['won']]),statistics.mean([perw.get(g['ep'],0) for g in G if not g['won']])))

print('\n===== 6. OGERPON ATTACK: is it a KO-or-hold decision? =====')
og=[a for a in A if a['attacker']=='Teal Mask Ogerpon ex']
print('  predicted dmg = 30+30*(myE+oppE). vs opp active maxHp:')
buck=collections.Counter()
for a in og:
    pred=30+30*(a['myE']+a['oppE'])
    buck[(pred>=a['oppHp'], a['ko']>0)]+=1
print('   (predicted>=oppHP, gotKO):',dict(buck))
lethal=[a for a in og if 30+30*(a['myE']+a['oppE'])>=a['oppHp']]
print('   attacks where predicted dmg >= target remaining HP: %d/%d (%.0f%%)'%(len(lethal),len(og),100*len(lethal)/len(og)))
print('   overkill ratio (pred/targetHP) when lethal: median %.2f'%statistics.median([(30+30*(a['myE']+a['oppE']))/max(1,a['oppHp']) for a in lethal]))
