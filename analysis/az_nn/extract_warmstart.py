#!/usr/bin/env python3
"""#1 WARM-START: extract expert Grimmsnarl demonstrations from real replays into the SAME sample
format the self-play trainer uses (encoder sparse + decoder sparse + policy target + shaped value).

For each MAIN decision by a strong Grimmsnarl player:
  - encoder input  = get_encoder_input(obs, our_deck)                 (full board state)
  - decoder input  = get_decoder_input(obs, enumerate_actions)        (one token per action combo)
  - policy target  = +1 for the combo the EXPERT chose, -1 for the rest  (BC / imitation)
  - value target   = shaped game outcome from the player's seat (prize-margin/6, natural win -> +1)

Pretraining the Transformer on these (via train_core._train_epoch) starts self-play from EXPERT-level
play instead of random — the single biggest lever for making the Kaggle training worth it.

Usage: extract_warmstart.py <out.pkl> [max_games_per_source]
Saved as a pickle of dicts {ei,ev,eo,di,dv,do,pol,val}; the Kaggle trainer reconstructs + pretrains.
"""
import glob
import json
import os
import pickle
import sys

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))  # cg-lib
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
from cg.api import to_observation_class
import nn_common as NN

OUR_DECK = [int(x) for x in open(os.path.join(ROOT, "my-agent/grimmsnarl_v17/deck.csv")).read().split()]

# strongest Grimmsnarl demonstrators: (player-name-substring, folder)
SOURCES = [
    ("bono", os.path.join(ROOT, "Bono")),
    ("Luca", "/Users/nickzwart/Desktop/Logs 07-22"),           # #1 player (1156)
    ("jiatu.l", "/Users/nickzwart/Desktop/Logs 07-22"),
    ("__Taichicchi__", "/Users/nickzwart/Desktop/Logs 07-22"),
    ("Kotaro OKUYAMA", "/Users/nickzwart/Desktop/Logs 07-22"),
    ("Rmy", "/Users/nickzwart/Desktop/Logs 07-22"),
]


def shaped_value(final_players, seat):
    """Prize-margin/6 from `seat`'s perspective, clamped [-1,1] (matches the trainer's shaped reward)."""
    try:
        pm = 6 - len((final_players[seat].get("prize")) or [])
        po = 6 - len((final_players[1 - seat].get("prize")) or [])
        return max(-1.0, min(1.0, (pm - po) / 6.0))
    except Exception:
        return None


def process_game(r, player_sub, samples):
    tn = r.get("info", {}).get("TeamNames") or []
    seat = next((i for i, n in enumerate(tn) if player_sub.lower() in (n or "").lower()), None)
    if seat is None:
        return 0
    steps = r.get("steps", [])
    # final prize counts from the last step that has them
    final_players = None
    for step in reversed(steps):
        for ent in step:
            pls = (((ent or {}).get("observation") or {}).get("current") or {}).get("players")
            if pls and len(pls) == 2 and pls[0] and pls[1]:
                final_players = pls
                break
        if final_players:
            break
    val = shaped_value(final_players, seat) if final_players else None
    if val is None:
        return 0
    added = 0
    for step in steps:
        ent = step[seat] if seat < len(step) else None
        if not ent:
            continue
        o = ent.get("observation") or {}
        sel = o.get("select")
        act = ent.get("action")
        cur = o.get("current")
        if not sel or not act or not cur:
            continue
        if sel.get("type") != 0:                      # MAIN decisions only
            continue
        opts = sel.get("option") or []
        if len(opts) <= 1:
            continue
        chosen = [int(x) for x in act if isinstance(x, int) and x < len(opts)]
        if not chosen:
            continue
        try:
            oc = to_observation_class({"current": cur, "select": sel, "logs": o.get("logs", []),
                                       "step": 0, "search_begin_input": o.get("search_begin_input")})
            actions = NN.enumerate_actions(oc.select, 64)
            # combo index whose option-set == the expert's chosen set
            chosen_set = set(chosen)
            tgt = next((j for j, a in enumerate(actions) if set(a) == chosen_set), None)
            if tgt is None:
                continue
            sv_e = NN.get_encoder_input(oc, OUR_DECK)
            sv_d = NN.get_decoder_input(oc, actions)
            pol = [1.0 if j == tgt else -1.0 for j in range(len(actions))]
            samples.append({"ei": sv_e.index, "ev": sv_e.value, "eo": sv_e.offset,
                            "di": sv_d.index, "dv": sv_d.value, "do": sv_d.offset,
                            "pol": pol, "val": float(val)})
            added += 1
        except Exception:
            continue
    return added


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "model/az/grimm_warmstart.pkl")
    maxg = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    samples = []
    for player_sub, folder in SOURCES:
        files = sorted(glob.glob(os.path.join(folder, "*.json")))
        games = 0
        before = len(samples)
        for f in files:
            if games >= maxg:
                break
            try:
                r = json.load(open(f))
            except Exception:
                continue
            n = process_game(r, player_sub, samples)
            if n > 0:
                games += 1
        print(f"  {player_sub:<16} {games:4d} games -> {len(samples)-before:6d} decisions", flush=True)
    print(f"total warm-start decisions: {len(samples)}")
    with open(out, "wb") as fh:
        pickle.dump(samples, fh, protocol=4)
    print(f"saved {out}  ({os.path.getsize(out)/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
