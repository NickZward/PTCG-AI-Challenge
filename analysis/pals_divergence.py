#!/usr/bin/env python3
"""Deep-dive the palsystem divergences recorded by agree_pals_net.py, with the correct
leave-games-out split, and the Hydrapple/Meganium evolution-timing test."""
import json
import os
from collections import Counter, defaultdict

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
rows = json.load(open("/tmp/agree_pals.jsonl"))

# ---- exact stage-2 split (train_imit_v2.py:242-267): first 14 games of rng(0).permutation ----
M_TGT, M_NCAND, M_STYPE, M_TURN, M_WON, M_WR, M_OPP, M_MARGIN, M_PID = range(9)
z = np.load(os.path.join(ROOT, "model/az/imit_pals_f2.npz"), allow_pickle=True)
meta = z["meta"]
key = np.stack([meta[:, M_WON], meta[:, M_WR], meta[:, M_OPP], meta[:, M_PID]], 1)
ng = np.ones(len(meta), bool)
ng[1:] = (meta[1:, M_TURN] < meta[:-1, M_TURN]) | (key[1:] != key[:-1]).any(1)
gid = np.cumsum(ng) - 1
n_g = int(gid[-1]) + 1
perm = np.random.default_rng(0).permutation(n_g)
order = []
for r in rows:
    if r["ep"] not in order:
        order.append(r["ep"])
HELD2 = {order[g] for g in perm[:14]}          # the 14 games train_f2b.log reported as held-out
print(f"stage-2 held-out games (the '96.2% held-out top1' set): {len(HELD2)}")


def score(label, sub):
    if not sub:
        print(f"  {label:36s} n=0")
        return
    a = sum(r["agree"] for r in sub)
    t = sum(r["agree"] or r["tie"] for r in sub)
    print(f"  {label:36s} n={len(sub):5d}  strict {a/len(sub):6.1%}  tie-aware {t/len(sub):6.1%}")


print("\nAGREEMENT BY STAGE-2 SPLIT (oger_f2pal_best.pth):")
score("all 91 games", rows)
score("stage-2 TRAIN (77 games)", [r for r in rows if r["ep"] not in HELD2])
score("stage-2 HELD (14 games)", [r for r in rows if r["ep"] in HELD2])

# ---------------------------------------------------------------- evolution timing
LINE = {**{c: 'HYDRAPPLE' for c in (149, 346, 93, 150)},
        **{c: 'MEGANIUM' for c in (917, 709, 918, 710)}}
NAMES = {149: 'Applin', 346: 'Applin', 93: 'Dipplin', 150: 'Hydrapple ex',
         917: 'Chikorita', 709: 'Bayleef', 918: 'Bayleef', 710: 'Meganium'}


def evo_targets(r, side):
    """Which evolution cards this action plays, from the human labels ('EVOLVE(A->B)')."""
    out = []
    for lab in r[side]:
        if lab.startswith("EVOLVE("):
            out.append(lab[7:-1])
    return out


print("\n=== EVOLUTION LINES: does the net evolve when he evolves? ===")
# every MAIN decision where at least one EVOLVE option was legal
legal = [r for r in rows if r["stype"] == 0 and r["n_evolve_opts"] > 0]
he_evo = [r for r in legal if any(l.startswith("EVOLVE") for l in r["his"])]
we_evo = [r for r in legal if any(l.startswith("EVOLVE") for l in r["mine"])]
both = [r for r in legal if r in he_evo and r in we_evo]
print(f"MAIN decisions with an EVOLVE legal: {len(legal)}")
print(f"  he evolved: {len(he_evo)} ({len(he_evo)/len(legal):.1%})   "
      f"we evolve: {len(we_evo)} ({len(we_evo)/len(legal):.1%})")
c = Counter((any(l.startswith('EVOLVE') for l in r['his']),
             any(l.startswith('EVOLVE') for l in r['mine'])) for r in legal)
print(f"  2x2  he/we  evolve-evolve {c[(True,True)]}  evolve-pass {c[(True,False)]}  "
      f"pass-evolve {c[(False,True)]}  pass-pass {c[(False,False)]}")
same_card = sum(1 for r in legal
                if evo_targets(r, 'his') and evo_targets(r, 'his') == evo_targets(r, 'mine'))
