#!/usr/bin/env python3
"""FIELD-WEIGHTED GAUNTLET for the Ogerpon slot.

Why this exists: our lab gate ranks agents against ONE opponent (our own champion), and it
misranked M-Lucario by 32 points and told us a 4-body Ogerpon deck was fine while the real
field bench-outs it in 11 of 14 losses. This harness instead weights each matchup by its
OBSERVED share of the field the Ogerpon slot actually faced (fresh ladder drop, n=22).

Observed shares (CORRECTED 2026-08-10 after an archetype-classifier bug): the "Dudunsparce
32%" cell was fake - bare "Dunsparce" is a generic pivot Basic and was matching Alakazam
decks first. Real shares: other 27% | ALAKAZAM 23% (our worst real cell, 1-4 = 20%) |
Grimmsnarl 9% | M-Starmie 9% | M-Lucario 9% | M-Lopunny 9% | Ogerpon 5% | Crustle 5% |
M-Froslass 5%.  We can only model archetypes we have sparring agents for; renormalised below.

Usage: field_gauntlet_oger.py <N_per_opponent> <agent_dir> [agent_dir2 ...]
Run on an IDLE machine (ps aux | grep "[p]ython3"), because grimm_v12_live is wall-clock
guarded and degrades under CPU load.
"""
import sys, os
os.environ.setdefault("PTCG_STOP", "25")          # must be set BEFORE round_robin import
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import round_robin as RR

# (label, agent dir, observed field share %)
FIELD = [
    ("Alakazam",    "my-agent/alakazam_v20",   23.0),   # our worst REAL cell: 1-4 = 20%
    ("Grimmsnarl",  "my-agent/grimm_v12_live",  9.0),
    ("M-Lucario",   "my-agent/mluc_v1",         9.0),
    ("Ogerpon",     "my-agent/ogerpon_v1",      5.0),
    ("Crustle",     "my-agent/bc_crustle",      5.0),
]
LOAD_SENSITIVE = {"my-agent/grimm_v12_live"}      # net+search agents; never gate under load


def duel(cand_dir, opp_dir, n):
    """N games, seats alternating. Returns (wins, losses, draws) from cand's view."""
    a0, d0 = RR.load(cand_dir, "cand_" + os.path.basename(cand_dir))
    a1, d1 = RR.load(opp_dir, "opp_" + os.path.basename(opp_dir))
    w = l = dr = 0
    for i in range(n):
        if i % 2 == 0:
            r = RR.play(a0, d0, a1, d1)
            mine, theirs = 0, 1
        else:
            r = RR.play(a1, d1, a0, d0)
            mine, theirs = 1, 0
        if r == mine:
            w += 1
        elif r == theirs:
            l += 1
        else:
            dr += 1
    return w, l, dr


def main():
    n = int(sys.argv[1])
    cands = sys.argv[2:]
    if not cands:
        print(__doc__); return

    total_share = sum(s for _, _, s in FIELD)
    print(f"Field-weighted gauntlet: N={n}/opponent, {len(FIELD)} archetypes "
          f"covering {total_share:.0f}% of observed field (renormalised)\n")

    results = {}
    for cand in cands:
        print(f"===== {cand} =====")
        weighted = 0.0
        rows = []
        for label, opp, share in FIELD:
            if os.path.abspath(cand) == os.path.abspath(os.path.join(ROOT, opp)):
                continue                                    # don't play the mirror vs itself
            w, l, dr = duel(cand, opp, n)
            played = w + l
            wr = (100.0 * w / played) if played else 0.0
            weighted += wr * share
            rows.append((label, w, l, dr, wr, share))
            flag = "  <-- LOAD-SENSITIVE (idle machine required)" if opp in LOAD_SENSITIVE else ""
            print(f"  vs {label:<13} {w:>3}-{l:<3} = {wr:5.1f}%   (field {share:.0f}%){flag}")
        used = sum(r[5] for r in rows)
        score = weighted / used if used else 0.0
        results[cand] = score
        print(f"  FIELD-WEIGHTED SCORE: {score:.1f}%\n")

    if len(results) > 1:
        print("=== RANKING (field-weighted) ===")
        for k, v in sorted(results.items(), key=lambda kv: -kv[1]):
            print(f"  {v:5.1f}%  {k}")


if __name__ == "__main__":
    main()
