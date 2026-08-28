#!/usr/bin/env python3
"""GENERAL field-weighted gauntlet — weights every matchup by its TRUE share of the live meta.

Shares measured from dump_index_0810.csv: 9,368 unique games / 18,700+ sides indexed 2026-08-11.
  Grimmsnarl 30.7% (WR 46.7%) | Alakazam 17.8% (50.5%) | M-Lopunny 12.1% (51.9%)
  Ogerpon 8.8% (50.6%) | M-Kangaskhan 8.6% (48.9%) | Dragapult 7.5% (59.3%)
  M-Lucario 3.8% (55.1%) | Hydrapple 3.4% (55.2%) | Crustle 1.2% (46.4%)
We can only model archetypes we hold a sparring agent for; those are renormalised.

Supersedes field_gauntlet_oger.py, which used the shares of the *Ogerpon slot's* observed field
(Alakazam 23%) rather than the true meta — fine for judging that one slot, wrong in general.

USAGE: field_gauntlet.py <N_per_opponent> <agent_dir> [agent_dir2 ...]

RUN IT LIKE THIS OR THE NUMBERS ARE MEANINGLESS:
  env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
      KMP_DUPLICATE_LIB_OK=TRUE python3 analysis/field_gauntlet.py 90 <agent>
Numpy agents without a BLAS thread cap spend 1794ms/forward instead of 32ms, which exhausts
main.py's wall-clock search budget inside game 1 and silently drops them to search_count=1.
Also verify the machine is idle first with `ps aux | grep "[p]ython3"` — pgrep is unreliable here.
"""
import sys, os
os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import round_robin as RR

# (label, agent dir, true meta share %)
# BAND-CORRECTED WEIGHTS (2026-08-12): the old weights were GLOBAL-meta shares, but our slots
# live at ~500-950 where composition differs sharply (band-composition law). Measured on our own
# fresh slot drops: M-Lucario 20-29% of the field (old weight: 3.8 — an 8x under-weight that made
# the lab miss exactly the cell that was beating us on the ladder). Mirror/Grimmsnarl thins with
# altitude (30.7 global -> ~15-21 in-band). mluc_v1 kept as the M-Lucario body until mluc_imit
# validates (GRIMM2 gate); swap it in after.
FIELD = [
    ("Grimmsnarl", "my-agent/grimm_v12_live", 18.0),
    ("M-Lucario",  "my-agent/mluc_imit",      24.0),   # VALIDATED 2026-08-12: beats the fixed rules pilot 68.3-31.7
    ("Alakazam",   "my-agent/ala_imit",       17.0),   # VALIDATED 2026-08-12: beats the tuned rules pilot 75.0-25.0
    ("Ogerpon",    "my-agent/oger_v6s",        8.0),   # UPGRADED 2026-08-14: best-ever Ogerpon (SS deck, 3-teacher corpus; beats oger_v4i 55.8% pooled N=240)
    ("Crustle",    "my-agent/crustle_imit",    5.0),   # VALIDATED 2026-08-12: 76.7% vs bc_crustle; REPRODUCES the ladder (85% vs oger_vf1 where real Crustle went 5-0)
]



# 1200-FIELD PROFILE (2026-08-12): select with PTCG_FIELD=top. Shares from the fresh 4,870-game
# dump (the band our agents fight AFTER climbing — the destination field, per the band-mismatch
# law the low-band weights capture the transit field instead). Bodies = the validated fleet.
if os.environ.get("PTCG_FIELD") == "top":
    FIELD = [
        ("Grimmsnarl", "my-agent/grimm_v12_live", 21.9),
        ("Alakazam",   "my-agent/ala_imit",       16.3),
        ("Dragapult",  "my-agent/drag_v4",        14.1),
        ("M-Lopunny",  "my-agent/mlop_imit",      13.1),
        ("Ogerpon",    "my-agent/oger_v6s",        9.5),   # UPGRADED 2026-08-14 (was oger_v4i)
        ("M-Lucario",  "my-agent/mluc_imit",       7.5),
        ("Crustle",    "my-agent/crustle_imit",    1.2),
    ]


def _reset_budgets(*mod_names):
    """main.py keeps a MODULE-LEVEL _SPENT wall-clock accumulator that never resets, and
    _budgeted_search degrades to 10 evals past 200s and to 1 (search off) past 400s. Loading an
    agent once and playing N games therefore handicaps it progressively — the OPPONENT most of
    all, which silently inflates the candidate's score in exactly the cells we care about.
    Reset every loaded agent's clock before each game so all N games are played at full depth."""
    for nm in mod_names:
        m = sys.modules.get(nm)
        sp = getattr(m, "_SPENT", None)
        if isinstance(sp, list) and sp:
            sp[0] = 0.0


    # Per-agent modules that MUST NOT be shared between the two agents in a duel.
