"""Rule-based agent v3 — config-driven pilot with bench-safety.

v3 upgrades (from ladder loss analysis of 36 real games):
  * BENCH SAFETY: 9 of 19 ladder losses were "KO with empty bench" — now the
    agent benches a Basic before doing anything else whenever reserves are low.
  * Rare Candy support (Basic -> Stage 2).
  * Conditional ability use (e.g. Run Away Draw only when it can't strand us).
  * Special-cased dynamic attack damage (Powerful Hand etc.).
  * Trigger-energy preference (Enriching/Telepath attach-triggers first).
"""

import os
import random

from cg.api import (
    Observation,
    to_observation_class,
    AreaType,
    OptionType,
    SelectType,
    SelectContext,
)

# ================= DECK CONFIG (replaced per deck) =================
CONFIG = {
 'MY_TYPE': 7,
 'BASICS': [646, 112, 860],
 'STAGE2S': {648},
 'MIN_BENCH': 3,
 'ABILITIES': {112, 1259},
 'DRAW_ABILITIES': {1259},
 'EVOLVE_ORDER': [648, 647, 104],
 'TRIGGER_ENERGY': set(),
 'ATTACH_TARGETS': [648, 112, 647, 646],
 'ENERGY_CAP': 2,
 'FETCH_PRIORITY': [648, 647, 646, 1079, 112, 7, 104, 860, 1219, 1227],
 'SETUP_PRIORITY': [646, 112, 860],
 'PROMOTE_PRIORITY': [648, 112, 647, 646, 104, 860],
 'DISCARD_PRIORITY': [1122, 1137, 1080, 1097, 1259, 1182, 7, 1152, 1086, 1219, 1227, 1231, 1079, 860, 104, 646, 647, 112, 648],
 'ENERGY_DISCARD': [7],
 'RECOVERABLE': {646, 647, 648, 112, 104, 860},
 'BENCH_FILLERS': {1086},
}

def PLAY_PRIORITY(cid, c):
    if c.get('deck_low') and cid in (1227, 1122):
        return 99
    if cid in (646, 112) and c['n_bench'] < 5: return 0
    if cid == 1079 and c['stage2_in_hand']: return 1
    if cid == 1231: return 2
    if cid == 1219 and not c['have'](1079): return 3
    if cid == 1097 and c.get('pokes_in_discard', 0) >= 1: return 3
    if cid == 1086 and c['n_bench'] < 5: return 4
    if cid == 1152 and not c['have'](648): return 5
    if cid == 1259: return 6
    if cid == 1227 and len(c['hand']) <= 4: return 7
    if cid == 860 and c['n_bench'] < 5: return 8
    if cid == 1097: return 9
    if cid == 1197:                                   # Xerosic: strip big hands
        try:
            _o = c['obs']
            _cur = _o.current
            _opp = _cur.players[1 - _cur.yourIndex]
            _my = _cur.players[_cur.yourIndex]
            if (_opp.handCount or 0) >= 6:
                return 2   # vs Alakazam a fat hand IS their damage — cut it now
        except Exception:
            pass
        return 10
    if cid == 1080: return 11
    if cid == 1182 and c['has_attacks'] and c['opp_hp'] <= 210: return 3
    if cid == 1122: return 12
    return 99
# ===================================================================

def cfg(key, default=None):
    return CONFIG.get(key, default)


# ---------------------------------------------------------------- data

_ATTACK_DB = None
_ATTACK_NAMES = None
_CARD_DB = None

def _load():
    global _ATTACK_DB, _ATTACK_NAMES, _CARD_DB
    if _ATTACK_DB is None:
        try:
            from cg.api import all_attack, all_card_data
            atks = all_attack()
            _ATTACK_DB = {a.attackId: a.damage for a in atks}
            _ATTACK_NAMES = {a.attackId: a.name for a in atks}
            _CARD_DB = {c.cardId: c for c in all_card_data()}
        except Exception:
            _ATTACK_DB, _ATTACK_NAMES, _CARD_DB = {}, {}, {}

def attack_damage(aid):
    _load(); return _ATTACK_DB.get(aid, 50)

def attack_name(aid):
    _load(); return _ATTACK_NAMES.get(aid, "")

def card_info(cid):
    _load(); return _CARD_DB.get(cid)


