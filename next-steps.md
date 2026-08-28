# PTCG AI Battle Challenge — Roadmap & Parked Ideas

## JULY 20 (eve) — NEW LOGS ANALYSIS + STUCK-ACTIVE BUG (verified)
51 new Kilupy games (ep 87068934..87132732). Records: dipplin 25-18 (58%,
above gauntlet projection), grimmsnarl 3-3 (only 6 games). MILL CURE HOLDS:
1/18 losses was a deckout (and that one we took 5 prizes first). Everything
else = prize races. Wins avg 14.3 two-energy-turns vs losses ~0-2 (energy
consistency is the live margin). Matchups: Crustle 7-2, M-Lucario 5-4 GOOD;
Starmie 1-4, Dragapult 2-3, Alakazam 1-2 SOFT.

STRUCTURAL (confirmed via weakness data): tanks are lost by construction.
Do the Wave is {G}; Starmie(wk {L}), M-Lucario({P}), Archaludon({R}),
Dragapult(none) — NONE weak to Grass. Max 40x5x2=400 barely OHKOs a 330-340
wall while they OHKO our 40-100 HP single-prizers every turn. ~44% of losses
are OUTMATCHED (tank meta). Don't chase these with card swaps.

*** STUCK-ACTIVE LOCK — ROOT CAUSE FOUND + FIXED (dipplin_v6, July 20 late) ***
Drove the ENGINE to reproduce the lock and logged every decision. TRUE CAUSE
(not KO-promote as guessed): SELF-INFLICTED. (1) SETUP_PRIORITY opened with
GROOKEY active (support/tutor line), not APPLIN (attacker line). (2) The pilot
then EVOLVED the active Grookey -> Thwackey (EVOLVE_ORDER ranked Thwackey 2nd,
no active-vs-bench check). Thwackey is a 0-energy body, retreat cost 2, can't
pay -> locked -> self-decks. Thwackey tutors fine from the BENCH; it should
NEVER be active.
FIX (my-agent/dipplin_v6, deck = Jack's v4 list UNCHANGED, 2 pilot lines):
  - SETUP_PRIORITY: APPLIN first (attacker line -> Dipplin active).
  - Evolve guard: forbid evolving the ACTIVE into a non-ready-attacker.
VERIFIED IT FIRES (the check the discarded Kieran attempt failed): lock-games
28->7 back-to-back, support-active selects 37%->18%. Robust win-rate: band-
weighted +3.1pp (run1) and +3.4pp (run2) over 2x1400 games — the AGGREGATE is
stable even though per-matchup deltas swing +-10pp at 200 games (only trust
the weighted aggregate). Biggest gains vs long-game decks; regressions vs
aggro (M-Lucario/Grimmsnarl) were within run-to-run noise.
HONEST MAGNITUDE: modest (+3.4pp), NOT the "convert 28% of losses -> 65%" I
first hypothesized. Many lock-states self-resolve (opponent KOs the stuck
Thwackey) so the lock isn't always fatal; its clearest cost is on ladder vs
SLOW/passive "other" decks (not in the gauntlet) that let dipplin self-deck.
Applin-first also just gets the attacker online faster (independent gain).
COUNTERFACTUAL REPLAY vs v5's EXACT 43 ladder opponents (July 20, archetype-
matched pilots driving each exact opp deck; 33/43 pilotable, 40 games each):
  v5 (on ladder now): 59.6%   v6-final: 63.4%  (+3.8pp)
