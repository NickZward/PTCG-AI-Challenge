"""Rule-based agent for the Mega Lucario ex deck.

Strategy:
  * Setup: put Riolu in the Active Spot, bench every other Riolu.
  * Evolve Riolu -> Mega Lucario ex as soon as possible.
  * Attach an Energy every turn (active first until it can attack, then bench).
  * Play search/draw Trainers with a fixed priority.
  * Attack: pick the cheapest attack that KOs, otherwise the biggest attack.
Every branch falls back to a safe random-but-valid selection.
"""

import os
import random

from cg.api import (
    Observation,
    to_observation_class,
    AreaType,
    CardType,
    OptionType,
    SelectType,
    SelectContext,
)

# ---------------------------------------------------------------- constants

MEGA_LUCARIO = 678
RIOLU = 677
F_ENERGY = 6
ROCK_F_ENERGY = 20

MAXIMUM_BELT = 1158
MEGA_SIGNAL = 1145
FIGHTING_GONG = 1142
POKEGEAR = 1122
SWITCH = 1123
NIGHT_STRETCHER = 1097
PREMIUM_POWER = 1141

CYRANO = 1205
BLACK_BELT = 1211
CHEREN = 1224
URBAIN = 1236
LILLIE = 1227
WAITRESS = 1235
TARRAGON = 1238

ENERGY_IDS = {F_ENERGY, ROCK_F_ENERGY}
POKEMON_IDS = {MEGA_LUCARIO, RIOLU}

# What we want most when searching cards into hand / onto bench.
FETCH_PRIORITY = [MEGA_LUCARIO, RIOLU, F_ENERGY, CYRANO, CHEREN, URBAIN,
                  MEGA_SIGNAL, FIGHTING_GONG, ROCK_F_ENERGY]

# Cards we are happiest to throw away when forced to discard.
DISCARD_PRIORITY = [PREMIUM_POWER, SWITCH, POKEGEAR, ROCK_F_ENERGY, F_ENERGY,
                    NIGHT_STRETCHER, WAITRESS, LILLIE, TARRAGON, BLACK_BELT,
                    URBAIN, CHEREN, FIGHTING_GONG, MEGA_SIGNAL, CYRANO,
                    MAXIMUM_BELT, RIOLU, MEGA_LUCARIO]

ATTACK_DAMAGE = {981: 30, 982: 130, 983: 270}  # Accelerating Stab / Aura Jab / Mega Brave


# ---------------------------------------------------------------- helpers

def read_deck_csv() -> list[int]:
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        csv = file.read().split("\n")
    return [int(csv[i]) for i in range(60)]


def safe_fallback(select) -> list[int]:
    """Always-valid selection."""
    n = max(select.minCount, min(1, select.maxCount))
    return random.sample(range(len(select.option)), n)


def card_at(obs, area, index, player_index):
    """Resolve an option's (area, index, playerIndex) to a card-ish object with .id."""
    st = obs.current
    try:
        if area == AreaType.HAND:
            hand = st.players[player_index].hand
            return hand[index] if hand else None
        if area == AreaType.ACTIVE:
            return st.players[player_index].active[index]
        if area == AreaType.BENCH:
            return st.players[player_index].bench[index]
        if area == AreaType.DISCARD:
            return st.players[player_index].discard[index]
        if area == AreaType.STADIUM:
            return st.stadium[index]
        if area == AreaType.LOOKING:
            return st.looking[index] if st.looking else None
        if area == AreaType.DECK:
            deck = obs.select.deck
            return deck[index] if deck else None
        if area == AreaType.PRIZE:
            return st.players[player_index].prize[index]
    except (IndexError, TypeError):
        return None
    return None


def option_card_id(obs, opt):
    """Best-effort card id for a CARD-like option."""
    if opt.cardId is not None:
        return opt.cardId
    if opt.area is None or opt.index is None:
        return None
    pi = opt.playerIndex if opt.playerIndex is not None else obs.current.yourIndex
    card = card_at(obs, opt.area, opt.index, pi)
    return getattr(card, "id", None) if card is not None else None


def me(obs):
    return obs.current.players[obs.current.yourIndex]


def opp(obs):
    return obs.current.players[1 - obs.current.yourIndex]


def energy_count(pokemon) -> int:
    return len(pokemon.energies) if pokemon and pokemon.energies else 0


def pick_by_priority(obs, select, priority, count=None):
    """Pick option indices whose card ids appear earliest in `priority`."""
    scored = []
    for i, o in enumerate(select.option):
        cid = option_card_id(obs, o)
        rank = priority.index(cid) if cid in priority else len(priority)
        scored.append((rank, i))
    scored.sort()
    want = count if count is not None else max(select.minCount, min(1, select.maxCount))
    want = max(select.minCount, min(want, select.maxCount))
    return [i for _, i in scored[:want]]


