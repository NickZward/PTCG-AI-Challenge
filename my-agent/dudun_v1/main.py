"""Rule-based agent dudun_v1 — Dudunsparce / Mega Lopunny ex adjudication-race
pilot on the grimmsnarl_v17 skeleton. Deck: the ladder #3's exact 60 (72-replay
mined, 2026-08-03).

Game plan (measured from the source pilot, 58-14): open Dunsparce/Buneary,
Poffin-flood the bench, evolve two M-Lopunny by T3-4, then every turn
free-retreat (Air Balloon) -> promote the other Lopunny -> Gale Thrust 230
(60+170 only on the turn it moves bench->active). Dudunsparce = draw-3 engine
that shuffles itself back (anti-deckout); Wally full-heal + Enriching-Energy
(attach = draw 3) recycle sustains the tank. 93% of its games end adjudicated
at the T13-15 cap with a 4-5 to 0-3 prize lead.
"""

import json as _json
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
DUNSPARCE, DUDUNSPARCE = 305, 66
BUNEARY, MLOPUNNY, FANROTOM = 848, 849, 174
MIST, ENRICHING, SPIKY = 11, 13, 14
AIRBALLOON, POFFIN, ULTRABALL, POKEGEAR, POKEPAD = 1174, 1086, 1121, 1122, 1152
BOSS, XEROSIC, HILDA, LILLIE, WALLY = 1182, 1197, 1225, 1227, 1229

CONFIG = {
 'MY_TYPE': 0,                     # colorless — nothing is weak to it
 'BASICS': [DUNSPARCE, BUNEARY, FANROTOM],
 'STAGE2S': set(),                 # no Rare Candy line in this deck
 'MIN_BENCH': 3,
 'ABILITIES': {DUDUNSPARCE, FANROTOM},   # Run Away Draw; Fan Call (engine gates T1)
 'DRAW_ABILITIES': {DUDUNSPARCE},
 'EVOLVE_ORDER': [DUDUNSPARCE, MLOPUNNY],   # source T2: engine first (1.76 vs 1.22 evolves)
 'TRIGGER_ENERGY': {ENRICHING},    # attach = draw 3: always attach it first
 'ENERGY_TARGET_OVERRIDE': {},
 'KEEP_ACTIVE': {MLOPUNNY},        # generic retreat leaves the tank; cycle rule below handles it
 'RETREAT_MIN_ENERGY': 1,          # Gale Thrust needs 1
 'ATTACH_TARGETS': [MLOPUNNY, BUNEARY],   # NEVER the Dudunsparce line (shuffles away)
 'ENERGY_CAP': 2,                  # Spiky Hopper needs 2; never stack more
 'ATTACK_MIN_ENERGY': 1,
 'ENERGY_IDS': [MIST, ENRICHING, SPIKY],
 'FETCH_PRIORITY': [MLOPUNNY, DUDUNSPARCE, BUNEARY, DUNSPARCE, ENRICHING,
                    AIRBALLOON, FANROTOM, MIST, SPIKY, WALLY, HILDA],
 # DELIBERATE deviation from the source pilot (they open Rotom/Dunsparce and
 # rotate out later): we open BUNEARY — it evolves into the 330HP Mega IN PLACE,
 # which needs none of the retreat machinery. Probed: junk-opener-stuck-active
 # was our #1 bleed (19 dead end-turns / 8 games).
 'SETUP_PRIORITY': [BUNEARY, DUNSPARCE, FANROTOM],
 # PROMOTE: a CHARGED Lopunny promotes into a 230 Gale next turn; a DRY Lopunny
 # promoted = a 3-prize gift (Mega died in 11/14 of the source pilot's losses,
 # never twice in any game) — custom scorer in choose_cards enforces charged-
 # first / fodder-before-dry-Mega. This list is the coarse tail order.
 'PROMOTE_PRIORITY': [MLOPUNNY, DUNSPARCE, BUNEARY, FANROTOM, DUDUNSPARCE],
 # measured from the pilot's Ultra Ball costs: SPARE SUPPORTERS discard first
 # (Lillie x82, Hilda x66 — they're 4-ofs and one-per-turn); energy LAST
 'DISCARD_PRIORITY': [LILLIE, HILDA, POKEGEAR, XEROSIC, POFFIN, POKEPAD,
                      ULTRABALL, BOSS, FANROTOM, DUNSPARCE, BUNEARY, WALLY,
                      SPIKY, MIST, AIRBALLOON, DUDUNSPARCE, ENRICHING, MLOPUNNY],
 'ENERGY_DISCARD': [ENRICHING, MIST, SPIKY],  # our attacks never discard energy —
                      # every ENERGY pick is Wally's return-to-hand: take Enriching
                      # (re-attach next turn = draw 3 again)
 'RECOVERABLE': {DUNSPARCE, DUDUNSPARCE, BUNEARY, MLOPUNNY, FANROTOM},
 'BENCH_FILLERS': {POFFIN},
 'HAND_IS_AMMO': False,
 'READY_ATTACKERS': {MLOPUNNY},
 'ATTACKER_LINE': {BUNEARY, MLOPUNNY},   # active may evolve along this line
 'SETUP_RANK_MAX': 5,
 # -------- tunable knobs (overridden by params.json) --------
 'COLLAPSE_BENCH': 2,     # bench below this + no basic in hand => dig mode
 'LILLIES_MAX_HAND': 5,   # play Lillie when hand <= this (draw 8 while un-prized)
 'BOSS_KO_MAX': 230,      # Boss's Orders when opp active hp <= this
 'BOSS_BENCH_MAX': 230,   # ...or a bench target Gale can finish (post-rotation 230)
 'ROTATE_HP': 180,        # tank loop: rotate the active Mega at/below this HP (source: 85-89%)
 'WALLY_HEAL_AT': 100,    # Wally full-heal once a Mega has soaked this much
 'RACE_DECK_AT': 20,
 'RACE_MARGIN': 3,
 'DECK_LOW_AT': 8,
 'XEROSIC_HAND': 6,       # Xerosic jumps the queue when opp hand >= this
 # -------- v8 anti-lock escape --------
 'ESCAPE_LOCK': 1,        # unstick a 0-energy body trapped active
 'ESCAPE_TOOLS': [AIRBALLOON],   # Air Balloon = free retreat
}

