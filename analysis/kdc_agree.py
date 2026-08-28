#!/usr/bin/env python3
"""Agreement analysis: our nets vs @kdcyberdude on his own 135 replays."""
import json, sys, math, csv
from collections import defaultdict, Counter

SP = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/"
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/"
STYPE = {0: 'MAIN', 1: 'CARD', 2: 'ATTACHED', 3: 'CARD_OR_AT', 4: 'ENERGY', 5: 'SKILL',
         6: 'ATTACK', 7: 'EVOLVE', 8: 'COUNT', 9: 'YES_NO', 10: 'SPEC_COND'}
SCTX = {0: 'MAIN', 1: 'SETUP_ACTIVE', 2: 'SETUP_BENCH', 3: 'SWITCH', 4: 'TO_ACTIVE', 5: 'TO_BENCH',
        6: 'TO_FIELD', 7: 'TO_HAND', 8: 'DISCARD', 9: 'TO_DECK', 10: 'TO_DECK_BOT', 11: 'TO_PRIZE',
        13: 'DMG_COUNTER', 14: 'DMG_CTR_ANY', 15: 'DAMAGE', 16: 'RM_DMG_CTR', 17: 'HEAL',
        18: 'EVOLVES_FROM', 19: 'EVOLVES_TO', 21: 'ATTACH_FROM', 22: 'ATTACH_TO', 24: 'LOOK',
        25: 'EFFECT_TGT', 26: 'DISC_EN_CARD', 28: 'SWITCH_EN_CARD', 30: 'DISCARD_ENERGY',
        33: 'SWITCH_ENERGY', 34: 'SKILL_ORDER', 35: 'ATTACK', 37: 'EVOLVE', 38: 'DRAW_COUNT',
        39: 'DMG_CTR_CNT', 40: 'RM_DMG_CTR_CNT', 41: 'IS_FIRST', 42: 'MULLIGAN', 43: 'ACTIVATE',
        44: 'FIRST_EFFECT', 46: 'COIN_HEAD', 47: 'AFF_SP_COND', 48: 'REC_SP_COND'}

TRAIN_EPS = set(r['episode'] for r in csv.DictReader(open(ROOT + 'grimm_teachers_manifest.csv'))
                if r['player'] == '@kdcyberdude')
IDX = {r['episode']: r for r in csv.DictReader(open(ROOT + 'dump_index_kdc.csv'))}


def lab(r):
    return "%s:%s" % (STYPE.get(r["stype"], r["stype"]), SCTX.get(r["sctx"], "ctx%d" % r["sctx"]))


A = [json.loads(l) for l in open(SP + "kdpol.jsonl")]
B = [json.loads(l) for l in open(SP + "v12.jsonl")]
assert [(r["f"], r["t"]) for r in A] == [(r["f"], r["t"]) for r in B], "decision sets differ"
for r in A + B:
    r["ep"] = r["f"].split(".")[0]
    r["split"] = "TRAIN(his 90 wins)" if r["ep"] in TRAIN_EPS else "HELD-OUT(his 45 losses)"
N = len(A)

STR = lambda r: r["hidx"] >= 0 and r["top"] == r["hidx"]          # exact index-set match
SEM = lambda r: r["hsig"] >= 0 and r["tsig"] == r["hsig"]          # same GAME ACTION
T3 = lambda r: r["hidx"] >= 0 and r["hidx"] in r["top3"]
P3 = lambda r: 0 <= r["play_rank"] < 3                             # his play in our top-3 PLAYS


def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "  n/a"


def block(R, f=None, name=""):
    R = [r for r in R if f(r)] if f else R
    n = len(R)
    if not n:
        return None
    return dict(n=n, strict=sum(map(STR, R)), sem=sum(map(SEM, R)), t3=sum(map(T3, R)),
                p3=sum(map(P3, R)),
                rnd=sum(1.0 / r["ncand"] for r in R),
                rndS=sum(r["hsig_n"] / float(r["ncand"]) for r in R),
                first=sum(1 for r in R if r["hidx"] == 0))


def show(f, title):
    print("\n%s" % title)
    print("  %-24s %7s %8s %9s %8s %9s | %8s %8s" %
          ("agent", "n", "STRICT", "TIE-AWARE", "TOP-3", "TOP-3play", "random", "1st-opt"))
    out = {}
    for nm, R in (("grimm_kdpol (NEW)", A), ("grimm_v12_polfix (CTL)", B)):
        m = block(R, f)
        out[nm] = m
        if not m:
            continue
        n = m["n"]
        print("  %-24s %7d %8s %9s %8s %9s | %8s %8s" %
              (nm, n, pct(m["strict"], n), pct(m["sem"], n), pct(m["t3"], n), pct(m["p3"], n),
               pct(m["rnd"], n), pct(m["first"], n)))
    a, b = out["grimm_kdpol (NEW)"], out["grimm_v12_polfix (CTL)"]
    if a and b:
        print("  %-24s %7s %+7.1f %+8.1f %+7.1f %+8.1f   (tie-aware random baseline %s)" %
              ("DELTA (pp)", "", 100.0 * (a["strict"] - b["strict"]) / a["n"],
               100.0 * (a["sem"] - b["sem"]) / a["n"], 100.0 * (a["t3"] - b["t3"]) / a["n"],
               100.0 * (a["p3"] - b["p3"]) / a["n"], pct(a["rndS"], a["n"])))
    return out


