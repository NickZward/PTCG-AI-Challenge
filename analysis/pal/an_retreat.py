import pickle,collections,statistics,json
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))
NAMES={int(k):v for k,v in json.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/cardnames.json')).items()}

ev=[]
for g in G:
    tl=sorted(g['decs'],key=lambda d:d['step'])
    bystep={d['step']:d for d in tl}; steps=sorted(bystep)
    for i,d in enumerate(tl):
        if d['seat']!=g['seat']: continue
        if not any(c['type']==12 for c in d['chosen']): continue
        a=d['me']['active'][0] if d['me']['active'] else None
        if not a: continue
        # next state for this game after retreat
        nxt=None
        for s in steps:
            if s>d['step']: nxt=bystep[s]; break
        newa = nxt['me']['active'][0] if nxt and nxt['me']['active'] else None
        oldonbench=None
        if nxt:
            for b in nxt['me']['bench']:
                if b['serial']==a['serial']: oldonbench=b
        ev.append(dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=d['turn'],
                       old=a['name'],oldHp=a['hp'],oldMax=a['maxHp'],oldEC=a['ec'],oldE=a['e'],
                       oldECafter=oldonbench['ec'] if oldonbench else None,
                       new=newa['name'] if newa else None,newEC=newa['ec'] if newa else None,
                       newHp=newa['hp'] if newa else None,newMax=newa['maxHp'] if newa else None,
                       oppName=(d['op']['active'][0]['name'] if d['op']['active'] else None)))
print('=== RETREATS n=%d over %d games (%.2f/game) ==='%(len(ev),len(G),len(ev)/len(G)))
print('retreating pokemon:',collections.Counter(e['old'] for e in ev).most_common())
print('replacement:',collections.Counter(e['new'] for e in ev).most_common())
og=[e for e in ev if e['old']=='Teal Mask Ogerpon ex']
print('\n--- Ogerpon retreats n=%d'%len(og))
print(' HP%% remaining when retreating Ogerpon:',dict(sorted(collections.Counter(round(100*e['oldHp']/e['oldMax']/10)*10 for e in og).items())))
print(' damaged (hp<max):',sum(1 for e in og if e['oldHp']<e['oldMax']),'/',len(og))
print(' energy cards on retreating Ogerpon (before):',dict(sorted(collections.Counter(e['oldEC'] for e in og).items())))
print(' energy cards on it AFTER (on bench):',dict(sorted(collections.Counter(e['oldECafter'] for e in og).items())))
lost=[(e['oldEC']-e['oldECafter']) for e in og if e['oldECafter'] is not None]
print(' energy cards LOST to retreat cost:',dict(sorted(collections.Counter(lost).items())))
print(' replacement was Ogerpon:',sum(1 for e in og if e['new']=='Teal Mask Ogerpon ex'),'/',len(og), '  replacement energy cards:',dict(sorted(collections.Counter(e['newEC'] for e in og if e['newEC'] is not None).items())))
print(' replacement names:',collections.Counter(e['new'] for e in og).most_common())
print('\n--- ALL retreats: energy lost')
lost=[(e['oldEC']-e['oldECafter']) for e in ev if e['oldECafter'] is not None]
print(' ',dict(sorted(collections.Counter(lost).items())))
print('\n--- retreat by turn:',dict(sorted(collections.Counter(e['turn'] for e in ev).items())))

# switch-type trainer cards & any card play distribution
cardplays=collections.Counter()
for g in G:
    for d in g['decs']:
        if d['seat']!=g['seat']: continue
        for c in d['chosen']:
            if c['type']==7 and c.get('index') is not None and c['index']<len(d['hand']):
                cardplays[NAMES.get(d['hand'][c['index']],'?')]+=1
print('\n=== CARDS PLAYED (n=%d) ==='%sum(cardplays.values()))
for k,n in cardplays.most_common(): print('  %-30s %4d  (%.2f/game)'%(k,n,n/len(G)))
