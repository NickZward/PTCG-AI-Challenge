"""Rule-based agent v3 — config-driven pilot with bench-safety.

Dipplin/Thwackey pilot (dipplin_v1), cloned from Jack's 4-0 top-ladder list.
Gameplan: Grookey up front, fill the bench (bench count IS the damage),
evolve to Dipplin + keep Festival Grounds in play so Do the Wave hits twice
(2 x 20 x bench), Thwackey's Boom Boom Groove tutors the missing piece every
turn, Rabsca/Shaymin blank all bench damage, Genesect + tool locks the
opponent's ACE SPEC.
"""

import os
import random

from cg.api import (
    Observation,
    to_observation_class,
    AreaType,
    LogType,
    OptionType,
    SelectType,
    SelectContext,
)

# ================= DECK CONFIG (replaced per deck) =================
GROOKEY, THWACKEY = 89, 90
APPLIN, DIPPLIN = 92, 93
RELLOR, RABSCA = 73, 74
GENESECT, SHAYMIN = 142, 343
FESTIVAL = 1245

CONFIG = {
 'MY_TYPE': 1,                     # Grass
 'BASICS': [APPLIN, GROOKEY, RELLOR, SHAYMIN, GENESECT],
 'STAGE2S': set(),
 'MIN_BENCH': 3,
 'ABILITIES': {THWACKEY},          # Boom Boom Groove: free tutor every turn
 'DRAW_ABILITIES': set(),
 'EVOLVE_ORDER': [DIPPLIN, THWACKEY, RABSCA],
 'TRIGGER_ENERGY': set(),
 'ENERGY_TARGET_OVERRIDE': {},
 'KEEP_ACTIVE': {DIPPLIN},
 'RETREAT_MIN_ENERGY': 1,
 'ATTACH_TARGETS': [DIPPLIN, APPLIN, RABSCA, RELLOR],  # energy is scarce: attackers only
 'ENERGY_CAP': 1,                  # Do the Wave costs a single {G}
 'FETCH_PRIORITY': [DIPPLIN, APPLIN, THWACKEY, GROOKEY, FESTIVAL, 1,
                    RABSCA, RELLOR, SHAYMIN, GENESECT, 1086, 1094, 1182, 1227, 1152],
 'SETUP_PRIORITY': [APPLIN, GROOKEY, RELLOR, SHAYMIN, GENESECT],  # v6: Applin active = attacker line (Dipplin); support stays benched
 'PROMOTE_PRIORITY': [DIPPLIN, APPLIN, THWACKEY, GROOKEY, RABSCA, RELLOR, GENESECT, SHAYMIN],
 'DISCARD_PRIORITY': [1223, 1187, 1174, 1175, 1094, 1152, 1086, 1227, 1182,
                      1080, 1211, 1191, FESTIVAL, GENESECT, SHAYMIN, RELLOR, RABSCA,
                      1097, 1184, 1, GROOKEY, APPLIN, THWACKEY, DIPPLIN],
 'ENERGY_DISCARD': [1],
 'RECOVERABLE': {GROOKEY, THWACKEY, APPLIN, DIPPLIN, RELLOR, RABSCA},
 'BENCH_FILLERS': {1086},
 'HAND_IS_AMMO': False,
 'READY_ATTACKERS': {DIPPLIN},
 'SETUP_RANK_MAX': 5,
 'ENERGY_IDS': [1],
 # -------- tunable knobs (overridden by params.json) --------
 'ENERGY_STOCK': 2,        # keep this many energies live (board + hand)
 'TUTOR_DECK_MARGIN': 5,   # stop tutoring when deck < opp deck - margin
 'COLLAPSE_BENCH': 2,
 'LILLIES_MAX_HAND': 5,
 'LILLIES_BIG_HAND': 8,    # hand >= this: Lillie's refuels the deck (mill race)
 'RACE_DECK_AT': 30,       # mill-race mode once deck below this...
 'RACE_MARGIN': 3,         # ...and not ahead of opponent by more than this
 'DECK_LOW_AT': 10,
 'STAMP_ON_KO': 0,        # Stamp refuels opp deck (hand-2) — off in mill meta
 # -------- v7 anti-lock escape --------
 'ESCAPE_LOCK': 1,        # unstick a 0-energy body trapped active (v7)
 'ESCAPE_TOOLS': [1174],  # Air Balloon (-2 retreat): free-retreat a stuck active
}

