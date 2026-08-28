"""Alakazam pilot v19 — modern body (oracle, prize inference, guards)
on Abhyuday's Battle Cage list. Powerful Hand = 2 damage counters (20 dmg) per card in
hand; it does NOT discard the hand (so attacking is free — the hold-gate exists only to
avoid shrinking the hand via ITEM plays before a big swing).

Deck: 59/60 identical to the current #2 (Majkel1337) and #3 (213tubo). v17 aligns the last
card to their list: 4 Enhanced Hammer / 2 Nighttime Mine (was 3/3).

v16 = v15 + MIRROR CONVERSION DISCIPLINE (14-agent autopsy of 31 mirror losses vs 21 elite
wins; our mirror 34% vs elite 52-70% on the identical deck; gap is CONVERSION/RESILIENCE
after Alakazam is in play, not setup speed):
  (1) ENERGY DISCIPLINE: attach only ever energizes the Alakazam line; never dead-ends our
      6 scarce psychic on Fez/Dunsparce/Dudunsparce.
  (2) FEZ PROMOTE-LAST: never volunteer the 2-prize Fezandipiti ex as active.
  (3) CANDY-BEFORE-ATTACH: resolve Rare Candy->Alakazam before the energy attach so the new
      Alakazam is energized the same turn (drove the +12pp mirror-cell / +6.2 field delta).
v17 = v16 + the 1-card DECK ALIGNMENT (4 Enhanced Hammer / 2 Nighttime Mine, matching the
current #2/#3). Validated self-play +6.6% / +0.29 prz vs v16 — 4th Hammer strips more of the
mirror opponent's Telepath special energy. AUTOPSY FIXES THAT FAILED VALIDATION (both tried,
both reverted, documented in-code): #1 rebuild-recovery-priority (lost 38% self-play — the
post-trade stall is a genuine resource brick, the value-search wall); #4 "attack every online
turn / delete hold-gate" (a NON-fix — Powerful Hand doesn't discard the hand so the pilot
already attacks every online turn; the hold-gate correctly avoids item-shrinking the hand). #5
anti-deckout = only 2/31 losses, skipped. So v17's only net change over v16 is the deck card.
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
ABRA, KADABRA, ALAKAZAM = 741, 742, 743
DUNSPARCE, DUDUNSPARCE, FEZ = 305, 66, 140
GROOKEY, THWACKEY = DUNSPARCE, DUDUNSPARCE   # body aliases
APPLIN, DIPPLIN = ABRA, ALAKAZAM
RELLOR, RABSCA = KADABRA, KADABRA
GENESECT, SHAYMIN = -1, -2
FESTIVAL = 1264                               # Battle Cage

CONFIG = {
 'MY_TYPE': 3,
 'BASICS': [ABRA, DUNSPARCE, FEZ],
 'STAGE2S': {ALAKAZAM},
 'MIN_BENCH': 3,
 'ABILITIES': {DUDUNSPARCE, FEZ},
 'DRAW_ABILITIES': {DUDUNSPARCE, FEZ},
 'EVOLVE_ORDER': [ALAKAZAM, KADABRA, DUDUNSPARCE],
 'TRIGGER_ENERGY': {13, 19},
 'ENERGY_TARGET_OVERRIDE': {},
 'KEEP_ACTIVE': {ALAKAZAM},
 'RETREAT_MIN_ENERGY': 1,
 'ATTACH_TARGETS': [ALAKAZAM, KADABRA, ABRA],
 'ENERGY_CAP': 1,                  # Powerful Hand costs {P}
 'ENERGY_IDS': [5, 13, 19],
 'FETCH_PRIORITY': [ALAKAZAM, KADABRA, ABRA, 1079, 19, 5, DUNSPARCE,
                    DUDUNSPARCE, FEZ, 1086, 1152, 1182, 1225],
 'SETUP_PRIORITY': [ABRA, DUNSPARCE, FEZ],
 # v16: Fez (Fezandipiti ex, 210hp, gives opp 2 PRIZES) moved to LAST — never volunteer
 # the 2-prize ex as active. Mirror autopsy (14-agent deep-read): our Fez died AS ACTIVE
 # in 19% of mirror losses (2 prizes each) vs Yushin 6% / our wins 0%. Keep it benched as
 # a draw engine; only promote it if literally nothing else remains.
 'PROMOTE_PRIORITY': [ALAKAZAM, KADABRA, DUNSPARCE, ABRA, DUDUNSPARCE, FEZ],
 # v11 DISCARD ORDER — measured from the July elite (Yushin 61% / Majkel 58% / bono 55%,
 # 137 Xerosic keep-3 decisions): they KEEP trainers (Xerosic 82%, Rare Candy 77%,
 # items ~70%+) and DISCARD the re-fetchable Pokemon/energy (Abra 27%, Alakazam 48%,
 # Kadabra 50%, energy 55%). Our old order was the exact INVERSE (0% agreement).
 # Order = discard-first ... keep-last, ascending measured keep%.
 'DISCARD_PRIORITY': [ABRA, ALAKAZAM, KADABRA, 305, 5, 19, 13, 1086, 1152, 1184,
                      DUNSPARCE, FEZ, DUDUNSPARCE, 343, 1264, 1266, 1081, 1182,
                      1129, 1225, 1231, 1097, 1079, 1197],
 'ENERGY_DISCARD': [5, 19, 13],
 'RECOVERABLE': {ABRA, KADABRA, ALAKAZAM, DUNSPARCE, DUDUNSPARCE},
 'BENCH_FILLERS': {1086},
 'HAND_IS_AMMO': True,
 'HAND_GROWERS': {1225, 1231, 66},  # Hilda, Dawn, Dudunsparce — play BEFORE attacking
 'READY_ATTACKERS': {ALAKAZAM},
 'ESCAPE_LOCK': 1,        # v13: ported grimm v8 escape funnel (unstick 0-energy actives)
 'ESCAPE_TOOLS': [],
 'SETUP_RANK_MAX': 5,
 # -------- tunable knobs (overridden by params.json) --------
 'ENERGY_STOCK': 2,
 'TUTOR_DECK_MARGIN': 5,
 'COLLAPSE_BENCH': 2,
 'LILLIES_MAX_HAND': 5,
 'HILDA_MAX_HAND': 10,  # v15: stop growing at 10 — convert
 # v19 ANTI-DECKOUT (fresh live data: 2/3 mirror losses = decked out while LEADING 4-3 with a
 # hoarded 22-25 card hand). Powerful Hand is already lethal at ~11 cards (220 dmg), so drawing
 # past HAND_CAP is pure overkill that only risks self-deckout; and Dawn/Hilla SEARCH -2/-3 deck
 # each so they must stop once the deck is scarce. Crown rule: deckout = instant loss even when
 # ahead on prizes.
 'HAND_CAP': 14,     # hand beyond this is overkill-lethal -> stop ALL optional draw/search
 'DECK_GUARD': 15,   # deck below this is scarce -> stop the deck-draining searches (Dawn/Hilda)
 'HOLD_HAND_AT': 9,     # v15 TEMPO: adjudication pays prize-lead at ~T13; an early hand-9 strike (180) that kills NOW beats a T10 hand-12 overkill. Elite 1st prize T6-7, ours was T9.    # v10: once Alakazam is online, HOLD cards (don't shrink Powerful Hand) when hand >= this   # v10: grow Powerful Hand to ~12 before attacking (Yushin's median; was cap 9 -> attacked at 180 not 240)
 'LILLIES_BIG_HAND': 99,   # no Lillie's here; Hilda/Dawn draw without shuffling
 'RACE_DECK_AT': 30,
 'RACE_MARGIN': 3,
 'DECK_LOW_AT': 8,         # hand is ammo: preserve deck less aggressively
 'STAMP_ON_KO': 0,
 'STAMP_BIG_HAND': 8,
}

import json as _json2
_SET_KEYS = {'STAGE2S', 'ABILITIES', 'DRAW_ABILITIES', 'KEEP_ACTIVE', 'RECOVERABLE',
             'BENCH_FILLERS', 'READY_ATTACKERS', 'TRIGGER_ENERGY'}
try:
    _pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'params.json')
    if os.path.exists(_pp):
        for _k, _v in _json2.load(open(_pp)).items():
            CONFIG[_k] = set(_v) if _k in _SET_KEYS else _v
except Exception:
    pass

def PLAY_PRIORITY(cid, c):
    if c.get('hard_low') and cid in (1225, 1231, 1152, 1086, 1097):
        return 99
    if cid in (ABRA, DUNSPARCE) and c['n_bench'] < 5: return 0
    # SETUP COLLAPSE GUARD
    if c['n_bench'] < CONFIG['COLLAPSE_BENCH'] and not any(x.id in CONFIG['BASICS'] for x in c['hand']):
        if cid == 1086: return 1
        if cid == 1152: return 1
        if cid == 1225: return 1
        if cid == 1231: return 2
    if cid == 1079 and c['stage2_in_hand']: return 1      # Candy -> Alakazam
    # v17 NOTE: a REBUILD priority (Night Stretcher/Sacred Ash boosted when lineless post-trade,
    # autopsy fix #1) was tried and REVERTED — it lost self-play 38% vs v16 (-0.82 prz). Forcing
    # recovery wastes tempo and Sacred Ash refills the DECK not the hand; the post-trade stall is
    # usually a genuine resource brick, not cheaply rule-fixable. The value-search wall again.
    if cid == FESTIVAL and not c.get('our_stadium'): return 2   # Battle Cage
    if cid == 1182 and c['has_attacks'] and c['opp_hp'] <= c.get('wave_dmg', 0): return 3
    if cid == 1182 and c['has_attacks'] and c.get('opp_bench_min_hp', 999) <= c.get('wave_dmg', 0): return 3
    if cid == 1086 and c['n_bench'] < 5: return 4
    if cid == 1152 and not c['have'](ALAKAZAM): return 5
    # draw supporters GROW THE HAND = grow the damage
    # v19: Hilda/Dawn SEARCH the deck (Hilda -2, Dawn -3) — gate by deck guard + hand cap so we
    # don't drain ourselves into a deckout once set up (they were firing at deck 7 / hand 21).
    _dk = c.get('deck_count', 99); _hd = len(c['hand'])
    if cid == 1225 and _hd <= CONFIG.get('HILDA_MAX_HAND', 12) and _dk > CONFIG.get('DECK_GUARD', 15): return 6  # Hilda
    if cid == 1231 and _hd < CONFIG.get('HAND_CAP', 14) and _dk > CONFIG.get('DECK_GUARD', 15): return 7          # Dawn
    if cid == 1197 and c.get('opp_hand', 0) >= 8: return 7
    if cid == FEZ and c['n_bench'] < 5: return 8
    if cid == 1097 and c.get('pokes_in_discard', 0) >= 2: return 9
    if cid == 1129 and c.get('pokes_in_discard', 0) >= 4: return 9   # Sacred Ash
    if cid == 1184 and c.get('pokes_in_discard', 0) >= 2: return 10
    if cid == 1081: return 11                             # Enhanced Hammer
    # v11: Nighttime Mine (Yushin/bono's swap for Enhanced Hammer) — taxes TERA attackers
    # +1 energy both sides, but OUR Alakazam is a plain Stage2 (not Tera) so it's a pure
    # one-sided tax on the Mega/Tera meta. Play whenever we don't control the stadium.
    if cid == 1266 and not c.get('our_stadium'): return 8
    if cid == 1080 and c.get('pre_ko') and CONFIG.get('STAMP_ON_KO', 1): return 2
    if cid == 1137 and c.get('opp_has_tool'): return 6
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
        return 20 * len(me(obs).hand or [])   # ignores weakness/resistance (engine-verified)
    if name == "Do the Wave":
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
        # 1. play a retreat-reducer tool onto the stuck active (none in deck)
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
                if len(hand) >= cfg('HAND_CAP', 14):   # v19: overkill hand -> stop draining deck
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

    # 2.5 ANTI-LOCK ESCAPE (v13, ported from grimm v8/v14): unstick a 0-energy body
    # trapped active while a charged Alakazam waits benched — live mirror losses showed
    # strike-ready Alakazam idling behind an unretreatable active; elite mirror winners
    # strike FIRST 86% of the time, so every stuck turn is tempo donated.
    esc = _escape_lock(obs, select, plays, attach, act_enabled=bool(cfg('ESCAPE_LOCK', 1)))
    if esc is not None:
        return esc

    # 2.6 v16 SETUP-SPEED (autopsy fix #4): resolve Rare Candy -> Alakazam BEFORE the energy
    # attach, so the freshly-made Alakazam is the body we energize THIS turn. Previously Rare
    # Candy fired at the trainer step (4), AFTER attach (3) — so on the turn we made Alakazam
    # the energy had already gone to a different body and the new attacker came online a turn
    # late (10/31 mirror losses). Only rush it when we still have this turn's attach to place
    # and no Alakazam is online yet (energy carries UP through the evolution).
    if not st.energyAttached and cfg('CANDY_BEFORE_ATTACH', 1):
        inplay = my_in_play(obs)
        has_online_ala = any(p.id == ALAKAZAM and energy_count(p) >= cfg('ENERGY_CAP', 1) for p in inplay)
        stage2_in_hand = any(c.id in cfg('STAGE2S', set()) for c in hand)
        if not has_online_ala and stage2_in_hand:
            for i, o in plays:
                cid = hand[o.index].id if (o.index is not None and o.index < len(hand)) else None
                if cid == 1079:   # Rare Candy — evolve a Basic straight to Alakazam now
                    return [i]

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
            return (src_rank, need, tgt_rank)
        # v16 ENERGY DISCIPLINE: only energize the Alakazam LINE (Alakazam/Kadabra/Abra —
        # energy carries UP through evolution, so a charged Abra becomes a charged Alakazam).
        # NEVER dead-end our 6 scarce psychic on a Fez/Dunsparce/Dudunsparce (they can't pay
        # Powerful Hand's {P}). Mirror autopsy's #1 leak = stranded energy on non-attackers
        # (act=Dunsparce+1e / Abra+1e chip-swings while the Alakazam rebuild starved). If no
        # line member can take energy this turn, HOLD it (strictly >= wasting it on a dead-end).
        def _tgt_cid(o):
            if o.inPlayArea == AreaType.ACTIVE:
                pkm = my.active[o.inPlayIndex] if my.active else None
            else:
                pkm = my.bench[o.inPlayIndex] if (o.inPlayIndex is not None and o.inPlayIndex < len(my.bench)) else None
            return getattr(pkm, "id", None)
        line_attach = [t for t in attach if _tgt_cid(t[1]) in att_pri]
        if line_attach:
            best = min(line_attach, key=lambda t: score(t[1]))
            return [best[0]]
        # else: no Alakazam-line target — hold the energy this turn (fall through)

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
            energy_in_hand = any(c.id in cfg('ENERGY_IDS', [1]) for c in hand)
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
    our_stadium = stadium is not None and stadium.id == FESTIVAL
    # Powerful Hand: 20 damage per card in hand (the hand IS the ammo).
    wave_dmg = 20 * len(hand)
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
    best_cid = None
    for i, o in plays:
        cid = hand[o.index].id if o.index is not None and o.index < len(hand) else None
        r = prio_fn(cid, ctx) if cid is not None else 99
        if r < best_rank:
            best_rank, best_play, best_cid = r, i, cid
    if best_play is not None and best_rank < 99:
        if cfg('HAND_IS_AMMO') and attacks:
            act = my.active[0] if my.active else None
            ready = act is not None and act.id in cfg('READY_ATTACKERS', set()) and energy_count(act) >= 1
            # v9 FIX: hand-growers (Hilda/Dawn) are ALWAYS played before attacking
            # — they grow Powerful Hand (20 x hand). The hold-gate was making a
            # charged Alakazam peck sub-lethally instead. (A/B verified +~10pp.)
            grower = best_cid in cfg('HAND_GROWERS', set())
            if ready and not grower and (best_rank > cfg('SETUP_RANK_MAX', 5)
                                         or len(hand) >= cfg('HOLD_HAND_AT', 11)):
                pass  # HOLD the hand & attack with a big Powerful Hand (Yushin holds to ~12);
                      # playing items shrinks the hand and the damage
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
    """Need-aware search priority for the Alakazam engine."""
    my = me(obs)
    hand_ids = [c.id for c in (my.hand or [])]
    in_play = my_in_play(obs)
    play_ids = [p.id for p in in_play]
    n_bench = len([b for b in (my.bench or []) if b])
    pri = []
    if n_bench < cfg('MIN_BENCH', 3) and not any(h in cfg('BASICS', []) for h in hand_ids):
        pri += [ABRA, DUNSPARCE, FEZ]
    # complete the Alakazam line: Abra + (Candy | Kadabra) -> Alakazam
    if ALAKAZAM not in play_ids and ABRA in play_ids:
        if ALAKAZAM not in hand_ids:
            pri.append(ALAKAZAM)
        if 1079 not in hand_ids and KADABRA not in hand_ids and KADABRA not in play_ids:
            pri += [1079, KADABRA]
    if ABRA not in play_ids and ABRA not in hand_ids:
        pri.append(ABRA)
    # energy for the attacker (trigger energies first)
    total_e = sum(len(p.energies or []) for p in in_play)
    if total_e + sum(1 for h in hand_ids if h in (5, 13, 19)) < cfg('ENERGY_STOCK', 2):
        pri += [19, 13, 5]
    # Dudunsparce draw engine
    if DUDUNSPARCE not in play_ids and DUDUNSPARCE not in hand_ids and DUNSPARCE in play_ids:
        pri.append(DUDUNSPARCE)
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
        # v11 guard on the consensus discard order: the elite toss Pokemon freely because
        # they can re-fetch — but never strand ourselves. If Alakazam is NOT yet in play,
        # protect ONE copy each of the line (Alakazam + Kadabra-or-RareCandy) by treating
        # them as keep-last for this decision.
        prio = list(cfg('DISCARD_PRIORITY', []))
        my_play_ids = [p.id for p in my_in_play(obs)]
        hand_ids = [c.id for c in (me(obs).hand or [])]
        # Protect the attacker line until it's REDUNDANT: the pros' 48% Alakazam keep-rate
        # is contextual (they toss spares only when double-set-up). Vs OHKO tanks the
        # backup is the game — keep one hand Alakazam until 2 are in play, and the
        # evolution path (Kadabra or Candy) until the first is online.
        if my_play_ids.count(ALAKAZAM) < 2 and hand_ids.count(ALAKAZAM) <= 1:
            if ALAKAZAM in prio:
                prio.remove(ALAKAZAM); prio.append(ALAKAZAM)
        if ALAKAZAM not in my_play_ids:
            for cid in (KADABRA if KADABRA in hand_ids else 1079,):
                if cid in prio and hand_ids.count(cid) <= 1:
                    prio.remove(cid); prio.append(cid)
        return pick_by_priority(obs, select, prio,
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
