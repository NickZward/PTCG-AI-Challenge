#!/usr/bin/env python3
"""Are the two mechanisms actually PREDICTIVE, for him and for us? The earlier study claimed
>=4 attacker-down turns predicted a loss 8/8 for our champion. Test it on 133 real expert games
and on our agents' played games, and check the Gym -> downtime link both sides."""
import os, sys, json, statistics as st

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"


def L(p):
    p = os.path.join(ROOT, p)
    return json.load(open(p)) if os.path.exists(p) else []


def norm(m):
    c = m["cond"]
    if "true" in c:
        m["cond"] = {True: c["true"], False: c["false"]}
    return m


def block(name, g):
    g = [norm(m) for m in g if m["max_turn"] >= 5]
    if not g:
        return
    print(f"\n--- {name}  (n={len(g)}, WR {sum(x['won'] for x in g)/len(g):.1%}) ---")
    print(f"  {'downtime turns':<18}{'n':>6}{'win rate':>11}")
    for lo, hi, lab in [(0, 0, "0"), (1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 99, ">=4")]:
        s = [x for x in g if lo <= x["down"] <= hi]
        if s:
            print(f"  {lab:<18}{len(s):>6}{sum(x['won'] for x in s)/len(s):>11.1%}")
    # gym uptime tertiles
    ups = sorted(x["gym_up"] / max(1, x["own_turns"]) for x in g)
    q1, q2 = ups[len(ups) // 3], ups[2 * len(ups) // 3]
    print(f"  {'gym uptime':<18}{'n':>6}{'win rate':>11}{'mean downtime':>15}")
    for lab, f in [(f"low  (<={q1:.2f})", lambda u: u <= q1),
                   (f"mid", lambda u: q1 < u <= q2),
                   (f"high (>{q2:.2f})", lambda u: u > q2)]:
        s = [x for x in g if f(x["gym_up"] / max(1, x["own_turns"]))]
        if s:
            print(f"  {lab:<18}{len(s):>6}{sum(x['won'] for x in s)/len(s):>11.1%}"
                  f"{st.mean([x['down'] for x in s]):>15.2f}")
    cu = [sum(x["cond"][True][i] for x in g) for i in (0, 1)]
    cd = [sum(x["cond"][False][i] for x in g) for i in (0, 1)]
    print(f"  P(next own turn attacker-down | Gym UP)   {cu[0]}/{cu[1]} = {cu[0]/max(1,cu[1]):.3f}")
    print(f"  P(next own turn attacker-down | Gym DOWN) {cd[0]}/{cd[1]} = {cd[0]/max(1,cd[1]):.3f}")


def main():
    block("@kdcyberdude, real ladder", L("analysis/kdc_replay_kpi.json"))
    for nm, fs in [("grimm_kdpol (NEW)", ["analysis/kpi_play_grimm_kdpol.json",
                                          "analysis/kpi_play_grimm_kdpol_mirror.json"]),
                   ("grimm_v12_polfix (CONTROL)", ["analysis/kpi_play_grimm_v12_polfix.json",
                                                   "analysis/kpi_play_grimm_v12_polfix_mirror.json"]),
                   ("grimm_v12_live (champion)", ["analysis/kpi_play_grimm_v12_live.json"])]:
        block(nm, [m for f in fs for m in L(f)])


if __name__ == "__main__":
    main()