import json as _json
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
    if c.get('hard_low') and cid in (1227, 1223, 1187, 1152, 1094, 1086, 1097):
        return 99
    if c.get('deck_low') and cid in (1097,):
        return 99
    # Bench count IS the damage — basics first while the bench is short.
    if cid in (APPLIN, GROOKEY, RELLOR, SHAYMIN, GENESECT) and c['n_bench'] < 5: return 0
    # SETUP COLLAPSE GUARD: bench nearly empty and nothing to bench — dig with
    # everything before the active gets sniped out from under us.
    if c['n_bench'] < CONFIG['COLLAPSE_BENCH'] and not any(x.id in (APPLIN, GROOKEY, RELLOR, SHAYMIN, GENESECT) for x in c['hand']):
        if cid == 1086: return 1
        if cid == 1094: return 1
        if cid == 1227: return 1
        if cid == 1152: return 2
        if cid == 1223 and len(c['hand']) <= 4: return 2
    # ENERGY SHORTAGE (v2, was full-drought only): recovery jumps the queue
    # whenever live energy is below stock and the discard holds some.
    if c.get('energy_short'):
        if cid == 1184 and c.get('energy_in_discard'): return 1   # Lana's: up to 3 back
        if cid == 1097 and c.get('energy_in_discard'): return 1
    if cid == FESTIVAL and not c.get('our_stadium'): return 1   # unlocks double attack
    # LILLIE'S INVERSION (v3): shuffles hand INTO deck then draws 6 — with a
    # big hand it REFUELS the deck. In a mill-race meta that wins games.
    if cid == 1227 and len(c['hand']) >= CONFIG['LILLIES_BIG_HAND']: return 2
    # DECK RACE (v2): optional dig items stop when we're milling ourselves out.
    if c.get('deck_race') and not c.get('energy_short') and cid in (1094, 1152, 1122):
        return 99
    if c.get('deck_race') and cid == 1187: return 99   # Morty's burns 2 cards
    if cid == 1086 and c.get('basics_in_deck', 1) == 0: return 99   # nothing left to find
    if cid == 1086 and c['n_bench'] < 5: return 2               # Poffin
    if cid == 1182 and c['has_attacks'] and c['opp_hp'] <= c.get('wave_dmg', 0): return 3
    # BOSS BENCH FARMING (v3): Boss exists to drag KO-able BENCH targets into
    # range — the old gate only looked at the active. Prizes end mill races.
    if cid == 1182 and c['has_attacks'] and c.get('opp_bench_min_hp', 999) <= c.get('wave_dmg', 0): return 3
    if cid in (1191, 1211) and c['has_attacks'] and c.get('opp_is_ex') \
            and c.get('wave_dmg', 0) < c['opp_hp'] <= c.get('wave_dmg', 0) + (30 if cid == 1191 else 40):
        return 3                                                # buff converts the KO
    if cid == 1152 and c.get('pokes_in_deck', 1) == 0: return 99
    if cid == 1152 and not c['have'](DIPPLIN): return 4         # Poke Pad digs for the line
    if cid == 1094: return 5                                    # Bug Catching Set
    if cid == 1227 and len(c['hand']) <= CONFIG['LILLIES_MAX_HAND']: return 6   # Lillie's Determination
    if cid == 1187 and len(c['hand']) >= 2 and c.get('opp_bench', 0) >= 2: return 7
    if cid in (1174, 1175): return 8                            # tools (Bangle/Balloon)
    if cid == 1097 and c.get('pokes_in_discard', 0) >= 1: return 9
    if cid == 1184 and c.get('pokes_in_discard', 0) >= 2: return 9
    if cid == 1080 and c.get('pre_ko') and CONFIG.get('STAMP_ON_KO', 1): return 2                # Unfair Stamp: punish their KO
    if cid == 1080: return 12                                   # Unfair Stamp
    if cid == 1223 and len(c['hand']) <= 2: return 13           # Harlequin: dead hand reset
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


