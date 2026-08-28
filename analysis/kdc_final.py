#!/usr/bin/env python3
"""FINAL like-for-like comparison: @kdcyberdude's real games vs our agents' played games,
matched ARCHETYPE BY ARCHETYPE (his overall averages are dominated by the mirror, which is 30%
of his field and where his numbers are most extreme -- aggregating across a different opponent
mix is the single easiest way to get a wrong answer here)."""
import sys, os, json, random, statistics as st
from collections import defaultdict

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
random.seed(7)
# true meta shares (field_gauntlet.py), renormalised over the three archetypes we can match
SHARE = {"Grimmsnarl": 30.7, "Alakazam": 17.8, "Ogerpon": 8.8}


def L(p):
    p = os.path.join(ROOT, p)
    return json.load(open(p)) if os.path.exists(p) else []


def norm(m):
    c = m["cond"]
    if "true" in c:
        m["cond"] = {True: c["true"], False: c["false"]}
    return m


def agg(g):
    if not g:
        return None
    own = sum(x["own_turns"] for x in g)
    elig = sum(x["elig"] for x in g)
    cb = [x for x in g if x.get("first_prize") not in (None, -1) and x["first_prize"] != x["seat"]]
    cu = [sum(x["cond"][True][i] for x in g) for i in (0, 1)]
    cd = [sum(x["cond"][False][i] for x in g) for i in (0, 1)]
    return dict(
        n=len(g), wr=sum(x["won"] for x in g) / len(g),
        medT=st.median([x["max_turn"] for x in g]), own_pg=own / len(g),
        down=sum(x["down"] for x in g) / max(1, elig),
        down_pg=sum(x["down"] for x in g) / len(g),
        gym=sum(x["gym_up"] for x in g) / max(1, own),
        never=sum(1 for x in g if x["first_grimm"] is None) / len(g),
        firstg=st.median([x["first_grimm"] for x in g if x["first_grimm"] is not None] or [0]),
        by8=st.mean([x["prizes_by8"] for x in g]),
        att=sum(x["attacks"] for x in g) / max(1, own),
        cb=sum(x["won"] for x in cb) / max(1, len(cb)), cb_n=len(cb),
        cond_up=cu[0] / max(1, cu[1]), cond_dn=cd[0] / max(1, cd[1]),
        raw=g,
    )


METRICS = [("down", "downtime rate", "{:.3f}"), ("gym", "Spikemuth uptime", "{:.3f}"),
           ("never", "never lands Grimm-ex", "{:.1%}"), ("by8", "prizes by T8", "{:.2f}"),
           ("att", "attacks / own turn", "{:.3f}"), ("cb", "comeback rate", "{:.1%}")]
EST = {"down": lambda g: sum(x["down"] for x in g) / max(1, sum(x["elig"] for x in g)),
       "gym": lambda g: sum(x["gym_up"] for x in g) / max(1, sum(x["own_turns"] for x in g)),
       "never": lambda g: sum(1 for x in g if x["first_grimm"] is None) / max(1, len(g)),
       "by8": lambda g: st.mean([x["prizes_by8"] for x in g]) if g else 0,
       "att": lambda g: sum(x["attacks"] for x in g) / max(1, sum(x["own_turns"] for x in g)),
       "cb": lambda g: (lambda c: sum(x["won"] for x in c) / max(1, len(c)))(
           [x for x in g if x.get("first_prize") not in (None, -1) and x["first_prize"] != x["seat"]])}


def boot(g, key, B=2000):
    v = sorted(EST[key]([g[random.randrange(len(g))] for _ in range(len(g))]) for _ in range(B))
    return v[int(.025 * B)], v[int(.975 * B)]


