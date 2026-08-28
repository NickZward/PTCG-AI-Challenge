#!/usr/bin/env python3
"""Decisive H1-vs-H2 test: when our pilot returns an OPTION-POSITION for a deck-fetch,
does the engine fetch the card that option refers to (H1, correct) or the card at that
DECK INDEX (H2, bug)? Drive a real game; at the first TO_HAND deck-fetch, submit a
chosen option-position and check which card actually enters hand."""
import sys, os, importlib.util
ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/dipplin_v1"))
from cg import game as cggame

def load_agent(subdir, modname):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(subdir, "main.py"))
    mod = importlib.util.module_from_spec(spec); sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    deck = [int(x) for x in open(os.path.join(subdir, "deck.csv")).read().split()]
    return mod.agent, deck

def hand_ids(obs):
    cur = obs.get("current") or {}
    you = cur.get("yourIndex", 0)
    p = cur.get("players", [None, None])[you] or {}
    h = p.get("hand") or []
    return [c.get("id") if isinstance(c, dict) else c for c in h]

def main():
    a_dir = sys.argv[1] if len(sys.argv) > 1 else "my-agent/grimmsnarl_v11"
    agent, deck = load_agent(a_dir, "probe_agent")
    _, deckB = load_agent(sys.argv[2] if len(sys.argv) > 2 else "my-agent/dipplin_v8", "oppB")
    tested = 0
    for game in range(40):
        obs, sd = cggame.battle_start(list(deck), list(deckB))
        if obs is None: continue
        try:
            for _ in range(4000):
                cur = obs.get("current") or {}
                if cur.get("result", -1) not in (None, -1): break
                sel = obs.get("select")
                if sel is None: break
                you = cur.get("yourIndex", 0)
                # is this OUR TO_HAND deck-fetch with a populated deck?
                is_fetch = (sel.get("type") == 1 and sel.get("context") == 7
                            and sel.get("deck") and len(sel.get("option") or []) > 1)
                wrapped = {"current": obs.get("current"), "select": sel, "logs": obs.get("logs", []),
                           "step": 0, "remainingOverageTime": 600,
                           "search_begin_input": obs.get("search_begin_input")}
                if is_fetch and you == 0 and tested < 8:
                    opts = sel["option"]; deck_arr = sel["deck"]
                    action = agent(wrapped)
                    pos = int(action[0])
                    opt = opts[pos]
                    # card the OPTION refers to (option.index into deck array)
                    oi = opt.get("index")
                    opt_card = deck_arr[oi].get("id") if (oi is not None and oi < len(deck_arr) and isinstance(deck_arr[oi], dict)) else None
                    # card at DECK INDEX == pos (the H2 interpretation)
                    deckpos_card = deck_arr[pos].get("id") if (pos < len(deck_arr) and isinstance(deck_arr[pos], dict)) else None
                    before = sorted(hand_ids(obs))
                    obs = cggame.battle_select([pos])
                    after = sorted(hand_ids(obs))
                    # what got added to hand
                    added = list((__import__("collections").Counter(after) - __import__("collections").Counter(before)).elements())
                    print(f"[fetch #{tested}] pos={pos} n_opt={len(opts)} n_deck={len(deck_arr)} "
                          f"opt.index={oi}")
                    print(f"   OPTION refers to card id = {opt_card}  (H1 expects this fetched)")
                    print(f"   card at DECK INDEX {pos}   = {deckpos_card}  (H2 would fetch this)")
                    print(f"   ACTUALLY added to hand    = {added}")
                    tested += 1
                    continue
                action = agent(wrapped)
                obs = cggame.battle_select([int(a) for a in action])
        finally:
            cggame.battle_finish()
        if tested >= 8: break
    print(f"\ntested {tested} deck-fetches")

if __name__ == "__main__":
    main()
