#!/usr/bin/env python3
"""Imitation extractor v2 — replaces extract_manifest.py.

Changes vs v1 (which produced the 377k-decision / 29%-top1 corpus):
  1. ALL select types, not MAIN-only (v1 hard-dropped `select.type != 0`). The select type is
     recorded per sample so any subset can be trained/measured later.
  2. Flat-array .npz storage instead of a pickle of Python lists — the 718MB v1 pkl expands to
     many GB of Python objects in RAM; this machine has 17GB.
  3. Per-sample METADATA (player winrate, game won, opponent deck, turn, select type, candidate
     count, target index) so the trainer can filter/weight by data quality instead of imitating a
     51.5%-winrate average of 47 players.
  4. A DROP LEDGER: every decision that does not become a sample is counted with a reason, and
     exceptions are recorded by type instead of swallowed by a bare `except: continue`.
  5. Value target = the game's actual result (+1/-1), with the shaped prize margin kept alongside.

Usage:
  extract_v2.py <manifest.csv>[,<manifest2.csv>...] <out.npz> [--cap=64] [--main-only] [--limit=N]
Manifests need columns: path, side, won, player_winrate, opp_deck (extra columns are ignored).
"""
import csv
import json
import os
import sys
import zipfile
from array import array
from collections import Counter, defaultdict

import numpy as np

M_TGT, M_NCAND, M_STYPE = 0, 1, 2

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
from cg.api import to_observation_class          # noqa: E402
import nn_common as NN                            # noqa: E402

# The deck that goes into the encoder's "your_deck" word for EVERY sample. This was hard-coded
# to the Grimmsnarl 60 with no override, so every non-Grimmsnarl corpus this project ever built
# (Dudunsparce, M-Lucario, Ogerpon) was encoded as if the pilot were holding Grimmsnarl's deck,
# and then deployed holding its own — an input the net had never seen. Measured cost: changing
# only this word flips ~24% of the model's decisions. Override with --deck=<path to deck.csv>.
OUR_DECK = [int(x) for x in open(os.path.join(ROOT, "my-agent/grimmsnarl_v17/deck.csv")).read().split()]

DECK_VOCAB = ['Grimmsnarl', 'Alakazam', 'Crustle', 'Cynthia-Garchomp', 'Dragapult', 'M-Lucario',
              'Dipplin', 'Archaludon', 'M-Starmie', 'M-Kangaskhan', 'other']
DECK_IDX = {d: i for i, d in enumerate(DECK_VOCAB)}

NCOL = 11  # metadata columns per decision (see meta_cols below); col 10 = TURN-CLOSING flag

# col 10 "close": did the expert END the turn or ATTACK at this decision?
# Measured on held-out pro games (2026-08-12): our agents systematically REFUSE to close the turn.
# palsystem picks END 139 times where our top-1 picks it 46 (3.0x); Dipam terminates his turn at
# 485 decisions and drag_pol keeps spending resources at 228 of them (47%), walking past Phantom
# Dive 73 times and END 71 times. Both agents over-develop and dump the hand instead of swinging.
# Recording it lets the trainer up-weight exactly those decisions (--boost-close).
CLOSE_OPTS = {13, 14}   # OptionType.ATTACK, OptionType.END

# Day-dump replays were archived (user compressed 20260722/23/24 into one zip to save 52GB);
# read members straight from the archive when the manifest path no longer exists on disk.
DUMP_ZIP = os.path.join(ROOT, "20260722:23:24.zip")
_ZIP = [None]


def load_replay(path):
    if os.path.exists(path):
        return json.load(open(path))
    # folders were moved from ~/Desktop into the project root — follow them
    moved = path.replace("/Users/nickzwart/Desktop/", ROOT + "/")
    if os.path.exists(moved):
        return json.load(open(moved))
    member = "/".join(path.rstrip("/").split("/")[-2:])       # e.g. 20260722/87363038.json
    if _ZIP[0] is None and os.path.exists(DUMP_ZIP):
        _ZIP[0] = zipfile.ZipFile(DUMP_ZIP)
    if _ZIP[0] is not None:
        try:
            with _ZIP[0].open(member) as f:
                return json.load(f)
        except KeyError:
            pass
    raise FileNotFoundError(path)


