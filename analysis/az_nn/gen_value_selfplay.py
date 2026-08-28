#!/usr/bin/env python3
"""Generate VALUE-training data on states OUR OWN agent actually reaches.

WHY: the value head has only ever seen expert-visited states with coarse outcome labels, and it
is now the measured bottleneck — search value saturates after a few evals because leaf values
cannot discriminate futures (fixed-vs-broken-search A/B 48.9%; argmax-vs-search 31/69; the one
value-target change in project history bought +135 rating). This script plays our deployed agent
locally and records every decision-state on OUR side(s) with the EXACT final outcome.

Audit fixes baked in (vs the extract_v2 pipeline):
  * margins are EXACT — we observe the true terminal state locally, no stale-single-view
    undercount of the winner's margin;
  * games run to turn 25 before prize adjudication (real ladder games run past T14 in ~20% of
    games; the old T14 stop truncated exactly the phase the value head is worst at).

Usage: gen_value_selfplay.py <agent_dir> <n_games> <out.npz> [--opp=<agent_dir>|mirror]
                             [--search=10] [--seed=0]
Mirror games record BOTH seats (both are our states); vs-opponent games record our seat only.
Output npz matches the extract_v2 ragged schema so the trainer's Ragged/collate reuse works.
"""
import json
import os
import random
import sys
from array import array
from collections import Counter

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
AGENT = sys.argv[1]
NGAMES = int(sys.argv[2])
OUT = sys.argv[3]
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[4:] if "=" in a}
OPP = F.get("opp", "mirror")
SEARCH = int(F.get("search", 10))
SEED = int(F.get("seed", 0))
STOP_TURN = 25

sys.path.insert(0, AGENT)
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
import np_common as NN                    # noqa: E402  (sets DEFAULT_FEAT on model load)
from mcts_agent import mcts_agent         # noqa: E402
from cg import game as cggame             # noqa: E402
from cg.api import to_observation_class   # noqa: E402

random.seed(SEED)
np.random.seed(SEED)

MODEL = NN.NpModel(os.path.join(AGENT, "model_np.npz"))
DECK = [int(x) for x in open(os.path.join(AGENT, "deck.csv")).read().split()]

if OPP == "mirror":
    OPP_MODEL, OPP_DECK = MODEL, DECK
else:
    sys.path.insert(0, OPP)
    OPP_MODEL = NN.NpModel(os.path.join(OPP, "model_np.npz"))
    OPP_DECK = [int(x) for x in open(os.path.join(OPP, "deck.csv")).read().split()]


class Accum:
    def __init__(self):
        self.index = array('i'); self.value = array('f')
        self.word_end = array('q'); self.n_words = array('i'); self.tok_start = array('q')

    def add(self, sv):
        base = len(self.index)
        self.tok_start.append(len(self.word_end))
        self.index.extend(sv.index); self.value.extend(sv.value)
        starts = list(sv.offset) + [len(sv.index)]
        for k in range(len(sv.offset)):
            self.word_end.append(base + starts[k + 1])
        self.n_words.append(len(sv.offset))

    def arrays(self, tag):
        return {f"{tag}_index": np.asarray(self.index, dtype=np.int32),
                f"{tag}_value": np.asarray(self.value, dtype=np.float32),
                f"{tag}_wordend": np.asarray(self.word_end, dtype=np.int64),
                f"{tag}_nwords": np.asarray(self.n_words, dtype=np.int32),
                f"{tag}_tokstart": np.asarray(self.tok_start, dtype=np.int64)}


def wrap(obs, steps):
    return {"current": obs.get("current"), "select": obs.get("select"),
            "logs": obs.get("logs", []), "step": steps, "remainingOverageTime": 600,
            "search_begin_input": obs.get("search_begin_input")}


