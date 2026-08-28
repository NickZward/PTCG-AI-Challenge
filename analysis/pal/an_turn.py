import pickle,collections,statistics,json
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))
NAMES={int(k):v for k,v in json.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/cardnames.json')).items()}

def slot(d,area,idx):
    s=d['me']
    if area==4: return s['active'][0] if s['active'] else None
    if area==5: return s['bench'][idx] if idx is not None and idx<len(s['bench']) else None
    return None

def turns(g):
    byturn=collections.defaultdict(list)
    for d in g['decs']:
        if d['seat']==g['seat']: byturn[d['turn']].append(d)
    out=[]
    for t in sorted(byturn):
        ds=sorted(byturn[t],key=lambda x:x['step'])
        first,last=ds[0],ds[-1]
        rec=dict(ep=g['ep'],arch=g['arch'],won=g['won'],turn=t,meg=first['meg'],
                 nd=len(ds),step0=first['step'],
                 act0=first['me']['active'][0] if first['me']['active'] else None,
                 bench0=first['me']['bench'], oppAct=first['op']['active'][0] if first['op']['active'] else None,
                 prizeMe=first['me']['prizeRem'],prizeOpp=first['op']['prizeRem'],
                 prizeMeEnd=last['me']['prizeRem'],prizeOppEnd=last['op']['prizeRem'],
                 handStart=first['hand'],deck=first['me']['deck'])
        teal_used=set(); teal_off=set(); attach=[]; atk=None; retreat=0; ends=0; cards=[]
        atkAvailNoUse=0; had_attack_opt=False
        for d in ds:
            board={}
            ch10={(c.get('area'),c.get('index')) for c in d['chosen'] if c['type']==10}
            for o in d['opts']:
                if o['type']==13: had_attack_opt=True
                if o['type']==10:
                    p=slot(d,o.get('area'),o.get('index'))
                    if p and p['name']=='Teal Mask Ogerpon ex':
                        teal_off.add(p['serial'])
                        if (o.get('area'),o.get('index')) in ch10: teal_used.add(p['serial'])
            for c in d['chosen']:
                if c['type']==8:
                    p=slot(d,c.get('inPlayArea'),c.get('inPlayIndex'))
                    attach.append((p['name'] if p else '?','active' if c.get('inPlayArea')==4 else 'bench',p['serial'] if p else None))
                elif c['type']==13:
                    a=d['me']['active'][0] if d['me']['active'] else None
                    oa=d['op']['active'][0] if d['op']['active'] else None
                    atk=dict(attackId=c.get('attackId'),name=a['name'] if a else None,e=a['e'] if a else 0,ec=a['ec'] if a else 0,
                             hp=a['hp'] if a else 0,mx=a['maxHp'] if a else 0,oppE=oa['e'] if oa else 0,
                             oppName=oa['name'] if oa else None,oppHp=oa['hp'] if oa else 0,oppMax=oa['maxHp'] if oa else 0)
                elif c['type']==12: retreat+=1
                elif c['type']==14: ends+=1
                elif c['type']==7: cards.append(NAMES.get(d['hand'][c['index']],'?') if c.get('index') is not None and c['index']<len(d['hand']) else '?')
        rec.update(teal_used=len(teal_used),teal_off=len(teal_off),attach=attach,atk=atk,retreat=retreat,
                   ended=ends,cards=cards,had_attack_opt=had_attack_opt,
                   nOger=sum(1 for b in first['me']['bench'] if b['name']=='Teal Mask Ogerpon ex')+(1 if first['me']['active'] and first['me']['active'][0]['name']=='Teal Mask Ogerpon ex' else 0))
        out.append(rec)
    return out

T=[]
for g in G: T+=turns(g)
pickle.dump(T,open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/turns.pkl','wb'))
print('his turns:',len(T),'games',len(G))

print('\n=== ATTACK vs BUILD by turn ===')
byt=collections.defaultdict(list)
for r in T: byt[r['turn']].append(r)
print(' turn   n  attacked%  attackOptAvailable%  attacked|available%  ogerAttack%')
for t in sorted(byt):
    if t>18: continue
    rs=byt[t]; n=len(rs)
    at=sum(1 for r in rs if r['atk']); av=sum(1 for r in rs if r['had_attack_opt'])
    og=sum(1 for r in rs if r['atk'] and r['atk']['name']=='Teal Mask Ogerpon ex')
    print('  %3d %4d   %5.0f%%      %5.0f%%             %5.0f%%        %5.0f%%'%(t,n,100*at/n,100*av/n,100*at/max(1,av),100*og/max(1,at)))

print('\n=== DELIBERATE PASS: attack available but not taken ===')
skip=[r for r in T if r['had_attack_opt'] and not r['atk']]
print('  n=%d of %d turns-with-attack-option (%.1f%%)'%(len(skip),sum(1 for r in T if r['had_attack_opt']),100*len(skip)/max(1,sum(1 for r in T if r['had_attack_opt']))))
print('  by turn:',dict(sorted(collections.Counter(r['turn'] for r in skip).items())))
print('  active when skipping:',collections.Counter((r['act0']['name'] if r['act0'] else None) for r in skip).most_common(6))
print('  energy-cards on active when skipping:',dict(sorted(collections.Counter((r['act0']['ec'] if r['act0'] else 0) for r in skip).items())))

print('\n=== FIRST ATTACK TURN (per game) ===')
fa=collections.Counter(); fao=collections.Counter()
pg=collections.defaultdict(list)
for r in T: pg[r['ep']].append(r)
for ep,rs in pg.items():
    a=[r for r in rs if r['atk']]
    if a: fa[min(x['turn'] for x in a)]+=1
    ao=[r for r in rs if r['atk'] and r['atk']['name']=='Teal Mask Ogerpon ex']
    if ao: fao[min(x['turn'] for x in ao)]+=1
print('  any attacker :',dict(sorted(fa.items())))
print('  Ogerpon      :',dict(sorted(fao.items())))

print('\n=== TEAL DANCE SATURATION (per his turn) ===')
c=collections.Counter()
for r in T:
    if r['teal_off']==0: continue
    c[(r['teal_off'],r['teal_used'])]+=1
tot=sum(c.values()); full=sum(n for (o,u),n in c.items() if o==u)
print('  turns with >=1 Teal Dance offered: %d ; used ALL offered: %d (%.0f%%)'%(tot,full,100*full/tot))
for k in sorted(c): print('    offered=%d used=%d : %d'%(k[0],k[1],c[k]))
