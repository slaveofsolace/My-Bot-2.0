# My Bot 2.0

A source-first rebuild of the MyBot Clash of Clans automation project for controlled, explicitly authorized testing. The project preserves the mature AutoIt feature base, brings current game and emulator compatibility into a reviewable integration line, and prepares the engine for a separate modern desktop UI.

> **Current status:** foundation and compatibility audit. The source branch is complete, but August 2026 game-client support has not yet passed Windows build, fixture, and emulator smoke-test gates.

## Use the correct branch

The runnable source and all new work are on:

```text
integration/unified-foundation
```

The existing `master` branch contains the prior v8.2.0 release metadata and is not the integration source baseline.

## What is being combined

| Source | Role |
| --- | --- |
| `MyBotRun/MyBot` v8.2.0 | Full AutoIt source foundation. |
| `xbebenk/MBR_xbebenkMod` | Selective current emulator, popup, Builder Base, image, and compatibility ports. Its older v7.9.9 core will not replace v8.2.0. |
| `clashautoloot/Clash-AutoLoot` | Public behavior reference for a focused dashboard, village modes, strategy selection, run limits, account queues, Star Bonus, walls, and Builder Base collection. No source or source license is published, so implementation is clean-room only. |
| `muratcandegirmenci78-lab/canmurat` | Lineage comparison. No meaningful current delta was identified. |

Exact reviewed commits and import rules are pinned in [`upstreams.lock.json`](upstreams.lock.json).

## Project direction

### Current-client compatibility

The game changed substantially after the v8.2.0 baseline. Work includes:

- TH18 units, defenses, levels, costs, walls, Guardians, and screens
- Dragon Duke and a data-driven six-Hero model
- regular Battles, Ranked Battles, tiered Legend League, Revenge, War, and Friendly routes
- current Army Recipes/Cookbook and no-training-time assumptions
- Hero Journey, current Hero Hall/Blacksmith/Profile flows, and equipment ordering
- Global Chat-safe navigation and donation handling
- live-battle fast-forward recognition
- Builder Base builder, cart, battle, shop, and upgrade changes
- current event, reward, Trader, shop, card-pack, chest, obstacle, and popup recovery
- current emulator discovery and instance addressing

The dated matrix is in [`docs/compatibility/GAME_UPDATE_MATRIX.md`](docs/compatibility/GAME_UPDATE_MATRIX.md).

### Unified operator experience

The planned UI keeps the original application's depth while replacing unexplained tabs and controls with:

- an environment and run overview
- a validated run planner
- detailed strategy and emulator selectors
- account queues and per-account overrides
- explicit stop conditions
- wall and upgrade rules with dry-run summaries
- readable activity history and diagnostics
- live, decision-useful metrics
- consistent descriptions, prerequisites, disabled reasons, and defaults
- keyboard navigation, reduced motion, scalable text, and light/dark themes

The full handoff is in [`docs/ui/UI_HANDOFF.md`](docs/ui/UI_HANDOFF.md).

## Quick development setup

### Requirements

- Windows 10 or Windows 11
- AutoIt 3.3.16.x
- SciTE for AutoIt, recommended
- Microsoft Visual C++ 2010 Redistributable, x86
- .NET Framework 4.5 or later Windows compatibility
- a separately installed Android environment supported by the branch being tested

### Clone

```powershell
git clone --branch integration/unified-foundation https://github.com/slaveofsolace/My-Bot-2.0.git
cd My-Bot-2.0
```

### Run the repository audit

```powershell
python tools/repo_audit.py --json audit-report.json
```

### Start from source

1. Open `MyBot.run.au3` in SciTE.
2. Run the AutoIt syntax check.
3. Start the script from source.
4. Use a fresh profile; do not copy an old configuration directory.
5. Verify emulator selection, capture, and Home Village recognition before enabling a feature.

The inherited tree contains compiled files and native libraries. They are not yet outputs of the new reproducible release process, so source-first development is preferred.

See [`docs/INSTALL.md`](docs/INSTALL.md) for the full setup, first-run checks, troubleshooting, and report template.

## Documentation

- [`docs/audit/BASELINE_AUDIT_2026-08-06.md`](docs/audit/BASELINE_AUDIT_2026-08-06.md) — source evaluation, structural findings, compatibility risks, and implementation order
- [`docs/compatibility/GAME_UPDATE_MATRIX.md`](docs/compatibility/GAME_UPDATE_MATRIX.md) — official game changes through August 6, 2026 and affected subsystems
- [`docs/architecture/REPOSITORY_PLAN.md`](docs/architecture/REPOSITORY_PLAN.md) — target architecture and phased file reorganization
- [`docs/development/MERGE_PLAYBOOK.md`](docs/development/MERGE_PLAYBOOK.md) — attributed GPL ports and clean-room implementation rules
- [`docs/ui/UI_HANDOFF.md`](docs/ui/UI_HANDOFF.md) — navigation, components, settings, charts, motion, accessibility, and engine boundary
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch, commit, provenance, validation, and review requirements
- [`SECURITY.md`](SECURITY.md) — private reporting, sensitive data, binaries, ADB, profiles, and release safety

## Repository checks

`.github/workflows/repository-audit.yml` runs a pinned, standard-library-only Python audit that checks:

- required project and policy files
- upstream commit pinning and import policies
- local AutoIt include resolution with Windows-style case handling
- common committed-secret patterns
- source/version metrics
- inherited executable, library, and archive inventory

A warning about inherited binaries is expected until provenance and source-based packaging are complete. Missing includes or likely secrets fail the workflow.

## Reorganization policy

The source tree will not be moved wholesale before its include graph and build are protected. Work proceeds in this order:

1. source foundation, provenance, audit, and CI
2. current game catalog and screenshot fixtures
3. low-risk emulator and interruption ports
4. TH18, six-Hero, Ranked, army, and current-client state changes
5. clean-room run-plan and account-queue features
6. modern UI through a stable engine adapter
7. behavior-neutral physical file moves
8. reproducible packaging, hashes, notices, signatures, and smoke-test evidence

## Authorization and account safety

Supercell's public fair-play policy prohibits unapproved gameplay bots and can permanently ban affected live accounts. This repository must be used only in environments and on accounts for which automation testing is explicitly authorized.

This project does not add or accept:

- detection-evasion or ban-avoidance features
- fingerprint spoofing
- claims that automation is undetectable or safe from enforcement
- credential collection
- automatic premium-currency spending without a narrow, explicit, off-by-default review
- closed-source code or assets extracted from compiled releases

This repository is not an official Supercell release and must not be represented as one.

## Licensing

The MyBot AutoIt source is distributed under GNU GPLv3. Preserve its notices and the attribution of every compatible upstream port. See [`License.txt`](License.txt), [`upstreams.lock.json`](upstreams.lock.json), and the inherited third-party notices before distributing a build.

Some inherited native libraries have separate or restrictive terms. Their presence in the historical tree does not establish permission to modify or redistribute them outside those terms. The release work will inventory each binary and replace or isolate unverifiable dependencies where practical.
