# From 617 to the Top Bracket with a Measurement-First Agent
### Strategy Track report — Team Kilupy (DRAFT v0.1, 2026-07-29)

> Working draft. Numbers are final measured values from the project log; sections marked TODO
> need the end-of-competition results filled in. Target length: adjust to track rules (TBC).

---

## 0. One-paragraph summary

We built a Pokémon TCG agent that climbed from a 617-rated rules engine to a stable top-bracket
neural agent (peak 957 in the pre-deflation era; v12/v14 live at the time of writing) using
imitation learning on top-player replays. The distinguishing feature of our entry is not the
architecture — it is the **measurement discipline** wrapped around it: every hypothesis was
pre-registered against a calibrated local gate or an in-game mechanism KPI, eight of eleven
well-motivated improvements were **rejected by our own instruments before shipping**, and two of
the project's largest gains came from *forensic debugging of the data pipeline* rather than
modelling. We present the method, the instruments, the negative results (with root causes), and
the general lessons for building game agents on replay data.

---

## 1. The arc (fill numbers at freeze)

| generation | change | local evidence | ladder result |
|---|---|---|---|
| rules v17/v20 | hand-written pilot | — | ~600-800, unstable |
| **v2** | imitation transformer, corrected labels + CE loss | beats rules 73%/86% | **760 stable** (first stable 700+) |
| **v4** | margin-shaped value targets + search/time fixes | gate 73.3% vs v2 | **~895 stable** (+135) |
| **v6** | fine-tune on then-#1 player (flg, 316 games) | gate 71.1% vs v4 | **~950** (peak 957) |
| v11 | positional candidate features (grafted) | gate: null; **ladder: +10pp window-matched** | 908.5 (deflated era) |
| **v12** | + top-3 consensus decklist + search-bug fix | do-no-harm | TODO |
| **v14** | + early-phase-weighted objective | **tempo KPI 1.31→1.58 (expert band)** | TODO |

## 2. The two foundational bug-finds (why our imitation worked at all)

### 2.1 The replay action/observation off-by-one
Kaggle replays store a seat's action in the **next** step's entry. The naive same-entry pairing
mislabels 100% of decisions with the *previous* decision's action. Three independent proofs:
option-count/legality validation (99.9% vs 72.2%), replaying our own agent against its own
replays (78.3% vs 22.4% reproduction), and the training outcome itself. **Fixing pairing + the
objective took held-out top-1 from 30.5% → 60.4% on 1% of the data.** Every published number we
could find from other teams' imitation attempts is consistent with some of them shipping on
mislabeled data.

### 2.2 The degenerate imitation objective
The reference notebook trains the policy head by Huber regression to ±1 with a tanh output — for
single-label imitation this saturates at "predict −1 everywhere" (measured: policy loss flatlines,
top-1 *below* the always-first-option baseline). Masked softmax cross-entropy over the legal
candidate set, plus **tie-aware credit** (60.7% of decisions contain byte-identical candidate
encodings; crediting the expert's indistinguishable twin removes contradictory gradients), is the
correct objective. 2×2 ablation table included (§Appendix A).

## 3. The instruments (the actual contribution)

1. **Calibrated gate.** 45-game round-robins carry ±10pp run-to-run noise *between functionally
   identical agents* (measured: 71.1% vs 60.0% same-weights). Rule: only ~70/30 outcomes are
   decisions; anything smaller goes to instrument #3.
2. **Mechanism KPIs ("verify the fix fires").** Every candidate ships with an in-gate behavioural
   measurement — e.g. v14's prizes-by-turn-8 (1.58 vs control 1.09 in the same games) — so
   acceptance never rests on a noisy win rate. Conversely, the expert-rate pre-check killed a
   plausible "fix" (fresh-tank promotion gate) by showing the #1 player does it *more* in wins.
3. **The ladder as A/B instrument.** Two active submission slots + fast rating convergence =
   free field experiment. Window-matched records (never raw scores — we measured ~55pt global
   rating deflation in one day) resolved sub-10pp effects the gate cannot (v11 > v6 by ~10pp,
   invisible locally).
4. **Baselines everywhere.** Random and always-first-option baselines accompany every fidelity
   number; value-head quality is reported as AUC on *real ladder states* by game phase.

## 4. Negative results (all pre-registered, all with root causes)

| hypothesis | verdict | root cause found |
|---|---|---|
| endgame/buzzer value blend in search | null vs own control | value head already trained on margins; turn count already an encoder feature |
| peer-level data (284 games, ~950-rated pilots) | null | teacher quality dominates volume |
| more #1-player data (449 games, rating 1201) | null | policy already 91% converged on it |
| opponent-deck determinization in search | invalid→retest | *(control leaked via path fallback — documented)* then: opponent **policy**, not deck, is the gap |
| positional candidate features (from scratch) | rejected | discards curriculum; fidelity ≠ strength |
| deeper search 10→32 evals; fixed sweep bug | both null | **search saturates: value head cannot discriminate futures** |
| KL-anchored self-play value refinement (2 recipes) | negative | mirror outcomes are draw-luck; 850 own games cannot beat a 400k-decision expert prior |
| early-phase-weighted objective (v14) | **KPI fired** | the one untried axis: phase-targeted, not global |

## 5. General lessons

1. **Data forensics > architecture.** Both breakthrough gains were pipeline bugs; zero came from
   architecture changes (a 60%-larger net with better features *lost* its gate).
2. **Fidelity is not strength.** +1.9pp real held-out top-1 = 0pp win rate, twice. Imitation
   agreement saturates; the game only cares about decisive states.
3. **Teacher quality dominates data volume; convergence comes fast.** One strong teacher (316
   games) = +50 rating; a second #1 corpus after convergence = 0.
4. **Silent exception handling is the most expensive bug class.** Three project incidents
   (`__file__` sandbox crash, an A/B control silently re-enabled by a path fallback, a search
   sweep dead for three generations via swallowed NameError).
5. **Phase-weighted objectives are a fresh axis after global ones saturate** (v14).
6. TODO: final ladder verdict on v12/v14 and closing rating.

## Appendix A: the 2×2 label/objective ablation (numbers final)
## Appendix B: gate noise calibration protocol
## Appendix C: pipeline diagram + reproduction commands
## Appendix D: full experiment ledger (19 tracked tasks, dates, outcomes)

---
*TODO before submission: track-rule compliance pass (format/length/code attachment), final
numbers, figures (rating trajectory, tempo KPI plot, AUC-by-phase bar chart).*
