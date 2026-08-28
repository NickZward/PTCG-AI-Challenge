#!/usr/bin/env python3
"""WHERE DO WE DISAGREE WITH THE #1 PLAYER?

We copy Dries @ Tufa Labs' moves ~82% of the time and are still ~250 rating points behind, and
more imitation data no longer helps (v9 gate-rejected). So the question is no longer "how often"
but "WHERE" — if the remaining 18% clusters into a recognisable behaviour, that is a MECHANISM,
and mechanism-level fixes are the ones that transplant (project transplant law).

For every decision Dries actually faced we run our deployed policy net on the same observation
and compare argmax vs his real choice, then bucket the disagreements by:
  * the OPTION TYPE he chose vs the one we chose  (the confusion matrix -- the money output)
  * game phase (turn), prize situation (ahead/level/behind), and whether he won that game

Usage: disagree_dries.py [agent_dir] [n_games] [replay_dir]
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
AGENT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "my-agent/grimm_imit_v6cand")
NGAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 150
RDIR = sys.argv[3] if len(sys.argv) > 3 else "/Users/nickzwart/Desktop/Dries Tufa Labs"
PLAYER = os.path.basename(RDIR).split()[0].lower()

sys.path.insert(0, AGENT)
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
import np_common as NN                       # noqa: E402
from cg.api import to_observation_class, OptionType   # noqa: E402

OPT_NAME = {getattr(OptionType, k): k for k in dir(OptionType) if not k.startswith("_")
            and isinstance(getattr(OptionType, k), int)}

model = NN.NpModel(os.path.join(AGENT, "model_np.npz"))
deck = [int(x) for x in open(os.path.join(AGENT, "deck.csv")).read().split()]


def opt_type_of(sel, idxs):
    """Name of the option type this action is 'about' (first non-END option, else END)."""
    opts = sel.get("option") or []
    names = []
    for i in idxs:
        if 0 <= i < len(opts):
            names.append(OPT_NAME.get(opts[i].get("type"), str(opts[i].get("type"))))
    if not names:
        return "NONE"
    for n in names:
        if n != "END":
            return n
    return "END"


def main():
    files = sorted(glob.glob(os.path.join(RDIR, "*.json")))[:NGAMES]
    agree = dis = 0
    conf = Counter()                       # (his_type, our_type) on disagreements
    by_turn = defaultdict(lambda: [0, 0])  # turn -> [disagree, total]
    by_prize = defaultdict(lambda: [0, 0])
    by_type = defaultdict(lambda: [0, 0])  # his option type -> [disagree, total]
    won_games = 0
    ngame = 0

    for fp in files:
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        tn = d.get("info", {}).get("TeamNames") or []
        seat = next((i for i, n in enumerate(tn) if PLAYER in n.strip().lower()), None)
        if seat is None:
            continue
        rw = d.get("rewards") or [None, None]
        if rw[seat] is None:
            continue
        won = rw[seat] > rw[1 - seat]
        ngame += 1
        won_games += won
        steps = d["steps"]
        for i, step in enumerate(steps):
            ent = step[seat] if seat < len(step) else None
            if not ent or ent.get("status") != "ACTIVE":
                continue
            o = ent.get("observation") or {}
            sel, cur = o.get("select"), o.get("current")
            if not sel or not cur:
                continue
            # ACTION ALIGNMENT: a seat's action lives in the NEXT step's entry (project law)
            nxt = steps[i + 1][seat] if (i + 1 < len(steps) and seat < len(steps[i + 1])) else None
            act = (nxt or {}).get("action")
            opts = sel.get("option") or []
            if act is None or len(opts) <= 1:
                continue
            his = [int(x) for x in act if isinstance(x, int) and 0 <= x < len(opts)]
            if not his:
                continue
            try:
                oc = to_observation_class({"current": cur, "select": sel, "logs": o.get("logs", []),
                                           "step": 0,
                                           "search_begin_input": o.get("search_begin_input")})
                actions = NN.enumerate_actions(oc.select, 64)
                if len(actions) < 2:
                    continue
                tgt = next((j for j, a in enumerate(actions) if set(a) == set(his)), None)
                if tgt is None:
                    continue
                sve = NN.get_encoder_input(oc, deck)
                svd = NN.get_decoder_input(oc, actions)
                _, pol = model.forward(sve, svd)
            except Exception:
                continue
            ours = int(np.argmax(pol))
            same = (ours == tgt)
            agree += same
            dis += (not same)

            ht = opt_type_of(sel, actions[tgt])
            ot = opt_type_of(sel, actions[ours])
            t = min(int(cur.get("turn", 0) or 0), 15)
            P = cur.get("players") or [{}, {}]
            mp = 6 - len(P[seat].get("prize") or [])
            op = 6 - len(P[1 - seat].get("prize") or [])
            band = "ahead" if mp > op else ("level" if mp == op else "behind")

            for d_, key in ((by_turn[t], None), (by_prize[band], None), (by_type[ht], None)):
                d_[1] += 1
                d_[0] += (not same)
            if not same:
                conf[(ht, ot)] += 1

    tot = agree + dis
    print(f"replayed {ngame} of {PLAYER}'s games ({won_games} wins) -> {tot} decision points")
    print(f"AGREEMENT with the #1 player: {agree}/{tot} = {agree/max(1,tot):.1%}"
          f"   (disagreements: {dis})\n")

    print("=== THE CONFUSION MATRIX: what HE did vs what WE would do (disagreements only) ===")
    print(f"{'HE chose':>16s}  {'WE chose':>16s}   count   share of all disagreements")
    for (ht, ot), c in conf.most_common(18):
        print(f"{ht:>16s}  {ot:>16s}   {c:5d}   {c/max(1,dis):5.1%}")

    print("\n=== disagreement rate by the option type HE chose (n>=40) ===")
    for k, (dd, nn) in sorted(by_type.items(), key=lambda kv: -kv[1][0]):
        if nn >= 40:
            print(f"  {k:>16s}  {dd:5d}/{nn:5d} = {dd/nn:5.1%} disagree")

    print("\n=== disagreement rate by turn ===")
    for t in sorted(by_turn):
        dd, nn = by_turn[t]
        if nn >= 30:
            print(f"  turn {t:2d}: {dd:5d}/{nn:5d} = {dd/nn:5.1%}")

    print("\n=== disagreement rate by prize situation ===")
    for b in ("ahead", "level", "behind"):
        if b in by_prize:
            dd, nn = by_prize[b]
            print(f"  {b:>7s}: {dd:5d}/{nn:5d} = {dd/nn:5.1%}")


if __name__ == "__main__":
    main()
