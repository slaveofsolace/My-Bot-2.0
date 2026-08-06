# Baseline audit — 2026-08-06

## Decision summary

The unified project will use the official MyBot v8.2.0 `develop` source as its base, selectively port current compatibility work from xbebenkMod, and reimplement the useful public behaviors described by Clash-AutoLoot without copying or inspecting its compiled application.

The first source-complete branch is `integration/unified-foundation`. It was created from upstream commit `8ad6e5a552347acc2fcb8048d30262e2735a0c33` and is intentionally separate from the repository's existing `master` branch.

## Repository state

### Target repository

The previous `master` branch points at the v8.2.0 release commit but contains release metadata rather than the runnable AutoIt tree. That made it unsuitable as an integration base. The new integration branch restores the source directories and entry points, including:

- `MyBot.run.au3`
- `MyBot.run.version.au3`
- `COCBot/`
- `CSV/`
- `Languages/`
- `Help/`
- supporting images, OCR data, libraries, watchdog code, and legacy compiled artifacts

The main entry point is a monolithic AutoIt bootstrap. It initializes global configuration, emulator discovery, the GUI, the watchdog, image/OCR systems, profile storage, and the main loop through a broad include graph.

### Upstream evaluation

| Source | Finding | Integration decision |
| --- | --- | --- |
| `MyBotRun/MyBot` | v8.2.0 is the newest official source baseline found. It targets the April 2025 game line and includes TH17-era logic. | Use as the source foundation. |
| `xbebenk/MBR_xbebenkMod` | Actively maintained through July 30, 2026. It contains recent emulator, Builder Base, popup, obstacle, scenery, and UI-compatibility fixes, but its core is based on v7.9.9. | Port changes by feature and file. Do not replace the v8.2.0 core wholesale. |
| `clashautoloot/Clash-AutoLoot` | The public repository contains a product README but no application source or source license. Releases are compiled. | Use only as a clean-room product-requirements reference. Do not copy or reverse engineer its implementation. |
| `muratcandegirmenci78-lab/canmurat` | Its visible history matches the v8.2.0 MyBot release lineage and does not provide a meaningful current delta. | No import planned. Keep as a lineage reference. |

Pinned commits and import rules are stored in `/upstreams.lock.json`.

## Material compatibility gap

The baseline predates more than a year of game changes. This is not a single template update. Later releases changed navigation, account state, army data, hero/equipment data, matchmaking, battle controls, chat surfaces, shops, event dialogs, and persistent village objects.

High-impact gaps include:

1. **Town Hall 18 data and imagery** — new buildings, defenses, troops, spells, Guardians, levels, costs, and upgrade ranges.
2. **Six-hero support** — Dragon Duke and later Hero Hall/Profile/Blacksmith layout changes require arrays, GUI controls, OCR regions, activation logic, and profile migration to stop assuming the prior hero count.
3. **Ranked battle separation and Legend League tiers** — the attack state machine must distinguish regular, ranked, tournament, and tiered Legend flows rather than treating the old attack path as universal.
4. **Training removal and Cookbook changes** — older queue, timer, boost, and readiness assumptions must be audited even where v8.2.0 partially addressed the transition.
5. **Hero Journey and new equipment** — persistent Hero Hall alerts, reward-track dialogs, equipment ordering, new currencies/rewards, and quest overlays can interrupt existing upgrade paths.
6. **Global Chat** — the redesigned chat button and new Groups, Communities, and Town Square surfaces affect safe coordinates, chat detection, donation navigation, popup recovery, and account safety.
7. **Fast-forward live battles** — a new in-battle control appears after 120 seconds in supported modes. Existing end-battle and timeout logic must avoid mistaking it for another control.
8. **Builder Base changes** — additional builder state, new crafted-defense interactions, altered progression, new event objects, and current emulator support all require review.
9. **August 2026 events** — Clash of Cards adds card-pack reveal sequences, a collection screen, Trader flows, chat requests, new HUD access points, and a persistent village decoration. Chief's Chronicles adds another left-side village entry and a multi-screen experience near the Trader.
10. **Seasonal and promotional windows** — chain offers, event shops, tasks, tutorials, scenery changes, and temporary army injections expand the set of screens that can block normal navigation.

The detailed matrix is maintained in `docs/compatibility/GAME_UPDATE_MATRIX.md`.

## Architecture findings

### Strengths

- Mature feature coverage across farming, upgrades, donations, Clan Games, Builder Base, multiple profiles, emulator management, notifications, and scripted attacks.
- A large existing library of image templates, OCR assets, localized strings, and recovery routines.
- Profile-based configuration and a watchdog are already established.
- GPLv3 source history provides a lawful basis for combining compatible open-source changes when attribution is preserved.

