# Clash of Clans compatibility matrix

**Audit date:** August 6, 2026  
**Baseline bot support claim:** April 2025 client family  
**Official facts verified through:** July 9, 2026

| Date | Official change | Systems affected | Current status |
|---|---|---|---|
| 2025-03-24 | Training and Hero healing time removed; Army Recipes introduced | Army preparation, timers, donation assumptions, UI navigation | Catalogued; recognition required |
| 2025-06-16 | Cookbook third tab and temporary Crafted Defenses | Army tabs, Crafting Station, defense catalog, attack analysis | Catalogued; recognition required |
| 2025-10-06 | Regular and Ranked Battles split; Revenge returns | Matchmaking, route selection, Trophies, shields, attack limits, Defense Log | Catalogued; separate routes required |
| 2025-11-17 | Town Hall 18 and Guardians | TH detection, walls, levels, costs, defense catalog, profiles | Catalogued; fixtures required |
| 2026-02-23 | Dragon Duke and six-Hero UI support | Hero arrays, Hero Hall, Blacksmith, Profile, deployment, reports | Catalogued; descriptor migration required |
| 2026-04-27 | Legend III, II, and I | Schedule, weekly/daily budgets, ranking, stop conditions | Catalogued; tier recognition required |
| 2026-05-26 | Extra Builder Base Builder; Barbarian King moves to TH4 | Builder counts, Builder Base upgrades, Hero unlock catalog | Catalogued; fixtures required |
| 2026-06-15 | Hero Journey, Global Chat, live-battle fast-forward, Chain Offers | Hero Hall, chat state, safe regions, timing, shop interruptions | Catalogued; handlers blocked |
| 2026-07-09 | Dragon Duke, Logger Guardian, and related balance changes | Hero/Guardian assumptions, equipment interactions, test baselines | Catalogued; no coordinate change assumed without fixtures |

## Legend route rules

| Surface | Schedule | Attack budget | Promotion or demotion rule |
|---|---|---:|---|
| Legend III | Weekly tournament | 24 per week | Top 5 promote |
| Legend II | Weekly tournament | 30 per week | Top 3 promote |
| Legend I | Four-week tournament | 8 per League Day | Players below rank 10,000 at weekly reset demote |

## Source ledger

- `https://supercell.com/en/games/clashofclans/blog/release-notes/welcome-to-clash-anytime-update/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/welcome-to-lets-get-crafty-update/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/get-ready-for-ranked-update/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/town-hall-18-crash-lands-update/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/the-february-update-has-escaped/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/the-sound-of-clash-update-is-here/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/may-update/`
- `https://supercell.com/en/games/clashofclans/blog/release-notes/the-anime-fury-update-is-here/`
- `https://supercell.com/en/games/clashofclans/blog/news/july-balance-update/`

## Acceptance rule

`Catalogued` means the official change and affected systems are recorded. It does not mean the bot recognizes or safely executes the changed surface. A route or screen becomes supported only after fixture, static, Windows, emulator, and controlled runtime evidence pass.
