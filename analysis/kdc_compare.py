#!/usr/bin/env python3
"""Side-by-side of the two mechanism KPIs (+ tempo/comeback) for @kdcyberdude's real games and
our agents' played games, and how much of the polfix->kdcyberdude gap the fine-tune closed."""
import sys, os, json, random, statistics as st

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
random.seed(0)


def load(p):
    return json.load(open(os.path.join(ROOT, p)))


def rates(games, horizon=None):
    """All KPIs as horizon-free RATES + per-game counts. horizon caps the turn window so that
    kdcyberdude's naturally-ending games and our T25-adjudicated games span the same turns."""
    g = [m for m in games if m["max_turn"] >= 5]
    if horizon:
        g = [dict(m) for m in g]
    down = sum(m["down"] for m in g); elig = sum(m["elig"] for m in g)
    gym = sum(m["gym_up"] for m in g); own = sum(m["own_turns"] for m in g)
    att = sum(m["attacks"] for m in g)
    fg = [m["first_grimm"] for m in g if m["first_grimm"] is not None]
    cb = [m for m in g if m.get("first_prize") not in (None, -1) and m["first_prize"] != m["seat"]]
    cu = [0, 0]; cd = [0, 0]
    for m in g:
        cu[0] += m["cond"]["true" if "true" in m["cond"] else True][0]
        cu[1] += m["cond"]["true" if "true" in m["cond"] else True][1]
        cd[0] += m["cond"]["false" if "false" in m["cond"] else False][0]
        cd[1] += m["cond"]["false" if "false" in m["cond"] else False][1]
    return dict(
        n=len(g), wr=sum(m["won"] for m in g) / max(1, len(g)),
        turns=st.median([m["max_turn"] for m in g]),
        own_pg=own / max(1, len(g)),
        down_rate=down / max(1, elig), down_pg=down / max(1, len(g)),
        down_win=st.mean([m["down"] for m in g if m["won"]] or [0]),
        down_loss=st.mean([m["down"] for m in g if not m["won"]] or [0]),
        gym=gym / max(1, own),
        cond_up=cu[0] / max(1, cu[1]), cond_dn=cd[0] / max(1, cd[1]),
        cu=cu, cd=cd,
        first_g=st.median(fg) if fg else float("nan"),
        never_g=(len(g) - len(fg)) / max(1, len(g)),
        by8=st.mean([m["prizes_by8"] for m in g]),
        att_pt=att / max(1, own),
        cb=sum(m["won"] for m in cb) / max(1, len(cb)), cb_n=len(cb),
        raw=g,
    )


def boot(games, fn, B=2000):
    vals = []
    for _ in range(B):
        s = [games[random.randrange(len(games))] for _ in range(len(games))]
        vals.append(fn(s))
    vals.sort()
    return vals[int(.025 * B)], vals[int(.975 * B)]


