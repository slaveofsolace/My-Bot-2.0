# Baseline audit

**Audit date:** August 6, 2026  
**Target repository:** `slaveofsolace/My-Bot-2.0`  
**Foundation:** MyBot v8.2.0 source from official `develop` commit `8ad6e5a552347acc2fcb8048d30262e2735a0c33`

## Executive finding

The repository now has a source-complete v8.2.0 foundation, but the inherited automation remains tied to the April 2025 game client family. Official Supercell changes through July 9, 2026 affect army preparation, battle routing, Town Hall and Hero catalogs, Legend limits, Builder Base builders, chat, interruptions, live-battle timing, upgrade logic, OCR, image templates, and fixed coordinates.

Current-client support is therefore a cross-cutting migration. No route, screen, Town Hall, Hero, Guardian, or emulator should be advertised as supported until its source model, fixture evidence, static tests, and controlled runtime evidence all pass.

## Source decisions

- Keep MyBot v8.2.0 as the core.
- Adapt selected GPL-compatible xbebenk changes by subsystem instead of overlaying its older v7.9.9 base.
- Treat Clash-AutoLoot as a clean-room behavior reference only because its public repository does not publish application source under a usable source license.
- Keep exact upstream commits and import rules in `upstreams.lock.json`.

## Verified current-game changes

The official source ledger in `config/game/current-client.json` records:

1. Clash Anytime and Army Recipes on March 24, 2025.
2. Cookbook and Crafted Defenses on June 16, 2025.
3. Separate Regular and Ranked Battles plus Revenge on October 6, 2025.
4. Town Hall 18 and Guardians on November 17, 2025.
5. Dragon Duke and six-Hero UI changes on February 23, 2026.
6. Legend III, II, and I on April 27, 2026.
7. The extra Builder Base Builder and Town Hall 4 Barbarian King on May 26, 2026.
8. Hero Journey, Global Chat, and live-battle fast-forward on June 15, 2026.
9. The July 9, 2026 Dragon Duke, Logger Guardian, and related balance adjustments.

No official Supercell source was found for two August event names previously included in this audit. Those names have been removed from compatibility claims and are retained only in the machine-readable exclusion register.

## Highest-risk systems

### Navigation and battle routing

The legacy main loop was built around the former multiplayer route. Regular, Ranked, Revenge, three Legend tiers, and Builder Base require separate route descriptors, limits, fixtures, and stop rules. Silent fallback is prohibited.

### Heroes and Town Hall data

The baseline knows Town Hall 17 and five Heroes. Current data requires Town Hall 18, Guardians, six Heroes, Dragon Duke, and four active Hero slots. Fixed arrays and GUI loops must be migrated to descriptors before the sixth Hero is enabled.

### Screen recognition and interruptions

Army Recipes, Cookbook, Crafted Defense, Ranked, tiered Legend, Guardian, Hero Journey, Global Chat, Chain Offers, and fast-forward add or move controls. Each surface requires dated fixtures, redaction review, recognition assertions, and bounded safe actions.

### Emulator support

LDPlayer9 and MuMu adapters are present on the first compatibility branch, but support remains gated on Windows instance, ADB, background capture, input, zoom, restart, and shutdown evidence.

### Packaging and inherited binaries

The inherited tree contains executable, DLL, and archive artifacts. Each must receive provenance, license, hash, source, and reproducible-build treatment before a new release.

## Test requirements

The release gate requires:

- repository integrity and secret-pattern audit;
- AutoIt syntax checks on baseline and current AutoIt releases;
- executable run-contract tests;
- canonical 860×732 current-client fixtures;
- runtime-evidence records pinned to exact commits;
- clean-profile startup;
- controlled emulator and route smoke tests;
- reproducible packaging and artifact hashes.

## Current status

The source foundation, architecture, run contracts, emulator adapters, UI metadata, fixture contract, evidence registry, and current-game data model are staged in stacked draft PRs. Full current-client recognition and controlled end-to-end execution remain intentionally blocked until their evidence exists.
