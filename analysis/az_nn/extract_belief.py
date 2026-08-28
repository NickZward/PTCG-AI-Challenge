#!/usr/bin/env python3
"""Belief-model extractor v0 — supervised data for predicting the OPPONENT'S HIDDEN HAND.

WHY: search fills the opponent's hidden hand/deck with crude dummies (energy fillers), which
measurably overfits the mirror and loses to the field (see ptcg-deeper-search-wall). Kaggle
replays are FULL-INFORMATION on the spectator stream, so supervised belief data is free.

ALIGNMENT (verified 100.0000% on 11,337 decisions across 80 games, 8 player folders):
  * steps[0][0].visualize is a list of per-decision frames; frame k corresponds to the decision
    taken at step k (frame k's `selected`/`action` echo the action that lands in steps[k+1]).
  * viz[k]['obs'] IS the acting seat's masked observation at step k (own-hand ids match the
    per-seat entry 100%).
  * viz[k]['current'] is the full-information state AFTER that action resolves; therefore the
    PRE-decision full state for the decision at step i is viz[i-1]['current'] (own-hand match
    100%, opp-hand length == masked handCount 100%; offset 0 gives only 41.6%/93.2%).
  * decks: viz[0]['action'] = [seat0_deck60, seat1_deck60].

Per sample: INPUT = the acting seat's masked observation through the existing feat-2 encoder
(np_common.get_encoder_input, same ragged npz schema as gen_value_selfplay/extract_v2 so the
trainer's Ragged/collate reuse works). TARGET = opponent hand as a count vector over a card
vocabulary built from all deck ids seen in the corpus. Both-seat perspectives are extracted.

NOTE ON SOURCES: the 03082026/04082026 Downloads dumps named in the original plan no longer
exist on disk; the same bare {id}.json Kaggle replays live in the per-player folders inside the
project root — those are the corpus (deduped by episode id across folders).

Usage: extract_belief.py <out.npz> [--cap=150000] [--games=2000] [--per-game=75] [--seed=0]
"""
import glob
import json
import os
import random
import sys
from array import array
from collections import Counter

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
import np_common as NN                       # noqa: E402  (torch-free encoder twin)
from cg.api import to_observation_class      # noqa: E402

NN.DEFAULT_FEAT[0] = 2

OUT = sys.argv[1]
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[2:] if "=" in a}
CAP = int(F.get("cap", 150000))
MAX_GAMES = int(F.get("games", 2000))
PER_GAME = int(F.get("per-game", 75))     # subsample per game so the cap SPREADS across games
SEED = int(F.get("seed", 0))

# bare {id}.json Kaggle-replay folders inside the project (Downloads dumps were deleted)
FOLDERS = ["ntumInoob", "LiamK", "Dries Tufa Labs", "James Cox & Henry Chao", "James Christian",
           "flg", "Majkel1337", "Dominic Peel", "__Taichicchi__", "Eggplanck", "Tonakaiiiii",
           "LiamK_05082926", "number 4_04082026", "Number 3", "JB Bryant", "Haggle", "highrated",
           "Luca", "flg_new"]

# archetype signature card -> label (same table as build_manifest_folders.py / analysis/digest.py)
ARCH = {648: 'Grimmsnarl', 743: 'Alakazam', 533: 'Crustle', 345: 'Crustle', 678: 'M-Lucario',
        93: 'Dipplin', 756: 'M-Kangaskhan', 190: 'Archaludon', 1031: 'M-Starmie',
        381: 'Cynthia-Garchomp', 121: 'Dragapult'}
ARCH_VOCAB = ['Grimmsnarl', 'Alakazam', 'Crustle', 'Cynthia-Garchomp', 'Dragapult', 'M-Lucario',
              'Dipplin', 'Archaludon', 'M-Starmie', 'M-Kangaskhan', 'other']
ARCH_IDX = {a: i for i, a in enumerate(ARCH_VOCAB)}


def arch_of(deck):
    c = Counter(deck)
    return next((lab for cid, lab in ARCH.items() if c.get(cid)), 'other')


class Accum:
    """Flat concatenated storage for variable-length sparse vectors (copy of gen_value_selfplay)."""

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


