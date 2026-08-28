#!/usr/bin/env python3
"""How close is our Ogerpon imitation to palsystem? Honest split, control, tie-aware +
transposition-aware agreement, systematic divergences."""
import json, math, sys, collections
from collections import defaultdict, Counter

SP = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/palsys_agree/"
sys.path.insert(0, SP)
from pal_files import palsystem_games, train_eps

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

G = palsystem_games()
TR = train_eps()

# ---- his full within-turn play sequences (incl. forced moves) ----
LATER = defaultdict(set)     # (ep, turn, t) -> sigs he played strictly LATER that same turn
ANY = defaultdict(set)       # (ep, turn) -> all sigs he played that turn
seq = defaultdict(list)
for l in open(SP + "pal_turnplays.jsonl"):
    r = json.loads(l)
    seq[(r["ep"], r["turn"])].append((r["t"], r["sig"]))
for k, v in seq.items():
    v.sort()
    ANY[k] = set(s for _, s in v)
    for i, (t, _) in enumerate(v):
        LATER[(k[0], k[1], t)] = set(s for _, s in v[i + 1:])

AG = [("oger_pol  (SHIPPED)", "pal_oger_pol.jsonl"),
      ("oger_vf1  (valuefix)", "pal_oger_vf1.jsonl"),
      ("oger_f2   (CONTROL)", "pal__probe_oger_f2.jsonl"),
      ("grimm_v11 (PAL-BLIND)", "pal__probe_blind.jsonl")]
D = {}
for nm, f in AG:
    R = [json.loads(l) for l in open(SP + f)]
    for r in R:
        v = G[r["ep"]]
        r["won"] = v["won"]
        r["opp_arch"] = v["opp_arch"]
        r["split"] = "TRAIN" if r["ep"] in TR else "HELD-OUT"
        k = (r["ep"], r["turn"], r["t"])
        r["transp"] = int(r["tsig_s"] in LATER.get(k, ()))
        r["transp_any"] = int(r["tsig_s"] in ANY.get((r["ep"], r["turn"]), ()) and r["tsig_s"] != r["hsig_s"])
    D[nm] = R
keys = [(r["ep"], r["t"]) for r in D[AG[0][0]]]
for nm, _ in AG[1:]:
    assert [(r["ep"], r["t"]) for r in D[nm]] == keys, "decision sets differ for " + nm
N = len(keys)

STR = lambda r: r["hidx"] >= 0 and r["top"] == r["hidx"]
SEM = lambda r: r["hsig"] >= 0 and r["tsig"] == r["hsig"]
T3 = lambda r: r["hidx"] >= 0 and r["hidx"] in r["top3"]
P3 = lambda r: 0 <= r["play_rank"] < 3
EFF = lambda r: SEM(r) or (r["hsig"] >= 0 and r["transp"] == 1)


def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "  n/a"


def block(R):
    n = len(R)
    if not n:
        return None
    return dict(n=n, strict=sum(map(STR, R)), sem=sum(map(SEM, R)), t3=sum(map(T3, R)),
                p3=sum(map(P3, R)), eff=sum(map(EFF, R)),
                rnd=sum(1.0 / r["ncand"] for r in R),
                rndS=sum(r["hsig_n"] / float(r["ncand"]) for r in R),
                first=sum(1 for r in R if r["hidx"] == 0))


def show(f, title, agents=None):
    agents = agents or [a for a, _ in AG]
    print("\n%s" % title)
    print("  %-22s %6s %8s %9s %9s %8s %9s | %8s %8s" %
          ("net", "n", "STRICT", "TIE-AWARE", "EFFECTIVE", "TOP-3", "TOP3-play", "random", "1st-opt"))
    out = {}
    for nm in agents:
        R = [r for r in D[nm] if f(r)] if f else D[nm]
        m = block(R)
        out[nm] = m
        if not m:
            continue
        n = m["n"]
        print("  %-22s %6d %8s %9s %9s %8s %9s | %8s %8s" %
              (nm, n, pct(m["strict"], n), pct(m["sem"], n), pct(m["eff"], n), pct(m["t3"], n),
               pct(m["p3"], n), pct(m["rnd"], n), pct(m["first"], n)))
    a, b = out.get(AG[0][0]), out.get(AG[2][0])
    if a and b:
        print("  %-22s %6s %+7.1f %+8.1f %+8.1f %+7.1f %+8.1f   (tie-aware random %s)" %
              ("DELTA pol-vs-CONTROL", "", 100.0 * (a["strict"] - b["strict"]) / a["n"],
               100.0 * (a["sem"] - b["sem"]) / a["n"], 100.0 * (a["eff"] - b["eff"]) / a["n"],
               100.0 * (a["t3"] - b["t3"]) / a["n"], 100.0 * (a["p3"] - b["p3"]) / a["n"],
               pct(a["rndS"], a["n"])))
    c = out.get(AG[1][0])
    if a and c:
        print("  %-22s %6s %+7.1f %+8.1f %+8.1f %+7.1f %+8.1f" %
              ("DELTA vf1-vs-pol", "", 100.0 * (c["strict"] - a["strict"]) / a["n"],
               100.0 * (c["sem"] - a["sem"]) / a["n"], 100.0 * (c["eff"] - a["eff"]) / a["n"],
               100.0 * (c["t3"] - a["t3"]) / a["n"], 100.0 * (c["p3"] - a["p3"]) / a["n"]))
    return out


