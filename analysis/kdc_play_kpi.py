#!/usr/bin/env python3
"""Play a Grimmsnarl agent against realistic field opponents and instrument the SAME KPIs the
replay scanner pulls out of @kdcyberdude's real games (analysis/kdc_kpi.py).

Isolation rules are load-bearing (see field_gauntlet.py): _purge_private() + _prime_path()
before EVERY load, _reset_budgets() before EVERY game. Without them both agents silently share
one 'mcts_agent'/'np_common' module and you measure the wrong agent.

USAGE: kdc_play_kpi.py <N_per_opponent> <agent_dir> [agent_dir2 ...]
"""
import sys, os, json
os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import round_robin as RR
import field_gauntlet as FG
from kdc_kpi import SideKPI
from cg import game as cggame

ALL_OPPS = {"Alakazam": "my-agent/alakazam_v20", "Ogerpon": "my-agent/oger_pol",
            # the mirror is 30% of kdcyberdude's real field and the archetype where his
            # mechanism numbers are most distinctive -- omitting it biases the comparison.
            "Grimmsnarl": "my-agent/grimm_v12_live"}
_want = os.environ.get("KPI_OPPS", "Alakazam,Ogerpon").split(",")
OPPS = [(k, ALL_OPPS[k]) for k in _want]
TAG = os.environ.get("KPI_TAG", "")
STOP = int(os.environ["PTCG_STOP"])


def play_instrumented(a0, d0, a1, d1, me_seat):
    """RR.play, with a SideKPI riding along on `me_seat`. Returns (result, SideKPI)."""
    obs, _ = cggame.battle_start(list(d0), list(d1))
    if obs is None:
        return -2, None
    k = None
    steps, last = 0, None
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            r = cur.get("result", -1)
            if r not in (None, -1):
                return r, k
            if obs.get("select") is None:
                return -2, k
            if k is None and cur.get("firstPlayer") in (0, 1):
                k = SideKPI(me_seat, cur["firstPlayer"])
            if k is not None:
                k.observe(cur, obs.get("logs"))
            turn = cur.get("turn", 0) or 0
            P = cur.get("players")
            if P and P[0] and P[1]:
                last = (6 - len(P[0].get("prize") or []), 6 - len(P[1].get("prize") or []),
                        P[0].get("deckCount") or 0, P[1].get("deckCount") or 0)
            if turn > STOP and last is not None:
                p0, p1, dd0, dd1 = last
                return ((0 if p0 > p1 else 1) if p0 != p1
                        else ((0 if dd0 > dd1 else 1) if dd0 != dd1 else -4)), k
            you = cur.get("yourIndex", 0)
            ag = a0 if you == 0 else a1
            w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                 "step": steps, "remainingOverageTime": 600,
                 "search_begin_input": obs.get("search_begin_input")}
            obs = cggame.battle_select([int(a) for a in ag(w)])
            steps += 1
        return -3, k
    finally:
        cggame.battle_finish()
        if k is not None:
            k.finish()


def run(cand_dir, n_per_opp):
    out = []
    n0 = "c_" + os.path.basename(cand_dir)
    for label, opp_dir in OPPS:
        n1 = "o_" + os.path.basename(opp_dir)
        FG._purge_private(); FG._prime_path(cand_dir)
        a0, d0 = RR.load(cand_dir, n0)
        FG._purge_private(); FG._prime_path(opp_dir)
        a1, d1 = RR.load(opp_dir, n1)
        w = l = 0
        for i in range(n_per_opp):
            FG._reset_budgets(n0, n1)
            me = 0 if i % 2 == 0 else 1
            if me == 0:
                r, k = play_instrumented(a0, d0, a1, d1, 0)
            else:
                r, k = play_instrumented(a1, d1, a0, d0, 1)
            if k is None:
                continue
            if r == me: w += 1
            elif r == (1 - me): l += 1
            m = k.metrics(r == me)
            m.update(opp=label, seat=me, first_prize=k.first_prize_taker, result=r)
            out.append(m)
            if (i + 1) % 10 == 0:
                print(f"    {label}: {i+1}/{n_per_opp} ({w}-{l})", flush=True)
        print(f"  vs {label:<10} {w}-{l}", flush=True)
    return out


def main():
    n = int(sys.argv[1]); cands = sys.argv[2:]
    for c in cands:
        print(f"===== {c} =====", flush=True)
        out = run(c, n)
        p = os.path.join(ROOT, f"analysis/kpi_play_{os.path.basename(c)}{TAG}.json")
        json.dump(out, open(p, "w"))
        print(f"  -> {p}  ({len(out)} games)", flush=True)


if __name__ == "__main__":
    main()
