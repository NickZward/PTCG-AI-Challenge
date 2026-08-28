#!/usr/bin/env python3
"""PROPER POLICY ITERATION (points 2+3): play the CURRENT learned agent (az_N) against a CLEAN
diverse stable, and record BOTH:
  - VALUE: (state_features -> T14-adjudicated outcome vs the field)   [trains V]
  - POLICY: (option_features -> was this the move az_N's SEARCH picked?)  [trains Pi to imitate
    the search-improved policy — the AlphaZero improvement operator, not rule-rollouts]
Retraining on this gives az_{N+1} whose policy narrows candidates the way the search would and
whose value reflects the real field. Loop it.

Usage: gen_policy_iter.py <agent_dir> <n_games> <out.npz> [workers=6] @stable.txt"""
import sys, os, importlib.util, random, json
import numpy as np
from multiprocessing import Pool
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
STOP = 14
_G = {"m": None, "deck": None, "opps": None, "F": None, "vocab": None, "cf": None, "adm": None}

def _load_agent_dir(sub):
    d = os.path.join(ROOT, sub)
    if d not in sys.path: sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location("azmod", os.path.join(d, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules["azmod"] = m; spec.loader.exec_module(m)
    m._az_load()
    import bc_features as F
    return m, [int(x) for x in open(os.path.join(d, "deck.csv")).read().split()], F

def _load_opp(sub):
    d = os.path.join(ROOT, sub)
    spec = importlib.util.spec_from_file_location("opp_" + os.path.basename(sub), os.path.join(d, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
    return m.agent, [int(x) for x in open(os.path.join(d, "deck.csv")).read().split()]

def _setup(agent_dir, opp_dirs):
    if _G["m"] is not None: return
    m, deck, F = _load_agent_dir(agent_dir)
    _G["m"], _G["deck"], _G["F"] = m, deck, F
    _G["vocab"], _G["cf"], _G["adm"] = m._AZ["vocab"], m._AZ["cf"], m._AZ["adm"]
    _G["opps"] = [_load_opp(d) for d in opp_dirs]

def _adj(cur):
    P = cur.get("players")
    p0, p1 = 6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or [])
    if p0 != p1: return 0 if p0 > p1 else 1
    d0, d1 = P[0].get("deckCount") or 0, P[1].get("deckCount") or 0
    if d0 != d1: return 0 if d0 > d1 else 1
    return -4

def play_game(seed):
    random.seed(seed * 40503 % (2**31))
    m, deck, F = _G["m"], _G["deck"], _G["F"]
    vocab, cf, adm = _G["vocab"], _G["cf"], _G["adm"]
    opp_ag, opp_deck = random.choice(_G["opps"])
    obs, _ = cggame.battle_start(list(deck), list(opp_deck))
    if obs is None: return None
    val_states = []; pol = []  # pol: (state_f used for group, [opt_f], pick_local)
    result = None; steps = 0
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            if r not in (None, -1): result = r; break
            if obs.get("select") is None: break
            turn = cur.get("turn", 0) or 0
            if turn > STOP: result = _adj(cur); break
            you = cur.get("yourIndex", 0)
            sel = obs.get("select"); opts = sel.get("option") or []
            w = {"current": cur, "select": sel, "logs": obs.get("logs", []), "step": steps,
                 "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
            if you == 0:
                if sel.get("type") == 0 and turn >= 1:
                    val_states.append(F.state_features(cur, 0, vocab, cf, step=turn))
                    if len(opts) > 1:
                        # az_N's actual move = its search pick (the policy-improvement target)
                        pick = m.agent(w)
                        pick_i = int(pick[0]) if pick else 0
                        ofs = [F.option_features(w, opts[i], i, len(opts), vocab, cf, adm) for i in range(len(opts))]
                        pol.append((ofs, pick_i))
                        action = pick if random.random() > 0.2 else [random.randrange(len(opts))]
                    else:
                        action = m.agent(w)
                else:
                    action = m.agent(w)
            else:
                action = opp_ag(w)
            obs = cggame.battle_select([int(a) for a in action]); steps += 1
    finally:
        cggame.battle_finish()
    if result is None or result == -4: return None
    outcome = 1.0 if result == 0 else 0.0
    return val_states, pol, outcome

def _worker(args):
    agent_dir, opp_dirs, seed = args
    _setup(agent_dir, opp_dirs)
    return play_game(seed)

def main():
    agent_dir = sys.argv[1]; N = int(sys.argv[2]); out = sys.argv[3]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("@") else 6
    sfile = [a for a in sys.argv if a.startswith("@")][0][1:]
    opp_dirs = [l.strip() for l in open(sfile) if l.strip() and not l.startswith("#")]
    print(f"policy-iter: {agent_dir} vs {len(opp_dirs)}-opp clean stable, {N} games", flush=True)
    Xs, ys, Xo, yo, grp = [], [], [], [], []
    gid = 0; done = 0; nwin = 0
    with Pool(workers) as p:
        for res in p.imap_unordered(_worker, [(agent_dir, opp_dirs, s) for s in range(N)], chunksize=2):
            done += 1
            if not res: continue
            val_states, pol, outcome = res
            for sf in val_states:
                Xs.append(sf); ys.append(outcome); nwin += outcome
            for ofs, pick in pol:
                for j, of in enumerate(ofs):
                    Xo.append(of); yo.append(1 if j == pick else 0); grp.append(gid)
                gid += 1
            if done % 20 == 0:
                print(f"  {done}/{N} games, {len(Xs)} value ({nwin/max(1,len(Xs)):.2f}), {len(Xo)} policy", flush=True)
    np.savez_compressed(out, Xs=np.array(Xs, dtype=np.float32), ys=np.array(ys, dtype=np.float32),
                        Xo=np.array(Xo, dtype=np.float32), yo=np.array(yo, dtype=np.int8), grp=np.array(grp, dtype=np.int32))
    print(f"saved {len(Xs)} value + {len(Xo)} policy ({gid} decisions, our winrate {nwin/max(1,len(Xs)):.2f}) -> {out}")

if __name__ == "__main__":
    main()