def read_deck_csv():
    p = "deck.csv"
    if not os.path.exists(p):
        p = "/kaggle_simulations/agent/" + p
    with open(p) as f:
        rows = f.read().split("\n")
    return [int(rows[i]) for i in range(60)]


def safe_fallback(select):
    n = max(select.minCount, min(1, select.maxCount))
    return random.sample(range(len(select.option)), n)


def card_at(obs, area, index, player_index):
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
    if opt.cardId is not None:
        return opt.cardId
    if opt.area is None or opt.index is None:
        return None
    pi = opt.playerIndex if opt.playerIndex is not None else obs.current.yourIndex
    c = card_at(obs, opt.area, opt.index, pi)
    return getattr(c, "id", None) if c is not None else None


def me(obs): return obs.current.players[obs.current.yourIndex]
def opp(obs): return obs.current.players[1 - obs.current.yourIndex]
def energy_count(p): return len(p.energies) if p and p.energies else 0

def my_in_play(obs):
    m = me(obs)
    out = [a for a in (m.active or []) if a]
    out += list(m.bench or [])
    return out


def opp_weak_mult(obs):
    act = opp(obs).active
    if act and act[0]:
        c = card_info(act[0].id)
        if c is not None and c.weakness == cfg('MY_TYPE'):
            return 2
    return 1


def effective_damage(obs, aid):
    dmg = attack_damage(aid)
    name = attack_name(aid)
    if name == "Powerful Hand":
        dmg = 20 * len(me(obs).hand or [])
    elif name == "Hungry Jaws":
        a = me(obs).active
        if a and a[0] and a[0].hp < a[0].maxHp:
            dmg += 150
    return dmg * opp_weak_mult(obs)


def pick_by_priority(obs, select, priority, count=None):
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