# ---------------------------------------------------------------- main phase

def choose_main(obs) -> list[int]:
    st = obs.current
    my = me(obs)
    select = obs.select

    evolve, attach, plays, attacks, end_idx = [], [], [], [], None
    for i, o in enumerate(select.option):
        if o.type == OptionType.EVOLVE:
            evolve.append((i, o))
        elif o.type == OptionType.ATTACH:
            attach.append((i, o))
        elif o.type == OptionType.PLAY:
            plays.append((i, o))
        elif o.type == OptionType.ATTACK:
            attacks.append((i, o))
        elif o.type == OptionType.END:
            end_idx = i

    # 1. Evolve whenever possible (Riolu -> Mega Lucario ex).
    if evolve:
        return [evolve[0][0]]

    # 2. Attach energy: active first until it has 2, then the neediest bench mon.
    if attach and not st.energyAttached:
        def target_score(o):
            if o.inPlayArea == AreaType.ACTIVE:
                pkm = my.active[o.inPlayIndex] if my.active else None
                base = 0 if energy_count(pkm) < 2 else 2
            else:
                pkm = my.bench[o.inPlayIndex] if o.inPlayIndex < len(my.bench) else None
                base = 1 if (pkm and pkm.id == MEGA_LUCARIO and energy_count(pkm) < 2) else 3
            # prefer attaching basic F energy over special
            hand = my.hand or []
            src = hand[o.index].id if (o.area == AreaType.HAND and o.index < len(hand)) else None
            return (base, 0 if src == F_ENERGY else 1)
        best = min(attach, key=lambda t: target_score(t[1]))
        return [best[0]]

    # 3. Play trainers / bench Pokemon with a priority list.
    hand = my.hand or []
    have_mega_in_hand = any(c.id == MEGA_LUCARIO for c in hand)
    n_bench = len(my.bench)
    active_is_riolu = bool(my.active and my.active[0] and my.active[0].id == RIOLU)
    bench_has_ready_mega = any(p.id == MEGA_LUCARIO and energy_count(p) >= 1 for p in my.bench)

    def play_priority(cid):
        if cid == RIOLU and n_bench < 4:
            return 0                       # bench more Riolu
        if cid == MEGA_SIGNAL and not have_mega_in_hand:
            return 1
        if cid == CYRANO and not have_mega_in_hand:
            return 2
        if cid == FIGHTING_GONG:
            return 3
        if cid == MAXIMUM_BELT:
            return 4
        if cid in (CHEREN, URBAIN):
            return 5
        if cid == LILLIE and len(hand) <= 3:
            return 6
        if cid == WAITRESS:
            return 7
        if cid == NIGHT_STRETCHER:
            return 8
        if cid == TARRAGON:
            return 9
        if cid == POKEGEAR:
            return 10
        if cid == SWITCH and active_is_riolu and bench_has_ready_mega:
            return 2  # urgent: get the Mega up front
        if cid == BLACK_BELT:
            return 11 if attacks else 99
        if cid == PREMIUM_POWER:
            return 12 if attacks else 99
        return 99  # everything else: don't play

    best_play, best_rank = None, 99
    for i, o in enumerate(plays):
        idx, opt = o
        cid = hand[opt.index].id if opt.index is not None and opt.index < len(hand) else None
        r = play_priority(cid) if cid is not None else 99
        if r < best_rank:
            best_rank, best_play = r, idx
    if best_play is not None and best_rank < 99:
        return [best_play]

    # 4. Attack: cheapest that KOs, else biggest.
    if attacks:
        opp_active = opp(obs).active
        opp_hp = opp_active[0].hp if (opp_active and opp_active[0]) else 999
        best = None
        for i, o in attacks:
            dmg = ATTACK_DAMAGE.get(o.attackId, 50)
            kills = dmg >= opp_hp
            key = (0, dmg) if kills else (1, -dmg)   # prefer KO w/ smallest dmg, else max dmg
            if best is None or key < best[0]:
                best = (key, i)
        return [best[1]]

    # 5. Nothing useful left.
    if end_idx is not None:
        return [end_idx]
    return safe_fallback(select)


# ---------------------------------------------------------------- selections

