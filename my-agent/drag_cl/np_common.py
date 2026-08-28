#!/usr/bin/env python3
"""Torch-free twin of nn_common: same encoder/decoder feature builders, plus a pure-numpy
forward pass of MyModel for Kaggle deployment (the sandbox verifiably has numpy — az2 ran on
sklearn/numpy — while torch is unproven there and the first torch upload failed validation).

Weights come from export_numpy.py (state_dict -> .npz). Numerics validated against the torch
model: argmax agreement and logit deltas are checked in export_numpy.py itself.
API mirrors nn_common where mcts_agent needs it: SparseVector, get_encoder_input,
get_decoder_input, enumerate_actions, eval_nn(sv_enc, sv_dec, model), SEARCH_COUNT.
"""
import math

import numpy as np

from cg.api import (
    AreaType,
    Observation,
    OptionType,
    PlayerState,
    SelectContext,
    all_attack,
    all_card_data,
)

# ---- vocabulary constants (identical derivation to nn_common) ----
all_card = all_card_data()
card_count = max(all_card, key=lambda c: c.cardId).cardId + 1
attack_count = max(all_attack(), key=lambda a: a.attackId).attackId + 1
num_words_encoder = 24
encoder_size = 22000
decoder_main_feature = 8
decoder_attack_offset = 14
decoder_card_offset = decoder_attack_offset + attack_count
decoder_size = decoder_card_offset + (1 + decoder_main_feature + SelectContext.RECOVER_SPECIAL_CONDITION) * card_count
SEARCH_COUNT = 10

# FEAT v2 positional candidate block — MUST stay in sync with nn_common.py
posblock_offset = decoder_size
_PB_AREA, _PB_SLOT, _PB_HP, _PB_DMG, _PB_ENE, _PB_COPY = 0, 10, 19, 23, 24, 28
POSBLOCK = 36
decoder_size_v2 = decoder_size + POSBLOCK
DEFAULT_FEAT = [1]   # set to 2 by NpModel when a v2-vocab checkpoint is loaded


class SparseVector:
    def __init__(self):
        self.index = []
        self.value = []
        self.offset = []
        self.pos = 0

    def add(self, index, value):
        value = float(value)
        if value != 0.0:
            self.index.append(self.pos + index)
            self.value.append(value)

    def add_pos(self, pos):
        self.pos += pos

    def add_single(self, value):
        value = float(value)
        if value != 0.0:
            self.index.append(self.pos)
            self.value.append(value)
        self.pos += 1

    def word_start(self):
        self.offset.append(len(self.index))


def add_card(sv, card):
    if card is not None:
        sv.add(card.id, 1)
    sv.add_pos(card_count)


def add_cards(sv, cards, value):
    if cards is not None:
        for card in cards:
            sv.add(card.id, value)
    sv.add_pos(card_count)


def add_pokemon(sv, poke):
    if poke is None:
        sv.add_single(1)
        sv.add_pos(1 + 3 * card_count)
    else:
        sv.add_single(0)
        sv.add_single(poke.hp / 400)
        add_card(sv, poke)
        add_cards(sv, poke.tools, 1.0)
        add_cards(sv, poke.energyCards, 0.5)


def add_player(sv, ps):
    sv.add_single(ps.deckCount / 60)
    sv.add_single(len(ps.discard) / 60)
    sv.add_single(ps.handCount / 8)
    sv.add_single(len(ps.bench) / 5)
    sv.add(len(ps.prize), 1)
    sv.add_pos(7)
    sv.add_single(ps.poisoned)
    sv.add_single(ps.burned)
    sv.add_single(ps.asleep)
    sv.add_single(ps.paralyzed)
    sv.add_single(ps.confused)
    add_cards(sv, ps.discard, 0.25)


