cd /Users/nickzwart/Desktop/PTCG-AI-Challenge
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1
LOG=strategy_track/V7.log
echo "== V7 REFRESH $(date) ==" > $LOG

# ---- Stage 1: harvest new games of the top-60 leaderboard teams ----
python3 - >> $LOG 2>&1 <<'PY'
import json, csv, glob, os, time, random, urllib.request
from concurrent.futures import ThreadPoolExecutor
SCRATCH="/private/tmp/claude-501/-Users-nickzwart-Desktop-PTCG-AI-Challenge/d10d2889-ad77-4e2a-a090-d7a2e74188bf/scratchpad/lb"
lb=sorted(glob.glob(SCRATCH+"/*.csv"))[-1]
rows=list(csv.DictReader(open(lb)))
key=[k for k in rows[0] if "core" in k][0]
rows.sort(key=lambda r:-float(r[key]))
top=[r["TeamName"] for r in rows[:60]]
def le(body):
    req=urllib.request.Request("https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))
# newest known episode per team from all indexes
have=set(); newest={}
for f in glob.glob("dump_index_*.csv"):
    try:
        for r in csv.DictReader(open(f)):
            have.add(str(r["episode"]))
            for p in (r["p0"],r["p1"]):
                if p in top:
                    e=int(r["episode"] or 0)
                    if e>newest.get(p,0): newest[p]=e
    except Exception: pass
for d in glob.glob("scraped/*/episode-*-replay.json"):
    have.add(os.path.basename(d).split("-")[1])
print(f"top-60 teams resolvable from indexes: {len(newest)}")
new=set()
for team,ep in sorted(newest.items()):
    try:
        d=le({"ids":[ep]})
        subs=set()
        for t in d.get("teams",[]):
            if t.get("teamName")==team and t.get("publicLeaderboardSubmissionId"):
                subs.add(t["publicLeaderboardSubmissionId"])
                tid=t["id"]
                for e in d.get("episodes",[]):
                    for a in e.get("agents",[]):
                        if a.get("teamId")==tid and a.get("submissionId"): subs.add(a["submissionId"])
        for s in subs:
            d2=le({"submissionId":s})
            ids=[x["id"] for x in d2.get("episodes",[]) if x.get("state")=="COMPLETED"]
            new |= {i for i in ids if str(i) not in have}
        time.sleep(0.4)
    except Exception as e:
        print(f"  {team}: {e}")
new=sorted(new)[-1500:]
print(f"NEW episodes to scrape (capped 1500): {len(new)}")
out="scraped/top60_0814"; os.makedirs(out, exist_ok=True)
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
    except Exception:
        return "err"
from collections import Counter
c=Counter(); done=0
with ThreadPoolExecutor(4) as ex:
    for res in ex.map(fetch, new):
        c[res]+=1; done+=1
        if done%200==0: print(f"  {done}/{len(new)} {dict(c)}", flush=True)
print("scrape:", dict(c))
PY
python3 analysis/index_dumps.py dump_index_top60.csv scraped/top60_0814 >> $LOG 2>&1

# ---- Stage 2: rebuild Dragapult manifest over EVERYTHING ----
python3 - >> $LOG 2>&1 <<'PY'
import csv, collections, glob
rows=[]
for f in glob.glob("dump_index_*.csv"):
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
with open("drag_v7_manifest.csv","w",newline="") as f:
    wtr=csv.DictWriter(f,fieldnames=["episode","path","player","side","won","player_winrate","opp_deck"])
    wtr.writeheader(); wtr.writerows(out)
nw=sum(1 for r in out if r["won"]==1); ss=sum(1 for r in out if r["player"]=="Sixth Sense")
print(f"drag_v7_manifest.csv: {len(out)} sides ({nw}W/{len(out)-nw}L); SS sides {ss}")
PY

# ---- Stage 3: train drag_v7 (v6f recipe, one variable: newest corpus) ----
python3 analysis/az_nn/extract_v2.py drag_v7_manifest.csv model/az/imit_drag_v7.npz \
  --deck=my-agent/drag_v5/deck.csv --feat=2 >> $LOG 2>&1
python3 analysis/az_nn/train_imit_v2.py model/az/imit_drag_v7.npz --out=drag_v7 --epochs=10 \
  --weight=quality --value-weight=2.0 --value-lambda=0.5 \
  --boost-players="Sixth Sense" --boost=3.0 --device=mps >> $LOG 2>&1
python3 analysis/az_nn/export_numpy.py drag_v7 120 >> $LOG 2>&1
python3 analysis/az_nn/build_agent_v2.py drag_v7 my-agent/drag_v7 --np --mcts=1 --deck=my-agent/grimm_v12_live >/dev/null 2>&1
cp my-agent/drag_v5/deck.csv my-agent/drag_v7/deck.csv
rm -f my-agent/drag_v7/opp_decks.json

# ---- Stage 4: gates vs drag_v6f ----
echo "== drag_v7 vs drag_v6f (run 1, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/drag_v7 my-agent/drag_v6f 120 >> $LOG 2>&1
echo "== drag_v7 vs drag_v6f (replication, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/drag_v7 my-agent/drag_v6f 120 >> $LOG 2>&1
rm -rf my-agent/drag_v7/__pycache__
(cd my-agent/drag_v7 && tar -czf ~/Desktop/submission_drag_v7.tar.gz --exclude='__pycache__' --exclude='.DS_Store' *)
echo V7_DONE >> $LOG
