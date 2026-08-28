#!/usr/bin/env python3
"""VERIFY-FIX-FIRES probe for the Ogerpon bench-out fix.

The field gauntlet says the extra bodies did not buy wins. Before concluding the fix is
worthless we must check whether it FIRES: does the deck change actually widen the bench and
stop us running out of Pokemon? If bench-outs drop but the win rate does not move, the lab
opponents are not punishing bench-out and the ladder is the only valid arbiter. If bench-outs
do NOT drop, the fix genuinely does nothing and we stop.

Usage: benchout_probe.py <N> <opp_dir> <agent_dir> [agent_dir2 ...]
"""
import sys, os
os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import round_robin as RR
from cg import game as cggame


def probe(cand_dir, opp_dir, n):
    a0, d0 = RR.load(cand_dir, "c_" + os.path.basename(cand_dir))
    a1, d1 = RR.load(opp_dir, "o_" + os.path.basename(opp_dir))
    stats = {"games": 0, "wins": 0, "benchouts": 0, "bench_sum": 0.0,
             "bench_obs": 0, "min1_end": 0, "bodies_sum": 0}
    for i in range(n):
        first = (i % 2 == 0)
        A, DA, B, DB = (a0, d0, a1, d1) if first else (a1, d1, a0, d0)
        me = 0 if first else 1
        obs, _ = cggame.battle_start(list(DA), list(DB))
        if obs is None:
            continue
        steps, last_board, serials, result = 0, None, set(), -1
        try:
            while steps < 4000:
                cur = (obs or {}).get("current") or {}
                r = cur.get("result", -1)
                if r not in (None, -1):
                    result = r
                    break
                if obs.get("select") is None:
                    break
                P = cur.get("players")
                if P and P[me]:
                    mine = P[me]
                    act = [s for s in (mine.get("active") or []) if isinstance(s, dict)]
                    bn = [s for s in (mine.get("bench") or []) if isinstance(s, dict)]
                    stats["bench_sum"] += len(bn); stats["bench_obs"] += 1
                    last_board = len(act) + len(bn)
                    for s in act + bn:
                        if s.get("serial") is not None:
                            serials.add(s.get("serial"))
                you = cur.get("yourIndex", 0)
                ag = A if you == 0 else B
                w = {"current": cur, "select": obs.get("select"), "logs": obs.get("logs", []),
                     "step": steps, "remainingOverageTime": 600,
                     "search_begin_input": obs.get("search_begin_input")}
                obs = cggame.battle_select([int(a) for a in ag(w)])
                steps += 1
                if obs is None:
                    break
        finally:
            cggame.battle_finish()
        stats["games"] += 1
        if result == me:
            stats["wins"] += 1
        if last_board is not None:
            if last_board == 0:
                stats["benchouts"] += 1
            if last_board <= 1:
                stats["min1_end"] += 1
        stats["bodies_sum"] += len(serials)
    return stats


def main():
    n = int(sys.argv[1]); opp = sys.argv[2]; cands = sys.argv[3:]
    print(f"bench-out probe: N={n} vs {opp}\n")
    print(f"{'agent':<24}{'games':>6}{'benchOUT(0)':>13}{'end<=1':>9}"
          f"{'meanBench':>11}{'bodies':>8}")
    for c in cands:
        s = probe(c, opp, n)
        g = max(s["games"], 1)
        print(f"{os.path.basename(c):<24}{s['games']:>6}"
              f"{s['benchouts']:>8} ({100*s['benchouts']/g:4.0f}%)"
              f"{s['min1_end']:>9}"
              f"{s['bench_sum']/max(s['bench_obs'],1):>11.2f}"
              f"{s['bodies_sum']/g:>8.2f}")


if __name__ == "__main__":
    main()
