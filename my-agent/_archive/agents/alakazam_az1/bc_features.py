"""Shared feature builder for behavioral cloning (Path B).

Works on the raw observation DICT shape, which is identical in replay files
(steps[t][p].observation) and in the live agent (obs_dict passed to agent()).
No sklearn imports here — the live pilot imports this file too.
"""

N_DENSE = 34
CARD_VOCAB = 96          # one-hot slots for the most frequent card ids
N_FEATURES = N_DENSE + CARD_VOCAB + 1


def resolve_card_id(obs, opt):
    """Card id an option refers to (dict-based mirror of option_card_id)."""
    if opt.get("cardId") is not None:
        return opt["cardId"]
    area, index = opt.get("area"), opt.get("index")
    if area is None or index is None:
        return None
    cur = obs.get("current") or {}
    you = cur.get("yourIndex", 0)
    pi = opt.get("playerIndex")
    if pi is None:
        pi = you
    players = cur.get("players") or [{}, {}]
    p = players[pi] if pi < len(players) else {}
    try:
        if area == 1:                       # HAND
            return (p.get("hand") or [])[index].get("id")
        if area == 2:                       # ACTIVE
            c = (p.get("active") or [])[index]
            return c.get("id") if c else None
        if area == 3:                       # BENCH
            c = (p.get("bench") or [])[index]
            return c.get("id") if c else None
        if area == 5:                       # DISCARD
            return (p.get("discard") or [])[index].get("id")
        if area == 6:                       # STADIUM
            return (cur.get("stadium") or [])[index].get("id")
        if area == 7:                       # LOOKING
            return (cur.get("looking") or [])[index].get("id")
        if area == 0:                       # DECK (select-scoped listing)
            sel = obs.get("select") or {}
            return (sel.get("deck") or [])[index].get("id")
        if area == 4:                       # PRIZE
            return (p.get("prize") or [])[index].get("id")
    except (IndexError, AttributeError, TypeError):
        return None
    return None


def option_features(obs, opt, opt_idx, n_opts, vocab, card_feats, attack_dmg):
    """-> list[float] of length N_FEATURES."""
    cur = obs.get("current") or {}
    sel = obs.get("select") or {}
    you = cur.get("yourIndex", 0)
    players = cur.get("players") or [{}, {}]
    me = players[you] if you < len(players) else {}
    op = players[1 - you] if len(players) > 1 else {}

    def act(p):
        a = p.get("active") or []
        return a[0] if a and a[0] else None

    ma, oa = act(me), act(op)
    bench_n = lambda p: len([b for b in (p.get("bench") or []) if b])
    en = lambda c: len(c.get("energies") or []) if c else 0

    cid = resolve_card_id(obs, opt)
    cf = card_feats.get(str(cid)) or card_feats.get(cid) or [0, 0, 0, 0]
    aid = opt.get("attackId")

    board_energy = 0
    for c in ([a for a in (me.get("active") or []) if a] +
              [b for b in (me.get("bench") or []) if b]):
        board_energy += en(c)

    f = [0.0] * N_FEATURES
    f[0] = len(me.get("prize") or [])
    f[1] = len(op.get("prize") or [])
    f[2] = bench_n(me)
    f[3] = bench_n(op)
    f[4] = len(me.get("hand") or [])
    f[5] = me.get("deckCount") or 0
    f[6] = op.get("deckCount") or 0
    f[7] = (ma or {}).get("hp") or 0
    f[8] = (ma or {}).get("maxHp") or 0
    f[9] = en(ma)
    f[10] = (oa or {}).get("hp") or 0
    f[11] = en(oa)
    f[12] = 1.0 if cur.get("energyAttached") else 0.0
    f[13] = 1.0 if cur.get("retreated") else 0.0
    f[14] = n_opts
    f[15] = opt_idx
    f[16] = sel.get("type") if sel.get("type") is not None else -1
    f[17] = sel.get("context") if sel.get("context") is not None else -1
    f[18] = opt.get("type") if opt.get("type") is not None else -1
    f[19] = opt.get("area") if opt.get("area") is not None else -1
    f[20] = cf[0]                            # card hp
    f[21] = cf[1]                            # is ex / rule box
    f[22] = cf[2]                            # category code
    f[23] = cf[3]                            # stage code
    f[24] = attack_dmg.get(str(aid), attack_dmg.get(aid, 0)) if aid is not None else 0
    f[25] = board_energy
    f[26] = len(me.get("discard") or [])
    f[27] = op.get("handCount") or 0
    f[28] = 1.0 if (opt.get("playerIndex") is not None and opt.get("playerIndex") != you) else 0.0
    f[29] = (oa or {}).get("maxHp") or 0
    # hand composition (what COULD we do this turn?)
    n_basic = n_energy = n_trainer = 0
    for h in (me.get("hand") or []):
        hf = card_feats.get(str(h.get("id"))) or [0, 0, 0, 0]
        if hf[2] == 1 and hf[3] <= 1:
            n_basic += 1
        elif hf[2] == 3:
            n_energy += 1
        elif hf[2] == 2:
            n_trainer += 1
    f[30] = n_basic
    f[31] = n_energy
    f[32] = n_trainer
    f[33] = obs.get("step") or 0
    # card-id one-hot
    slot = vocab.get(str(cid), vocab.get(cid))
    if slot is None:
        f[N_DENSE + CARD_VOCAB] = 1.0        # "other"
    else:
        f[N_DENSE + slot] = 1.0
    return f