def mcnemar(X, Y, f, pred):
    b = sum(1 for x, y in zip(X, Y) if (not f or f(x)) and pred(x) and not pred(y))
    c = sum(1 for x, y in zip(X, Y) if (not f or f(x)) and not pred(x) and pred(y))
    z = (b - c) / math.sqrt(b + c) if (b + c) else 0.0
    p = 2 * (0.5 * math.erfc(abs(z) / math.sqrt(2)))
    return b, c, z, p


def lab(r):
    return "%s:%s" % (STYPE.get(r["stype"], r["stype"]), SCTX.get(r["sctx"], "ctx%d" % r["sctx"]))


HELD = lambda r: r["split"] == "HELD-OUT"
TRN = lambda r: r["split"] == "TRAIN"

print("=" * 112)
print("SETUP  --  Ogerpon / pro \"palsystem\" (ladder #2, 61.1%% over 149 games)")
w = sum(1 for e in G if G[e]["won"])
print("  replays: %d episodes (%d WINS / %d LOSSES). His submitted 60-card deck is identical to"
      % (len(G), w, len(G) - w))
print("  my-agent/oger_pal/deck.csv (multiset) in 149/149 games, so every decision is on OUR deck.")
print("  SPLIT: oger_pals_manifest.csv (the fine-tune corpus) == EXACTLY his 91 WINS, verified by")
print("  episode id (set equality, 0 in one and not the other). HELD-OUT = his 58 LOSSES.")
print("  Off-by-one validated on 2575 decisions/40 games: NEXT-step action is a legal selection")
print("  99.5%% of the time and matches an enumerated action 99.1%%; SAME-step (what")
print("  analysis/agree_general.py uses) only 72.5%% / 57.8%%.  -> NEXT step is correct.")
print("  Fast policy-argmax path validated against the REAL deployed agent (main.py -> mcts_agent,")
print("  SEARCH=1, loaded via field_gauntlet._purge_private/_prime_path): 493/500 = 98.6%%;")
print("  all 7 misses are CARD:TO_HAND, the context where the agent reshuffles its own deck.")
print("  Each net probed in its OWN process (no np_common/mcts_agent module sharing).")
print()
print("  *** CONTROL CAVEAT *** model/az/oger_f2_best.pth was trained on imit_oger_f2.npz")
print("  (oger_combined_manifest.csv) which CONTAINS all 91 palsystem wins, and it was trained")
print("  with --boost-players=palsystem --boost=3.0. So the 'control' already saw -- and was")
print("  3x-upweighted on -- the entire TRAIN split. It is a control for the EXTRA fine-tune")
print("  stage only; the delta below is a LOWER BOUND on what palsystem data bought.")
print("  It is still clean on the HELD-OUT split (it never saw a single palsystem loss).")
print()
print("  *** vf1 CONTAMINATION *** oger_valfix = oger_f2pal + 6 epochs on imit_oger_both.npz")
print("  (oger_bothsides_manifest.csv), which contains 146 palsystem sides = his 91 wins AND 55")
print("  of his 58 losses. oger_vf1 has therefore SEEN most of the held-out set. Its held-out")
print("  number is NOT held-out; read it as a second train number.")

A = D[AG[0][0]]
print("\nDECISION UNIVERSE: N = %d decisions (>=2 enumerated candidates, his seat, status ACTIVE)" % N)
print("  of %d total actions he took; %d were forced (1 candidate) and are excluded" %
      (sum(1 for _ in open(SP + "pal_turnplays.jsonl")), sum(1 for _ in open(SP + "pal_turnplays.jsonl")) - N))
unre = sum(1 for r in A if r["hidx"] < 0)
print("  his move not representable by our action enumerator : %4d (%.2f%%)" % (unre, 100.0 * unre / N))
print("  ALL candidates byte-identical to the net (enc)      : %4d (%.1f%%)" %
      (sum(1 for r in A if r["ngroups"] == 1), 100.0 * sum(1 for r in A if r["ngroups"] == 1) / N))