_DECK_CACHE = None

def read_deck_csv():
    global _DECK_CACHE
    if _DECK_CACHE is not None:
        return list(_DECK_CACHE)
    paths = []
    try:
        # __file__ is undefined in Kaggle's exec-based agent runner — guard it
        paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv"))
    except NameError:
        pass
    paths += ["/kaggle_simulations/agent/deck.csv", "deck.csv"]
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p) as f:
                    rows = f.read().split("\n")
                deck = [int(rows[i]) for i in range(60)]
                _DECK_CACHE = deck
                return list(deck)
        except Exception:
            continue
    raise FileNotFoundError("deck.csv")


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


# ------------------------------------------------ v7 anti-lock escape
# Instrumentation (verification only; harmless in play): lock_dp counts MAIN
# decision-points spent in the stuck state; esc_* count escape actions taken.
_INSTR = {'lock_dp': 0, 'esc_tool': 0, 'esc_attach': 0, 'esc_retreat': 0}

def _escape_lock(obs, select, plays, attach, act_enabled=True):
    """A 0-energy body is trapped ACTIVE — can't attack, can't pay any retreat
    cost — while a charged, ready attacker sits benched. This is the force-open
    lock (no attacker basic in the opening hand) and the Boss's-Orders-gust lock
    that recurred in 6/8 of the first v6/v7 ladder games and threw one won game.
    The v7 retreat fix only fires when RETREAT is ALREADY legal; a 0-energy body
    is never offered retreat, so nothing unsticks it. Here we BUY the escape:
    retreat if now legal, else play a retreat-reducer tool (Air Balloon), else
    funnel this turn's energy into the stuck active until retreat becomes legal
    (then it retreats into the charged attacker next pass).

    Returns an option list to execute, or None to fall through to normal play.
    Detection (lock_dp) is counted even when disabled so baseline vs fixed can
    be compared apples-to-apples."""
    try:
        my = me(obs); st = obs.current
        act = my.active[0] if my.active else None
        if act is None:
            return None
        ready = cfg('READY_ATTACKERS', set())
        thr = cfg('RETREAT_MIN_ENERGY', 1)     # energy an attacker needs to attack
        # active is already a functional attacker -> not stuck, leave it
        if act.id in ready and energy_count(act) >= thr:
            return None
        # a benched attacker that can actually attack this turn must be waiting
        if not any(b is not None and b.id in ready and energy_count(b) >= thr
                   for b in (my.bench or [])):
            return None
        # locked whenever we cannot retreat into that attacker right now
        ridx = next((i for i, o in enumerate(select.option)
                     if o.type == OptionType.RETREAT), None)
        _INSTR['lock_dp'] += 1
        if not act_enabled:
            return None
        # legal to retreat now (0-cost after Air Balloon, or funneled cost paid)?
        if ridx is not None and not st.retreated:
            _INSTR['esc_retreat'] += 1
            return [ridx]
        # safety cap: never pour more than 3 energy into an escape
        if energy_count(act) >= 3:
            return None
        # 1. play a retreat-reducer tool (Air Balloon, -2) onto the stuck active
        if not act.tools:
            hand = my.hand or []
            esc_tools = set(cfg('ESCAPE_TOOLS', []))
            for i, o in plays:
                cid = hand[o.index].id if (o.index is not None and o.index < len(hand)) else None
                if cid in esc_tools:
                    _INSTR['esc_tool'] += 1
                    return [i]
        # 2. else funnel this turn's energy INTO the stuck active to buy retreat
        if attach and not st.energyAttached:
            for i, o in attach:
                if o.inPlayArea == AreaType.ACTIVE:
                    _INSTR['esc_attach'] += 1
                    return [i]
        return None
    except Exception:
        return None


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
    # DECK RACE (v2): every ladder loss was a deck-out — our tutor+items burn
    # ~2 cards/turn vs the opponent's 1. Once we're this far ahead on
    # consumption, optional digging stops unless it's fixing an energy drought.
    # MILL-RACE MODE (v3): every ladder game ends in deck-out — treat the
    # deck as the primary resource once setup is done. Race mode = past the
    # opening AND not comfortably ahead on cards.
    deck_race = (my.deckCount < cfg('RACE_DECK_AT', 30)
                 and my.deckCount <= opp(obs).deckCount + cfg('RACE_MARGIN', 3))
    _energy_ids = set(cfg('ENERGY_IDS', [1]))
    _board_energy = sum(len(p.energies or []) for p in my_in_play(obs))
    _hand_energy = sum(1 for c in hand if c.id in _energy_ids)
    energy_short = (_board_energy + _hand_energy) < cfg('ENERGY_STOCK', 2)

    # 1. Conditional abilities.
    # v7: draw abilities are only gated when the deck is CRITICALLY low, or when
    # the hand is already stocked — hand size IS our damage (Powerful Hand), so
    # starving the hand to save deck lost far more games than deck-out did.
    for i, o in abilities:
        cid = option_card_id(obs, o)
        if cid in cfg('ABILITIES', set()):
            if cid == THWACKEY and (deck_race or hard_low) and not energy_short:
                continue   # tutor costs a deck card — don't mill ourselves out
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
        ready = cfg('READY_ATTACKERS', set())
        def erank(t):
            o = t[1]
            cid = option_card_id(obs, o)
            # ANTI-LOCK (v6): NEVER evolve the ACTIVE spot into a non-attacker
            # (Thwackey/Rabsca). It traps a 0-energy body active (retreat cost
            # 2 -> can't retreat -> self-decks won games). Thwackey tutors fine
            # from the bench; keep those evolutions benched. This was the true
            # cause of the stuck-active lock (10/41 games, 28% of losses).
            if getattr(o, 'inPlayArea', None) == AreaType.ACTIVE and cid not in ready:
                return 999
            return order.index(cid) if cid in order else len(order)
        evolve.sort(key=erank)
        if erank(evolve[0]) < 999:
            return [evolve[0][0]]
        # else: only active->support evolves available -> skip evolving this pass

    # 2.5 ANTI-LOCK ESCAPE (v7): unstick a 0-energy body trapped active while a
    # charged attacker waits on the bench (force-open / Boss's-gust lock).
    esc = _escape_lock(obs, select, plays, attach, act_enabled=bool(cfg('ESCAPE_LOCK', 1)))
    if esc is not None:
        return esc

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
            # v8: ARM THE ACTIVE ready-attacker FIRST — it can KO this turn; a
            # benched copy can't. Fixes attaching to the bench while the active
            # Dipplin sits at 0 energy and we durdle into a deckout loss while
            # AHEAD with lethal on board (ep 87243047).
            is_active = (o.inPlayArea == AreaType.ACTIVE)
            arm = 0 if (is_active and cid in cfg('READY_ATTACKERS', set())
                        and pkm is not None and energy_count(pkm) < cfg('ENERGY_CAP', 2)) else 1
            return (src_rank, arm, need, tgt_rank)
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
            energy_in_hand = any(c.id == 1 for c in hand)
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

    # 3.6 TAKE THE KO (v8): when the active can attack for a KO/prize NOW, do it
    # instead of durdling into optional draws. Several won games were THROWN by
    # decking out while ahead with lethal on board (ep 87243047: opp ex at 10 HP
    # ignored for ~18 turns while we self-milled). Applies to non-HAND_IS_AMMO decks.
    if attacks and not cfg('HAND_IS_AMMO'):
        best_dmg = max((effective_damage(obs, o.attackId) for _, o in attacks), default=0)
        if best_dmg >= opp_hp:                     # lethal on the active — take it
            best = None
            for i, o in attacks:
                d = effective_damage(obs, o.attackId)
                k = (0, d) if d >= opp_hp else (1, -d)
                if best is None or k < best[0]:
                    best = (k, i)
            return [best[1]]
        _orc = oracle_attacks(obs) if cfg('USE_ORACLE_ATTACK', 1) else {}
        if _orc and any((w or pz >= 1) for (w, pz, d) in _orc.values()):
            return [max(_orc, key=lambda i: _orc[i])]   # oracle confirms a KO/prize

    # 4. Play trainers / Pokemon by configured priority function.
    stadium = st.stadium[0] if (st.stadium and st.stadium[0]) else None
    our_stadium = stadium is not None and stadium.id == FESTIVAL
    # Full damage output this turn: Do the Wave twice while Festival Grounds
    # is up (the engine offers the second attack after the first resolves).
    wave_once = 20 * n_bench
    wave_dmg = wave_once * (2 if our_stadium else 1)
    opp_act = opp(obs).active
    opp_ci = card_info(opp_act[0].id) if (opp_act and opp_act[0]) else None
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
        'wave_dmg': wave_dmg * opp_weak_mult(obs),
        'opp_bench': len([b for b in (opp(obs).bench or []) if b]),
        'opp_bench_min_hp': min([(b.hp or 999) for b in (opp(obs).bench or []) if b] or [999]),
        'opp_is_ex': bool(opp_ci is not None and getattr(opp_ci, 'ex', False)),
        'opp_hand': opp(obs).handCount or 0,
        'opp_has_tool': any(bool(getattr(x, 'tools', None)) for x in
                            ([a for a in (opp(obs).active or []) if a] + [b for b in (opp(obs).bench or []) if b])),
        'energy_drought': (_board_energy == 0 and _hand_energy == 0),
        'energy_short': energy_short,
        'energy_in_discard': any(c.id in _energy_ids for c in (my.discard or [])),
        'deck_race': deck_race,
        'pre_ko': _TRK.get('pre_ko', False),
    }
    # v4 ORACLE: exact damage/KO by simulation replaces the wave_dmg estimate
    try:
        _orc = oracle_attacks(obs)
        ctx['oracle'] = _orc
        if _orc and cfg('USE_ORACLE_DMG', 1):
            ctx['wave_dmg'] = max(d for _, _, d in _orc.values())
        _dc = deck_counts(obs)
        ctx['basics_in_deck'] = sum(_dc.get(b, 0) for b in cfg('BASICS', []))
        ctx['energy_in_deck'] = sum(_dc.get(e, 0) for e in _energy_ids)
        ctx['pokes_in_deck'] = ctx['basics_in_deck'] + _dc.get(DIPPLIN, 0) + _dc.get(THWACKEY, 0) + _dc.get(RABSCA, 0)
    except Exception:
        pass
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

    # 5. Attack: oracle-simulated outcome first (win > prizes > damage),
    # heuristic fallback.
    if attacks:
        orc = (ctx.get('oracle') or {}) if cfg('USE_ORACLE_ATTACK', 1) else {}
        if orc:
            best_i = max(orc, key=lambda i: orc[i])
            return [best_i]
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