v6 FINAL = v5's proven deck (Boss1/Lana2) + anti-lock pilot (I re-based v6
onto the ladder deck; the earlier v4-deck v6 was only +1.7pp b/c it dropped
the Lana edge). Per-archetype v5->v6: Crustle 79->85, Dragapult 55->62,
Alakazam 68->73, Archaludon 38->42, Grimmsnarl 60->72(small n); FLAT vs tanks
M-Lucario 55->54, Starmie 39->40 (structural, expected). Conversion of v5's
16 lost matchups: 56%->60% expected — modest, because most v5 'losses' were
~coinflip matchups lost to VARIANCE, not structural losses. Honest takeaway:
v6 is a steady +3.8pp across the board from fixing the self-inflicted lock +
keeping the proven deck, NOT a dramatic loss-conversion.
Caveat: opponents piloted by archetype-matched gauntlet agents (not the exact
ladder agents); 10/43 'other'/Cynthia/Kangaskhan games excluded (no pilot).
STATUS: submission_dipplin_v6.tar.gz = ladder-deck + fix, packed + Kaggle-
validated. STAGED (freeze). Ship decision needs current ladder score: v6 is a
clean +3.8pp upgrade of exactly what's running now (same deck, one bug fixed)
-> low-risk swap if v5 has stalled; hold if still climbing.

## (superseded) earlier stuck-active notes (Kieran attempt failed, discarded)
A 0-energy support Pokemon (Thwackey/Grookey) gets trapped ACTIVE with
charged Dipplins benched. Retreat cost 2, 0 energy -> can't retreat; Kieran
switch is (a) gated on opp_is_ex so never fires vs non-ex tanks AND (b)
un-playable anyway because the pilot spends its 1 supporter/turn on draw
cards. Result: passes turns and SELF-DECKS a WON game (verified ep 87085707:
17 turns stuck at prize 1/6 vs a 40HP Great Tusk; ep 87082979: 8 turns stuck
at prize 1/1 sudden-death). QUANTIFIED: lock hits 10/41 games (24%), LOST 5
of them = 28% of all dipplin losses. Converting 3-4 -> dipplin ~65%.

FIX ATTEMPT v6 (Kieran-switch-when-stuck) = FAILED VERIFICATION, DISCARDED
(moved to my-agent/.wip_dipplin_stuckfix_DOESNOTWORK). Instrumentation proved
Kieran is offered as playable 0/194 stuck-selects (supporter slot already
spent). v6 was functionally identical to v4; the "+3.6pp gauntlet" was NOISE
(150-game samples carry ~3pp; caught it before shipping — same trap as the
4 prior noise-accepts). NO submission changed.

