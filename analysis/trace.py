#!/usr/bin/env python3
"""Turn-by-turn trace of Kilupy's decisions in one replay.
Usage: python3 /tmp/trace.py <episode_path> [--verbose]"""
import json, sys, csv
cards={}
for r in csv.DictReader(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/pokemon-tcg-ai-battle/EN_Card_Data.csv')):
    cid=int(r['Card ID'])
    if cid not in cards: cards[cid]=r['Card Name']
def cn(cid): return cards.get(cid,f'#{cid}')
OPT={0:'MAIN',1:'CARD',5:'ATTACK?',6:'ATTACK',7:'ATTACH',8:'ATTACH',13:'ATTACK',9:'ABILITY',12:'RETREAT',14:'END',3:'PLAY'}
path=sys.argv[1]; verbose='--verbose' in sys.argv
d=json.load(open(path))
names=d['info']['TeamNames']; rw=d['rewards']
mi=names.index('Kilupy') if names.count('Kilupy')==1 else 0
print(f"ep {path.split('-')[1]} | {names} | rewards {rw} | Kilupy=p{mi} {'WON' if rw[mi]==1 else 'LOST'}")
n=0
for t,step in enumerate(d['steps']):
    e=step[mi]; o=e.get('observation') or {}
    cur=o.get('current'); sel=o.get('select')
    if not cur or not sel: continue
    act=e.get('action') or []
    if sel.get('type')!=0 and not verbose: continue
    if not act and not verbose: continue
    me=cur['players'][mi]; op=cur['players'][1-mi]
    a=(me.get('active') or [None]); a=a[0] if a and a[0] else None
    oa=(op.get('active') or [None]); oa=oa[0] if oa and oa[0] else None
    bench=[b['id'] for b in (me.get('bench') or []) if b]
    obench=[b['id'] for b in (op.get('bench') or []) if b]
    hand=[c['id'] for c in (me.get('hand') or [])]
    stad=(cur.get('stadium') or [None]); stad=stad[0]['id'] if stad and stad[0] else None
    opts=sel.get('option') or []
    picked=[]
    for x in act:
        if isinstance(x,int) and x<len(opts):
            op2=opts[x]; picked.append(f"{OPT.get(op2.get('type'),op2.get('type'))}:{cn(op2.get('cardId')) if op2.get('cardId') else (op2.get('area'),op2.get('index'))}")
    if sel.get('type')==0: n+=1
    aid=a['id'] if a else None; aen=len(a.get('energies') or []) if a else 0
    print(f"m{n} s{t} act={cn(aid)}(e{aen}) bench{len(bench)} stad={cn(stad) if stad else '-'} | opp={cn(oa['id']) if oa else None}(hp{oa['hp'] if oa else 0}) obench{len(obench)} | prz {len(me.get('prize') or [])}/{len(op.get('prize') or [])} deck{me.get('deckCount')} hand{len(hand)} -> {picked}")