# ============ v4: card tracking, prize inference, attack oracle ============
_TRK = {"prized": None, "pre_ko": False, "cur_log": [], "pre_log": [], "turn_seen": -1}

def _trk_reset():
    _TRK["prized"] = None; _TRK["pre_ko"] = False
    _TRK["cur_log"] = []; _TRK["pre_log"] = []

def _remaining_counts(obs):
    """{card id: copies still in our deck+prizes} via serial tracking."""
    from collections import Counter as _C
    counts = _C(read_deck_csv())
    seen = set()
    my_i = obs.current.yourIndex
    def add(card):
        if card is None:
            return
        ser = getattr(card, "serial", None)
        if ser is None or ser in seen:
            return
        pi = getattr(card, "playerIndex", None)
        if pi is not None and pi != my_i and not hasattr(card, "energyCards"):
            return
        seen.add(ser)
        counts[card.id] -= 1
        for e in (getattr(card, "energyCards", None) or []): add(e)
        for t in (getattr(card, "tools", None) or []): add(t)
        for pv in (getattr(card, "preEvolution", None) or []): add(pv)
    st = obs.current; my = st.players[my_i]
    for c in (my.hand or []): add(c)
    for c in (my.discard or []): add(c)
    for c in [a for a in (my.active or []) if a] + [b for b in (my.bench or []) if b]: add(c)
    for c in (st.stadium or []): add(c)
    for c in (st.looking or []) if st.looking else []: add(c)
    return counts

