cd /Users/nickzwart/Desktop/PTCG-AI-Challenge
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1
LOG=strategy_track/OGER_REFRESH.log
echo "== OGERPON REFRESH $(date) ==" > $LOG

# ---- Stage 1: harvest the three elite Ogerpon teachers ----
python3 - >> $LOG 2>&1 <<'PY'
import json, csv, glob, os, urllib.request
def le(body):
    req=urllib.request.Request("https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))
have=set()
for f in glob.glob("dump_index_*.csv"):
    try:
        for r in csv.DictReader(open(f)): have.add(str(r["episode"]))
    except Exception: pass
for d in glob.glob("scraped/*/episode-*-replay.json"):
    have.add(os.path.basename(d).split("-")[1])
def subs_for(known_ep, team_name):
    d=le({"ids":[known_ep]})
    out=set()
    for t in d.get("teams",[]):
        if t.get("teamName")==team_name:
            if t.get("publicLeaderboardSubmissionId"): out.add(t["publicLeaderboardSubmissionId"])
            tid=t["id"]
            for e in d.get("episodes",[]):
                for a in e.get("agents",[]):
                    if a.get("teamId")==tid and a.get("submissionId"): out.add(a["submissionId"])
    return out
TEACHERS=[("Sixth Sense",92719924,"ss_0813"),("Dipam Chakraborty",92517093,"oger_dipam"),
          ("palsystem",91986057,"oger_pal")]
for name, ep, folder in TEACHERS:
    try: subs=subs_for(ep,name)
    except Exception as e: print(f"{name}: resolve failed {e}"); continue
    new=set()
    for s in subs:
        try: d=le({"submissionId":s})
        except Exception as e: print(f"{name} sub {s}: list failed {e}"); continue
        eps=[x["id"] for x in d.get("episodes",[]) if x.get("state")=="COMPLETED"]
        new |= {i for i in eps if str(i) not in have}
        print(f"{name} sub {s}: {len(eps)} episodes")
    json.dump(sorted(new), open(f"/tmp/harvest_{folder}.json","w"))
    print(f"{name}: {len(new)} NEW episodes -> /tmp/harvest_{folder}.json")
PY
for f in ss_0813 oger_dipam oger_pal; do
  [ -s /tmp/harvest_$f.json ] && python3 analysis/scrape_episodes.py scraped/$f /tmp/harvest_$f.json >> $LOG 2>&1
done

# ---- Stage 2: index the harvest ----
python3 analysis/index_dumps.py dump_index_harvest.csv scraped/ss_0813 scraped/oger_dipam scraped/oger_pal >> $LOG 2>&1

# ---- Stage 3: rebuild the Ogerpon both-sides manifest over EVERYTHING ----
python3 - >> $LOG 2>&1 <<'PY'
import csv, collections
IDX=("dump_index_0810.csv dump_index_pal2.csv dump_index_kdc.csv dump_index_kdf.csv "
     "dump_index_slots2.csv dump_index_1108.csv dump_index_dragv4.csv dump_index_topfresh.csv "
     "dump_index_v5.csv dump_index_harvest.csv").split()
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
        if a!="Ogerpon" or pil[(a,p)][1]<6: continue
        k=(r["episode"],si)
        if k in keys: continue
        keys.add(k)
        wn,n=pil[(a,p)]
        out.append({"episode":r["episode"],"path":r["path"],"player":p,"side":si,
                    "won":1 if w==si else 0,"player_winrate":round(wn/n,4),"opp_deck":opp})
with open("oger_final2_manifest.csv","w",newline="") as f:
    wtr=csv.DictWriter(f,fieldnames=["episode","path","player","side","won","player_winrate","opp_deck"])
    wtr.writeheader(); wtr.writerows(out)
nw=sum(1 for r in out if r["won"]==1)
byp=collections.Counter(r["player"] for r in out)
print(f"oger_final2_manifest.csv: {len(out)} sides ({nw}W/{len(out)-nw}L)")
print("top pilots:", byp.most_common(8))
PY

# ---- Stage 4: Sixth Sense's new Ogerpon 60 (fallback to the 4-game recon) ----
python3 analysis/recon_deck.py ss_oger_deck.csv "Sixth Sense" Ogerpon dump_index_harvest.csv >> $LOG 2>&1 || cp /tmp/ss_oger.csv ss_oger_deck.csv

# ---- Stage 5: extract + train candidate A (SS deck, 3 teachers boosted) ----
python3 analysis/az_nn/extract_v2.py oger_final2_manifest.csv model/az/imit_oger_v6s.npz \
  --deck=ss_oger_deck.csv --feat=2 >> $LOG 2>&1
python3 analysis/az_nn/train_imit_v2.py model/az/imit_oger_v6s.npz --out=oger_v6s --epochs=10 \
  --weight=quality --value-weight=2.0 --value-lambda=0.5 \
  --boost-players="Sixth Sense,Dipam Chakraborty,palsystem" --boost=3.0 --device=mps >> $LOG 2>&1
python3 analysis/az_nn/export_numpy.py oger_v6s 120 >> $LOG 2>&1
python3 analysis/az_nn/build_agent_v2.py oger_v6s my-agent/oger_v6s --np --mcts=1 --deck=my-agent/grimm_v12_live >/dev/null 2>&1
cp ss_oger_deck.csv my-agent/oger_v6s/deck.csv
rm -f my-agent/oger_v6s/opp_decks.json

# ---- Stage 6: gates ----
echo "== oger_v6s vs oger_v4i (run 1, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/oger_v6s my-agent/oger_v4i 120 >> $LOG 2>&1
echo "== oger_v6s vs oger_v4i (replication, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/oger_v6s my-agent/oger_v4i 120 >> $LOG 2>&1
echo "== oger_v6s vs drag_v5 (band probe, N=120) ==" >> $LOG
python3 /tmp/h2h.py my-agent/oger_v6s my-agent/drag_v5 120 >> $LOG 2>&1
rm -rf my-agent/oger_v6s/__pycache__
(cd my-agent/oger_v6s && tar -czf ~/Desktop/submission_oger_v6s.tar.gz --exclude='__pycache__' --exclude='.DS_Store' *)
echo OGER_REFRESH_DONE >> $LOG
