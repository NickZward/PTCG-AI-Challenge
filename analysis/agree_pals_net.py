#!/usr/bin/env python3
"""Decision agreement of a TRAINED NET vs palsystem's real choices, on palsystem's own games.

Replays every game in oger_pals_manifest.csv, and at each decision palsystem actually faced
(status==ACTIVE, action lives in the NEXT step's same-seat entry -- the off-by-one law from
extract_v2.py:146) asks the checkpoint what IT would do.

Comparison is done in the CANONICAL action space, not on raw option ints: the expert's action set
is matched against NN.enumerate_actions() exactly the way the extractor builds its training target,
so a disagreement here is the same disagreement the trainer scored. (The 2026-07 agree_general bug
compared a raw int list to a canonical index and manufactured false disagreement.)

Every disagreement is classified:
  TIE   -- our candidate's decoder token bag is BYTE-IDENTICAL to his: the net physically cannot
           tell them apart, and neither can the reference encoding. Harmless.
  REAL  -- different bags, i.e. a genuinely different play.

Usage: agree_pals_net.py [ckpt] [--deck=...] [--out=<jsonl>]
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import torch

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
from cg.api import all_card_data, to_observation_class  # noqa: E402
import nn_common as NN  # noqa: E402

CKPT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
    else os.path.join(ROOT, "model/az/oger_f2pal_best.pth")
F = {a.split("=")[0].lstrip("-"): a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
DECK_PATH = F.get("deck", os.path.join(ROOT, "my-agent/oger_pal/deck.csv"))
MANIFEST = F.get("manifest", os.path.join(ROOT, "oger_pals_manifest.csv"))
OUT = F.get("out", "/tmp/agree_pals.jsonl")
CAP = int(F.get("cap", 64))

arch = json.load(open(CKPT.replace("_best.pth", "_arch.json")))
FEAT = int(arch.get("feat", 1))
DVOCAB = int(arch.get("decoder_vocab", NN.decoder_size))
model = NN.MyModel(*arch["model"], policy_tanh=arch.get("policy_tanh", False), decoder_vocab=DVOCAB)
model.load_state_dict(torch.load(CKPT, map_location="cpu"))
model.eval()
OUR_DECK = [int(x) for x in open(DECK_PATH).read().split()]
assert len(OUR_DECK) == 60
print(f"ckpt={os.path.basename(CKPT)} feat={FEAT} dvocab={DVOCAB} deck={os.path.basename(os.path.dirname(DECK_PATH))}",
      flush=True)

CARD = {c.cardId: c for c in all_card_data()}
NAME = lambda cid: getattr(CARD.get(cid), "name", f"#{cid}")  # noqa: E731

OTYPE = {0: 'number', 1: 'yes', 2: 'no', 3: 'card', 4: 'tool', 5: 'ecard', 6: 'energy', 7: 'play',
         8: 'attach', 9: 'EVOLVE', 10: 'ability', 11: 'discard', 12: 'retreat', 13: 'ATTACK',
         14: 'end', 15: 'skill', 16: 'spcond'}
STYPE = {0: 'MAIN', 1: 'CARD', 2: 'ATTACHED_CARD', 3: 'CARD_OR_ATT', 4: 'ENERGY', 5: 'SKILL',
         6: 'ATTACK', 7: 'EVOLVE', 8: 'COUNT', 9: 'YES_NO', 10: 'SPECIAL_COND'}
CTX = {0: 'MAIN', 1: 'SETUP_ACTIVE', 2: 'SETUP_BENCH', 3: 'SWITCH', 4: 'TO_ACTIVE', 5: 'TO_BENCH',
       6: 'TO_FIELD', 7: 'TO_HAND', 8: 'DISCARD', 9: 'TO_DECK', 10: 'TO_DECK_BOTTOM',
       11: 'TO_PRIZE', 18: 'EVOLVES_FROM', 19: 'EVOLVES_TO', 21: 'ATTACH_FROM', 22: 'ATTACH_TO',
       24: 'LOOK', 25: 'EFFECT_TARGET', 35: 'ATTACK', 37: 'EVOLVE', 43: 'ACTIVATE'}

# the two evolution lines that are the whole reason we chose imitation
LINES = {149: 'Applin', 346: 'Applin', 93: 'Dipplin', 150: 'Hydrapple ex',
         917: 'Chikorita', 709: 'Bayleef', 918: 'Bayleef', 710: 'Meganium'}
LINE_OF = {**{c: 'HYDRAPPLE' for c in (149, 346, 93, 150)},
           **{c: 'MEGANIUM' for c in (917, 709, 918, 710)}}


def bags(sv, n):
    """Per-candidate (index,value) byte bags from a decoder SparseVector."""
    starts = list(sv.offset) + [len(sv.index)]
    return [(tuple(sv.index[starts[k]:starts[k + 1]]), tuple(sv.value[starts[k]:starts[k + 1]]))
            for k in range(n)]


def opt_desc(obs, opts, picks):
    """Human label of an action: option types plus the card each one touches."""
    parts = []
    for p in picks:
        o = opts[p]
        t = int(getattr(o, "type", -1))
        lab = OTYPE.get(t, f"t{t}")
        cid = None
        try:
            if t == 9:  # EVOLVE: (card from hand) -> (in-play target)
                a = NN.get_card(obs, o.area, o.index, obs.current.yourIndex)
                b = NN.get_card(obs, o.inPlayArea, o.inPlayIndex, obs.current.yourIndex)
                lab += f"({NAME(a.id)}->{NAME(b.id)})"
                cid = a.id
            elif t == 8:  # ATTACH energy -> target
                b = NN.get_card(obs, o.inPlayArea, o.inPlayIndex, obs.current.yourIndex)
                lab += f"(->{NAME(b.id)})"
            elif t in (7, 10, 11):
                a = NN.get_card(obs, o.area, o.index, obs.current.yourIndex)
                lab += f"({NAME(a.id)})"
                cid = a.id
            elif t == 13:
                lab += f"(atk{o.attackId})"
            elif t == 3:
                a = NN.get_card(obs, o.area, o.index, o.playerIndex)
                lab += f"({NAME(a.id)})"
                cid = a.id
        except Exception:
            pass
        parts.append((lab, t, cid))
    return parts


rows = []
drops = Counter()
games = 0
manifest = list(csv.DictReader(open(MANIFEST)))
for rec in manifest:
    path = rec["path"]
    if not os.path.exists(path):
        drops["missing_replay"] += 1
        continue
    d = json.load(open(path))
    seat = int(rec["side"])
    steps = d.get("steps", [])
    games += 1
    for i, step in enumerate(steps):
        ent = step[seat] if seat < len(step) else None
        if not ent or ent.get("status") != "ACTIVE":
            continue
        o = ent.get("observation") or {}
        sel, cur = o.get("select"), o.get("current")
        nxt = steps[i + 1][seat] if (i + 1 < len(steps) and seat < len(steps[i + 1])) else None
        act = (nxt or {}).get("action")
        if not sel or act is None or not cur:
            drops["no_select_or_action"] += 1
            continue
        raw_opts = sel.get("option") or []
        stype = int(sel.get("type", -1))
        if len(raw_opts) <= 1:
            drops["trivial_single_option"] += 1
            continue
        chosen = [int(x) for x in act if isinstance(x, int) and 0 <= x < len(raw_opts)]
        if not chosen:
            drops["empty_choice"] += 1
            continue
        try:
            oc = to_observation_class({"current": cur, "select": sel, "logs": o.get("logs", []),
                                       "step": 0, "search_begin_input": o.get("search_begin_input")})
            actions = NN.enumerate_actions(oc.select, CAP)
            cs = set(chosen)
            tgt = next((j for j, a in enumerate(actions) if set(a) == cs), None)
            if tgt is None:
                drops[f"target_not_enumerated_{STYPE.get(stype, stype)}"] += 1
                continue
            se = NN.get_encoder_input(oc, OUR_DECK)
            sd = NN.get_decoder_input(oc, actions, FEAT)
            if (se.index and max(se.index) >= NN.encoder_size) or (sd.index and max(sd.index) >= DVOCAB):
                drops["index_oob"] += 1
                continue
            with torch.inference_mode():
                val, pol = NN.eval_nn(se, sd, model)
        except Exception as e:
            drops[f"exc:{type(e).__name__}"] += 1
            continue
        pol = pol[:len(actions)]
        ours = int(np.argmax(pol))
        B = bags(sd, len(actions))
        tie = (B[ours] == B[tgt])
        his = opt_desc(oc, oc.select.option, actions[tgt])
        mine = opt_desc(oc, oc.select.option, actions[ours])
        rows.append({
            "ep": rec["episode"], "turn": int(cur.get("turn", 0) or 0),
            "stype": stype, "ctx": int(sel.get("context", -1)),
            "ncand": len(actions), "tgt": tgt, "ours": ours,
            "agree": tgt == ours, "tie": bool(tie),
            "p_his": float(np.exp(pol[tgt]) / np.exp(pol).sum()),
            "p_ours": float(np.exp(pol[ours]) / np.exp(pol).sum()),
            "his": [h[0] for h in his], "mine": [m[0] for m in mine],
            "his_types": sorted({h[1] for h in his}), "mine_types": sorted({m[1] for m in mine}),
            "his_cids": [h[2] for h in his], "mine_cids": [m[2] for m in mine],
            "n_evolve_opts": sum(1 for op in oc.select.option if int(getattr(op, "type", -1)) == 9),
            "value": float(val),
        })

json.dump(rows, open(OUT, "w"))
print(f"{games} games -> {len(rows)} scored decisions -> {OUT}")
print("\nDROP LEDGER:")
for k, v in drops.most_common(20):
    print(f"  {k:44s} {v}")

A = sum(r["agree"] for r in rows)
T = len(rows)
Aeff = sum(r["agree"] or r["tie"] for r in rows)
print(f"\nOVERALL strict agreement : {A}/{T} = {A/T:.1%}")
print(f"OVERALL tie-aware agreement: {Aeff}/{T} = {Aeff/T:.1%}")
dis = [r for r in rows if not r["agree"]]
print(f"disagreements: {len(dis)}, of which byte-identical TIES {sum(r['tie'] for r in dis)} "
      f"({sum(r['tie'] for r in dis)/max(1,len(dis)):.1%}) -> REAL divergences "
      f"{sum(not r['tie'] for r in dis)} ({sum(not r['tie'] for r in dis)/T:.1%} of all decisions)")

print("\nBY SELECT TYPE (n>=15):")
by = defaultdict(lambda: [0, 0, 0])
for r in rows:
    k = STYPE.get(r["stype"], r["stype"])
    by[k][0] += r["agree"]; by[k][1] += 1; by[k][2] += (r["agree"] or r["tie"])
for k, v in sorted(by.items(), key=lambda kv: -kv[1][1]):
    if v[1] >= 15:
        print(f"  {str(k):14s} strict {v[0]:5d}/{v[1]:5d} = {v[0]/v[1]:5.1%}   tie-aware {v[2]/v[1]:5.1%}")

print("\nBY SELECT CONTEXT (n>=15):")
by = defaultdict(lambda: [0, 0, 0])
for r in rows:
    k = CTX.get(r["ctx"], f"ctx{r['ctx']}")
    by[k][0] += r["agree"]; by[k][1] += 1; by[k][2] += (r["agree"] or r["tie"])
for k, v in sorted(by.items(), key=lambda kv: -kv[1][1]):
    if v[1] >= 15:
        print(f"  {str(k):14s} strict {v[0]:5d}/{v[1]:5d} = {v[0]/v[1]:5.1%}   tie-aware {v[2]/v[1]:5.1%}")

print("\nMAIN decisions, by the ACTION TYPE he chose (n>=10):")
by = defaultdict(lambda: [0, 0, 0])
for r in rows:
    if r["stype"] != 0:
        continue
    k = "+".join(OTYPE.get(t, str(t)) for t in r["his_types"])
    by[k][0] += r["agree"]; by[k][1] += 1; by[k][2] += (r["agree"] or r["tie"])
for k, v in sorted(by.items(), key=lambda kv: -kv[1][1]):
    if v[1] >= 10:
        print(f"  {k:16s} strict {v[0]:5d}/{v[1]:5d} = {v[0]/v[1]:5.1%}   tie-aware {v[2]/v[1]:5.1%}")

print("\nMAIN REAL divergences (not ties), his type -> our type, top 20:")
c = Counter()
for r in rows:
    if r["stype"] == 0 and not r["agree"] and not r["tie"]:
        c[("+".join(OTYPE.get(t, str(t)) for t in r["his_types"]),
           "+".join(OTYPE.get(t, str(t)) for t in r["mine_types"]))] += 1
for (a, b), n in c.most_common(20):
    print(f"  {a:16s} -> {b:16s} {n}")