def play_one(mirror, our_seat):
    """Play one game; return (per-seat pending samples, winner, exact final margin for seat0)."""
    left = list(DECK) if (mirror or our_seat == 0) else list(OPP_DECK)
    right = list(DECK) if (mirror or our_seat == 1) else list(OPP_DECK)
    obs, _ = cggame.battle_start(left, right)
    if obs is None:
        return None
    pending = [[], []]        # per seat: (sv_enc, sv_dec, ncand, stype, turn)
    result = None
    final_margin0 = 0.0
    steps = 0
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            P = cur.get("players")
            if P and P[0] and P[1]:
                p0 = 6 - len(P[0].get("prize") or []); p1 = 6 - len(P[1].get("prize") or [])
                final_margin0 = max(-1.0, min(1.0, (p0 - p1) / 6.0))
            r = cur.get("result", -1)
            if r not in (None, -1):
                result = r if r in (0, 1) else None
                break
            if obs.get("select") is None:
                break
            turn = cur.get("turn", 0) or 0
            if turn > STOP_TURN:
                if P and P[0] and P[1]:
                    if p0 != p1:
                        result = 0 if p0 > p1 else 1
                    else:
                        d0 = P[0].get("deckCount") or 0; d1 = P[1].get("deckCount") or 0
                        result = 0 if d0 > d1 else (1 if d1 > d0 else None)
                break
            you = cur.get("yourIndex", 0)
            w = wrap(obs, steps)
            ours = mirror or (you == our_seat)
            model = MODEL if ours else OPP_MODEL
            deck = DECK if ours else OPP_DECK
            # record BEFORE acting: this exact observation is a state our policy visited
            if ours:
                try:
                    oc = to_observation_class(w)
                    if oc.select is not None:
                        acts = NN.enumerate_actions(oc.select, 64)
                        if len(acts) >= 2:
                            sve = NN.get_encoder_input(oc, deck)
                            svd = NN.get_decoder_input(oc, acts)
                            pending[you].append((sve, svd, len(acts),
                                                 int((obs.get("select") or {}).get("type", -1)),
                                                 int(turn)))
                except Exception:
                    pass
            sel, _ = mcts_agent(w, deck, model, search_count=SEARCH)
            obs = cggame.battle_select([int(x) for x in sel])
            steps += 1
    finally:
        cggame.battle_finish()
    if result is None:
        return None
    return pending, result, final_margin0


def main():
    enc, dec = Accum(), Accum()
    rows = array('f')
    kept = games = 0
    attempts = 0
    while games < NGAMES and attempts < NGAMES * 3:
        attempts += 1
        mirror = (OPP == "mirror")
        our_seat = random.randint(0, 1)
        out = play_one(mirror, our_seat)
        if out is None:
            continue
        pending, winner, margin0 = out
        games += 1
        for seat in (0, 1):
            if not pending[seat]:
                continue
            if not mirror and seat != our_seat:
                continue
            won = 1.0 if winner == seat else 0.0
            margin = margin0 if seat == 0 else -margin0
            for sve, svd, ncand, stype, turn in pending[seat]:
                enc.add(sve); dec.add(svd)
                rows.extend((0.0, float(ncand), float(stype), float(turn), won,
                             0.6, 10.0, float(margin), 0.0))   # pid must index players[]
                kept += 1
        if games % 25 == 0:
            print(f"  {games}/{NGAMES} games -> {kept} states", flush=True)

    R = np.frombuffer(rows, dtype=np.float32).reshape(-1, 9)
    data = {}
    data.update(enc.arrays("enc")); data.update(dec.arrays("dec"))
    data["meta"] = R
    data["meta_cols"] = np.asarray(["tgt", "ncand", "stype", "turn", "won", "wr", "oppdeck",
                                    "margin", "pid"])
    data["players"] = np.asarray(["selfplay"])
    data["deck_vocab"] = np.asarray(["selfplay"])
    data["feat"] = np.asarray([2 if MODEL.feat == 2 else 1])
    data["decoder_vocab"] = np.asarray([NN.decoder_size_v2 if MODEL.feat == 2 else NN.decoder_size])
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    np.savez(OUT, **data)
    print(f"DONE: {games} games ({attempts - games} void) -> {kept} our-side states -> {OUT} "
          f"({os.path.getsize(OUT)/1e6:.0f}MB)  feat={int(data['feat'][0])}")


if __name__ == "__main__":
    main()
