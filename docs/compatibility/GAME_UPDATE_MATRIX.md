# Clash of Clans compatibility matrix

**Audit date:** 2026-08-06  
**Source baseline:** MyBot v8.2.0, released May 8, 2025  
**Baseline game claim:** April 2025 client line (`17.126.20+`)

This matrix tracks changes that can alter screen recognition, coordinates, navigation, data tables, state transitions, or recovery behavior. A row marked **Not covered** means the baseline predates the change; it does not mean every related function is broken.

## Update impact

| Date | Game change | Automation surfaces affected | Baseline status | Planned response |
| --- | --- | --- | --- | --- |
| 2025-03-24 | **Clash Anytime** removed training/healing time, added Army Recipes, changed donations, shield/matchmaking behavior, and army screens. | Army readiness, training timers, boosts, donation cost/flow, request cooldowns, shield logic, matchmaking, army editor coordinates. | **Partially covered** by the v8.2.0 timeframe; all timer and queue assumptions still require an explicit audit. | Inventory training/readiness checks, remove stale waits, and add fixtures for Recipes and donation states. |
| 2025-06-16 | **Let's Get Crafty** added Crafted Defenses, Ice Block, Cookbook tab, new army ordering, SCID guest accounts, shop indicators, and a larger Builder Base elixir cart. | Training tabs, troop/spell tables, Hero lineup drag order, account switching, shop notifications, Builder Base cart detection, defense recognition. | **Not covered.** | Add data and templates; make army-tab navigation semantic rather than fixed-index; validate guest-account handling. |
| 2025-10-06 | **Ranked update** split regular Battles from Ranked Battles and reworked shields, revenge, tournament mode, traps, loot, task counts, and attack-screen controls. | Attack routing, stop conditions, trophy logic, shield state, battle logs, revenge screens, challenge detection, Clan Games expectations. | **Not covered.** | Introduce an explicit battle-mode enum and separate regular, ranked, revenge, war, friendly, and tournament routes. |
| 2025-11-17 | **Town Hall 18** added Guardians, Meteor Golem, Totem Spell, Revenge Tower, Super Wizard Tower, new upgrade ranges, Crafted Defense phase 2, Fancy Shop, and a unique TH18 reveal flow. | TH detection, building/troop/spell data, upgrade menus, hero-like defender state, shop navigation, one-time cinematic/reveal recovery, battle-end screens. | **Not covered.** The baseline's visible icon references stop at TH17. | Extend the game model before adding templates. Treat Guardians separately from attacking Heroes. Add TH18 onboarding and meteor-removal fixtures. |
| 2026-02-23 | **February update** introduced Dragon Duke as a sixth Hero, changed Hero Hall/Blacksmith/Profile layouts, reworked Gold Pass and Daily Tasks, added Prospector and more TH18 levels. | Fixed-size Hero arrays, Hero GUI controls, equipment slots, upgrade planning, profile parsing, task and pass popups, resource display. | **Not covered.** | Convert Hero handling to data-driven collections, add a sixth-Hero migration, and update all Hero Hall/Profile/Blacksmith recognition. |
| 2026-04-27 | **Sound of Clash** split Legend League into three tiers, changed tournament schedules and battle counts, added Logger, and refreshed Ranked logs, layouts, leaderboards, and progression screens. | Ranked enrollment, run budgets, weekly timing, league OCR, battle-count stop rules, layout management, Guardian data, promotion/demotion dialogs. | **Not covered.** | Build a Ranked capability model read from current UI state instead of hard-coded historical limits. |
| 2026-05-26 | **Mandatory May update** added another Builder Base builder and moved Barbarian King unlock to TH4. | Builder counts, upgrade capacity, early-game hero assumptions, Builder Base progress and shop surfaces. | **Not covered.** | Remove fixed builder caps and Town Hall assumptions; add low-TH profile fixtures. |
| 2026-06-15 | **Anime Fury** added Hero Journey, Ruin Witch, Monolith Arrow, Angry Spell, new building/hero levels, Global Chat, live-battle fast-forward, Capital Treasury, Chain Offers, and equipment-order changes. | Hero Hall alerts, reward dialogs, troop/spell/equipment tables, chat and donation routing, battle controls after 120 seconds, shop popups, capital navigation. | **Not covered.** xbebenk contains a candidate Hero Journey message handler, but it is not a full v8.2.0 port. | Add an interruption registry, current data catalog, Global Chat-safe routing, fast-forward recognition, and deterministic popup fixtures. |
| 2026-07-09 | **July balance update** changed current TH18 units and noted a Rocket Backpack interaction requiring a later client fix. | Strategy assumptions, equipment behavior, result expectations, regression fixtures. | **Data not covered.** | Keep strategy presets versioned and avoid using expected damage/result values as screen-state proof. |
| 2026-08-01 | **Clash of Cards** added an event HUD entry, Card Hunt rewards from battles, a three-step pack reveal, collection and Trader screens, clan-chat trade requests, and a persistent village decoration. | Post-battle recovery, popup dismissal, HUD recognition, chat parsing, Trader navigation, obstacle/deco handling, run-loop interruption priority. | **Not covered.** | Add event-window fixtures and classify the decoration as a safe persistent object. Never auto-spend Gems or trade cards without an explicit, separately authorized feature. |
| 2026-08-06 | **Chief's Chronicles** announced a new left-side village shield near the Trader and a multi-screen year-in-review experience running August 8–31. | Village safe coordinates, Trader access, left-side HUD matching, unexpected-screen recovery, share dialogs. | **Not covered.** | Add a non-entry guard and fixtures before the event begins; recovery should return home without interacting with recap/share flows. |

