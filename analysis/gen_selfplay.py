#!/usr/bin/env python3
"""SELF-PLAY DATA GENERATION for the learned agent (AlphaZero-lite policy iteration).
Plays self-play games with the CURRENT policy (rules for iter 0, the neural agent after).
At each of OUR MAIN decisions, rolls out K candidate moves to the T14 buzzer (LADDER-adjudicated:
prize leader wins, deckout=loss) -> per-candidate value. Records:
  - VALUE data:  (state_features, game_outcome)         -> train V(state)=P(win at buzzer)
  - POLICY data: (option_features, is_search_best)      -> train Pi(option)=P(best move)
The search-improved policy (argmax of rollouts) is a BETTER target than the current policy —
that's the improvement operator that makes iteration work.

Usage: gen_selfplay.py <deck_dir> <n_games> <out.npz> [K=5] [workers=6] [net_dir=""]
  net_dir: if given, self-play + rollouts use the neural agent there (later iterations)."""
import sys, os, importlib.util, random, json
from collections import Counter
import numpy as np
from multiprocessing import Pool
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v13"))
from cg import game as cggame
from cg.api import search_begin, search_step, search_end, to_observation_class, SelectType, all_attack
import bc_features as F
VOCABJ = json.load(open(os.path.join(ROOT, "my-agent/grimmsnarl_v13/bc_vocab.json")))
VOCAB, CF = VOCABJ["vocab"], VOCABJ["card_feats"]
ADM = {str(a.attackId): (a.damage or 0) for a in all_attack()}
STOP = 14

_G = {"pilot": None, "deck": None, "net": None}

