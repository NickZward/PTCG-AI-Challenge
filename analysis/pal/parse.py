import json,glob,collections,os,sys

NAMES={int(k):v for k,v in json.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/cardnames.json')).items()}
PKMN=set(json.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/pkmn_ids.json')))
FILES=sorted(glob.glob('/Users/nickzwart/Desktop/Palsystem/*.json'))

def archetype(oppnames):
    s=set(oppnames)
    def has(x): return any(x in n for n in s)
    if has('Alakazam'): return 'Alakazam'
    if has("Marnie's Grimmsnarl"): return 'Grimmsnarl'
    if has('Mega Froslass'): return 'MFroslass/MLopunny'
    if has('Mega Lopunny'): return 'MLopunny'
    if has('Dragapult'): return 'Dragapult'
    if has('Mega Lucario'): return 'MLucario'
    if has('Mega Kangaskhan'): return 'MKangaskhan'
    if has("N's Zoroark") or has('N’s Zoroark'): return 'NsZoroark'
    if has('Crustle'): return 'Crustle'
    if has('Teal Mask Ogerpon'): return 'Mirror-Ogerpon'
    if has('Mega Starmie'): return 'MStarmie'
    if has('Mega Abomasnow'): return 'MAbomasnow'
    if has("Cynthia's Garchomp"): return 'Garchomp'
    return 'Other:'+','.join(sorted(s))[:60]

def poke(c):
    if not c: return None
    return dict(id=c['id'],name=NAMES.get(c['id'],str(c['id'])),serial=c['serial'],hp=c['hp'],maxHp=c['maxHp'],
                e=len(c.get('energies') or []),ec=len(c.get('energyCards') or []),tools=len(c.get('tools') or []),
                pre=[x['serial'] for x in (c.get('preEvolution') or [])])

def side(p):
    return dict(active=[poke(c) for c in (p.get('active') or [])],
                bench=[poke(c) for c in (p.get('bench') or [])],
                prizeRem=len(p.get('prize') or []),
                deck=p.get('deckCount'),
                handCount=p.get('handCount'),
                hand=[c['id'] for c in (p.get('hand') or [])],
                discard=[c['id'] for c in (p.get('discard') or [])])

def game(f):
    d=json.load(open(f))
    tn=d['info']['TeamNames']
    if 'palsystem' not in tn: return None
    seat=tn.index('palsystem'); opp=1-seat
    won = d['rewards'][seat]==1 if d['rewards'] else None
    v=d['steps'][0][0]['visualize'][0]['current']
    oppdeck=[NAMES[c['id']] for c in v['players'][opp]['deck'] if c['id'] in PKMN]
    st=d['steps']
    decs=[]
    for i in range(1,len(st)-1):
        for s in (0,1):
            e=st[i][s]
            if e['status']!='ACTIVE': continue
            o=e.get('observation') or {}
            sel=o.get('select')
            cur=o.get('current')
            if not sel or not cur: continue
            opts=sel.get('option') or []
            act=st[i+1][s].get('action') or []
            chosen=[opts[k] for k in act if isinstance(k,int) and k<len(opts)]
            decs.append(dict(step=i,seat=s,turn=cur['turn'],ctxtype=sel.get('type'),
                             opts=opts,chosen=chosen,act=act,
                             me=side(cur['players'][seat]),op=side(cur['players'][opp]),
                             energyAttached=cur.get('energyAttached'),retreated=cur.get('retreated'),
                             stadium=[c['id'] for c in (cur.get('stadium') or [])],
                             meg=any(NAMES.get(c['id'])=='Meganium' for c in (cur['players'][seat].get('active') or [])+(cur['players'][seat].get('bench') or []) if c),
                             hand=[c['id'] for c in cur['players'][seat].get('hand') or []]))
    # logs (deltas) with step + turn + acting seat
    logs=[]
    lastturn=0
    seen=set()
    for i,s in enumerate(st):
        cur=None
        for e in s:
            c=(e.get('observation') or {}).get('current')
            if c: cur=c; break
        if cur: lastturn=cur['turn']
        for si,e in enumerate(s):
            for j,l in enumerate((e.get('observation') or {}).get('logs') or []):
                key=(i,json.dumps(l,sort_keys=True),j)
                if key in seen: continue
                seen.add(key)
                logs.append(dict(step=i,turn=lastturn,**l))
    # dedupe logs that appear in both seats at same step
    ded=[];seenk=set()
    for l in logs:
        k=(l['step'],json.dumps({a:b for a,b in l.items() if a!='step'},sort_keys=True))
        if k in seenk: continue
        seenk.add(k); ded.append(l)
    return dict(file=f,ep=d['id'],seat=seat,won=won,arch=archetype(oppdeck),oppdeck=oppdeck,
                nsteps=len(st),decs=decs,logs=ded,rewards=d['rewards'])

if __name__=='__main__':
    out=[]
    for f in FILES:
        g=game(f)
        if g: out.append(g)
    print('games',len(out))
    import pickle
    pickle.dump(out,open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','wb'))
    c=collections.Counter((g['arch'],g['won']) for g in out)
    a=collections.Counter(g['arch'] for g in out)
    for k in sorted(a,key=lambda x:-a[x]):
        w=c[(k,True)];l=c[(k,False)]
        print(f'{k:20s} {w}-{l}  n={a[k]}  {100*w/max(1,w+l):.0f}%')
    print('total', sum(1 for g in out if g['won']),'-',sum(1 for g in out if not g['won']))