def get_encoder_input(obs, your_deck):
    your_index = obs.current.yourIndex
    state = obs.current
    sv = SparseVector()
    for i in range(2):
        ps = state.players[i ^ your_index]
        for j in range(8):
            sv.word_start()
            pos = sv.pos
            if j < len(ps.bench):
                add_pokemon(sv, ps.bench[j])
            else:
                add_pokemon(sv, None)
            if j != 7:
                sv.pos = pos
    for i in range(2):
        ps = state.players[i ^ your_index]
        sv.word_start()
        if 0 < len(ps.active):
            add_pokemon(sv, ps.active[0])
        else:
            add_pokemon(sv, None)
    for i in range(2):
        ps = state.players[i ^ your_index]
        sv.word_start()
        add_player(sv, ps)
    sv.word_start()
    add_cards(sv, state.players[your_index].hand, 0.25)
    sv.word_start()
    for cid in your_deck:
        sv.add(cid, 0.25)
    sv.add_pos(card_count)
    sv.word_start()
    add_cards(sv, state.stadium, 1.0)
    sv.word_start()
    sv.add_single(1)
    sv.add_single(state.turn / 10)
    sv.add_single(state.firstPlayer == your_index)
    return sv


def get_card(obs, area, index, player_index):
    ps = obs.current.players[player_index]
    if area == AreaType.DECK:
        return obs.select.deck[index]
    if area == AreaType.HAND:
        return ps.hand[index]
    if area == AreaType.DISCARD:
        return ps.discard[index]
    if area == AreaType.ACTIVE:
        return ps.active[index]
    if area == AreaType.BENCH:
        return ps.bench[index]
    if area == AreaType.PRIZE:
        return ps.prize[index]
    if area == AreaType.STADIUM:
        return obs.current.stadium[index]
    if area == AreaType.LOOKING:
        return obs.current.looking[index]
    return None


def decoder_main(sv, feature_index, card):
    if card is not None:
        sv.add(decoder_card_offset + feature_index * card_count + card.id, 1)


def decoder_card_id(sv, context, card_id):
    sv.add(decoder_card_offset + (decoder_main_feature + context) * card_count + card_id, 1)


def decoder_card(sv, context, card):
    if card is not None:
        decoder_card_id(sv, context, card.id)


def _pos_features(sv, obs, o, your_index):
    """FEAT v2 positional features for one option (mirror of nn_common._pos_features)."""
    area = getattr(o, "area", None)
    if area is None:
        return
    sv.add(posblock_offset + _PB_AREA + min(int(area), 9), 1)
    idx = getattr(o, "index", None)
    if idx is not None:
        sv.add(posblock_offset + _PB_COPY + min(int(idx), 7), 1)
    host = None
    slot = None
    ipa = getattr(o, "inPlayArea", None)
    ipi = getattr(o, "inPlayIndex", None)
    pi = getattr(o, "playerIndex", your_index)
    try:
        if ipa is not None and ipi is not None:
            host = get_card(obs, ipa, ipi, your_index)
            slot = 0 if ipa == AreaType.ACTIVE else 1 + min(int(ipi), 7)
        elif area in (AreaType.ACTIVE, AreaType.BENCH) and idx is not None:
            host = get_card(obs, area, idx, pi if pi is not None else your_index)
            slot = 0 if area == AreaType.ACTIVE else 1 + min(int(idx), 7)
    except Exception:
        host = None
    if slot is not None:
        sv.add(posblock_offset + _PB_SLOT + slot, 1)
    if host is not None:
        hp = getattr(host, "hp", None)
        mx = getattr(host, "maxHp", None) or 0
        if hp is not None and mx:
            sv.add(posblock_offset + _PB_HP + min(3, int(4 * max(0, min(hp, mx) - 1) / mx)), 1)
            if hp < mx:
                sv.add(posblock_offset + _PB_DMG, 1)
        ecs = getattr(host, "energyCards", None)
        if ecs is not None:
            sv.add(posblock_offset + _PB_ENE + min(len(ecs), 3), 1)