_SET_KEYS = {'STAGE2S', 'ABILITIES', 'DRAW_ABILITIES', 'KEEP_ACTIVE', 'RECOVERABLE',
             'BENCH_FILLERS', 'READY_ATTACKERS', 'TRIGGER_ENERGY'}
def _params_path():
    """Kaggle execs main.py WITHOUT __file__ defined. A bare __file__ reference therefore
    raises NameError and, inside a blanket try/except, SILENTLY discards params.json — which
    is where this agent's whole deck configuration lives. Resolve defensively, like _base()
    in grimm_v12_live/main.py does for its model."""
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    dirs += ["/kaggle_simulations/agent", os.getcwd(), "."]
    for _d in dirs:
        _p = os.path.join(_d, "params.json")
        if os.path.exists(_p):
            return _p
    return None

PARAMS_LOADED = False
_pp = _params_path()
if _pp:
    try:
        for _k, _v in _json.load(open(_pp)).items():
            CONFIG[_k] = set(_v) if _k in _SET_KEYS else _v
        PARAMS_LOADED = True
    except Exception:
        pass

def PLAY_PRIORITY(cid, c):
    if c.get('hard_low') and cid in (LILLIE, POKEPAD, POKEGEAR, POFFIN, ULTRABALL):
        return 99
    # bench the board out — source pilot benches 1.6 basics on T1 alone
    if cid in (DUNSPARCE, BUNEARY, FANROTOM) and c['n_bench'] < 5: return 0
    # SETUP COLLAPSE GUARD: bench nearly empty and no basic in hand — dig with
    # everything before the active gets sniped out from under us.
    if c['n_bench'] < CONFIG['COLLAPSE_BENCH'] and not any(x.id in CONFIG['BASICS'] for x in c['hand']):
        if cid == POFFIN: return 1
        if cid in (POKEPAD, ULTRABALL): return 2
        if cid == POKEGEAR: return 2   # digs for Hilda/Lillie
    # WALLY FULL-HEAL: the tank must never die — Mega death = 3 prizes and shows
    # up in 11/14 of the source pilot's losses. Their Wally cadence: 1.8/game, T4-6.
    if cid == WALLY and c.get('lop_dmg', 0) >= CONFIG['WALLY_HEAL_AT']: return 1
    # LILLIE early: draw 8 while un-prized was their T2 supporter in 51% of games
    if cid == LILLIE and c.get('prizes_full') and len(c['hand']) <= 7: return 4
    if cid == POFFIN and c.get('basics_in_deck', 1) == 0: return 99
    if cid == POFFIN and c['n_bench'] < 5: return 3
    # BOSS = REMOVAL (39/49 of their gusts attacked same turn, 32/49 converted a KO)
    if cid == BOSS and c['has_attacks'] and c['opp_hp'] <= c.get('oracle_dmg', CONFIG['BOSS_KO_MAX']):
        return 99  # active already dies — never waste the gust
    if cid == BOSS and c['has_attacks'] and c.get('opp_bench_min_hp', 999) <= c.get('oracle_dmg', CONFIG['BOSS_BENCH_MAX']): return 3
    # HILDA: Lopunny + energy in one card — the line completer (their T1-2 staple)
    if cid == HILDA and (c.get('need_lop') or not any(x.id in CONFIG['ENERGY_IDS'] for x in c['hand'])): return 4
    if cid == ULTRABALL and c.get('need_lop') and len(c['hand']) >= 4: return 5
    if cid == POKEPAD and (c.get('need_lop') or c.get('need_dudun')): return 5
    # AIR BALLOON onto the Lopunny line = the free-rotation engine
    if cid == AIRBALLOON and c.get('balloon_want'): return 6
    # LILLIE: draw 8 while un-prized (their T2 supporter 51% of games), draw 6 after
    if cid == LILLIE and len(c['hand']) <= CONFIG['LILLIES_MAX_HAND']: return 7
    if cid == XEROSIC:                                    # strip big hands
        try:
            if c.get('opp_hand', 0) >= CONFIG['XEROSIC_HAND']:
                return 2
        except Exception:
            pass
        return 13
    if cid == WALLY and c.get('lop_dmg', 0) >= 60: return 9
    # RACE GATES: optional dig stops when the deck race is on (they never deck out)
    if c.get('deck_race') and cid in (POKEGEAR, POKEPAD): return 99
    if cid == HILDA: return 11
    if cid == POKEGEAR: return 12
    if cid == POKEPAD: return 14
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
    if name == "Gale Thrust":
        # 60 + 170 if this Pokemon moved bench->active THIS turn (the whole deck
        # is built around triggering this). The oracle computes it exactly; this
        # heuristic covers the no-oracle fallback.
        a = me(obs).active
        if a and a[0] and getattr(a[0], "appearThisTurn", False):
            dmg += 170
    elif name == "Assault Landing":
        if not (obs.current.stadium and obs.current.stadium[0]):
            dmg = 0
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


