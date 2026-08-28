# Mega Lucario ex — Starter Deck (PTCG AI Battle Challenge)

## Why this archetype
- **Simple line for an agent:** Riolu → Mega Lucario ex (Stage 1, no Rare Candy logic needed)
- **Cheap attacks:** Aura Jab does 130 for one {F} Energy *and* re-attaches up to 3 Basic {F} Energy from the discard to your bench — the deck refuels itself
- **Nuke option:** Mega Brave, 270 for {F}{F} (can't repeat next turn — agent should alternate attackers or use Aura Jab)
- 340 HP tank; community starter agents use this same core, so it's proven on the ladder

## Deck list (60)

| Qty | ID | Card | Role |
|----:|-----:|------|------|
| 4 | 677 | Riolu (80 HP) | Basic; evolves into Mega Lucario |
| 4 | 678 | Mega Lucario ex | Main attacker |
| 4 | 1145 | Mega Signal | Search Mega Evolution ex |
| 4 | 1142 | Fighting Gong | Search {F} Energy or {F} Basic |
| 4 | 1122 | Pokégear 3.0 | Find draw Supporters |
| 2 | 1123 | Switch | Pivot out of the Active Spot |
| 2 | 1097 | Night Stretcher | Recover Pokémon/Energy from discard |
| 2 | 1141 | Premium Power Pro | +30 dmg for {F} attackers this turn |
| 1 | 1158 | Maximum Belt (ACE SPEC) | +50 dmg vs Pokémon ex → Mega Brave hits 320+ |
| 4 | 1224 | Cheren | Draw 3 |
| 4 | 1236 | Urbain | Draw 3 |
| 2 | 1227 | Lillie's Determination | Shuffle-draw 6 (8 at 6 prizes) |
| 2 | 1235 | Waitress | Energy acceleration from top 6 |
| 2 | 1205 | Cyrano | Search up to 3 Pokémon ex |
| 2 | 1211 | Black Belt's Training | +40 dmg vs ex (stacks with Belt: 270+50+40 = 360 = OHKO on opposing Megas) |
| 1 | 1238 | Tarragon | Recover 4 {F} Pokémon/Energy from discard |
| 13 | 6 | Basic {F} Energy | |
| 3 | 20 | Rock Fighting Energy | Provides {F} + blocks attack effects |

## Validation
- Exactly 60 cards ✓
- Max 4 per card name (basic energy exempt) ✓
- Exactly 1 ACE SPEC (Maximum Belt) ✓

## Agent implications (next step)
1. Turn 1 priority: bench Riolu(s), Fighting Gong for energy/basics
2. Evolve to Mega Lucario ASAP (Mega Signal / Cyrano find it)
3. Attack policy: Mega Brave when it KOs (esp. with Belt/Black Belt vs ex), otherwise Aura Jab to refuel the bench
4. Always attach energy every turn; keep a benched backup Lucario charged