# ===================== Path C: state value features =====================
N_STATE_DENSE = 34
N_STATE = N_STATE_DENSE + 3 * (CARD_VOCAB + 1)   # + my-active/opp-active/stadium one-hots


def _g(x, k, default=None):
    """Field access that works for dicts AND dataclass objects."""
    if x is None:
        return default
    if isinstance(x, dict):
        v = x.get(k)
    else:
        v = getattr(x, k, None)
    return default if v is None else v


def state_features(current, me_index, vocab, card_feats, step=0):
    """Featurize a board state from player `me_index`'s perspective.
    `current` = Observation.current (dict or dataclass)."""
    players = _g(current, "players", [{}, {}])
    me = players[me_index]
    op = players[1 - me_index]

    def act(p):
        a = _g(p, "active", [])
        return a[0] if a and a[0] else None

    def bench(p):
        return [b for b in (_g(p, "bench", []) or []) if b]

    def en(c):
        return len(_g(c, "energies", []) or []) if c else 0

    def cardf(cid):
        return card_feats.get(str(cid)) or card_feats.get(cid) or [0, 0, 0, 0]

    ma, oa = act(me), act(op)
    ma_id, oa_id = _g(ma, "id"), _g(oa, "id")
    maf, oaf = cardf(ma_id), cardf(oa_id)

    def board_stats(p):
        mons = ([a for a in (_g(p, "active", []) or []) if a] + bench(p))
        hp = sum((_g(c, "hp", 0) or 0) for c in mons)
        e = sum(en(c) for c in mons)
        evolved = sum(1 for c in mons if cardf(_g(c, "id"))[3] >= 2)
        exes = sum(1 for c in mons if cardf(_g(c, "id"))[1])
        return hp, e, evolved, exes

    mhp, men, mev, mex = board_stats(me)
    ohp, oen, oev, oex = board_stats(op)

    f = [0.0] * N_STATE
    f[0] = len(_g(me, "prize", []) or [])
    f[1] = len(_g(op, "prize", []) or [])
    f[2] = f[1] - f[0]                      # prize advantage (they have more left = we lead)
    f[3] = len(bench(me))
    f[4] = len(bench(op))
    f[5] = len(_g(me, "hand", []) or []) or (_g(me, "handCount", 0) or 0)
    f[6] = _g(op, "handCount", 0) or 0
    f[7] = _g(me, "deckCount", 0) or 0
    f[8] = _g(op, "deckCount", 0) or 0
    f[9] = (_g(ma, "hp", 0) or 0)
    f[10] = (_g(ma, "maxHp", 0) or 0)
    f[11] = en(ma)
    f[12] = maf[1]
    f[13] = maf[3]
    f[14] = (_g(oa, "hp", 0) or 0)
    f[15] = (_g(oa, "maxHp", 0) or 0)
    f[16] = en(oa)
    f[17] = oaf[1]
    f[18] = oaf[3]
    f[19] = mhp
    f[20] = ohp
    f[21] = men
    f[22] = oen
    f[23] = mev
    f[24] = oev
    f[25] = mex
    f[26] = oex
    f[27] = len(_g(me, "discard", []) or [])
    f[28] = len(_g(op, "discard", []) or [])
    f[29] = 1.0 if _g(current, "energyAttached") else 0.0
    f[30] = 1.0 if _g(current, "retreated") else 0.0
    f[31] = step
    f[32] = (f[9] / f[10]) if f[10] else 0.0      # my active hp fraction
    f[33] = (f[14] / f[15]) if f[15] else 0.0     # opp active hp fraction

    def hot(base, cid):
        slot = vocab.get(str(cid), vocab.get(cid))
        if slot is None:
            f[base + CARD_VOCAB] = 1.0
        else:
            f[base + slot] = 1.0

    hot(N_STATE_DENSE, ma_id)
    hot(N_STATE_DENSE + CARD_VOCAB + 1, oa_id)
    stad = _g(current, "stadium", []) or []
    hot(N_STATE_DENSE + 2 * (CARD_VOCAB + 1), _g(stad[0], "id") if stad and stad[0] else None)
    return f


