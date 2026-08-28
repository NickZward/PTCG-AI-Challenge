# Strategy — getting closer to top-player behavior

*Grounded in this session's evidence (2026-07-25). See memory: ptcg-top40-recipe, ptcg-grimm-exposure-fix,
ptcg-deeper-search-wall, ptcg-starmie-autopsy.*

## TL;DR

**Does copying top players work? YES — but only through an imitation-learned MODEL, not through
hand-copied RULES.** The #40 player (1035) got there by pure imitation on ~21k games. When we tried to
copy his specific plays as rules this session, only the *do-no-harm safety* fix survived; every
*judgment* fix (counter-routing) failed, because his edge is matchup-dependent judgment a single rule
can't express. **Rules are for safety; the learned model is for judgment.** That division is the
strategy.

---

## 1. Does copying top players work?

**Through imitation: yes (proven).**
- #40 NguyenThanhNhan = 1035, **pure imitation on ~21k games / H200 / 3-4 hr**. He wins by crushing the
  field we throw (Crustle 4-1, Alakazam 8-1) and even *loses* the mirror (3-9) — his rating is off-mirror
  field dominance, learned wholesale.
- Our own imitation attempt was **capped only because it was under-powered**, not because the method
  fails: 61k Grimm-only decisions (vs his ~400k+), a tiny 13M/128-dim net, on CPU, and then we
  **contaminated it with self-play** which dragged the weights off the expert. The "27% top-1 imitation"
  we measured was starvation, not a ceiling. It was never a fair test.

**Through rules: partially, then a hard ceiling (proven this session).**
- Copying his Alakazam recipe as a rule (never feed a chipped 2-prize ex into a scaling OHKO) → **worked**
  and shipped (v18→v19), because it's a clean *do-no-harm* rule.
- Copying his counter-routing as a rule (cash KOs / target Mega walls) → **failed both times**: looked
  +17.8 vs M-Lucario on run 1, was noise (run 2 −1.2), and consistently *hurt* Starmie −14pp — because
  the right routing is matchup-dependent (tank a tanky Mega, snipe a fragile Mega's support) and one rule
  can't hold both. His imitation net just *learns* the distinction.
- **The recurring unifying gap** is the "engine-first" inversion: he treats the Munkidori/Froslass
  counter-engine as his weapon and GrimmEX as a tank (fires ~5-9/game @ 85% energized every game); we
  treat GrimmEX as the weapon and fire the engine ~2/game (0% in our losses). That's a whole priority
  orientation across dozens of decisions — learnable, not ruleable.

---

## 2. What you need to get closer to top-player behavior

**Lever 1 — Scale the imitation (biggest, highest-confidence).** Redo our imitation the way the #40
player did, undoing our two fatal shortcuts:
- Data: **all decks, ~all his games (~400k+ decisions)**, not 61k Grimm-only.
- Model: **bigger policy net** (ours was 13M/128-dim).
- Compute: **the H200**, pure imitation, **no self-play** on top.
- The machinery already exists in `analysis/az_nn/` (canonical encoder/decoder, extract_warmstart,
  train_core pretrain); it just needs to be scaled and run clean.

**Lever 2 — Deck selection (deck-EV over 13,621 real ladder games, 3 days 07-22/23/24).** The meta is
**consolidating hard around Grimmsnarl** (share rising 38%→39%→54%), Alakazam ~21%, Crustle ~8%,
everything else fading, and **M-Starmie/M-Lucario VANISHED (<1%)**. Deck-EV (meta-weighted win rate):
**Dipplin 58.5%** (n=404: beats Grimm 61%/n197, Alakazam 57%/n83, Crustle 66%) > Grimmsnarl 51.3%
(n huge) > Crustle 47% > Alakazam 46%. Dipplin is the highest-EV deck — a hard counter to the whole
field, and its old tank-deck weakness disappeared. **BUT the decision is a genuine tradeoff, and for an
IMITATION checkpoint the data likely decides it:**
- *Dipplin* = highest ceiling (58.5%) but **data-starved**: only ~404 games / 1.5% of the meta to imitate.
- *Grimmsnarl* = solid 51% EV, the **dominant + rising meta (54%)**, and **~12k games** of training data;
  the mirror is half your matches and there's abundant top-player mirror play to learn (see [[ptcg-top40-recipe]]).
=> Point the MAIN checkpoint at **Grimmsnarl** (data-rich, dominant, mirror-centric) unless you can source
enough strong Dipplin games; keep **Dipplin as a high-EV pocket counter** if you can feed it. NOTE: much
of this session's Starmie/M-Lucario work targeted LOWER-bracket threats absent at the top; v19's remaining
top-meta value is vs Alakazam (21%). Deck-EV spread across reliable decks is only ~5-7pp — **pilot quality
(the imitation model) remains the bigger lever than deck choice.**

**Lever 3 — Emphasize engine-uptime in training + eval.** The single behavior separating his Grimm from
ours is engine uptime. Make it an explicit eval KPI: **energized-Munkidori-turns and Adrena-Brain
fires/game**. If the checkpoint hits ~85% energized like the top bots, the Grimm mirror falls into place
(in the mirror, that number basically *is* the win rate).

**Lever 4 — A faithful evaluator (the wall behind everything).** Our local eval swings ±15-20pp and the
proxies are unfaithful (proxy Dipplin 73% vs real 38%); it manufactured then erased "wins" repeatedly
this session (az2, the Starmie fix, Fix #3). **The ladder is the only faithful judge** (cheap churn,
converges <1 hr, 5 uploads/day). So the improvement loop is **train → ship → measure ladder KPIs →
iterate**, NOT local A/B. Budget the ladder as the measurement instrument.

**Lever 5 — To EXCEED top players (not just match).** The top players are themselves imitation-capped
(the #40 *loses* the mirror 25%). Going beyond needs a search/PPO layer **on top of a strong imitation
base** — but the hidden-information wall is real: our 2-ply search played *worse* than 1-ply because
guessing the opponent's hidden cards adds noise that compounds. Self-play PPO hits the same wall; it
lives or dies on how the hidden state is determinized. This is the research-grade lever — do it last,
carefully, only after the imitation base is strong.

---

## 3. The plan, prioritized

1. **Scale the imitation** (Lever 1) — all-deck data, bigger net, H200, pure. The biggest step toward
   top-40-class behavior.
2. **Deck selection** (Lever 2) — free; do it now; re-check as the meta shifts.
3. **Ship + measure on the ladder** (Lever 4) — the only honest signal; every iteration goes through it.
4. **Keep rules as a do-no-harm safety layer** — v19-style fixes (never feed a chipped ex) can wrap the
   neural policy cheaply; they don't need to hold the judgment.
5. **Later: value-search / PPO** (Lever 5) — only on a strong base, handling opponent determinization
   carefully.

## 4. The honest ceiling + the division of labor

- **Imitation-at-scale gets you ~top-40-class** (matching the experts you copy). It does **not** reach
  #1 — the experts are imitation-capped too. Exceeding them needs Lever 5 + solving hidden-info
  determinization, which is a genuine research problem.
- **Division of labor (the session's core lesson):** the **learned model carries the judgment**
  (engine-first play, adaptive routing, opponent reads — none of it ruleable); **rules carry the
  do-no-harm safety** (don't feed a chipped ex, escape a stuck active). Build both; don't ask rules to
  do the model's job — that's the ceiling we hit all session.
</content>
