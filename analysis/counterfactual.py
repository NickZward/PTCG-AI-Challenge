#!/usr/bin/env python3
"""COUNTERFACTUAL REPLAY: match the FIXED agents against the EXACT opponent decks from
each real loss, vs the OLD (live) agents. Opponent deck is extracted from the replay;
driven by the archetype-matched proxy pilot (BC proxy fallback). Same opponent for old
and fixed, so the DELTA (fixed - old) is trustworthy even though absolute WRs are
proxy-inflated. Answers: on the decks we lost to, do the fixes win more?"""
import sys, os, json, csv, importlib.util, shutil, random
from collections import defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
SC = "/private/tmp/claude-501/-Users-nickzwart-Desktop-PTCG-AI-Challenge/357909bf-c972-4782-b638-d3f1aad983aa/scratchpad"
R = f"{ROOT}/my-agent"

# ---- archetype detection + proxy mapping ----
name2id = defaultdict(list)
for r in csv.DictReader(open(f"{ROOT}/pokemon-tcg-ai-battle/EN_Card_Data.csv")):
    name2id[r["Card Name"]].append(int(r["Card ID"]))
def ids(sub): return {c for nm, cs in name2id.items() if sub.lower() in nm.lower() for c in cs}
# (archetype, signature ids, proxy dir)   proxy=None -> use BC proxy
MAP = [
    ('M-Lucario', ids('Mega Lucario'), f'{R}/gauntlet/mlucario'),
    ('Crustle', ids('Crustle') | ids('Dwebble'), f'{R}/gauntlet/crustle'),
    ('M-Starmie', ids('Mega Starmie') | ids('Starmie'), f'{R}/gauntlet/starmie'),
    ('Archaludon', ids('Archaludon'), f'{R}/gauntlet/archaludon'),
    ('Alakazam', ids('Alakazam'), f'{R}/pool/alakazam_v7'),
    ('Grimmsnarl', ids("Grimmsnarl"), f'{R}/pool/grimmsnarl_v3'),
    ('Dragapult', ids('Dragapult') | ids('Drakloak'), f'{R}/dragapult_v5'),
    ('Okidogi', ids('Okidogi'), f'{R}/gauntlet/okidogi'),
]
def detect(deck):
    s = set(deck)
    for name, sig, proxy in MAP:
        if s & sig:
            return name, proxy
    return 'other(BC)', None

def opp_deck(ep):
    d = json.load(open(f"{ROOT}/Logs/auto/episode-{ep}-replay.json"))
    names = d['info']['TeamNames']; mi = names.index('Kilupy')
    decks = d['steps'][0][0]['visualize'][0]['action']
    return decks[1 - mi]

_c = [0]
def load(sub):
    _c[0] += 1; mn = f"m{_c[0]}"
    spec = importlib.util.spec_from_file_location(mn, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[mn] = m; spec.loader.exec_module(m)
    deck = [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]
    return m.agent, deck
def load_agent_only(sub):
    _c[0] += 1; mn = f"m{_c[0]}"
    spec = importlib.util.spec_from_file_location(mn, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[mn] = m; spec.loader.exec_module(m)
    return m.agent
def play(a0, d0, a1, d1, mx=4000):
    obs, sd = cggame.battle_start(list(d0), list(d1))
    if obs is None: return -2
    s = 0
    try:
        while s < mx:
            cur = obs.get("current") or {}; r = cur.get("result", -1)
            if r is not None and r != -1: return r
            if obs.get("select") is None: return -2
            ag = a0 if cur.get("yourIndex", 0) == 0 else a1
            w = {"current": obs.get("current"), "select": obs.get("select"), "logs": obs.get("logs", []),
                 "step": s, "remainingOverageTime": 600, "search_begin_input": obs.get("search_begin_input")}
            obs = cggame.battle_select([int(x) for x in ag(w)]); s += 1
        return -3
    finally: cggame.battle_finish()

def opp_agent(proxy, deck, ep):
    """Build an opponent dir (proxy pilot or BC) with the exact loss deck."""
    d = f"{SC}/cf_opp/{ep}"; os.makedirs(d, exist_ok=True)
    src = f"{proxy}/main.py" if proxy else f"{SC}/bc_proxy_main.py"
    shutil.copy(src, f"{d}/main.py")
    open(f"{d}/deck.csv", "w").write("\n".join(map(str, sorted(deck))))
    return load_agent_only(d), deck

# ---- losses ----
DIP = ['87239298','87241400','87242089','87242366','87242500','87243047','87244140','87245802','87246339']
GRM = ['87238703','87239266','87239811','87240345','87242464','87242973','87243540','87244106','87246828','87247374','87247912','87249521','87250605']
VERS = {'dipplin': (f'{R}/dipplin_v6', f'{R}/dipplin_v8'), 'grimmsnarl': (f'{R}/grimmsnarl_v7', f'{R}/grimmsnarl_v9')}

def ab(agent_dir, opp_ag, opp_deck_, N, seed):
    ag, deck = load(agent_dir); w = t = 0
    random.seed(seed)
    for g in range(N):
        if g % 2 == 0: r = play(ag, deck, opp_ag, opp_deck_); win = (r == 0)
        else: r = play(opp_ag, opp_deck_, ag, deck); win = (r == 1)
        if r in (0, 1): t += 1; w += int(win)
    return w, t

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    WHICH = sys.argv[2] if len(sys.argv) > 2 else 'both'
    allsets = [('dipplin', DIP), ('grimmsnarl', GRM)]
    for deckname, eps in [x for x in allsets if WHICH in ('both', x[0])]:
        old_dir, fix_dir = VERS[deckname]
        print(f"\n{'='*76}\n{deckname.upper()}  old={old_dir.split('/')[-1]}  fixed={fix_dir.split('/')[-1]}  (N={N}/side, exact loss decks)\n{'='*76}")
        print(f"  {'ep':<10}{'opp archetype':<16}{'OLD':>7}{'FIXED':>8}{'Δ':>7}")
        tot_o = tot_f = tot_t = 0
        for ep in eps:
            dk = opp_deck(ep)
            arch, proxy = detect(dk)
            oag, odk = opp_agent(proxy, dk, ep)
            ow, ot = ab(old_dir, oag, odk, N, 1)
            fw, ft = ab(fix_dir, oag, odk, N, 1)
            owr = ow/ot if ot else 0; fwr = fw/ft if ft else 0
            tot_o += ow; tot_f += fw; tot_t += min(ot, ft)
            print(f"  {ep:<10}{arch:<16}{owr:>6.0%}{fwr:>8.0%}{fwr-owr:>+7.0%}", flush=True)
        print(f"  {'-'*44}")
        print(f"  AGGREGATE on {len(eps)} loss decks:  OLD {tot_o/(len(eps)*N):.0%}  ->  FIXED {tot_f/(len(eps)*N):.0%}  (Δ{tot_f/(len(eps)*N)-tot_o/(len(eps)*N):+.0%})", flush=True)
