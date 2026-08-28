#!/usr/bin/env python3
"""Generate VALUE training data by playing OUR agent against a DIVERSE STABLE (not the mirror).
The agent's search is guided by the value net, so training it on outcomes vs the real field
(diverse decks + agents) teaches it to pick moves that beat the FIELD, fixing the self-mirror
overfit. Records (state_features at our decisions -> T14-adjudicated outcome vs that opponent).

Usage: gen_value_vs_stable.py <our_dir> <n_games> <out.npz> [workers=6] @stable.txt
  stable.txt lists opponent dirs (one per line)."""
import sys, os, importlib.util, random, json
import numpy as np
from multiprocessing import Pool
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v13"))
from cg import game as cggame
from cg.api import to_observation_class
import bc_features as F
VOCABJ = json.load(open(os.path.join(ROOT, "my-agent/grimmsnarl_v13/bc_vocab.json")))
VOCAB, CF = VOCABJ["vocab"], VOCABJ["card_feats"]
STOP = 14
_G = {"our": None, "our_deck": None, "opps": None}

def _load(sub):
    spec = importlib.util.spec_from_file_location("m_" + os.path.basename(sub), os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]

def _setup(our_dir, opp_dirs):
    if _G["our"] is not None: return
    _G["our"], _G["our_deck"] = _load(os.path.join(ROOT, our_dir))
    _G["opps"] = [_load(os.path.join(ROOT, d)) for d in opp_dirs]

def _adj(cur):
    P = cur.get("players")
    p0, p1 = 6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or [])
    if p0 != p1: return 0 if p0 > p1 else 1
    d0, d1 = P[0].get("deckCount") or 0, P[1].get("deckCount") or 0
    if d0 != d1: return 0 if d0 > d1 else 1
    return -4

def play_game(seed):
    random.seed(seed * 40503 % (2**31))
    our_ag, our_deck = _G["our"], _G["our_deck"]
    opp_ag, opp_deck = random.choice(_G["opps"])
    obs, _ = cggame.battle_start(list(our_deck), list(opp_deck))   # we are side 0
    if obs is None: return None
    states = []; result = None; steps = 0
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            if r not in (None, -1): result = r; break
            if obs.get("select") is None: break
            turn = cur.get("turn", 0) or 0
            if turn > STOP:
                result = _adj(cur); break
            you = cur.get("yourIndex", 0)
            w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                 "step": steps, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
            if you == 0:
                if (obs.get("select") or {}).get("type") == 0 and turn >= 1:
                    states.append(F.state_features(cur, 0, VOCAB, CF, step=turn))
                action = our_ag(w)
            else:
                action = opp_ag(w)
            obs = cggame.battle_select([int(a) for a in action]); steps += 1
    finally:
        cggame.battle_finish()
    if result is None or result == -4: return None
    outcome = 1.0 if result == 0 else 0.0
    return states, outcome

def _worker(args):
    our_dir, opp_dirs, seed = args
    _setup(our_dir, opp_dirs)
    return play_game(seed)

def main():
    our_dir = sys.argv[1]; N = int(sys.argv[2]); out = sys.argv[3]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("@") else 6
    sfile = [a for a in sys.argv if a.startswith("@")][0][1:]
    opp_dirs = [l.strip() for l in open(sfile) if l.strip() and not l.startswith("#")]
    print(f"our={our_dir} vs stable of {len(opp_dirs)} opponents, {N} games", flush=True)
    jobs = [(our_dir, opp_dirs, s) for s in range(N)]
    Xs, ys = [], []; done = 0; nwin = 0
    with Pool(workers) as p:
        for res in p.imap_unordered(_worker, jobs, chunksize=2):
            done += 1
            if not res: continue
            states, outcome = res
            for sf in states:
                Xs.append(sf); ys.append(outcome); nwin += outcome
            if done % 25 == 0:
                print(f"  {done}/{N} games, {len(Xs)} states, our-winrate {nwin/max(1,len(Xs)):.2f}", flush=True)
    np.savez_compressed(out, Xs=np.array(Xs, dtype=np.float32), ys=np.array(ys, dtype=np.float32))
    print(f"saved {len(Xs)} value-vs-field states (our winrate {nwin/max(1,len(Xs)):.2f}) -> {out}")

if __name__ == "__main__":
    main()
