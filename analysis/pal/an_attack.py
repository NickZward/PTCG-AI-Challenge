import pickle,collections,json,statistics
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))

def enrich(g):
    tl=sorted(g['decs'],key=lambda d:d['step'])
    bystep={d['step']:d for d in tl}; steps=sorted(bystep)
    atks=[]
    for d in tl:
        if d['seat']!=g['seat']: continue
        for ch in d['chosen']:
            if ch['type']!=13:continue
            me=d['me']; op=d['op']
            a=me['active'][0] if me['active'] else None
            oa=op['active'][0] if op['active'] else None
            after=None
            for s in steps:
                if s>d['step'] and bystep[s]['turn']>d['turn']: after=bystep[s]; break
            if after is None: after=bystep[steps[-1]]
            dmg=0; started=False
            for l in g['logs']:
                if l['step']<d['step']: continue
                if l['type']==15:
                    if started: break
                    started=True; continue
                if not started: continue
                if l['type']==16 and l.get('playerIndex')==1-g['seat'] and l.get('value',0)<0: dmg+=-l['value']
            atks.append(dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=d['turn'],step=d['step'],meg=d['meg'],
                attacker=a['name'] if a else None, attackId=ch.get('attackId'),
                myE=a['e'] if a else 0, myEC=a['ec'] if a else 0, oppE=oa['e'] if oa else 0,
                oppName=oa['name'] if oa else None, oppHp=oa['hp'] if oa else 0, oppMax=oa['maxHp'] if oa else 0,
                myHp=a['hp'] if a else 0, myMax=a['maxHp'] if a else 0,
                prizeBefore=me['prizeRem'], prizeAfter=after['me']['prizeRem'],
                dmg=dmg, ko=me['prizeRem']-after['me']['prizeRem'],
                benchOgerEC=[b['ec'] for b in me['bench'] if b['name']=='Teal Mask Ogerpon ex'],
                nbench=len(me['bench'])))
    return atks

ALL=[]
for g in G: ALL+=enrich(g)
pickle.dump(ALL,open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/attacks.pkl','wb'))
print('total attacks by palsystem:',len(ALL))

def dist(vals):
    c=collections.Counter(vals); n=len(vals)
    return ' '.join('%s:%d(%.0f%%)'%(k,c[k],100*c[k]/n) for k in sorted(c))

OG=[a for a in ALL if a['attacker']=='Teal Mask Ogerpon ex']
print('\n=== OGERPON ATTACKS n=%d (of %d total) ==='%(len(OG),len(ALL)))
for tag,sub in (('ALL',OG),('no-Meganium',[a for a in OG if not a['meg']]),('with-Meganium',[a for a in OG if a['meg']])):
    if not sub: continue
    print('\n-- %s n=%d'%(tag,len(sub)))
    print('  ENERGY CARDS on attacking Ogerpon: '+dist([a['myEC'] for a in sub]))
    print('  mean cards %.2f median %d'%(statistics.mean(a['myEC'] for a in sub),statistics.median(a['myEC'] for a in sub)))
    print('  ENERGY PROVIDED (dmg unit): '+dist([a['myE'] for a in sub]))
    print('  opp active energy: '+dist([a['oppE'] for a in sub]))
    print('  KO rate: %.1f%% (%d/%d), mean prizes %.2f'%(100*sum(1 for a in sub if a['ko']>0)/len(sub),sum(1 for a in sub if a['ko']>0),len(sub),statistics.mean(a['ko'] for a in sub)))
print('\nOgerpon energy CARDS by turn (no-Meganium / with-Meganium):')
byt=collections.defaultdict(lambda: ([],[]))
for a in OG: byt[a['turn']][1 if a['meg'] else 0].append(a['myEC'])
for t in sorted(byt):
    nm,wm=byt[t]
    print('  turn %2d  noMeg n=%2d mean=%s dist=%s | Meg n=%2d mean=%s dist=%s'%(t,len(nm),
        '%.2f'%statistics.mean(nm) if nm else '-', dict(sorted(collections.Counter(nm).items())),
        len(wm),'%.2f'%statistics.mean(wm) if wm else '-',dict(sorted(collections.Counter(wm).items()))))
print('\nAll attackers: n / KOrate / mean dmg')
for name in sorted(set(a['attacker'] for a in ALL)):
    sub=[a for a in ALL if a['attacker']==name]
    print('  %-22s n=%3d  KO%%=%.0f  prizes=%d  meanDmg=%.0f'%(name,len(sub),100*sum(1 for a in sub if a['ko']>0)/len(sub),sum(a['ko'] for a in sub),statistics.mean(a['dmg'] for a in sub)))
