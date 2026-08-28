#!/usr/bin/env python3
"""Replay compiler — turns a Kaggle PTCG replay (4MB JSON) into a compact turn-by-turn
digest + metrics + rule-based failure classification. Encodes every measurement lesson
this project has learned so nothing rediscovers them expensively:
  - attacks (type15) appear ONLY in the DEFENDER's view -> both sides' attacks extracted
    from the opposing player's logs
  - recorded action ints are engine-canonical: NEVER decoded; everything is state-diff/logs
  - games may end UNRESOLVED at a cap (result=-1 with rewards assigned) -> ending_type
  - engine events: Adrena-Brain fires = ctx16 selects; energized/exposure per turn
  - supporter-paralysis detection (Petrel+Candy dead-gate, Lillie's 5-7 dead zone, lineless)

Usage:
  digest.py <replay.json> [--me NAME]          # full digest to stdout (~3KB)
  digest.py --batch <replay.json ...>          # one metrics/classification line per game
"""
import sys, json
from collections import Counter

CARD = {648:'GrimmEX',647:'Morgrem',646:'Impidimp',112:'Munkidori',104:'Froslass',860:'Snorunt',
        743:'Alakazam',742:'Kadabra',741:'Abra',66:'Dudunsparce',65:'Dunsparce',343:'FezEX',
        1079:'Candy',1219:'Petrel',1227:'Lillies',1182:'Boss',1197:'Xerosic',1161:'Fan',
        1259:'Spikemuth',1266:'NightMine',533:'Crustle',345:'Crustle',678:'MLucarioEX',
        1031:'MStarmieEX',190:'Archaludon',121:'Dragapult',756:'MKangaskhanEX',381:'CynGarchompEX',
        7:'DarkE',5:'PsyE',19:'E19',13:'E13',305:'c305',140:'c140',1086:'Poffin',1152:'c1152',
        1225:'c1225',1231:'Dawn',1080:'Stamp',1097:'NightStretcher',1121:'UltraBall',1122:'Pokegear'}
def nm(c): return CARD.get(c, f'c{c}')
ARCH = {648:'Grimmsnarl',743:'Alakazam',533:'Crustle',345:'Crustle',678:'M-Lucario',93:'Dipplin',
        756:'M-Kangaskhan',190:'Archaludon',1031:'M-Starmie',381:'Cynthia-Garchomp',121:'Dragapult'}

GRIMM, MORG, IMP, MUNKI = 648, 647, 646, 112
PETREL, CANDY, LILLIE = 1219, 1079, 1227

def mon_s(x):
    if not x: return '-'
    dmg = (x.get('maxHp',0) or 0) - (x.get('hp',0) or 0)
    e = len(x.get('energies') or [])
    s = nm(x.get('id'))
    if e: s += f'+{e}e'
    if dmg: s += f'({x.get("hp")}hp)'
    return s

