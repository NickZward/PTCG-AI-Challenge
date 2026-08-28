#!/usr/bin/env python3
"""Decision-agreement of the dudun_v1 RULES agent vs the #3 pilot's real choices.

Replays the 72 'Number 3' games; at every decision the pilot faced (status==ACTIVE,
action in NEXT step's same-seat entry — the off-by-one law), asks dudun_v1 what it
would do and scores strict set-match. Breakdown by select type/context and, for MAIN
decisions, a confusion matrix over option TYPES (they attacked / we ended turn, etc.).
Oracle is auto-disabled (replays carry no search_begin_input) — live play adds it back.

Usage: agree_dudun.py [agent_dir]   (default my-agent/dudun_v1)
"""
import glob, importlib.util, json, os, sys
from collections import Counter

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
AGENT_DIR = sys.argv[1] if len(sys.argv) > 1 else "my-agent/dudun_v1"
sys.path.insert(0, os.path.join(ROOT, AGENT_DIR))
spec = importlib.util.spec_from_file_location("dudun_agent", os.path.join(ROOT, AGENT_DIR, "main.py"))
mod = importlib.util.module_from_spec(spec); sys.modules["dudun_agent"] = mod
spec.loader.exec_module(mod)
os.chdir(os.path.join(ROOT, AGENT_DIR))          # so read_deck_csv finds deck.csv

TEAM = 'やる気元気ミワハルキ'
OTYPE = {0:'number',1:'yes',2:'no',3:'card',4:'tool',5:'ecard',6:'energy',7:'play',
         8:'attach',9:'evolve',10:'ability',12:'retreat',13:'ATTACK',14:'end'}

tot = Counter(); agree = Counter(); confusion = Counter(); miss_ctx = Counter()
for path in sorted(glob.glob('/Users/nickzwart/Desktop/Number 3/*.json')):
    d = json.load(open(path))
    tn = d['info']['TeamNames']
    if TEAM not in tn: continue
    seat = tn.index(TEAM)
    steps = d['steps']
    for i, step in enumerate(steps):
        ent = step[seat] if seat < len(step) else None
        if not ent or ent.get('status') != 'ACTIVE': continue
        o = ent.get('observation') or {}
        sel, cur = o.get('select'), o.get('current')
        nxt = steps[i+1][seat] if (i+1 < len(steps) and seat < len(steps[i+1])) else None
        act = (nxt or {}).get('action')
        if not sel or act is None or not cur: continue
        opts = sel.get('option') or []
        if len(opts) <= 1: continue
        chosen = [int(x) for x in act if isinstance(x, int) and 0 <= x < len(opts)]
        if not chosen: continue
        try:
            ours = mod.agent({'current': cur, 'select': sel, 'logs': o.get('logs', []),
                              'step': 0, 'remainingOverageTime': 600,
                              'search_begin_input': o.get('search_begin_input')})
            ours = [int(x) for x in ours]
        except Exception:
            ours = []
        stype = sel.get('type', -1)
        key = f"t{stype}/ctx{sel.get('context')}"
        tot[key] += 1
        ok = set(ours) == set(chosen)
        if ok: agree[key] += 1
        if stype == 0:      # MAIN: option-type confusion
            def otyp(picks):
                ts = {OTYPE.get((opts[p] or {}).get('type'), '?') for p in picks if p < len(opts)}
                return '+'.join(sorted(ts)) or 'none'
            confusion[(otyp(chosen), otyp(ours))] += 1
            if not ok:
                miss_ctx[(otyp(chosen), otyp(ours))] += 1

T = sum(tot.values()); A = sum(agree.values())
print(f"OVERALL agreement: {A}/{T} = {A/T:.1%}\n")
print("by select type/context (n>=20):")
for k in sorted(tot, key=lambda k: -tot[k]):
    if tot[k] >= 20:
        print(f"  {k:12s} {agree[k]:4d}/{tot[k]:4d} = {agree[k]/tot[k]:.0%}")
print("\nMAIN option-type confusion (their_choice -> our_choice), mismatches only, top 15:")
for (theirs, ours), n in miss_ctx.most_common(15):
    print(f"  {theirs:16s} -> {ours:16s} {n}")
print("\nMAIN same-type picks (right action type, maybe wrong target):")
same = sum(n for (a,b),n in confusion.items() if a==b)
print(f"  {same}/{sum(confusion.values())} = {same/max(1,sum(confusion.values())):.0%}")
