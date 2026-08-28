#!/usr/bin/env python3
"""Train the VF on MC value targets (analysis/gen_mc_data.py output): determinized
end-of-turn states labeled with true Monte-Carlo win/loss. This is the on-distribution +
full-coverage (good AND bad candidate moves) data a replay VF lacked. state_features (325),
drops into grimmsnarl_v13. Usage: train_vf_mc.py [data.npz] [out.joblib]"""
import sys, os
import numpy as np
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "model/mc_vf_data.npz")
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "model/grimm_vf_mc.joblib")
d = np.load(data); X, y = d["X"], d["y"].astype(np.int32)
print(f"MC samples {len(X)}, mean value {y.mean():.3f}, features {X.shape[1]}")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss
# random split (samples are correlated within a game, so this AUC is optimistic — the real
# test is the mirror; this just confirms the model learns something)
rng = np.random.RandomState(0)
idx = rng.permutation(len(X)); cut = int(0.85 * len(X))
tr, te = idx[:cut], idx[cut:]
clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_depth=6,
                                     l2_regularization=1.0, min_samples_leaf=50)
clf.fit(X[tr], y[tr])
pte = clf.predict_proba(X[te])[:, 1]
print(f"holdout AUC {roc_auc_score(y[te], pte):.3f}  logloss {log_loss(y[te], pte):.3f}")
print("calibration:")
for b in range(5):
    m = (pte >= b*0.2) & (pte < (b+1)*0.2)
    if m.sum() > 20: print(f"   [{b*0.2:.1f},{(b+1)*0.2:.1f}) n={m.sum():>5} actual={y[te][m].mean():.2f}")
# retrain on all -> ship
clf_full = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_depth=6,
                                         l2_regularization=1.0, min_samples_leaf=50)
clf_full.fit(X, y)
import joblib
joblib.dump(clf_full, out)
print(f"saved -> {out}")
