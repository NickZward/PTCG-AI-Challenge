#!/usr/bin/env python3
"""PURE imitation pretrain on the top-player Grimm corpus (no self-play — the corrected recipe).
Bigger model + 6.7x the data of the earlier 61k/27% attempt. Tracks held-out top-1 fidelity."""
import sys, os, pickle, time, random
ROOT="/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT,"my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT,"analysis/az_nn"))
import torch, nn_common as NN
from train_core import _WS, _train_epoch
data=pickle.load(open(os.path.join(ROOT,"model/az/grimm_imitation.pkl"),"rb"))
print(f"loaded {len(data)} decisions", flush=True)
random.seed(0); random.shuffle(data)
NHELD=5000
held=[_WS(d) for d in data[:NHELD]]; train=[_WS(d) for d in data[NHELD:]]
del data
model=NN.MyModel(128,8,512,4,4)   # d_model=128 (deployable embed tables) but deeper: 8 heads, 4+4 layers
print(f"params: {sum(p.numel() for p in model.parameters()):,}", flush=True)
opt=torch.optim.AdamW(model.parameters(),lr=3e-4)
cfg={"batch_size":128}; dev=torch.device("cpu")
def top1(samples):
    model.eval(); c=t=0
    with torch.inference_mode():
        for s in samples[:3000]:
            v,p=NN.eval_nn(s.sv_enc,s.sv_dec,model)
            tgt=s.policy.index(1.0) if 1.0 in s.policy else -1
            if tgt>=0:
                t+=1; c+=int(max(range(len(p)),key=lambda i:p[i])==tgt)
    return c/max(1,t)
best=0.0
for ep in range(20):
    t0=time.time(); model.train()
    loss=_train_epoch(model,opt,train,cfg,dev)
    acc=top1(held)
    print(f"epoch {ep}: loss {loss:.4f}  held-out top1 {acc:.1%}  {time.time()-t0:.0f}s", flush=True)
    torch.save(model.state_dict(), os.path.join(ROOT,"model/az/grimm_imitation.pth"))
    if acc>best:
        best=acc; torch.save(model.state_dict(), os.path.join(ROOT,"model/az/grimm_imitation_best.pth"))
        open(os.path.join(ROOT,"model/az/grimm_imitation_arch.json"),"w").write('{"model": [128, 8, 512, 4, 4]}')
print(f"BEST held-out top1: {best:.1%}  (earlier 61k attempt: 27%)")
