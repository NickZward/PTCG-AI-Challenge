#!/usr/bin/env python3
"""Extract imitation training decisions from the top-player manifest (path + explicit side).
Usage: extract_manifest.py <manifest.csv> [min_winrate=0.0] [out.pkl]
Each sample = {ei,ev,eo,di,dv,do, pol(+1 expert/-1 else), val(shaped), wr, won}."""
import json, os, sys, csv, pickle
from collections import defaultdict
ROOT="/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT,"my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT,"analysis/az_nn"))
from cg.api import to_observation_class
import nn_common as NN
OUR_DECK=[int(x) for x in open(os.path.join(ROOT,"my-agent/grimmsnarl_v17/deck.csv")).read().split()]

def shaped_value(fp, seat):
    try:
        pm=6-len((fp[seat].get("prize")) or []); po=6-len((fp[1-seat].get("prize")) or [])
        return max(-1.0,min(1.0,(pm-po)/6.0))
    except: return None

def extract_seat(r, seat, wr, won, samples):
    steps=r.get("steps",[]); fp=None
    for step in reversed(steps):
        for ent in step:
            pls=(((ent or {}).get("observation") or {}).get("current") or {}).get("players")
            if pls and len(pls)==2 and pls[0] and pls[1]: fp=pls; break
        if fp: break
    val=shaped_value(fp,seat) if fp else None
    if val is None: return 0
    added=0
    for step in steps:
        ent=step[seat] if seat<len(step) else None
        if not ent: continue
        o=ent.get("observation") or {}; sel=o.get("select"); act=ent.get("action"); cur=o.get("current")
        if not sel or not act or not cur or sel.get("type")!=0: continue
        opts=sel.get("option") or []
        if len(opts)<=1: continue
        chosen=[int(x) for x in act if isinstance(x,int) and x<len(opts)]
        if not chosen: continue
        try:
            oc=to_observation_class({"current":cur,"select":sel,"logs":o.get("logs",[]),"step":0,
                                     "search_begin_input":o.get("search_begin_input")})
            actions=NN.enumerate_actions(oc.select,64); cs=set(chosen)
            tgt=next((j for j,a in enumerate(actions) if set(a)==cs),None)
            if tgt is None: continue
            se=NN.get_encoder_input(oc,OUR_DECK); sd=NN.get_decoder_input(oc,actions)
            samples.append({"ei":se.index,"ev":se.value,"eo":se.offset,"di":sd.index,"dv":sd.value,"do":sd.offset,
                            "pol":[1.0 if j==tgt else -1.0 for j in range(len(actions))],"val":float(val),"wr":wr,"won":won})
            added+=1
        except: continue
    return added

byp=defaultdict(list); minwr=float(sys.argv[2]) if len(sys.argv)>2 else 0.0
for row in csv.DictReader(open(sys.argv[1])):
    if float(row["player_winrate"])>=minwr:
        byp[row["path"]].append((int(row["side"]),float(row["player_winrate"]),int(row["won"])))
samples=[]; ng=0
for path,sides in byp.items():
    try: r=json.load(open(path))
    except: continue
    for seat,wr,won in sides: extract_seat(r,seat,wr,won,samples)
    ng+=1
    if ng%500==0: print(f"  {ng}/{len(byp)} games -> {len(samples)} decisions",flush=True)
out=sys.argv[3] if len(sys.argv)>3 else os.path.join(ROOT,"model/az/grimm_imitation.pkl")
os.makedirs(os.path.dirname(out),exist_ok=True)
pickle.dump(samples,open(out,"wb"),protocol=4)
print(f"DONE: {ng} games -> {len(samples)} decisions -> {out} ({os.path.getsize(out)/1e6:.0f}MB)")
