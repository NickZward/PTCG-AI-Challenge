"""Rule-based agent v4 — config-driven pilot with bench-safety + need-aware
search, dead-active recovery, energy discipline (ported from dipplin_v1),
and tunable knobs loaded from params.json (self-play tuner, Path A).

Dragapult ex pilot (dragapult_v2). Deck: LumenLiquidity's 17-5 ladder list.
"""

import json as _json
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
DREEPY, DRAKLOAK, DRAGAPULT = 119, 120, 121
DUSKULL, DUSCLOPS, DUSKNOIR = 131, 132, 133
MUNKIDORI, FEZ, BUDEW, MOLTRES, MEOWTH = 112, 140, 235, 791, 1071

CONFIG = {
 'MY_TYPE': 9,                     # Dragon — nothing is weak to it, no doubling
 'BASICS': [DREEPY, DUSKULL, MUNKIDORI, FEZ, BUDEW, MOLTRES, MEOWTH],
 'STAGE2S': {DRAGAPULT, DUSKNOIR},
 'MIN_BENCH': 3,
 'ABILITIES': {DRAKLOAK, DUSCLOPS, DUSKNOIR, FEZ, MUNKIDORI},
 'DRAW_ABILITIES': {DRAKLOAK, FEZ},
 'EVOLVE_ORDER': [DRAGAPULT, DRAKLOAK, DUSKNOIR, DUSCLOPS],
 'TRIGGER_ENERGY': set(),
 'ENERGY_TARGET_OVERRIDE': {7: [MUNKIDORI]},  # the single {D} feeds Munkidori
 'KEEP_ACTIVE': {DRAGAPULT},
 'RETREAT_MIN_ENERGY': 2,
 'ATTACH_TARGETS': [DRAGAPULT, DRAKLOAK, DREEPY, MOLTRES],
 'ENERGY_CAP': 2,                  # Phantom Dive costs {R}{P}
 'ENERGY_IDS': [2, 5, 7],
 'FETCH_PRIORITY': [DRAKLOAK, DRAGAPULT, DREEPY, 2, 5, DUSCLOPS, DUSKULL,
                    DUSKNOIR, FEZ, MUNKIDORI, 1121, 1086, 1182],
 'SETUP_PRIORITY': [DREEPY, BUDEW, DUSKULL, MUNKIDORI, FEZ, MOLTRES, MEOWTH],
 'PROMOTE_PRIORITY': [DRAGAPULT, DUSKNOIR, DRAKLOAK, MOLTRES, FEZ, MUNKIDORI,
                      DUSCLOPS, MEOWTH, DREEPY, DUSKULL, BUDEW],
 'DISCARD_PRIORITY': [1120, 1080, 1256, 1198, 1152, 1227, 1231, 1121, 1086, 1097,
                      1182, 7, 2, 5, BUDEW, MOLTRES, MEOWTH, DUSKULL, DUSCLOPS,
                      DREEPY, MUNKIDORI, FEZ, DRAKLOAK, DUSKNOIR, DRAGAPULT],
 'ENERGY_DISCARD': [7, 2, 5],
 'RECOVERABLE': {DREEPY, DRAKLOAK, DRAGAPULT, DUSKULL, DUSCLOPS, DUSKNOIR},
 'BENCH_FILLERS': {1086},
 'HAND_IS_AMMO': False,
 'READY_ATTACKERS': {DRAGAPULT},
 'SETUP_RANK_MAX': 5,
 # -------- tunable knobs (overridden by params.json) --------
 'COLLAPSE_BENCH': 2,     # bench below this + no basic in hand => dig mode
 'LILLIES_MAX_HAND': 5,   # play Lillie's when hand <= this
 'BOSS_KO_MAX': 200,      # Boss's Orders when opp active hp <= this
 'BOSS_BENCH_MAX': 200,   # ...or a benched target Phantom Dive (200) can KO
 'DECK_LOW_AT': 10,       # deck preservation threshold
}

_SET_KEYS = {'STAGE2S', 'ABILITIES', 'DRAW_ABILITIES', 'KEEP_ACTIVE', 'RECOVERABLE',
             'BENCH_FILLERS', 'READY_ATTACKERS', 'TRIGGER_ENERGY'}