class Accum:
    """Flat concatenated storage for variable-length sparse vectors.

    Uses array.array, not Python lists: the full corpus is ~1.1M decisions x ~350 sparse entries,
    which as lists of int objects is ~10GB (this machine has 17GB). Raw 4/8-byte cells keep it
    under ~2GB.
    """

    def __init__(self):
        self.index = array('i')        # int32, running
        self.value = array('f')        # float32
        self.word_end = array('q')     # int64: end offset (into index) of each word, running
        self.n_words = array('i')      # int32 per sample
        self.tok_start = array('q')    # int64: first word of this sample

    def add(self, sv):
        base = len(self.index)
        self.tok_start.append(len(self.word_end))
        self.index.extend(sv.index)
        self.value.extend(sv.value)
        # sv.offset holds the START of each word; convert to running ends
        starts = list(sv.offset) + [len(sv.index)]
        for k in range(len(sv.offset)):
            self.word_end.append(base + starts[k + 1])
        self.n_words.append(len(sv.offset))

    def arrays(self, tag):
        return {
            f"{tag}_index": np.asarray(self.index, dtype=np.int32),
            f"{tag}_value": np.asarray(self.value, dtype=np.float32),
            f"{tag}_wordend": np.asarray(self.word_end, dtype=np.int64),
            f"{tag}_nwords": np.asarray(self.n_words, dtype=np.int32),
            f"{tag}_tokstart": np.asarray(self.tok_start, dtype=np.int64),
        }


def shaped_margin(final_players, seat):
    try:
        pm = 6 - len((final_players[seat].get("prize")) or [])
        po = 6 - len((final_players[1 - seat].get("prize")) or [])
        return max(-1.0, min(1.0, (pm - po) / 6.0))
    except Exception:
        return 0.0


