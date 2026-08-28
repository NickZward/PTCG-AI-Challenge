#!/usr/bin/env python3
"""SLOT AUTOPSY — what is actually killing a ladder slot.

Usage: slot_autopsy.py <replay_dir> [our_team_name]

Reports: overall W/L, per-archetype cells, and for LOSSES the mechanism signals —
turn length, prize differential, our bench width, and the biggest single-turn hit we
took (the OHKO-threshold test that matters for a 210 HP single-attacker deck).
"""
import sys, os, json, glob, collections, csv

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
OURS = sys.argv[2] if len(sys.argv) > 2 else "Kilupy"

# ---- card id -> name -------------------------------------------------------
NAMES = {}
with open(os.path.join(ROOT, "pokemon-tcg-ai-battle/EN_Card_Data.csv")) as f:
    for r in csv.DictReader(f):
        cid = r["Card ID"].strip()
        if cid and cid not in NAMES:
            NAMES[cid] = r["Card Name"]

# ---- archetype signatures (checked in order; first hit wins) ---------------
SIGS = [
    ("M-Kangaskhan", ("Kangaskhan",)),
    ("M-Lucario",    ("Lucario",)),
    ("M-Starmie",    ("Starmie",)),
    ("Grimmsnarl",   ("Grimmsnarl", "Impidimp", "Morgrem")),
    ("Ogerpon",      ("Ogerpon",)),
    # Alakazam MUST be tested before Dudunsparce. Bare "Dunsparce" is a generic pivot
    # Basic played by many archetypes (notably Alakazam); matching it first relabelled
    # every Alakazam deck as Dudunsparce and invented a fake 32%-share matchup.
    ("Alakazam",     ("Alakazam", "Kadabra", "Abra")),
    ("M-Lopunny",    ("Lopunny",)),
    ("M-Froslass",   ("Froslass",)),
    ("Dudunsparce",  ("Dudunsparce",)),
    ("Dragapult",    ("Dragapult", "Drakloak", "Dreepy")),
    ("Crustle",      ("Crustle", "Dwebble")),
    ("Archaludon",   ("Archaludon", "Duraludon")),
    ("Dipplin",      ("Dipplin", "Applin")),
    ("Hydrapple",    ("Hydrapple",)),
    ("Meganium",     ("Meganium", "Bayleef", "Chikorita")),
    ("Garchomp",     ("Garchomp", "Gabite", "Gible")),
    ("Charizard",    ("Charizard", "Charmeleon")),
    ("Gholdengo",    ("Gholdengo", "Gimmighoul")),
]

def archetype(mon_names):
    for arch, keys in SIGS:
        for n in mon_names:
            if any(k in n for k in keys):
                return arch
    return "other"


def mons_of(pl):
    """Every Pokémon card id visible on a player's board + discard.
    Board slots and discard entries can legitimately be None — guard everything."""
    out = []
    for group in ("active", "bench"):
        for slot in (pl.get(group) or []):
            if not isinstance(slot, dict):
                continue
            out.append(slot.get("id"))
            for pe in (slot.get("preEvolution") or []):
                out.append(pe.get("id") if isinstance(pe, dict) else pe)
    for c in (pl.get("discard") or []):
        if isinstance(c, dict):
            out.append(c.get("id"))
    return [x for x in out if x is not None]


def analyse(path):
    d = json.load(open(path))
    teams = (d.get("info") or {}).get("TeamNames") or []
    if OURS not in teams:
        return None
    us = teams.index(OURS)
    opp = 1 - us
    rew = d.get("rewards") or [0, 0]
    won = (rew[us] or 0) > (rew[opp] or 0)

    steps = d.get("steps") or []
    opp_mon_ids, our_mon_ids = set(), set()
    last_turn = 0
    our_prizes_taken = opp_prizes_taken = 0
    bench_samples = []
    biggest_hit = 0            # largest single drop in our active's HP
    ohko_full_hp = 0           # times our active died from (near) full HP
    prev = {}                  # serial -> hp for our side
    our_serials = set()        # distinct bodies we ever got onto the board
    final_board = [0]          # our total Pokémon at the last LIVE step

    for st in steps:
        obs = (st[0].get("observation") or {})
        cur = obs.get("current") or {}
        P = cur.get("players")
        if not P or not P[0] or not P[1]:
            continue
        last_turn = max(last_turn, cur.get("turn") or 0)
        ours, theirs = P[us], P[opp]

        for cid in mons_of(theirs):
            opp_mon_ids.add(cid)
        for cid in mons_of(ours):
            our_mon_ids.add(cid)

        # prizes REMAINING -> taken. `prize` is None when hidden and the list is CLEARED
        # on terminal steps, so only read it while the game is still live.
        res = cur.get("result", -1)
        live = res in (None, -1)
        if live:
            pr_us, pr_op = ours.get("prize"), theirs.get("prize")
            if isinstance(pr_us, list) and pr_us:
                our_prizes_taken = max(our_prizes_taken, 6 - len(pr_us))
            if isinstance(pr_op, list) and pr_op:
                opp_prizes_taken = max(opp_prizes_taken, 6 - len(pr_op))
            # board width at the last live step = did we bench out?
            act = [s for s in (ours.get("active") or []) if isinstance(s, dict)]
            bn = [s for s in (ours.get("bench") or []) if isinstance(s, dict)]
            final_board[0] = len(act) + len(bn)
            for s in act + bn:
                if s.get("serial") is not None:
                    our_serials.add(s.get("serial"))
        bench_samples.append(len(ours.get("bench") or []))

        # track damage to our active
        for slot in (ours.get("active") or []):
            if not isinstance(slot, dict):
                continue
            ser, hp, mx = slot.get("serial"), slot.get("hp"), slot.get("maxHp")
            if ser is None or hp is None:
                continue
            if ser in prev:
                drop = prev[ser] - hp
                if drop > 0:
                    biggest_hit = max(biggest_hit, drop)
                    if prev[ser] == mx and hp <= 0:
                        ohko_full_hp += 1
            prev[ser] = hp

    opp_names = [NAMES.get(str(c), "") for c in opp_mon_ids]
    our_names = [NAMES.get(str(c), "") for c in our_mon_ids]
    return {
        "ep": os.path.basename(path).split("-")[1],
        "won": won,
        "opp": archetype(opp_names),
        "ours": archetype(our_names),
        "turn": last_turn,
        "pz_us": our_prizes_taken,
        "pz_op": opp_prizes_taken,
        "bench": (sum(bench_samples) / len(bench_samples)) if bench_samples else 0,
        "bench_min": min(bench_samples) if bench_samples else 0,
        "biggest_hit": biggest_hit,
        "ohko": ohko_full_hp,
        "bodies": len(our_serials),
        "final_board": final_board[0],
    }