def choose_cards(obs) -> list[int]:
    select = obs.select
    ctx = select.context

    if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
        return pick_by_priority(obs, select, [RIOLU], count=1)

    if ctx == SelectContext.SETUP_BENCH_POKEMON:
        return pick_by_priority(obs, select, [RIOLU], count=select.maxCount)

    if ctx in (SelectContext.TO_HAND, SelectContext.TO_FIELD, SelectContext.TO_BENCH):
        # deck searches: grab what the deck needs most
        return pick_by_priority(obs, select, FETCH_PRIORITY, count=select.maxCount)

    if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
        # promote the Pokemon with the most energy / biggest body
        def score(i):
            o = select.option[i]
            pi = o.playerIndex if o.playerIndex is not None else obs.current.yourIndex
            card = card_at(obs, o.area, o.index, pi)
            if card is None:
                return (9, 0)
            cid = getattr(card, "id", None)
            en = energy_count(card) if hasattr(card, "energies") else 0
            return (0 if cid == MEGA_LUCARIO else 1, -en)
        idxs = sorted(range(len(select.option)), key=score)
        n = max(select.minCount, min(1, select.maxCount))
        return idxs[:n]

    if ctx in (SelectContext.DISCARD, SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM,
               SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
        return pick_by_priority(obs, select, DISCARD_PRIORITY, count=select.minCount or select.maxCount)

    if ctx in (SelectContext.ATTACH_FROM, SelectContext.ATTACH_TO, SelectContext.EFFECT_TARGET):
        # e.g. Aura Jab refuel / Waitress target: feed benched Mega Lucario first
        return pick_by_priority(obs, select, [MEGA_LUCARIO, RIOLU, F_ENERGY, ROCK_F_ENERGY],
                                count=select.maxCount)

    if ctx in (SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER):
        return pick_by_priority(obs, select, [MEGA_LUCARIO, RIOLU], count=select.maxCount)

    # opponent-facing choices (damage, gust targets): hit whatever has least HP
    if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
        def hp_score(i):
            o = select.option[i]
            pi = o.playerIndex if o.playerIndex is not None else 1 - obs.current.yourIndex
            card = card_at(obs, o.area, o.index, pi)
            return getattr(card, "hp", 999) or 999
        idxs = sorted(range(len(select.option)), key=hp_score)
        n = max(select.minCount, min(select.maxCount, len(idxs)))
        return idxs[:n]

    # generic: take the maximum allowed of our favourite cards
    return pick_by_priority(obs, select, FETCH_PRIORITY, count=select.maxCount)


def choose_yes_no(obs) -> list[int]:
    select = obs.select
    ctx = select.context
    yes_idx = next((i for i, o in enumerate(select.option) if o.type == OptionType.YES), 0)
    no_idx = next((i for i, o in enumerate(select.option) if o.type == OptionType.NO), 0)
    if ctx in (SelectContext.IS_FIRST, SelectContext.ACTIVATE, SelectContext.FIRST_EFFECT,
               SelectContext.COIN_HEAD, SelectContext.MULLIGAN):
        return [yes_idx]
    if ctx == SelectContext.MORE_DEVOLVE:
        return [no_idx]
    return [yes_idx]


def choose_attack(obs) -> list[int]:
    select = obs.select
    opp_active = opp(obs).active
    opp_hp = opp_active[0].hp if (opp_active and opp_active[0]) else 999
    best = None
    for i, o in enumerate(select.option):
        dmg = ATTACK_DAMAGE.get(o.attackId, 50)
        kills = dmg >= opp_hp
        key = (0, dmg) if kills else (1, -dmg)
        if best is None or key < best[0]:
            best = (key, i)
    return [best[1]] if best else safe_fallback(select)


def choose_count(obs) -> list[int]:
    # draw / heal as much as possible
    select = obs.select
    best_i, best_n = 0, -1
    for i, o in enumerate(select.option):
        n = o.number if o.number is not None else 0
        if n > best_n:
            best_i, best_n = i, n
    return [best_i]


# ---------------------------------------------------------------- entrypoint

def _validate(result, select) -> list[int]:
    """Guarantee the returned indices are legal."""
    try:
        result = [int(x) for x in result]
        result = list(dict.fromkeys(x for x in result if 0 <= x < len(select.option)))
        if len(result) > select.maxCount:
            result = result[: select.maxCount]
        while len(result) < select.minCount:
            extra = [i for i in range(len(select.option)) if i not in result]
            if not extra:
                break
            result.append(random.choice(extra))
        return result
    except Exception:
        return safe_fallback(select)


def agent(obs_dict: dict) -> list[int]:
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()

    select = obs.select
    try:
        t = select.type
        if t == SelectType.MAIN:
            result = choose_main(obs)
        elif t in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD):
            result = choose_cards(obs)
        elif t == SelectType.YES_NO:
            result = choose_yes_no(obs)
        elif t == SelectType.ATTACK:
            result = choose_attack(obs)
        elif t == SelectType.COUNT:
            result = choose_count(obs)
        elif t == SelectType.EVOLVE:
            result = [0]
        elif t == SelectType.ENERGY:
            # discard basic F first (they come back via Aura Jab), keep specials
            result = pick_by_priority(obs, select, [F_ENERGY, ROCK_F_ENERGY],
                                      count=max(select.minCount, 1))
        else:
            result = safe_fallback(select)
    except Exception:
        result = safe_fallback(select)

    return _validate(result, select)