def mcnemar(f, pred):
    b = sum(1 for x, y in zip(A, B) if (not f or f(x)) and pred(x) and not pred(y))
    c = sum(1 for x, y in zip(A, B) if (not f or f(x)) and not pred(x) and pred(y))
    z = (b - c) / math.sqrt(b + c) if (b + c) else 0.0
    p = 2 * (0.5 * math.erfc(abs(z) / math.sqrt(2)))
    return b, c, z, p


print("=" * 108)
print("SETUP")
print("  135 replays of @kdcyberdude (ladder #8, 1160.6, 90-45). Deck reconstructed from his own")
print("  step-1 submission in all 135 games: byte-identical to my-agent/*/deck.csv in 135/135.")
print("  Decision = his seat, status=ACTIVE, a select with >1 enumerated candidate.")
print("  Off-by-one validated empirically: NEXT-step action is a legal selection 99.5%% of the time,")
print("  SAME-step only 69.4%% (n=7559 over 40 games) -- analysis/agree_general.py uses the SAME step.")
print("  Fast policy-argmax path validated against the REAL deployed agent (main.py -> mcts_agent,")
print("  SEARCH=1, loaded via round_robin.load + field_gauntlet._purge_private/_prime_path):")
print("  587/600 identical; all 13 misses are CARD:TO_HAND, the one context where the agent's own")
print("  determinization reshuffles the deck (self-consistency there is only 85%% over 5 reruns).")
print()
print("  *** CONTAMINATION *** the fine-tune's teacher manifest (grimm_teachers_manifest.csv, 243")
print("  sides) contains exactly 90 kdcyberdude sides, and they are exactly his 90 WINS.")
print("  So the split is: TRAIN = his 90 wins, HELD-OUT = his 45 losses. Reported separately.")
print("  The control (v12) saw none of these 135 games, so the DELTA stays interpretable on both.")

unre = sum(1 for r in A if r["hidx"] < 0)
deg_enc = sum(1 for r in A if r["ngroups"] == 1)
deg_play = sum(1 for r in A if r["nplays"] == 1)
print("\nDECISION UNIVERSE: N = %d decisions" % N)
print("  his move not representable by our action enumerator : %4d (%.2f%%)" % (unre, 100.0 * unre / N))
print("  ALL candidates byte-identical to the net (enc)      : %4d (%.1f%%)" % (deg_enc, 100.0 * deg_enc / N))
print("  ALL candidates are the SAME GAME ACTION (play sig)  : %4d (%.1f%%)  <- choice cannot matter"
      % (deg_play, 100.0 * deg_play / N))
dupe = sum(1 for r in A if r["hsig_n"] > 1)
print("  his chosen play has >1 interchangeable encoding     : %4d (%.1f%%)  <- strict agreement is"
      " unfairly penalised here" % (dupe, 100.0 * dupe / N))

show(None, "=" * 108 + "\nHEADLINE - ALL 135 GAMES (contaminated: 2/3 of it is training data)")
show(lambda r: r["split"].startswith("TRAIN"), "TRAIN SPLIT - his 90 WINS, seen by the fine-tune")
show(lambda r: r["split"].startswith("HELD"), "HELD-OUT SPLIT - his 45 LOSSES, seen by neither net  <== THE HONEST NUMBER")

MAT = lambda r: r["nplays"] >= 2 and r["hsig"] >= 0
show(MAT, "=" * 108 + "\nWHERE THE CHOICE DEMONSTRABLY MATTERS (>=2 distinct game actions available) - ALL games")
show(lambda r: MAT(r) and r["split"].startswith("HELD"),
     "WHERE THE CHOICE DEMONSTRABLY MATTERS - HELD-OUT ONLY")

print("\n" + "=" * 108)
print("HOW MUCH DISAGREEMENT IS HARMLESS")
print("  %-22s %-14s %8s %10s %12s %12s" % ("agent", "split", "disagree", "of N", "HARMLESS", "REAL"))
for nm, R in (("grimm_kdpol", A), ("grimm_v12_polfix", B)):
    for sp in ("TRAIN(his 90 wins)", "HELD-OUT(his 45 losses)", "ALL"):
        RR = [r for r in R if sp == "ALL" or r["split"] == sp]
        n = len(RR)
        dis = [r for r in RR if r["hidx"] >= 0 and r["top"] != r["hidx"]]
        harm = [r for r in dis if r["tsig"] == r["hsig"]]
        real = [r for r in dis if r["tsig"] != r["hsig"]]
        print("  %-22s %-14s %8d %10s %6d %5.1f%% %6d %5.1f%%" %
              (nm, sp.split("(")[0], len(dis), pct(len(dis), n), len(harm),
               100.0 * len(harm) / max(1, len(dis)), len(real), 100.0 * len(real) / n))