## Current source checks required

The following searches and code reviews are mandatory before claiming current-client support:

- every array or loop whose length assumes five Heroes or TH17 as the maximum
- troop, spell, pet, siege, equipment, building, wall, and cost enums
- all attack-screen image regions and button priority rules
- training timers, queue waits, barracks boosts, Hero-heal waits, and readiness fallbacks
- Battle/Ranked/Legend/War/Friendly/Revenge state distinctions
- SCID switch failure and account-name matching behavior
- chat button detection and donation flow after Global Chat
- Builder Base builder counts, shop access, cart collection, and battle-end routing
- Shop, Trader, Gold Pass, Hero Journey, Chain Offer, Card Pack, Chief's Chronicles, and event tutorial interruptions
- obstacle, chest, scenery, decoration, and left-side HUD safe-area logic
- post-attack cleanup when Card Hunt or other event rewards are awarded

## Acceptance levels

| Level | Meaning |
| --- | --- |
| **Catalogued** | The game change and affected source areas are documented. |
| **Implemented** | Code and assets have been updated, but no current-client run is recorded. |
| **Fixture-tested** | Recognition and transitions pass deterministic screenshot/state tests. |
| **Smoke-tested** | A controlled Windows/emulator run completed the documented scenario. |
| **Supported** | Repeated smoke tests pass on every advertised environment and the evidence is attached to a release. |

A feature must not be described as supported based only on a recent commit date or copied templates.

## Official references

- [Welcome to Clash Anytime Update](https://supercell.com/en/games/clashofclans/blog/release-notes/welcome-to-clash-anytime-update/)
- [Welcome to Let's Get Crafty Update](https://supercell.com/en/games/clashofclans/blog/release-notes/welcome-to-lets-get-crafty-update/)
- [Get Ready for Ranked](https://supercell.com/en/games/clashofclans/blog/release-notes/get-ready-for-ranked-update/)
- [Town Hall 18 Crash Lands](https://supercell.com/en/games/clashofclans/blog/release-notes/town-hall-18-crash-lands-update/)
- [The February Update Has Escaped](https://supercell.com/en/games/clashofclans/blog/release-notes/the-february-update-has-escaped/)
- [The Sound of Clash Update](https://supercell.com/en/games/clashofclans/blog/release-notes/the-sound-of-clash-update/)
- [The Anime Fury Update Is Here](https://supercell.com/en/games/clashofclans/blog/release-notes/the-anime-fury-update-is-here/)
- [July Balance Update](https://supercell.com/en/games/clashofclans/blog/news/july-balance-update/)
- [Clash of Cards Event](https://supercell.com/en/games/clashofclans/blog/news/clash-of-cards-event/)
- [Chief's Chronicles Are Here](https://supercell.com/en/games/clashofclans/blog/news/chiefs-chronicles-are-here/)
- [Clash of Clans news archive](https://supercell.com/en/games/clashofclans/blog/)
