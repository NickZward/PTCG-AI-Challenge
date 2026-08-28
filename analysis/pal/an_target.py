import pickle,collections,json,statistics
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))
NAMES={int(k):v for k,v in json.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/cardnames.json')).items()}
BOSS=1182
def bd(sd):
    return [p for p in (sd['active'] or [])+(sd['bench'] or []) if p]

kos=[]   # KOs he scored
lost=[]  # his pokemon KO'd
for g in G:
    tl=sorted(g['decs'],key=lambda d:d['step'])
    prev=None
    for d in tl:
        if prev:
            # he scored KO: his prizeRem dropped
            if True:
                dk=prev['me']['prizeRem']-d['me']['prizeRem']
                oldser={p['serial']:p for p in bd(prev['op'])}
                new=bd(d['op'])
                newser={p['serial'] for p in new}|{x for p in new for x in p['pre']}
                gone=[p for s,p in oldser.items() if s not in newser]
                if len(new)>=len(bd(prev['op'])): gone=[]
                for p in gone:
                    kos.append(dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=d['turn'],name=p['name'],
                                    hpmax=p['maxHp'],wasActive=any(x['serial']==p['serial'] for x in prev['op']['active']),
                                    prizeMe=prev['me']['prizeRem'],prizeOpp=prev['op']['prizeRem'],npz=dk))
            if True:
                dl=prev['op']['prizeRem']-d['op']['prizeRem']
                oldser={p['serial']:p for p in bd(prev['me'])}
                new=bd(d['me'])
                newser={p['serial'] for p in new}|{x for p in new for x in p['pre']}
                gone=[p for s,p in oldser.items() if s not in newser]
                if len(new)>=len(bd(prev['me'])): gone=[]
                for p in gone:
                    lost.append(dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=d['turn'],name=p['name'],
                                     ec=p['ec'],wasActive=any(x['serial']==p['serial'] for x in prev['me']['active'])))
        prev=d

print('=== KOs SCORED by palsystem: n=%d (%.2f/game) ==='%(len(kos),len(kos)/126))
print(' victims:',collections.Counter(k['name'] for k in kos).most_common(14))
print(' was benched target (gusted/sniped):',sum(1 for k in kos if not k['wasActive']),'/',len(kos),
      '(%.0f%%)'%(100*sum(1 for k in kos if not k['wasActive'])/len(kos)))
print(' by turn:',dict(sorted(collections.Counter(k['turn'] for k in kos).items())))
print('\n=== HIS POKEMON KOd: n=%d (%.2f/game) ==='%(len(lost),len(lost)/126))
print(' victims:',collections.Counter(l['name'] for l in lost).most_common(12))
print(' benched (sniped):',sum(1 for l in lost if not l['wasActive']),'/',len(lost))
print(' energy cards lost with them:',dict(sorted(collections.Counter(l['ec'] for l in lost).items())))
og=[l for l in lost if l['name']=='Teal Mask Ogerpon ex']
print(' Ogerpon KOd n=%d, mean energy cards stranded %.2f, dist %s'%(len(og),statistics.mean(l['ec'] for l in og),dict(sorted(collections.Counter(l['ec'] for l in og).items()))))

print('\n=== BOSS\'S ORDERS (gust) ===')
bo=[]
for g in G:
    tl=sorted(g['decs'],key=lambda d:d['step'])
    for i,d in enumerate(tl):
        if d['seat']!=g['seat']: continue
        played=any(c['type']==7 and c.get('index') is not None and c['index']<len(d['hand']) and d['hand'][c['index']]==BOSS for c in d['chosen'])
        if not played: continue
        tgt=None
        for j in range(i+1,min(i+4,len(tl))):
            e=tl[j]
            if e['seat']!=g['seat']: break
            for c in e['chosen']:
                if c['type']==3 and c.get('playerIndex')==1-g['seat'] and c.get('area')==5:
                    idx=c.get('index')
                    bench=e['op']['bench']
                    if idx is not None and idx<len(bench): tgt=bench[idx]
            if tgt: break
        # did he attack this turn after?
        atk=None
        for j in range(i,len(tl)):
            e=tl[j]
            if e['turn']!=d['turn'] or e['seat']!=g['seat']: continue
            for c in e['chosen']:
                if c['type']==13: atk=dict(name=e['me']['active'][0]['name'] if e['me']['active'] else None,
                                           opp=e['op']['active'][0]['name'] if e['op']['active'] else None,
                                           oppHp=e['op']['active'][0]['hp'] if e['op']['active'] else None)
        bo.append(dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=d['turn'],tgt=tgt['name'] if tgt else None,
                       tgtHp=tgt['hp'] if tgt else None,tgtMax=tgt['maxHp'] if tgt else None,
                       tgtEC=tgt['ec'] if tgt else None,atk=atk,prizeMe=d['me']['prizeRem'],prizeOpp=d['op']['prizeRem']))
print(' n=%d (%.2f/game); resolved targets=%d'%(len(bo),len(bo)/126,sum(1 for b in bo if b['tgt'])))
print(' targets:',collections.Counter(b['tgt'] for b in bo).most_common(15))
print(' turn dist:',dict(sorted(collections.Counter(b['turn'] for b in bo).items())))
print(' attacked same turn:',sum(1 for b in bo if b['atk']),'/',len(bo))
print(' attacker used:',collections.Counter(b['atk']['name'] for b in bo if b['atk']).most_common())
print(' his prizes remaining when Boss played:',dict(sorted(collections.Counter(b['prizeMe'] for b in bo).items())))
print(' target was undamaged:',sum(1 for b in bo if b['tgt'] and b['tgtHp']==b['tgtMax']),'/',sum(1 for b in bo if b['tgt']))
print(' target had energy:',dict(sorted(collections.Counter(b['tgtEC'] for b in bo if b['tgt']).items())))
pickle.dump(dict(kos=kos,lost=lost,bo=bo),open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/targets.pkl','wb'))