def _track(obs):
    st = obs.current
    if st is None:
        return
    if st.turn == 0 and _TRK["turn_seen"] > 0:
        _trk_reset()
    _TRK["turn_seen"] = st.turn
    for log in (obs.logs or []):
        _TRK["cur_log"].append(log)
        if log.type == LogType.TURN_END:
            _TRK["pre_log"] = _TRK["cur_log"]; _TRK["cur_log"] = []
    my_i = st.yourIndex
    _TRK["pre_ko"] = any(
        getattr(l, "type", None) == LogType.MOVE_CARD and l.playerIndex == my_i
        and l.fromArea in (AreaType.BENCH, AreaType.ACTIVE) and l.toArea == AreaType.DISCARD
        for l in _TRK["pre_log"])
    # exact prize inference whenever the engine shows us our deck contents
    if obs.select is not None and obs.select.deck is not None:
        rem = _remaining_counts(obs)
        for card in obs.select.deck:
            rem[card.id] -= 1
        _TRK["prized"] = {k: max(0, v) for k, v in rem.items() if v > 0}

def deck_counts(obs):
    """{card id: copies actually in DECK} (remaining minus known prizes)."""
    rem = _remaining_counts(obs)
    if _TRK["prized"]:
        for k, v in _TRK["prized"].items():
            rem[k] -= v
    return {k: max(0, v) for k, v in rem.items()}