_PRIVATE = ("mcts_agent", "np_common", "nn_common")


def _prime_path(agent_dir):
    """Force this agent's own directory to the FRONT of sys.path before loading it.
    main.py only does `if _HERE not in sys.path: sys.path.insert(0,_HERE)`. On a RE-load the dir
    is already present (from an earlier duel) but no longer first, so the guard skips and the
    agent imports whichever mcts_agent/np_common the previously-loaded agent left at the front.
    Measured: drag_pol reads 86% vs alakazam_v20 in a fresh process and 1.7% in a gauntlet where
    the Grimmsnarl duel ran first. Purging alone is NOT enough — the search path must be primed."""
    p = os.path.abspath(os.path.join(ROOT, agent_dir))
    while p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)


def _purge_private():
    """Every agent's main.py does sys.path.insert(0,_HERE) then `from mcts_agent import ...`.
    The module NAME is process-global, so the FIRST agent loaded claims the cache slot and every
    agent loaded after it silently runs the FIRST agent's search code. Verified: after loading
    drag_pol then grimm_v12_live, sys.modules['mcts_agent'].__file__ pointed at drag_pol's copy
    and both mains held the SAME function object.
    That is not cosmetic — the two files differ. grimm_v12_live/mcts_agent.py:319 passes an
    undefined `your_deck` so its root sweep raises NameError into `except: pass`, which this
    project previously measured as ACCIDENTALLY BENEFICIAL (it keeps prior-guided UCB instead of
    collapsing wide decisions into 1-eval value-greedy picks). Running v12 on the "fixed" sweep
    therefore makes it play materially worse: 4.8 attacks/game vs 6.7, 2.75 prizes vs 3.97.
    Measured effect on one cell: drag_pol vs v12 reads 78.3% shared, 34.4% isolated, and 0.0%
    if v12 loads first. Purging between loads makes each main.py import its OWN copy; the
    already-loaded agent keeps the reference it bound at import time.
    (This also fixes the np_common.DEFAULT_FEAT global that the last agent loaded would clobber.)
    """
    for m in _PRIVATE:
        sys.modules.pop(m, None)


def duel(cand_dir, opp_dir, n):
    n0 = "c_" + os.path.basename(cand_dir)
    n1 = "o_" + os.path.basename(opp_dir)
    _purge_private(); _prime_path(cand_dir)
    a0, d0 = RR.load(cand_dir, n0)
    _purge_private(); _prime_path(opp_dir)
    a1, d1 = RR.load(opp_dir, n1)
    w = l = 0
    for i in range(n):
        _reset_budgets(n0, n1)
        if i % 2 == 0:
            r = RR.play(a0, d0, a1, d1); mine, theirs = 0, 1
        else:
            r = RR.play(a1, d1, a0, d0); mine, theirs = 1, 0
        if r == mine: w += 1
        elif r == theirs: l += 1
    return w, l


def main():
    n = int(sys.argv[1]); cands = sys.argv[2:]
    if not cands:
        print(__doc__); return
    cover = sum(s for _, _, s in FIELD)
    print(f"General field gauntlet: N={n}/opponent, {len(FIELD)} archetypes = "
          f"{cover:.1f}% of the true meta (renormalised)\n")
    results = {}
    for cand in cands:
        print(f"===== {cand} =====")
        acc = used = 0.0
        for label, opp, share in FIELD:
            if os.path.abspath(cand) == os.path.abspath(os.path.join(ROOT, opp)):
                continue
            w, l = duel(cand, opp, n)
            played = w + l
            wr = (100.0 * w / played) if played else 0.0
            acc += wr * share; used += share
            print(f"  vs {label:<12} {w:>3}-{l:<3} = {wr:5.1f}%   (meta {share:.1f}%)")
        score = acc / used if used else 0.0
        results[cand] = score
        print(f"  FIELD-WEIGHTED SCORE: {score:.1f}%\n")
    if len(results) > 1:
        print("=== RANKING ===")
        for k, v in sorted(results.items(), key=lambda kv: -kv[1]):
            print(f"  {v:5.1f}%  {k}")


if __name__ == "__main__":
    main()
