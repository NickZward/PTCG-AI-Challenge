#!/usr/bin/env python3
"""Canonical Transformer encoder/decoder + model, ported faithfully from the competition's
official RL/MCTS reference notebook, adapted to import from our local cg-lib.

This is the AUTHORITATIVE feature encoding (replaces our reverse-engineered bc_features):
  - get_encoder_input(obs, your_deck) -> SparseVector  (full board state, 24 "word" tokens)
  - get_decoder_input(obs, actions)   -> SparseVector  (one token per candidate action combo)
  - MyModel(value_head, policy_head)  Transformer over EmbeddingBag-summed sparse features

Shared by:  validate_encoder.py (step 1),  the Transformer+MCTS agent (step 2),  training (step 3).

Constants are derived from the live card DB at import (card_count / attack_count), so this stays
correct as the card set changes and is drop-in for the Kaggle runtime.
"""
import math
import random

import torch
import torch.nn
import torch.nn.functional

from cg.api import (
    AreaType,
    Card,
    Observation,
    OptionType,
    PlayerState,
    Pokemon,
    SelectContext,
    all_attack,
    all_card_data,
)

# ----------------------------------------------------------------------------------------
# Card / attack reference data + vocabulary sizes (identical derivation to the reference)
# ----------------------------------------------------------------------------------------
all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}
card_count = max(all_card, key=lambda c: c.cardId).cardId + 1          # max cardId + 1  (== 1268 today)
attack_count = max(all_attack(), key=lambda a: a.attackId).attackId + 1  # max attackId + 1 (== 1557 today)

num_words_encoder = 24     # number of "word" tokens the encoder sequence holds
encoder_size = 22000       # encoder input vocab (must exceed max encoder feature index; traced max 21599)

decoder_main_feature = 8                                   # feature count of SelectContext.Main
decoder_attack_offset = 14                                 # first index of the Attack feature block
decoder_card_offset = decoder_attack_offset + attack_count  # first index of the Card feature block
decoder_size = decoder_card_offset + (1 + decoder_main_feature + SelectContext.RECOVER_SPECIAL_CONDITION) * card_count

# ---- FEAT v2: positional candidate block (appended AFTER the reference features) -------------
# The reference decoder encodes a candidate as (feature_slot, card_id) only — no board position.
# Measured cost: 60.7% of decisions contain byte-identical candidate bags, and 11.5% of decisions
# hide a REAL board difference behind them (same card id on a different Pokemon / another copy).
# v2 appends WHERE-features so those twins become distinguishable. Old models ignore the block
# (their embedding tables simply don't have these rows); v2 models are built with
# decoder_vocab=decoder_size_v2 and trained on v2-extracted data.
posblock_offset = decoder_size
_PB_AREA = 0            # + area id (0..9)                      : which zone the pick lives in
_PB_SLOT = 10           # + slot (0=active, 1..8=bench index)    : which in-play Pokemon hosts it
_PB_HP = 19             # + hp bucket 0..3 (hp/maxHp quartile)   : host health state
_PB_DMG = 23            # + 1 if host is damaged
_PB_ENE = 24            # + min(energy count,3) 0..3             : host energization
_PB_COPY = 28           # + min(index in area,7) 0..7            : which COPY of a duplicate card
POSBLOCK = 36
decoder_size_v2 = decoder_size + POSBLOCK

SEARCH_COUNT = 10          # MCTS simulations per decision (agent/self-play default; overridable)


# ----------------------------------------------------------------------------------------
# torch.nn.EmbeddingBag input builder
# ----------------------------------------------------------------------------------------
class SparseVector:
    def __init__(self):
        self.index = []
        self.value = []
        self.offset = []
        self.pos = 0

    def add(self, index: int, value):
        value = float(value)
        if value != 0.0:
            self.index.append(self.pos + index)
            self.value.append(value)

    def add_pos(self, pos: int):
        self.pos += pos

    def add_single(self, value):
        value = float(value)
        if value != 0.0:
            self.index.append(self.pos)
            self.value.append(value)
        self.pos += 1

    def word_start(self):
        self.offset.append(len(self.index))


# ---- encoder feature helpers ----
def add_card(sv: SparseVector, card):
    if card is not None:
        sv.add(card.id, 1)
    sv.add_pos(card_count)


def add_cards(sv: SparseVector, cards, value: float):
    if cards is not None:
        for card in cards:
            sv.add(card.id, value)
    sv.add_pos(card_count)


def add_pokemon(sv: SparseVector, poke):
    if poke is None:
        sv.add_single(1)
        sv.add_pos(1 + 3 * card_count)
    else:
        sv.add_single(0)
        sv.add_single(poke.hp / 400)
        add_card(sv, poke)
        add_cards(sv, poke.tools, 1.0)
        add_cards(sv, poke.energyCards, 0.5)


def add_player(sv: SparseVector, ps: PlayerState):
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


def get_encoder_input(obs: Observation, your_deck) -> SparseVector:
    your_index = obs.current.yourIndex
    state = obs.current

    sv = SparseVector()
    for i in range(2):
        ps = state.players[i ^ your_index]
        for j in range(8):  # bench (8 word-slots; slots share feature range, differ as tokens)
            sv.word_start()
            pos = sv.pos
            if j < len(ps.bench):
                add_pokemon(sv, ps.bench[j])
            else:
                add_pokemon(sv, None)
            if j != 7:            # all but the last reset pos (shared range)
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


def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
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


