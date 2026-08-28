#!/usr/bin/env python3
"""Run the shared KPI extractor over @kdcyberdude's 135 real ladder replays."""
import sys, os, csv, json, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kdc_kpi import scan_replay

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
ME = "@kdcyberdude"
HORIZON = int(os.environ.get("KPI_HORIZON", "0")) or None


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "dump_index_kdc.csv"))))
    out = []
    for r in rows:
        seat = 0 if r["p0"] == ME else 1
        assert r["p0"] == ME or r["p1"] == ME, r
        try:
            k, winner, mt = scan_replay(r["path"], seat)
        except Exception as e:
            print(f"  ERR {r['path']}: {e}", file=sys.stderr)
            continue
        if k is None or winner is None:
            continue
        m = k.metrics(winner == seat, horizon=HORIZON)
        m["episode"] = r["episode"]
        m["opp_arch"] = r["a1"] if seat == 0 else r["a0"]
        m["first_prize"] = k.first_prize_taker
        m["seat"] = seat
        m["idx_turns"] = int(r["turns"])
        out.append(m)
    json.dump(out, open(os.path.join(ROOT, "analysis/kdc_replay_kpi.json"), "w"))
    report("kdcyberdude (REAL ladder replays)", out)


def report(label, out, min_turns=5):
    full = [m for m in out if m["max_turn"] >= min_turns]
    print(f"\n===== {label} =====")
    print(f"games={len(out)}  (usable, >={min_turns} turns: {len(full)})  "
          f"record={sum(m['won'] for m in out)}-{sum(not m['won'] for m in out)}")
    print(f"median game length: {statistics.median([m['max_turn'] for m in full])} turns "
          f"| own turns/game {statistics.mean([m['own_turns'] for m in full]):.1f}")
    W = [m for m in full if m["won"]]
    L = [m for m in full if not m["won"]]

    def mean(xs):
        return statistics.mean(xs) if xs else float("nan")

    tot_down = sum(m["down"] for m in full); tot_elig = sum(m["elig"] for m in full)
    print(f"\n1. ATTACKER DOWNTIME (own turns t>=3, no Marnie's Grimmsnarl ex on board)")
    print(f"   rate = {tot_down}/{tot_elig} = {tot_down/max(1,tot_elig):.3f} of eligible own turns")
    print(f"   per game: all {mean([m['down'] for m in full]):.2f} | "
          f"wins {mean([m['down'] for m in W]):.2f} (n={len(W)}) | "
          f"losses {mean([m['down'] for m in L]):.2f} (n={len(L)})")
    hi = [m for m in full if m["down"] >= 4]
    print(f"   games with >=4 downtime turns: {len(hi)}; of those, losses = "
          f"{sum(not m['won'] for m in hi)}/{len(hi)}")

    tg = sum(m["gym_up"] for m in full); to = sum(m["own_turns"] for m in full)
    print(f"\n2. SPIKEMUTH GYM UPTIME (own turns with Spikemuth Gym in the stadium slot)")
    print(f"   {tg}/{to} = {tg/max(1,to):.3f}   | wins {mean([m['gym_up']/max(1,m['own_turns']) for m in W]):.3f}"
          f"  losses {mean([m['gym_up']/max(1,m['own_turns']) for m in L]):.3f}")
    cu = [0, 0]; cd = [0, 0]
    for m in full:
        cu[0] += m["cond"][True][0]; cu[1] += m["cond"][True][1]
        cd[0] += m["cond"][False][0]; cd[1] += m["cond"][False][1]
    print(f"   P(next own turn attacker-down | Gym UP)   = {cu[0]}/{cu[1]} = {cu[0]/max(1,cu[1]):.3f}")
    print(f"   P(next own turn attacker-down | Gym DOWN) = {cd[0]}/{cd[1]} = {cd[0]/max(1,cd[1]):.3f}")

    fg = [m["first_grimm"] for m in full if m["first_grimm"] is not None]
    print(f"\n3. FIRST Marnie's Grimmsnarl ex turn: median {statistics.median(fg):.1f} "
          f"mean {mean(fg):.2f}  (never played in {len(full)-len(fg)}/{len(full)} games)")
    print(f"4. TEMPO prizes by T8: {mean([m['prizes_by8'] for m in full]):.2f} "
          f"| wins {mean([m['prizes_by8'] for m in W]):.2f}  losses {mean([m['prizes_by8'] for m in L]):.2f}")
    print(f"5. ATTACKS per own turn: {sum(m['attacks'] for m in full)/max(1,to):.3f}")
    seat_of = {m["episode"]: m["seat"] for m in full}
    cb = [m for m in full if m["first_prize"] not in (None, -1) and m["first_prize"] != m["seat"]]
    print(f"6. COMEBACK (won after conceding 1st prize): {sum(m['won'] for m in cb)}/{len(cb)} = "
          f"{sum(m['won'] for m in cb)/max(1,len(cb)):.3f}   "
          f"[unattributable first prize in {sum(1 for m in full if m['first_prize']==-1)} games]")
    fpm = [m for m in full if m["first_prize"] == m["seat"]]
    print(f"   (took 1st prize: {sum(m['won'] for m in fpm)}/{len(fpm)} = "
          f"{sum(m['won'] for m in fpm)/max(1,len(fpm)):.3f})")


if __name__ == "__main__":
    main()
