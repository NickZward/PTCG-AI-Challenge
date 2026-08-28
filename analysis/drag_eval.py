import sys, json, os, shutil, random
sys.path.insert(0,'/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent/dipplin_v1')
sys.path.insert(0,'/Users/nickzwart/Desktop/PTCG-AI-Challenge/model')
from tuner import load_agent
from cg import game as cggame
from collections import Counter
R='/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent'
field=json.load(open('/tmp/opp_field.json'))
weights=json.load(open('/tmp/arch_weights.json'))
PILOT={'Alakazam':f'{R}/pool/alakazam_v7','Grimmsnarl':f'{R}/pool/grimmsnarl_v3',
       'Crustle':f'{R}/gauntlet/crustle','M-Lucario':f'{R}/gauntlet/mlucario',
       'Archaludon':f'{R}/gauntlet/archaludon','Starmie':f'{R}/gauntlet/starmie',
       'Dragapult':f'{R}/dragapult_v4','Dipplin':f'{R}/dipplin_v6'}
tmp='/private/tmp/claude-501/-Users-nickzwart-Desktop-PTCG-AI-Challenge/4d6207e8-48a2-4237-8e92-a6ba8f16b02b/scratchpad'+'/drag_opp'
shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
def opp_dir(arch,deck,idx):
    d=f'{tmp}/{arch}_{idx}'; os.makedirs(d,exist_ok=True)
    shutil.copy(f'{PILOT[arch]}/main.py',f'{d}/main.py')
    open(f'{d}/deck.csv','w').write('\n'.join(map(str,sorted(deck))))
    return d

drag=f'{R}/dragapult_v4'
DRAG=121; DRAK=120; DREE=119; SUPP={112,140,235,1071}  # Munkidori/Fez/Budew/Meowth
def instrumented_game(dd, opp_d):
    a,da=load_agent(dd); b,db=load_agent(opp_d)
    # alternate seat
    import random as _r
    seat=_r.randint(0,1)
    d0,d1=(da,db) if seat==0 else (db,da); ai=seat
    obs,sd=cggame.battle_start(list(d0),list(d1)); steps=0; res=None
    stuck=0; brick_turns=0; pd=0; jet=0; main_atk=0; consec=0
    while steps<4000:
        cur=obs.get('current') or {}
        if cur.get('result',-1)!=-1: res=cur['result']; break
        sel=obs.get('select')
        if sel is None: break
        you=cur.get('yourIndex',0)
        ag0=a if ai==0 else b; ag1=b if ai==0 else a
        ag=ag0 if you==0 else ag1
        if you==ai and sel.get('type')==0:
            me=cur['players'][ai]; actv=(me.get('active') or [None]); actv=actv[0] if actv and actv[0] else None
            if actv:
                aid=actv['id']; ens=[e for e in (actv.get('energies') or [])]
                # stuck: support active 0 energy, Dragapult benched charged
                if aid in SUPP and len(ens)==0 and any(x['id']==DRAG and len(x.get('energies') or [])>=2 for x in (me.get('bench') or []) if x): consec+=1
                else: consec=0
                # energy-brick: Dragapult active with 2+ same-type energy (can't pay R+P)
                if aid==DRAG and len(ens)>=2:
                    from collections import Counter as C
                    ec=C(ens)
                    if max(ec.values())>=2 and len(ec)<2: brick_turns+=1
            opts=sel.get('option') or []
            act=ag({'current':cur,'select':sel,'logs':obs.get('logs',[]),'step':steps,'remainingOverageTime':600,'search_begin_input':obs.get('search_begin_input')})
            for x in act:
                if isinstance(x,int) and x<len(opts) and opts[x].get('type')==13:
                    main_atk+=1
                    aidatk=opts[x].get('attackId')
                    # Phantom Dive attackId vs Jet Headbutt - track both
        else:
            act=ag({'current':cur,'select':sel,'logs':obs.get('logs',[]),'step':steps,'remainingOverageTime':600,'search_begin_input':obs.get('search_begin_input')})
        if consec>=3: stuck=1
        obs=cggame.battle_select([int(x) for x in act]); steps+=1
    me_f=(obs.get('current') or {}).get('players',[{},{}])[ai]; op_f=(obs.get('current') or {}).get('players',[{},{}])[1-ai]
    won=res==ai
    mode='WIN' if won else ('deckout' if (me_f.get('deckCount') or 0)==0 else ('prized' if len(op_f.get('prize') or [])==0 else 'other'))
    cggame.battle_finish()
    return won,mode,stuck,brick_turns,main_atk

N_PER=40
pilotable=[a for a in PILOT]
results={}; agg_w=agg_t=0; loss_modes=Counter(); stuck_games=0; brick_total=0; games_run=0
for a in pilotable:
    decks=field.get(a,[])
    if not decks: continue
    w=t=0
    for i in range(N_PER):
        deck=decks[i%len(decks)]
        od=opp_dir(a,deck,i%len(decks))
        won,mode,st,br,atk=instrumented_game(drag,od)
        t+=1; w+=int(won); games_run+=1
        loss_modes[mode]+=1; stuck_games+=st; brick_total+=br
    results[a]=(w,t)
    agg_w+=w*weights.get(a,1)/N_PER; agg_t+=weights.get(a,1)
    print(f"  drag vs {a:<12} {w}/{t} = {w/t:.0%}", flush=True)
print(f"\n=== FIELD-WEIGHTED win rate (pilotable ~84% of field): {agg_w/agg_t:.0%} ===")
print(f"loss/outcome modes: {dict(loss_modes)}")
print(f"stuck-active games: {stuck_games}/{games_run} ({stuck_games/games_run:.0%})")
print(f"energy-brick turns (Dragapult 2+ same-energy): {brick_total} across {games_run} games")
