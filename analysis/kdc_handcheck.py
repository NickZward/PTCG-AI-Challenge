#!/usr/bin/env python3
"""HAND-VERIFY the comparison on one concrete decision: print the raw option list from the
replay, the raw action bytes he sent, our enumerated candidates, and our net's pick — so the
raw-int-vs-canonical-action encoding bug that bit agree_general.py cannot hide here."""
import os, sys, json
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
AG = "/Users/nickzwart/Desktop/PTCG-AI-Challenge/my-agent/grimm_kdpol"
sys.path.insert(0, AG)
import numpy as np, np_common as NN
from cg.api import to_observation_class, all_card_data, OptionType
CARDS = {c.cardId: c.name for c in all_card_data()}
M = NN.NpModel(AG + "/model_np.npz")
DECK = [int(x) for x in open(AG + "/deck.csv").read().split()]

fn, T, PI = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
S = json.load(open("/Users/nickzwart/Desktop/kdcyberdude/" + fn))["steps"]
e = S[T][PI]
o = e["observation"]
sel = o["select"]
print("step", T, "seat", PI, "status", e["status"], "turn", o["current"]["turn"])
print("select type=%s context=%s min=%s max=%s  n_opt=%d" %
      (sel["type"], sel["context"], sel["minCount"], sel["maxCount"], len(sel["option"])))
print("RAW action recorded at step %d (next step, per the off-by-one law): %s" % (T + 1, S[T + 1][PI]["action"]))
print("RAW action recorded at step %d (same step)                       : %s" % (T, S[T]["action"] if isinstance(S[T], dict) else S[T][PI]["action"]))
w = {"current": o["current"], "select": sel, "logs": o.get("logs", []), "step": T,
     "remainingOverageTime": 600, "search_begin_input": o.get("search_begin_input")}
oc = to_observation_class(w)
ps = oc.current.players[oc.current.yourIndex]
acts = NN.enumerate_actions(oc.select, cap=64)
sv_e = NN.get_encoder_input(oc, DECK); sv_d = NN.get_decoder_input(oc, acts)
val, pol = NN.eval_nn(sv_e, sv_d, M)
starts = list(sv_d.offset) + [len(sv_d.index)]
print("\n idx  policy   encoding-hash            option")
order = list(np.argsort(-np.asarray(pol[:len(acts)])))
his = sorted(S[T + 1][PI]["action"])
for k in range(len(acts)):
    s, en = starts[k], starts[k + 1]
    h = hash(tuple(sorted(zip(sv_d.index[s:en], sv_d.value[s:en])))) & 0xffffff
    op = oc.select.option[acts[k][0]]
    t = int(op.type)
    d = OptionType(t).name
    try:
        if t == OptionType.PLAY: d += ":" + CARDS[ps.hand[op.index].id]
        elif t == OptionType.ABILITY: d += ":" + CARDS[NN.get_card(oc, op.area, op.index, oc.current.yourIndex).id]
        elif t == OptionType.ATTACH: d += ":%s->%s" % (CARDS[NN.get_card(oc, op.area, op.index, oc.current.yourIndex).id],
                                                       CARDS[NN.get_card(oc, op.inPlayArea, op.inPlayIndex, oc.current.yourIndex).id])
        elif t == OptionType.EVOLVE: d += ":%s->%s" % (CARDS[NN.get_card(oc, op.area, op.index, oc.current.yourIndex).id],
                                                       CARDS[NN.get_card(oc, op.inPlayArea, op.inPlayIndex, oc.current.yourIndex).id])
        elif t == OptionType.CARD: d += ":%s(area%s,i%s)" % (CARDS[NN.get_card(oc, op.area, op.index, op.playerIndex).id], int(op.area), op.index)
    except Exception:
        pass
    mark = ""
    if sorted(acts[k]) == his: mark += "  <== HIS MOVE"
    if k == order[0]: mark += "  <== OUR PICK"
    print("%4d %8.3f  %8x  cand=%-10s %s%s" % (k, pol[k], h, acts[k], d, mark))