print("  HARMLESS = same GAME ACTION, different interchangeable copy of an identical card"
      " (model blindness).")

print("\n" + "=" * 108)
print("PAIRED SIGNIFICANCE (McNemar, kdpol vs v12 on the SAME decisions)")
for sp, f in (("ALL", None), ("TRAIN", lambda r: r["split"].startswith("TRAIN")),
              ("HELD-OUT", lambda r: r["split"].startswith("HELD"))):
    b, c, z, p = mcnemar(f, STR)
    b2, c2, z2, p2 = mcnemar(f, SEM)
    print("  %-9s strict: kdpol-only %5d  v12-only %4d  z=%6.2f p=%.2e |"
          " tie-aware: %5d / %4d  z=%6.2f p=%.2e" % (sp, b, c, z, p, b2, c2, z2, p2))

print("\n" + "=" * 108)
print("BY DECISION CONTEXT - HELD-OUT GAMES ONLY (his 45 losses), buckets with n>=25")
print("  %-22s %6s | %-22s | %-22s | %6s" % ("select_type:context", "n",
      "kdpol strict/tie/top3", "v12   strict/tie/top3", "d_tie"))
buck = defaultdict(list)
for i, r in enumerate(A):
    if r["split"].startswith("HELD"):
        buck[lab(r)].append(i)
rows = []
for k, ix in buck.items():
    if len(ix) < 25:
        continue
    ma, mb = block([A[i] for i in ix]), block([B[i] for i in ix])
    rows.append((len(ix), k, ma, mb, 100.0 * (ma["sem"] - mb["sem"]) / len(ix)))
for n, k, ma, mb, d in sorted(rows, key=lambda x: -x[0]):
    print("  %-22s %6d | %6s %6s %6s   | %6s %6s %6s   | %+5.1f" %
          (k, n, pct(ma["strict"], n), pct(ma["sem"], n), pct(ma["t3"], n),
           pct(mb["strict"], n), pct(mb["sem"], n), pct(mb["t3"], n), d))

print("\n" + "=" * 108)
print("BY DECISION CONTEXT - ALL 135 GAMES, buckets with n>=25 (bigger samples, contaminated)")
buck = defaultdict(list)
for i, r in enumerate(A):
    buck[lab(r)].append(i)
rows = []
for k, ix in buck.items():
    if len(ix) < 25:
        continue
    ma, mb = block([A[i] for i in ix]), block([B[i] for i in ix])
    rows.append((len(ix), k, ma, mb, 100.0 * (ma["sem"] - mb["sem"]) / len(ix)))
for n, k, ma, mb, d in sorted(rows, key=lambda x: -x[0]):
    print("  %-22s %6d | %6s %6s %6s   | %6s %6s %6s   | %+5.1f" %
          (k, n, pct(ma["strict"], n), pct(ma["sem"], n), pct(ma["t3"], n),
           pct(mb["strict"], n), pct(mb["sem"], n), pct(mb["t3"], n), d))


def kind(s):
    return s.split(":")[0]


def patterns(R, title, topn=18):
    real = [r for r in R if r["hsig"] >= 0 and r["tsig"] != r["hsig"]]
    print("\n%s" % title)
    print("  real (non-tie) divergences: %d of %d decisions = %.1f%%" %
          (len(real), len(R), 100.0 * len(real) / max(1, len(R))))
    c1 = Counter("%-18s he=%-8s -> we=%-8s" % (lab(r), kind(r["hlab"].split("+")[0]),
                                               kind(r["tlab"].split("+")[0])) for r in real)
    print("  -- by move KIND --")
    for k, v in c1.most_common(topn):
        print("   %5d (%4.1f%%)  %s" % (v, 100.0 * v / len(real), k))
    c2 = Counter("%-18s he=%-30s -> we=%-30s" % (lab(r), r["hlab"][:30], r["tlab"][:30]) for r in real)
    print("  -- exact plays --")
    for k, v in c2.most_common(topn):
        print("   %5d (%4.1f%%)  %s" % (v, 100.0 * v / len(real), k))


patterns([r for r in A if r["split"].startswith("HELD")],
         "=" * 108 + "\nSYSTEMATIC DIVERGENCES  grimm_kdpol vs him - HELD-OUT (his 45 losses)")
patterns(A, "=" * 108 + "\nSYSTEMATIC DIVERGENCES  grimm_kdpol vs him - ALL 135 games")