def choose_main(obs):
    st = obs.current
    my = me(obs)
    select = obs.select

    evolve, attach, plays, attacks, abilities, end_idx = [], [], [], [], [], None
    for i, o in enumerate(select.option):
        t = o.type
        if t == OptionType.EVOLVE: evolve.append((i, o))
        elif t == OptionType.ATTACH: attach.append((i, o))
        elif t == OptionType.PLAY: plays.append((i, o))
        elif t == OptionType.ATTACK: attacks.append((i, o))
        elif t == OptionType.ABILITY: abilities.append((i, o))
        elif t == OptionType.END: end_idx = i

    hand = my.hand or []
    basics = set(cfg('BASICS', []))
    n_bench = len(my.bench or [])
    in_play = len(my_in_play(obs))

    # 0. BENCH SAFETY: if reserves are thin, bench a Basic before anything else.
    if n_bench < cfg('MIN_BENCH', 2):
        for i, o in plays:
            cid = hand[o.index].id if o.index is not None and o.index < len(hand) else None
            if cid in basics:
                return [i]
        # ANTI-DONK: empty bench and no basic in hand -> direct-bench searchers
        # (Poffin) outrank everything, including draw supporters.
        if n_bench == 0:
            for i, o in plays:
                cid = hand[o.index].id if o.index is not None and o.index < len(hand) else None
                if cid in cfg('BENCH_FILLERS', set()):
                    return [i]

    # 0.5 DECK PRESERVATION: in a deck-out race, stop all voluntary consumption.
    deck_low = (my.deckCount < 10 and my.deckCount <= opp(obs).deckCount + 2)

    # 1. Conditional abilities.
    for i, o in abilities:
        cid = option_card_id(obs, o)
        if cid in cfg('ABILITIES', set()):
            if deck_low and cid in cfg('DRAW_ABILITIES', set()):
                continue
            if cid == 66:  # Run Away Draw: never strand ourselves; keep value
                if in_play >= 4:
                    return [i]
            else:
                return [i]

    # 2. Evolve (Stage2 target first, then configured order).
    if evolve:
        order = cfg('EVOLVE_ORDER', [])
        def erank(t):
            cid = option_card_id(obs, t[1])
            return order.index(cid) if cid in order else len(order)
        evolve.sort(key=erank)
        return [evolve[0][0]]

    # 3. Attach energy (trigger-energies first, then best target).
    if attach and not st.energyAttached:
        trig = cfg('TRIGGER_ENERGY', set())
        att_pri = cfg('ATTACH_TARGETS', [])
        override = cfg('ENERGY_TARGET_OVERRIDE', {})
        def score(o):
            src = hand[o.index].id if (o.area == AreaType.HAND and o.index is not None and o.index < len(hand)) else None
            src_rank = 0 if src in trig else 1
            if o.inPlayArea == AreaType.ACTIVE:
                pkm = my.active[o.inPlayIndex] if my.active else None
            else:
                pkm = my.bench[o.inPlayIndex] if (o.inPlayIndex is not None and o.inPlayIndex < len(my.bench)) else None
            cid = getattr(pkm, "id", None)
            if src in override:
                pri = override[src]
                tgt_rank = pri.index(cid) if cid in pri else len(pri)
                return (src_rank, 0, tgt_rank)
            tgt_rank = att_pri.index(cid) if cid in att_pri else len(att_pri)
            need = 0 if (pkm is not None and energy_count(pkm) < cfg('ENERGY_CAP', 2)) else 1
            return (src_rank, need, tgt_rank)
        best = min(attach, key=lambda t: score(t[1]))
        return [best[0]]

    # 3.5 If the current hand already produces a KO, attack NOW (hand is ammo
    # for Powerful Hand — playing more trainers shrinks it).
    opp_active = opp(obs).active
    opp_hp = opp_active[0].hp if (opp_active and opp_active[0]) else 999
    if attacks and cfg('HAND_IS_AMMO'):
        best_now = max(effective_damage(obs, o.attackId) for _, o in attacks)
        if best_now >= opp_hp:
            best = max(attacks, key=lambda t: (effective_damage(obs, t[1].attackId) >= opp_hp,
                                               -effective_damage(obs, t[1].attackId)))
            for i, o in attacks:
                d = effective_damage(obs, o.attackId)
                if d >= opp_hp:
                    return [i]

    # 4. Play trainers / Pokemon by configured priority function.
    ctx = {
        'hand': hand, 'n_bench': n_bench, 'in_play': in_play,
        'has_attacks': bool(attacks), 'opp_hp': opp_hp,
        'have': lambda cid: any(c.id == cid for c in hand),
        'stage2_in_hand': any(c.id in cfg('STAGE2S', set()) for c in hand),
        'deck_low': deck_low,
        'obs': obs,
    }
    prio_fn = PLAY_PRIORITY
    best_play, best_rank = None, 99
    for i, o in plays:
        cid = hand[o.index].id if o.index is not None and o.index < len(hand) else None
        r = prio_fn(cid, ctx) if cid is not None else 99
        if r < best_rank:
            best_rank, best_play = r, i
    if best_play is not None and best_rank < 99:
        if cfg('HAND_IS_AMMO') and attacks:
            act = my.active[0] if my.active else None
            ready = act is not None and act.id in cfg('READY_ATTACKERS', set()) and energy_count(act) >= 1
            if ready and best_rank > cfg('SETUP_RANK_MAX', 5):
                pass  # hold the hand; fall through to attack
            else:
                return [best_play]
        else:
            return [best_play]

    # 5. Attack: cheapest KO else biggest.
    if attacks:
        best = None
        for i, o in attacks:
            dmg = effective_damage(obs, o.attackId)
            key = (0, dmg) if dmg >= opp_hp else (1, -dmg)
            if best is None or key < best[0]:
                best = (key, i)
        return [best[1]]

    if end_idx is not None:
        return [end_idx]
    return safe_fallback(select)


# ---------------------------------------------------------------- selections

