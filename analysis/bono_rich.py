#!/usr/bin/env python3
"""Richer bono clone: the diagnosis says UNDERFIT, so give the model the info bono's
policy actually uses — full hand multiset, full board (both benches), the option's
target Pokemon, full option addressing, turn/flags — and train PER-CONTEXT models
(MAIN vs fetch vs routing are different decisions). Target: top-1 -> 80%+."""
import sys, os, glob, json
from collections import Counter, defaultdict
import numpy as np
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, f"{ROOT}/my-agent/dipplin_v1")
from cg.api import all_card_data, all_attack
EX = {c.cardId for c in all_card_data() if getattr(c, "ex", False)}
HPOF = {c.cardId: (getattr(c, "hp", 0) or 0) for c in all_card_data()}
ATK = {a.attackId: (a.damage or 0) for a in all_attack()}
VOCAB = json.load(open(f"{ROOT}/model/bc_vocab.json"))["vocab"]   # cardid(str)->slot(0..95)
NV = 96
def slot(cid):
    s = VOCAB.get(str(cid), VOCAB.get(cid))
    return s if s is not None else NV      # NV = "other"

def resolve_cid(o, opt):
    if opt.get("cardId") is not None: return opt["cardId"]
    a, i = opt.get("area"), opt.get("index")
    if a is None or i is None: return None
    cur = o.get("current") or {}; pi = opt.get("playerIndex")
    pi = cur.get("yourIndex", 0) if pi is None else pi
    pls = cur.get("players") or [{}, {}]; p = pls[pi] if pi < len(pls) else {}
    try:
        if a == 2: return (p.get("hand") or [])[i].get("id")
        if a == 4: c = (p.get("active") or [])[i]; return c.get("id") if c else None
        if a == 5: c = (p.get("bench") or [])[i]; return c.get("id") if c else None
        if a == 3: return (p.get("discard") or [])[i].get("id")
        if a == 1: return ((o.get("select") or {}).get("deck") or [])[i].get("id")
        if a == 6: return (p.get("prize") or [])[i]
    except Exception:
        return None
    return None

def target_pkm(o, opt):
    """The board Pokemon an option acts on (inPlayArea/inPlayIndex)."""
    ipa, ipi = opt.get("inPlayArea"), opt.get("inPlayIndex")
    if ipa is None or ipi is None: return None
    cur = o.get("current") or {}; pi = opt.get("playerIndex")
    pi = cur.get("yourIndex", 0) if pi is None else pi
    pls = cur.get("players") or [{}, {}]; p = pls[pi] if pi < len(pls) else {}
    try:
        if ipa == 4: c = (p.get("active") or [])[ipi]; return c if c else None
        if ipa == 5: c = (p.get("bench") or [])[ipi]; return c if c else None
    except Exception:
        return None
    return None

def feats(o, opt, i, n):
    cur = o["current"]; you = cur.get("yourIndex", 0)
    me = cur["players"][you]; op = cur["players"][1 - you]
    def act(p):
        a = p.get("active") or []; return a[0] if a and a[0] else None
    ma, oa = act(me), act(op)
    f = [len(me.get("prize") or []), len(op.get("prize") or []),
         len([b for b in (me.get("bench") or []) if b]), len([b for b in (op.get("bench") or []) if b]),
         len(me.get("hand") or []), me.get("deckCount", 0) or 0, op.get("deckCount", 0) or 0,
         cur.get("turn", 0) or 0, int(bool(cur.get("energyAttached"))), int(bool(cur.get("retreated"))),
         int(bool(cur.get("supporterPlayed"))), int(bool(cur.get("stadiumPlayed")))]
    for c in (ma, oa):
        f += [(c or {}).get("hp", 0) or 0, (c or {}).get("maxHp", 0) or 0, len((c or {}).get("energies") or [])]
    bm = [b for b in (me.get("bench") or []) if b]
    for k in range(5):
        c = bm[k] if k < len(bm) else None
        f += [(c or {}).get("hp", 0) or 0, len((c or {}).get("energies") or [])]
    bo = [b for b in (op.get("bench") or []) if b]
    for k in range(5):
        c = bo[k] if k < len(bo) else None
        f += [(c or {}).get("hp", 0) or 0]
    sel = o["select"]
    f += [sel.get("minCount", 0) or 0, sel.get("maxCount", 1) or 1, n, i]
    # option addressing
    f += [opt.get("type", -1), _g(opt, "area"), _g(opt, "index"), _g(opt, "inPlayArea"),
          _g(opt, "inPlayIndex"), _g(opt, "playerIndex"), _g(opt, "toolIndex"),
          ATK.get(opt.get("attackId"), 0) if opt.get("attackId") is not None else 0]
    # option's card + its features + target pokemon
    cid = resolve_cid(o, opt)
    f += [HPOF.get(cid, 0), 1 if cid in EX else 0]
    tg = target_pkm(o, opt)
    f += [(tg or {}).get("hp", 0) or 0, len((tg or {}).get("energies") or []),
          1 if (tg or {}).get("id") in EX else 0, (tg or {}).get("id", 0) or 0]
    # one-hots: option card, my active, opp active
    oh = [0.0] * (NV + 1); oh[slot(cid)] = 1.0; f += oh
    oh = [0.0] * (NV + 1); oh[slot((ma or {}).get("id"))] = 1.0; f += oh
    oh = [0.0] * (NV + 1); oh[slot((oa or {}).get("id"))] = 1.0; f += oh
    # hand multiset
    hc = Counter(slot(c.get("id")) for c in (me.get("hand") or []))
    hv = [0.0] * (NV + 1)
    for s, cnt in hc.items(): hv[s] = cnt
    f += hv
    return f