def _load_pilot(deck_dir):
    spec = importlib.util.spec_from_file_location("sp_pilot", os.path.join(deck_dir, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules["sp_pilot"] = m; spec.loader.exec_module(m)
    _G["pilot"] = m
    _G["deck"] = [int(x) for x in open(os.path.join(deck_dir, "deck.csv")).read().split()]

def rule_dispatch(o):
    P = _G["pilot"]; t = o.select.type
    if t == SelectType.MAIN: r = P.choose_main(o)
    elif t in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD): r = P.choose_cards(o)
    elif t == SelectType.YES_NO: r = P.choose_yes_no(o)
    elif t == SelectType.ATTACK: r = P.choose_attack(o)
    elif t == SelectType.COUNT: r = P.choose_count(o)
    elif t == SelectType.EVOLVE: r = P.choose_cards(o)
    elif t == SelectType.ENERGY: r = P.pick_by_priority(o, o.select, P.cfg('ENERGY_DISCARD', []), count=max(o.select.minCount, 1))
    else: r = P.safe_fallback(o.select)
    return P._validate(r, o.select)

def _unseen(deck, seen):
    pc = Counter(deck)
    for cid in seen:
        if cid is not None and pc.get(cid, 0) > 0: pc[cid] -= 1
    pool = list(pc.elements()); random.shuffle(pool); return pool

def determinize(oc):
    P = _G["pilot"]; deck = _G["deck"]
    me, op = P.me(oc), P.opp(oc)
    seen = [c.id for c in (me.hand or [])] + [c.id for c in (me.discard or [])]
    for pk in P.my_in_play(oc):
        seen.append(pk.id); seen += [getattr(e, "id", None) for e in (pk.energies or [])]
    mine = _unseen(deck, seen)
    need = me.deckCount + len(me.prize or []); mine += [5] * max(0, need - len(mine))
    yd = mine[:me.deckCount]; yp = mine[me.deckCount:me.deckCount + len(me.prize or [])]
    ob = [a for a in (op.active or []) if a] + [b for b in (op.bench or []) if b]
    oseen = [c.id for c in (op.discard or [])]
    for pk in ob:
        oseen.append(pk.id); oseen += [getattr(e, "id", None) for e in (pk.energies or [])]
    theirs = _unseen(deck, oseen)
    oneed = op.deckCount + len(op.prize or []) + (op.handCount or 0)
    theirs += [5] * max(0, oneed - len(theirs))
    od = theirs[:op.deckCount] or [5]
    opz = theirs[op.deckCount:op.deckCount + len(op.prize or [])]
    oh = theirs[op.deckCount + len(op.prize or []):op.deckCount + len(op.prize or []) + (op.handCount or 0)]
    return yd, yp, od, opz, oh

def _adj_result(cur):
    """LADDER adjudication at the buzzer: prize leader (us=0) wins; deck breaks ties."""
    P = cur.players
    p0, p1 = 6 - len(P[0].prize or []), 6 - len(P[1].prize or [])
    if p0 != p1: return 0 if p0 > p1 else 1
    d0, d1 = P[0].deckCount or 0, P[1].deckCount or 0
    if d0 != d1: return 0 if d0 > d1 else 1
    return -4

def rollout(oc, cand):
    """Apply candidate, play both sides with current policy to the T14 buzzer, adjudicate.
    Returns 1.0 (we win) / 0.0 (lose) / None (indeterminate)."""
    yd, yp, od, opz, oh = determinize(oc)
    try:
        s = search_step(search_begin(oc, yd, yp, od, opz, oh, [5]).searchId, [cand])
        o = s.observation; d = 0
        while d < 400:
            cur = o.current
            if cur.result != -1:
                r = cur.result; search_end(); return 1.0 if r == 0 else 0.0
            if (cur.turn or 0) > STOP:
                r = _adj_result(cur); search_end(); return 1.0 if r == 0 else (0.0 if r == 1 else None)
            if o.select is None: search_end(); return None
            s = search_step(s.searchId, rule_dispatch(o)); o = s.observation; d += 1
        search_end(); return None
    except Exception:
        try: search_end()
        except Exception: pass
        return None

def play_game(seed):
    random.seed(seed * 2654435761 % (2**31))
    deck = _G["deck"]; P = _G["pilot"]
    obs, _ = cggame.battle_start(list(deck), list(deck))
    if obs is None: return None
    dec = []          # (state_f, [opt_f], best_local, side)
    steps = 0; result = None
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            if r not in (None, -1): result = r; break
            if obs.get("select") is None: break
            turn = cur.get("turn", 0) or 0
            you = cur.get("yourIndex", 0)
            sel = obs.get("select"); opts = sel.get("option") or []
            wrapped = {"current": cur, "select": sel, "logs": obs.get("logs", []), "step": steps,
                       "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
            if turn > STOP:
                oc = to_observation_class(wrapped); result = _adj_result(oc.current); break
            action = None
            # BOTH sides play the rollout-improved policy (symmetric self-play); record both perspectives.
            if (sel.get("type") == 0 and len(opts) > 1 and turn >= 1
                    and wrapped["search_begin_input"] is not None):
                oc = to_observation_class(wrapped)
                rc = P._validate(P.choose_main(oc), oc.select); rule_i = rc[0] if rc else 0
                cand = [rule_i] + [i for i in range(len(opts)) if i != rule_i]
                rest = cand[1:]; random.shuffle(rest); cand = [rule_i] + rest[:K - 1]
                vals = {}
                for c in cand:
                    v = rollout(oc, c)
                    if v is not None: vals[c] = v
                if len(vals) >= 2:
                    keys = list(vals.keys())
                    sf = F.state_features(cur, you, VOCAB, CF, step=turn)
                    ofs = [F.option_features(wrapped, opts[c], c, len(opts), VOCAB, CF, ADM) for c in keys]
                    best_local = max(range(len(keys)), key=lambda k: vals[keys[k]])
                    dec.append((sf, ofs, best_local, you))
                    action = [keys[best_local]] if random.random() > 0.25 else [random.choice(keys)]
            if action is None:
                action = P.agent(wrapped)
            obs = cggame.battle_select([int(a) for a in action]); steps += 1
    finally:
        cggame.battle_finish()
    if result is None or result == -4:
        return None
    return dec, result

def _worker(args):
    deck_dir, seed = args
    if _G["pilot"] is None: _load_pilot(deck_dir)
    return play_game(seed)

K = 5
def main():
    global K
    deck_dir = sys.argv[1]; N = int(sys.argv[2]); out = sys.argv[3]
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    workers = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    jobs = [(deck_dir, s) for s in range(N)]
    Xs, ys = [], []          # value: state -> outcome
    Xo, yo, grp = [], [], []  # policy: option -> is_best (grouped by decision)
    gid = 0; done = 0
    nwin = 0
    with Pool(workers) as p:
        for res in p.imap_unordered(_worker, jobs, chunksize=2):
            done += 1
            if not res: continue
            dec, result = res
            for sf, ofs, best, side in dec:
                outcome = 1.0 if result == side else 0.0
                Xs.append(sf); ys.append(outcome); nwin += outcome
                for j, of in enumerate(ofs):
                    Xo.append(of); yo.append(1 if j == best else 0); grp.append(gid)
                gid += 1
            if done % 25 == 0:
                print(f"  {done}/{N} games, {len(Xs)} value-samples ({nwin/max(1,len(Xs)):.2f} win), {len(Xo)} policy", flush=True)
    np.savez_compressed(out, Xs=np.array(Xs, dtype=np.float32), ys=np.array(ys, dtype=np.float32),
                        Xo=np.array(Xo, dtype=np.float32), yo=np.array(yo, dtype=np.int8),
                        grp=np.array(grp, dtype=np.int32))
    print(f"saved {len(Xs)} value + {len(Xo)} policy samples ({gid} decisions) -> {out}")

if __name__ == "__main__":
    main()
