# Current game model: implementation slice 1

**Branch:** `integration/current-game-model-1`  
**Audit date:** August 6, 2026  
**Official facts verified through:** July 9, 2026

## Purpose

Move current Clash of Clans facts out of scattered coordinates, comments, and assumptions into a sourced, machine-readable model. The model describes what exists, what screen evidence is required, and which routes are still blocked. It does not mark a feature supported merely because a record was added.

## Catalogs

### `config/game/current-client.json`

The source ledger and update timeline. Every dated rule used by the other catalogs points to an official Supercell Clash of Clans article. The ledger records the current maximum Town Hall, six-Hero roster, four active Hero slots, and verified updates through the July 9, 2026 balance post.

Two names used in the earlier audit—`Clash of Cards` and `Chief's Chronicles`—were removed from compatibility claims. No official Supercell release note or news article for either name was found during the August 6 review. They remain only in the exclusion register so the validator can prevent accidental reintroduction.

### `config/game/battle-surfaces.json`

Regular, Ranked, Revenge, the three Legend tiers, and Builder Base are modeled independently. Every surface defaults to:

- current-client recognition required;
- execution blocked or not implemented;
- no legacy fallback;
- explicit attack-budget semantics;
- one or more evidence fixtures.

The Legend budgets are modeled exactly as published in April 2026: 24 weekly attacks for Legend III, 30 weekly attacks for Legend II, and eight attacks per League Day for Legend I.

### `config/game/heroes.json`

The six current Home Village Heroes are modeled with unlock Town Hall, movement family, evidence source, and required fixture IDs. The roster contains Barbarian King, Archer Queen, Minion Prince, Grand Warden, Royal Champion, and Dragon Duke. The active Hero slot limit remains four.

### `config/game/screen-states.json`

The registry contains current Army Recipes, Cookbook, Crafted Defense, battle entry, Legend, fast-forward, TH18, Guardian, six-Hero, Dragon Duke, Hero Journey, Global Chat, Builder Base Builder, and Chain Offer surfaces. Every state defines:

- source article;
- linked capabilities and fixtures;
- whether it blocks automation;
- recognition and handler status;
- a bounded safe default action;
- retry limit.

No screen-state handler is enabled in this slice.

## Validation

`tools/validate_game_catalog.py` checks:

- official Supercell source domains and dates;
- unique identifiers and cross-file references;
- exact Regular, Ranked, Revenge, and Legend rules;
- the six-Hero roster and unlock progression;
- fixture and capability references;
- closed readiness defaults;
- safe actions and bounded retries;
- removal of unsupported August event claims from project documents.

## Acceptance boundary

A catalog entry is descriptive evidence, not operational support. The next slices must add approved 860×732 fixtures, recognition assertions, AutoIt descriptors, and controlled route evidence. Only then may a screen or route move from `fixture-required` or `blocked` to `verified`.