_ORC = {"busy": False}

def _oracle_dispatch(o):
    t = o.select.type
    if t in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD):
        r = choose_cards(o)
    elif t == SelectType.YES_NO: r = choose_yes_no(o)
    elif t == SelectType.ATTACK: r = choose_attack(o)
    elif t == SelectType.COUNT: r = choose_count(o)
    elif t == SelectType.EVOLVE: r = choose_cards(o)
    elif t == SelectType.ENERGY:
        r = pick_by_priority(o, o.select, cfg('ENERGY_DISCARD', []), count=max(o.select.minCount, 1))
    else: r = safe_fallback(o.select)
    return _validate(r, o.select)

def oracle_attacks(obs):
    """Simulate each ATTACK option in the current select: exact damage,
    prizes gained, win. Returns {opt_idx: (win, prizes, damage)} or {}."""
    if _ORC["busy"] or obs.search_begin_input is None:
        return {}
    atk = [i for i, o in enumerate(obs.select.option) if o.type == OptionType.ATTACK]
    if not atk:
        return {}
    _ORC["busy"] = True
    try:
        from cg.api import search_begin, search_step, search_end
        my_i = obs.current.yourIndex
        my_p = me(obs); op = opp(obs)
        pool = list(_remaining_counts(obs).elements())
        random.shuffle(pool)
        need = my_p.deckCount + len(my_p.prize or [])
        pool += [1] * max(0, need - len(pool))
        root = search_begin(obs, pool[:my_p.deckCount],
                            pool[my_p.deckCount:need],
                            [741] + [5] * max(0, op.deckCount - 1),
                            [5] * len(op.prize or []),
                            [5] * (op.handCount or 0), [741])
        prz0 = len(my_p.prize or [])
        oa0 = (op.active or [None])[0]
        hp0 = (oa0.hp if oa0 else 0) or 0
        ser0 = oa0.serial if oa0 else None
        out = {}
        for i in atk:
            s = search_step(root.searchId, [i])
            o, depth = s.observation, 0
            while (o.select is not None and o.current.result == -1
                   and o.current.yourIndex == my_i and depth < 12):
                if o.select.type == SelectType.MAIN:
                    break
                s = search_step(s.searchId, _oracle_dispatch(o))
                o = s.observation
                depth += 1
            cur = o.current
            if cur.result != -1:
                if cur.result == my_i:
                    out[i] = (True, 6, 999)      # winning line: take it
                else:
                    out[i] = (False, -9, -999)   # losing/draw line: never
                continue
            my2 = cur.players[my_i]; op2 = cur.players[1 - my_i]
            prz = prz0 - len(my2.prize or [])
            oa1 = (op2.active or [None])[0]
            if oa1 is not None and oa1.serial == ser0:
                dmg = hp0 - ((oa1.hp or 0))
            else:
                dmg = hp0     # active left the field: treat as full damage
            out[i] = (False, prz, max(0, dmg))
        search_end()
        return out
    except Exception:
        try:
            from cg.api import search_end
            search_end()
        except Exception:
            pass
        return {}
    finally:
        _ORC["busy"] = False