# ---- decoder feature helpers ----
def decoder_main(sv: SparseVector, feature_index: int, card):
    if card is not None:
        sv.add(decoder_card_offset + feature_index * card_count + card.id, 1)


def decoder_card_id(sv: SparseVector, context: int, card_id: int):
    sv.add(decoder_card_offset + (decoder_main_feature + context) * card_count + card_id, 1)


def decoder_card(sv: SparseVector, context: int, card):
    if card is not None:
        decoder_card_id(sv, context, card.id)


def _pos_features(sv: SparseVector, obs, o, your_index):
    """FEAT v2 positional features for one option (see posblock constants above)."""
    area = getattr(o, "area", None)
    if area is None:
        return
    sv.add(posblock_offset + _PB_AREA + min(int(area), 9), 1)
    idx = getattr(o, "index", None)
    if idx is not None:
        sv.add(posblock_offset + _PB_COPY + min(int(idx), 7), 1)
    # host in-play Pokemon: explicit target (ATTACH/EVOLVE) or the picked in-play card itself
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


def get_decoder_input(obs: Observation, actions, feat: int = 1) -> SparseVector:
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


# ----------------------------------------------------------------------------------------
# Model (identical architecture to the reference)
# ----------------------------------------------------------------------------------------
class DecoderLayer(torch.nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_feedforward: int):
        super().__init__()
        self.attention = torch.nn.MultiheadAttention(d_model, num_heads)
        self.fc1 = torch.nn.Linear(d_model, d_feedforward)
        self.fc2 = torch.nn.Linear(d_feedforward, d_model)
        self.norm1 = torch.nn.LayerNorm(d_model)
        self.norm2 = torch.nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, encoder_out: torch.Tensor) -> torch.Tensor:
        y, _ = self.attention(x, encoder_out, encoder_out, need_weights=False)
        res = self.norm1(x + y)
        y = self.fc1(res)
        y = torch.nn.functional.relu(y)
        y = self.fc2(y)
        return self.norm2(res + y)


class MyModel(torch.nn.Module):
    """policy_tanh=True reproduces the reference head exactly (tanh-squashed per-action score,
    trained by regression to +/-1). policy_tanh=False emits RAW LOGITS for softmax cross-entropy
    imitation — argmax is identical either way (tanh is monotonic), but CE needs unsquashed
    logits or the gradients die at saturation. The choice is persisted in model_arch.json."""

    def __init__(self, d_model, num_heads, d_feedforward, num_layers_encoder, num_layers_decoder,
                 policy_tanh=True, decoder_vocab=None):
        super().__init__()
        self.d_model = d_model
        self.policy_tanh = policy_tanh
        self.decoder_vocab = decoder_vocab or decoder_size   # v2-feature models pass decoder_size_v2
        self.encoder_bag = torch.nn.EmbeddingBag(encoder_size, d_model, mode="sum")
        encoder_layer = torch.nn.TransformerEncoderLayer(d_model, num_heads, d_feedforward, 0)
        self.encoder = torch.nn.TransformerEncoder(encoder_layer, num_layers_encoder, enable_nested_tensor=False)
        self.encoder_fc = torch.nn.Linear(d_model, 1)
        self.decoder_bag = torch.nn.EmbeddingBag(self.decoder_vocab, d_model, mode="sum")
        self.decoder = torch.nn.ModuleList()
        for _ in range(num_layers_decoder):
            self.decoder.append(DecoderLayer(d_model, num_heads, d_feedforward))
        self.decoder_fc = torch.nn.Linear(d_model, 1)

    def forward(self, index_encoder, value_encoder, offset_encoder,
                index_decoder, value_decoder, offset_decoder):
        v = self.encoder_bag(index_encoder, offset_encoder, value_encoder)
        v = v.reshape(-1, num_words_encoder, self.d_model).transpose(0, 1)
        batch_size = v.size(1)
        encoder_out = self.encoder(v)
        v = self.encoder_fc(encoder_out)
        v = torch.tanh(v.mean(0))

        p = self.decoder_bag(index_decoder, offset_decoder, value_decoder)
        p = p.reshape(batch_size, -1, self.d_model).transpose(0, 1)
        for layer in self.decoder:
            p = layer(p, encoder_out)
        p = self.decoder_fc(p)
        p = p.transpose(0, 1).view(batch_size, -1)
        if self.policy_tanh:
            p = torch.tanh(p)
        return (v, p)


def eval_nn(sv_enc: SparseVector, sv_dec: SparseVector, model: MyModel):
    """Run the model on one state (sv_enc) + its candidate actions (sv_dec).
    Returns (value: float, policy: list[float]) — value in [-1,1], one policy logit per action."""
    device = next(model.parameters()).device
    value, policy = model(
        torch.tensor(sv_enc.index, dtype=torch.int32, device=device),
        torch.tensor(sv_enc.value, dtype=torch.float32, device=device),
        torch.tensor(sv_enc.offset, dtype=torch.int32, device=device),
        torch.tensor(sv_dec.index, dtype=torch.int32, device=device),
        torch.tensor(sv_dec.value, dtype=torch.float32, device=device),
        torch.tensor(sv_dec.offset, dtype=torch.int32, device=device),
    )
    return (value.tolist()[0][0], policy.tolist()[0])


def enumerate_actions(select, cap: int = 64):
    """Enumerate up to `cap` action combinations of size select.maxCount over the options,
    in the exact combinatorial order the reference uses (so decoder tokens line up)."""
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