print("  ALL candidates are the SAME GAME ACTION             : %4d (%.1f%%)  <- choice cannot matter" %
      (sum(1 for r in A if r["nplays"] == 1), 100.0 * sum(1 for r in A if r["nplays"] == 1) / N))
print("  his chosen play has >1 interchangeable encoding     : %4d (%.1f%%)  <- strict is unfair here" %
      (sum(1 for r in A if r["hsig_n"] > 1), 100.0 * sum(1 for r in A if r["hsig_n"] > 1) / N))
for sp, f in (("TRAIN (91 wins)", TRN), ("HELD-OUT (58 losses)", HELD)):
    print("  %-22s %5d decisions over %3d games" %
          (sp, sum(1 for r in A if f(r)), len(set(r["ep"] for r in A if f(r)))))

show(None, "=" * 112 + "\nALL 149 GAMES (contaminated: 61%% of it is training data)")
show(TRN, "TRAIN SPLIT - his 91 WINS, the exact fine-tune corpus")
show(HELD, "HELD-OUT SPLIT - his 58 LOSSES  <== THE HONEST NUMBER (clean for oger_pol & the control)")

MAT = lambda r: r["nplays"] >= 2 and r["hsig"] >= 0
show(lambda r: MAT(r) and HELD(r),
     "=" * 112 + "\nWHERE THE CHOICE DEMONSTRABLY MATTERS (>=2 distinct game actions) - HELD-OUT ONLY")
show(lambda r: MAT(r) and TRN(r), "WHERE THE CHOICE DEMONSTRABLY MATTERS - TRAIN ONLY")

print("\n" + "=" * 112)
print("MEMORISATION CHECK  (train-minus-heldout gap; a big gap on the fine-tuned net + ~0 gap on")
print("the control = memorisation rather than transferable skill)")
print("  %-22s %10s %10s %8s | %10s %10s %8s" %
      ("net", "TRAIN str", "HELD str", "gap", "TRAIN tie", "HELD tie", "gap"))
for nm, _ in AG:
    a, b = block([r for r in D[nm] if TRN(r)]), block([r for r in D[nm] if HELD(r)])
    print("  %-22s %10s %10s %+7.1f | %10s %10s %+7.1f" %
          (nm, pct(a["strict"], a["n"]), pct(b["strict"], b["n"]),
           100.0 * (a["strict"] / a["n"] - b["strict"] / b["n"]),
           pct(a["sem"], a["n"]), pct(b["sem"], b["n"]),
           100.0 * (a["sem"] / a["n"] - b["sem"] / b["n"])))

print("\n" + "=" * 112)
print("HOW MUCH DISAGREEMENT IS HARMLESS  (of the decisions where our top-1 play != his)")
print("  %-22s %-9s %9s %8s | %-22s %-24s %10s" %
      ("net", "split", "disagree", "of N", "dup-encoding (same play)", "within-turn transposition",
       "REAL"))
for nm, _ in AG:
    for sp, f in (("TRAIN", TRN), ("HELD-OUT", HELD), ("ALL", None)):
        R = [r for r in D[nm] if (f(r) if f else True)]
        n = len(R)
        dis = [r for r in R if r["hidx"] >= 0 and r["top"] != r["hidx"]]
        dup = [r for r in dis if r["tsig"] == r["hsig"]]
        tra = [r for r in dis if r["tsig"] != r["hsig"] and r["transp"]]
        real = [r for r in dis if r["tsig"] != r["hsig"] and not r["transp"]]
        print("  %-22s %-9s %9d %8s | %6d %5.1f%% of dis   %6d %5.1f%% of dis    %6d %5.1f%% of N" %
              (nm, sp, len(dis), pct(len(dis), n), len(dup), 100.0 * len(dup) / max(1, len(dis)),
               len(tra), 100.0 * len(tra) / max(1, len(dis)), len(real), 100.0 * len(real) / n))
print("  dup-encoding = same GAME ACTION via an interchangeable copy of an identical card.")
print("  transposition = he executes OUR chosen play LATER in the SAME turn (ordering only).")

print("\n" + "=" * 112)
print("GAME-CLUSTERED BOOTSTRAP (resample the 58 held-out GAMES, 4000 reps) -- decisions inside one")
print("game are not independent, so this is the interval that matters")
import random
random.seed(11)
HG = sorted(set(r["ep"] for r in D[AG[0][0]] if HELD(r)))
byg = {nm: defaultdict(list) for nm, _ in AG}
for nm, _ in AG:
    for r in D[nm]:
        if HELD(r):
            byg[nm][r["ep"]].append(r)