def get_decoder_input(obs, actions, feat=None):
    if feat is None:
        feat = DEFAULT_FEAT[0]
    sv = SparseVector()
    your_index = obs.current.yourIndex
    ps = obs.current.players[your_index]
    context = obs.select.context
    for action in actions:
        sv.word_start()
        if len(action) == 0:
            sv.add(0, 1)
            continue
        for i in action:
            o = obs.select.option[i]
            t = o.type
            if t == OptionType.END:
                sv.add(1, 1)
            elif t == OptionType.YES:
                sv.add(2, 1)
            elif t == OptionType.NO:
                sv.add(3, 1)
            elif t == OptionType.SPECIAL_CONDITION:
                sv.add(4 + o.specialConditionType, 1)
            elif t == OptionType.NUMBER:
                sv.add(9 + min(o.number, 4), 1)
            elif t == OptionType.ATTACK:
                sv.add(decoder_attack_offset + o.attackId, 1)
            elif t == OptionType.PLAY:
                decoder_main(sv, 0, ps.hand[o.index])
            elif t == OptionType.ATTACH:
                decoder_main(sv, 1, get_card(obs, o.area, o.index, your_index))
                decoder_main(sv, 2, get_card(obs, o.inPlayArea, o.inPlayIndex, your_index))
            elif t == OptionType.EVOLVE:
                decoder_main(sv, 3, get_card(obs, o.area, o.index, your_index))
                decoder_main(sv, 4, get_card(obs, o.inPlayArea, o.inPlayIndex, your_index))
            elif t == OptionType.ABILITY:
                decoder_main(sv, 5, get_card(obs, o.area, o.index, your_index))
            elif t == OptionType.DISCARD:
                decoder_main(sv, 6, get_card(obs, o.area, o.index, your_index))
            elif t == OptionType.RETREAT:
                decoder_main(sv, 7, ps.active[0])
            elif t == OptionType.CARD:
                decoder_card(sv, context, get_card(obs, o.area, o.index, o.playerIndex))
            elif t == OptionType.TOOL_CARD:
                card = get_card(obs, o.area, o.index, o.playerIndex)
                decoder_card(sv, context, card.tools[o.toolIndex])
            elif t == OptionType.ENERGY_CARD or t == OptionType.ENERGY:
                card = get_card(obs, o.area, o.index, o.playerIndex)
                decoder_card(sv, context, card.energyCards[o.energyIndex])
            elif t == OptionType.SKILL:
                decoder_card_id(sv, context, o.cardId)
            if feat >= 2:
                _pos_features(sv, obs, o, your_index)
    return sv


def enumerate_actions(select, cap=64):
    n_opt = len(select.option)
    max_count = select.maxCount
    actions = []
    indices = list(range(max_count))
    for _ in range(cap):
        actions.append(indices.copy())
        for i in range(len(indices)):
            index = len(indices) - i - 1
            if indices[index] < n_opt - i - 1:
                indices[index] += 1
                for j in range(index + 1, len(indices)):
                    indices[j] = indices[j - 1] + 1
                break
        else:
            break
    return actions


