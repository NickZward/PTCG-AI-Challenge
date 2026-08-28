import sys, json, os, shutil
sys.path.insert(0,'/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent/dipplin_v1')
sys.path.insert(0,'/Users/nickzwart/Desktop/PTCG-AI-Challenge/model')
from tuner import load_agent, play
R='/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent'
S='/private/tmp/claude-501/-Users-nickzwart-Desktop-PTCG-AI-Challenge/4d6207e8-48a2-4237-8e92-a6ba8f16b02b/scratchpad'
field=json.load(open('/tmp/opp_field.json'))
weights=json.load(open('/tmp/arch_weights.json'))
PILOT={'Alakazam':f'{R}/pool/alakazam_v7','Grimmsnarl':f'{R}/pool/grimmsnarl_v3',
       'Crustle':f'{R}/gauntlet/crustle','M-Lucario':f'{R}/gauntlet/mlucario',
       'Archaludon':f'{R}/gauntlet/archaludon','Starmie':f'{R}/gauntlet/starmie',
       'Dragapult':f'{R}/dragapult_v5','Dipplin':f'{R}/dipplin_v6'}
tmp=f'{S}/field_opp'; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
def opp_dir(arch,deck,idx):
    d=f'{tmp}/{arch}_{idx}'
    if not os.path.exists(d):
        os.makedirs(d); shutil.copy(f'{PILOT[arch]}/main.py',f'{d}/main.py')
        open(f'{d}/deck.csv','w').write('\n'.join(map(str,sorted(deck))))
    return d
def match(a,b,n):
    aa,da=load_agent(a); bb,db=load_agent(b)
    w=t=0
    for g in range(n):
        if g%2==0: r=play(aa,da,bb,db); win=(r==0)
        else: r=play(bb,db,aa,da); win=(r==1)
        if r in (0,1): t+=1; w+=int(win)
    return w,t
N=40
ARCHS=list(PILOT)
def field_eval(agent_dir, label):
    line=f"  {label:<14}: "; num=den=0
    for a in ARCHS:
        decks=field.get(a,[])
        if not decks: continue
        w=t=0
        for i in range(N):
            od=opp_dir(a,decks[i%len(decks)],i%len(decks))
            wi,ti=match(agent_dir,od,1); w+=wi; t+=ti
        r=w/t if t else 0
        wt=weights.get(a,1)
        line+=f"{a[:4]} {r:.0%} "
        num+=wt*r; den+=wt
    print(line+f"| FIELD-WT {num/den:.0%}", flush=True)
    return num/den
print("=== ALL THREE DECKS vs the replay-derived field (weighted by true field freq) ===")
field_eval(f'{R}/dipplin_v6','dipplin_v6')
field_eval(f'{R}/grimmsnarl_v6','grimmsnarl_v6')
field_eval(f'{R}/dragapult_v5','dragapult_v5')
