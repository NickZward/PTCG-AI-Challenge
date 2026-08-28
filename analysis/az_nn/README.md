# az_nn — Transformer + MCTS learned agent (from the competition's reference design)

Built 2026-07-24. Replaces the GBM + 1-ply `alakazam_az*` line's *architecture* with the design the
competition actually intends: a small **Transformer** (encoder/decoder over EmbeddingBag-summed sparse
features) + **real MCTS** via the Search API + AlphaZero self-play. First target deck: **Grimmsnarl**
(the apex / highest-skill-ceiling deck — 43.8% of the 1100+ band; our v17 rules already peak 802 on
Luca's #1 list, a ~350pt pure-piloting gap that search/RL can close). See memory `ptcg-scoring-and-meta`.

## Files
- `nn_common.py` — canonical feature encoding (`get_encoder_input`/`get_decoder_input`) + `MyModel`,
  ported faithfully from the reference notebook, importing our local cg-lib. **Authoritative** encoding
  (replaces the reverse-engineered `bc_features`). Constants derive from the live card DB (card_count
  1268, attack_count 1557; traced max encoder index 21598 < 22000).
- `mcts_agent.py` — MCTS on the reference template, with **our determinization**: deck-aware + seen-card
  dedup (`_unseen`) for our side; deck-aware for the opponent when its deck is known (self-play), else a
  neutral Snorlax/energy fill (unknown ladder opponent). `search_begin` is guarded (legal-default fallback).
- `train_core.py` — self-play training. **Mirror self-play is the majority signal** (the reference's proven
  climber) + a **curriculum** minority vs real rule opponents (M-Lucario/Crustle first) for matchup coverage
  without weak opponents distorting the policy. **T14 ladder adjudication** for value labels. Reference
  TD(λ) value + MCTS-advantage policy + combined Huber loss. Per-iteration eval vs the curriculum.
- `train_selfplay.py` — local entry: `smoke` (validated), `local`, `full`.
- `build_kaggle.py` → generates `kaggle_train_grimm.py` — a SINGLE self-contained file (base64-embeds the
  modules + curriculum agents + decks). Edit the sources, rerun build, re-upload.
- `validate_encoder.py`, `test_agent_game.py` — step-1 / step-2 checks (both pass).

## Validation status (all local, CPU)
1. Encoder/decoder: runs on fresh + real-replay states, index bounds + value/policy sane. ✅
2. Agent: plays full games, MCTS/Search-API/both determinization paths, legal moves, ~6ms/decision. ✅
3. Training: smoke run collects samples (T14-adjudicated) from mirror+curriculum, trains, evals, saves. ✅
4. Deploy: `my-agent/grimm_nn0/` loads in `round_robin` and plays legally (smoke model ≈ random → loses,
   as expected; the *pipeline* is what's validated). ✅

## HOW TO GET A STRONG AGENT (the compute step — Kaggle GPU)
1. Kaggle → New Notebook in **pokemon-tcg-ai-battle**; Settings → Accelerator **GPU**, Internet **on**,
   add the competition data (puts cg-lib + card data under `/kaggle/input`).
2. Paste `kaggle_train_grimm.py` into one cell → **Run All**. (Scale knobs in `CFG`: iterations,
   games_per_iter, search_count, and `model` size — bump to `(256,4,512,2,2)` for a stronger net.)
3. Download `/kaggle/working/model_final.pth` + `model_arch.json`.
4. Drop both into `my-agent/grimm_nn0/` (replace the placeholder `model.pth`; keep `model_arch.json`).

## THEN validate + ship (local)
```
# round-robin vs rules + curriculum + HELD-OUT validators (honest generalization)
python3 analysis/round_robin.py 45 \
  my-agent/grimm_nn0 my-agent/grimmsnarl_v17 \
  my-agent/gauntlet/mlucario my-agent/gauntlet/crustle \
  my-agent/gauntlet/archaludon my-agent/bc_yushin my-agent/gauntlet/okidogi
```
Look for: grimm_nn0 beats grimmsnarl_v17 head-to-head + improves the M-Lucario/Crustle matchups. Then pack
`my-agent/grimm_nn0/` (main.py + nn_common.py + mcts_agent.py + deck.csv + model.pth + model_arch.json) as a
submission tarball and A/B on the ladder (peak converges ~1h). `model.pth` ≈48MB fp32 (fp16 → ~25MB if needed).

## Notes / next levers
- `model.pth` in grimm_nn0 today is a near-random SMOKE placeholder — replace via Kaggle training before shipping.
- Value-grounding enhancement (ready to wire): pretrain the value head on real top-player game states→T14
  outcomes from `Logs 07-22/` (4,639 top games incl. Luca/Yushin) — sidesteps the BC move-cloning wall.
- Same pipeline retargets to Alakazam (swap deck_dir + curriculum) for a Transformer Alakazam later.
