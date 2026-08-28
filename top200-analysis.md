# Top-200 Ladder Analysis + Win-Prediction Model
*529 top-200 replays · 137 unique decks · your 61 fresh games · July 19, 2026*

## 1. Your fresh results (already covered, quick recap)

Grimmsnarl 13W–12L (52%) — first deck of ours above water; beats M-Lucario 3–1.
Alakazam v6 17W–19L (47%) — the mirror is the problem (2–6 vs other Alakazams).

## 2. What the top 200 actually plays

| Archetype | Decks | Avg rating |
|---|---|---|
| Alakazam | 116 | 1007 |
| Grimmsnarl | 40 | **1019** (highest) |
| Crustle | 40 | ~1005 |
| M-Lucario | 22 | ~995 |
| Dragapult | 16 | ~1000 |

Head-to-head at the top: **Grimmsnarl beats Alakazam 46–26**, "other" decks beat
Alakazam 37–26, and **Dragapult beats both** — 16–11 vs Alakazam, 9–3 vs
Grimmsnarl. In the 1100+ rating band the Grimmsnarl share climbs to 25% while
Alakazam falls to 37%. Alakazam is the most-played deck and the most-countered.

## 3. Win-prediction model (deck lists → winner)

Trained logistic regression + gradient boosting on card-count differences,
5-fold cross-validation grouped by episode.

- LogReg CV AUC **0.571**, GBM 0.552. Read: deck choice alone explains a real
  but modest edge — most variance is piloting + draw luck. That matches what
  we've seen: our version bumps moved ratings more than deck swaps did.

**Cards the model likes (positive weight per extra copy):** Battle Cage
(+0.49), Dunsparce 305 (+0.44), Relicanth (+0.43), Dusk Ball, Lana's Aid
(+0.30), Fezandipiti ex (+0.19), Marnie's Grimmsnarl ex (+0.17), Judge,
Xerosic's Machinations (in 82/137 decks — the field's favorite disruption).

**Cards the model dislikes:** Brock's Scouting (−0.57), Dudunsparce 66
(−0.39), Switch (−0.38), Rare Candy (−0.28), **Alakazam 743 (−0.24)**, Shaymin
(−0.24), Latias ex, Lillie's Determination, Night Stretcher (both ubiquitous,
slightly negative = they're in losing piles too).

The striking one: Alakazam itself carries a *negative* weight now. The meta has
adapted — playing Alakazam is a headwind at the top. Note our Dudunsparce/
Shaymin/Rare Candy package is all negative-weight; that's the mirror-heavy
Alakazam shell being farmed by Grimmsnarl.

## 4. Our decks scored against the whole top-200 field

| Deck | Exp. win rate (GBM) | vs 1000+ rated decks |
|---|---|---|
| Grimmsnarl v6 | **59.9%** | **53.4%** |
| Alakazam v6 | 49.2% | 45.5% |
| Sharpedo v6 | 43.5% | 39.7% |
| Best ladder Dragapult (rated 1122) | 75.3%* | — |

*Inflated (that deck's own games are in the training data), but directionally
right: Dragapult is the best-positioned archetype and only 16/307 decks play it.

## 5. Recommendations

1. **Don't upload Sharpedo v6.** 43.5% expected vs the field, 39.7% vs good
   decks — worst of our three. Shelve it.
2. **Keep Grimmsnarl as an active slot.** Best deck we own by both live results
   and model score.
3. **Build a Dragapult pilot.** It beats both top archetypes, almost nobody
   plays it, and the model loves it. I saved the exact 60 cards of the
   highest-rated ladder Dragapult (1122) to `best_dragapult_deck.csv` — we can
   clone the list and write a v3-template pilot for it today, using the
   remaining upload slots for Dragapult instead of Sharpedo.
4. Alakazam v6 is treading water in a hostile meta; its ceiling is capped until
   the mirror improves (that's a search-pilot problem, not a card problem).

## Appendix: best ladder Dragapult list (rated 1122)

4 Basic {R} Energy (2), 3 Basic {P} Energy (5), 1 Basic {D} Energy (7),
1 Munkidori (112), 4 Dreepy (119), 4 Drakloak (120), 3 Dragapult ex (121),
2 Duskull (131), 2 Dusclops (132), 1 Dusknoir (133), 1 Fezandipiti ex (140),
1 Budew (235), 1 Moltres (791), 1 Meowth ex (1071), 1 Unfair Stamp (1080),
4 Buddy-Buddy Poffin (1086), 2 Night Stretcher (1097), 3 Crushing Hammer (1120),
4 Ultra Ball (1121), 4 Poké Pad (1152), 3 Boss's Orders (1182), 3 Crispin (1198),
4 Lillie's Determination (1227), 1 Dawn (1231), 2 Team Rocket's Watchtower (1256)

Gameplan: Drakloak's Recon Directive smooths draws every turn; Dragapult ex
Phantom Dive (200 + 6 spread counters on their bench) sets up multi-KO turns;
Dusknoir line converts spread into surprise KOs; Crushing Hammer + Budew slow
the opponent's setup. The bench-spread damage is what breaks Grimmsnarl (kills
Impidimps) and Alakazam (kills Abra/Dunsparce) before they come online.
