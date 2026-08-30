# Pokémon TCG AI Challenge

My working repository for the [Pokémon TCG AI Challenge](https://www.kaggle.com/competitions/pokemon-tcg-pocket-ai-challenge) on Kaggle: building agents that play the Pokémon Trading Card Game Pocket, from hand-written rule engines to self-play reinforcement learning and imitation learning from scraped ladder replays.

**Status:** the competition's Strategy Track writeup is in progress (deadline Sept 13, 2026). A cleaned-up writeup with figures will land here after submission. Until then, this repo is the raw working state: research code, experiment logs, and evidence, not a polished library.

## What's here

| Path | Contents |
|---|---|
| `analysis/` | The main toolkit: self-play generation, value/policy training, round-robin evaluation, behavior-cloning sparring opponents, replay autopsy tools |
| `strategy_track/` | Writeup draft, figures, and the experiment logs behind every claim |
| `SESSION_HANDOFF.md` | The living lab notebook: findings, dead ends, and current state |
| Top-level `*.py` | Replay scrapers (Kaggle episode API) and utilities |
| `*.csv` | Deck lists and replay manifests |

## Highlights of the approach

- **AlphaZero-lite pipeline:** self-play generation, value and policy networks, policy-guided search, and a stable round-robin validator to keep evaluation honest.
- **Imitation learning from real ladder replays**, including the debugging story: a one-step action/observation misalignment and a degenerate loss choice had capped fidelity at 30%; fixing both roughly doubled top-1 accuracy.
- **Realistic evaluation:** behavior-cloned clones of top ladder players as sparring partners, because pure self-play win rates lie.
- **A lot of negative results**, documented: deeper search that loses to the field, proxies that don't transfer, and why.

Replay data and model weights are excluded from the repo (the working set was ~155GB); everything needed to understand and reproduce the reasoning is in the code and logs.