try:
    _pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'params.json')
    if os.path.exists(_pp):
        for _k, _v in _json.load(open(_pp)).items():
            CONFIG[_k] = set(_v) if _k in _SET_KEYS else _v
except Exception:
    pass

def PLAY_PRIORITY(cid, c):
    if c.get('hard_low') and cid in (1231, 1227, 1152, 1121, 1086, 1097):
        return 99
    if c.get('deck_low') and cid in (1097,):
        return 99
    if cid in (DREEPY, DUSKULL) and c['n_bench'] < 5: return 0   # evolution seeds first
    # SETUP COLLAPSE GUARD: bench nearly empty and no basic in hand — dig with
    # everything before the active gets sniped out from under us.
    if c['n_bench'] < CONFIG['COLLAPSE_BENCH'] and not any(x.id in CONFIG['BASICS'] for x in c['hand']):
        if cid == 1086: return 1
        if cid == 1121: return 1     # Ultra Ball (need-aware fetch grabs a basic)
        if cid == 1227: return 1
        if cid == 1152: return 2
    # ENERGY DROUGHT: no energy on board or in hand — recovery jumps the queue.
    if c.get('energy_drought'):
        if cid == 1198: return 1     # Crispin: 2 energy from deck
        if cid == 1097 and c.get('energy_in_discard'): return 1
    if cid == 1231: return 2                              # Dawn
    if cid == 1182 and c['has_attacks'] and c['opp_hp'] <= CONFIG['BOSS_KO_MAX']: return 3
    # BOSS BENCH FARMING (v5): Phantom Dive (200) OHKOs almost any benched
    # target; drag up a KO-able bench Pokemon to convert spread into prizes.
    if cid == 1182 and c['has_attacks'] and c.get('opp_bench_min_hp', 999) <= CONFIG.get('BOSS_BENCH_MAX', 200): return 3
    if cid == 1121: return 4                              # Ultra Ball
    if cid == 1086 and c['n_bench'] < 5: return 4         # Poffin
    if cid == 1152: return 5                              # Poke Pad (was over-gated in v1)
    if cid == 1198:                                       # Crispin: fuel Phantom Dive
        try:
            _o = c['obs']
            _my = _o.current.players[_o.current.yourIndex]
            _mons = [a for a in (_my.active or []) if a] + [b for b in (_my.bench or []) if b]
            if any(m.id in (DRAGAPULT, DRAKLOAK) and len(m.energies or []) < 2 for m in _mons):
                return 2   # an attacker is dry — energy beats every other supporter
        except Exception:
            pass
        return 7
    if cid == 1227 and len(c['hand']) <= CONFIG['LILLIES_MAX_HAND']: return 6
    if cid == MUNKIDORI and c['n_bench'] < 5: return 8
    if cid == FEZ and c['n_bench'] < 5: return 9
    if cid == MEOWTH and c['n_bench'] < 5: return 10
    if cid == BUDEW and c['n_bench'] < 5: return 11
    if cid == MOLTRES and c['n_bench'] < 5: return 12
    if cid == 1097 and c.get('pokes_in_discard', 0) >= 1: return 13
    if cid == 1120: return 14                             # Crushing Hammer
    if cid == 1256: return 15                             # Watchtower
    if cid == 1080: return 16                             # Unfair Stamp
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
    elif name == "Do the Wave":
        dmg = 20 * len([b for b in (me(obs).bench or []) if b])
    elif name == "Hungry Jaws":
        a = me(obs).active
        if a and a[0] and a[0].hp < a[0].maxHp:
            dmg += 150
    elif name == "Fighting Wings":
        act = opp(obs).active
        if act and act[0]:
            ci = card_info(act[0].id)
            if ci is not None and getattr(ci, "ex", False):
                dmg += 90
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
    deck_low = (my.deckCount < cfg('DECK_LOW_AT', 10) and my.deckCount <= opp(obs).deckCount + 2)
    hard_low = my.deckCount < 4

    # 1. Conditional abilities.
    # v7: draw abilities are only gated when the deck is CRITICALLY low, or when
    # the hand is already stocked — hand size IS our damage (Powerful Hand), so
    # starving the hand to save deck lost far more games than deck-out did.
    for i, o in abilities:
        cid = option_card_id(obs, o)
        if cid in cfg('ABILITIES', set()):
            if cid in (132, 133):
                # Cursed Blast KOs its own user (gives up a prize) — only fire
                # when the counters convert a KO on the opponent's side.
                cap = 50 if cid == 132 else 130
                opp_mons = [a for a in (opp(obs).active or []) if a] + \
                           [b for b in (opp(obs).bench or []) if b]
                if not any((p.hp or 999) <= cap for p in opp_mons):
                    continue
            if cid in cfg('DRAW_ABILITIES', set()):
                if my.deckCount < 5:
                    continue
                if deck_low and len(hand) >= 6:
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
            if cid not in att_pri:
                need = 2   # never feed scarce energy to non-attackers
            # PHANTOM DIVE {R}{P} energy discipline (v5): the attacker needs
            # exactly one Fire(2) + one Psychic(5). EnergyType==card id here.
            if cid in (DRAGAPULT, DRAKLOAK, DREEPY):
                have = [getattr(e, "id", e) for e in (getattr(pkm, "energies", None) or [])]
                if src == 7:            # Dark is useless to the attacker line
                    need += 5
                elif src in (2, 5) and src in have:
                    need += 5           # HARD block a duplicate type (was +1, a brick)
                elif src in (2, 5):
                    # attaching the MISSING type completes {R}{P} -> top priority
                    other = 5 if src == 2 else 2
                    if other in have:
                        need = -1       # this attach makes Phantom Dive live
            return (src_rank, need, tgt_rank)
        best = min(attach, key=lambda t: score(t[1]))
        return [best[0]]

    # 3.2 RETREAT (v7): 8 of 19 ladder losses were spent attacking with a
    # support Pokemon (Dunsparce/Fezandipiti) for 0 damage while a charged
    # attacker sat on the bench. If the active can't fight and a ready
    # attacker is benched, retreat into it.
    retreat_idx = next((i for i, o in enumerate(select.option)
                        if o.type == OptionType.RETREAT), None)
    if retreat_idx is not None and not st.retreated:
        act = my.active[0] if my.active else None
        keep = cfg('KEEP_ACTIVE', set())
        ready = cfg('READY_ATTACKERS', set())
        if act is not None:
            # A dry attacker with no energy coming is as dead as a support
            # Pokemon — swap it for a charged one instead of passing forever.
            energy_in_hand = any(c.id in set(cfg('ENERGY_IDS', [1])) for c in hand)
            stuck = (act.id in keep and energy_count(act) == 0
                     and st.energyAttached and not energy_in_hand)
            if act.id not in keep or stuck:
                bench_ready = any(b is not None and b.id in ready and energy_count(b) >= cfg('RETREAT_MIN_ENERGY', 1)
                                  for b in (my.bench or []))
                if bench_ready:
                    return [retreat_idx]

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
    stadium = st.stadium[0] if (st.stadium and st.stadium[0]) else None
    our_stadium = stadium is not None and stadium.id == 1256   # Watchtower
    opp_act = opp(obs).active
    opp_ci = card_info(opp_act[0].id) if (opp_act and opp_act[0]) else None
    energy_ids = set(cfg('ENERGY_IDS', [1]))
    ctx = {
        'hand': hand, 'n_bench': n_bench, 'in_play': in_play,
        'has_attacks': bool(attacks), 'opp_hp': opp_hp,
        'have': lambda cid: any(c.id == cid for c in hand),
        'stage2_in_hand': any(c.id in cfg('STAGE2S', set()) for c in hand),
        'deck_low': deck_low,
        'hard_low': hard_low,
        'pokes_in_discard': sum(1 for c in (my.discard or []) if c.id in cfg('RECOVERABLE', set())),
        'deck_count': my.deckCount,
        'obs': obs,
        'our_stadium': our_stadium,
        'opp_bench': len([b for b in (opp(obs).bench or []) if b]),
        'opp_bench_min_hp': min([(b.hp or 999) for b in (opp(obs).bench or []) if b] or [999]),
        'opp_is_ex': bool(opp_ci is not None and getattr(opp_ci, 'ex', False)),
        'energy_drought': (sum(len(p.energies or []) for p in my_in_play(obs)) == 0
                          and not any(c.id in energy_ids for c in hand)),
        'energy_in_discard': any(c.id in energy_ids for c in (my.discard or [])),
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

def dynamic_fetch(obs):
    """Need-aware search priority — what to grab depends on what the board is
    missing. Fixes the v1 bug where Ultra Ball fetched unbenchable Drakloaks
    while we had no basic in play."""
    my = me(obs)
    hand_ids = [c.id for c in (my.hand or [])]
    in_play = my_in_play(obs)
    play_ids = [p.id for p in in_play]
    n_bench = len([b for b in (my.bench or []) if b])
    pri = []
    # 1. Bench safety: benchless with no basic in hand -> ANY basic first.
    if n_bench < cfg('MIN_BENCH', 3) and not any(h in cfg('BASICS', []) for h in hand_ids):
        pri += [DREEPY, DUSKULL, BUDEW, MUNKIDORI, FEZ, MOLTRES, MEOWTH]
    # 2. Attacker line: complete Dreepy -> Drakloak -> Dragapult ex.
    if DRAGAPULT not in play_ids and DRAGAPULT not in hand_ids and DRAKLOAK in play_ids:
        pri.append(DRAGAPULT)
    if DRAKLOAK not in play_ids and DRAKLOAK not in hand_ids and DREEPY in play_ids:
        pri.append(DRAKLOAK)
    if DREEPY not in play_ids and DREEPY not in hand_ids:
        pri.append(DREEPY)
    # 3. Energy for a dry attacker.
    attackers = [p for p in in_play if p.id in (DRAGAPULT, DRAKLOAK)]
    if attackers and all(len(p.energies or []) < 2 for p in attackers) \
            and not any(h in (2, 5) for h in hand_ids):
        pri += [2, 5]
    # 4. Dusknoir line converts spread into KOs.
    if DUSKULL not in play_ids and DUSKULL not in hand_ids and n_bench < 5:
        pri.append(DUSKULL)
    if DUSCLOPS not in play_ids and DUSCLOPS not in hand_ids and DUSKULL in play_ids:
        pri.append(DUSCLOPS)
    return pri + cfg('FETCH_PRIORITY', [])


def choose_cards(obs):
    select = obs.select
    ctx = select.context
    my_index = obs.current.yourIndex
    fetch = dynamic_fetch(obs)
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


# ================= Path C: 1-ply search with learned value function ========
_VF = {"model": None, "vocab": None, "deck": None, "ok": False}

def _vf_load():
    if _VF["ok"] or _VF["model"] is False:
        return
    try:
        import sys as _sys
        import joblib, json as _j
        base = os.path.dirname(os.path.abspath(__file__))
        if base not in _sys.path:
            _sys.path.insert(0, base)
        _VF["model"] = joblib.load(os.path.join(base, "vf_model.joblib"))
        _VF["vocab"] = _j.load(open(os.path.join(base, "bc_vocab.json")))
        _VF["deck"] = read_deck_csv()
        _VF["ok"] = True
    except Exception:
        _VF["model"] = False


def _unseen_pool(obs):
    """Our full deck minus every card we can currently see."""
    from collections import Counter as _C
    my = me(obs)
    pool = _C(_VF["deck"])
    seen = []
    seen += [c.id for c in (my.hand or [])]
    seen += [c.id for c in (my.discard or [])]
    for pkm in my_in_play(obs):
        seen.append(pkm.id)
        seen += [getattr(e, "id", None) for e in (pkm.energies or [])]
    st = obs.current.stadium
    if st and st[0] is not None:
        seen.append(st[0].id)
    for cid in seen:
        if cid is not None and pool.get(cid, 0) > 0:
            pool[cid] -= 1
    return list(pool.elements())


def _rule_dispatch(o):
    """Resolve a sub-select inside the search with the rule policy."""
    t = o.select.type
    if t == SelectType.MAIN: r = choose_main(o)
    elif t in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD):
        r = choose_cards(o)
    elif t == SelectType.YES_NO: r = choose_yes_no(o)
    elif t == SelectType.ATTACK: r = choose_attack(o)
    elif t == SelectType.COUNT: r = choose_count(o)
    elif t == SelectType.EVOLVE: r = choose_cards(o)
    elif t == SelectType.ENERGY:
        r = pick_by_priority(o, o.select, cfg('ENERGY_DISCARD', []), count=max(o.select.minCount, 1))
    else: r = safe_fallback(o.select)
    return _validate(r, o.select)