print(f"  when both evolve, SAME card pair: {same_card}/{c[(True,True)]}")

print("\n  by evolution step (his choice -> did we match exactly?):")
by = defaultdict(lambda: [0, 0])
for r in he_evo:
    for t in evo_targets(r, 'his'):
        by[t][0] += r["agree"]
        by[t][1] += 1
for k, v in sorted(by.items(), key=lambda kv: -kv[1][1]):
    print(f"    {k:34s} {v[0]:4d}/{v[1]:4d} = {v[0]/v[1]:5.1%}")

print("\n  TURN-OF-EVOLUTION per game (his turn vs the first turn we would have done it):")
his_turn, our_turn = defaultdict(dict), defaultdict(dict)
for r in sorted(rows, key=lambda r: (r["ep"], r["turn"])):
    if r["stype"] != 0:
        continue
    for t in evo_targets(r, 'his'):
        his_turn[t.split('->')[1]].setdefault(r["ep"], r["turn"])
    for t in evo_targets(r, 'mine'):
        our_turn[t.split('->')[1]].setdefault(r["ep"], r["turn"])
for card in ("Hydrapple ex", "Meganium", "Dipplin", "Bayleef"):
    h, o = his_turn.get(card, {}), our_turn.get(card, {})
    common = set(h) & set(o)
    if not common:
        print(f"    {card:14s} he:{len(h):3d} games   we:{len(o):3d} games   (no overlap)")
        continue
    dl = [o[e] - h[e] for e in common]
    print(f"    {card:14s} he:{len(h):3d} games   we:{len(o):3d} games   overlap {len(common)}   "
          f"same turn {sum(1 for x in dl if x==0)}/{len(dl)}   mean delta {np.mean(dl):+.2f} turns")

# ---------------------------------------------------------------- biggest real divergences
print("\n=== REAL (non-tie) divergences, ranked by bucket ===")
real = [r for r in rows if not r["agree"] and not r["tie"]]
print(f"{len(real)} real divergences out of {len(rows)} decisions ({len(real)/len(rows):.1%})")
c = Counter()
for r in real:
    c[(r["stype"], r["ctx"])] += 1
tot = Counter((r["stype"], r["ctx"]) for r in rows)
print("\n  by (select type, context):")
for k, v in c.most_common(12):
    print(f"    stype={k[0]} ctx={k[1]:2d}   {v:4d} real divergences   ({v/tot[k]:5.1%} of {tot[k]} such decisions)")

print("\n  MAIN, his exact action -> our exact action (top 25 real divergences):")
c = Counter()
for r in real:
    if r["stype"] == 0:
        c[("+".join(r["his"]), "+".join(r["mine"]))] += 1
for (a, b), n in c.most_common(25):
    print(f"    {a[:52]:52s} -> {b[:52]:52s} {n}")

print("\n  confidence on real divergences (softmax prob our net gave HIS move):")
p = np.array([r["p_his"] for r in real])
q = np.array([r["p_ours"] for r in real])
print(f"    p(his move) mean {p.mean():.3f} median {np.median(p):.3f}   "
      f"frac < 0.05: {float((p<0.05).mean()):.1%}   frac < 0.20: {float((p<0.20).mean()):.1%}")
print(f"    p(our move) mean {q.mean():.3f} median {np.median(q):.3f}")
pa = np.array([r["p_his"] for r in rows if r["agree"]])
print(f"    (for comparison, p(his move) when we AGREE: mean {pa.mean():.3f})")

print("\n  real divergences by turn bucket:")
for lo, hi in ((0, 2), (3, 5), (6, 8), (9, 12), (13, 99)):
    sub = [r for r in rows if lo <= r["turn"] <= hi]
    rr = [r for r in sub if not r["agree"] and not r["tie"]]
    if sub:
        print(f"    turn {lo:2d}-{hi:2d}: {len(rr):4d}/{len(sub):5d} = {len(rr)/len(sub):5.1%} real divergence")

print("\n  ATTACH (energy attachment) real divergences, his target -> ours:")
c = Counter()
for r in real:
    if 8 in r["his_types"]:
        c[("+".join(x for x in r["his"] if x.startswith("attach")),
           "+".join(r["mine"]))] += 1
for (a, b), n in c.most_common(12):
    print(f"    {a[:44]:44s} -> {b[:44]:44s} {n}")
