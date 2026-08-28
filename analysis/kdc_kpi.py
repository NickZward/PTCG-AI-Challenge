#!/usr/bin/env python3
"""KPI extractor for Grimmsnarl pilots -- ONE definition used for BOTH real replays and
live-played games, so the comparison is like-for-like.

Mechanisms re-measured (from the earlier Grimmsnarl study):
  1. ATTACKER DOWNTIME  own turns with t>=3 and ZERO Marnie's Grimmsnarl ex (648) on our board
  2. SPIKEMUTH UPTIME   fraction of own turns with Spikemuth Gym (1259) in the stadium slot
plus first-Grimm-ex turn, prizes by T8, attacks per own turn, comeback rate.

TURN SEMANTICS (verified): `turn` increments once per PLAYER-turn. Turn t is owned by
`firstPlayer` when t is odd, by the other seat when t is even.
SNAPSHOT RULE: every per-turn fact is read at the FIRST decision of that own turn (start of
turn). Live play only ever exposes the acting seat's view, so replays are read the same way --
only entries with status ACTIVE -- or the two sides would not be measured alike.
ATTACKS: log type 15, attributed by log playerIndex, harvested only from ACTIVE-status views
(the log buffer accumulates while a seat is idle and is REPEATED in every idle entry; counting
idle entries double-counts by ~5x).
"""
GRIMM_EX = 648
SPIKEMUTH = 1259


class SideKPI:
    """Accumulates one seat's facts for one game from start-of-own-turn snapshots."""

    def __init__(self, seat, first_player):
        self.seat = seat
        self.fp = first_player
        self.snaps = {}          # turn -> dict(grimm=bool, gym=bool, prizes=int, oprizes=int)
        self.attacks = 0
        self.first_prize_taker = None
        self.max_turn = 0
        self.by8 = 0          # prizes WE had taken at any sighting with turn<=8
        self.oby8 = 0
        self._prev = None     # last (taken0, taken1) seen, for first-prize attribution
        self._pend = [{}, {}]  # per-viewer unmatched attack events (see observe())

    def finish(self):
        """Count attack events only ever witnessed by one of the two viewers."""
        self.attacks += sum(sum(p.values()) for p in self._pend)
        self._pend = [{}, {}]

    def owns(self, turn):
        if turn is None or turn < 1:
            return False
        return (self.fp if turn % 2 == 1 else 1 - self.fp) == self.seat

    def observe(self, cur, logs):
        """cur = observation['current'] from an ACTIVE view; logs = that view's log delta."""
        turn = cur.get("turn") or 0
        P = cur.get("players") or [None, None]
        me, opp = P[self.seat] or {}, P[1 - self.seat] or {}
        self.max_turn = max(self.max_turn, turn)
        # --- prize tracking. NOTE: `prize` is [] BEFORE the prizes are dealt, which reads as
        # "6 taken" if you naively do 6-len(); that mislabelled every game. Require 6 dealt. ---
        p0 = (P[0] or {}).get("prize") or []
        p1 = (P[1] or {}).get("prize") or []
        if len(p0) > 0 and len(p1) > 0:
            t0, t1 = 6 - len(p0), 6 - len(p1)
            mine, theirs = (t0, t1) if self.seat == 0 else (t1, t0)
            if turn <= 8:
                self.by8 = max(self.by8, mine)
                self.oby8 = max(self.oby8, theirs)
            if self.first_prize_taker is None and (t0 or t1):
                if t0 and not t1:
                    self.first_prize_taker = 0
                elif t1 and not t0:
                    self.first_prize_taker = 1
                else:                        # both moved inside one gap: unattributable
                    self.first_prize_taker = -1
            self._prev = (t0, t1)
        # --- attacks. VERIFIED: one attack is written into BOTH players' log buffers, so a naive
        # count inflates by ~2x (it read 1.14 attacks per own turn, above the physical max of 1).
        # Match each event across the two viewers and count it once; anything still unmatched at
        # the end (e.g. a game-winning attack the loser never gets to see) counts once too. ---
        v = cur.get("yourIndex")
        if v in (0, 1):
            for L in logs or []:
                if not (isinstance(L, dict) and L.get("type") == 15
                        and L.get("playerIndex") == self.seat):
                    continue
                key = (L.get("attackId"), L.get("serial"))
                if self._pend[1 - v].get(key):
                    self._pend[1 - v][key] -= 1
                    self.attacks += 1
                else:
                    self._pend[v][key] = self._pend[v].get(key, 0) + 1
        # --- start-of-own-turn snapshot ---
        if not self.owns(turn) or turn in self.snaps:
            return
        board = [x for x in (me.get("active") or []) + (me.get("bench") or []) if x]
        stad = cur.get("stadium") or []
        self.snaps[turn] = dict(
            grimm=any(x.get("id") == GRIMM_EX for x in board),
            gym=any((s or {}).get("id") == SPIKEMUTH for s in stad),
            prizes=6 - len(me.get("prize") or []),
            oprizes=6 - len(opp.get("prize") or []),
        )

    # ---------------- derived metrics ----------------
    def metrics(self, won, horizon=None):
        ts = sorted(t for t in self.snaps if horizon is None or t <= horizon)
        own = len(ts)
        elig = [t for t in ts if t >= 3]
        down = [t for t in elig if not self.snaps[t]["grimm"]]
        gym_up = [t for t in ts if self.snaps[t]["gym"]]
        first_g = next((t for t in sorted(self.snaps) if self.snaps[t]["grimm"]), None)
        by8 = self.by8
        # conditional: P(next own turn is attacker-down | gym state this own turn)
        cond = {True: [0, 0], False: [0, 0]}   # gym_up -> [down_next, n]
        order = sorted(self.snaps)
        for a, b in zip(order, order[1:]):
            if b < 3:
                continue
            g = self.snaps[a]["gym"]
            cond[g][1] += 1
            cond[g][0] += (not self.snaps[b]["grimm"])
        return dict(own_turns=own, elig=len(elig), down=len(down), gym_up=len(gym_up),
                    first_grimm=first_g, prizes_by8=by8, attacks=self.attacks,
                    won=won, cond=cond, max_turn=self.max_turn)


def scan_replay(path, seat):
    """Return SideKPI for `seat` plus (winner_seat, total_turns)."""
    import json
    d = json.load(open(path))
    steps = d["steps"]
    fp = None
    for step in steps:
        for e in step:
            c = (e.get("observation") or {}).get("current") or {}
            if c.get("firstPlayer") in (0, 1):   # it is -1 on the very first step
                fp = c["firstPlayer"]
                break
        if fp is not None:
            break
    if fp is None:
        return None, None, None
    k = SideKPI(seat, fp)
    last_res = -1
    for step in steps:
        for e in step:
            if e.get("status") != "ACTIVE":
                continue
            ob = e.get("observation") or {}
            cur = ob.get("current") or {}
            if not cur:
                continue
            if cur.get("result", -1) not in (None, -1):
                last_res = cur["result"]
            k.observe(cur, ob.get("logs"))
    k.finish()
    rw = d.get("rewards")
    if rw in ([1, -1], [-1, 1]):
        winner = 0 if rw[0] == 1 else 1
    else:
        winner = last_res if last_res in (0, 1) else None
    return k, winner, k.max_turn