def _g(opt, k):
    v = opt.get(k); return -1 if v is None else v

def bidx(d):
    for i, n in enumerate(d['info']['TeamNames']):
        if 'bono' in n.lower(): return i
    return 0

if __name__ == "__main__":
    rows = defaultdict(lambda: {"X": [], "y": [], "grp": [], "gm": []})
    dec = 0; g = 0
    for f_ in sorted(glob.glob(f"{ROOT}/Bono/*.json")):
        try: d = json.load(open(f_))
        except Exception: continue
        b = bidx(d)
        for step in d['steps']:
            e = step[b] if b < len(step) else None
            if not e: continue
            o = e.get('observation') or {}; sel = o.get('select'); act = e.get('action')
            if not sel or not act: continue
            opts = sel.get('option') or []
            if len(opts) <= 1: continue
            ch = set(int(x) for x in act if isinstance(x, int) and x < len(opts))
            if not ch: continue
            ctx = sel.get('type', -1)      # bucket by select TYPE (MAIN vs CARD vs COUNT...)
            od = {'current': o.get('current'), 'select': sel}
            R = rows[ctx]
            for i, op in enumerate(opts):
                try: ft = feats(od, op, i, len(opts))
                except Exception: ft = None
                if ft is None: continue
                R["X"].append(ft); R["y"].append(1 if i in ch else 0); R["grp"].append(dec); R["gm"].append(g)
            dec += 1
        g += 1
    from sklearn.ensemble import HistGradientBoostingClassifier
    def top1(clf, X, y, grp, mask):
        s = clf.predict_proba(X[mask])[:, 1]; gg = grp[mask]; yy = y[mask]; c = t = 0
        for u in np.unique(gg):
            m = gg == u
            if yy[m].sum() == 0: continue
            t += 1; c += int(yy[m][np.argmax(s[m])] == 1)
        return c, t
    print(f"{'select-type':<12}{'train':>8}{'val':>8}{'n_dec':>8}")
    tot_c = tot_t = 0; models = {}
    STN = {0:'MAIN',1:'CARD',2:'ATTACHED',3:'CARD_OR_AT',4:'ENERGY',6:'ATTACK',7:'EVOLVE',8:'COUNT',9:'YES_NO'}
    for ctx, R in sorted(rows.items(), key=lambda kv: -len(kv[1]["y"])):
        X = np.array(R["X"], dtype=np.float32); y = np.array(R["y"], dtype=np.int8)
        grp = np.array(R["grp"]); gm = np.array(R["gm"])
        if len(np.unique(grp)) < 30: continue
        cut = np.quantile(gm, 0.85); tr, va = gm <= cut, gm > cut
        clf = HistGradientBoostingClassifier(max_iter=700, learning_rate=0.08, min_samples_leaf=15,
                                             l2_regularization=0.5, random_state=0)
        clf.fit(X[tr], y[tr]); models[ctx] = clf
        trc, trt = top1(clf, X, y, grp, tr); vc, vt = top1(clf, X, y, grp, va)
        tot_c += vc; tot_t += vt
        print(f"  {STN.get(ctx,ctx):<10}{trc/max(1,trt):>7.0%}{vc/max(1,vt):>7.0%}{vt:>8}")
    print(f"\n  WEIGHTED VAL top-1 (all contexts): {tot_c}/{tot_t} = {tot_c/max(1,tot_t):.1%}  (was 50%, target 80%)")
    import joblib
    joblib.dump({"models": models, "feat_ver": "rich1"}, f"{ROOT}/model/bono_rich_models.joblib")
    print("saved model/bono_rich_models.joblib")
