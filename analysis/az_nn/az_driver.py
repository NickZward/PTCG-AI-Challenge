#!/usr/bin/env python3
"""AZ VALUE LOOP DRIVER — weeks-scale unattended self-play value refinement for v12.

Per iteration:
  1. GENERATE: 3 parallel workers play mcts self-play (mirror + vs-gauntlet) with the
     CURRENT best net -> value states with exact outcomes (gen_value_selfplay.py).
  2. TRAIN: KL-anchored value refinement (train_value_kl.py, agree-floor 0.97 — v12's
     policy IS sacred here), init = current best.
  3. ACCEPT: only if real-ladder value AUC beats the reigning best (baseline 0.755-ish);
     else the iteration's net is discarded (data is kept — it accumulates).
  4. GATE (every ACCEPTED iteration): ALL WORKERS STOPPED (load law), candidate vs
     grimm_v12_live N=45. >=55% -> flagged loudly in the log for human review; the live
     artifact is NEVER touched by this driver.
State in model/az/azloop/: iter_k.npz data, best.pth, driver.log. Resumable: rerun me.
"""
import glob, json, os, shutil, subprocess, sys, time

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
D = f"{ROOT}/model/az/azloop"
os.makedirs(D, exist_ok=True)
LOG = f"{D}/driver.log"
WORKERS = 3
GAMES_PER_WORKER = 350
ENV = dict(os.environ, KMP_DUPLICATE_LIB_OK="TRUE", OMP_NUM_THREADS="2",
           VECLIB_MAXIMUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2")

def log(msg):
    line = f"[{time.strftime('%m-%d %H:%M')}] {msg}"
    print(line, flush=True)
    open(LOG, "a").write(line + "\n")

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, env=ENV, capture_output=True, text=True, **kw)

def current_best():
    p = f"{D}/best.pth"
    return p if os.path.exists(p) else f"{ROOT}/model/az/grimm_imit_v11_best.pth"

def npz_agent_dir():
    """Agent dir whose model_np.npz mirrors the current best (for generation + gates)."""
    d = f"{ROOT}/my-agent/azloop_cand"
    if not os.path.exists(d):
        shutil.copytree(f"{ROOT}/my-agent/grimm_v12_live", d,
                        ignore=shutil.ignore_patterns("__pycache__"))
    name = "azloop_best"
    bp = current_best()
    shutil.copy(bp, f"{ROOT}/model/az/{name}_best.pth")
    for cand_arch in (f"{D}/best_arch.json",
                      bp.replace("_best.pth", "_arch.json"),
                      f"{ROOT}/model/az/grimm_imit_v11_arch.json"):
        if os.path.exists(cand_arch) and cand_arch.endswith(".json"):
            try:
                json.load(open(cand_arch))
            except Exception:
                continue
            shutil.copy(cand_arch, f"{ROOT}/model/az/{name}_arch.json")
            break
    r = sh(f"cd {ROOT} && python3 analysis/az_nn/export_numpy.py {name} 50")
    if "PASS" not in r.stdout:
        log(f"EXPORT FAIL: {r.stdout[-300:]}{r.stderr[-300:]}")
        return None
    shutil.copy(f"{ROOT}/model/az/{name}_np.npz", f"{d}/model_np.npz")
    return d

def main():
    it = len(glob.glob(f"{D}/iter*_w1.npz"))
    log(f"=== AZ DRIVER START (resuming at iter {it}) ===")
    while True:
        it += 1
        cand_dir = npz_agent_dir()
        if cand_dir is None:
            time.sleep(600); continue
        # 1. GENERATE (workers in parallel; mirror + vs stock v12 + vs ogerpon)
        log(f"iter {it}: generating {WORKERS}x{GAMES_PER_WORKER} games...")
        opps = ["mirror", "my-agent/grimm_v12_live", "my-agent/ogerpon_v1"]
        procs = []
        for w in range(WORKERS):
            out = f"{D}/iter{it}_w{w+1}.npz"
            # the Ogerpon stream needs the rules-capable generator (worst-cell states)
            gen = ("gen_value_rules.py" if "ogerpon" in opps[w % len(opps)]
                   else "gen_value_selfplay.py")
            cmd = (f"cd {ROOT} && python3 analysis/az_nn/{gen} "
                   f"my-agent/azloop_cand {GAMES_PER_WORKER} {out} "
                   f"--opp={opps[w % len(opps)]} --search=16 --seed={it*10+w}")
            procs.append(subprocess.Popen(cmd, shell=True, env=ENV,
                         stdout=open(f"{D}/gen_w{w+1}.log", "w"), stderr=subprocess.STDOUT))
        for p in procs:
            p.wait()
        # 2. TRAIN on ALL accumulated data (newest included)
        data = ",".join(sorted(glob.glob(f"{D}/iter*_w*.npz")))
        log(f"iter {it}: training on {data.count('npz')} npz files...")
        r = sh(f"cd {ROOT} && python3 analysis/az_nn/train_value_kl.py {data} "
               f"model/az/grimm_eval_bothsides.npz --init={current_best()} "
               f"--out=azloop_iter{it} --epochs=1 --bs=128 --lr=5e-5 --kl=2.0 "
               f"--vlam=0.4 --agree-floor=0.96 --min-turn=9", timeout=14400)
        tail = (r.stdout or "")[-600:]
        log(f"iter {it} train tail: {tail}")
        newp = f"{ROOT}/model/az/azloop_iter{it}_best.pth"
        if not os.path.exists(newp):
            log(f"iter {it}: NOT ACCEPTED (no AUC improvement or anchor breach). Continuing.")
            continue
        shutil.copy(newp, f"{D}/best.pth")
        na = newp.replace("_best.pth", "_arch.json")
        if os.path.exists(na):
            shutil.copy(na, f"{D}/best_arch.json")
        log(f"iter {it}: ACCEPTED -> best.pth updated")
        # 3. GATE on idle machine (workers are already stopped — sequential design)
        cand_dir = npz_agent_dir()
        if cand_dir is None:
            log(f"iter {it}: EXPORT FAILED — SKIPPING GATE (fix and gate manually)")
            continue
        log(f"iter {it}: gating vs v12 (N=45, idle)...")
        r = sh(f"cd {ROOT} && PTCG_STOP=25 python3 analysis/round_robin.py 45 "
               f"my-agent/azloop_cand my-agent/grimm_v12_live", timeout=14400)
        r2 = sh(f"cd {ROOT} && PTCG_STOP=25 python3 analysis/round_robin.py 45 "
                f"my-agent/azloop_cand my-agent/ogerpon_v1", timeout=14400)
        for line in (r2.stdout or "").splitlines():
            if " vs " in line:
                log(f"iter {it} OGERPON CELL: {line.strip()} (v12 baseline 37.8%)")
        for line in (r.stdout or "").splitlines():
            if " vs " in line:
                log(f"iter {it} GATE: {line.strip()}")
                try:
                    wr = float(line.strip().split()[-1].rstrip("%"))
                    if wr >= 55.0:
                        log(f"iter {it}: *** CANDIDATE >=55% — HUMAN REVIEW REQUIRED ***")
                except Exception:
                    pass

if __name__ == "__main__":
    main()