def digest(path, me_name='Kilupy', full=True):
    d = json.load(open(path))
    names = d['info']['TeamNames']
    me = next((i for i,n in enumerate(names) if me_name.lower() in n.lower()), 0)
    rw = d.get('rewards')
    won = rw[me] == 1 if rw in ([1,-1],[-1,1]) else None
    decks = d['steps'][0][0]['visualize'][0]['action']
    def arch(dk):
        c = Counter(dk)
        return next((l for cid,l in ARCH.items() if c.get(cid)), 'other')
    steps = d['steps']

    turns = {}          # turn -> dict of facts
    kos_by_us = Counter(); kos_by_them = Counter()
    fires = 0; last_res = -1
    prev_opp = {}; prev_own = {}
    seen_logs = [0, 0]  # per viewer
    # supporter-paralysis + engine trackers
    lineless_rot = 0; lineless_turns = 0; expo_danger = 0; grimm_expo = 0
    en_t = 0; on_t = 0

    for t_i, step in enumerate(steps):
        for viewer in (me, 1-me):
            e = step[viewer] if viewer < len(step) else None
            if not e: continue
            o = e.get('observation') or {}
            cur = o.get('current') or {}
            if cur.get('result', -1) not in (None, -1): last_res = cur['result']
            turn = cur.get('turn', 0) or 0
            T = turns.setdefault(turn, {'events': [], 'snap': None})
            pl = (cur.get('players') or [None,None])
            mepl, oppl = pl[me] or {}, pl[1-me] or {}
            # snapshot from OUR view (once per turn, first sighting)
            if viewer == me and T['snap'] is None:
                act = (mepl.get('active') or [None])[0]
                oact = (oppl.get('active') or [None])[0]
                hand = [c.get('id') for c in (mepl.get('hand') or [])]
                play = [x.get('id') for x in (mepl.get('active') or [])+(mepl.get('bench') or []) if x]
                oh = oppl.get('handCount') or 0
                T['snap'] = dict(
                    act=mon_s(act), oact=mon_s(oact), nh=len(hand), oh=oh,
                    mp=6-len(mepl.get('prize') or []), op=6-len(oppl.get('prize') or []),
                    deck=mepl.get('deckCount'), bench=len([b for b in (mepl.get('bench') or []) if b]))
                # engine + paralysis trackers
                munki = [x for x in (mepl.get('active') or [])+(mepl.get('bench') or []) if x and x.get('id')==MUNKI]
                if munki:
                    on_t += 1
                    if any(len(m.get('energies') or [])>0 for m in munki): en_t += 1
                if act and act.get('id')==GRIMM:
                    grimm_expo += 1
                    if oh >= 12: expo_danger += 1
                if turn >= 3 and GRIMM not in play and MORG not in play:
                    lineless_turns += 1
                    if (PETREL in hand and CANDY in hand) or (LILLIE in hand and 5<=len(hand)<=7):
                        lineless_rot += 1
                        T['events'].append('ROT: rebuild tool idle in hand (lineless)')
            # KO detection via our view of both boards
            if viewer == me:
                om = {x.get('serial'): x.get('id') for x in (oppl.get('active') or [])+(oppl.get('bench') or []) if x}
                for s_,cid in prev_opp.items():
                    if s_ not in om:
                        kos_by_us[cid] += 1; T['events'].append(f'KO their {nm(cid)}')
                prev_opp = om
                mm = {x.get('serial'): x.get('id') for x in (mepl.get('active') or [])+(mepl.get('bench') or []) if x}
                for s_,cid in prev_own.items():
                    if s_ not in mm:
                        kos_by_them[cid] += 1; T['events'].append(f'LOST our {nm(cid)}')
                prev_own = mm
                sel = o.get('select')
                if sel and sel.get('type')==1 and sel.get('context')==16 and e.get('action'):
                    fires += 1; T['events'].append('AdrenaBrain FIRE')
            # attacks: read each side's attacks from the OTHER side's log view
            vi = 0 if viewer == me else 1
            logs = o.get('logs') or []
            for L in logs[seen_logs[vi]:]:
                if not isinstance(L, dict): continue
                ty = L.get('type')
                if ty == 15:
                    side = 'THEY' if viewer == me else 'WE'
                    T['events'].append(f'{side} attack w/ {nm(L.get("cardId"))}')
                elif ty == 4 and L.get('playerIndex') == me and viewer == me:
                    if L.get('cardId') in (PETREL, LILLIE, 1182, 1197, 1231, 1080):
                        T['events'].append(f'we play {nm(L.get("cardId"))}')
            seen_logs[vi] = len(logs)

    ending = 'board' if last_res in (0,1) else 'CAP/unresolved'
    fin = {}
    for turn in sorted(turns, reverse=True):
        if turns[turn].get('snap'):
            fin = turns[turn]['snap']; break
    # classification
    tags = []
    if on_t and en_t/max(1,on_t) < 0.45: tags.append('engine_starved(%d%%)' % (100*en_t/max(1,on_t)))
    if fires <= 1 and on_t >= 4: tags.append('engine_idle(%dfires)' % fires)
    if lineless_rot >= 3: tags.append('supporter_paralysis(%dturns)' % lineless_rot)
    if grimm_expo and expo_danger/max(1,grimm_expo) > 0.6: tags.append('exposed_ex(%d%%)' % (100*expo_danger/max(1,grimm_expo)))
    if fin.get('deck', 99) is not None and (fin.get('deck') or 99) <= 2: tags.append('deckout_risk')
    if won is False and (fin.get('op',0) or 0) >= 5: tags.append('prized_out')

    head = (f"{'WIN' if won else 'LOSS' if won is False else '?'} | us={arch(decks[me])} vs {arch(decks[1-me])}"
            f" ({names[1-me]}) | end={ending} | prizes {fin.get('mp','?')}-{fin.get('op','?')}"
            f" | fires={fires} energized={100*en_t//max(1,on_t)}% | KOs us:{dict(kos_by_us)} them:{dict(kos_by_them)}"
            f" | tags={tags or ['clean']}")
    if not full:
        return head
    lines = [head, '---']
    for turn in sorted(turns):
        T = turns[turn]; s = T.get('snap') or {}
        ev = '; '.join(T['events'][:7])
        lines.append(f"T{turn:>2} act={s.get('act','?'):<22} opp={s.get('oact','?'):<20} "
                     f"hand={s.get('nh','?')}/opp{s.get('oh','?')} prz={s.get('mp','?')}-{s.get('op','?')} "
                     f"deck={s.get('deck','?')} | {ev}")
    return '\n'.join(lines)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    me_name = 'Kilupy'
    if '--me' in sys.argv:
        me_name = sys.argv[sys.argv.index('--me')+1]
        args = [a for a in args if a != me_name]
    batch = '--batch' in sys.argv
    for p in args:
        try:
            print(digest(p, me_name, full=not batch))
        except Exception as ex:
            print(f'{p}: ERROR {ex}')
        if not batch: print()