### Risks

#### Global state and include coupling

Most subsystems share global variables and are assembled through large AutoIt include files. A small data-model change, such as adding a hero or troop, can affect GUI arrays, config serialization, OCR, attack deployment, donation, upgrade logic, and reports at once.

#### Pixel and coordinate coupling

A large portion of behavior depends on fixed regions, colors, coordinate tables, and image templates. Game UI changes can create false positives that look like valid state transitions. Compatibility work must update both recognition and the recovery path used when recognition fails.

#### Mixed source and release artifacts

Compiled `.exe` and native library files are committed beside source. Their provenance, build flags, signatures, and reproducibility are not currently enforced. Releases should eventually be generated from a documented build pipeline rather than inherited binaries.

#### No dependable automated test gate

There is no repository-level CI gate that checks local includes, source provenance, obvious secrets, required documentation, or build artifacts. Full gameplay tests also require a controlled Windows test environment and approved accounts. Static checks will be added first; deterministic screenshot/state fixtures should follow.

#### Legacy installation guidance

Existing instructions reference obsolete Windows versions and rely heavily on external forum links. The repository needs a source-first Windows 10/11 guide, exact supported tool versions, emulator compatibility status, fresh-profile requirements, and a troubleshooting table.

#### Configuration migration risk

The project warns users not to reuse old configuration files, but there is no explicit schema version or migration contract. New UI and feature work should not write directly into an undocumented set of legacy INI keys without a versioned adapter.

#### Update and popup handling are scattered

New game windows are typically handled by adding local checks in existing flows. That scales poorly. A centralized screen registry and interruption dispatcher should own recognition priority, dismiss/enter behavior, retry limits, and diagnostic capture.

## Clean-room feature scope from Clash-AutoLoot

The following public behaviors are reasonable requirements for a new implementation:

- a focused run dashboard
- explicit Home Village and Builder Base modes
- strategy selection with clear prerequisites
- session duration and stop conditions
- star-bonus mode
- multi-account queues
- wall-upgrade rules
- Builder Base resource-cart collection
- visible run statistics and recent-action history

The following are not integration targets:

- license-server code or machine-binding behavior from a closed build
- claims of being undetectable
- ban-wave avoidance
- input randomization intended to evade enforcement
- protected code, assets, or implementation details obtained from compiled releases

## Initial implementation order

### Phase 0 — source foundation

- Create the source-complete integration branch. **Done.**
- Pin upstream commits and import rules. **Done.**
- Add the initial audit, compatibility matrix, architecture plan, install guide, and merge rules. **In progress.**
- Add static repository checks and CI. **Next.**

### Phase 1 — compatibility inventory

- Build a machine-readable catalog of troops, spells, heroes, equipment, buildings, windows, and templates.
- Identify all fixed-size hero/troop/equipment arrays.
- Inventory screen-recognition entry points and recovery behavior.
- Diff xbebenk's July 2026 changes by subsystem against the v8.2.0 baseline.
- Add screenshot fixtures for known Home Village, Builder Base, attack, Hero Hall, chat, shop, event, and popup states.

### Phase 2 — low-risk compatibility ports

- Emulator discovery and ADB addressing fixes.
- Generic popup and interruption handling.
- Current obstacle/chest/scenery guards.
- Builder Base navigation fixes.
- Data additions that do not alter the main attack state machine.

Each port must identify its upstream commit, explain adaptation to v8.2.0, and include a reproducible check.

### Phase 3 — current game model

- TH18 and six-hero model.
- current troop, spell, equipment, building, wall, cost, and level tables
- Ranked/Legend routing
- Hero Journey and current Hero Hall/Blacksmith flows
- current attack bar and army interfaces

### Phase 4 — clean-room feature merge

- run-plan model
- account queue
- stop-condition engine
- Home Village/Builder Base strategy adapters
- wall and resource automation rules
- operator-readable statistics

### Phase 5 — UI replacement

The UI project should consume stable engine services rather than directly mutating legacy globals. A compatibility adapter can bridge the old AutoIt controls during migration. The UI handoff document defines the required screens, component behaviors, accessibility rules, descriptions, and status language.

### Phase 6 — packaging and release

- source-based build instructions
- dependency inventory and notices
- deterministic release manifest and checksums
- signed binaries where available
- fresh-profile and migration validation
- smoke-test evidence for each supported Windows/emulator combination

## Validation status

This audit establishes source lineage and performs a structural review. It does not claim that the bot currently works against the August 2026 game client. No live game execution, Windows compilation, or emulator smoke test has been completed in this environment. Those results must be recorded separately and must not be inferred from source recency alone.
