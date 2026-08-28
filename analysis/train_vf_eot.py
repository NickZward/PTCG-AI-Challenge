#!/usr/bin/env python3
"""On-distribution VF: train on END-OF-TURN states (the LAST decision of each of the
player's turns) instead of all/start-of-turn states. The 1-ply search scores end-of-turn
states (after the rule policy finishes the turn), so the VF must be calibrated on THAT
distribution — training on start-of-turn states made it systematically avoid good
aggressive lines (search deviations were monotonically worse). state_features (325-dim),
same as grimm_vf.joblib, so it drops straight into grimmsnarl_v13."""
import sys, os, json, glob
from collections import Counter
import numpy as np
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v13"))
import bc_features as F
VOCABJ = json.load(open(os.path.join(ROOT, "my-agent/grimmsnarl_v13/bc_vocab.json")))
VOCAB, CF = VOCABJ["vocab"], VOCABJ["card_feats"]

def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1

def collect(files, who, grimm_only):
    X, y, phase, gid = [], [], [], []
    g = 0
    for p in files:
        try: d = json.load(open(p))
        except Exception: continue
        me = pidx(d, who)
        if me < 0: continue
        rw = d.get('rewards')
        if rw not in ([1, -1], [-1, 1]): continue
        if grimm_only:
            try: decks = d['steps'][0][0]['visualize'][0]['action']
            except Exception: continue
            if Counter(decks[me]).get(648, 0) == 0: continue
        won = 1 if rw[me] == 1 else 0
        last_by_turn = {}   # turn -> the LAST (current) state that turn = end-of-turn proxy
        for t, step in enumerate(d['steps']):
            e = step[me] if me < len(step) else None
            if not e: continue
            o = e.get('observation') or {}
            cur = o.get('current'); sel = o.get('select')
            if not cur or not sel: continue
            turn = cur.get('turn', 0) or 0
            last_by_turn[turn] = cur     # overwrite -> keeps the latest state of the turn
        for turn, cur in last_by_turn.items():
            try: feat = F.state_features(cur, me, VOCAB, CF, step=turn)
            except Exception: continue
            X.append(feat); y.append(won)
            mp = len(cur['players'][me].get('prize') or [])
            op = len(cur['players'][1 - me].get('prize') or [])
            phase.append(min(mp, op)); gid.append((who, g))
        g += 1
    return X, y, phase, gid

def main():
    Xb, yb, pb, gb = collect(sorted(glob.glob(f"{ROOT}/Bono/*.json")), "bono", False)
    Xo, yo, po, go = collect(sorted(glob.glob(f"{ROOT}/Logs/auto/*replay.json")), "Kilupy", True)
    X = np.array(Xb + Xo, dtype=np.float32); y = np.array(yb + yo, dtype=np.int32)
    phase = np.array(pb + po); gids = gb + go
    uniq = sorted(set(gids)); test_games = set(uniq[::5])
    tr = np.array([g not in test_games for g in gids]); te = ~tr
    print(f"END-OF-TURN states {len(X)} (bono {len(Xb)}, ours {len(Xo)}), base wr {y.mean():.2f}, train {tr.sum()}/test {te.sum()}")
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_depth=6,
                                         l2_regularization=1.0, min_samples_leaf=40)
    clf.fit(X[tr], y[tr]); pte = clf.predict_proba(X[te])[:, 1]
    print(f"TEST AUC (game-split): {roc_auc_score(y[te], pte):.3f}")
    for lo, hi, lbl in [(0, 1, 'endgame<=1'), (2, 3, 'mid2-3'), (4, 6, 'early4-6')]:
        m = (phase[te] >= lo) & (phase[te] <= hi)
        if m.sum() > 30 and len(set(y[te][m])) > 1:
            print(f"   {lbl:<12} AUC {roc_auc_score(y[te][m], pte[m]):.3f} (n={m.sum()})")
    clf_full = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_depth=6,
                                             l2_regularization=1.0, min_samples_leaf=40)
    clf_full.fit(X, y)
    import joblib
    out = os.path.join(ROOT, "model/grimm_vf_eot.joblib"); joblib.dump(clf_full, out)
    print(f"saved -> {out}")

if __name__ == "__main__":
    main()