def choose_main_search(obs):
    """Evaluate every MAIN option by simulating it (plus forced follow-ups)
    and scoring the resulting position with the value function."""
    _vf_load()
    if not _VF["ok"] or obs.search_begin_input is None:
        return None
    # Optional phase gate: the value fn is near-noise in the opening
    # (AUC .54) and sharp late (.79-.93) — only override where it's sharp.
    if os.environ.get('VF_LATE', '1') == '1':
        _mp = len(me(obs).prize or [])
        _op = len(opp(obs).prize or [])
        if min(_mp, _op) > 4:
            return None
    from cg.api import search_begin, search_step, search_end
    import numpy as np
    import bc_features as F
    me_i = obs.current.yourIndex
    op = opp(obs)
    try:
        pool = _unseen_pool(obs)
        random.shuffle(pool)
        my_p = me(obs)
        need = my_p.deckCount + len(my_p.prize or [])
        pool += [5] * max(0, need - len(pool))
        your_deck = pool[:my_p.deckCount]
        your_prize = pool[my_p.deckCount:my_p.deckCount + len(my_p.prize or [])]
        opp_deck = [741] + [5] * max(0, op.deckCount - 1)
        opp_prize = [5] * len(op.prize or [])
        opp_hand = [5] * (op.handCount or 0)
        opp_active = [741]
        root = search_begin(obs, your_deck, your_prize,
                            opp_deck, opp_prize, opp_hand, opp_active)
        vocab, cf = _VF["vocab"]["vocab"], _VF["vocab"]["card_feats"]
        n = len(obs.select.option)
        feats, terminal = [], {}
        for i in range(n):
            s = search_step(root.searchId, [i])
            o, depth = s.observation, 0
            # CONSISTENT HORIZON: after the candidate move, let the rule
            # policy finish the ENTIRE turn, then score where it landed.
            # (Comparing mid-turn vs end-of-turn states biased the value fn.)
            while (o.select is not None and o.current.result == -1
                   and o.current.yourIndex == me_i and depth < 40):
                s = search_step(s.searchId, _rule_dispatch(o))
                o = s.observation
                depth += 1
            if o.current.result != -1:
                terminal[i] = 1.0 if o.current.result == me_i else 0.0
                feats.append([0.0] * F.N_STATE)
            else:
                feats.append(F.state_features(o.current, me_i, vocab, cf,
                                              step=_VF.get("step", 0)))
        vals = _VF["model"].predict_proba(np.array(feats, dtype=np.float32))[:, 1]
        for i, tv in terminal.items():
            vals[i] = tv
        search_end()
        # Deviate from the rule policy only on a confident improvement —
        # 50 noise-driven deviations per game is how you lose to yourself.
        rule = _validate(choose_main(obs), obs.select)
        rule_idx = rule[0] if rule else 0
        best = int(np.argmax(vals))
        margin = float(os.environ.get('VF_MARGIN', '0.10'))
        if best != rule_idx and vals[best] > vals[rule_idx] + margin:
            return [best]
        return rule
    except Exception:
        try:
            search_end()
        except Exception:
            pass
        return None
# ===========================================================================


def agent(obs_dict):
    _VF["step"] = obs_dict.get("step") or 0    # Observation drops this field
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()
    select = obs.select
    try:
        t = select.type
        if t == SelectType.MAIN:
            result = choose_main_search(obs) or choose_main(obs)
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