def main():
    d = sys.argv[1]
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*-replay.json"))):
        try:
            r = analyse(p)
            if r:
                rows.append(r)
        except Exception as e:
            print(f"  !! {os.path.basename(p)}: {type(e).__name__} {e}")
    if not rows:
        print("no games found for team", OURS); return

    W = sum(1 for r in rows if r["won"]); L = len(rows) - W
    print(f"\n===== {d}  ({OURS}) =====")
    print(f"RECORD {W}-{L} = {100*W/len(rows):.1f}%   (n={len(rows)})")
    print(f"our deck detected: {collections.Counter(r['ours'] for r in rows).most_common()}")

    print("\n--- PER-ARCHETYPE CELLS (sorted by share) ---")
    cells = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        cells[r["opp"]][0 if r["won"] else 1] += 1
    for arch, (w, l) in sorted(cells.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        n = w + l
        print(f"  {arch:<14} {w}-{l}  = {100*w/n:5.1f}%   ({n} games, {100*n/len(rows):.0f}% of field)")

    losses = [r for r in rows if not r["won"]]
    wins = [r for r in rows if r["won"]]
    def avg(xs, k): return (sum(x[k] for x in xs) / len(xs)) if xs else 0
    print("\n--- MECHANISM: losses vs wins ---")
    print(f"  turns         L {avg(losses,'turn'):.1f}  vs W {avg(wins,'turn'):.1f}")
    print(f"  our prizes    L {avg(losses,'pz_us'):.2f}  vs W {avg(wins,'pz_us'):.2f}")
    print(f"  opp prizes    L {avg(losses,'pz_op'):.2f}  vs W {avg(wins,'pz_op'):.2f}")
    print(f"  our bench avg L {avg(losses,'bench'):.2f}  vs W {avg(wins,'bench'):.2f}")
    print(f"  bodies played L {avg(losses,'bodies'):.2f}  vs W {avg(wins,'bodies'):.2f}")
    print(f"  biggest hit   L {avg(losses,'biggest_hit'):.0f}  vs W {avg(wins,'biggest_hit'):.0f}")
    blowout = sum(1 for r in losses if r["pz_us"] <= 2)
    close = sum(1 for r in losses if r["pz_us"] >= 4)
    print(f"  BLOWOUT losses (we took <=2 prizes): {blowout}/{len(losses)}")
    print(f"  CLOSE   losses (we took >=4 prizes): {close}/{len(losses)}")
    bo = sum(1 for r in losses if r["final_board"] <= 1)
    print(f"  BENCH-OUT RISK (<=1 Pokémon left at last live step): {bo}/{len(losses)} losses")
    silent = sum(1 for r in losses if r["biggest_hit"] < 100)
    print(f"  ALL-OHKO losses (never observed a partial hit = one-shot every time): "
          f"{silent}/{len(losses)}")

    print("\n--- LOSS DETAIL ---")
    for r in sorted(losses, key=lambda r: r["turn"]):
        print(f"  ep{r['ep']}  vs {r['opp']:<13} T{r['turn']:<3} prizes {r['pz_us']}-{r['pz_op']}  "
              f"bench~{r['bench']:.1f}  bodies {r['bodies']}  endboard {r['final_board']}  "
              f"maxhit {r['biggest_hit']}")

if __name__ == "__main__":
    main()
