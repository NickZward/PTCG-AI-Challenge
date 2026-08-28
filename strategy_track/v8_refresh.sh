cd /Users/nickzwart/Desktop/PTCG-AI-Challenge
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1
LOG=strategy_track/V8.log
echo "== V8 REFRESH $(date) ==" > $LOG
cp /tmp/flg_drag.csv flg_drag_deck.csv

# ---- Stage 1: gentle harvest of palsystem + kdcyberdude missing games ----
python3 - >> $LOG 2>&1 <<'PY'
import json, csv, glob, os, time, urllib.request
def le(body, tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request("https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
                data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            time.sleep(20*(i+1))
    return {}
have=set()
for f in glob.glob("dump_index_*.csv"):
    try:
        for r in csv.DictReader(open(f)): have.add(str(r["episode"]))
    except Exception: pass
for d in glob.glob("scraped/*/episode-*-replay.json"): have.add(os.path.basename(d).split("-")[1])
missing=set()
for pilot in ("palsystem","@kdcyberdude"):
    ep=None
    for f in ("dump_index_top60.csv","dump_index_harvest.csv"):
        try:
            for r in csv.DictReader(open(f)):
                if pilot in (r["p0"],r["p1"]): ep=int(r["episode"])
        except Exception: pass
    if not ep: print(f"{pilot}: no known episode"); continue
    d=le({"ids":[ep]})
    tid=None; subs=set()
    for t in d.get("teams",[]):
        if t.get("teamName")==pilot:
            tid=t["id"]
            if t.get("publicLeaderboardSubmissionId"): subs.add(t["publicLeaderboardSubmissionId"])
    for e in d.get("episodes",[]):
        for a in e.get("agents",[]):
            if a.get("teamId")==tid and a.get("submissionId"): subs.add(a["submissionId"])
    n=0
    for s in subs:
        d2=le({"submissionId":s})
        ids=[x["id"] for x in d2.get("episodes",[]) if x.get("state")=="COMPLETED"]
        n+=len(ids); missing|={i for i in ids if str(i) not in have}
        time.sleep(1.0)
    print(f"{pilot}: subs {sorted(subs)}, {n} episodes listed")
print(f"missing to scrape: {len(missing)}")
json.dump(sorted(missing), open("/tmp/v8_missing.json","w"))
PY
python3 analysis/scrape_episodes.py scraped/v8_extra /tmp/v8_missing.json >> $LOG 2>&1
python3 analysis/index_dumps.py dump_index_v8extra.csv scraped/v8_extra >> $LOG 2>&1

# ---- Stage 2: rebuild Dragapult manifest over EVERYTHING (now incl. flg_full + v8_extra) ----
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
with open("drag_v8_manifest.csv","w",newline="") as f:
    wtr=csv.DictWriter(f,fieldnames=["episode","path","player","side","won","player_winrate","opp_deck"])
    wtr.writeheader(); wtr.writerows(out)
byp=collections.Counter(r["player"] for r in out)
print(f"drag_v8_manifest.csv: {len(out)} sides; teachers:",
      {p:byp[p] for p in ("Sixth Sense","flg","palsystem","@kdcyberdude") if p in byp})
PY

# ---- Stage 3: train drag_v8 (flg's 60; 4 elite teachers boosted) ----
python3 analysis/az_nn/extract_v2.py drag_v8_manifest.csv model/az/imit_drag_v8.npz \
  --deck=flg_drag_deck.csv --feat=2 >> $LOG 2>&1
python3 analysis/az_nn/train_imit_v2.py model/az/imit_drag_v8.npz --out=drag_v8 --epochs=10 \
  --weight=quality --value-weight=2.0 --value-lambda=0.5 \
  --boost-players="Sixth Sense,flg,palsystem,@kdcyberdude" --boost=3.0 --device=mps >> $LOG 2>&1
python3 analysis/az_nn/export_numpy.py drag_v8 120 >> $LOG 2>&1
python3 analysis/az_nn/build_agent_v2.py drag_v8 my-agent/drag_v8 --np --mcts=1 --deck=my-agent/grimm_v12_live >/dev/null 2>&1
cp flg_drag_deck.csv my-agent/drag_v8/deck.csv
rm -f my-agent/drag_v8/opp_decks.json

# ---- Stage 4: gates vs drag_v6f ----
echo "== drag_v8 vs drag_v6f (run 1, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/drag_v8 my-agent/drag_v6f 120 >> $LOG 2>&1
echo "== drag_v8 vs drag_v6f (replication, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/drag_v8 my-agent/drag_v6f 120 >> $LOG 2>&1
rm -rf my-agent/drag_v8/__pycache__
(cd my-agent/drag_v8 && tar -czf ~/Desktop/submission_drag_v8.tar.gz --exclude='__pycache__' --exclude='.DS_Store' *)
echo V8_DONE >> $LOG