def main():
    kdc_all = load("analysis/kdc_replay_kpi.json")
    for m in kdc_all:
        m["cond"] = {True: m["cond"]["true"], False: m["cond"]["false"]} if "true" in m["cond"] else m["cond"]
    MATCH = {"Alakazam", "Ogerpon"}
    kdc_m = [m for m in kdc_all if m["opp_arch"] in MATCH]

    cols = [("kdcyberdude ALL", rates(kdc_all)),
            ("kdc vs Ala/Oger", rates(kdc_m))]
    for nm, f in [("grimm_kdpol NEW", "analysis/kpi_play_grimm_kdpol.json"),
                  ("grimm_v12_polfix", "analysis/kpi_play_grimm_v12_polfix.json"),
                  ("grimm_v12_live", "analysis/kpi_play_grimm_v12_live.json")]:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            cols.append((nm, rates(load(f))))

    hdr = f"{'metric':<34}" + "".join(f"{c[0]:>18}" for c in cols)
    print(hdr); print("-" * len(hdr))
    rows = [
        ("games (>=5 turns)", "n", "{:>18d}"),
        ("win rate", "wr", "{:>17.1%} "),
        ("median game length (turns)", "turns", "{:>18.0f}"),
        ("own turns / game", "own_pg", "{:>18.2f}"),
        ("", None, None),
        ("1. DOWNTIME rate (per elig. turn)", "down_rate", "{:>18.3f}"),
        ("   downtime turns / game", "down_pg", "{:>18.2f}"),
        ("   ... in wins", "down_win", "{:>18.2f}"),
        ("   ... in losses", "down_loss", "{:>18.2f}"),
        ("", None, None),
        ("2. SPIKEMUTH GYM uptime", "gym", "{:>18.3f}"),
        ("   P(down next | Gym UP)", "cond_up", "{:>18.3f}"),
        ("   P(down next | Gym DOWN)", "cond_dn", "{:>18.3f}"),
        ("", None, None),
        ("3. first Grimmsnarl-ex turn (med)", "first_g", "{:>18.1f}"),
        ("   games it never lands", "never_g", "{:>17.1%} "),
        ("4. prizes by T8", "by8", "{:>18.2f}"),
        ("5. attacks / own turn", "att_pt", "{:>18.3f}"),
        ("6. comeback rate", "cb", "{:>17.1%} "),
        ("   (comeback games n)", "cb_n", "{:>18d}"),
    ]
    for label, key, fmt in rows:
        if key is None:
            print(); continue
        print(f"{label:<34}" + "".join(fmt.format(c[1][key]) for c in cols))

    # ---- gap analysis: polfix -> kdpol, target kdcyberdude ----
    K = dict(cols)["kdcyberdude ALL"]
    KM = dict(cols)["kdc vs Ala/Oger"]
    A = dict(cols)["grimm_kdpol NEW"]
    B = dict(cols)["grimm_v12_polfix"]
    print("\n=== GAP CLOSED by the fine-tune (control grimm_v12_polfix -> grimm_kdpol) ===")
    print(f"{'mechanism':<30}{'polfix':>10}{'kdpol':>10}{'kdc':>10}{'gap closed':>13}   95% CI on the move")
    for label, key, f_ in [("attacker-downtime rate", "down_rate", "{:.3f}"),
                           ("Spikemuth gym uptime", "gym", "{:.3f}"),
                           ("prizes by T8", "by8", "{:.2f}"),
                           ("attacks / own turn", "att_pt", "{:.3f}"),
                           ("comeback rate", "cb", "{:.3f}")]:
        b, a, k = B[key], A[key], K[key]
        gap = k - b
        closed = (a - b) / gap * 100 if abs(gap) > 1e-9 else float("nan")
        fn = {"down_rate": lambda g: sum(x["down"] for x in g) / max(1, sum(x["elig"] for x in g)),
              "gym": lambda g: sum(x["gym_up"] for x in g) / max(1, sum(x["own_turns"] for x in g)),
              "by8": lambda g: st.mean([x["prizes_by8"] for x in g]),
              "att_pt": lambda g: sum(x["attacks"] for x in g) / max(1, sum(x["own_turns"] for x in g)),
              "cb": lambda g: (lambda c: sum(x["won"] for x in c) / max(1, len(c)))(
                  [x for x in g if x.get("first_prize") not in (None, -1) and x["first_prize"] != x["seat"]])}[key]
        lo1, hi1 = boot(A["raw"], fn); lo2, hi2 = boot(B["raw"], fn)
        print(f"{label:<30}{f_.format(b):>10}{f_.format(a):>10}{f_.format(k):>10}"
              f"{closed:>12.0f}%   kdpol[{f_.format(lo1)},{f_.format(hi1)}] polfix[{f_.format(lo2)},{f_.format(hi2)}]")
    print(f"\n(matched-opponent teacher slice, kdc vs Alakazam/Ogerpon only, n={KM['n']}: "
          f"downtime {KM['down_rate']:.3f}, gym {KM['gym']:.3f}, by8 {KM['by8']:.2f}, "
          f"att/turn {KM['att_pt']:.3f}, comeback {KM['cb']:.1%})")


if __name__ == "__main__":
    main()
