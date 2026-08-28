cd /Users/nickzwart/Desktop/PTCG-AI-Challenge
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1
LOG=strategy_track/SSFULL.log
echo "== SS FULL-HISTORY REFRESH $(date) ==" > $LOG

# ---- Stage 1: parallel scrape of the 1,215 missing Sixth Sense episodes ----
python3 - >> $LOG 2>&1 <<'PY'
import json, os, time, urllib.request, random
from concurrent.futures import ThreadPoolExecutor
ids=json.load(open("/tmp/ss_missing_ids.json"))
out="scraped/ss_full"; os.makedirs(out, exist_ok=True)
def fetch(eid):
    p=os.path.join(out, f"episode-{eid}-replay.json")
    if os.path.exists(p): return "skip"
    time.sleep(random.uniform(0.1,0.4))
    try:
        req=urllib.request.Request(f"https://www.kaggleusercontent.com/episodes/{eid}.json",
                                   headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d=json.load(r)
        if not d or "steps" not in d: return "bad"
        json.dump(d, open(p,"w")); return "ok"
    except Exception as e:
        return f"err:{e}"
from collections import Counter
c=Counter(); done=0
with ThreadPoolExecutor(4) as ex:
    for res in ex.map(fetch, ids):
        c[res.split(":")[0]]+=1; done+=1
        if done%100==0: print(f"  {done}/{len(ids)} {dict(c)}", flush=True)
print("scrape done:", dict(c))
# one retry pass for errors
retry=[i for i in ids if not os.path.exists(os.path.join(out,f"episode-{i}-replay.json"))]
print(f"retrying {len(retry)}")
for i in retry:
    fetch(i); time.sleep(0.5)
have=sum(1 for i in ids if os.path.exists(os.path.join(out,f"episode-{i}-replay.json")))
print(f"final: {have}/{len(ids)} fetched")
PY

# ---- Stage 2: index + rebuild the Dragapult manifest over EVERYTHING ----
python3 analysis/index_dumps.py dump_index_ssfull.csv scraped/ss_full >> $LOG 2>&1
python3 - >> $LOG 2>&1 <<'PY'
import csv, collections
IDX=("dump_index_0810.csv dump_index_pal2.csv dump_index_kdc.csv dump_index_kdf.csv "
     "dump_index_slots2.csv dump_index_1108.csv dump_index_dragv4.csv dump_index_topfresh.csv "
     "dump_index_v5.csv dump_index_v6s.csv dump_index_harvest.csv dump_index_ssfull.csv").split()
rows=[]
for f in IDX:
    try: rows+=list(csv.DictReader(open(f)))
    except Exception: pass
seen=set(); u=[]
for r in rows:
    if r["episode"] and r["episode"] not in seen: seen.add(r["episode"]); u.append(r)
pil=collections.defaultdict(lambda:[0,0])
for r in u:
    w=int(r["winner"])
    for si,(a,p) in enumerate(((r["a0"],r["p0"]),(r["a1"],r["p1"]))):
        pil[(a,p)][0]+=(w==si); pil[(a,p)][1]+=1
out=[]; keys=set()
for r in u:
    w=int(r["winner"])
    if w<0: continue
    for si,(a,p,opp) in enumerate(((r["a0"],r["p0"],r["a1"]),(r["a1"],r["p1"],r["a0"]))):
        if a!="Dragapult" or pil[(a,p)][1]<6: continue
        k=(r["episode"],si)
        if k in keys: continue
        keys.add(k)
        wn,n=pil[(a,p)]
        out.append({"episode":r["episode"],"path":r["path"],"player":p,"side":si,
                    "won":1 if w==si else 0,"player_winrate":round(wn/n,4),"opp_deck":opp})
with open("drag_full_manifest.csv","w",newline="") as f:
    wtr=csv.DictWriter(f,fieldnames=["episode","path","player","side","won","player_winrate","opp_deck"])
    wtr.writeheader(); wtr.writerows(out)
nw=sum(1 for r in out if r["won"]==1)
ss=sum(1 for r in out if r["player"]=="Sixth Sense")
print(f"drag_full_manifest.csv: {len(out)} sides ({nw}W/{len(out)-nw}L); Sixth Sense sides: {ss}")
PY

# ---- Stage 3: extract + train drag_v6f (ONE variable vs v5: corpus += full teacher history) ----
python3 analysis/az_nn/extract_v2.py drag_full_manifest.csv model/az/imit_drag_v6f.npz \
  --deck=my-agent/drag_v5/deck.csv --feat=2 >> $LOG 2>&1
python3 analysis/az_nn/train_imit_v2.py model/az/imit_drag_v6f.npz --out=drag_v6f --epochs=10 \
  --weight=quality --value-weight=2.0 --value-lambda=0.5 \
  --boost-players="Sixth Sense" --boost=3.0 --device=mps >> $LOG 2>&1
python3 analysis/az_nn/export_numpy.py drag_v6f 120 >> $LOG 2>&1
python3 analysis/az_nn/build_agent_v2.py drag_v6f my-agent/drag_v6f --np --mcts=1 --deck=my-agent/grimm_v12_live >/dev/null 2>&1
cp my-agent/drag_v5/deck.csv my-agent/drag_v6f/deck.csv
rm -f my-agent/drag_v6f/opp_decks.json

# ---- Stage 4: gates vs drag_v5 ----
echo "== drag_v6f vs drag_v5 (run 1, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/drag_v6f my-agent/drag_v5 120 >> $LOG 2>&1
echo "== drag_v6f vs drag_v5 (replication, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/drag_v6f my-agent/drag_v5 120 >> $LOG 2>&1
rm -rf my-agent/drag_v6f/__pycache__
(cd my-agent/drag_v6f && tar -czf ~/Desktop/submission_drag_v6f.tar.gz --exclude='__pycache__' --exclude='.DS_Store' *)
echo SSFULL_DONE >> $LOG