B = 4000
draws = [[HG[random.randrange(len(HG))] for _ in range(len(HG))] for _ in range(B)]


def bootci(nm, pred):
    v = []
    for dr in draws:
        num = den = 0
        for g in dr:
            R = byg[nm][g]
            den += len(R)
            num += sum(1 for r in R if pred(r))
        v.append(100.0 * num / den)
    v.sort()
    return v[int(.025 * B)], v[int(.975 * B)]


def bootdelta(n1, n2, pred):
    v = []
    for dr in draws:
        a = b = den = 0
        for g in dr:
            R1, R2 = byg[n1][g], byg[n2][g]
            den += len(R1)
            a += sum(1 for r in R1 if pred(r))
            b += sum(1 for r in R2 if pred(r))
        v.append(100.0 * (a - b) / den)
    v.sort()
    return v[int(.025 * B)], v[int(.975 * B)]


for nm, _ in AG:
    m = block([r for r in D[nm] if HELD(r)])
    lo, hi = bootci(nm, STR)
    lo2, hi2 = bootci(nm, SEM)
    print("  %-22s HELD-OUT strict %5.1f%% [%.1f, %.1f]   tie-aware %5.1f%% [%.1f, %.1f]" %
          (nm, 100.0 * m["strict"] / m["n"], lo, hi, 100.0 * m["sem"] / m["n"], lo2, hi2))
for tag, a, b in (("pol - CONTROL", AG[0][0], AG[2][0]), ("vf1 - pol", AG[1][0], AG[0][0])):
    lo, hi = bootdelta(a, b, STR)
    lo2, hi2 = bootdelta(a, b, SEM)
    print("  DELTA %-16s strict %+5.1f pp [%+.1f, %+.1f]   tie-aware %+5.1f pp [%+.1f, %+.1f]" %
          (tag,
           100.0 * (block([r for r in D[a] if HELD(r)])["strict"]
                    - block([r for r in D[b] if HELD(r)])["strict"]) / len([r for r in D[a] if HELD(r)]),
           lo, hi,
           100.0 * (block([r for r in D[a] if HELD(r)])["sem"]
                    - block([r for r in D[b] if HELD(r)])["sem"]) / len([r for r in D[a] if HELD(r)]),
           lo2, hi2))

print("\n" + "=" * 112)
print("vf1 ON THE 3 LOSSES IT GENUINELY NEVER SAW (oger_bothsides_manifest.csv holds 55 of his 58")
print("losses; these 3 are the only clean ones for vf1). Tiny n -- reported for honesty, not power.")
CLEAN = {"90907145", "91113407", "91578244"}
for nm, _ in AG:
    m = block([r for r in D[nm] if r["ep"] in CLEAN])
    print("  %-22s n=%4d  strict %5.1f%%  tie %5.1f%%  eff %5.1f%%  top3 %5.1f%%" %
          (nm, m["n"], 100.0 * m["strict"] / m["n"], 100.0 * m["sem"] / m["n"],
           100.0 * m["eff"] / m["n"], 100.0 * m["t3"] / m["n"]))
m55 = lambda r: HELD(r) and r["ep"] not in CLEAN
for nm, _ in AG[:2]:
    m = block([r for r in D[nm] if m55(r)])
    print("  %-22s on the 55 losses vf1 DID train on: strict %5.1f%%  tie %5.1f%%" %
          (nm, 100.0 * m["strict"] / m["n"], 100.0 * m["sem"] / m["n"]))

print("\n" + "=" * 112)
print("PAIRED SIGNIFICANCE (McNemar on the SAME decisions)")
for tag, X, Y in (("pol vs CONTROL", D[AG[0][0]], D[AG[2][0]]),
                  ("vf1 vs pol", D[AG[1][0]], D[AG[0][0]])):
    for sp, f in (("ALL", None), ("TRAIN", TRN), ("HELD-OUT", HELD)):
        b, c, z, p = mcnemar(X, Y, f, STR)
        b2, c2, z2, p2 = mcnemar(X, Y, f, SEM)
        print("  %-15s %-9s strict: A-only %5d  B-only %5d  z=%6.2f p=%.2e |"
              " tie-aware: %5d / %5d  z=%6.2f p=%.2e" % (tag, sp, b, c, z, p, b2, c2, z2, p2))

