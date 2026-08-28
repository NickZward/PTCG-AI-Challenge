#!/usr/bin/env python3
"""Turn-by-turn trace of the ALAKAZAM player's decisions in a replay.
Usage: python3 analysis/trace_ala.py <replay_path>"""
import json, sys, csv
cards={int(r['Card ID']):r['Card Name'] for r in csv.DictReader(open('pokemon-tcg-ai-battle/EN_Card_Data.csv'))}
def cn(c): return cards.get(c,f'#{c}')
OPT={7:'PLAY',8:'ATTACH',9:'EVOLVE',10:'ABILITY',12:'RETREAT',13:'ATTACK',14:'END'}
d=json.load(open(sys.argv[1])); decks=d['steps'][0][0]['visualize'][0]['action']
mi=0 if 743 in decks[0] else 1  # Alakazam player
rw=d['rewards']; names=d['info']['TeamNames']
print(f"{names} rewards {rw} | Alakazam=p{mi} ({'WON' if rw[mi]==1 else 'LOST'})")
n=0
for t,step in enumerate(d['steps']):
    e=step[mi]; o=e.get('observation') or {}
    cur=o.get('current'); sel=o.get('select')
    if not cur or not sel: continue
    act=e.get('action') or []
    if sel.get('type')!=0 or not act: continue
    me=cur['players'][mi]; op=cur['players'][1-mi]
    a=(me.get('active') or [None]); a=a[0] if a and a[0] else None
    oa=(op.get('active') or [None]); oa=oa[0] if oa and oa[0] else None
    opts=sel.get('option') or []
    picked=[f"{OPT.get(opts[x].get('type'),opts[x].get('type'))}:{cn(opts[x].get('cardId')) if opts[x].get('cardId') else ''}" for x in act if isinstance(x,int) and x<len(opts)]
    n+=1
    print(f"m{n} act={cn(a['id']) if a else None}(e{len(a.get('energies') or []) if a else 0}) hand{len(me.get('hand') or [])} deck{me.get('deckCount')} | opp={cn(oa['id']) if oa else None}(hp{oa['hp'] if oa else 0}) ohand{op.get('handCount')} | prz{len(me.get('prize') or [])}/{len(op.get('prize') or [])} -> {picked}")
