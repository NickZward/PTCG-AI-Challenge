═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★★★ LATEST (2026-08-10) — STRATEGY TRACK REPORT DRAFTED; EVIDENCE PRESERVED
═══════════════════════════════════════════════════════════════════════════════════════════
**THE $240k DELIVERABLE IS NOW SPEC'D AND DRAFTED.** Requirements finally read off the Kaggle
page: Writeup **≤2000 words** (FIGURES DON'T COUNT — push data into them) + optional Media
Gallery; **Sept 6 = entry/rules-acceptance + merger deadline, Sept 13 = final submission**;
8 finalists × $30,000. Rubric **Model 70% / Deck 20% / Report 10%** — and only ONE of the five
Model bullets is ladder performance; the rest are clarity, originality, consistency under
repeated matches, and robustness to specific states/matchups. The page says outright that
mid/lower-tier teams can win on analysis quality. Only ~341 teams submitted here vs 5,582 on
the ladder. **This is our best expected-value play and it does not depend on the ladder.**

DELIVERABLE (all in `strategy_track/`): `WRITEUP.md` = 1,996 words, thesis **"Pick the deck your
agent can actually pilot"**; `make_figures.py` → 7 PNGs in `figures/`; `evidence/` = 44 preserved
gate logs. Structure maps 1:1 onto the rubric bullets.

**THREE CORRECTIONS MADE WHILE FACT-CHECKING (all were in our own favour to get wrong):**
1. **"Nothing ever beat v12" was FALSE.** 21 gated challengers: **4 became champion** (v2+search,
   v4, v6, v12) — a real improvement chain — then **17 consecutive failures after v12**. The
   honest framing ("progress was real, then it stopped") is stronger AND more credible.
2. **Ogerpon's gate number was unsettled** (62 / 65.6 / 71.1 across logs). Re-ran clean N=90 on an
   idle machine → **64.4%**. Four N=90 readings pool to 66.7%; we publish the conservative 64.4%.
3. **`pgrep` IS BROKEN ON THIS MAC** — returns 0 while `ps aux` shows workers at ~196% CPU. Every
   "verified idle" claim ever made with pgrep is unverified. **Use `ps aux | grep "[p]ython3"`.**
   `pkill -f` still works, so past kills likely took effect, but were never confirmed.

DECK-COMPLEXITY LAW (the report's spine, 4 builds): Ogerpon 1 sub-engine **64.4%** / Dudunsparce 3
**38.9%** / M-Lucario 4 **20.0%** / M-Kangaskhan 5 **11.1%** = **−13.7pp per sub-engine**.
Corollary: human-like lists are WORSE for us — real Ogerpon pilots run 17-21 bodies, ours runs 4;
a 10-body build bought nothing (64.4 vs 71.1, inside noise) and a full palsystem toolbox clone
scored 0%. TODO before Sept 6: confirm Kilupy is ENTERED + rules-accepted in the Strategy comp.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★★★ (2026-07-27 night) — v6 (flg fine-tune) GATE-PASSED: SHIP IT
═══════════════════════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★ 2026-08-06 (PM) — TWO MOONSHOTS LAUNCHED (user-approved, weeks-scale, background)
═══════════════════════════════════════════════════════════════════════════════════════════
**The only remaining v12-improvement ingredients are now running as unattended programs:**
**M1 — AZ VALUE LOOP: analysis/az_nn/az_driver.py (RUNNING as nohup; state+log in
model/az/azloop/driver.log).** Per iteration: 3 workers × 350 mcts-self-play games
(mirror + vs-v12 + vs-ogerpon, search=16, gen_value_selfplay.py) → train_value_kl on ALL
accumulated data (init=current best, kl=2.0, agree-floor 0.97 — v12's policy IS sacred) →
accept only if real-AUC beats best (eval set = model/az/grimm_eval_bothsides.npz, 214 Kilupy
sides 125W/89L) → gate vs v12 N=45 (workers naturally stopped — sequential design; load law).
NEVER touches live artifacts; >=55% gate = loud HUMAN REVIEW flag in log. Resumable: rerun
the script. First gate expected ~2-3 days. CHECK: tail model/az/azloop/driver.log.
**M2 — OPPONENT BELIEF MODEL: agent building extract_belief.py + train_belief.py from the
FULL-INFO spectator streams (both hands visible in steps[i][0].visualize) of the 9.5k-game
day-dumps. v0 metric: hand-prediction AUC/top-K vs archetype-average baseline. If it beats
baseline: integrate into mcts determinization (the crude-dummy fill that killed 2-ply) and
re-run the depth A/B.** Report remains the priority deliverable (Sept 13) — these run in the
background; do NOT let them eat writing time. Slots: v12 at 931 + dudun slot pending swap
back to canonical v12.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★ 2026-08-06 — OGERPON CELL FORMALLY CLOSED (fire-count zero); INSTRUMENT GAINED;
#     DUDUN LADDER DAY-1: 44.4% field, M-LUC = 31% OF LOW BAND
═══════════════════════════════════════════════════════════════════════════════════════════
**Dudun slot day-1: 16-20 (44.4%), score 500.7 — in the projected band but the low-band field
is 31% M-LUCARIO (the archetype's counter, hyper-dense down low: Majkel copycats farm Dudun
copies) and it farms us 2-9; ex-M-Luc we're 14-11. Good cells: Ala 4-0, Dragapult 3-0.
BAND-COMPOSITION LAW: a climb is decided by the band's counter-density, not deck strength
alone. Recommended: swap slot back to canonical v12 (experiment complete).** OGERPON ARC:
built my-agent/ogerpon_v1 (rules sparring, modal winners' 60; Teal Dance ability = the deck,
+32pp alone; 3 fix rounds → instrument beats stock v12 62%) → gated shell variant
(never-END + target-96) A/B: 44.4 vs 37.8 = +6.6pp BUT FIRE-COUNT ZERO in 10 games → delta
was noise; v12's stalls are NO-ATTACKER-READY (deep policy) — cell formally ACCEPTED (~3pp
at 5% share); variant deleted; ogerpon_v1 joins the permanent gauntlet (v12's hardest local
opponent). v12 other slot: 931, 46% window = plateau equilibrium.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★ 2026-08-05 (night) — SHIP NIGHT: RULES DUDUN TO LADDER; SCALING CURVE 3-PT NULL;
#     "MEGANIUM" = OGERPON RAMP, MECHANISM DECODED
═══════════════════════════════════════════════════════════════════════════════════════════
**SHIPPED (user decision, override of 60% bar): submission_dudun_rules_v1.tar.gz (Desktop,
md5 dbcc57b2) = dudun_v1 rules + params(240/150), gen-1 list, 38.9% vs v12 — to ONE slot;
v12 keeps the other. Expect field WR 40-55%, equilibrium ~700-900; the RUN IS THE EXPERIMENT
(first real-field cells for our Dudun incl. the mirror). Autopsy its first drop like v12's.**
Same night: (1) g2 style-pure compound REJECTED 22.2% (113-side corpus too thin; LiamK
iterates lists). (2) Day-dump mining (9.5k games): dudun corpus 516→1,549 sides; SCALING
POINT 3 = 20.0% → curve 24.4/22.2/20.0 = FLAT AT ALL SCALES; dudun imitation CLOSED (quality
ceiling — mid-band winners' moves don't encode elite skill). (3) meganium_manifest.csv: 926
Ogerpon-deck wins (Majkel played it! 80 wins @65%; 493 wins vs Grimm) = sparring-agent
material. (4) OGERPON AUTOPSY (37 teacher wins vs 8 our losses): id 96 = Teal Mask Ogerpon ex
(NOT Meganium); teachers win via NEVER-STALL attack pipeline (0 wasted attacker turns; attack
every turn T3-4+) + SB-always-into-Ogerpon + chip-finish next turn (2.03 Oger KOs/game; 30%
of wins are BENCH-OUTS of the thin bot); v12 loses via 4-9 attackless turns = deep policy,
NOT shell-patchable; DON'T implement bench-narrowing/tanking/energy-denial (proven
irrelevant). v12 fresh window 60.7% (n=117) at 880-950 band; mirror 21-11; Ogerpon cell 1-12
lifetime accepted (~3pp at 5% share) pending sparring-agent measurement.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★ 2026-08-05/06 — THE 4-OPTION DUDUN CAMPAIGN: 22% → 39% IN A DAY; MOAT HOLDS AT ~40
═══════════════════════════════════════════════════════════════════════════════════════════
**User approved all 4 improvement levers; all ran to completion (~24h). Final ladder of
builds vs v12 (idle-machine gates — see LOAD LAW below): imitation-only 22.2% | rules base
31.9% | Path C = imit policy + selfplay VALUE + search 37.8% (VF: gen_value_rules.py 165k
states → AUC 0.761 vs 0.736 baseline, late-game 0.850 vs 0.799, 1 epoch + --agree-floor=0.90)
| rules + knobs 38.9% N=90 (sweep found ROTATE_HP=240/WALLY=150; the 48.3% arm was winner's
curse — real effect +5-7pp; mechanism = rotate before 2-hit-kill range, matching the autopsy:
11/15 losses were board-preservation failures). Both branches asymptote ~38-39%; 60% bar NOT
reached — the pilot moat holds. LOAD LAW (new): v12's time-guard degrades under CPU
contention; any gate run with background compute is VOID (dudun "won" 71% under load).
KEPT: dudun_v1 + params.json(240/150) = upgraded sparring partner; dudun_vf1_best.pth +
model_np (the first value net that beat its baseline); 165k selfplay states; tune_dudun.sh.
REMAINING LIVE HYPOTHESIS (last one): LiamK-solo style-pure policy (his solo corpus ~250+
wins, scrape_liamk.py tops up in minutes) + dudun_vf1 value + search ≈ projected mid-40s.
Fire only if the wave persists; otherwise the campaign is complete and documented.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-08-05 (later) — DUDUN CORPUS AT 516 SIDES; CALIBRATION PROBE SAYS CURVE IS FLAT
═══════════════════════════════════════════════════════════════════════════════════════════
**Meta: podium now Majkel(M-Luc 1280)/Raihan(GRIMM 1169)/LiamK(Dudun gen-2, 1156). LiamK —
elite ex-Grimm teacher — went all-in on an EVOLVED Dudun list (Froslass pings for the mirror;
saved: dudunsparce_liamk_deck.csv): 114 games, vs Grimm 19-2 (90%), vs M-Luc 3-24, mirror
14-5. #5 ntumlnoob = wave ORIGINAL (554 games all-Dudun since Aug 2, 55.1%, vs M-Luc 10-100).
V12 CEILING FACT: elite Dudun walls the 1100+ neighborhood at ~90% vs Grimm; band copycats
stay fodder.** CORPUS: dudun_manifest.csv → 516 winning sides / 33k decisions (ntum 305,
やる気 84, LiamK 67, wwww 52) → imit_dudun.npz. **CALIBRATION PROBE dudun_imit_a (init
v11_best, held-out 57.5%): gate vs v12 = 22.2% — the DATA-SCALING CURVE IS FLAT (256
sides→24.4%, 516→22.2%, rules pilot 32%). Doubling mixed-pilot data bought zero; suspected
style-contradiction (Lopunny-pure vs Froslass-variant) + cross-deck floor >>1,000 sides.
REVISED PLAN: passive daily banking continues (free), but the next training attempt waits for
a SINGLE-elite-pilot corpus (LiamK solo reaching ~400-500 wins on his one list) — style-pure
is the only untested variable left. v12 holds both slots; nothing ships.**

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★ 2026-08-05 — v19 NEW-META FINE-TUNE REJECTED: THE 9th AND FINAL IMITATION DOOR
═══════════════════════════════════════════════════════════════════════════════════════════
**The one open imitation door ("v12 never saw the new archetypes — fresh top-Grimm-vs-new-meta
games are genuinely NEW information, unlike v8") was tested cleanly and CLOSED.** Executed:
scrape_grimm_fresh.py pulled 1,448 fresh replays of 7 named top-band Grimm pilots (incl.
leaderboard-#3 Raihan Ramadistra, 2-0 vs the top Dudunsparce teams; new-meta window
EP_FLOOR=89.5M; 1 failure total) → grimm_fresh_manifest.csv: 772 winning teacher sides /
67.7k decisions (76 vs Dudunsparce, 37 vs Meganium, 78 vs M-Lucario, 233 mirror) →
grimm_imit_v19 fine-tuned from v12's net (lr 1e-4, 3 epochs) → held-out 74.6%. **GATES:
do-no-harm vs v12 = 37.8% (tempo UP 1.60-1.33 but comebacks 6/19 vs 15/26 — v14's aggression
signature); CONTROLLED CELL TEST vs dudun_v1 = 62.2% where v12 scores ~68% on the SAME
opponent — the target-cell knowledge did not transfer either.** Fine-tuning dilutes v12
without buying the new cells. NOT shipped; candidate deleted; corpus + checkpoint kept as
report evidence. **v12 is now the terminal imitation artifact against EVERY tested axis
including new-information data. Remaining work: Strategy Track report (Sept 13), slot
maintenance, meta watch (Meganium share tripwire >10%), Dudun corpus accumulation (pure
option).** Tooling kept: scrape_grimm_fresh.py (name-targeted fresh-window scraper),
build_manifest_grimm_fresh.py, analysis/agree_dudun.py.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-08-04 (early) — "TRAIN DUDUN LIKE THE #3": AGREEMENT UP, STRENGTH FLAT. CEILING.
═══════════════════════════════════════════════════════════════════════════════════════════
**User asked to train dudun_v1 to behave like the #3. Built analysis/agree_dudun.py — a
DECISION-AGREEMENT harness for rules agents: replays all 5,306 of the #3's real decisions
(off-by-one law) and scores our agent's match, with per-context breakdown + MAIN option-type
confusion matrix. REUSABLE for any rules pilot vs any scraped corpus.** Round 1 findings →
fixes: ability over-fire (~860 over-picks), attach-after-plays sequencing, engine-first
evolves, DISCARD=spare-Lillie/Hilda-first (10%→35%), HEAL=most-damaged (27%→87%), TO_BENCH=
Dunsparce-first (30%→40%), rotation soft band 181-240. Agreement 28→34.9%. **BUT GATE 2:
28.9% with tempo COLLAPSE (T8 1.27→0.76) — two transplanted behaviors were context-entangled:
attach-late loses held energy to our own Lillie refresh; ability spacing starved draws.
Reverted those two, kept the five clean fixes → GATE 3: 31.1%. Three gates 35.6/28.9/31.1 =
all within noise, pooled 43/135 = 31.9%.** VERDICT: behavior cloning in RULE-space hits the
same wall as weight-space — the pilot's skill lives in invisible context (when Lillie is
coming, when the tank can afford to stay), not in copyable priorities. ~32% vs v12 is this
rules pilot's ceiling. NOT shipped (bar 60%); current build (clean fixes kept) = the sparring
partner. If a REAL Dudunsparce agent is ever needed (wave descends): the remaining route is
self-play RL (az pipeline) seeded with dudun_v1 as opponent — multi-day, only if justified.
NOTE metric subtlety: strict index-match under-counts (duplicate copies in hand = tie noise);
true agreement is higher — tie-aware credit would fix the metric (same lesson as imitation CE).

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-08-03 (late night) — DUDUN HEDGE BUILT, GATE-REJECTED 35.6%; KEPT AS SPARRING
═══════════════════════════════════════════════════════════════════════════════════════════
**Built my-agent/dudun_v1: complete rules pilot of the #3's Dudunsparce/M-Lopunny list
(dudunsparce_number3_deck.csv) on the grimmsnarl_v17 skeleton.** Full decoded mechanics
implemented: Gale Thrust 230-on-rotation loop, Air Balloon free-retreat (surfaces as ATTACH
type-8, NOT a play — cost 2 probe rounds), Buneary-opener (evolves to the 330 tank in place),
energy-scarcity routing (8-in-60; never feed the Dudunsparce line — it shuffles away), Wally
full-heal, Boss-as-removal, never-promote-a-dry-Mega discipline. 5 probe-fix iterations
(1/8 → 4/14): fixed balloon-never-deploys, energy-on-draw-engine, stuck-junk-active,
energy-starved-fetch, retreat-fuel priority inversion. **GATE vs grimm_v12_live N=45:
35.6% (tempo T8 1.27 vs 1.18 — early race EVEN; comeback 4/19 vs 14/26 — we lose the mid/late
game).** The source pilot wins this matchup 88% — the gap is pilot execution depth (tank
uptime + heal cadence), confirming AGAIN that pilot > deck. NOT shipped; both slots stay
canonical v12. KEPT VALUE: (1) dudun_v1 = the only Dudunsparce SPARRING PARTNER we own —
v12 rehearses the matchup before the wave descends (v12 beats OUR pilot 64%; the real #3
would be far worse); (2) the full 72-game playbook + card table live in the agent comments;
(3) probes in scratchpad (dudun_probe*.py). REVISIT TRIGGER: first Dudunsparce sighting in a
v12 replay drop, or the wave reaching >5% of our band. Next lever if revisited: tank-uptime
tuning (rotation earlier, Wally cadence 1.8/gm vs our ~0.6) — measured gaps, not guesses.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★ 2026-08-03 (night) — NEW #3 IS A DUDUNSPARCE GRIMM-FARMER (21-3 vs our archetype)
═══════════════════════════════════════════════════════════════════════════════════════════
**72-game scrape of the new #3 やる気元気ミワハルキ (1169.4, on the board 9h): ONE Dudunsparce/
M-Lopunny ex list (4x Buneary/Dunsparce/Dudunsparce + 3x M-Lopunny), 58-14 = 80.6% overall,
and 21-3 = 88% vs GRIMMSNARL.** Mechanism (measured over all 72 games): **93% of its games end
ADJUDICATED at the T13-15 turn cap — nobody prizes out; it simply leads the prize COUNT at the
buzzer (typically 4-5 vs 0-3)**. It is a deck engineered for the prize-leader-wins ruleset:
bank early prizes, tank the midgame with M-Lopunny, let the clock call it. Its ONLY losing
matchup is M-Lucario (0-4; H2H vs Majkel1337 1-4) → meta triangle: M-Lucario > Dudun-stall >
Grimmsnarl > (weakly) M-Lucario. The 3 Grimm wins against it all won the EARLY race (4-5 prizes
by T13) — aggression, not attrition, is the counter-shape. **Our exposure TODAY: zero — 0/97
new-era band games vs any Dudunsparce deck. The risk is descent-by-copying (meta-churn law).
STANDING TRIPWIRE: first Dudunsparce sighting in a v12 replay drop → measure the cell
immediately.** Also: top-3 composition has now turned over 4x in ~a week — more report material.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-08-03 (evening) — CROSS-ERA AUTOPSY: "1000+ then, <900 now" IS ORDER STATISTICS
═══════════════════════════════════════════════════════════════════════════════════════════
**User asked why v12 hit 1000+ before but the fresh slots sit at 728/873. 10-agent audited
workup over 341 decided games (old era V12/V12-3007_01/_02 n=244 vs new V12_1/V12_2 n=97):
AGENT UNCHANGED — 56.1% vs 55.7% WR, z=0.08.** The score gap decomposes as: (1) PEAK-VS-SPOT —
1000+ was the running MAX of a multi-day run; E[max over 250 games] − E[value at 50 games]
≈ +325-350 pts for identical strength; our own two slots (same tarball, same 5h) differ by 144
pts = walk noise. (2) MID-CLIMB — 600→1000 takes ~130-220 games at 56%; scheduler gives fresh
subs ~205-266 games/day decaying to ~40-75/day; expect ~900-1000 in 24-48h, P(touch 1000+)
60-85%. Plateau signature: an aged sub sits at exactly 50% WR (V12-3007_02 was 32-32).
(3) FIELD SHIFT (minor, net FAVORABLE): mirror share halved 27→16.5% (our worst cell, 44%),
M-Lucario tripled 5→14.4% — the one real bleed (8/43 new losses, 5 never-in-the-race; cell
67%→43%, Fisher p=0.27 so direction-only). Mix-adjusted expected WR 58.5% vs actual 55.7% =
within noise. Dudunsparce: ZERO games in our band yet. Strong names (Dries/Peel/Luca/Yushin)
appear only in old-era replays = the new subs haven't re-reached that neighborhood. Loss anatomy
unchanged (prize-race 98%); new losses actually LESS catastrophic (blowouts 58%→42%). Watch
item: Meganium/Ogerpon ramp (other[1,96,1094], opp 'monnosuke') is 0-4 lifetime vs us.
Episode-id clock ≈7,000 ids/hour (3-way calibrated) — reusable for future era comparisons.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-08-03 (later) — CROSS-DECK FINE-TUNE FAILS: v18-mluc GATE-REJECTED 24.4%
═══════════════════════════════════════════════════════════════════════════════════════════
**Experiment: can v11's card knowledge + fine-tuning on the #1's M-Lucario games produce a viable
second-deck pilot?** Built majkel_manifest.csv (256 winning sides from Majkel1337's replays, his
exact 60 saved to mlucario_majkel_deck.csv), extracted imit_majkel.npz (14,443 decisions,
--feat=2), fine-tuned from grimm_imit_v11_best (4 epochs, lr 1e-4, value-lambda 0.4). Held-out
top-1 60.1% (baselines 19.1/27.9) — the net LEARNED his move distribution. **But the GATE
(v18-mluc + Majkel's deck vs grimm_v12_live, N=45, T25): 24.4%. Tempo prizes-by-T8 0.58 vs 1.22,
comeback 4/23.** 60%-move-fidelity ≠ piloting: with ~1/25th the Grimm corpus, the net imitates
individual choices but cannot execute the deck's game plan (M-Lucario's setup sequencing is
unforgiving; misordered energy/evolution turns = dead board). LAW: **cross-deck transfer needs a
full-size teacher corpus (100k+ decisions), not a fine-tune drizzle.** Candidate deleted; nothing
shipped; both slots stay canonical v12. This also empirically re-confirms the meta-churn verdict
below: even WITH the #1's exact list + his games in hand, a competitive second-deck agent is >1
scrape-and-train cycle away — i.e. longer than the meta half-life. M-Kangaskhan agent: skipped
(deck already dead at top). Checkpoint kept for the report: model/az/grimm_imit_v18mluc_best.pth.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-08-03 — META CHURN VERDICT: DO NOT DECK-CHASE. v12 ENDURES. MAINTENANCE MODE.
═══════════════════════════════════════════════════════════════════════════════════════════
**#1 turnover in SIX DAYS: Dries (Grimm, 1209) → James Cox&Henry Chao (M-Kang, 1173) → Majkel1337
(M-LUCARIO, 1281.7, 257 games one list, 74.7% — highest WR ever measured).** The M-Kang era
lasted 3 days (now 2% of top field, Majkel 5-0 vs it). **NEW WAVE: DUDUNSPARCE decks = ~26% of
the 1200+ field** (67/87 of the 'other' cluster; brand-new archetype absent from all our data);
Majkel farms it 93% — that IS his rating. Top meta now: Grimm 29% / Ala 24% / Dudunsparce ~26%.
**STRATEGIC CONCLUSION (proven by natural experiment): counter-deck chasing is STRUCTURALLY
LOSING at a 2-3-day meta half-life — an agent takes 1-2 days to build+gate+climb and arrives
stale (yesterday's planned M-Kang agent is already obsolete). v12's Grimm position endures:
Grimm is the #1's SOFTEST matchup (he wins only 57% vs Grimm, n=75) and Grimm remains ~29% of
the top field. HOLD both slots on canonical v12; watch (a) whether Dudunsparce descends to our
band and how v12 fares vs it (UNKNOWN cell — first replay drop will show), (b) top-3 deck churn.
The remaining project = the STRATEGY TRACK REPORT — the meta-churn observation itself is report
material (agent half-life vs meta half-life).**

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★ 2026-08-02 FINAL EXPERIMENT — SCALE IS NOT THE MISSING INGREDIENT. THE MAP IS COMPLETE.
═══════════════════════════════════════════════════════════════════════════════════════════
**v17-big: 34M-param general net (256,8,1024,6,6), trained on Kaggle T4x2 for 30 epochs over the
ALL-DECK BOTH-WINNER corpus (imit_allwins.npz: 15,820 winning sides / 1.24M decisions, every
archetype incl. the #1's M-Kang play). Peak held-out top-1 72.0% (baselines 22.4/32.8). GATE:
policy-vs-policy argmax 45 games vs the 13.9M specialist = 46.7%, tempo 1.89v1.87, comeback
10/22 v 12/23 — IDENTICAL STRENGTH.** 2.4x params + 2x data + ~50x compute bought nothing:
the replay ecology's information ceiling has now been hit from EVERY direction (data quality,
quantity, teachers, features, search, value, phase/matchup/situational targeting, and SCALE).
ALSO: 34M in numpy = ~45s/move → undeployable with search on Kaggle regardless; distillation
would be the route IF the big net had won — it didn't, so moot. Checkpoints kept:
model/az/grimm_imit_v17_best.pth/_np.npz (evidence for the report).
KAGGLE-OPS LAWS (cost ~2 days): CLI `--accelerator` is DECORATIVE (server ignores it) — the
accelerator is set ONLY in the notebook UI (Session options), and EVERY CLI push restarts the
kernel on the stored default (was P100 = torch-unsupported = silent CPU fallback at 5h/epoch);
kernels cannot list themselves as sources (resume via a side checkpoint DATASET; dataset
version updates do NOT restart kernels); dataset processing must complete before first push.
**FINAL STATE: v12 (canonical md5 ef8abd98) IS the agent. The remaining high-value work is the
STRATEGY TRACK REPORT (Sept 13) — this scale-null is a strong chapter: a controlled compute-
scaling experiment with a clean negative is exactly the honest-methodology material the track
rewards — plus 5-min/day maintenance (deck-drift diff vs top-3, M-Kang/Spidops share watch).**

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ 2026-07-30 — META FLIP: NEW #1 = M-KANGASKHAN. Slot2 mystery SOLVED. Field toughening.
═══════════════════════════════════════════════════════════════════════════════════════════
**NEW #1 "James Cox & Henry Chao" @1173: pure M-KANGASKHAN (444/444 games, 61%). Beats
GRIMMSNARL 63% over n=248** (their field is 56% Grimm — their rating is built on beating our
archetype). Their weakness: **CRUSTLE 40% (n=55)** — meta triangle forming: M-Kang > Grimm,
Crustle > M-Kang. Spidops steady ~6%. M-Kang at OUR band still rare (~2% of our games) — the
threat descends from the top if copycats follow. **CONTINGENCY DATA BANKED: his folder contains
~92 winning-Grimm-side games vs M-Kang (the 37% who beat him) — harvest for a targeted fine-tune
ONLY IF M-Kang passes ~10% of our field (v16 lesson: situational boosts can backfire).**
**OUR SLOTS: slot1 (good v12) 943.2** — 58% lifetime, but **43% in the newest window** (field
toughened; top compressed 1209→1173; strong bots multiplying). **Slot2 (fixed-search) 771.9,
MYSTERY SOLVED:** logs pristine (0 stderr, timings = slot1) — no environmental failure. The
mechanism: the FIXED root sweep expands every root child once → wide decisions become 1-eval
VALUE-GREEDY picks that sideline the policy prior; the weak value head can't carry that, while
the broken build's failed sweep accidentally preserved PRIOR-GUIDED UCB. Behavioral, field-only,
invisible to same-handicap local mirrors. LESSON: with a weak value function the policy prior IS
the search's strength — breadth-first "fixes" that dilute the prior are regressions.
**ACTION: replace slot2 with a fresh upload of canonical v12 (md5 ef8abd98...)** — its 772 is a
dead anchor; a fresh climb converges near slot1. Quarantined build stays quarantined.

═══════════════════════════════════════════════════════════════════════════════════════════
# 2026-07-29/30 — MIRROR CLOSED: v15 AND v16 both rejected. THE MIRROR IS NOT IMITATABLE.
═══════════════════════════════════════════════════════════════════════════════════════════
**Mirror facts at n=26 real 1000+ mirrors (V12 combined folders):** record 46%; conversion
(win when taking 1st prize) 69% ≈ Dries' 74% ✓; tempo 1.50 ≈ his 1.58 ✓; **comeback (win after
conceding 1st prize) 23% vs Dries' 62% = THE gap.** New pipeline support built for targeting it:
extract_v2 col 9 = per-decision CURRENT prize diff (NCOL=10, v4 corpora: imit_top_v4/imit_full_v4);
train_imit_v2 --boost-behind-mirror; round_robin PTCG_TEMPO now also prints a COMEBACK KPI.
**v16 (behind-mirror x4 on the 17.3% slice, v11 ckpt, artifact-law build) = GATE-REJECTED:
42.2% overall AND comeback KPI 33% vs control's 50% — the boost taught early urgency (tempo
1.80), not recovery.** With v15 (blanket mirror boost, 44.4%) both mirror-targeted axes are dead:
**comeback skill does not transfer through weighted imitation.** Mirror stays ~46%; the field
cells carry the rating (combined V12: 65.1%, Crustle 9-2, M-Luc 5-0, Archaludon 4-1, Ala 62%).
HOLD CONFIG UNCHANGED: both slots = canonical v12 (md5 ef8abd98...).
SCRAPER: scrape_top3_full.py works (probe maps full histories: Dries 1747/Luca 1096/LiamK 2234
eps) but the REPLAY endpoint rate-limits hard; run-1 fail-fast bug fixed (429 backoff+retry,
paced failures). User stopped the overnight run and scrapes #1 manually instead; 19 Dries files
in ~/Desktop/scraped_top/.