def main():
    random.seed(SEED)
    # ---- corpus: dedupe by episode id, shuffle for cross-folder spread ----
    by_id = {}
    for d in FOLDERS:
        for p in sorted(glob.glob(os.path.join(ROOT, d, "[0-9]*.json"))):
            by_id.setdefault(os.path.splitext(os.path.basename(p))[0], p)
    paths = sorted(by_id.items())
    random.shuffle(paths)
    print(f"{len(paths)} unique games across {len(FOLDERS)} folders; "
          f"processing up to {MAX_GAMES} games / {CAP} samples", flush=True)

    enc = Accum()
    targets = []          # per sample: list of opp-hand card ids (densified after vocab build)
    meta_rows = []        # per sample: game_idx, seat, step, turn, opp_arch, hand_count, stype
    game_ids = []         # per game actually contributing samples
    game_decks = []       # per game: (deck0, deck1) for deck-aware baselines later
    drops = Counter()
    align_ok = align_bad = 0
    games_used = 0

    for gid, path in paths:
        if games_used >= MAX_GAMES or len(targets) >= CAP:
            break
        try:
            rep = json.load(open(path))
            steps = rep["steps"]
            viz = next(e["visualize"] for e in steps[0] if e and e.get("visualize"))
            decks = viz[0]["action"]
            assert len(decks) == 2 and len(decks[0]) == 60 and len(decks[1]) == 60
        except Exception as e:
            drops[f"game_fail:{type(e).__name__}"] += 1
            continue
        game_idx = len(game_ids)
        pend = []                 # (sve, opp_hand, meta_row) buffered, then subsampled
        arch = [ARCH_IDX.get(arch_of(decks[0]), ARCH_IDX['other']),
                ARCH_IDX.get(arch_of(decks[1]), ARCH_IDX['other'])]

        for i, step in enumerate(steps):
            actors = [s for s, e in enumerate(step)
                      if e and e.get("status") == "ACTIVE"
                      and ((e.get("observation") or {}).get("select"))]
            if len(actors) != 1:
                if len(actors) > 1:
                    drops["multi_actor_step"] += 1
                continue
            s = actors[0]
            o = step[s]["observation"]
            if i < 1 or i - 1 >= len(viz):
                drops["no_frame"] += 1
                continue
            full = viz[i - 1].get("current")
            if not full:
                drops["frame_no_current"] += 1
                continue
            try:
                # ---- per-sample alignment guard (must hold; verified 100% in dev) ----
                own_m = sorted(c["id"] for c in ((o["current"]["players"][s] or {}).get("hand") or []))
                own_f = sorted(c["id"] for c in ((full["players"][s] or {}).get("hand") or []))
                opp_hand = [c["id"] for c in ((full["players"][1 - s] or {}).get("hand") or [])]
                opp_cnt = (o["current"]["players"][1 - s] or {}).get("handCount")
                if own_m != own_f or len(opp_hand) != opp_cnt:
                    align_bad += 1
                    drops["align_mismatch"] += 1
                    continue
                align_ok += 1
                if not opp_hand:
                    drops["opp_hand_empty"] += 1
                    continue
                oc = to_observation_class({"current": o["current"], "select": o["select"],
                                           "logs": o.get("logs", []), "step": 0,
                                           "search_begin_input": o.get("search_begin_input")})
                sve = NN.get_encoder_input(oc, decks[s])
                if sve.index and max(sve.index) >= NN.encoder_size:
                    drops["encoder_index_oob"] += 1
                    continue
            except Exception as e:
                drops[f"exc:{type(e).__name__}"] += 1
                continue
            pend.append((sve, opp_hand,
                         (game_idx, s, i, int(o["current"].get("turn", 0) or 0),
                          arch[1 - s], len(opp_hand), int(o["select"].get("type", -1) or 0))))
        if pend:
            if len(pend) > PER_GAME:
                keep = sorted(random.sample(range(len(pend)), PER_GAME))
                drops["per_game_subsampled"] += len(pend) - PER_GAME
                pend = [pend[k] for k in keep]
            pend = pend[:max(0, CAP - len(targets))]
            for sve, opp_hand, row in pend:
                enc.add(sve)
                targets.append(opp_hand)
                meta_rows.append(row)
            game_ids.append(gid)
            game_decks.append(decks)
            games_used += 1
        if games_used and games_used % 200 == 0:
            print(f"  {games_used} games, {len(targets)} samples, "
                  f"align {align_ok}/{align_ok + align_bad}", flush=True)

    # ---- card vocabulary: every id seen in any deck of the corpus ----
    vocab = sorted({cid for d0, d1 in game_decks for cid in d0 + d1})
    vidx = {cid: j for j, cid in enumerate(vocab)}
    tgt = np.zeros((len(targets), len(vocab)), dtype=np.uint8)
    oov = 0
    for r, hand in enumerate(targets):
        for cid in hand:
            j = vidx.get(cid)
            if j is None:
                oov += 1
                continue
            tgt[r, j] += 1

    deck_counts = np.zeros((len(game_decks), 2, len(vocab)), dtype=np.uint8)
    for g, (d0, d1) in enumerate(game_decks):
        for seat, dk in enumerate((d0, d1)):
            for cid in dk:
                deck_counts[g, seat, vidx[cid]] += 1

    meta = np.asarray(meta_rows, dtype=np.int32)
    rate = align_ok / max(1, align_ok + align_bad)
    out = {**enc.arrays("enc"), "target": tgt, "meta": meta,
           "vocab": np.asarray(vocab, dtype=np.int32),
           "games": np.asarray(game_ids), "deck_counts": deck_counts,
           "arch_vocab": np.asarray(ARCH_VOCAB),
           "align_rate": np.float64(rate)}
    np.savez_compressed(OUT, **out)
    print(f"\nwrote {OUT}: {len(meta)} samples / {len(game_ids)} games, vocab={len(vocab)}, "
          f"oov_hand_cards={oov}", flush=True)
    print(f"ALIGNMENT: {align_ok}/{align_ok + align_bad} = {rate:.4%}")
    print("drops:", dict(drops.most_common(12)))
    ph = meta[:, 3]
    print(f"phase split: T0-6={int((ph <= 6).sum())}  T7+={int((ph >= 7).sum())}")
    print("opp arch histogram:", {ARCH_VOCAB[a]: int(n) for a, n in
                                  zip(*np.unique(meta[:, 4], return_counts=True))})


if __name__ == "__main__":
    main()
