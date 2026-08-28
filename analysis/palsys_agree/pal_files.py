#!/usr/bin/env python3
"""Resolve the 149 palsystem replay files + their win/loss split. Shared by probe & analysis."""
import csv, glob, os, json

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/"
WHO = os.environ.get("PAL_PLAYER", "palsystem").lower()


def palsystem_games():
    fidx = {}
    for p in glob.glob(ROOT + "*/*.json"):
        fidx.setdefault(os.path.basename(p), p)
    rows = []
    for f in ("dump_index_0810.csv", "dump_index_pal2.csv"):
        rows += list(csv.DictReader(open(ROOT + f)))
    seen, out = set(), {}
    for r in rows:
        if not (WHO in (r["p0"] or "").lower() or WHO in (r["p1"] or "").lower()):
            continue
        ep = r["episode"]
        if ep in out:
            continue
        p = fidx.get(os.path.basename(r["path"]))
        if not p:
            continue
        seat = 0 if WHO in r["p0"].lower() else 1
        out[ep] = dict(path=p, ep=ep, seat=seat, won=int(int(r["winner"]) == seat),
                       opp=(r["p1"] if seat == 0 else r["p0"]),
                       opp_arch=(r["a1"] if seat == 0 else r["a0"]),
                       my_arch=(r["a0"] if seat == 0 else r["a1"]), turns=int(r["turns"]))
    return out


def train_eps():
    return set(r["episode"] for r in csv.DictReader(open(ROOT + "oger_pals_manifest.csv")))


if __name__ == "__main__":
    g = palsystem_games()
    tr = train_eps()
    w = set(e for e, v in g.items() if v["won"])
    print(json.dumps(dict(n=len(g), wins=len(w), losses=len(g) - len(w),
                          manifest=len(tr), manifest_eq_wins=(tr == w),
                          manifest_minus_wins=len(tr - w), wins_minus_manifest=len(w - tr))))