# ===========================================================================


def dynamic_fetch(obs):
    """Need-aware search priority (Thwackey tutors ANY card every turn —
    what to grab depends entirely on what the board is missing)."""
    my = me(obs)
    hand_ids = [c.id for c in (my.hand or [])]
    in_play = my_in_play(obs)
    play_ids = [p.id for p in in_play]
    st = obs.current
    stadium = st.stadium[0] if (st.stadium and st.stadium[0]) else None
    pri = []
    try:
        _e_in_deck = deck_counts(obs).get(1, 1)
    except Exception:
        _e_in_deck = 1
    # ANTI-TANK (v4): when the opponent's active out-HPs our whole turn
    # (Archaludon/Mega Starmie walls) but their bench is KO-able, the tutor's
    # job is fetching Boss's Orders — farm 6 prizes from the support line.
    n_bench = len([b for b in (my.bench or []) if b])
    _op = opp(obs)
    _oa = (_op.active or [None])[0]
    _wave_full = 40 * n_bench
    if (_oa is not None and ((_oa.hp or 0) > _wave_full)
            and any(b is not None and (b.hp or 999) <= _wave_full for b in (_op.bench or []))
            and 1182 not in hand_ids):
        pri.append(1182)
    # replacement secured -> energy outranks the next Dipplin (v3): one fetch
    # per turn can't cover both attrition and banking; bank when safe.
    total_e_early = sum(len(p.energies or []) for p in in_play) + hand_ids.count(1)
    dipplin_secured = (play_ids.count(DIPPLIN) + hand_ids.count(DIPPLIN)) >= 2
    if dipplin_secured and total_e_early < cfg('ENERGY_STOCK', 2) and _e_in_deck > 0:
        pri.append(1)
    if DIPPLIN not in play_ids and DIPPLIN not in hand_ids:
        pri.append(DIPPLIN)
    if APPLIN not in play_ids and APPLIN not in hand_ids:
        pri.append(APPLIN)
    if not (stadium is not None and stadium.id == FESTIVAL) and FESTIVAL not in hand_ids:
        pri.append(FESTIVAL)     # double attack is the whole deck
    # ENERGY STOCKPILING (v2): keep ENERGY_STOCK energies live (board+hand) so
    # a KO'd Dipplin always has a charged successor — the ladder stalls all
    # came from one lone energy circulating through the discard.
    total_energy = sum(len(p.energies or []) for p in in_play)
    if total_energy + hand_ids.count(1) < cfg('ENERGY_STOCK', 2) and _e_in_deck > 0:
        pri.append(1)
    if THWACKEY not in play_ids and THWACKEY not in hand_ids:
        pri.append(THWACKEY)
        if GROOKEY not in play_ids and GROOKEY not in hand_ids:
            pri.append(GROOKEY)
    if n_bench < 5:
        pri += [APPLIN, GROOKEY, SHAYMIN, RELLOR, GENESECT, 1086]
    if RABSCA not in play_ids:
        pri += [RABSCA] if RELLOR in play_ids else [RELLOR]
    return pri + [1182, 1, DIPPLIN, THWACKEY, 1227, 1094, 1152] + cfg('FETCH_PRIORITY', [])


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
    orc = oracle_attacks(obs) if cfg('USE_ORACLE_ATTACK', 1) else {}
    if orc:
        return [max(orc, key=lambda i: orc[i])]
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
    try:
        _track(obs)
    except Exception:
        pass
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