# ------------------------------------------------ v8 anti-lock escape
# Instrumentation (verification only; harmless in play): lock_dp counts MAIN
# decision-points spent in the stuck state; esc_* count escape actions taken.
_INSTR = {'lock_dp': 0, 'esc_tool': 0, 'esc_attach': 0, 'esc_retreat': 0}

def _escape_lock(obs, select, plays, attach, act_enabled=True):
    """A 0-energy body is trapped ACTIVE — can't attack, can't pay any retreat
    cost — while a charged, ready attacker sits benched. This is the force-open
    lock (no Marnie's Impidimp in the opening hand) and the Boss's-Orders-gust
    lock (opp gusts our empty Grimmsnarl ex, stranding the charged copy) that
    recurred in 6/8 of the first v6/v7 ladder games and threw one won game
    (ep 87233423, ahead 4/5). The v7 retreat fix only fires when RETREAT is
    ALREADY legal; a 0-energy body is never offered retreat, so nothing unsticks
    it. Here we BUY the escape: retreat if now legal, else (no escape tool in
    this deck) funnel this turn's energy into the stuck active until retreat
    becomes legal (then it retreats into the charged attacker next pass).

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
        # legal to retreat now (cost paid via funneled energy)?
        if ridx is not None and not st.retreated:
            _INSTR['esc_retreat'] += 1
            return [ridx]
        # safety cap: never pour more than 3 energy into an escape
        if energy_count(act) >= 3:
            return None
        # 1. put an escape tool on the stuck active. Air Balloon surfaces as an
        # ATTACH option (type 8) targeting the active — and tool attachment is
        # NOT once-per-turn, so do not gate this on st.energyAttached.
        if not act.tools:
            hand = my.hand or []
            esc_tools = set(cfg('ESCAPE_TOOLS', []))
            for i, o in attach:
                if o.inPlayArea == AreaType.ACTIVE:
                    src = hand[o.index].id if (o.area == AreaType.HAND and o.index is not None
                                               and o.index < len(hand)) else None
                    if src in esc_tools:
                        _INSTR['esc_tool'] += 1
                        return [i]
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
    # MILL-RACE MODE (v5): every ladder game ends in deck-out — once setup is
    # done and we're not ahead on cards, voluntary deck consumption stops.
    deck_race = (my.deckCount < cfg('RACE_DECK_AT', 30)
                 and my.deckCount <= opp(obs).deckCount + cfg('RACE_MARGIN', 3))

    # 1. Conditional abilities.
    # v7: draw abilities are only gated when the deck is CRITICALLY low, or when
    # the hand is already stocked — hand size IS our damage (Powerful Hand), so
    # starving the hand to save deck lost far more games than deck-out did.
    for i, o in abilities:
        cid = option_card_id(obs, o)
        if cid in cfg('ABILITIES', set()):
            if cid in cfg('DRAW_ABILITIES', set()):
                if my.deckCount < 5:
                    continue
                if deck_low and len(hand) >= 6:
                    continue
            if cid == DUDUNSPARCE:
                # Run Away Draw shuffles itself + its Dunsparce back in: never
                # strand a thin board, never vaporize our own ACTIVE mid-fight,
                # and DON'T over-fire — the source pilot hoards toward an 8-11
                # card hand and spaces the draws (agreement mining: our #1
                # over-pick, ~860 ability choices where they did something else)
                act0 = my.active[0] if my.active else None
                if act0 is not None and act0.id == DUDUNSPARCE:
                    continue
                if in_play >= 4:
                    return [i]
            else:
                return [i]

    # 2. Evolve (Stage2 target first, then configured order).
    if evolve:
        order = cfg('EVOLVE_ORDER', [])
        line = cfg('ATTACKER_LINE', cfg('READY_ATTACKERS', set()))
        def erank(t):
            o = t[1]
            cid = option_card_id(obs, o)
            # ANTI-LOCK (v7): never evolve the ACTIVE into a non-attacker-line
            # Pokemon (Froslass). A 0-energy support stuck active stalls setup
            # (Grimmsnarl never comes online in 15/132 field losses). Support
            # evolves belong on the bench; the active stays Impidimp->Grimmsnarl.
            if getattr(o, 'inPlayArea', None) == AreaType.ACTIVE and cid not in line:
                return 999
            return order.index(cid) if cid in order else len(order)
        evolve.sort(key=erank)
        if erank(evolve[0]) < 999:
            return [evolve[0][0]]

    # 2.5 ANTI-LOCK ESCAPE (v8): unstick a 0-energy body trapped active while a
    # charged attacker waits on the bench (force-open / Boss's-gust lock).
    esc = _escape_lock(obs, select, plays, attach, act_enabled=bool(cfg('ESCAPE_LOCK', 1)))
    if esc is not None:
        return esc

    # 3a. TOOLS (Air Balloon surfaces as an ATTACH option, same as energy, but is
    # NOT once-per-turn): place a balloon on the rotation engine the moment we
    # hold one — the free retreat IS the 230 loop (source pilot: 50% of T1
    # attachments are Balloon-on-Buneary; 219/219 of their rotations were free).
    if attach:
        def _tgt_of(o):
            if o.inPlayArea == AreaType.ACTIVE:
                return my.active[o.inPlayIndex] if my.active else None
            if o.inPlayIndex is not None and o.inPlayIndex < len(my.bench or []):
                return my.bench[o.inPlayIndex]
            return None
        balloons = []
        for i, o in attach:
            src = hand[o.index].id if (o.area == AreaType.HAND and o.index is not None
                                       and o.index < len(hand)) else None
            if src == AIRBALLOON:
                balloons.append((i, o))
        if balloons:
            def bscore(t):
                pkm = _tgt_of(t[1])
                if pkm is None: return (9, 0)
                if any(getattr(tl, 'id', None) == AIRBALLOON for tl in (pkm.tools or [])):
                    return (8, 0)          # already ballooned
                order = {MLOPUNNY: 0, BUNEARY: 1, DUDUNSPARCE: 2, DUNSPARCE: 3}
                return (order.get(pkm.id, 4), -energy_count(pkm))
            best = min(balloons, key=bscore)
            if bscore(best)[0] < 8:
                return [best[0]]

    # ENERGY ATTACH — deliberately evaluated in a helper so the ladder can call
    # it AFTER trainer plays (source pilot sequencing: dig/search FIRST, attach
    # LAST — e.g. Hilda fetches the Enriching you then attach for draw 3; our
    # old attach-first order burned the once-per-turn attach on a worse energy.
    # Agreement mining: play->attach was the single biggest confusion, 323 cases).
    def _energy_attach():
        if not (attach and not st.energyAttached):
            return None
        trig = cfg('TRIGGER_ENERGY', set())
        att_pri = cfg('ATTACH_TARGETS', [])
        override = cfg('ENERGY_TARGET_OVERRIDE', {})
        energy_ids_set = set(cfg('ENERGY_IDS', []))
        att_e = [(i, o) for i, o in attach
                 if (o.area == AreaType.HAND and o.index is not None
                     and o.index < len(hand) and hand[o.index].id in energy_ids_set)] or attach
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
            is_active = (o.inPlayArea == AreaType.ACTIVE)
            en = energy_count(pkm) if pkm is not None else 0
            ready = cid in cfg('READY_ATTACKERS', set())
            atk_min = cfg('ATTACK_MIN_ENERGY', cfg('ENERGY_CAP', 2))
            # v9 energy routing (fixes 4 energy_misplay losses): (0) ARM the ACTIVE
            # attacker to attack THIS turn; (1) then bank a bench attacker BACKUP;
            # (2) build other attach targets (Munkidori); (3) DON'T over-stack an
            # already-armed attacker — Punk Up loads 5 D, piling more onto one
            # Grimmsnarl then losing it to a KO dumps the whole Darkness supply into
            # the (unrecoverable) discard and leaves every later Grimmsnarl at 0;
            # (4) never feed scarce energy to non-attackers.
            # v14 ENGINE BOOTSTRAP (from LIVE v12r data vs bono, 2026-07-22): bono's game is
            # a loop — energize Munkidori turn ~2, fire Adrena-Brain EVERY turn (5.47/game vs
            # our 1.43), self-heal the pings, never die (0.39 vs our 0.70 deaths/game). Our
            # live pilot already routes 67% of dry-Munkidori+dark turns to Munkidori, but the
            # missed 33% + 7/23 games NEVER energized keep the engine off. Rule: a DRY
            # Munkidori takes the manual Dark over everything except an ACTIVE attacker that
            # can be armed to swing (Punk Up feeds the attacker line; manual attaches are
            # Munkidori's ONLY supply). Verify via fires/game + energized-rate mech metrics.
            if cid not in att_pri:
                # RETREAT FUEL: a dry junk body stuck ACTIVE while a CHARGED Mega
                # waits behind it gets one energy to buy the retreat — this
                # converts a dead turn into a rotation + Gale 230, so it outranks
                # even charging the bench (probe: priority inversion here left
                # stuck actives passing turns with energy in hand)
                if (is_active and en == 0
                        and any(b is not None and b.id == MLOPUNNY and energy_count(b) >= 1
                                for b in (my.bench or []))):
                    arm = 0.5
                elif (is_active and en == 0
                        and any(b is not None and b.id in (MLOPUNNY, BUNEARY)
                                for b in (my.bench or []))):
                    arm = 2
                else:
                    arm = 5
            elif ready and en < atk_min and is_active:
                arm = 0                      # arm the ACTIVE attacker to swing this turn
            elif ready and en < atk_min:
                arm = 1                      # dry bench Mega: the rotation partner MUST
                                             # stay charged or the 230 loop stalls
            elif en < cfg('ENERGY_CAP', 2):
                arm = 3
            else:
                arm = 4
            return (src_rank, arm, tgt_rank)
        best = min(att_e, key=lambda t: score(t[1]))
        # HOLD the energy rather than feed a non-target (8 energy in the whole
        # deck; one wasted on a body that shuffles away = a dead rotation turn)
        if score(best[1])[1] < 5:
            return [best[0]]
        return None

    # 3. Attach energy EARLY (reverted: gate-2's attach-after-plays regressed
    # tempo 1.27->0.76 — Lillie hand-refreshes shuffled away the held energy)
    _ea = _energy_attach()
    if _ea is not None:
        return _ea

    # 3.15 TANK ROTATION (the deck's core identity, mined from 242 source-pilot
    # swaps): pre-attack, rotate the ACTIVE Mega out when it is damaged to
    # ROTATE_HP or below (they rotate 85-89% at <=180, only 12% when fresh) or
    # when it is dry, PROVIDED a charged Mega waits on the bench — the incoming
    # Lopunny attacks Gale Thrust for 230 (fresh-off-the-bench bonus) and the
    # damaged one heals up behind (Wally). Free with Air Balloon; otherwise the
    # 1-energy retreat cost is still worth +170 damage when we're the healthy side.
    retreat_idx = next((i for i, o in enumerate(select.option)
                        if o.type == OptionType.RETREAT), None)
    if retreat_idx is not None and not st.retreated:
        act = my.active[0] if my.active else None
        if act is not None and act.id == MLOPUNNY:
            charged = [b for b in (my.bench or [])
                       if b is not None and b.id == MLOPUNNY and energy_count(b) >= 1]
            hurt = (act.hp or 0) <= cfg('ROTATE_HP', 180)
            # source pilot also rotates 44% in the 181-240 band — take those when
            # the incoming Mega is FRESH (full HP): trades nothing, gains the 230
            soft = ((act.hp or 0) <= 240
                    and any((b.hp or 0) >= (b.maxHp or 330) for b in charged))
            dry = energy_count(act) == 0
            if charged and (hurt or soft or dry):
                return [retreat_idx]

    # 3.2 RETREAT (v7): if the active can't fight and a ready
    # attacker is benched, retreat into it.
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

    # 3.6 TAKE THE KO (v9): when the active can attack for a KO/prize NOW, do it
    # instead of durdling — several losses left a free KO on the board (opp active
    # at 10-20 HP) for 20-30 turns while bench-sniping and self-milling.
    if attacks and not cfg('HAND_IS_AMMO'):
        best_dmg = max((effective_damage(obs, o.attackId) for _, o in attacks), default=0)
        if best_dmg >= opp_hp:
            best = None
            for i, o in attacks:
                d = effective_damage(obs, o.attackId)
                k = (0, d) if d >= opp_hp else (1, -d)
                if best is None or k < best[0]:
                    best = (k, i)
            return [best[1]]
        _orc = oracle_attacks(obs) if cfg('USE_ORACLE_ATTACK', 1) else {}
        if _orc and any((w or pz >= 1) for (w, pz, d) in _orc.values()):
            return [max(_orc, key=lambda i: _orc[i])]

    # 4. Play trainers / Pokemon by configured priority function.
    our_stadium = False               # no stadium in this deck
    opp_act = opp(obs).active
    opp_ci = card_info(opp_act[0].id) if (opp_act and opp_act[0]) else None
    energy_ids = set(cfg('ENERGY_IDS', [1]))
    _board = my_in_play(obs)
    _play_ids = [p.id for p in _board]
    _hand_ids = [c.id for c in hand]
    ctx = {
        'lop_dmg': max([((p.maxHp or 0) - (p.hp or 0)) for p in _board
                        if p.id == MLOPUNNY] or [0]),
        'need_lop': (_play_ids.count(MLOPUNNY) + _hand_ids.count(MLOPUNNY) < 2
                     and (BUNEARY in _play_ids or BUNEARY in _hand_ids)),
        'need_dudun': (DUDUNSPARCE not in _play_ids and DUDUNSPARCE not in _hand_ids),
        'balloon_want': any(p.id in (MLOPUNNY, BUNEARY, DUDUNSPARCE)
                            and not any(getattr(t, 'id', None) == AIRBALLOON
                                        for t in (p.tools or []))
                            for p in _board),
        'prizes_full': len(my.prize or []) == 6,
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
        'deck_race': deck_race,
        'opp_hand': opp(obs).handCount or 0,
        'opp_is_ex': bool(opp_ci is not None and getattr(opp_ci, 'ex', False)),
        'energy_drought': (sum(len(p.energies or []) for p in my_in_play(obs)) == 0
                          and not any(c.id in energy_ids for c in hand)),
        'energy_in_discard': any(c.id in energy_ids for c in (my.discard or [])),
        'pre_ko': _TRK.get('pre_ko', False),
    }
    # v6 ORACLE: exact damage by simulation replaces the static Boss gates
    try:
        _orc = oracle_attacks(obs)
        ctx['oracle'] = _orc
        if _orc and cfg('USE_ORACLE_DMG', 1):
            ctx['oracle_dmg'] = max(d for _, _, d in _orc.values())
        _dc = deck_counts(obs)
        ctx['basics_in_deck'] = sum(_dc.get(b, 0) for b in cfg('BASICS', []))
        ctx['energy_in_deck'] = sum(_dc.get(e, 0) for e in energy_ids)
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
            return [max(orc, key=lambda i: orc[i])]
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
        pool += [MIST] * max(0, need - len(pool))
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
    """Need-aware search priority — what to grab depends on what the board is
    missing (basics when benchless, then the two-Mega rotation engine)."""
    my = me(obs)
    hand_ids = [c.id for c in (my.hand or [])]
    in_play = my_in_play(obs)
    play_ids = [p.id for p in in_play]
    n_bench = len([b for b in (my.bench or []) if b])
    pri = []
    # 1. Bench safety: benchless with no basic in hand -> ANY basic first.
    if n_bench < cfg('MIN_BENCH', 3) and not any(h in cfg('BASICS', []) for h in hand_ids):
        pri += [DUNSPARCE, BUNEARY, FANROTOM]
    # 2. THE TWO-MEGA ENGINE: the rotation needs 2 Lopunnies; a fetched Mega is
    #    live as soon as any Buneary is down.
    n_lop = play_ids.count(MLOPUNNY) + hand_ids.count(MLOPUNNY)
    n_bun = play_ids.count(BUNEARY)
    if n_lop < 2 and (n_bun > 0 or BUNEARY in hand_ids):
        pri.append(MLOPUNNY)
    if play_ids.count(BUNEARY) + hand_ids.count(BUNEARY) + play_ids.count(MLOPUNNY) < 2:
        pri.append(BUNEARY)
    # 3. Draw engine: one Dudunsparce line on board keeps the gas flowing.
    if DUDUNSPARCE not in play_ids and DUDUNSPARCE not in hand_ids and DUNSPARCE in play_ids:
        pri.append(DUDUNSPARCE)
    if DUNSPARCE not in play_ids and DUNSPARCE not in hand_ids:
        pri.append(DUNSPARCE)
    # 4. ENERGY IS THE SCARCE RESOURCE (8 in 60): a dry Mega on board makes
    #    energy the TOP fetch — a benched Lopunny with 0 energy is a stalled
    #    rotation and a stalled rotation is a lost prize race.
    if any(p.id == MLOPUNNY and len(p.energies or []) == 0 for p in in_play) and \
            not any(h in cfg('ENERGY_IDS', []) for h in hand_ids):
        pri = [ENRICHING, MIST, SPIKY] + pri
    elif ENRICHING not in hand_ids:
        pri.append(ENRICHING)
    # 6. Balloon for the rotation if none held and a bare Mega is out.
    if AIRBALLOON not in hand_ids and any(
            p.id == MLOPUNNY and not any(getattr(t, 'id', None) == AIRBALLOON
                                         for t in (p.tools or []))
            for p in in_play):
        pri.append(AIRBALLOON)
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

    if ctx == SelectContext.TO_BENCH:
        # Poffin-class direct-bench: the pilot benches DUNSPARCE 2.5:1 over
        # Buneary (draw-engine fodder first; the Lopunny line comes via hand)
        return pick_by_priority(obs, select, [DUNSPARCE, BUNEARY, FANROTOM] + fetch,
                                count=select.maxCount)
    if ctx in (SelectContext.TO_HAND, SelectContext.TO_FIELD):
        return pick_by_priority(obs, select, fetch, count=select.maxCount)

    if ctx in (SelectContext.EVOLVES_FROM, SelectContext.EVOLVES_TO, SelectContext.EVOLVE):
        return pick_by_priority(obs, select, cfg('EVOLVE_ORDER', []) + fetch, count=max(select.minCount, 1))

    if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
        opp_side = [o for o in select.option if o.playerIndex is not None and o.playerIndex != my_index]
        if opp_side and len(opp_side) == len([o for o in select.option if o.playerIndex is not None]):
            # v17 GUST TARGETING (July mining, 122 expert gusts + anti-Alakazam autopsy):
            # pros drag up the most VALUABLE KO-able threat / most-energized strand target,
            # not the lowest-HP fodder. Winners vs Alakazam KO 2.68 completed Alakazams per
            # game (we managed 1.63 farming Abras with the old lowest-HP rule). Rank:
            # (1) KO-able this turn (hp <= our best damage), threat-weighted (evolved
            # attacker line > energized > rest), (2) then most-energy (strand it), (3) hp.
            try:
                my_dmg = max((effective_damage(obs, a.attackId)
                              for p2 in (me(obs).active or []) if p2
                              for a in (getattr(p2, 'attacks', None) or [])), default=230)
            except Exception:
                my_dmg = 230   # post-rotation Gale Thrust
            # source pilot's gust book: Munkidori #1 target (14/49), then evolved
            # attackers/engines — removal, not stalling
            THREAT = {112: 3, 743: 3, 742: 2, 648: 3, 647: 2, 104: 2}
            def gust_score(i):
                o = select.option[i]
                c = card_at(obs, o.area, o.index, o.playerIndex)
                if c is None: return (9, 0, 999)
                hp = getattr(c, "hp", 999) or 999
                en = energy_count(c) if hasattr(c, "energies") else 0
                threat = THREAT.get(getattr(c, "id", None), 1 if en > 0 else 0)
                if hp <= my_dmg:
                    # KO-able: take the most valuable kill (completed line pieces first)
                    return (0, -threat, hp)
                # not KO-able: STRAND the most useless body (dry, low threat) — never
                # drag their armed attacker into the active for free
                return (1, en, threat)
            idxs = sorted(range(len(select.option)), key=gust_score)
            return idxs[:max(select.minCount, 1)]
        promote = cfg('PROMOTE_PRIORITY', [])
        def score(i):
            o = select.option[i]
            pi = o.playerIndex if o.playerIndex is not None else my_index
            c = card_at(obs, o.area, o.index, pi)
            if c is None: return (9, 0, 0)
            cid = getattr(c, "id", None)
            en = energy_count(c) if hasattr(c, "energies") else 0
            # SACRIFICE DISCIPLINE (this deck's do-not-violate rule): a CHARGED
            # Mega promotes into a 230 Gale Thrust next turn — best. A DRY Mega
            # promoted is a 3-prize gift under fire (Mega death = 11/14 of the
            # source pilot's losses; never twice in any game) — promote 1-prize
            # fodder ahead of it.
            if cid == MLOPUNNY:
                tier = 0 if en >= 1 else 2
            elif cid in (DUNSPARCE, BUNEARY, FANROTOM):
                tier = 1
            else:
                tier = 1 if cid != DUDUNSPARCE else 1   # Dudunsparce = fodder too
            r = promote.index(cid) if cid in promote else len(promote)
            return (tier, r, -en, -(getattr(c, "hp", 0) or 0))
        idxs = sorted(range(len(select.option)), key=score)
        return idxs[:max(select.minCount, min(1, select.maxCount))]

    if ctx in (SelectContext.DISCARD, SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM,
               SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
        return pick_by_priority(obs, select, cfg('DISCARD_PRIORITY', []),
                                count=select.minCount or select.maxCount)

    if ctx in (SelectContext.ATTACH_FROM, SelectContext.ATTACH_TO, SelectContext.EFFECT_TARGET):
        return pick_by_priority(obs, select, cfg('ATTACH_TARGETS', []) + fetch, count=select.maxCount)

    if ctx in (SelectContext.REMOVE_DAMAGE_COUNTER, SelectContext.HEAL):
        # Wally's Compassion targeting: heal the MOST-DAMAGED body, tie-break the
        # Mega (the tank is what must never die — source pilot's 128 heals were
        # overwhelmingly on M-Lopunny, mean 219 healed).
        def rm_dmg_score(i):
            o = select.option[i]
            pi2 = o.playerIndex if o.playerIndex is not None else my_index
            c = card_at(obs, o.area, o.index, pi2)
            if c is None: return (-1, -1, 0)
            cid = getattr(c, "id", None)
            hp = getattr(c, "hp", 0) or 0
            dmg = (getattr(c, "maxHp", 0) or 0) - hp
            return (1 if cid == MLOPUNNY else 0, dmg, hp)
        idxs = sorted(range(len(select.option)), key=rm_dmg_score, reverse=True)
        return idxs[:max(select.minCount, min(1, select.maxCount))]
    if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
        # v11 MUNKIDORI ROUTING learned from bono (#1) over 351 real placements:
        # 95% go on the BENCH, ~never the active (the active eats Shadow Bullet's 180
        # anyway) — soften bench bodies that the 30 snipe / Boss / next turn finish.
        # Then lowest HP. Sources (our Pokemon) stay last. This raised bono-agreement.
        def route(i):
            o = select.option[i]
            pi = o.playerIndex if o.playerIndex is not None else 1 - my_index
            c = card_at(obs, o.area, o.index, pi)
            hp = getattr(c, "hp", 999) or 999
            if pi != my_index:
                is_active = (o.area == AreaType.ACTIVE)
                return (0, 1 if is_active else 0, hp)   # opp BENCH first, then lowest HP
            return (1, 0, hp)                            # our own bodies last
        idxs = sorted(range(len(select.option)), key=route)
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
    # v11 (bono-learned): for Munkidori/counter MOVES, bono moves just 1 counter at
    # a time (~64%) for precise placement — NOT the max. Other counts (draw) take max.
    if select.context in (SelectContext.DAMAGE_COUNTER_COUNT, SelectContext.REMOVE_DAMAGE_COUNTER_COUNT):
        best_i, best_n = 0, 10**9
        for i, o in enumerate(select.option):
            n = o.number if o.number is not None else 0
            if 1 <= n < best_n: best_i, best_n = i, n
        return [best_i]
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
