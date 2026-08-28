cd /Users/nickzwart/Desktop/PTCG-AI-Challenge
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1
LOG=strategy_track/OGER_SS.log
echo "== OGER_SS SPRINT $(date) ==" > $LOG

# Stage 1: index the banked SS-Ogerpon games (harvester already scraped today's)
python3 analysis/index_dumps.py dump_index_ssoger.csv scraped/ss_oger_daily >> $LOG 2>&1

# Stage 2: recon his CURRENT Ogerpon 60 from the newest games; fallback to Aug-13 recon
python3 analysis/recon_deck.py ss_oger_now.csv "Sixth Sense" Ogerpon dump_index_ssoger.csv dump_index_ss0813.csv >> $LOG 2>&1 || cp ss_oger_deck.csv ss_oger_now.csv

# Stage 3: rebuild the Ogerpon manifest over everything
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
        if a!="Ogerpon" or pil[(a,p)][1]<6: continue
        k=(r["episode"],si)
        if k in keys: continue
        keys.add(k)
        wn,n=pil[(a,p)]
        out.append({"episode":r["episode"],"path":r["path"],"player":p,"side":si,
                    "won":1 if w==si else 0,"player_winrate":round(wn/n,4),"opp_deck":opp})
with open("oger_ss_manifest.csv","w",newline="") as f:
    wtr=csv.DictWriter(f,fieldnames=["episode","path","player","side","won","player_winrate","opp_deck"])
    wtr.writeheader(); wtr.writerows(out)
ss=sum(1 for r in out if r["player"]=="Sixth Sense")
print(f"oger_ss_manifest.csv: {len(out)} sides; Sixth Sense sides: {ss}")
PY

# Stage 4: extract + train (SS as SOLE boosted teacher — the pre-registered design; 8 epochs for the clock)
python3 analysis/az_nn/extract_v2.py oger_ss_manifest.csv model/az/imit_oger_ss.npz \
  --deck=ss_oger_now.csv --feat=2 >> $LOG 2>&1
python3 analysis/az_nn/train_imit_v2.py model/az/imit_oger_ss.npz --out=oger_ss --epochs=8 \
  --weight=quality --value-weight=2.0 --value-lambda=0.5 \
  --boost-players="Sixth Sense" --boost=3.0 --device=mps >> $LOG 2>&1
python3 analysis/az_nn/export_numpy.py oger_ss 120 >> $LOG 2>&1
python3 analysis/az_nn/build_agent_v2.py oger_ss my-agent/oger_ss --np --mcts=1 --deck=my-agent/grimm_v12_live >/dev/null 2>&1
cp ss_oger_now.csv my-agent/oger_ss/deck.csv
rm -f my-agent/oger_ss/opp_decks.json
rm -rf my-agent/oger_ss/__pycache__
(cd my-agent/oger_ss && tar -czf ~/Desktop/submission_oger_ss.tar.gz --exclude='__pycache__' --exclude='.DS_Store' *)
echo BUILD_DONE >> $LOG

# Stage 5: the one gate that fits — vs oger_v6s (pre-registered), then vs drag_v6f if clock allows
echo "== oger_ss vs oger_v6s (N=60) ==" >> $LOG
python3 /tmp/h2h.py my-agent/oger_ss my-agent/oger_v6s 60 >> $LOG 2>&1
echo GATE1_DONE >> $LOG
echo "== oger_ss vs drag_v6f (N=60) ==" >> $LOG
python3 /tmp/h2h.py my-agent/oger_ss my-agent/drag_v6f 60 >> $LOG 2>&1
echo SPRINT_DONE >> $LOG