# --- Grimmsnarl-aware VF features: encode the things that actually decide these games
#     (the counter engine + the attacker + the wall matchup) that generic features miss. ---
GRIMMSNARL, MUNKIDORI, FROSLASS, MORGREM, IMPIDIMP = 648, 112, 104, 647, 646
N_GRIMM = 11

def grimm_extra(current, me_index):
    players = _g(current, "players", [{}, {}])
    me = players[me_index]; op = players[1 - me_index]
    def mons(p):
        return [x for x in (_g(p, "active", []) or []) if x] + [b for b in (_g(p, "bench", []) or []) if b]
    def en(c): return len(_g(c, "energies", []) or []) if c else 0
    mm = mons(me); om = mons(op)
    munki = [c for c in mm if _g(c, "id") == MUNKIDORI]
    grimm = [c for c in mm if _g(c, "id") == GRIMMSNARL]
    munki_energized = 1.0 if any(en(c) >= 1 for c in munki) else 0.0
    grimm_charged = 1.0 if any(en(c) >= 2 for c in grimm) else 0.0
    froslass = 1.0 if any(_g(c, "id") == FROSLASS for c in mm) else 0.0
    ability_mons = sum(1 for c in mm if _g(c, "id") in (MUNKIDORI, FROSLASS))
    our_dmg = sum(max(0, (_g(c, "maxHp", 0) or 0) - (_g(c, "hp", 0) or 0)) for c in mm) / 10.0
    engine_ready = 1.0 if (munki_energized and our_dmg >= 1) else 0.0   # Adrena-Brain can fire NOW
    opp_wall = 1.0 if any(_g(c, "id") in (533, 345) for c in om) else 0.0
    opp_max_hp = max([(_g(c, "maxHp", 0) or 0) for c in om] + [0])
    opp_tank = 1.0 if opp_max_hp >= 260 else 0.0
    return [munki_energized, grimm_charged, froslass, float(len(munki)), float(len(grimm)),
            float(ability_mons), our_dmg, engine_ready, opp_wall, opp_tank, opp_max_hp / 100.0]

N_FULL = N_STATE + N_GRIMM

def full_features(current, me_index, vocab, card_feats, step=0):
    return state_features(current, me_index, vocab, card_feats, step) + grimm_extra(current, me_index)
