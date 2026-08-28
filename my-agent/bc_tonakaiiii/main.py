"""BC SPARRING PARTNER — a behavioral clone of a top player (Majkel1337), used as a
REALISTIC opponent to sharpen local validation. At each decision it scores every legal
option with the trained imitation model and picks the highest (rule-free); it can only
ever choose an offered option, so play is always legal/coherent. Not a submission — an
opponent for field_eval/mirror_ab."""
import os, sys, json
_D = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
for _p in (_D, os.getcwd(), "/kaggle_simulations/agent"):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)
import bc_features as F

_M = {"model": None, "vocab": None, "cf": None, "adm": None, "deck": None, "ok": None}

def _load():
    if _M["ok"] is not None:
        return _M["ok"]
    try:
        import joblib
        _M["model"] = joblib.load(os.path.join(_D, "bc_model.joblib"))
        _M["vocab"] = json.load(open(os.path.join(_D, "bc_vocab.json")))["vocab"]
        # card feats + attack dmg from the SDK (same as training)
        from cg.api import all_attack, all_card_data
        _M["adm"] = {str(a.attackId): (a.damage or 0) for a in all_attack()}
        cf = {}
        for c in all_card_data():
            cat = 1 if getattr(c, "hp", None) else (3 if "Energy" in (c.name or "") else 2)
            cf[str(c.cardId)] = [getattr(c, "hp", 0) or 0, 1 if getattr(c, "ex", False) else 0,
                                 cat, getattr(c, "stage", 0) or 0]
        _M["cf"] = cf
        _M["deck"] = [int(x) for x in open(os.path.join(_D, "deck.csv")).read().split()]
        # correct AreaType resolver (matches training)
        def resolve_fixed(obs, opt):
            if opt.get("cardId") is not None: return opt["cardId"]
            area, index = opt.get("area"), opt.get("index")
            if area is None or index is None: return None
            cur = obs.get("current") or {}; you = cur.get("yourIndex", 0)
            pi = opt.get("playerIndex"); pi = you if pi is None else pi
            players = cur.get("players") or [{}, {}]; p = players[pi] if pi < len(players) else {}
            try:
                if area == 2: return (p.get("hand") or [])[index].get("id")
                if area == 4:
                    c = (p.get("active") or [])[index]; return c.get("id") if c else None
                if area == 5:
                    c = (p.get("bench") or [])[index]; return c.get("id") if c else None
                if area == 3: return (p.get("discard") or [])[index].get("id")
                if area == 7: return (cur.get("stadium") or [])[index].get("id")
                # areas 12 (LOOKING) and 6 (PRIZE) were handled by the TRAINING resolver
                # (analysis/bc_train.py:34,36) but missing here — the live clone was
                # card-identity-blind on look-at-top-N picks while the model was trained
                # seeing real ids there.
                if area == 12: return (cur.get("looking") or [])[index].get("id")
                if area == 6: return (p.get("prize") or [])[index].get("id")
                if area == 1: return ((obs.get("select") or {}).get("deck") or [])[index].get("id")
            except (IndexError, AttributeError, TypeError):
                return None
            return None
        F.resolve_card_id = resolve_fixed
        _M["ok"] = True
    except Exception as _e:
        import sys as _sys
        # was silent: a joblib/sklearn/numpy drift turned this clone into a pick-first bot
        # with no observable signal. Print once so a dead clone is visible in gate logs.
        print(f"BC-CLONE MODEL LOAD FAILED ({type(_e).__name__}: {_e}) — "
              f"agent degraded to pick-first", file=_sys.stderr)
        _M["ok"] = False
    return _M["ok"]

def agent(obs_dict):
    sel = obs_dict.get("select")
    if sel is None:
        return _M["deck"] if _load() and _M["deck"] else []
    opts = sel.get("option") or []
    if not opts:
        return []
    if len(opts) == 1 or not _load():
        need = max(sel.get("minCount", 1) or 1, 1)
        return list(range(min(need, len(opts))))
    try:
        import numpy as np
        obs = {"current": obs_dict.get("current"), "select": sel, "step": 0}
        feats = []
        for i, op in enumerate(opts):
            try:
                feats.append(F.option_features(obs, op, i, len(opts), _M["vocab"], _M["cf"], _M["adm"]))
            except Exception:
                feats.append([0.0] * F.N_FEATURES)
        scores = _M["model"].predict_proba(np.array(feats, dtype=np.float32))[:, 1]
        order = sorted(range(len(opts)), key=lambda i: -scores[i])
        lo = max(sel.get("minCount", 1) or 1, 1)
        hi = sel.get("maxCount", lo) or lo
        # take the top-1 (or the min required); most contexts are single-choice
        k = lo if lo > 1 else 1
        return order[:min(k, hi, len(opts))]
    except Exception:
        need = max(sel.get("minCount", 1) or 1, 1)
        return list(range(min(need, len(opts))))
