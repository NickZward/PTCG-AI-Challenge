#!/usr/bin/env python3
"""Train the POLICY and VALUE networks from self-play data (analysis/gen_selfplay.py).
  VALUE net:  state_features (325) -> P(win at the T14 buzzer)
  POLICY net: option_features (131) -> P(this option is the search-best move)
Both are HistGradientBoosting (fast CPU inference for the Kaggle runtime + the search loop).
Usage: train_az.py <data.npz> <out_prefix>   (writes <prefix>_value.joblib / _policy.joblib)"""
import sys, os
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
import joblib

data = sys.argv[1]; prefix = sys.argv[2]
d = np.load(data)
Xs, ys, Xo, yo, grp = d["Xs"], d["ys"].astype(int), d["Xo"], d["yo"].astype(int), d["grp"]
print(f"value {Xs.shape} (mean {ys.mean():.3f}) | policy {Xo.shape} (pos {yo.mean():.3f}, {grp.max()+1} decisions)")

rng = np.random.RandomState(0)

# ---- VALUE net ----
idx = rng.permutation(len(Xs)); cut = int(0.85 * len(Xs))
vc = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_depth=6,
                                    l2_regularization=1.0, min_samples_leaf=40)
vc.fit(Xs[idx[:cut]], ys[idx[:cut]])
pv = vc.predict_proba(Xs[idx[cut:]])[:, 1]
try: print(f"VALUE  holdout AUC {roc_auc_score(ys[idx[cut:]], pv):.3f}")
except Exception: pass
HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_depth=6,
                               l2_regularization=1.0, min_samples_leaf=40).fit(Xs, ys)
vfull = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_depth=6,
                                       l2_regularization=1.0, min_samples_leaf=40).fit(Xs, ys)
joblib.dump(vfull, f"{prefix}_value.joblib")

# ---- POLICY net (split by DECISION group so no leakage) ----
gcut = np.quantile(grp, 0.85)
tr, te = grp <= gcut, grp > gcut
pc = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.07, max_depth=None,
                                    min_samples_leaf=40, l2_regularization=1.0)
pc.fit(Xo[tr], yo[tr])
# top-1 accuracy: per decision, does the model rank the true best option first?
def top1(mask):
    s = pc.predict_proba(Xo[mask])[:, 1]; g = grp[mask]; yy = yo[mask]; c = t = 0
    for gg in np.unique(g):
        m = g == gg
        if yy[m].sum() == 0: continue
        t += 1; c += int(yy[m][np.argmax(s[m])] == 1)
    return c, t
c, t = top1(te)
print(f"POLICY holdout top-1 (picks search-best): {c}/{t} = {c/max(1,t):.1%}")
pfull = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.07, max_depth=None,
                                       min_samples_leaf=40, l2_regularization=1.0).fit(Xo, yo)
joblib.dump(pfull, f"{prefix}_policy.joblib")
print(f"saved {prefix}_value.joblib + {prefix}_policy.joblib")