# ----------------------------------------------------------------------------------------
# numpy forward pass (exact port of nn_common.MyModel, batch size 1)
# ----------------------------------------------------------------------------------------
def _layernorm(x, w, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * w + b


def _mha(q_in, kv_in, W, B, Wo, Bo, heads):
    """torch.nn.MultiheadAttention forward, batch 1. q_in [Tq,E], kv_in [Tk,E]."""
    E = q_in.shape[1]
    hd = E // heads
    q = q_in @ W[:E].T + B[:E]
    k = kv_in @ W[E:2 * E].T + B[E:2 * E]
    v = kv_in @ W[2 * E:].T + B[2 * E:]
    q = q.reshape(-1, heads, hd).transpose(1, 0, 2)          # [h, Tq, hd]
    k = k.reshape(-1, heads, hd).transpose(1, 0, 2)
    v = v.reshape(-1, heads, hd).transpose(1, 0, 2)
    a = q @ k.transpose(0, 2, 1) / math.sqrt(hd)             # [h, Tq, Tk]
    a = a - a.max(-1, keepdims=True)
    a = np.exp(a)
    a /= a.sum(-1, keepdims=True)
    out = (a @ v).transpose(1, 0, 2).reshape(-1, E)          # [Tq, E]
    return out @ Wo.T + Bo


class NpModel:
    """Weights dict from export_numpy.py; forward mirrors nn_common.MyModel exactly."""

    def __init__(self, npz_path):
        z = np.load(npz_path)
        self.w = {k: z[k].astype(np.float32) for k in z.files}
        self.heads = int(self.w["_meta"][1])
        self.n_enc = int(self.w["_meta"][3])
        self.n_dec = int(self.w["_meta"][4])
        self.policy_tanh = bool(self.w["_meta"][5])
        self.d_model = int(self.w["_meta"][0])
        # v2-feature checkpoints have the positional block rows in the decoder table; route the
        # module-wide default so mcts_agent/agents encode candidates the way this net was trained
        self.feat = 2 if self.w["decoder_bag.weight"].shape[0] >= decoder_size_v2 else 1
        DEFAULT_FEAT[0] = self.feat

    def _bag(self, table, sv):
        """EmbeddingBag(mode=sum) with per_sample_weights."""
        starts = list(sv.offset) + [len(sv.index)]
        out = np.zeros((len(sv.offset), self.d_model), dtype=np.float32)
        idx = np.asarray(sv.index, dtype=np.int64)
        val = np.asarray(sv.value, dtype=np.float32)
        for wd in range(len(sv.offset)):
            s, e = starts[wd], starts[wd + 1]
            if e > s:
                out[wd] = (table[idx[s:e]] * val[s:e, None]).sum(0)
        return out

    def forward(self, sv_enc, sv_dec):
        w = self.w
        x = self._bag(w["encoder_bag.weight"], sv_enc)                       # [24, E]
        for i in range(self.n_enc):
            p = f"encoder.layers.{i}."
            y = _mha(x, x, w[p + "self_attn.in_proj_weight"], w[p + "self_attn.in_proj_bias"],
                     w[p + "self_attn.out_proj.weight"], w[p + "self_attn.out_proj.bias"], self.heads)
            x = _layernorm(x + y, w[p + "norm1.weight"], w[p + "norm1.bias"])
            y = np.maximum(x @ w[p + "linear1.weight"].T + w[p + "linear1.bias"], 0.0)
            y = y @ w[p + "linear2.weight"].T + w[p + "linear2.bias"]
            x = _layernorm(x + y, w[p + "norm2.weight"], w[p + "norm2.bias"])
        v = x @ w["encoder_fc.weight"].T + w["encoder_fc.bias"]
        value = float(np.tanh(v.mean()))

        d = self._bag(w["decoder_bag.weight"], sv_dec)                       # [C, E]
        for i in range(self.n_dec):
            p = f"decoder.{i}."
            y = _mha(d, x, w[p + "attention.in_proj_weight"], w[p + "attention.in_proj_bias"],
                     w[p + "attention.out_proj.weight"], w[p + "attention.out_proj.bias"], self.heads)
            res = _layernorm(d + y, w[p + "norm1.weight"], w[p + "norm1.bias"])
            y = np.maximum(res @ w[p + "fc1.weight"].T + w[p + "fc1.bias"], 0.0)
            y = y @ w[p + "fc2.weight"].T + w[p + "fc2.bias"]
            d = _layernorm(res + y, w[p + "norm2.weight"], w[p + "norm2.bias"])
        pol = (d @ w["decoder_fc.weight"].T + w["decoder_fc.bias"]).reshape(-1)
        if self.policy_tanh:
            pol = np.tanh(pol)
        return value, pol.tolist()


def eval_nn(sv_enc, sv_dec, model):
    """Same signature as nn_common.eval_nn -> (value, policy list)."""
    return model.forward(sv_enc, sv_dec)
