#!/usr/bin/env python3
"""Per-context pattern inspector: for a given select-context, characterize what the PRO
actually does across all their replays, so we can learn the rule. Optionally compares to
what OUR pilot picks.

Usage:
  inspect_ctx.py <replay_folder> <player_substr> <sel_type> <sel_context> [n_games] [agent_dir]

Reports, across all matching decisions:
  - how many OPTIONS the pro faced (distribution)
  - which option POSITION the pro chose (distribution) -> reveals "always pick first" rules
  - the chosen option PAYLOAD shape (area/type/playerIndex) -> reveals target semantics
  - if agent_dir given: our pilot's choice + agreement, and OUR position distribution
"""
import sys, os, json, glob, importlib.util
from collections import Counter, defaultdict
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))

def load(sub):
    n = "cand_" + os.path.basename(sub)
    spec = importlib.util.spec_from_file_location(n, os.path.join(sub, "main.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m)
    return m

def pidx(d, sub):
    for i, n in enumerate(d['info']['TeamNames']):
        if sub.lower() in n.lower(): return i
    return -1

def main():
    folder, psub, stype, sctx = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    N = int(sys.argv[5]) if len(sys.argv) > 5 else 9999
    agent_dir = sys.argv[6] if len(sys.argv) > 6 else None
    mod = load(agent_dir) if agent_dir else None

    files = sorted(glob.glob(f"{folder}/*.json"))[:N]
    n_opts_dist = Counter()      # how many options the pro faced
    pro_pos = Counter()          # which position (index into option list) the pro chose
    pro_payload = Counter()      # (area,type) of the chosen option
    our_pos = Counter()          # which position OUR pilot chose
    agree = [0, 0]               # [n_agree, n_total] when agent given
    examples = []

    for f in files:
        try: d = json.load(open(f))
        except Exception: continue
        pi = pidx(d, psub)
        if pi < 0: continue
        if mod is not None:
            try: mod._TRK.update({"prized": None, "pre_ko": False, "cur_log": [], "pre_log": [], "turn_seen": -1})
            except Exception: pass
        for t, step in enumerate(d['steps']):
            e = step[pi] if pi < len(step) else None
            if not e: continue
            o = e.get('observation') or {}; sel = o.get('select'); act = e.get('action')
            if not sel or not act: continue
            if sel.get('type') != stype or sel.get('context') != sctx: continue
            opts = sel.get('option') or []
            if len(opts) <= 1: continue
            n_opts_dist[len(opts)] += 1
            # pro chosen positions
            try:
                chosen = [int(x) for x in act]
            except Exception:
                continue
            for c in chosen:
                pro_pos[c] += 1
                if 0 <= c < len(opts):
                    op = opts[c]
                    pro_payload[(op.get('area'), op.get('type'))] += 1
            # our pilot
            if mod is not None:
                wrapped = {'current': o.get('current'), 'select': sel, 'logs': o.get('logs', []),
                           'step': t, 'remainingOverageTime': 600,
                           'search_begin_input': o.get('search_begin_input')}
                try: ours = mod.agent(wrapped)
                except Exception: ours = None
                if ours is not None:
                    try:
                        ours_i = [int(x) for x in ours]
                        for c in ours_i: our_pos[c] += 1
                        ag = set(ours_i) == set(chosen)
                    except Exception:
                        ag = False
                    agree[0] += int(ag); agree[1] += 1
                    if len(examples) < 6 and not ag:
                        examples.append((os.path.basename(f), t, len(opts), chosen, ours,
                                         [ {k:op.get(k) for k in ('area','index','type','playerIndex')} for op in opts[:6] ]))

    tot = sum(n_opts_dist.values())
    print(f"\n=== {psub}  type={stype} ctx={sctx}  ({tot} decisions across {len(files)} files) ===")
    print("n_options faced (top):", dict(n_opts_dist.most_common(8)))
    print("PRO chose POSITION (top):", dict(pro_pos.most_common(10)))
    print("PRO chosen payload (area,type):", dict(pro_payload.most_common(8)))
    if mod is not None:
        print(f"OUR agreement: {agree[0]}/{agree[1]} = {agree[0]/max(1,agree[1]):.1%}")
        print("OUR chose POSITION (top):", dict(our_pos.most_common(10)))
        print("--- example disagreements ---")
        for fn, t, no, chosen, ours, opts in examples:
            print(f"  {fn} step{t} nopt={no} PRO={chosen} OURS={ours}")
            for j,op in enumerate(opts): print(f"      opt{j}: {op}")

if __name__ == "__main__":
    main()