def main():
    kdc = [norm(m) for m in L("analysis/kdc_replay_kpi.json") if m["max_turn"] >= 5]
    K = defaultdict(list)
    for m in kdc:
        K[m["opp_arch"]].append(m)

    ours = {}
    for nm, files in [("kdpol", ["analysis/kpi_play_grimm_kdpol.json",
                                 "analysis/kpi_play_grimm_kdpol_mirror.json"]),
                      ("polfix", ["analysis/kpi_play_grimm_v12_polfix.json",
                                  "analysis/kpi_play_grimm_v12_polfix_mirror.json"]),
                      ("v12live", ["analysis/kpi_play_grimm_v12_live.json"])]:
        g = [norm(m) for f in files for m in L(f) if m["max_turn"] >= 5]
        if g:
            d = defaultdict(list)
            for m in g:
                d[m["opp"]].append(m)
            ours[nm] = d

    arch = [a for a in ("Grimmsnarl", "Alakazam", "Ogerpon") if K.get(a)]
    KW = defaultdict(list)
    for a in arch:
        KW[a] = [m for m in K[a] if m["won"]]
    names = ["kdcyberdude", "kdc_wins"] + list(ours)
    print("=" * 108)
    print("PER-ARCHETYPE, like-for-like (his real opponents vs our sparring agents of the same archetype)")
    print("=" * 108)
    for a in arch:
        print(f"\n--- vs {a}  (meta share {SHARE[a]}%) ---")
        # the fine-tune's teacher manifest is exactly kdcyberdude's 90 WINS, so his winning
        # behaviour is the thing it was actually asked to copy; his losses are the held-out set.
        rowsrc = ([("kdc ALL", agg(K[a])),
                   ("kdc WINS*", agg([m for m in K[a] if m["won"]])),
                   ("kdc losses", agg([m for m in K[a] if not m["won"]]))]
                  + [(n, agg(ours[n].get(a, []))) for n in ours])
        rowsrc = [(n, v) for n, v in rowsrc if v]
        print(f"  {'':<14}{'n':>5}{'WR':>7}{'medT':>6}{'own/g':>7}"
              + "".join(f"{lab:>22}" for _, lab, _ in METRICS))
        for n, v in rowsrc:
            print(f"  {n:<14}{v['n']:>5}{v['wr']:>7.1%}{v['medT']:>6.0f}{v['own_pg']:>7.2f}"
                  + "".join(f"{f.format(v[k]):>22}" for k, _, f in METRICS))

    # ---- meta-weighted aggregate over the matched archetypes ----
    print("\n" + "=" * 108)
    print("META-WEIGHTED over the matched archetypes "
          f"({'+'.join(arch)} = {sum(SHARE[a] for a in arch):.1f}% of the true meta, renormalised)")
    print("=" * 108)
    tot = sum(SHARE[a] for a in arch)

    def wavg(getter):
        return sum(SHARE[a] * getter(a) for a in arch) / tot

    print(f"  {'':<14}" + "".join(f"{lab:>22}" for _, lab, _ in METRICS))
    W = {}
    for n in names:
        src = ({"kdcyberdude": lambda a: K[a], "kdc_wins": lambda a: KW[a]}.get(n)
               or (lambda a, n=n: ours[n].get(a, [])))
        if any(not src(a) for a in arch):
            continue
        W[n] = {k: wavg(lambda a: EST[k](src(a))) for k, _, _ in METRICS}
        print(f"  {n:<14}" + "".join(f"{f.format(W[n][k]):>22}" for k, _, f in METRICS))

    if "kdpol" in W and "polfix" in W:
        print("\n" + "=" * 108)
        print("GAP CLOSED toward @kdcyberdude  (control grimm_v12_polfix -> grimm_kdpol)")
        print("=" * 108)
        print(f"  {'mechanism':<24}{'polfix':>9}{'kdpol':>9}{'kdc':>9}{'gap':>9}{'moved':>9}"
              f"{'closed':>9}   95% CI (kdpol / polfix), meta-weighted")
        for k, lab, f in METRICS:
            b, a, kk = W["polfix"][k], W["kdpol"][k], W["kdcyberdude"][k]
            gap = kk - b
            moved = a - b
            closed = moved / gap * 100 if abs(gap) > 1e-9 else float("nan")
            ci = []
            for who in ("kdpol", "polfix"):
                lo = wavg(lambda x: boot(ours[who][x], k)[0])
                hi = wavg(lambda x: boot(ours[who][x], k)[1])
                ci.append(f"[{f.format(lo)},{f.format(hi)}]")
            print(f"  {lab:<24}{f.format(b):>9}{f.format(a):>9}{f.format(kk):>9}"
                  f"{f.format(gap):>9}{f.format(moved):>9}{closed:>8.0f}%   {ci[0]} / {ci[1]}")


if __name__ == "__main__":
    main()
