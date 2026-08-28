#!/usr/bin/env python3
"""Reconstruct a pilot's 60-card deck from replays via the serial-aggregation method.

Every card in a replay carries a globally-unique per-seat `serial`; collecting
serial->id over all zones across a game gives a lower bound on the deck, and
max-aggregating across games converges on the exact 60 (validated: recovered
grimm_v12_live's deck 60/60, palsystem's 60/60 = byte-identical to oger_pal).

Usage: recon_deck.py <out.csv> <pilot_name> <archetype> <index.csv> [index2.csv ...]
Writes newline-separated card ids (Kaggle format). Prints the resolved list.
"""
import csv, collections, json, os, sys

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"


def load_replay(p):
    if os.path.exists(p):
        return json.load(open(p))
    return json.load(open(p.replace("/Users/nickzwart/Desktop/", ROOT + "/")))


def main():
    out, pilot, arch = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = []
    for f in sys.argv[4:]:
        rows += list(csv.DictReader(open(f)))
    seen, uniq = set(), []
    for r in rows:
        if r["episode"] and r["episode"] not in seen:
            seen.add(r["episode"]); uniq.append(r)
    g = [r for r in uniq if pilot in (r["p0"], r["p1"])
         and (r["a0"] if r["p0"] == pilot else r["a1"]) == arch]
    g.sort(key=lambda r: -int(r["episode"] or 0))
    best = collections.Counter(); used = 0
    for r in g[:120]:
        seat = 0 if r["p0"] == pilot else 1
        try:
            d = load_replay(r["path"])
        except Exception:
            continue
        ser = {}
        for st in d.get("steps") or []:
            try:
                cur = (st[0].get("observation") or {}).get("current") or {}
            except Exception:
                continue
            P = cur.get("players")
            if not P or not P[seat]:
                continue
            pl = P[seat]
            for gp in ("hand", "discard", "prize", "looking"):
                for c in (pl.get(gp) or []):
                    if isinstance(c, dict) and c.get("serial") is not None:
                        ser[c["serial"]] = c.get("id")
            for gp in ("active", "bench"):
                for s in (pl.get(gp) or []):
                    if not isinstance(s, dict):
                        continue
                    if s.get("serial") is not None:
                        ser[s["serial"]] = s.get("id")
                    for sub in ("preEvolution", "energyCards", "tools"):
                        for c in (s.get(sub) or []):
                            if isinstance(c, dict) and c.get("serial") is not None:
                                ser[c["serial"]] = c.get("id")
        c = collections.Counter(v for v in ser.values() if v is not None)
        for cid, k in c.items():
            best[cid] = max(best[cid], k)
        used += 1
        if sum(best.values()) >= 60:
            break
    tot = sum(best.values())
    if tot != 60:
        print(f"FAIL: reconstructed {tot} cards from {used} games "
              f"({'mixed lists — pilot changed decks mid-window' if tot > 60 else 'not enough games'})")
        sys.exit(1)
    open(out, "w").write("\n".join(str(c) for c, k in sorted(best.items()) for _ in range(k)) + "\n")
    NAME = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "pokemon-tcg-ai-battle/EN_Card_Data.csv"))):
        NAME.setdefault(r["Card ID"], r["Card Name"])
    print(f"OK: {out} from {used} games of {pilot} ({arch})")
    for cid, k in sorted(best.items(), key=lambda kv: -kv[1])[:10]:
        print(f"   {k}x {NAME.get(str(cid), '?')}")


if __name__ == "__main__":
    main()
