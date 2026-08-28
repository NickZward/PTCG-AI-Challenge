#!/usr/bin/env python3
"""Deeper divergence mining: (a) is a MAIN divergence a real plan difference or just move ORDER
(transposition) -- did he play OUR move later in the SAME turn? (b) damage-counter targeting,
(c) the shared CARD:ATTACH_TO blind spot."""
import json, csv
from collections import defaultdict, Counter

SP = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/"
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/"
TRAIN = set(r['episode'] for r in csv.DictReader(open(ROOT + 'grimm_teachers_manifest.csv'))
            if r['player'] == '@kdcyberdude')
A = [json.loads(l) for l in open(SP + "kdpol.jsonl")]
for r in A:
    r["held"] = r["f"].split(".")[0] not in TRAIN

# ---------- (a) transposition test on MAIN:MAIN ----------
turns = defaultdict(list)
for i, r in enumerate(A):
    if r["stype"] == 0:
        turns[(r["f"], r["turn"])].append(i)
for k in turns:
    turns[k].sort(key=lambda i: A[i]["t"])

def report(sel, name):
    div = [i for i in range(len(A)) if A[i]["stype"] == 0 and sel(A[i])
           and A[i]["hsig"] >= 0 and A[i]["tsig"] != A[i]["hsig"]]
    trans = same_card = 0
    for i in div:
        seq = turns[(A[i]["f"], A[i]["turn"])]
        later = [A[j]["hlab"] for j in seq if A[j]["t"] > A[i]["t"]]
        if A[i]["tlab"] in later:
            trans += 1
        if A[i]["tlab"].split(":")[0] == A[i]["hlab"].split(":")[0] and \
           A[i]["tlab"].split(":")[-1].split("@")[0] == A[i]["hlab"].split(":")[-1].split("@")[0]:
            same_card += 1
    n_main = sum(1 for r in A if r["stype"] == 0 and sel(r))
    print("\n%s  MAIN:MAIN decisions=%d, real divergences=%d (%.1f%%)" %
          (name, n_main, len(div), 100.0 * len(div) / max(1, n_main)))
    print("   of those, TRANSPOSITIONS (he made OUR move later in the same turn): %d = %.1f%%"
          % (trans, 100.0 * trans / max(1, len(div))))
    print("   -> genuine plan differences: %d = %.1f%% of all his MAIN decisions"
          % (len(div) - trans, 100.0 * (len(div) - trans) / max(1, n_main)))
    # what does he do that we skip, and vice versa, on the non-transposition cases
    c_his, c_our = Counter(), Counter()
    for i in div:
        seq = turns[(A[i]["f"], A[i]["turn"])]
        later = [A[j]["hlab"] for j in seq if A[j]["t"] > A[i]["t"]]
        if A[i]["tlab"] in later:
            continue
        c_his[A[i]["hlab"][:40]] += 1
        c_our[A[i]["tlab"][:40]] += 1
    print("   NON-transposition: HIS move (top 10)              | OUR move (top 10)")
    hh, oo = c_his.most_common(10), c_our.most_common(10)
    for j in range(10):
        a = "%5d %-40s" % (hh[j][1], hh[j][0]) if j < len(hh) else " " * 46
        b = "%5d %-40s" % (oo[j][1], oo[j][0]) if j < len(oo) else ""
        print("      %s | %s" % (a, b))

report(lambda r: r["held"], "HELD-OUT (his 45 losses)")
report(lambda r: True, "ALL 135 games")

# ---------- (b) damage-counter / heal targeting ----------
print("\n" + "=" * 100)
print("DAMAGE-COUNTER FAMILY (Munkidori Adrena-Brain + Marnie's Grimmsnarl ex), HELD-OUT")
for ctx, nm in ((13, "DMG_COUNTER (put counters on)"), (16, "RM_DMG_CTR (take counters off)"),
                (15, "DAMAGE (deal damage to)")):
    rs = [r for r in A if r["sctx"] == ctx and r["held"] and r["hsig"] >= 0]
    div = [r for r in rs if r["tsig"] != r["hsig"]]
    def slot(l):
        if "(opp)" in l: return "OPP-" + ("ACTIVE" if "ACTIVE" in l else "BENCH" if "BENCH" in l else "?")
        return "OUR-" + ("ACTIVE" if "ACTIVE" in l else "BENCH" if "BENCH" in l else "?")
    c = Counter("he=%-11s -> we=%-11s" % (slot(r["hlab"]), slot(r["tlab"])) for r in div)
    print("  %-30s n=%4d divergences=%4d (%.0f%%)" % (nm, len(rs), len(div),
          100.0 * len(div) / max(1, len(rs))))
    for k, v in c.most_common(6):
        print("        %4d  %s" % (v, k))

# ---------- (c) ATTACH_TO blind spot ----------
print("\n" + "=" * 100)
print("CARD:ATTACH_TO -- both nets score ~4%; is it a real disagreement or an enumeration artefact?")
rs = [r for r in A if r["sctx"] == 22]
print("  n=%d  his move representable: %d  mean ncand=%.1f  mean nopt=%.1f  min/maxCount=%s" %
      (len(rs), sum(1 for r in rs if r["hidx"] >= 0), sum(r["ncand"] for r in rs) / len(rs),
       sum(r["nopt"] for r in rs) / len(rs), Counter((r["mn"], r["mx"]) for r in rs).most_common(3)))
print("  his index distribution :", Counter(r["hidx"] for r in rs).most_common(6))
print("  our pick distribution  :", Counter(r["top"] for r in rs).most_common(6))
print("  his play  :", Counter(r["hlab"][:44] for r in rs).most_common(5))
print("  our play  :", Counter(r["tlab"][:44] for r in rs).most_common(5))

# ---------- (d) attack timing ----------
print("\n" + "=" * 100)
print("ATTACK TIMING (MAIN), HELD-OUT")
rs = [r for r in A if r["stype"] == 0 and r["held"] and r["hsig"] >= 0]
he_att_we_not = sum(1 for r in rs if r["hlab"].startswith("ATTACK") and not r["tlab"].startswith("ATTACK") and r["tsig"] != r["hsig"])
we_att_he_not = sum(1 for r in rs if r["tlab"].startswith("ATTACK") and not r["hlab"].startswith("ATTACK") and r["tsig"] != r["hsig"])
he_end_we_not = sum(1 for r in rs if r["hlab"] == "END" and r["tlab"] != "END" and r["tsig"] != r["hsig"])
we_end_he_not = sum(1 for r in rs if r["tlab"] == "END" and r["hlab"] != "END" and r["tsig"] != r["hsig"])
print("  he ATTACKS, we do something else : %d" % he_att_we_not)
print("  we ATTACK,  he does something else: %d" % we_att_he_not)
print("  he ENDS turn, we keep playing     : %d" % he_end_we_not)
print("  we END turn, he keeps playing     : %d" % we_end_he_not)
