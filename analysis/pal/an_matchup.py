import pickle,collections,statistics,json,sys
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))
T=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/turns.pkl','rb'))
A=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/attacks.pkl','rb'))
TG=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/targets.pkl','rb'))
def bd(sd): return [p for p in (sd['active'] or [])+(sd['bench'] or []) if p]

# ---- opponent attacks against him
oppatk=[]
for g in G:
    tl=sorted(g['decs'],key=lambda d:d['step'])
    for i,d in enumerate(tl):
        if d['seat']==g['seat']: continue
        for c in d['chosen']:
            if c['type']!=13: continue
            oa=d['op']['active'][0] if d['op']['active'] else None
            ma=d['me']['active'][0] if d['me']['active'] else None
            oppatk.append(dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=d['turn'],
                atkr=oa['name'] if oa else None,attackId=c.get('attackId'),
                tgt=ma['name'] if ma else None,tgtHp=ma['hp'] if ma else None,tgtMax=ma['maxHp'] if ma else None,
                tgtEC=ma['ec'] if ma else None))

def matchup(arch):
    sub=[g for g in G if g['arch']==arch]
    W=[g for g in sub if g['won']]; L=[g for g in sub if not g['won']]
    eps={g['ep']:g['won'] for g in sub}
    print('\n########## %s  %d-%d ##########'%(arch,len(W),len(L)))
    # his attacks
    for tag,flag in (('WINS',True),('LOSSES',False)):
        at=[a for a in A if a['ep'] in eps and eps[a['ep']]==flag]
        tr=[r for r in T if r['ep'] in eps and eps[r['ep']]==flag]
        ng=len(W) if flag else len(L)
        if ng==0: continue
        og=[a for a in at if a['attacker']=='Teal Mask Ogerpon ex']
        hy=[a for a in at if a['attacker']=='Hydrapple ex']
        firsts=[]
        pg=collections.defaultdict(list)
        for r in tr: pg[r['ep']].append(r)
        for ep,rs in pg.items():
            aa=[x['turn'] for x in rs if x['atk']]
            if aa: firsts.append(min(aa))
        print(' %-7s n=%d | attacks/game %.2f (Oger %.2f, Hydra %.2f) | 1st-attack turn mean %.1f med %s'%(
            tag,ng,len(at)/ng,len(og)/ng,len(hy)/ng,statistics.mean(firsts) if firsts else 0,statistics.median(firsts) if firsts else '-'))
        if og: print('          Ogerpon: meanEcards %.2f dist %s | KO%% %.0f | oppActiveE mean %.2f'%(
            statistics.mean(a['myEC'] for a in og),dict(sorted(collections.Counter(a['myEC'] for a in og).items())),
            100*sum(1 for a in og if a['ko']>0)/len(og), statistics.mean(a['oppE'] for a in og)))
        if hy: print('          Hydrapple: meanEcards %.2f | KO%% %.0f | mean dmg %.0f'%(
            statistics.mean(a['myEC'] for a in hy),100*sum(1 for a in hy if a['ko']>0)/len(hy),statistics.mean(a['dmg'] for a in hy)))
        oa=[o for o in oppatk if o['ep'] in eps and eps[o['ep']]==flag]
        print('          opp attacks/game %.2f ; their attackers %s'%(len(oa)/ng,collections.Counter(o['atkr'] for o in oa).most_common(4)))
        lostp=[l for l in TG['lost'] if l['ep'] in eps and eps[l['ep']]==flag]
        print('          he loses %.2f pokemon/game: %s ; energy stranded/game %.2f'%(
            len(lostp)/ng,collections.Counter(l['name'] for l in lostp).most_common(4),sum(l['ec'] for l in lostp)/ng))
        kosc=[k for k in TG['kos'] if k['ep'] in eps and eps[k['ep']]==flag]
        print('          he KOs %.2f/game: %s ; first KO turn mean %.1f'%(len(kosc)/ng,collections.Counter(k['name'] for k in kosc).most_common(4),
            statistics.mean([min(k['turn'] for k in kosc if k['ep']==ep) for ep in set(k['ep'] for k in kosc)]) if kosc else 0))
        # turns where he could not attack
        noatk=[r for r in tr if not r['atk'] and r['turn']>=3]
        print('          turns(>=3) without attack: %.0f%% (%d/%d)'%(100*len(noatk)/max(1,len([r for r in tr if r['turn']>=3])),len(noatk),len([r for r in tr if r['turn']>=3])))

for a in ('Alakazam','Grimmsnarl','MFroslass/MLopunny','Dragapult','MKangaskhan','MLucario'):
    matchup(a)

print('\n\n=== WHAT KOs HIM, by archetype (opponent attacker -> his pokemon) ===')
for arch in ('Alakazam','Grimmsnarl'):
    print('--',arch)
    sub={g['ep']:g['won'] for g in G if g['arch']==arch}
    oa=[o for o in oppatk if o['ep'] in sub]
    print('  their attacks: ',collections.Counter((o['atkr'],o['attackId']) for o in oa).most_common(8))
    lostp=[l for l in TG['lost'] if l['ep'] in sub]
    print('  his losses: ',collections.Counter(l['name'] for l in lostp).most_common(8))
    print('  his losses by turn: ',dict(sorted(collections.Counter(l['turn'] for l in lostp).items())))
    print('  energy stranded dist: ',dict(sorted(collections.Counter(l['ec'] for l in lostp).items())))
