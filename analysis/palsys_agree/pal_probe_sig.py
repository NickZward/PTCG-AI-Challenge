"""Play-signature / label helpers shared by pal_probe.py and pal_turnplays.py."""
import os
import np_common as NN
from cg.api import OptionType, AreaType, all_card_data

CARDS = {c.cardId: c.name for c in all_card_data()}
OT = {int(e): e.name for e in OptionType}
AT = {int(e): e.name for e in AreaType}
POSITIONAL = (int(AreaType.ACTIVE), int(AreaType.BENCH), int(AreaType.STADIUM))



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