def extract_game(replay, seat, meta, enc, dec, rows, drops, cap, main_only, feat=1):
    steps = replay.get("steps", [])
    final_players = None
    for step in reversed(steps):
        for ent in step:
            pls = (((ent or {}).get("observation") or {}).get("current") or {}).get("players")
            if pls and len(pls) == 2 and pls[0] and pls[1]:
                final_players = pls
                break
        if final_players:
            break
    margin = shaped_margin(final_players, seat) if final_players else 0.0
    won = meta["won"]
    added = 0

    for i, step in enumerate(steps):
        ent = step[seat] if seat < len(step) else None
        if not ent:
            continue
        if ent.get("status") != "ACTIVE":       # the other seat's view; it was never asked to act
            drops["inactive_seat"] += 1
            continue
        o = ent.get("observation") or {}
        sel = o.get("select")
        cur = o.get("current")
        # ---- ACTION/OBSERVATION ALIGNMENT (the v1 bug) --------------------------------------
        # In these Kaggle replays a seat's submitted action is recorded in the NEXT step's entry
        # for that seat, not alongside the observation it responds to. Verified three ways:
        #   * same-entry pairing validates against the select's option list / minCount-maxCount
        #     only 72.2% of the time (14.1% out-of-range, 10.2% empty); next-step pairing: 99.9%.
        #   * re-running our own grimmsnarl_v19 agent on its own ladder replays reproduces the
        #     NEXT-step action 78.3% of the time vs 22.4% for the same-entry action.
        # v1 (extract_manifest.py) used the same entry, so every one of its 377k training labels
        # was the action for the PREVIOUS decision. That is the primary cause of the 29% plateau.
        nxt = steps[i + 1][seat] if (i + 1 < len(steps) and seat < len(steps[i + 1])) else None
        act = (nxt or {}).get("action")
        if not sel or act is None or not cur:
            drops["no_select_or_action"] += 1
            continue
        stype = sel.get("type", -1)
        if main_only and stype != 0:
            drops[f"nonmain_type{stype}"] += 1
            continue
        opts = sel.get("option") or []
        if len(opts) <= 1:
            drops["trivial_single_option"] += 1
            continue
        chosen = [int(x) for x in act if isinstance(x, int) and 0 <= x < len(opts)]
        if len(chosen) != len([x for x in act if isinstance(x, int)]):
            # audit 2026-08-12: silently truncating out-of-range indices can leave a survivor
            # set that still matches an enumerated combo — a WRONG label, worse than no label.
            drops["choice_index_out_of_range"] += 1
            continue
        if not chosen:
            drops["empty_choice"] += 1
            continue
        try:
            oc = to_observation_class({"current": cur, "select": sel, "logs": o.get("logs", []),
                                       "step": 0, "search_begin_input": o.get("search_begin_input")})
            actions = NN.enumerate_actions(oc.select, cap)
            cs = set(chosen)
            tgt = next((j for j, a in enumerate(actions) if set(a) == cs), None)
            if tgt is None:
                drops[f"target_not_enumerated_type{stype}"] += 1
                continue
            # was the expert's chosen action a turn-CLOSER (attack or end)?
            try:
                _ot = [getattr(opts[c].get("type", -1) if isinstance(opts[c], dict)
                               else getattr(opts[c], "type", -1), "value",
                               opts[c].get("type", -1) if isinstance(opts[c], dict)
                               else getattr(opts[c], "type", -1)) for c in chosen]
                is_close = 1.0 if any(int(t) in CLOSE_OPTS for t in _ot) else 0.0
            except Exception:
                is_close = 0.0
            se = NN.get_encoder_input(oc, OUR_DECK)
            sd = NN.get_decoder_input(oc, actions, feat)
            if se.index and max(se.index) >= NN.encoder_size:
                drops["encoder_index_oob"] += 1
                continue
            dvocab = NN.decoder_size_v2 if feat >= 2 else NN.decoder_size
            if sd.index and max(sd.index) >= dvocab:
                drops[f"decoder_index_oob_type{stype}"] += 1
                continue
        except Exception as e:
            drops[f"exc:{type(e).__name__}"] += 1
            continue

        # current prize differential AT THIS DECISION (mine - theirs; 0 during setup) — lets
        # trainers target situational slices like "behind in the mirror" (added 2026-07-29 for
        # v16: our mirror-comeback win rate is 23% vs the #1's 62%)
        try:
            _pls = cur.get("players") or [None, None]
            _pm = _pls[seat] or {}; _po = _pls[1 - seat] or {}
            _prm = _pm.get("prize"); _pro = _po.get("prize")
            pdiff = float((6 - len(_prm)) - (6 - len(_pro))) if (_prm and _pro) else 0.0
        except Exception:
            pdiff = 0.0
        enc.add(se)
        dec.add(sd)
        rows.extend((
            tgt,                                    # 0 target index
            len(actions),                           # 1 candidate count
            stype,                                  # 2 select type
            int(cur.get("turn", 0) or 0),           # 3 turn
            1 if won else 0,                        # 4 game won
            meta["wr"],                             # 5 player winrate
            DECK_IDX.get(meta["opp"], DECK_IDX['other']),   # 6 opponent deck
            margin,                                 # 7 shaped prize margin
            meta["pid"],                            # 8 player id
            pdiff,                                  # 9 current prize diff at decision
            is_close,                               # 10 expert ENDED the turn or ATTACKED here
        ))
        added += 1
    return added


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in sys.argv[1:] if a.startswith("--")}
    manifests = args[0].split(",")
    out = args[1]
    cap = int(flags.get("--cap", 64))
    main_only = bool(flags.get("--main-only", False))
    limit = int(flags.get("--limit", 0))
    feat = int(flags.get("--feat", 1))

    # --deck: the pilot's OWN 60 must go into the encoder, otherwise the net learns to play a
    # deck it will never be dealt. Defaults to the historical Grimmsnarl list for reproducibility.
    if flags.get("--deck"):
        global OUR_DECK
        OUR_DECK = [int(x) for x in open(flags["--deck"]).read().split()]
        assert len(OUR_DECK) == 60, f"--deck must be 60 cards, got {len(OUR_DECK)}"
        print(f"encoder your_deck <- {flags['--deck']} ({len(OUR_DECK)} cards)", flush=True)
    else:
        print("encoder your_deck <- DEFAULT grimmsnarl_v17 deck (pass --deck for other archetypes)",
              flush=True)

    by_path = defaultdict(list)
    players = {}
    for mp in manifests:
        for row in csv.DictReader(open(mp)):
            p = row["player"]
            if p not in players:
                players[p] = len(players)
            by_path[row["path"]].append({
                "seat": int(row["side"]),
                "won": int(row["won"]),
                "wr": float(row["player_winrate"] or 0.5),
                "opp": row.get("opp_deck", "other"),
                "pid": players[p],
            })

    paths = list(by_path)
    if limit:
        paths = paths[:limit]
    print(f"{len(paths)} games / {len(players)} players / cap={cap} main_only={main_only} feat={feat}", flush=True)

    enc, dec, rows = Accum(), Accum(), array('f')   # rows = flat NCOL-wide metadata table
    drops = Counter()
    ng = 0
    for path in paths:
        try:
            r = load_replay(path)
        except Exception as e:
            drops[f"unreadable:{type(e).__name__}"] += 1
            continue
        for meta in by_path[path]:
            extract_game(r, meta["seat"], meta, enc, dec, rows, drops, cap, main_only, feat)
        ng += 1
        if ng % 250 == 0:
            print(f"  {ng}/{len(paths)} games -> {len(rows) // NCOL} decisions", flush=True)

    R = np.frombuffer(rows, dtype=np.float32).reshape(-1, NCOL)
    data = {}
    data.update(enc.arrays("enc"))
    data.update(dec.arrays("dec"))
    data["meta"] = R
    data["meta_cols"] = np.asarray(["tgt", "ncand", "stype", "turn", "won", "wr", "oppdeck",
                                    "margin", "pid", "pdiff", "close"])
    data["players"] = np.asarray([p for p, _ in sorted(players.items(), key=lambda kv: kv[1])])
    data["deck_vocab"] = np.asarray(DECK_VOCAB)
    data["feat"] = np.asarray([feat])
    data["decoder_vocab"] = np.asarray([NN.decoder_size_v2 if feat >= 2 else NN.decoder_size])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    np.savez(out, **data)

    print(f"\nDONE: {ng} games -> {len(R)} decisions -> {out} "
          f"({os.path.getsize(out) / 1e6:.0f}MB)")
    print("\nDROP LEDGER (decisions not turned into samples):")
    tot_drop = sum(drops.values())
    for k, v in drops.most_common(40):
        print(f"  {k:44s} {v:8d}  ({v / max(1, tot_drop):5.1%} of drops)")
    print(f"  {'TOTAL DROPPED':44s} {tot_drop:8d}   kept {len(R)} "
          f"({len(R) / max(1, len(R) + tot_drop):.1%} of all decisions)")
    if len(R):
        st = Counter(R[:, M_STYPE].astype(int).tolist())
        print("\nkept by select type:", dict(st.most_common()))
        nc = R[:, M_NCAND]
        print(f"candidates: mean {nc.mean():.1f} median {np.median(nc):.0f} "
              f"p90 {np.percentile(nc, 90):.0f} max {nc.max():.0f}")
        tg = R[:, M_TGT]
        print(f"target index: mean {tg.mean():.2f}  frac==0 {float((tg == 0).mean()):.1%}  "
              f"random-guess top1 {float((1.0 / nc).mean()):.1%}")


if __name__ == "__main__":
    main()