def choose_cards(obs):
    select = obs.select
    ctx = select.context
    my_index = obs.current.yourIndex
    fetch = cfg('FETCH_PRIORITY', [])
    setup = cfg('SETUP_PRIORITY', [])

    if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
        return pick_by_priority(obs, select, setup, count=1)
    if ctx == SelectContext.SETUP_BENCH_POKEMON:
        return pick_by_priority(obs, select, setup, count=select.maxCount)

    if ctx in (SelectContext.TO_HAND, SelectContext.TO_FIELD, SelectContext.TO_BENCH):
        return pick_by_priority(obs, select, fetch, count=select.maxCount)

    if ctx in (SelectContext.EVOLVES_FROM, SelectContext.EVOLVES_TO, SelectContext.EVOLVE):
        return pick_by_priority(obs, select, cfg('EVOLVE_ORDER', []) + fetch, count=max(select.minCount, 1))

    if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
        opp_side = [o for o in select.option if o.playerIndex is not None and o.playerIndex != my_index]
        if opp_side and len(opp_side) == len([o for o in select.option if o.playerIndex is not None]):
            def hp_score(i):
                o = select.option[i]
                c = card_at(obs, o.area, o.index, o.playerIndex)
                return getattr(c, "hp", 999) or 999
            idxs = sorted(range(len(select.option)), key=hp_score)
            return idxs[:max(select.minCount, 1)]
        promote = cfg('PROMOTE_PRIORITY', [])
        def score(i):
            o = select.option[i]
            pi = o.playerIndex if o.playerIndex is not None else my_index
            c = card_at(obs, o.area, o.index, pi)
            if c is None: return (9, 0, 0)
            cid = getattr(c, "id", None)
            en = energy_count(c) if hasattr(c, "energies") else 0
            r = promote.index(cid) if cid in promote else len(promote)
            return (r, -en, -(getattr(c, "hp", 0) or 0))
        idxs = sorted(range(len(select.option)), key=score)
        return idxs[:max(select.minCount, min(1, select.maxCount))]

    if ctx in (SelectContext.DISCARD, SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM,
               SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
        return pick_by_priority(obs, select, cfg('DISCARD_PRIORITY', []),
                                count=select.minCount or select.maxCount)

    if ctx in (SelectContext.ATTACH_FROM, SelectContext.ATTACH_TO, SelectContext.EFFECT_TARGET):
        return pick_by_priority(obs, select, cfg('ATTACH_TARGETS', []) + fetch, count=select.maxCount)

    if ctx in (SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER):
        return pick_by_priority(obs, select, cfg('ATTACH_TARGETS', []), count=select.maxCount)

    if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
        def hp_score(i):
            o = select.option[i]
            pi = o.playerIndex if o.playerIndex is not None else 1 - my_index
            c = card_at(obs, o.area, o.index, pi)
            return getattr(c, "hp", 999) or 999
        idxs = sorted(range(len(select.option)), key=hp_score)
        return idxs[:max(select.minCount, min(select.maxCount, len(idxs)))]

    return pick_by_priority(obs, select, fetch, count=select.maxCount)


def choose_yes_no(obs):
    select = obs.select
    yes_i = next((i for i, o in enumerate(select.option) if o.type == OptionType.YES), 0)
    no_i = next((i for i, o in enumerate(select.option) if o.type == OptionType.NO), 0)
    if select.context == SelectContext.MORE_DEVOLVE:
        return [no_i]
    return [yes_i]


def choose_attack(obs):
    select = obs.select
    opp_active = opp(obs).active
    opp_hp = opp_active[0].hp if (opp_active and opp_active[0]) else 999
    best = None
    for i, o in enumerate(select.option):
        dmg = effective_damage(obs, o.attackId) if o.attackId is not None else 0
        key = (0, dmg) if dmg >= opp_hp else (1, -dmg)
        if best is None or key < best[0]:
            best = (key, i)
    return [best[1]] if best else safe_fallback(select)


def choose_count(obs):
    select = obs.select
    best_i, best_n = 0, -1
    for i, o in enumerate(select.option):
        n = o.number if o.number is not None else 0
        if n > best_n: best_i, best_n = i, n
    return [best_i]


def _validate(result, select):
    try:
        result = [int(x) for x in result]
        result = list(dict.fromkeys(x for x in result if 0 <= x < len(select.option)))
        if len(result) > select.maxCount:
            result = result[:select.maxCount]
        while len(result) < select.minCount:
            extra = [i for i in range(len(select.option)) if i not in result]
            if not extra: break
            result.append(random.choice(extra))
        return result
    except Exception:
        return safe_fallback(select)


def agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()
    select = obs.select
    try:
        t = select.type
        if t == SelectType.MAIN: result = choose_main(obs)
        elif t in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD):
            result = choose_cards(obs)
        elif t == SelectType.YES_NO: result = choose_yes_no(obs)
        elif t == SelectType.ATTACK: result = choose_attack(obs)
        elif t == SelectType.COUNT: result = choose_count(obs)
        elif t == SelectType.EVOLVE: result = choose_cards(obs)
        elif t == SelectType.ENERGY:
            result = pick_by_priority(obs, select, cfg('ENERGY_DISCARD', []), count=max(select.minCount, 1))
        else: result = safe_fallback(select)
    except Exception:
        result = safe_fallback(select)
    return _validate(result, select)
