#!/usr/bin/env python3
"""Replay palsystem's own 149 games and record, at every decision HE faced, what ONE of our nets
would pick. One process per agent -> no mcts_agent/np_common module-sharing hazard.

Adapted from analysis/kdc_probe.py (the Grimmsnarl teacher study). Two equivalence notions:
  ENC group = byte-identical decoder encoding (net structurally cannot prefer one).
  PLAY sig  = the same GAME ACTION (collapses interchangeable copies of a card in a hidden zone).
Plus, for the within-turn-transposition test, every decision carries its (game, turn, step) and
the pro's chosen play-sig as a string so the analyser can ask "did he make OUR move later this
same turn?".

Usage: pal_probe.py <agent_dir> <out.jsonl>
"""
import os, sys, json

os.environ.setdefault("PTCG_STOP", "25")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

AGENT = os.path.abspath(sys.argv[1])
OUT = sys.argv[2]

sys.path.insert(0, AGENT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import np_common as NN
from cg.api import to_observation_class, OptionType, AreaType, all_card_data
from pal_files import palsystem_games

CARDS = {c.cardId: c.name for c in all_card_data()}
OT = {int(e): e.name for e in OptionType}
AT = {int(e): e.name for e in AreaType}
POSITIONAL = (int(AreaType.ACTIVE), int(AreaType.BENCH), int(AreaType.STADIUM))

MODEL = NN.NpModel(os.path.join(AGENT, "model_np.npz"))
DECK = [int(x) for x in open(os.path.join(AGENT, "deck.csv")).read().split()]
sys.stderr.write("loaded %s feat=%d policy_tanh=%s\n" % (AGENT, MODEL.feat, MODEL.policy_tanh))


def cid(card):
    return getattr(card, "id", None)


def cname(card):
    return "?" if card is None else CARDS.get(cid(card), "?%s" % cid(card))


def opt_sig(oc, i):
    yi = oc.current.yourIndex
    try:
        o = oc.select.option[i]
    except Exception:
        return ("opt", i)
    t = int(o.type)
    ps = oc.current.players[yi]
    try:
        if t == OptionType.END: return ("END",)
        if t == OptionType.YES: return ("YES",)
        if t == OptionType.NO: return ("NO",)
        if t == OptionType.NUMBER: return ("N", int(o.number))
        if t == OptionType.SPECIAL_CONDITION: return ("SC", int(o.specialConditionType))
        if t == OptionType.ATTACK: return ("ATTACK", int(o.attackId))
        if t == OptionType.RETREAT: return ("RETREAT",)
        if t == OptionType.PLAY: return ("PLAY", cid(ps.hand[o.index]))
        if t == OptionType.ATTACH:
            return ("ATTACH", cid(NN.get_card(oc, o.area, o.index, yi)), int(o.inPlayArea), int(o.inPlayIndex))
        if t == OptionType.EVOLVE:
            return ("EVOLVE", cid(NN.get_card(oc, o.area, o.index, yi)), int(o.inPlayArea), int(o.inPlayIndex))
        if t == OptionType.ABILITY:
            return ("ABILITY", cid(NN.get_card(oc, o.area, o.index, yi)), int(o.area), int(o.index))
        if t == OptionType.DISCARD:
            c = NN.get_card(oc, o.area, o.index, yi)
            return ("DISCARD", cid(c), int(o.area)) + ((int(o.index),) if int(o.area) in POSITIONAL else ())
        if t == OptionType.SKILL: return ("SKILL", int(o.cardId))
        if t == OptionType.TOOL_CARD:
            c = NN.get_card(oc, o.area, o.index, o.playerIndex)
            return ("TOOL", cid(c.tools[o.toolIndex]), int(o.area), int(o.index), int(o.playerIndex))
        if t in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            c = NN.get_card(oc, o.area, o.index, o.playerIndex)
            return ("EN", cid(c.energyCards[o.energyIndex]), int(o.area), int(o.index), int(o.playerIndex))
        if t == OptionType.CARD:
            c = NN.get_card(oc, o.area, o.index, o.playerIndex)
            base = ("CARD", cid(c), int(o.area), int(o.playerIndex))
            return base + ((int(o.index),) if int(o.area) in POSITIONAL else ())
    except Exception:
        pass
    return ("t%d" % t, i)


def opt_label(oc, i):
    yi = oc.current.yourIndex
    try:
        o = oc.select.option[i]
    except Exception:
        return "opt%d" % i
    t = int(o.type)
    ps = oc.current.players[yi]
    try:
        if t == OptionType.END: return "END"
        if t == OptionType.YES: return "YES"
        if t == OptionType.NO: return "NO"
        if t == OptionType.NUMBER: return "N=%s" % o.number
        if t == OptionType.SPECIAL_CONDITION: return "SC%s" % o.specialConditionType
        if t == OptionType.ATTACK: return "ATTACK:a%s" % o.attackId
        if t == OptionType.RETREAT: return "RETREAT:%s" % cname(ps.active[0] if ps.active else None)
        if t == OptionType.PLAY: return "PLAY:%s" % cname(ps.hand[o.index])
        if t == OptionType.ATTACH:
            return "ATTACH:%s>%s" % (cname(NN.get_card(oc, o.area, o.index, yi)),
                                     cname(NN.get_card(oc, o.inPlayArea, o.inPlayIndex, yi)))
        if t == OptionType.EVOLVE:
            return "EVOLVE:%s>%s" % (cname(NN.get_card(oc, o.area, o.index, yi)),
                                     cname(NN.get_card(oc, o.inPlayArea, o.inPlayIndex, yi)))
        if t == OptionType.ABILITY:
            return "ABILITY:%s" % cname(NN.get_card(oc, o.area, o.index, yi))
        if t == OptionType.DISCARD: return "DISCARD:%s" % cname(NN.get_card(oc, o.area, o.index, yi))
        if t == OptionType.SKILL: return "SKILL:%s" % CARDS.get(o.cardId, o.cardId)
        if t == OptionType.TOOL_CARD:
            return "TOOL:%s" % cname(NN.get_card(oc, o.area, o.index, o.playerIndex).tools[o.toolIndex])
        if t in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            c = NN.get_card(oc, o.area, o.index, o.playerIndex)
            return "EN:%s@%s%s" % (cname(c.energyCards[o.energyIndex]), AT.get(int(o.area), o.area), o.index)
        if t == OptionType.CARD:
            return "CARD:%s@%s%s%s" % (cname(NN.get_card(oc, o.area, o.index, o.playerIndex)),
                                       AT.get(int(o.area), o.area),
                                       o.index if int(o.area) in POSITIONAL else "",
                                       "" if o.playerIndex == yi else "(opp)")
    except Exception:
        pass
    return "%s?" % OT.get(t, t)


def act_label(oc, act):
    return "+".join(opt_label(oc, i) for i in act) if act else "(empty)"


def act_sig(oc, act, cache):
    out = []
    for i in act:
        if i not in cache:
            cache[i] = opt_sig(oc, i)
        out.append(cache[i])
    return tuple(sorted(out, key=repr))


def enc_groups(sv, n):
    starts = list(sv.offset) + [len(sv.index)]
    keys = [tuple(sorted(zip(sv.index[starts[k]:starts[k + 1]], sv.value[starts[k]:starts[k + 1]])))
            for k in range(n)]
    uniq, out = {}, []
    for k in keys:
        uniq.setdefault(k, len(uniq)); out.append(uniq[k])
    return out, len(uniq)


def main():
    G = palsystem_games()
    fo = open(OUT, "w")
    n_dec = n_err = 0
    for ep in sorted(G):
        v = G[ep]
        try:
            d = json.load(open(v["path"]))
        except Exception:
            continue
        pi = v["seat"]
        S = d["steps"]
        for t in range(len(S) - 1):
            e = S[t][pi]
            if e.get("status") != "ACTIVE":
                continue
            o = e.get("observation") or {}
            sel = o.get("select")
            if not sel:
                continue
            opts = sel.get("option") or []
            act = S[t + 1][pi].get("action")
            if not isinstance(act, list) or not act:
                continue
            if not all(isinstance(x, int) and 0 <= x < len(opts) for x in act):
                continue
            wrapped = {"current": o.get("current"), "select": sel, "logs": o.get("logs", []),
                       "step": t, "remainingOverageTime": 600,
                       "search_begin_input": o.get("search_begin_input")}
            try:
                oc = to_observation_class(wrapped)
                if oc.current.yourIndex != pi:
                    continue
                actions = NN.enumerate_actions(oc.select, cap=64)
                if len(actions) <= 1:
                    continue
                sv_enc = NN.get_encoder_input(oc, DECK)
                sv_dec = NN.get_decoder_input(oc, actions)
                value, policy = NN.eval_nn(sv_enc, sv_dec, MODEL)
                sc = {}
                sigs = [act_sig(oc, a, sc) for a in actions]
                hsig = act_sig(oc, sorted(act), sc)
                turn = int(oc.current.turn)
                fp = int(oc.current.firstPlayer)
                # no turn-player field in the observation; turn 1 belongs to firstPlayer and
                # alternates, so turnPlayer = fp when turn is odd.
                is_own = int((fp if turn % 2 == 1 else 1 - fp) == pi) if turn >= 1 else -1
            except Exception:
                n_err += 1
                continue
            pol = np.asarray(policy[:len(actions)], dtype=np.float64)
            order = [int(x) for x in np.argsort(-pol, kind="stable")]
            groups, ngroups = enc_groups(sv_dec, len(actions))

            sig_ids, sid = [], {}
            for s in sigs:
                sid.setdefault(s, len(sid)); sig_ids.append(sid[s])
            best = {}
            for k in order:
                best.setdefault(sig_ids[k], k)
            play_order = [best[g] for g in sorted(best, key=lambda g: -pol[best[g]])]
            play_rank_of = {sig_ids[k]: r for r, k in enumerate(play_order)}

            hs = sorted(act)
            hidx = next((k for k, a in enumerate(actions) if sorted(a) == hs), -1)
            hsig_id = sid.get(hsig, -1)
            top = order[0]
            rec = {
                "ep": ep, "t": t, "seat": pi, "turn": turn, "own": is_own, "fp": fp,
                "tac": int(getattr(oc.current, "turnActionCount", -1)),
                "stype": int(sel.get("type")), "sctx": int(sel.get("context")),
                "nopt": len(opts), "ncand": len(actions), "ngroups": ngroups, "nplays": len(sid),
                "hidx": hidx, "top": top,
                "rank": order.index(hidx) if hidx >= 0 else -1,
                "top3": order[:3],
                "hgrp": groups[hidx] if hidx >= 0 else -1, "tgrp": groups[top],
                "hsig": hsig_id, "tsig": sig_ids[top],
                "hsig_s": repr(hsig) if hidx >= 0 else "",
                "tsig_s": repr(sigs[top]),
                "top3sig_s": [repr(sigs[k]) for k in order[:3]],
                "hsig_n": sum(1 for x in sig_ids if x == hsig_id) if hsig_id >= 0 else 0,
                "play_rank": play_rank_of.get(hsig_id, -1),
                "p_top": float(pol[top]), "p_h": float(pol[hidx]) if hidx >= 0 else None,
                "value": float(value),
                "hlab": act_label(oc, actions[hidx]) if hidx >= 0 else act_label(oc, hs),
                "tlab": act_label(oc, actions[top]),
            }
            fo.write(json.dumps(rec) + "\n")
            n_dec += 1
    fo.close()
    sys.stderr.write("decisions=%d errors=%d\n" % (n_dec, n_err))


main()