for title, filt in (("HELD-OUT (his 58 losses)", HELD), ("ALL 149 games", None)):
    print("\n" + "=" * 112)
    print("BY SELECT TYPE : CONTEXT - %s, buckets with n>=40" % title)
    print("  %-24s %6s | %-24s | %-24s | %-24s" %
          ("select_type:context", "n", "oger_pol  str/tie/eff", "CONTROL   str/tie/eff",
           "oger_vf1  str/tie/eff"))
    buck = defaultdict(list)
    for i, r in enumerate(D[AG[0][0]]):
        if not filt or filt(r):
            buck[lab(r)].append(i)
    rows = []
    for k, ix in buck.items():
        if len(ix) < 40:
            continue
        ms = [block([D[nm][i] for i in ix]) for nm, _ in AG]
        rows.append((len(ix), k, ms))
    for n, k, ms in sorted(rows, key=lambda x: -x[0]):
        print("  %-24s %6d | %s| %s| %s" % (k, n,
              "".join("%7s %7s %7s " % (pct(m["strict"], n), pct(m["sem"], n), pct(m["eff"], n))
                      for m in ms[:1]),
              "".join("%7s %7s %7s " % (pct(m["strict"], n), pct(m["sem"], n), pct(m["eff"], n))
                      for m in ms[2:3]),
              "".join("%7s %7s %7s " % (pct(m["strict"], n), pct(m["sem"], n), pct(m["eff"], n))
                      for m in ms[1:2])))

print("\n" + "=" * 112)
print("BY OPPONENT ARCHETYPE - HELD-OUT only (n>=40 decisions)")
buck = defaultdict(list)
for i, r in enumerate(D[AG[0][0]]):
    if HELD(r):
        buck[r["opp_arch"]].append(i)
print("  %-16s %6s %5s | %8s %9s %9s | %8s %9s %9s" %
      ("opp archetype", "n", "games", "pol str", "pol tie", "pol eff", "ctl str", "ctl tie", "ctl eff"))
for k, ix in sorted(buck.items(), key=lambda x: -len(x[1])):
    if len(ix) < 40:
        continue
    n = len(ix)
    a = block([D[AG[0][0]][i] for i in ix]); b = block([D[AG[2][0]][i] for i in ix])
    ng = len(set(D[AG[0][0]][i]["ep"] for i in ix))
    print("  %-16s %6d %5d | %8s %9s %9s | %8s %9s %9s" %
          (k, n, ng, pct(a["strict"], n), pct(a["sem"], n), pct(a["eff"], n),
           pct(b["strict"], n), pct(b["sem"], n), pct(b["eff"], n)))


def kind(s):
    return s.split(":")[0]


def patterns(R, title, topn=14):
    real = [r for r in R if r["hsig"] >= 0 and r["tsig"] != r["hsig"] and not r["transp"]]
    print("\n%s" % title)
    print("  REAL (non-tie, non-transposition) divergences: %d of %d decisions = %.1f%%" %
          (len(real), len(R), 100.0 * len(real) / max(1, len(R))))
    c1 = Counter("%-20s he=%-10s -> we=%-10s" % (lab(r), kind(r["hlab"].split("+")[0]),
                                                 kind(r["tlab"].split("+")[0])) for r in real)
    print("  -- by move KIND --")
    for k, v in c1.most_common(topn):
        print("   %5d (%4.1f%%)  %s" % (v, 100.0 * v / len(real), k))
    c2 = Counter("%-20s he=%-34s -> we=%-34s" % (lab(r), r["hlab"][:34], r["tlab"][:34]) for r in real)
    print("  -- exact plays --")
    for k, v in c2.most_common(topn):
        print("   %5d (%4.1f%%)  %s" % (v, 100.0 * v / len(real), k))
    # net direction: which concrete cards/plays does he pick more than we do, and vice versa
    hc = Counter(r["hlab"][:38] for r in real)
    tc = Counter(r["tlab"][:38] for r in real)
    net = Counter()
    for k in set(hc) | set(tc):
        net[k] = hc[k] - tc[k]
    print("  -- NET direction (his count minus ours over the same decisions) --")
    print("     HE does MORE:")
    for k, v in net.most_common(10):
        if v <= 0:
            break
        print("      %+5d  %s" % (v, k))
    print("     WE do MORE:")
    for k, v in sorted(net.items(), key=lambda x: x[1])[:10]:
        if v >= 0:
            break
        print("      %+5d  %s" % (v, k))


patterns([r for r in D[AG[0][0]] if HELD(r)],
         "=" * 112 + "\nSYSTEMATIC DIVERGENCES  oger_pol vs palsystem - HELD-OUT (his 58 losses)")
patterns(D[AG[0][0]], "=" * 112 + "\nSYSTEMATIC DIVERGENCES  oger_pol vs palsystem - ALL 149 games")