═══════════════════════════════════════════════════════════════════════════════════════════
# ⚠️⚠️ 2026-07-29 NIGHT — ARTIFACT IDENTITY LAW. THE CANONICAL v12 = md5 ef8abd98... ONLY.
═══════════════════════════════════════════════════════════════════════════════════════════
**FIELD RESULT: the ORIGINAL v12 build (with the sweep NameError still in it) = the 1009/1112
agent. The repacked "fixed-search" build COLLAPSED SUB-700 on the ladder** — despite being
locally indistinguishable on every instrument (exec-mode OK, 1.2x per-move time at 1 thread,
full games clean, head-to-heads 48.9%/60%). Cause NOT reproducible locally; to diagnose, get the
sub-700 submission's replays+agent logs (stderr/durations will show it in one look). Until then:
**canonical ship artifact = my-agent/submission_grimm_imit_v12.tar.gz, md5
ef8abd98547decba08c97006d8456452** (copied from the user's Kaggle download); the repack is
quarantined as my-agent/quarantine_v12_fixedsearch_LADDERFAIL.tar.gz — DO NOT UPLOAD IT.
**LAW: never replace a ladder-validated artifact with ANY repack — even a "strength-neutral"
code cleanup — without re-validating ON THE LADDER. The ladder validated the artifact, not the
idea of it. Local instruments have now missed a 300-point defect once.**
**V12 @ ~1009 (peak 1112): 35-25 (58.3%) at the 1000+ band** — Alakazam 67% (30% of field),
tempo rose to 1.53 by itself (deck fix + search fix), **mirror = the weak big cell: 8-11 (42%)
at 32% of field**, losses mostly to PEER-level mirrors. Spidops ~2%, M-Kang 5% — no pivot.
**V14 (early-tempo) = LADDER-REJECTED despite its KPI firing:** stuck at 50% in a LOWER band;
M-Lucario 4-8, Archaludon 1-5 — indiscriminate early aggression feeds prizes into TANKS. Lesson:
a phase-boosted objective needs a MATCHUP CONDITION the objective didn't carry. Slot freed.
**v15 (mirror-weighted fine-tune, --boost-opp=Grimmsnarl x3, Dries/flg mirrors at 12x) =
GATE-REJECTED 44.4% in the DIRECT mirror gate vs v12** (tempo equal). WHY: the corpus is ALREADY
43% mirror — the majority slice was never underweighted, so reweighting adds no information
(v14 worked because early decisions are a MINORITY slice with a measured deficit). Mirror-via-
reweighted-imitation is now CLOSED. Note the honest mirror ceiling: flg wins 57%, Dries 67% —
the mirror is high-variance even for #1s; realistic target from 42% is ~55%, worth ~+15-20 pts.
**CURRENT CONFIG: both slots = v12 (upload submission_grimm_imit_v12.tar.gz twice = two climb
trajectories, leaderboard takes the best). HOLD 1000-1050 = deck-drift diff every few days +
meta watch. Report draft: STRATEGY_TRACK_REPORT_draft.md (fill v12's final number).**

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★★★★★★ 2026-07-29: v14 EARLY-TEMPO FINE-TUNE — local KPI FIRED (ladder verdict above)
═══════════════════════════════════════════════════════════════════════════════════════════
**THE EARLY GAME WAS THE LAST REAL GAP, AND IT MOVED.** Measured on identical code across
1,000+ games: v11 takes **1.31 prizes by T8** vs the #1-class players' **1.61-1.68**, with EQUAL
board development (board@T4 4.14 vs their 3.9-4.6) — setup fine, EARLY CONVERSION slow. (This
also partially explains the weak T1-6 value AUC: our own early play makes positions less decisive.)
**v14 = v11 checkpoint + PHASE-TARGETED fine-tune** (new `--boost-early=3` in train_imit_v2:
turn<=8 decisions x3, on top of top-5-players x4, lr 5e-5, 2 ep; fidelity held at 76.4% MAIN).
**ACCEPTANCE BY MECHANISM, not gate noise** (new: PTCG_TEMPO=1 in round_robin prints per-side
prizes-by-T8): in the 45 gate games **v14 = 1.58 vs v12 = 1.09 — the KPI hit the expert band**;
gate 52.3% = do-no-harm pass. **SHIP `my-agent/submission_grimm_imit_v14.tar.gz`; recommended
slots v14 + v12 (window-matched ladder A/B after ~50-75 games decides which stays).**
v14cand = v14 net + top-3 deck + fixed search, opp-modelling off. This is the ONE candidate of
eight whose mechanism demonstrably fired at expert level — the phase-targeted axis was the only
untried one. If the ladder confirms, the recipe generalises (phase-weighted objectives).

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★★★★★ 2026-07-29: VALUE REFINEMENT NEGATIVE (2 recipes) — EVERY OTHER LEVER MEASURED
═══════════════════════════════════════════════════════════════════════════════════════════
**KL-ANCHORED SELF-PLAY VALUE REFINEMENT: NEGATIVE, twice, cleanly.** Built the full pipeline
(analysis/az_nn/gen_value_selfplay.py — T25 horizon + EXACT margins; train_value_kl.py — KL
policy anchor + save-gate agree>=0.97; validation = our agents' REAL ladder states with real
outcomes: model/az/kilupy_real_v3.npz 18,852 states / kilupy_train+held game-disjoint split).
BASELINE MEASURED (v11 head on real field states): value AUC 0.755 overall — **0.665 at T1-6**
(the phase our losses live in) rising to 0.841 T11+.
  * Run 1 (1,300 games, mirror-heavy 169k states, kl=1): real AUC DEGRADED monotonically
    0.765→0.752→0.736 — mirror outcomes are DRAW-LUCK; fitting luck corrupts the head.
  * Run 2 (cross-net only + real ladder states 3x in training, kl=2, lr=3e-5): degraded again
    0.710→0.698 on clean game-disjoint real held-out. Nothing saved; v11's head stays.
**READ: ~200 own games + 650 cross-net games cannot beat a value prior distilled from ~400k
expert decisions with margin labels — fine-tuning erodes it. And T1-6 AUC ~0.67 is plausibly
near the INTRINSIC predictability limit (draw luck). To retry honestly you would need 10k+
diverse-opponent games (~20h+ generation) with little expected gain.**
**THE COMPLETE MEASURED PICTURE (nothing left unmeasured at this scale):** policy SATURATED
(v8/v9/v11), search SATURATED (48.9% fixed-vs-broken, 54.5% 32-vs-10), value refinement NEGATIVE
at feasible scale, imitation data SPENT (91% self-agreement with a fresh #1 corpus), deck FIXED
(v12). The v11/v12 family ≈ the ceiling of this architecture+data ecology (~910-950-era rating;
#1 sits ~1150-1200, presumably bigger training/arch — kaggle_train_grimm.py exists if the
big-GPU route is ever wanted). **HIGHEST-EV MOVES NOW: (1) the Strategy Track report ($240k,
Sept 13) — the material is exceptional (label-bug forensics, 2x2 objective A/B, calibrated gate,
ladder-as-instrument, SIX gate-killed hypotheses incl. two invalidated-control post-mortems,
saturation proofs); (2) maintenance: deck-drift diff vs top-3 every few days + meta watch
(Spidops trigger 10%); (3) ship v12 (v11 net + top-3 deck + fixed search).**

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★★★★ 2026-07-29 — LADDER VINDICATED v11; v12 = v11 + TOP-3 DECK + FIXED SEARCH. SHIP v12.
═══════════════════════════════════════════════════════════════════════════════════════════
**AUDIT FOUND A 3-GENERATION SEARCH BUG (fixed 2026-07-29):** the root-breadth sweep in
mcts_agent.py called create_node with `your_deck` — UNDEFINED in that scope (param is
`our_deck`); the NameError was swallowed by a bare `except: pass` and the budget spent anyway.
Since v4, EVERY move burned min(ncand,32) of its 32 evals on nothing, and decisions with >=32
candidates got ZERO search (played the first enumerated action — the sweep guaranteed the exact
pathology it was built to fix). Empirically verified: 29 model calls/move before, 33 after.
Second latent bug: final pick broke visit-ties by "first enumerated" (strict <) — now ties break
by mean value. NEVER wrap expansion in a silent except (now counts into IDENT_STATS).
**BUT: fixed-vs-broken A/B = 48.9% (n=45, identical net+deck) — restoring the budget changed
NOTHING.** Together with 32-vs-10 evals = 54.5% and argmax-vs-search(v2 era) = 31/69, the story
is: the first few evals matter, everything beyond saturates — because the VALUE FUNCTION cannot
discriminate between candidate futures. Strongest evidence yet for the value-bottleneck thesis.
ALSO from the audit (unfixed, queued): (a) local gates stop at T14 but ~20% of REAL ladder games
run past T14 (measured end turns up to 35) — raise future gates to ~T25; (b) extract_v2 margin
labels UNDERCOUNT winners 1-2 prizes (read from one seat's stale final view) — fix in the value
retrain; (c) extraction feeds OUR old 60 as the your_deck encoder feature even for expert seats
(they played the new 60) — fix at next re-extraction; (d) minor: identify_opponent doesn't sum
Crustle's two sig ids; build_manifest_folders reads winrates from a moved path (silently empty).
**LADDER RESULTS (user uploaded all three):** v4 918.8 / v6 914.0 / v11 908.5 — but the WHOLE
ladder deflated (~55pts off the top; #1 now 1153.8) so raw scores across eras are NOT comparable.
WINDOW-MATCHED records (same era, from the replay folders): **V11 70.7% (n=75) vs V6 60.7%
(n=28)** — with V11 cells Alakazam **19-2 (90%)** and mirror 9-2 (82%). => v11 IS our best agent;
the feat-2 fidelity gain was real but under the local gate's ±10pp floor. LADDER > GATE for <10pp
effects; the two active slots are a free A/B instrument.
**TOP OF LADDER NOW: #1 Dominic Peel 1153.8, #2 flg 1152.1, #3 LiamK 1150.7.** LiamK profile
(508 games): pure Grimmsnarl, ONE list all 508 games, 61.6%; beats Spidops 70% (n=37); mirror 58%.
**THE DECK FIND: #1 AND #3 RUN OUR EXACT 60 EXCEPT −2 Handheld Fan(1161), +1 Pokégear 3.0(1122),
+1 Tool Scrapper(1137). AND our teachers (Dries, flg, Taichicchi) ALREADY PLAYED THAT LIST** —
the net was trained watching experts use Pokégear/Scrapper and has near-zero expert signal for
the Fans our agents have been drawing. v12 = v11 checkpoint + that 60 (deck/policy MISMATCH
REMOVAL, not a tweak). Gate: 54.5% vs v11 (do-no-harm PASS). **SHIP
`my-agent/submission_grimm_imit_v12.tar.gz`** — recommended slots: v12 + v11 (drop v6).
META @1100+: Grimm 54%, Alakazam 29%, **Spidops settled ~7%** (below the 10% pivot trigger;
LiamK beats it 70% — Grimm handles it). M-Lucario resurged in v11's window (17% share, our
softest cell at 54%). LiamK adds nothing as a teacher (61.6% ~ corpus level; v9 law holds).

**★★★ THE SESSION'S FINAL FINDING: TOP-1 FIDELITY != STRENGTH; THE VALUE HEAD IS THE BOTTLENECK.**
NEW TOOL `analysis/disagree_dries.py` — replays our policy against every decision the #1 player
faced and classifies the disagreements. Result (150 Dries games, 12,662 decisions, 63.7% raw
agreement): the worst classes are ATTACH 73.3% disagree and RETREAT 75.4%, but splitting them by
whether the model COULD SEE the difference:
    CARD    42.1% BLIND   ATTACH 40.8% BLIND   ABILITY 20%   EVOLVE 16%
    RETREAT 0% blind      ATTACK 0%            PLAY 0.6%     END 0%    (= genuine judgement)
So we grafted the feat-2 positional block onto v6 (`analysis/az_nn/graft_feat2.py`, preserves all
weights + 36 new rows, low-LR fine-tune = exactly the retry v5's post-mortem prescribed). It did
what it was meant to: strict top-1 **73.9% -> 75.8%**, tie-gap 13pts -> 2.9pts, feat=2 verified
live in the packed agent. GATE: **51.1% vs v6 (with search), 53.5% vs v6 (search OFF)** -> v11
NOT SHIPPED. A real fidelity gain bought ZERO strength at both the full-agent AND pure-policy
level. Mechanism: byte-identical candidates are usually NEAR-EQUIVALENT candidates — agreement
weights all decisions equally, the game only cares about the few that swing it.
**=> SIX consecutive rejections (endgame blend / v8 peer data / v9 #1-player data / v10 opponent
modelling / v11 features / deeper search) vs the ONE value-head change (v4 margin targets) that
bought +135. THE POLICY IS SATURATED; THE VALUE FUNCTION IS THE BINDING CONSTRAINT.**
**NEXT (and last) LEVER: KL-anchored self-play value refinement** — the value head only ever saw
EXPERT-visited states and extrapolates everywhere our play diverges; generate value targets on
states OUR agent reaches, anchored to the imitation policy so self-play cannot drag the weights
off the experts (the documented past failure). Do NOT spend more on imitation data, candidate
features, or search heuristics — all three are now measured dead ends.

**⚠️ CORRECTION — THE v10 VERDICT BELOW IS INVALID (found 2026-07-27 late).** mcts_agent.py
loaded opp_decks.json via a repo-relative fallback, so the v10 "control" (built by deleting the
agent's own copy) STILL had opponent modelling on: the A/B compared two identical agents and its
42.2% was noise. Fallback removed — an agent dir is now self-contained (its own opp_decks.json
is the on/off switch). The two arguably-valid cells both used v6cand, which predates the feature:
**v10cand 51.1% and v10ctl 63.6% vs v6cand — averaging ~57%, i.e. MILDLY POSITIVE, not negative.**
OPPONENT MODELLING IS UNRESOLVED AND WORTH A CLEAN RE-RUN (with an assert that the control really
has the feature off). The "we fixed the deck, the gap is the opponent's POLICY" reasoning below
is still a good hypothesis but is NOT evidence-backed.

**★ LEVER 1 (opponent modelling) GATE-REJECTED — AND IT DIAGNOSES THE REAL BLOCKER (2026-07-27).**
Built it properly: `mcts_agent.identify_opponent()` reads the opponent's archetype off their
VISIBLE cards (in-play + discard) and determinizes their hidden zones from that archetype's real
60 (`model/opp_decks.json`, modal lists from 2,027 replays; Grimm 71% / Archaludon 79% /
M-Kangaskhan 73% representative). Identification VERIFIED on real ladder states: **71.3% correct,
1.8% wrong, 26.8% safe-abstain**; fire-rate 0% at T0-2 (correctly silent), 74% by T4, ~100% from
T9. Clean A/B (identical weights/search; only difference = presence of opp_decks.json):
**42.2% vs its own control**, 51.1% vs v6 -> NOT SHIPPED (kept in tree; delete opp_decks.json
from an agent dir to disable).
**WHY IT FAILED — the useful part:** in the search, the OPPONENT'S MOVES ARE CHOSEN BY OUR OWN
POLICY NET, which was trained exclusively on Grimmsnarl-side decisions. Handing it a real
Alakazam/Archaludon deck asks it to pilot an archetype it has never seen — so the change swapped
a harmless-but-predictable simulated opponent for a dangerous-but-ERRATIC one. **We fixed the
opponent's DECK when the gap is the opponent's POLICY.**
**=> THE NEXT LEVER (1b), and the data already exists:** every replay has TWO sides and
`build_manifest_folders.py` hard-filters `TARGET='Grimmsnarl'`, discarding the opponent's ~13,008
side-games (Alakazam/Archaludon/Crustle/... piloted by the same ladder population). Train a
GENERAL multi-archetype policy/value net on both sides, then let the search use it to pilot the
opponent. That is the only version of opponent modelling that can work — and it may improve the
Grimm pilot too (more data + general TCG structure). Extraction needs a `--any-deck` manifest
mode; everything else in the pipeline is deck-agnostic already.
**FOUR CONSECUTIVE REJECTIONS (endgame blend, v8 peer data, v9 #1-player data, v10 opponent
modelling) — v6 is at a local optimum for this architecture; incremental tweaks are exhausted.**

**⚠️ META WATCH — flg ABANDONED GRIMMSNARL FOR "TEAM ROCKET SPIDOPS" (2026-07-27, 2h old).**
flg (was #1 with Grimmsnarl at 65.2%) uploaded a NEW agent on a COMPLETELY DIFFERENT deck and is
already **#2 @1196.0** (#1 Dries still Grimmsnarl @1209.4). The 60 (from ~/Desktop/flg_new, all
30 games identical list): 4x TR Tarountula(400) / 4x TR Spidops(401,130hp) / 2x TR Mewtwo
ex(431,280hp) / 3x TR Mimikyu(434) / 2x TR Articuno(414) / 4x TR Transceiver(1134) / 4x Poké
Pad(1152) / 4x TR Ariana(1216) / 4x TR Proton(1220) / 3x Bug Catching Set(1094) / 3x TR
Giovanni(1218) / 3x Lillie's Determination(1227) / 3x TR Factory(1257) / 2x Buddy-Buddy
Poffin(1086) / 1x Ultra Ball(1121) / 1x Hero's Cape(1159) / 1x Brave Bangle(1175) / 1x TR
Archer(1217) / 4x TR Energy(15) / 7x Basic{G}(1).
RESULTS: 25-5 (83.3%) overall; **7-2 (78%) vs GRIMMSNARL — our deck**. Climb-bias checked and
it is NOT the explanation: first 15 games 87%, last 15 **80%** (still likely climbing at 2h).
OUR EXPOSURE: v6 has faced it **twice, ever (1-1)** — it sits inside the "other" bucket; we have
ZERO training data for the matchup.
**ASSESSMENT: do NOT pivot decks yet** — #1 is still Grimmsnarl and above him, n=30, and we could
not train a Spidops pilot anyway (from-scratch needed ~9.6k games; we have 30). **DO track it:**
re-scrape flg_new in 1-2 days (and watch for copycats). Decision trigger = Spidops passing ~10%
of our ladder field OR taking #1. The pipeline is deck-agnostic, so a pivot is mechanically cheap
IF the teacher data ever exists — the blocker is data, not tooling.

**★★ v9 GATE-REJECTED = IMITATION HAS CONVERGED (2026-07-27) — READ THIS BEFORE SCRAPING MORE.**
Fine-tuned v6 on **Dries @ Tufa Labs, the CURRENT #1 (1201.8; 449 Grimm games, 63.7%, mirror
67%/n196)** — a strictly better teacher than flg and 250 rating points above us. Best fidelity
ever: MAIN 82.3% / all 88.1% / strict 75.8%. GATE: **51.2% vs v6**, 50.0% vs v4 -> NOT SHIPPED.
DECISIVE DIAGNOSTIC: v6 and v9 agree on **91.1% of 1,500 real decision points** — the fine-tune
moved ~9% of moves and they cancelled out. v6 had already converged on the top-player policy.
=> **We copy the #1's moves ~82% of the time and are still 250 points weaker, so the remaining
gap is not a "which move" problem and MORE EXPERT DATA WILL NOT CLOSE IT.** (flg gave +50 while
the policy was still unconverged; Dries gave 0.) Corpora/manifests kept: grimm_dries_manifest.csv,
model/az/imit_dries.npz (38,589 decisions) — reusable if we ever retrain from scratch.
**NEXT LEVERS ARE NON-IMITATION, ranked:**
 1. **Opponent modelling in search (best-motivated).** `mcts_agent.determinize_for_search` still
    fills a ladder opponent's hidden deck/hand/prizes with FILLER_BASIC Snorlax + basic energy,
    so every simulated opponent reply in the search is nonsense. Mid-game we CAN identify their
    archetype from visible cards (ARCH table in analysis/digest.py) and determinize with that
    archetype's real 60 (we have decklists for every archetype in the replay corpora).
 2. Deeper search — 32 evals costs ~50s of the 600s budget (~11x headroom).
 3. Value refinement / self-play on states our own agent reaches (KL-anchored to the imitation
    policy so it cannot drift off the experts).

**v8 GATE-REJECTED + THE DATA-SOURCING LAW (2026-07-27):** built 284 NEW Grimm games —
Eggplanck (135 @ 56.3%, rank 201/948) + the new **OPPONENT-HARVEST** (149 winning Grimmsnarl
sides pulled from 70 mixed pilots across ALL 8 replay folders, incl. 14 vs Archaludon; script
pattern in the session log, manifests `grimm_eggplanck_manifest.csv` / `grimm_harvest_new.csv`,
corpus `model/az/imit_fresh284.npz`). Fine-tuned v6 -> v8: fidelity ROSE (MAIN 80.5->81.2%) but
gate **53.3% vs v6** (pre-registered bar >=60%) and 56.8% vs v4 where v6 scored 71.1%. NOT
SHIPPED; **v6 remains champion**. LAW: teacher QUALITY dominates volume — flg (rank #1, 65.2%,
316 games) bought +50 rating; 284 games of PEER-level play (Eggplanck is rated 948 vs our 950)
bought nothing. **Only scrape pilots ABOVE us: rank <~150 / rating 1000+.**
ALSO: PLAYERS SWITCH DECKS — tonakaiiii (4,689 Grimm games in the July index) now pilots CRUSTLE
(117/117, 58.1%); haggle (191 Grimm) now pilots ALAKAZAM (47/47, 63.8%). The index winrates are
historical + deck-specific — verify the CURRENT deck from recent replays before scraping.
Confirmed non-issues this round: Grimm-vs-Alakazam is ~50/50 at rating 1000 (haggle 50% over
n=14) while we run 60% — that cell is a STRENGTH. All replay folders now live INSIDE the repo.

**v6 AUTOPSY (48 games @ ~950) — 2026-07-27:** field 25-23 (52.1%) — LOWER than v4's 66.7% but
50 rating HIGHER: a ladder equilibrates at ~50%, so FIELD WIN RATE IS NOT A PROGRESS METRIC; use
head-to-head gates + rating only. **MIRROR FIXED by the flg fine-tune: 33% (2-4) -> 75% (6-2)** —
targeted teacher data fixes targeted cells (the session's most reusable result). Loss shape:
8/23 losses we NEVER LED (setup races); from -3 prizes we are **0-for-13**; blowouts 35%.
Live field @950: Alakazam 31% (60%), Grimm 17% (75%), Archaludon 17% (38%), Crustle 8%.
**TWO FIXES REJECTED BEFORE SHIPPING (both would have been do-harm):**
 * fresh-full-HP-GrimmEX promotion gate — killed by the EXPERT-RATE CHECK: flg does it MORE in
   games he WINS (0.20/g) than we do (0.12/g); it is a losing SYMPTOM, not a bug. **New standard
   pre-check: before ruling on any loss pattern, measure the expert's rate for the same pattern.**
 * endgame/buzzer value blend — 51.1% vs its own control (see below).
**ARCHALUDON SCARE = NOISE.** Our "worst cell 3-5 (38%)" was n=8. James Christian (pure
Archaludon specialist, 389 games, 48.1% WR, rated 600-910) wins **52% vs Grimmsnarl (n=29)** —
i.e. the matchup is ~50/50 from 3.6x more data. Built `my-agent/bc_archaludon` +
`model/bc_archaludon.joblib` (bc_train.py on his 389 games, 55.6% agreement) to measure it
properly — but v6 beats the clone **93.3%**: BC clones are too weak to discriminate (known
project law re-confirmed). Clone kept as a gauntlet member only. NET: no Archaludon problem;
the coverage gap (17% live vs 0.3% of corpus) is an optimization, not a hole.

**v4 AUTOPSY (55 games @ ~900) + v7 EXPERIMENT (rejected) — 2026-07-27:**
FIELD 36-18 (66.7%, was 56.9%). ALL v4 FIXES VERIFIED FIRED: behind-recovery 34-41%→**61%**
(expert band 57-64%), prize slope T8→T13 +0.36→**+2.13** (experts +1.88), prizes-by-T8
1.08→1.46, BLOWOUT losses 64%→22%, 0 timeouts (worst 54.5s/600s at 32 evals = 11x headroom).
META MOVED: M-Lucario 31%→7% of field (2-2, no longer the problem); M-Kangaskhan ABSENT at ~900
(only as tech in Crustle shells — it's a flg-band threat); now Alakazam 30% (11-5), Archaludon
20% (7-4), Crustle 15% (7-1). **NEW WORST CELL = the Grimmsnarl MIRROR 2-4 (33%, n=6, noisy).**
ENDGAME PROFILE: 78% of games end at the buzzer; 44% of losses decided by ≤1 prize (3 at an
exact tie). STILL UNFIXED across v2→v4: fresh-full-HP-GrimmEX promoted then OHKO'd — 6 occurrences
in 5 losses vs 1 in 36 wins, and those losses are CLOSE (margins -1..-3) = the best remaining
ruleable do-no-harm target.
**v7 endgame-blend (search leaf value → prize margin, turn-ramped) = GATE-REJECTED**: 51.1% vs
its own control; disabled via ENDGAME_W=0 default in mcts_agent.py (code + rationale kept).
Reason it can't work: encoder already feeds turn/10 and v4+ value heads train on margin-shaped
targets (buzzer awareness ALREADY learned — that IS the behind-recovery win), plus at this depth
the margin is near-constant across root candidates and cancels in the argmax.
**GATE NOISE CALIBRATED: ±10pp at N=45 even between IDENTICAL agents (v6 71.1% / v7ctl 60.0% vs
the same v4). Trust only ~70/30-scale deltas; judge a change by its DIRECT A/B vs its own
control, never by comparing two agents against a third.**

**LADDER UPDATE: v4 stable ~890-900 (peak 909); v6 ~950 (peak 957) — the 71.1% gate PREDICTED
~950+, making the local gate 3-for-3 as a ladder predictor (v2 760 → v4 895 → v6 950; two
sessions ago the best was 617). Gap to #40 imitation bot (1035): ~85 pts; top ≈ 1130. At this
altitude opposition = other strong bots and the MIRROR decides; next levers = v6 replay autopsy
(M-Kangaskhan + mirror + behind-recovery), fresh flg batches, mirror-targeted fine-tune
(flg's 156 mirror games), then KL-anchored self-play.**
**User provided 316 replays of the #1 player "flg" (~/Desktop/flg): ALL Grimmsnarl, 65.2% WR
(mirror 57%/n156, Alakazam 71%/n45, M-Kangaskhan 53%/n47 — NOTE M-KANGASKHAN NOW 15% of the #1's
opposition = NEW META THREAT, was ~4%). Built grimm_flg_manifest.csv (wr hand-set 0.652) →
model/az/imit_flg.npz (25,948 decisions, feat=1).**

**v6 = v4 checkpoint fine-tuned on flg+main corpus (--init=t3v, --boost-players flg+top3 x3,
lr 1e-4, 3 ep, margin value). Trainer got GLOBAL PLAYER-ID NAMESPACING across multi-file corpora
(load() remaps pids — without it a boost name in file A boosts an unrelated pid in file B).
GATE: v6 71.1% vs v4, 86.7% vs v17 (N=45) — THIRD consecutive ~70/30 tier (v2→v4→v6).
SHIP `my-agent/submission_grimm_imit_v6.tar.gz` (27.5MB, exec-mode verified). Checkpoint:
grimm_imit_v6_best.pth (held-out MAIN 80.4% on the flg-mixed split).**

Ladder KPIs for v6: overall vs v4's read; the M-Kangaskhan cell (new threat, flg's hardest at
53%); mirror rate (half of top-table games). The flg corpus is also the mirror-play goldmine
(156 #1-player mirror games) for any future mirror-targeted fine-tune.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★★ EARLIER (2026-07-27 evening) — v4 was CURRENT BEST; v5 experiment REJECTED
═══════════════════════════════════════════════════════════════════════════════════════════
**v4 is LIVE (user uploaded submission_grimm_imit_v4.tar.gz). Await its ladder read; when the
user drops a folder of v4's replays, autopsy (M-Lucario cell FIRST — was 6-10, 31% of field).**

**v5 EXPERIMENT = GATE-REJECTED (documented negative, in memory too):** representation-v2
positional candidate features (--feat=2; tie collisions 0.90→0.20/dec) + d=192/22M from scratch:
strict fidelity UP (73.6% vs 70.3%) but **26.7% vs v4** head-to-head (66.7% vs v17; v4 71.1%).
Fidelity != strength; the v4 lineage's staged curriculum matters. Machinery kept (extract_v2
--feat=2 reads the day-dump ZIP `20260722:23:24.zip` directly; imit_full_v3.npz on disk). If
revisited: graft feat-2 onto the v4 checkpoint (extend decoder-embedding rows, low-LR), NOT
from-scratch. NOTE: user MOVED (not deleted) the player folders + manifests INTO the repo root.

**NEXT LEVERS (ranked): (1) v4 ladder autopsy → targeted fix (M-Lucario promotion mask if the
cell is still red); (2) KL-anchored AZ-style self-play fine-tune of v4's value/policy on
self-visited states (the principled drift fix); (3) Strategy-Track report drafting ($240k,
Sept 13) — the v2→v4→v5 gate-driven arc + the label-bug forensics is the originality story.**

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★★ EARLIER (2026-07-27) — v2 LIVE @ ~760 STABLE (best ever); v4 shipped
═══════════════════════════════════════════════════════════════════════════════════════════
**LADDER VERDICT on grimm_imit_v2_np_mcts: peak 799, STABLE ~760 — first agent ever stable in
the 700s.** 53-game autopsy (4-agent workflow, all confirmed): (1) STYLE TRANSFER PROVEN —
engine KPI dead-match (Adrena fires 5.35/g vs experts 5.34; Munkidori energized 89% vs 90%;
rules v11 was ~2/53%); (2) health CLEAN (0 errors, <0.6% fallback bound, 30s/600s worst clock);
(3) losses: M-Lucario 6-10 (experts 13-6) + Archaludon 5-5 (experts 15-1) = 15/23 losses, 64%
blowouts (v19 was 47% close — inverted); killer pattern = FRESH full-HP GrimmEX promoted after
KO then OHKO'd (8x: 7 in losses, 0 in wins); chipped-GrimmEX feeds are FINE (expert plan);
(4) drift = BEHIND-RECOVERY: from -1/-2 experts win 57-64%, we won 34-41% (slope +1.88 vs
+0.36 prizes T8→T13) — value head's coarse ±1 labels; (5) ctx=7 deck-search first-option
collapse 40.2% vs experts 13.2%; (6) one loss WHILE AHEAD to episode runTimeout.

**grimm_imit_v4 = all fixes: SHIP `my-agent/submission_grimm_imit_v4.tar.gz` (27.5MB).**
v4 = t3-boosted policy (top-3 players x3, --boost-players) + margin-shaped value head
(--value-lambda=0.4 --value-weight=0.6; targets behind-recovery) + root-breadth-first sweep in
mcts_agent.py + search=32 (A/B: 32>10 by 54.5%) + episode time guard in main template.
GATE: **73.3% vs the live 760-champion, 73.3% vs v17 (N=45 each)** — a full tier above live.
Checkpoints: grimm_imit_v2t3_best.pth (policy) → grimm_imit_v2t3v_best.pth (=v4, +margin value).
NOT yet done: M-Lucario promotion gate (item #3 — held per do-no-harm until v4's ladder read
shows whether learning fixed the cell), ctx=7-targeted training, MC-rollout value targets
(stage 2 if behind-recovery persists). NOTE: user DELETED the Desktop replay folders
(Taichicchi/Dominic Peel/Luca/V18/V19) — their decisions live on in model/az/imit_full_v2.npz;
fresh replays can no longer be re-extracted. Ladder KPIs for v4: M-Lucario cell, prizes-by-T8
(was 1.08, target ≥1.3), comeback slope, cap-tie losses (was 4).

═══════════════════════════════════════════════════════════════════════════════════════════
# ★★ EARLIER (2026-07-26 afternoon) — THE IMITATION BREAKTHROUGH
═══════════════════════════════════════════════════════════════════════════════════════════
Memory updated: **ptcg-imitation-architecture** (CORRECTED — the morning block below is
SUPERSEDED where it blames the "73k action space").

**THE FINDING: the 29% imitation plateau was TWO PIPELINE BUGS, not an architecture ceiling.**
 1. **Replay off-by-one:** a seat's action is stored in the NEXT step's entry, not beside the
    observation it answers. v1 extract_manifest.py mislabeled ALL 377k samples. (Verified: option
    legality 99.9% next-step vs 72.2% same-step; replaying our own v19 on its own games matches
    next-step 78.3% vs 22.4%.)
 2. **Degenerate loss:** tanh + Huber-to-±1 regression saturates at "everything is -1"; replaced
    with masked softmax CE. Plus **tie-aware CE**: 60.7% of decisions contain byte-identical
    candidate encodings (decoder features carry no board position), so the expert's whole
    indistinguishable group is credited (-log sum-p). 2x2 A/B: 30.5% -> 60%+ on 1% of the data.

**RESULT (grimm_imit_v2, trained ~75 min on MPS):** 1.02M corrected decisions (9,603 games incl.
415 fresh Taichicchi/Dominic-Peel/Luca games), filtered to >=0.55-wr pilots = 422k, quality-
weighted, model 128,8,512,4,4. Held-out (game-disjoint): **MAIN top-1 77.4%, all 83.4%, top3
96.7%** (baselines: random 24.8% / always-first 29.8%). ROUND-ROBIN (N=45/pair):
  **grimm_imit_v2_mcts (search=10) 73.3% avg — beats EVERYTHING**: v17 73.3%, v19 68.9%,
  bc_crustle 66.7% (v17 scores 33.3% there — the Crustle wall BROKEN), bc_yushin 88.9%.
  Pure-argmax variant 59.6% avg (53.3% vs v17) — first learned Grimm above v17. v17=50.3%, v19=47.0%.
Latency: ~30ms/move local incl. search — no Kaggle timing risk. Tarballs are ~53MB (model.pth
55MB) — if Kaggle rejects on size, re-save weights fp16.

**SHIP: `my-agent/submission_grimm_imit_v2_np_mcts.tar.gz`** (27.5MB, NUMPY backend — the one to
upload; argmax fallback: submission_grimm_imit_v2_np.tar.gz). The first (torch) upload FAILED
Kaggle validation: the sandbox execs main.py with NO `__file__` defined -> NameError at import
(the proven agents guard it; the generated main.py didn't). Fixed via _base() resolver
(try/except __file__ -> /kaggle_simulations/agent -> cwd) AND de-risked torch entirely: pure-
numpy inference port (analysis/az_nn/np_common.py NpModel + export_numpy.py exporter, validated
300/300 argmax-identical to torch, fp16). np_mcts sanity: 83.3% vs v17 (n=12); exec-mode (no
__file__) tested locally. Ladder KPIs: overall vs v17's 802 peak; the Crustle + Alakazam cells;
within-1-prize loss rate.

**TOOLING (v2 pipeline, replaces v1):** analysis/az_nn/{build_manifest_folders,extract_v2,
train_imit_v2,build_agent_v2}.py + analysis/rr_pairs.sh (crash-isolated round-robin driver;
NOTE: torch+sklearn in one process segfaults on libomp — export KMP_DUPLICATE_LIB_OK=TRUE).
Corpus: model/az/imit_full_v2.npz (1.45GB) + .tiemask.npy cache. Manifests:
~/Desktop/grimm_train_manifest_fixed.csv (day-dump paths repaired) + grimm_new415_manifest.csv.
model/az/grimm_imitation.pkl (718MB) is now KNOWN-BAD (mislabeled) — safe to delete.

**NEXT LEVERS (ranked):** (a) upload + read ladder; (b) re-extract with dedupe at inference +
richer candidate tokens (11.5% of decisions hide a REAL board difference behind identical
encodings — the remaining representation gap); (c) raise search_count (30ms/move leaves huge
headroom); (d) fine-tune on the specific ladder losses the ladder reveals; (e) same v2 pipeline
for Alakazam/Dipplin decks. V18/V19 ladder-loss autopsy (engine-uptime KPI) still UNDONE.

═══════════════════════════════════════════════════════════════════════════════════════════
# ★ EARLIER 07-26 SESSION (morning) — partly SUPERSEDED by the block above
═══════════════════════════════════════════════════════════════════════════════════════════
New memory this session: **ptcg-imitation-architecture** (the big finding), ptcg-top40-recipe,
ptcg-grimm-exposure-fix, ptcg-starmie-autopsy, ptcg-deeper-search-wall; updated ptcg-dipplin-structural.
Also **STRATEGY.md** (root) = the written strategy.

**1. CURRENT SHIPPABLE = grimmsnarl_v19** (uploaded, live publicScore ~621; `submission_grimmsnarl_v19.tar.gz`).
   v19 = v17 + prize-exposure retreat (mirror-gated) + observed-OHKO signal — do-no-harm VERIFIED by
   fire-counts; targets Alakazam (our worst high-meta cell). v17 kept PRISTINE. Fix#3 (KO-routing) TRIED
   + REVERTED (hurt Starmie). Fix#2 (engine uptime) not built (worked-over). Ladder KPIs to watch:
   within-1-prize loss rate (was 47%) + the Alakazam cell.

**2. META SHIFTED (13,621 real games, 07-22/23/24):** Grimmsnarl **54% and RISING**, Alakazam 21%,
   Crustle 8%; **M-Starmie & M-Lucario VANISHED (<1%)** — much of this session's Starmie/M-Lucario work
   targeted LOWER-bracket threats absent at top. Deck-EV: **Dipplin 58.5%** (best, hard-counters the field)
   but only 1.5% of meta = DATA-STARVED for imitation; **Grimmsnarl 51%** = data-rich + dominant + mirror
   is half your games. => train the MAIN checkpoint on GRIMMSNARL; Dipplin = pocket counter if feedable.

**3. ★ THE BIG FINDING — imitation-at-scale STILL fails; culprit = ACTION REPRESENTATION (not data).**
   Built the full imitation pipeline the #40 player uses: `~/Desktop/grimm_train_manifest.csv` (9,188
   top-player Grimm games, W+L, side-labeled) → `extract_manifest.py` → `model/az/grimm_imitation.pkl`
   (377k decisions, 6.2x prior) → `pretrain_imitation.py` (PURE imitation, model 128,8,512,4,4). RESULT:
   top-1 fidelity PLATEAUS ~29% (6x data didn't help), agent `my-agent/grimm_imit` loses to v17 (20% mcts
   / 4% pure-argmax). NOT data, NOT self-play — the reference **73,847-token combo-decoder** caps fidelity;
   29%/move compounds into a weak agent. #40's 1035 is impossible at 29% → HIS arch reaches higher fidelity
   = almost certainly a **factored/smaller action space**. Also we trained MAIN-only (train all select types
   next). **DATA PIPELINE IS DONE + REUSABLE for any new model.** See [[ptcg-imitation-architecture]].

**NEXT STEPS (ranked):** (a) SHIP is done (v19 live) — read the ladder. (b) **Fix the imitation
   ARCHITECTURE** — get #40's action encoding (fastest), else re-architect the action head (factored,
   smaller) + train on all decision types; the 377k corpus is ready. (c) More scraping WON'T fix the agent
   (bottleneck is architecture); `top200_scraper.py` scripts incremental pulls (~44 recent/player API limit).
   (d) Rules track: v19 shipped; further rules gains are below the noise floor / value-search ceiling.
   Cleanup done: my-agent/ tidied, old versions in my-agent/_archive/.

═══════════════════════════════════════════════════════════════════════════════════════════

# PTCG AI Battle — MASTER HANDOFF (2026-07-24, the RL-PIVOT session)

New session: read THIS first, then the memory files (auto-recalled). Key memory:
**ptcg-rl-system** (the learned agents — the current front), **ptcg-scoring-and-meta** (how the
ladder scores + strategy), ptcg-realistic-validator, ptcg-alakazam-program, ptcg-grimm-engine-gap.
Team "Kilupy". Deadlines: sim track (pokemon-tcg-ai-battle) **Aug 16** = Knowledge/no-cash; the
REAL prize = **Strategy Track** (pokemon-tcg-ai-battle-challenge-strategy) **$240k, top-8/234,
Sept 13**, judged on sim results + a technical report on originality/ingenuity. userHasEntered=True
on both. VERIFY the entry is submitted.

════════════════════════════════════════════════════════════════════════════
## 0. THE BIG PIVOT THIS SESSION: RULES PLATEAUED → RL WORKS, CLIMBS, IS STEERABLE
════════════════════════════════════════════════════════════════════════════
Weeks of hand-written rules plateaued (Ala v20 peak **739**, Grimm v17 peak **802**). The gap to
the top (~1130) is decision quality rules can't express. We BUILT a from-scratch AlphaZero-lite
learned-agent system and it is BEATING our own rules and CLIMBING each iteration:
- **az0** (iter0): first LEARNED agent to beat the rules on the round-robin validator.
- **az1p** (iter1, done right): LIVE Kaggle peak **791** (best Ala ever, +52 over v20), 52% live
  (first Ala above break-even), FIXED THE ALA MIRROR (2-1 live vs the chronic 0-3), beats Crustle.
- **az2** (iter2): beats az1p 60% head-to-head; we weighted M-Lucario in the stable → az2 beats
  M-Lucario 55.6% (up from az1p's live 42%). The loop is STEERABLE at named weaknesses.
=> This is now the main thrust. Rule-tweaking is a dead end (documented, don't restart it).

════════════════════════════════════════════════════════════════════════════
## 1. CURRENT BEST AGENTS + UPLOAD STATE
════════════════════════════════════════════════════════════════════════════
- **Alakazam (learned): az2 = CURRENT BEST**, packed `my-agent/submission_alakazam_az2.tar.gz`.
  Lineage az0 → az1p (live 791) → az2. az1p is live on Kaggle (peaked 791). az2 not yet uploaded.
- Alakazam (rules): v20 (peak 739) — the strong-rules baseline; DON'T tune further.
- **Grimmsnarl: v17 = BEST** (peak 802). v21/v22 REGRESSED to 657-705 (local gates lied) — if a
  Grimm is live, it should be v17 (`submission_grimmsnarl_v17.tar.gz`). No learned Grimm yet.
- SCORING (verified): leaderboard = your best ACTIVE sub; ~2 most-recent stay active; ratings
  CONVERGE IN <1 HOUR (Praxel hit rank5/1137 on a 42-min-old sub). Use GAME-HISTORY PEAKS, NOT the
  CLI publicScore (a lagging snapshot). Each upload resets that sub to ~600 and re-climbs in ~1h,
  so the ladder is a FAST A/B tool (5 uploads/day). Churn ≠ costly; agent QUALITY is everything.

════════════════════════════════════════════════════════════════════════════
## 2. THE RL SYSTEM — HOW TO RUN AN ITERATION (the core ongoing loop)
════════════════════════════════════════════════════════════════════════════
Tools in analysis/ (all built this session): gen_selfplay.py (mirror self-play w/ policy+value
targets), gen_value_vs_stable.py (value data vs a stable), **gen_policy_iter.py** (THE iterator:
plays the current agent vs a clean stable, records its SEARCH PICKS as policy targets), train_az.py,
**round_robin.py** (THE validator — correlates with Kaggle per the top-team method), field_eval_realistic.py.
Agent = my-agent/alakazam_az0 body: `choose_main_az` = POLICY net narrows top-K candidates, VALUE
net 1-ply-searches them; PHASE GATE (AZ_GATE=4, baked): rules for setup, learned search for endgame.
Kaggle-safe (rule fallback). Nets: HistGradientBoosting (CPU-fast). Features: bc_features + bc_vocab
(deck-agnostic, in each agent dir). Persistent data/nets: model/az/*.npz + *_value/policy.joblib.
Stables (PERSISTED): model/az/stable_clean.txt (11 strong opps, no weak clones),
model/az/stable_iter2.txt (M-Luc 2x weighted). Held-out validators: gauntlet/okidogi, bc_yushin, bc_bono.

**ONE ITERATION (az2 → az3), copy-paste recipe:**
```
# 1) DATA: current best vs the stable (weight the LIVE weakness deck 2x in the .txt)
python3 analysis/gen_policy_iter.py my-agent/alakazam_az2 220 model/az/ala_iter3.npz 6 @model/az/stable_iter2.txt
# 2) TRAIN: value on ALL iters (coverage) + policy on the NEW iter (search picks). Inline pattern:
#    Xs=concat(iter0,iter1_proper,iter2,iter3 .npz 'Xs'); ys=concat(...'ys'); HistGB.fit -> ala_iter3_value.joblib
#    Xo,yo = iter3 'Xo','yo'; HistGB(max_depth=None).fit -> ala_iter3_policy.joblib   (see the iter2 cmd in journal)
# 3) BUILD: cp -r my-agent/alakazam_az0 my-agent/alakazam_az3; swap in value_net.joblib + policy_net.joblib
# 4) MEASURE: python3 analysis/round_robin.py 45 my-agent/alakazam_az3 my-agent/alakazam_az2 \
#      my-agent/alakazam_v20 <live-weakness deck> my-agent/gauntlet/okidogi my-agent/bc_yushin my-agent/gauntlet/crustle
#    Look for: az3 beats az2 head-to-head + improved on the targeted matchup. Then pack + (user) upload.
```
CAVEATS/LAWS: az agents are STOCHASTIC (determinization RNG) → single matchups swing ±several pp;
trust HEAD-TO-HEAD + avg over the panel, N>=45. RL is fits-and-starts (non-monotonic) — a bad
iteration ≠ failure; keep the best, re-roll. Include HELD-OUT agents in the round-robin (honest
generalization). Keep the stable STRONG (no weak clones — they distort the value signal; that broke
iter1's first attempt). gen_policy_iter is slow (the agent searches) — ~220 games is a good batch.

════════════════════════════════════════════════════════════════════════════
## 3. STRATEGY, META, LAWS (durable)
════════════════════════════════════════════════════════════════════════════
- Decks are SOLVED: our Ala = 60/60 the current #2/#3 (Majkel/213tubo); our Grimm 58/60 the #1
  (Luca). Top-3 run OUR decks → the gap is 100% PILOTING → RL is the only lever. Don't hunt decks.
- Meta (top-table): Alakazam dominant (~38%), Crustle SURGING (~25%, crushes Grimm), Grimm fading.
  Our bracket (~600-800) is M-Lucario-heavy (~19%, vs 2% top-table) — a live weakness to target.
- VALIDATION LOOP: local round-robin vs the clean stable (coarse, correlates w/ Kaggle "usually,
  not always" — "walls" = low-rated counter-decks) → fast ladder (~1h) = final truth. The old
  self-play-field proxy LIED (ranked Ala v13<v15 backwards); the round-robin/realistic-clone method
  fixed it. Distrust single-opponent mirror gates.
- Adjudication: ladder stops ~T14, PRIZE LEADER wins, DECKOUT=loss, deck breaks ties. All training
  targets + harness_adj.py use this. NEVER deck out while ahead.
- LAWS: replay action ints are engine-canonical (never decode; state-diffs/logs only); type15
  attacks log only in the DEFENDER view; deck.csv newline-separated; verify-fix-fires + 2-runs
  before believing a delta; proxies lie in absolutes (trust deltas + the ladder).

════════════════════════════════════════════════════════════════════════════
## 4. IMMEDIATE NEXT (ranked)
════════════════════════════════════════════════════════════════════════════
1. **Crank iteration 3+** (recipe §2): az2 → az3 → ... Get az2's LIVE weakness (scrape/user screenshot),
   weight that deck in the stable, iterate. This is the main climb.
2. **Upload az2** for a real Kaggle peak (az1p=791; az2 should meet/beat). Read the live weakness.
3. **Grow the learned population** — each az_N joins the stable as a strong opponent (currently az0,
   az0b in it; add az1p/az2). Consider a LEARNED GRIMMSNARL (same pipeline, grimm deck + grimm stable).
4. **Strategy Track report** (Sept 13, $240k): our from-scratch RL system + measurement/validation
   stack + honest science is a strong, unusual writeup — the real prize. Start outlining when climbing stalls.

Session stats: pivoted from a plateaued rule agent (739) to a LEARNED agent live at 791 and climbing,
built the entire RL + validation stack, and proved the loop climbs + steers. The learned front is the game now.
