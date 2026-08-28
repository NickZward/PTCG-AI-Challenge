#!/usr/bin/env python3
"""Loss-gauntlet experiment harness: eval a candidate agent (optionally with a
params.json knob override) against the EXACT opponent decks from its real losses.
Per-deck + aggregate WR, 2 seeds (so gains must replicate, not be noise). Prints
worst cells so I can target them. NOTE: proxy opponents can't reproduce the real
losses, so this measures 'beat the proxy version of these decks' — gains here are
directional, must sanity-check for overfitting."""
import sys, os, json, csv, importlib.util, shutil, random
from collections import defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame
SC = "/private/tmp/claude-501/-Users-nickzwart-Desktop-PTCG-AI-Challenge/357909bf-c972-4782-b638-d3f1aad983aa/scratchpad"
R = f"{ROOT}/my-agent"
name2id = defaultdict(list)
for r in csv.DictReader(open(f"{ROOT}/pokemon-tcg-ai-battle/EN_Card_Data.csv")):
    name2id[r["Card Name"]].append(int(r["Card ID"]))
def ids(sub): return {c for nm, cs in name2id.items() if sub.lower() in nm.lower() for c in cs}
MAP = [('M-Lucario', ids('Mega Lucario'), f'{R}/gauntlet/mlucario'),
       ('Crustle', ids('Crustle') | ids('Dwebble'), f'{R}/gauntlet/crustle'),
       ('M-Starmie', ids('Mega Starmie') | ids('Starmie'), f'{R}/gauntlet/starmie'),
       ('Archaludon', ids('Archaludon'), f'{R}/gauntlet/archaludon'),
       ('Alakazam', ids('Alakazam'), f'{R}/pool/alakazam_v7'),
       ('Grimmsnarl', ids("Grimmsnarl"), f'{R}/pool/grimmsnarl_v3'),
       ('Dragapult', ids('Dragapult') | ids('Drakloak'), f'{R}/dragapult_v5'),
       ('Okidogi', ids('Okidogi'), f'{R}/gauntlet/okidogi')]
def detect(deck):
    s = set(deck)
    for name, sig, proxy in MAP:
        if s & sig: return name, proxy
    return 'other', None
def opp_deck(ep):
    d = json.load(open(f"{ROOT}/Logs/auto/episode-{ep}-replay.json"))
    mi = d['info']['TeamNames'].index('Kilupy')
    return d['steps'][0][0]['visualize'][0]['action'][1 - mi]
_c = [0]
def load(sub, params=None):
    if params is not None:
        with open(os.path.join(sub, "params.json"), "w") as f: json.dump(params, f)
    _c[0] += 1; mn = f"m{_c[0]}"
    spec = importlib.util.spec_from_file_location(mn, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[mn] = m; spec.loader.exec_module(m)
    deck = [int(x) for x in open(os.path.join(sub, "deck.csv")).read().split()]
    return m.agent, deck
def load_ag(sub):
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
_oc = {}
def opp_for(ep):
    if ep in _oc: return _oc[ep]
    dk = opp_deck(ep); arch, proxy = detect(dk)
    d = f"{SC}/g_opp/{ep}"; os.makedirs(d, exist_ok=True)
    shutil.copy(f"{proxy}/main.py" if proxy else f"{SC}/bc_proxy_main.py", f"{d}/main.py")
    open(f"{d}/deck.csv", "w").write("\n".join(map(str, sorted(dk))))
    _oc[ep] = (arch, load_ag(d), dk); return _oc[ep]
DIP = ['87239298','87241400','87242089','87242366','87242500','87243047','87244140','87245802','87246339']
GRM = ['87238703','87239266','87239811','87240345','87242464','87242973','87243540','87244106','87246828','87247374','87247912','87249521','87250605']
def evalcand(agent_dir, eps, N, params=None, seeds=(1, 2)):
    ag, deck = load(agent_dir, params)
    per = {}
    for ep in eps:
        arch, oag, odk = opp_for(ep)
        w = t = 0
        for seed in seeds:
            random.seed(seed)
            for g in range(N):
                if (g + seed) % 2 == 0: r = play(ag, deck, oag, odk); win = (r == 0)
                else: r = play(oag, odk, ag, deck); win = (r == 1)
                if r in (0, 1): t += 1; w += int(win)
        per[ep] = (arch, w, t)
    agg = sum(w for _, w, _ in per.values()) / max(1, sum(t for _, _, t in per.values()))
    return agg, per
if __name__ == "__main__":
    deckname = sys.argv[1]                       # dipplin | grimmsnarl
    cand = sys.argv[2]                            # agent dir under my-agent/
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    params = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    fast = os.environ.get("FAST") == "1"    # skip slow BC-opponent (other) decks
    eps = DIP if deckname == 'dipplin' else GRM
    if fast:
        eps = [e for e in eps if detect(opp_deck(e))[1] is not None]
    agg, per = evalcand(f"{R}/{cand}", eps, N, params)
    label = f"{cand}" + (f" +{params}" if params else "")
    print(f"\n{label}  vs {deckname} loss decks (N={N}x2seeds):  AGG {agg:.1%}")
    for ep in eps:
        arch, w, t = per[ep]
        print(f"  {ep} {arch:<12} {w}/{t} = {w/t if t else 0:.0%}")
    # clean up test params
    if params and os.path.exists(f"{R}/{cand}/params.json"): os.remove(f"{R}/{cand}/params.json")
