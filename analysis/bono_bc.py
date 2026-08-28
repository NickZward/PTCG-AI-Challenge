#!/usr/bin/env python3
"""Behavioral cloning of BONO (#1, our exact Grimmsnarl deck) from the 187 Bono/
replays. One expert, one deck = a clean, learnable policy. Fixes bc_features'
wrong AreaType codes so option card-identity is correct. Trains an option-scorer;
top-1 (= bono-agreement) by context; saves model for the pilot to use."""
import sys, os, glob, json, csv
from collections import defaultdict
import numpy as np
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "model"))
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
import bc_features as F

# ---- FIX: correct AreaType codes (DECK=1,HAND=2,DISCARD=3,ACTIVE=4,BENCH=5,PRIZE=6,STADIUM=7,LOOKING=12) ----
def resolve_fixed(obs, opt):
    if opt.get("cardId") is not None:
        return opt["cardId"]
    area, index = opt.get("area"), opt.get("index")
    if area is None or index is None:
        return None
    cur = obs.get("current") or {}
    you = cur.get("yourIndex", 0)
    pi = opt.get("playerIndex"); pi = you if pi is None else pi
    players = cur.get("players") or [{}, {}]
    p = players[pi] if pi < len(players) else {}
    try:
        if area == 2: return (p.get("hand") or [])[index].get("id")
        if area == 4:
            c = (p.get("active") or [])[index]; return c.get("id") if c else None
        if area == 5:
            c = (p.get("bench") or [])[index]; return c.get("id") if c else None
        if area == 3: return (p.get("discard") or [])[index].get("id")
        if area == 7: return (cur.get("stadium") or [])[index].get("id")
        if area == 12: return (cur.get("looking") or [])[index].get("id")
        if area == 1: return ((obs.get("select") or {}).get("deck") or [])[index].get("id")
        if area == 6: return (p.get("prize") or [])[index].get("id")
    except (IndexError, AttributeError, TypeError):
        return None
    return None
F.resolve_card_id = resolve_fixed

# ---- card feats + attack dmg from SDK ----
from cg.api import all_attack, all_card_data
attack_dmg = {str(a.attackId): (a.damage or 0) for a in all_attack()}
card_feats = {}
for c in all_card_data():
    cat = 1 if getattr(c, "hp", None) else (3 if "Energy" in (c.name or "") else 2)
    card_feats[str(c.cardId)] = [getattr(c, "hp", 0) or 0, 1 if getattr(c, "ex", False) else 0,
                                 cat, getattr(c, "stage", 0) or 0]
vocab = json.load(open(os.path.join(ROOT, "model/bc_vocab.json")))["vocab"]

def bono_idx(d):
    for i, n in enumerate(d['info']['TeamNames']):
        if 'bono' in n.lower(): return i
    return 0

# ---- extract bono decisions ----
X, y, group, ctxs, game = [], [], [], [], []   # group = per-DECISION id; game = per-GAME id
files = sorted(glob.glob(f"{ROOT}/Bono/*.json"))
gid = 0
dec = 0
for f in files:
    try:
        d = json.load(open(f))
    except Exception:
        continue
    b = bono_idx(d)
    for step in d['steps']:
        e = step[b] if b < len(step) else None
        if not e: continue
        o = e.get('observation') or {}
        sel = o.get('select'); act = e.get('action')
        if not sel or not act: continue
        opts = sel.get('option') or []
        if len(opts) <= 1: continue
        chosen = set(int(x) for x in act if isinstance(x, int) and x < len(opts))
        if not chosen: continue
        obs = {'current': o.get('current'), 'select': sel, 'step': 0}
        for i, op in enumerate(opts):
            try:
                feats = F.option_features(obs, op, i, len(opts), vocab, card_feats, attack_dmg)
            except Exception:
                feats = [0.0] * F.N_FEATURES
            X.append(feats); y.append(1 if i in chosen else 0)
            group.append(dec); game.append(gid); ctxs.append(sel.get('context', -1))
        dec += 1
    gid += 1
X = np.array(X, dtype=np.float32); y = np.array(y, dtype=np.int8)
group = np.array(group, dtype=np.int32); game = np.array(game, dtype=np.int32); ctxs = np.array(ctxs, dtype=np.int16)
print(f"extracted {len(y)} option-samples from {gid} bono games "
      f"({len(np.unique(group))} games, {int(y.sum())} positive)")

# ---- train (split by game so no leakage) ----
from sklearn.ensemble import HistGradientBoostingClassifier
cut = np.quantile(game, 0.85)          # split by GAME (no leakage)
tr, va = game <= cut, game > cut
clf = HistGradientBoostingClassifier(max_iter=500, learning_rate=0.07, max_depth=None,
                                     min_samples_leaf=30, l2_regularization=1.0,
                                     early_stopping=True, validation_fraction=0.1, random_state=0)
clf.fit(X[tr], y[tr])
print(f"trained {clf.n_iter_} trees on {tr.sum()} samples")

def top1(mask):
    if mask.sum() == 0: return 0, 0
    score = clf.predict_proba(X[mask])[:, 1]; g = group[mask]; yy = y[mask]
    c = t = 0
    for gg in np.unique(g):
        m = g == gg
        if yy[m].sum() == 0: continue
        t += 1; c += int(yy[m][np.argmax(score[m])] == 1)
    return c, t

c, t = top1(va)
print(f"\nBONO-BC VAL top-1 (= agreement): {c}/{t} = {c/t:.1%}   (rule pilot = 30%)")
# by context
SCTX = {0:'MAIN',7:'TO_HAND',13:'DMG_COUNTER',14:'DMG_CTR_ANY',15:'DAMAGE',16:'RM_COUNTER',
        6:'TO_FIELD',39:'DMG_CTR_COUNT',40:'RM_CTR_COUNT',37:'EVOLVE',3:'SWITCH',22:'ATTACH_TO'}
print("by context (val):")
for cx in sorted(set(ctxs[va].tolist())):
    m = va & (ctxs == cx)
    cc, tt = top1(m)
    if tt >= 10: print(f"  {SCTX.get(cx,'ctx'+str(cx)):<14} {cc}/{tt} = {cc/tt:.0%}")

import joblib
joblib.dump(clf, f"{ROOT}/model/bono_model.joblib")
print("\nsaved model/bono_model.joblib")