REAL FIX (next session, needs engine source): PREVENT the lock, don't escape
it. Read 'ptcgProgram 22/'SelectProc.h to find the exact forced-promote
context (TO_ACTIVE=4 filter caught 0 in sim — promotion surfaces elsewhere),
then either (a) guarantee a charged Dipplin is promoted over Thwackey, or
(b) prophylactic Air Balloon (-2 retreat, in deck x2) on benched support so a
stuck active can free-retreat, or (c) reserve the supporter slot for Kieran
when a lock is one KO away. MUST re-verify the fix FIRES (today's method)
before trusting any win-rate delta.

Also new: full C++ ENGINE SOURCE now local (ptcgProgram 22/) + manifest.csv
(daily Kaggle episode datasets). Engine unlocks exact-sim multi-ply search
(energy sequencing = the live loss margin) and deterministic self-play tuning.

## NEW BATCH + OKIDOGI (July 21) — from user's loss_step_by_step screenshots
Screenshots pointed to ep 87225113 (Dipplin lost to miruto=Okidogi). Found it in
logs -> parsed full JSON (better than screenshots). Analyzed the whole NEW 16-game
batch (ep 87138558..87225113): Dipplin 6-5 (55%), Grimmsnarl 1-4 (20%, small n).
ALL 9 losses = prize-race BLOWOUTS; 6 of 9 took 0 prizes; 2 were total bricks
(0 attacks). Opponents mostly fast-aggro/tanky "other" decks (Okidogi, M-Kangaskhan,
Mega Abomasnow) + structural Archaludon. NOT one common bug — diffuse variance/
early-game losses (fragile 40HP Applin + slow Grimmsnarl setup run over by aggro).
OKIDOGI added to gauntlet (my-agent/gauntlet/okidogi/ — Fighting aggro, Good Punch
70/+100 Adrena-Power). SURPRISE: Okidogi is NOT a hard matchup — we're FAVORED:
dipplin 61-69%, grimmsnarl 66-76%. The miruto loss was a bad-opening blowout, not
structural.
IMPORTANT TRADEOFF FOUND: the anti-lock fix HURTS fast-aggro matchups. vs Okidogi:
dipplin v4 69% -> v6 61%; grimmsnarl v6 76% -> v7 66% (both ~-8-10pp, same direction
= real, not noise). Anti-lock changes setup/evolve, exposing the fragile early game
vs aggression. Net-positive FIELD-WEIGHTED still holds (Alakazam 35% >> aggro ~11%),
so v6/v7 upload recommendation stands — but it's a TRADEOFF, not a pure win. Future:
a fix variant that doesn't expose the early game vs aggro.

## GRIMMSNARL losses vs the 1311-replay field -> FIXED (July 21, grimmsnarl_v7)
Played grimmsnarl_v6 vs the replay field. 59% field-weighted, LOSSES = prize
races (122 prized-out). Mistake signals: Grimmsnarl NEVER came online in 15/132
losses (setup failure), losses 2 turns slower to online, stuck-active 68/320
games (support trapped active). grimmsnarl_v6 LACKED the anti-lock evolve guard.
FIX (grimmsnarl_v7, deck IDENTICAL to v6, 1 pilot change): ATTACKER_LINE anti-
lock evolve guard — forbid evolving the ACTIVE into a non-attacker-line Pokemon
(Froslass); allow Impidimp->Morgrem->Grimmsnarl on the active. Keeps the attacker
line active -> Grimmsnarl online faster. (Used the ATTACKER_LINE form from the
start, learned from the failed Alakazam guard which blocked the 2-step setup.)
VERIFIED: 2 robustness runs +6/+10pp on the big matchups; FULL FIELD v6 54% ->
v7 62% (+8pp). Gains: Alakazam +11 (35% of field), Grimmsnarl mirror +18,
M-Lucario +12; small regressions on low-weight Archaludon(-13,4%) & Dipplin(-7,1%).
STATUS: submission_grimmsnarl_v7.tar.gz packed + Kaggle-validated. STAGED.
Climb pair upgrade: dipplin_v6 + grimmsnarl_v7 (v7 replaces v6, same deck + fix).

## DRAGAPULT vs the 1311-REPLAY FIELD — diagnose/fix/retry (July 21, dragapult_v5)
Played dragapult_v4 against the opponent field derived from all replays
(archetype-matched pilots on real opp decks, weighted by the true field:
Alakazam 35%/Grimmsnarl 15%/Crustle 13%/tanks). BASELINE: 36% field-weighted
(weakest deck). Dominant loss mode = PRIZED-OUT (outraced). Mistake signals:
energy-brick 385 turns (Dragapult with 2+ same-type energy, can't pay {R}{P});
stuck-active minor (7%).
FIXES (dragapult_v5, verified to fire):
 1. Hard {R}{P} energy discipline: guarantee 1 Fire+1 Psychic, never Dark on
    the attacker line, HARD-block duplicate type (was a weak +1 tiebreak).
    Brick-turns 74->29 (halved).
 2. Boss-bench-farming: drag up a benched Pokemon Phantom Dive (200) can KO,
    converting spread into prizes (pilot only Bossed the active before).
RESULT (2 robustness runs, field-weighted): v4 33-36% -> v5 38-40% (+4-5pp).
Biggest gain vs ALAKAZAM (35% of field): +7-14pp (Boss-farms the fragile
Abra/Dunsparce bench to win the race). No consistent regression (M-Lucario
-16 in run1 was noise, +1 in run2). EnergyType==card id (Fire2/Psych5/Dark7).
CEILING UNCHANGED: still ~39% = weakest deck. Structural: Crustle immune to
ex damage; Alakazam-heavy field outraces it. The real gap (Phantom Dive spread
SEQUENCING for multi-KO turns, 77% in human hands) needs the multi-ply search
pilot — a bigger project. v5 is a real +4-5pp but Dragapult stays a SUMMIT/
situational deck, not for the climb.
STATUS: submission_dragapult_v5.tar.gz packed + Kaggle-validated. STAGED.

## ALAKAZAM AGENT — BUILT + TRAINED (July 21, alakazam_v9)
Deck = JACK's list (rank #3, 416 games; best-tested): 4 Abra/Kadabra/Alakazam,
4 Enhanced Hammer, 3 Xerosic, 3 Rare Candy, 4 Hilda/Dawn, 3 Boss, 2 Nighttime
Mine, NO Battle Cage. Bake-off: beat the v8 Battle-Cage variant (Battle Cage
is dead in the single-big-attacker tank meta; Powerful Hand is single-target
not spread).
PILOT = v8 base + 4 EVIDENCE-BACKED fixes (from verified-audit workflow, one
A/B-tested by the agent itself):
  1. KEY: HAND_IS_AMMO hold-gate now EXEMPTS hand-growers (Hilda/Dawn/Dudun).
     Bug: a charged Alakazam attacked sub-lethally instead of first playing
     draw supporters to GROW Powerful Hand (20 x hand). Agent A/B +10pp.
  2. Powerful Hand IGNORES weakness (engine-verified CardImpl.h) — removed the
     bogus weakness multiplier that overestimated KO damage.
  3. Dead retreat guard fixed (checked energy id 1; deck's energies are 5/13/19).
  4. Hilda play-cap raised 7->9.
MY INDEPENDENT A/B (720 games vs field): base 50% -> fixed 55% (+5pp). Gains:
Crustle 41->52, Dragapult 61->73, M-Lucario 57->65; flat Starmie/Archaludon;
loses to our own dipplin_v6 (26%). Two independent confirmations (agent +10pp,
mine +5pp).
FAILED ATTEMPTS (discarded, honest record): tried porting dipplin's anti-lock
evolve-guard — made it WORSE (Alakazam is a 2-step line Abra->Kadabra->Alakazam;
the guard blocked the attacker's own active-spot setup). The support-stuck lock
(Dunsparce/Fez active, 14-31/60 games) remains partly unfixed; the hand-grower
fix helped more than the lock port.
TUNER: ran vs field, accepted only noise-level knobs (baseline ~56%) -> ship
defaults.
HONEST CEILING: Alakazam is the MOST-COUNTERED deck; even Jack/Yushin cap at
50-52% over 100s of games, and v9 LOSES to our dipplin_v6. v9 at ~55% vs the
gauntlet is near the archetype ceiling. It beats Dragapult (73%) but so does
grimmsnarl. VERDICT: solid build, but it does NOT clearly earn a slot over
dipplin_v6 + grimmsnarl_v6 for the climb. Keep as a situational option.
STATUS: submission_alakazam_v9.tar.gz packed + Kaggle-validated. STAGED.

## THE 800+ CLIMB PLAN (July 20 — gauntlet era)
Band meta (public notebook, July 19, 830 teams): 600-699 = Ala 22/Crustle 19/
MLucario 19; 700-799 = ARCHALUDON 26/Ala 17/MLucario 17; 800-899 = Ala 41/
Archaludon 23. New submissions START AT 600 — every re-upload resets the
climb, so FREEZE versions once uploaded; score = winrate x time-on-ladder.

GAUNTLET (my-agent/gauntlet/): archaludon, crustle, mlucario, starmie pilots
built from the field's best-performing mined lists. This replaces the old
self-pool as the validation target for ALL future changes + tuner runs.

Matrix (60 games/cell) + band-weighted expected WR:
                  600s   700s   800s   worst matchups
  dipplin_v4       57%    44%    51%   Archaludon 22% (structural: Full Metal
                                       Lab -30 + heals + stadium war),
                                       Starmie 31% (was 18%, anti-tank fix)
  grimmsnarl_v6    47%    48%    46%   Alakazam 40% (fixable pilot gap — TOP
                                       open work item)
  dragapult_v4     34%    38%    30%   BENCH IT for the climb; summit deck
                                       only (1100+ band = Ala+Grimm 71%,
                                       Crustle 0%)
Anti-tank fix shipped in dipplin_v4: tutor fetches Boss's Orders when opp
active out-HPs our full turn but their bench is farmable (Starmie +13pp).
Lineup for the climb: dipplin_v4 + grimmsnarl_v6 (+ third slot: consider
old alakazam_v7 — rough numbers suggest ~56% at 700-799, verify first).
GRIMMSNARL ANTI-ALAKAZAM FIX (July 20, shipped in grimmsnarl_v6 repack):
Diagnosis (40 instrumented games): losses = Grimmsnarl online turn ~23 vs
~13 in wins, opp hand ballooning to 13.6 avg (Powerful Hand 270+ = OHKO),
Xerosic fired 0.05/game in losses. Fixes: (1) searches surface Xerosic when
opp hand >= 7; (2) Unfair Stamp fat-hand exception (STAMP_BIG_HAND=8
overrides the mill ban — resetting a Powerful Hand stockpile > mill cost);
(3) THE BIG ONE: Spikemuth mill-gate made setup-aware — free search is
never skipped until Grimmsnarl is online (tempo > deck economy pre-setup).
Result: 40% -> 55% vs alakazam (198 games); regression sweep all clean or
better (mlucario 40->54, mirror 48->57); band-weighted now 56/53/53 across
600-899 — best climber in the stable.
Gauntlet retune DONE (July 20): dipplin_v4 defaults held (57% vs pool);
grimmsnarl's one accepted knob (ENERGY_CAP 3) FAILED independent 240-game
replication (48% vs 47% baseline) — noise-accept, reverted to defaults.
Lesson reaffirmed: always re-verify tuner accepts with fresh games.
DECK EVOLUTION (July 20): first empirical deck search — 152 single-card
mutations of Jack's list, 120-game screens + 360-game confirms vs the
band-weighted gauntlet (~20k games, 13 min). ONE swap survived:
-1 Boss's Orders (2->1), +1 Lana's Aid (1->2). Confirmed TWICE
independently: 56.1% vs 51.4% (360g) then 54.2% vs 46.7% (600g each).
Why it works: Thwackey tutors Boss on demand (anti-tank logic), so the 2nd
copy was redundant; 2nd Lana's Aid feeds the attrition war (3 bodies+energy
back) = exactly dipplin's blowout weakness. 7 other finalists collapsed on
confirmation (screen noise, correctly rejected).
STAGED as my-agent/submission_dipplin_v5.tar.gz (validated). DECISION RULE:
if dipplin_v4 stalls below ~750 at next ladder check -> swap to v5 (the
600-reset is worth +7pp); if it punched through the 700s -> hold freeze.
Open items:
(2) submission ledger below — FILL IN public scores as you see them.

## SUBMISSION LEDGER (one line per upload; add score when observed)
| date (2026) | file | notes | public score |
|---|---|---|---|
| ~Jul 19 | submission_dipplin_v1 | first Dipplin | (ended ~56% WR) |
| ~Jul 19 | submission_dragapult_v1 | LumenLiquidity clone, old pilot | |
| ~Jul 19 | submission_grimmsnarl_v3 | Luca list + Xerosic, old pilot | |
| Jul 20 am | submission_dipplin_v2 | energy stockpile + tutor gate | |
| Jul 20 am | submission_grimmsnarl_v4 | setup-collapse fixes | |
| Jul 20 | submission_dipplin_v3 | mill-race patch | |
| Jul 20 | submission_grimmsnarl_v5 | mill-race patch | |
| Jul 20 | submission_dipplin_v4 | oracle + prize-inference + anti-tank | |
| Jul 20 | submission_grimmsnarl_v6 | oracle + anti-Alakazam + setup-aware gate | |
| Jul 20 | (STAGED) dipplin_v6 | ladder-deck + anti-lock pilot, +3.8pp vs v5 on its exact opponents | (not uploaded) |
| (freeze) | — | NO MORE SWAPS unless provably broken — score = WR x time | |

First post-upload batch (Jul 20 pm, 58 games): dipplin 15-13 (54%),
grimmsnarl 17-13 (57%) — both tracking gauntlet projections. ZERO deck-outs
(mill cure holding). Grimm losses = close prize races (4 losses at 5 prizes
taken). Dipplin: 9/13 losses were 0-prize blowouts SPREAD across archetypes
= opening-consistency variance (80HP attackers punish slow starts), the
deck's known tail risk. Parked improvement idea for a future session:
opening consistency (mulligan-equivalent logic / first-3-turn priorities),
NOT worth breaking the freeze for at current numbers.

## THE MILL-RACE FINDING (July 20 — read this before any pilot work)
Day-1 ladder run of dipplin_v2 + grimmsnarl_v4 (33 decided games): EVERY
decided game ended in deck-out — all 19 losses AND all 14 wins. At our
rating the meta is a mill race: rule-based agents rarely convert 6 prizes,
so whoever consumes deck slower wins. Consistency engines (tutors, dig
items) are ANTI-optimal once setup is done. Implications baked into v3/v5:
 1. Lillie's INVERSION: shuffles hand into deck then draws 6 — with hand>=8
    it REFUELS the deck (+2 or more). Old gate (play at hand<=5) was
    backwards for mill wars. Both decks run 4 copies = the race weapon.
 2. MILL-RACE MODE: once deck<30 and not ahead on cards by 3+, all optional
    consumption stops (tutor/Spikemuth/dig items/Petrel/Morty's).
 3. BOSS BENCH FARMING: gate on KO-able BENCH targets (old gate only
    checked the active) — converting prizes is how races end early.
 4. Local validation caveat: our pool decks close games, so ladder stalls
    are under-represented locally. Long mirrors are the best proxy.

## Ready to upload (when slots reset)
- `my-agent/submission_dipplin_v4.tar.gz` + `submission_grimmsnarl_v6.tar.gz`
  (July 20) — v3/v5 + the harvest from the two official samples:
  (1) ATTACK ORACLE: search_begin/search_step simulates each attack — exact
      damage/KO replaces heuristics; Boss gates use simulated damage.
  (2) PRIZE INFERENCE: serial tracking -> exact prized cards + true deck
      counts gate Poffin/Poke Pad/energy fetch.
  (3) Unfair Stamp KO-timing built but DEFAULT OFF ('STAMP_ON_KO': 0) —
      Stamp refuels opp deck by hand-2 cards = anti-mill. Knob for tuner.
  Bugs fixed en route (regression-tested): deck.csv now read from module
  dir (root's stale deck.csv poisoned tracking locally); oracle terminal
  states ranked losses as +6 prizes/999 dmg (pilot preferred simulated
  suicides — 48%->62% vs alakazam after fix).
  Validated: dipplin v4 beats v3 53.0% (400-game mirror); grimm v6 beats
  v5 51.8% (400 games). All features toggleable via params.json.
- `my-agent/submission_dipplin_v3.tar.gz` — mill-race pilot (above) +
  energy-first tutor when replacement Dipplin secured + recovery cards
  protected in discard priority. 54.0% vs v2 (500-game mirror), 71/100 vs
  alakazam (v2: 64), pool 57.2% (no regression).
- `my-agent/submission_grimmsnarl_v5.tar.gz` — same mill-race patch set.
  51.8% vs v4 (500-game mirror), deck economy +3.2 cards vs alakazam,
  pool 56.4% (no regression).
- `my-agent/submission_dipplin_v2.tar.gz` — dipplin_v1 ladder post-mortem
  (July 20, 52 games, 29-23 = 56%): ALL 23 losses were deck-outs; half the
  losses had <=4 attacks in 30-70 turns. Root cause: one lone energy
  circulating (fetch only grabbed energy at total drought -> no charged
  backup, KO'd Dipplin = drought again) while Thwackey tutor + dig items
  burned ~2 deck cards/turn vs opponent's 1. v2 fixes: ENERGY_STOCK
  (fetch/recover until 2 energies live), TUTOR_DECK_MARGIN (tutor + Poke
  Pad/Bug Catching stop when deck < opp-5 unless energy-short), Lana's Aid
  energy recovery. Validated vs alakazam_v7: 57%->70% wins, deck-out losses
  26->18, attacks/game 3.3->3.9. Pool 57.8%, mirror vs v1 50.2% (stalls
  don't occur in mirrors). Deck variant +2 energy TESTED AND REJECTED
  (54.2% pool vs 57.8% — dilution beats supply; Jack's 5-energy validated).
  Tuner running on new knobs; repack with params.json when done.
- `my-agent/submission_dipplin_v1.tar.gz` — Jack's (#3) 4-0 Dipplin/Thwackey list
  + dedicated pilot. Local record vs our own decks: 27-13 vs alakazam_v7,
  15-5 vs grimmsnarl_v3, 14-6 vs dragapult_v1 (70% overall, 100 games).
  Pilot tricks: bench-fill first (bench = Do the Wave damage), Festival
  Grounds priority, need-aware Thwackey tutor, dry-active retreat, energy
  only to attackers (deck runs just 5).
- `my-agent/submission_dragapult_v2.tar.gz` — same deck as v1, pilot patched
  after July 19 ladder losses (8/13 were setup collapses: Ultra Ball fetched
  unbenchable Drakloaks, Poke Pad/Lillie's gated shut). Fixes: need-aware
  fetch, setup-collapse guard, dry-active retreat, energy discipline.
  Final numbers (big samples): 52.1% vs old v1 (500-game mirror); 43.9% vs
  fixed pool [alakazam_v7 + grimmsnarl_v3 + dipplin_v1] where v1 scores 36.7%
  (+7.2pp). Knobs tuned by model/tuner.py, 240-game evals: defaults held.
- `my-agent/submission_grimmsnarl_v4.tar.gz` — same deck as v3, same pilot
  patch (7/12 ladder losses were setup collapses). Final numbers: 57.5% vs
  old v3 (500-game mirror); 56.2% vs fixed pool [alakazam_v7 + dragapult_v1 +
  dipplin_v1] where v3 scores 43.8% (+12.4pp).
- Engine speed discovery: local games run at ~23ms each (~2,600 games/min) —
  any pilot change can be validated on 1,000 games in under a minute
  (model/tuner.py `evaluate`, or scratch harness).
- Path B (behavioral cloning) — DONE, NEGATIVE RESULT (July 19). Extracted
  20,444 decisions / 149k option-samples from 344 games by 1000+ rated
  players (model/bc_extract.py -> bc_data.npz), trained a GBM option scorer
  (model/bc_train.py -> bc_model.joblib). Offline top-1 48.3% vs 46.4%
  "always first option" baseline. Online (my-agent/dragapult_v3, BC-driven
  card selects, harness A/B vs rule pilot v2): full BC 29% mirror / 26% vs
  pool; per-context best was discard at 51.7% (parity within noise), all
  others 41-48%. Conclusion: imitation without deck-specific intent loses to
  the need-aware rules; do NOT ship dragapult_v3. Assets kept for Path C
  (same feature builder reusable for a state-value function).
- Path C (July 19) — SHIPPED as `my-agent/submission_dragapult_v4.tar.gz`.
  Value function: model/vf_extract.py + vf_train.py -> vf_model.joblib,
  trained on 226,777 states from 869 games; val AUC .746 overall
  (.54 opening / .60 early-mid / .79 late-mid / .93 endgame).
  Pilot design that WORKS (dragapult_v4): rules decide by default; 1-ply
  search (search_begin/search_step, determinized hidden zones, rule-policy
  rollout to end of turn for a consistent horizon) may OVERRIDE only
  late-game (min prizes left <= 4) with >= 0.10 win-prob margin.
  Designs that FAILED (recorded so we don't retry them): raw VF argmax over
  MAIN options 13.5% vs rules; consistent horizon alone 21%; ungated
  override ~parity. Final: 52% over 1,000 mirror games vs v2, pool 45.7%
  (v2 43.9%, v1 36.7%). Graceful fallback: if sklearn/joblib missing in the
  competition runtime, v4 behaves exactly like v2.
  Lesson (Paths B+C agree): never let a noisy model replace a strong rule
  policy wholesale — gate deviations by model competence + confidence.
  Next ideas: multiple determinizations averaged, VF also for ATTACK/Boss
  target selects, retrain VF on future scraped games, port v4 wrapper to
  grimmsnarl/dipplin pilots.
- Known shared weakness (pre-existing, not from the patch): both lose ~30%
  to alakazam_v7 locally — the Powerful Hand race punishes slow setups.
- `my-agent/submission_alakazam_v6.tar.gz` — bench-engine pilot: fills bench to 5,
  recovery cards (Night Stretcher / Sacred Ash / Lana's Aid) jump to top priority
  when ≥2 Pokémon are in the discard, Sacred Ash becomes the #1 play in a deck-out
  race (+5 cards AND +5 bodies back into the deck).
- `my-agent/submission_sharpedo_v6.tar.gz` — same bench engine; Night Stretcher
  prioritized whenever a Pokémon is in the discard.
- Upload order: Alakazam first, Sharpedo last (last two = tracked pair).

## Parked experiment: Marnie's Grimmsnarl (Luca's list — the Alakazam-slayer)
The only deck going even-or-better with the #1 Alakazam archetype at the top of
the ladder (beat Yushin Ito head-to-head in episode 86657557).

Exact 60 (already prototyped in workspace `deck_grimmsnarl/`):
10x Basic {D} Energy (7), 2x Froslass (104), 4x Munkidori (112),
4x Marnie's Impidimp (646), 3x Marnie's Morgrem (647), 3x Marnie's Grimmsnarl ex (648),
2x Snorunt (860), 3x Rare Candy (1079), 1x Unfair Stamp (1080),
4x Buddy-Buddy Poffin (1086), 3x Night Stretcher (1097), 1x Pokégear 3.0 (1122),
1x Tool Scrapper (1137), 4x Poké Pad (1152), 2x Boss's Orders (1182),
4x Team Rocket's Petrel (1219), 4x Lillie's Determination (1227), 1x Dawn (1231),
4x Spikemuth Gym (1259)

Gameplan: Froslass pings every Ability Pokémon each checkup; Munkidori (with D
energy) moves those counters onto whatever matters; Grimmsnarl ex (320 HP) tanks
and Shadow Bullets (180 + 30 bench snipe); Punk Up on evolve attaches 5 D energy
from deck; Spikemuth Gym = free Marnie's search every turn.

Why parked: our rule-based pilot went 1–13 with it — the deck's edge lives in
Munkidori's damage-counter routing decisions, which need lookahead. Revisit once
the search pilot exists.

## Built: Dragapult (cloned from the 1122-rated ladder list)
`deck_dragapult/` + `submission_dragapult_v1.tar.gz` — packaged and validated.
The archetype beats both Alakazam (16-11) and Grimmsnarl (9-3) at the top of the
ladder, but our rules pilot only manages ~45% vs our own Alakazam v7 and loses
to our Grimmsnarl. Pilot work done: type-aware energy attach (Phantom Dive
needs {R}+{P}, never fired before the fix), Crispin prioritized when attackers
are dry, Cursed Blast gated to KO-conversions only, Fighting Wings +90 vs ex.
Remaining gap: no-Rare-Candy Stage 2 setup speed + spread-damage targeting —
both are search-pilot problems. Revisit alongside Grimmsnarl when search lands.

## The big project: lookahead-search pilot
Use the SDK's search_begin / search_step (cg/api.py) to simulate candidate moves
before choosing. Applies to every deck; expected to convert the 4-5-prize
near-miss losses. Start with 1-ply (evaluate each legal option, score resulting
state: prizes, board HP, hand size, deck count), then deepen.

## Key dates
- Entry/team deadline: Aug 9, 2026 · Final submissions: Aug 16 · Leaderboard final ~Aug 31
