# My Bot 2.0 continuation handoff

**Prepared:** August 7, 2026  
**Repository:** `slaveofsolace/My-Bot-2.0`  
**Default branch:** `master`  
**Code baseline summarized here:** `62cf8b06537fdedb91eb0dc0f52089c06935e1e8`  
**Baseline tree:** `68ca77c6b3f693175a564861d14dfaa28d63add7`  
**Merged implementation PR:** [#6 — Consolidate the integration stack, repair the run engine, and add a working Run Planner](https://github.com/slaveofsolace/My-Bot-2.0/pull/6)

This document is the continuation point for the next implementation pass. It is intentionally
self-contained. The code state described below is commit `62cf8b0`; this handoff itself is added in a
later documentation-only commit and does not change runtime behavior.

## Operator directives

These are the current owner decisions and should be treated as project requirements:

1. Work lands on `master`, the repository's default branch.
2. Do not spend more time deleting or rewriting the stale
   `claude/coc-bot-merge-ui-kobgds` branch. Leave it as-is.
3. The owner reports receiving express written permission from Fandom to use automated access for
   the Clash of Clans Wiki. The approval email is retained privately and is not committed.
4. The native AutoIt Run Planner should ultimately be replaced by the most visually polished and
   easy-to-navigate version of the local web interface. The current code has not completed that
   replacement.
5. Preserve the project's evidence-first support model. A catalog entry or statically valid adapter
   is not the same as demonstrated support.
6. Do not add credential storage to the planner, queue, run plan, or telemetry.
7. Do not spend implementation time on branch-history cosmetics before current-client data,
   fixtures, recognition, and UI integration.

## Current status in one page

The repository is a source-complete MyBot.run v8.2.0 AutoIt application with a new orchestration
layer, current-game descriptors, emulator adapters, generated planner metadata, a native Run Planner,
a local browser Run Planner, validators, and Windows CI.

The non-client parts are structurally healthy:

- the complete local validation suite passes;
- the generated AutoIt files are current;
- all local include paths resolve;
- the AutoIt linter passes across 369 AutoIt files;
- GitHub CI passes on the baseline commit;
- Windows Au3Check and runtime contract tests pass on AutoIt 3.3.16.1 and 3.3.18.0.

The project is **not** current-client operational support:

- all 20 required current-client fixtures are missing;
- no runtime evidence records are committed;
- all 24 capability entries are blocked from support review;
- LDPlayer 9 and MuMu adapters have not been run on real hardware;
- no current-client battle route has controlled end-to-end evidence;
- the wiki ingest has only an offline parser selftest and has never completed a live production run;
- the local web planner writes a plan file, but no AutoIt runtime code currently reads that file;
- the web interface is an additional front-end, not yet the replacement for the native planner.

## Verified working state

### Baseline commit

`master` resolves to:

```text
62cf8b06537fdedb91eb0dc0f52089c06935e1e8
```

Commit title:

```text
Add a local web front-end for the Run Planner
```

### GitHub Actions

The baseline commit has two successful workflows:

| Workflow | Run | Result |
|---|---:|---|
| CI | `31187870829` | success |
| Windows AutoIt validation | `31187870818` | success |

The Windows matrix contains two successful jobs:

| AutoIt | Job | Result |
|---|---:|---|
| 3.3.16.1 | `92896927464` | success |
| 3.3.18.0 | `92896927388` | success |

Each Windows job:

- downloads the official portable AutoIt package;
- checks its Authenticode signature;
- runs Au3Check on the three entry points and three AutoIt test scripts;
- executes the three contract-test scripts;
- uploads validation evidence.

The checked entry points are:

```text
MyBot.run.au3
MyBot.run.MiniGui.au3
MyBot.run.Watchdog.au3
```

The executed AutoIt tests are:

```text
tests/autoit/RunContractsTest.au3
tests/autoit/GameCatalogTest.au3
tests/autoit/RunEngineTest.au3
```

### Fresh local validation performed for this handoff

The following commands were run against a fresh source export of commit `62cf8b0`. Every command
returned exit code `0`:

```text
python -m compileall -q tools
python tools/repo_audit.py
python tools/lint_autoit.py --all
python tools/validate_game_catalog.py
python tools/generate_game_catalog_autoit.py --check
python tools/generate_run_planner_autoit.py --check
python tools/verify_current_game_model.py
python tools/verify_current_client_compat.py
python tools/validate_ui_metadata.py
python tools/preview_run_planner.py
python tools/planner_ui.py --selftest
python tools/validate_current_client_fixtures.py
python tools/validate_runtime_evidence.py
python tools/evaluate_support_readiness.py
python tools/wiki_ingest.py selftest
```

Key measured results:

| Check | Result |
|---|---|
| Repository files | 2,611 |
| AutoIt files | 369 |
| Local includes | 417 |
| Missing includes | 0 |
| Repository-audit errors | 0 |
| Repository-audit warnings | 1 |
| Game-catalog sources | 11 |
| Game-catalog updates | 9 |
| Battle surfaces | 7 |
| Heroes | 6 |
| Screen states | 17 |
| Current-game verifier checks | 66 passed |
| Current-client verifier checks | 82 passed |
| Planner sections | 12 |
| Planner settings | 37 |
| Native planner controls in geometry preview | 113 |
| Fixture inventory | 20 total, 0 complete |
| Runtime evidence | 0 records |
| Capabilities ready for support review | 0 of 24 |

Expected warnings:

1. The repository carries 17 inherited binary/archive artifacts whose provenance is not yet
   established for a new release.
2. Planner sections are valid but not stored in display order in the JSON source.
3. No runtime-evidence records are committed.

No new emulator, Windows-client, or game-client run was performed during this handoff pass.

## What was completed during the merge

### Source-complete v8.2.0 foundation

PR #6 consolidated the prior integration stack into a runnable source tree and preserved the
historical `master` lineage. The foundation is the MyBot.run v8.2.0 source, not the old sparse
release-metadata-only tree.

The merge retained:

- AutoIt application source;
- GUI modules;
- recognition images and OCR resources;
- language resources;
- libraries and inherited binaries;
- Mini GUI and Watchdog entry points;
- upstream GPL notices and provenance records.

`upstreams.lock.json` records the source roles and import policies.

### Broken stacked work repaired

PR #6 fixed failures left by the earlier stacked branches:

- committed the previously missing generated game catalog;
- corrected the generation/verification order;
- wired the current game catalog and screen-state registry into the compatibility entry point;
- corrected UI metadata identifier validation;
- implemented the run-intent, Hero-loadout, and battle-quota modules that earlier PR text had
  described but had not actually supplied;
- consolidated branch-specific CI into current read-only validation workflows;
- added a cross-platform AutoIt linter.

Do not recreate old `apply_*` migration workflows or assume the old stacked branches contain a
better final implementation. `master` is the consolidated source of truth.

### Run engine

The new orchestration layer is under `COCBot/functions/Run/`.

#### `RunPlan.au3`

Defines the operator's requested session:

- mode;
- strategy;
- duration;
- battle limit;
- Star Bonus stop;
- failure limit;
- Gold, Elixir, and Dark Elixir targets;
- upgrade policy;
- account-queue reference.

The run plan intentionally contains no credentials.

#### `AccountQueue.au3`

Provides deterministic local-profile ordering, enabled/disabled entries, optional cycling, and
duplicate prevention. It stores local profile references only.

#### `BattleRoute.au3`

Represents exact route identity and readiness. Regular, Ranked, Legend, and Builder Base are not one
generic multiplayer route.

#### `HeroLoadout.au3`

Models the current six-Hero Home Village catalog with a maximum of four active slots. It validates:

- catalog membership;
- duplicate selection;
- Town Hall unlock requirements;
- slot count;
- removal of selections that become invalid when Town Hall is lowered.

#### `BattleQuota.au3`

Separates published attack limits from observed remaining attacks:

- Regular Battles are catalogued as unlimited.
- Finite or UI-reported modes begin unobserved.
- A published maximum is never treated as the live remaining count.
- Consumption decrements an observed quota and rejects over-consumption.

#### `RunIntent.au3`

Binds:

- one validated run plan;
- one exact battle surface;
- one validated Hero loadout;
- the matching attack quota;
- an optional local profile reference.

This is the gate that prevents choosing one mode and accidentally executing whichever old screen
coordinates respond.

#### `RunSession.au3`

Implements a deterministic state machine:

```text
ready
running
stopping
completed
failed
```

It records battle counts, success/failure counts, loot totals, stop reason, last error, and
verification state.

#### `RunVerification.au3`

Implements the evidence boundary:

- a demonstrated route may remain verified;
- an undemonstrated route can run only as a diagnostic observation;
- diagnostic state is a one-way latch;
- no code moves a diagnostic session back to verified;
- the attack-quota gate is not relaxed by diagnostic mode.

#### `RunEvent.au3`

Produces structured JSONL events for lifecycle, route, battle, loot, warning, and error state. It is
designed to exclude credentials, session secrets, chat contents, and machine identity.

### Current-game source model

The current model is split across:

```text
config/game/current-client.json
config/game/battle-surfaces.json
config/game/heroes.json
config/game/screen-states.json
config/current-client-capabilities.json
```

The JSON files are authoritative. They generate:

```text
COCBot/functions/Game/GameCatalog.generated.au3
```

Runtime query and gate code lives in:

```text
COCBot/functions/Game/GameCatalog.au3
COCBot/functions/Game/ScreenStateRegistry.au3
```

The current compact model records:

- Town Hall 18 as the maximum;
- six Home Village Heroes and four active slots;
- Regular, Ranked, Revenge, Legend III, Legend II, Legend I, and Builder Base surfaces;
- current screen states for Army Recipes, Cookbook, Crafted Defenses, battle entry surfaces,
  fast-forward, TH18, Guardians, six-Hero UI, Dragon Duke, Hero Journey, Global Chat, Builder Base,
  and Chain Offers;
- capability status and evidence requirements.

This is a compatibility ledger and runtime projection, not the complete game database.

### Emulator adapters

New modules:

```text
COCBot/functions/Android/AndroidLDPlayer9.au3
COCBot/functions/Android/AndroidMumu.au3
```

LDPlayer 9 includes the multi-instance ADB formula:

```text
5554 + (2 * instance index)
```

MuMu reads the instance-specific `ADB_PORT_EX` value rather than assuming a fixed formula.

Both adapters provide discovery, launch/shutdown, ADB selection, shared-folder discovery,
resolution/DPI setup, window lookup, background mode, reboot setup, and zoom hooks.

Important decision: the compatibility entry point belongs only in the main build. Do not move it
into a shared include reached by the Mini GUI or Watchdog; those builds do not load the Android core
and will fail on missing functions/globals.

### Native Run Planner

The native planner is implemented in:

```text
COCBot/GUI/MBR GUI Design Run Planner.au3
COCBot/GUI/MBR GUI Control Run Planner.au3
COCBot/GUI/RunPlannerMetadata.generated.au3
```

Source metadata:

```text
config/ui/run-planner.settings.json
```

Generators and validators:

```text
tools/generate_run_planner_settings.py
tools/generate_run_planner_autoit.py
tools/validate_ui_metadata.py
tools/preview_run_planner.py
```

Current native surface:

- 12 tab pages;
- 37 settings;
- 113 controls in the layout model;
- multiline tab strip;
- required labels are emphasized;
- selection color reflects availability;
- each meaningful option carries a summary, description, prerequisites, warning, and disabled reason;
- Apply constructs a real `RunIntent` and reports the engine's readiness decision.

The 12 tab pages are:

```text
Battle
Heroes
Emulator
Army
Search
Limits
Loot
Donate
Events
Upkeep
Notify
Debug
```

### Local web Run Planner

Implemented by:

```text
tools/planner_ui.py
ui/planner.html
docs/development/PLANNER_UI.md
```

Current behavior:

- standard-library local HTTP server;
- loopback binding at `127.0.0.1`;
- reads the same planner metadata as the native UI;
- dark three-column layout;
- section navigation stored in the URL hash;
- main control pane;
- contextual detail pane;
- event feed from `logs/run-events.jsonl`;
- writes validated local plans to `config/run-plan.local.json`;
- has a CI selftest for defaults, numeric clamping, unknown settings, and invalid options.

The web UI is currently an additional front-end. It has not replaced the native planner.

### Wiki ingest proof of concept

Implemented by:

```text
tools/wiki_ingest.py
docs/development/WIKI_INGEST.md
data/wiki-staging/.gitkeep
data/wiki-parsed/.gitkeep
```

Current implementation:

- MediaWiki API rather than arbitrary HTML crawling;
- separate network fetch and offline parse commands;
- ten direct category groups;
- revision IDs and source URLs at the page level;
- simple infobox extraction;
- simple level-table extraction;
- offline selftest;
- parsed data remains outside `config/game/`.

The user now reports express written Fandom permission. The current tool still requires substantial
production work described below; permission alone does not make the proof of concept complete.

### Validation and CI

Current workflows:

```text
.github/workflows/ci.yml
.github/workflows/windows-autoit.yml
```

Current tooling includes:

```text
tools/lint_autoit.py
tools/repo_audit.py
tools/validate_game_catalog.py
tools/verify_current_game_model.py
tools/verify_current_client_compat.py
tools/validate_ui_metadata.py
tools/validate_current_client_fixtures.py
tools/validate_runtime_evidence.py
tools/evaluate_support_readiness.py
tools/preview_run_planner.py
```

Generated files are drift-checked. Do not hand-edit them:

```text
COCBot/functions/Game/GameCatalog.generated.au3
COCBot/GUI/RunPlannerMetadata.generated.au3
```

## Important implementation decisions

### JSON catalogs are authoritative

Edit the JSON source and rerun the generator. Do not patch generated AutoIt tables manually.

### Exact surfaces are preserved end-to-end

Regular, Ranked, Revenge, Legend tiers, and Builder Base have different rules. Do not collapse them
back into a single multiplayer boolean or generic attack route.

### Live quota is not a published maximum

Do not initialize a finite route's remaining attacks from a release-note maximum. The live count
must be observed from the current client.

### Verification is evidence-based

The status vocabulary is deliberate:

| Status | Meaning |
|---|---|
| `catalogued` | The game feature is documented; recognition/execution are not supplied. |
| `adapter-added` | Driver code exists; controlled hardware evidence is missing. |
| `engine-added` | Reusable contract and static tests exist; runtime evidence is missing. |
| `supported` | Required fixtures and controlled runtime evidence both pass review. |

Do not promote a capability because its code compiles.

### Diagnostic state is one-way

Diagnostic runs are observations, not proof. Do not add a reset that turns a diagnostic run into a
verified run.

### Legacy source moves are deferred

The inherited application has hundreds of path-sensitive includes and asset references. Avoid broad
directory reorganization until moves are protected by include-graph tests and behavior-neutral
validation.

### Selective upstream adaptation

`xbebenk/MBR_xbebenkMod` is useful but derives from an older MyBot architecture. Do not overlay it
wholesale. Adapt a specific fix against the v8.2.0 code only when the underlying defect is relevant.

`Clash-AutoLoot` is a behavior reference only. Do not unpack, decompile, or copy its compiled
implementation.

## UI status and continuation requirements

### Completed

- Native planner renders all current metadata.
- Layout geometry validation passes with no errors or warnings.
- Native planner option surface was expanded from 16 to 37 settings.
- The local web UI reads the same metadata and displays disabled reasons.
- Web plan submission is schema-aware at a basic level.
- The web server contract selftest passes.
- Both UIs share one metadata source.

### Incomplete or incorrect

1. **The native UI has not been replaced.**  
   The user explicitly wants the polished local web experience to become the primary planner.

2. **The web plan is not consumed by the AutoIt engine.**  
   `config/run-plan.local.json` is written only by `tools/planner_ui.py`. A repository-wide search
   finds no AutoIt loader or runtime reader. `docs/development/PLANNER_UI.md` currently says the
   engine reads the file; that statement is ahead of the implementation.

3. **Boolean coercion is incorrect.**  
   `validate_plan()` uses `bool(value)`, so JSON string `"false"` becomes `true`.

4. **POST size is unbounded.**  
   `Content-Length` is trusted without a maximum or negative-length check.

5. **Event tailing is not bounded.**  
   The whole JSONL file is read into memory before the last records are selected.

6. **Plan writes are not atomic.**  
   The server writes directly to the final file and can leave a truncated plan if interrupted.

7. **The web UI is visually functional, not the final design-system pass.**  
   It is one HTML file with inline CSS/JavaScript. It has no overview dashboard, run history,
   account workspace, data browser, accessibility audit, or polished responsive shell described in
   `docs/ui/UI_HANDOFF.md`.

8. **Fresh interactive screenshot QA was not completed in this handoff environment.**  
   Geometry validation and the server selftest pass; the baseline commit's prior CI is green. Do a
   new desktop/mobile browser pass before changing the UI and again before handoff.

### Recommended replacement approach

Short-term, lowest risk:

1. Make the web Control Center the authoritative planner UI.
2. Reduce the native Run Planner tab to a small launcher/status bridge:
   - start or detect the local server;
   - open the browser;
   - show current plan path and server health;
   - retain a safe fallback message when Python is unavailable.
3. Add an AutoIt plan loader that:
   - atomically reads `config/run-plan.local.json`;
   - validates every field again;
   - converts the flat metadata IDs into `RunPlan`, `HeroLoadout`, `BattleQuota`, and `RunIntent`;
   - reports exact errors in the native log and web UI.
4. Only consider WebView2 embedding after the bridge is stable; do not introduce it as a prerequisite
   for the first working replacement.

## Known issues and technical debt

### P0 — source-ledger correctness

#### Guardian Builder requirement is wrong

`config/game/current-client.json` currently says Guardian upgrades do not require a Builder. The
official Town Hall 18 material says a free Builder is required.

Required correction:

- change the fact;
- represent `builder_required: true` in a machine-readable record;
- add a regression check tied to the official source ID.

#### Sound of Clash URL is noncanonical

The April 2026 source path should be reconciled to the canonical official page and checked for
unexpected redirects.

#### Guardian taxonomy is inconsistent

The TH18 update lists `heroes` as an affected catalog even though Guardians are a distinct defensive
system. The compact schema has no `guardians` catalog enum.

Required correction:

- add a Guardian entity/catalog projection;
- remove Guardian implications from the Hero catalog;
- extend affected-catalog enums beyond battle surfaces, Heroes, and screen states.

### P0 — web planner/engine contract

The documentation says the engine reads `config/run-plan.local.json`; the code does not. Do not
continue visual work without deciding and implementing the actual bridge.

### P0 — production wiki acquisition gate

The owner reports written permission, but the repository has no non-sensitive permission record,
terms record, or robots snapshot contract.

Before a production run:

- add a permission record that states the approval basis without publishing private email text;
- fetch and hash `robots.txt`;
- fail closed on an unavailable or disallowing robots policy;
- query `siteinfo`;
- run a three-page trial: one troop, one village-specific building, one Hero;
- archive request/response metadata.

### P1 — wiki ingest architecture

`tools/wiki_ingest.py` is a proof of concept. It currently:

- pulls only ten direct categories;
- excludes subcategories/files through namespace filtering;
- has no recursive category graph;
- has no namespace-zero `allpages` reconciliation;
- has no redirect/disambiguation disposition report;
- parses nested wiki structures with regular expressions;
- strips templates/HTML before field-level provenance exists;
- records provenance only at the page level;
- does not explicitly honor `Retry-After`;
- can report category failures and still exit success;
- silently skips pages with no revision;
- has never run against the live Fandom API;
- has no image metadata inventory;
- has no canonical entity/level/assertion/change/asset schema.

Production architecture should remain API-first and revision-pinned:

```text
permission/terms/robots preflight
  -> siteinfo
  -> recursive category graph
  -> allpages reconciliation
  -> redirect and alias resolution
  -> immutable revision staging
  -> revision-pinned action=parse metadata
  -> offline template/table extraction
  -> normalized entity/level/assertion records
  -> conflict and missing-data reports
  -> reviewed repository projections
```

Do not write crawler output directly into authoritative runtime catalogs.

### P1 — canonical game-data model is incomplete

The compact runtime catalogs contain identities and route/screen descriptors, not all Clash of
Clans values.

Missing domain coverage includes:

- Home Village buildings, defenses, traps, walls, resources, storages, collectors;
- Builder Base army/buildings/resources/progression;
- Clan Capital districts, buildings, troops, spells, and prerequisites;
- troop, Super Troop, spell, Siege Machine, spawned-unit, pet, equipment, Guardian, and ability
  progression;
- per-level HP, DPS, damage, attack speed, range, housing, costs, durations, prerequisites, and
  maximum levels by hall;
- Army Recipes and Cookbook structure;
- update and balance history;
- asset metadata and licensing status;
- assertion-level provenance.

The next data layer should use separate versioned schemas for:

```text
entity
level
assertion
relationship
ability
change
asset
source
crawl run
extraction error
```

Unknown must be `null`; zero must mean a verified zero.

### P1 — fixture and recognition system is only a placeholder inventory

Current state:

- 20 required fixtures;
- all 20 are `missing`;
- no negative examples;
- no theme/scenery matrix;
- no locale;
- no client build/channel;
- no emulator version;
- no DPI;
- no bounding boxes/polygons;
- no expected recognition outcomes.

The validator checks dimensions, hash, and basic review metadata but not recognition annotations or
environmental variants.

`builder.home.extra-builder` is also named as if it were a Home Village capture; rename it to a
Builder Base-specific ID with migration/alias handling.

### P1 — capture helper was not completed

The interrupted Claude session screenshot showed work beginning on:

```text
tools/capture_fixture.py
```

That file is not in `master`.

Implement it rather than assuming it exists. Recommended commands:

```text
list
add <fixture-id> <png>
redact <fixture-id>
verify <fixture-id>
```

It should enforce the manifest dimensions, compute SHA-256, write schema-valid metadata, preserve
privacy-review state, and never alter network state.

### P1 — runtime evidence and hardware work are absent

`config/runtime-evidence.schema.json` and validation exist, but there are zero records.

Required evidence includes:

- clean-profile startup;
- LDPlayer 9 instance 0 and non-zero instance;
- MuMu instance 0 and non-zero instance;
- ADB reconnect;
- window recreation;
- background capture;
- clicks and drags;
- zoom;
- restart and shutdown;
- route separation;
- exact battle-surface entry;
- live remaining-attack reading;
- deterministic session stop conditions.

### P2 — inherited binary provenance

The repository audit warns about 17 inherited executables, DLLs, or archives. Before a new release:

- inventory hashes;
- identify source/build version;
- document license/provenance;
- remove unnecessary binaries;
- establish reproducible build output;
- create a signed release manifest.

### P2 — documentation drift

Known examples:

- the web planner documentation says the engine reads the plan file, but no loader exists;
- wiki documentation overstates the completeness and legal simplicity of the proof-of-concept
  extraction;
- the UI metadata validator warns that sections are not stored in display order.

Correct documentation together with implementation, not separately months later.

## Files to inspect first

### First 15 files

1. `docs/development/CONTINUATION_HANDOFF_2026-08-07.md`
2. `README.md`
3. `docs/development/ENGINEERING_NOTES.md`
4. `docs/ui/UI_HANDOFF.md`
5. `docs/development/PLANNER_UI.md`
6. `tools/planner_ui.py`
7. `ui/planner.html`
8. `COCBot/GUI/MBR GUI Design Run Planner.au3`
9. `COCBot/GUI/MBR GUI Control Run Planner.au3`
10. `config/ui/run-planner.settings.json`
11. `COCBot/functions/Run/RunIntent.au3`
12. `COCBot/functions/Run/RunPlan.au3`
13. `COCBot/functions/Run/RunVerification.au3`
14. `tools/wiki_ingest.py`
15. `config/game/current-client.json`

### Then inspect

```text
COCBot/functions/Run/HeroLoadout.au3
COCBot/functions/Run/BattleQuota.au3
COCBot/functions/Run/BattleRoute.au3
COCBot/functions/Run/RunSession.au3
COCBot/functions/Run/RunEvent.au3
COCBot/functions/Game/GameCatalog.au3
COCBot/functions/Game/ScreenStateRegistry.au3
COCBot/functions/Other/CurrentClientCompat.au3
config/current-client-capabilities.json
tests/fixtures/current-client/manifest.json
tools/validate_current_client_fixtures.py
tools/validate_game_catalog.py
tools/verify_current_client_compat.py
tools/verify_current_game_model.py
.github/workflows/ci.yml
.github/workflows/windows-autoit.yml
```

## Recommended next steps

### 1. Correct the authority layer before importing more data

Acceptance:

- Guardian Builder statement fixed;
- canonical Sound of Clash URL recorded;
- Guardian catalog/taxonomy represented explicitly;
- regression tests pass;
- generated AutoIt refreshed and drift-free.

### 2. Make the web planner contract real and safe

Acceptance:

- strict boolean parsing;
- maximum request-body size;
- bounded reverse event tail;
- atomic plan writes;
- loopback Host/Origin checks;
- AutoIt loader for the plan file;
- web and native status agree;
- docs no longer claim an unimplemented read path;
- tests cover `"false"`, `"0"`, `0`, `null`, arrays, oversized bodies, and interrupted writes.

### 3. Replace the native planner with a web-primary launcher bridge

Acceptance:

- native tab no longer duplicates all 37 controls;
- native tab launches/detects the Control Center and shows health;
- web UI handles the full planning flow;
- desktop and mobile browser QA completed;
- keyboard and reduced-motion behavior checked;
- no setting from `config/ui/run-planner.settings.json` disappears.

### 4. Implement the fixture-capture helper and richer fixture suites

Acceptance:

- `tools/capture_fixture.py` added with list/add/redact/verify flow;
- metadata includes client build, locale, emulator/version, DPI, scenery/theme, source channel,
  assertions, annotations, and negative expectations;
- fixture IDs are context-correct;
- validator checks the new contract;
- at least the three-page/three-screen trial path is documented.

### 5. Replace the wiki proof of concept with the production evidence pipeline

Acceptance:

- permission/robots/siteinfo preflight;
- resumable request manifest;
- required-group failures exit nonzero;
- recursive categories plus `allpages` reconciliation;
- revision-pinned immutable staging;
- rendered table geometry with rowspan/colspan support;
- raw, expanded, and normalized values preserved;
- assertion-level provenance;
- unknown-template/table-shape reports;
- asset metadata reference pass;
- canonical JSONL handoff and review CSVs;
- no direct promotion to runtime catalogs.

### 6. Run the authorized wiki trial, then the full inventory

Trial pages should exercise:

- one troop;
- one Home/Builder/Capital variant family;
- one Hero.

Only proceed to the full crawl after raw, rendered, and normalized trial values agree.

### 7. Generate reviewed runtime projections

Generate compact files from the canonical handoff rather than manually growing
`config/game/heroes.json` and similar projections.

Acceptance:

- source handoff version recorded;
- import diff generated;
- official conflicts block promotion;
- hand edits become override assertions;
- generated projections are deterministic.

### 8. Acquire current-client fixtures and runtime evidence

Use approved fake/test accounts and controlled emulator environments. Do not promote any capability
until fixture and runtime gates pass.

### 9. Complete release engineering

Only after the core runtime is demonstrated:

- binary provenance;
- reproducible build;
- release hashes;
- signing;
- clean-machine install test;
- release notes that distinguish supported from catalogued behavior.

## Do not revert or duplicate

- Do not hand-edit generated AutoIt catalog or planner metadata files.
- Do not restore one-shot `apply_*` workflows or old branch-specific CI.
- Do not move `CurrentClientCompat.au3` into a shared include used by Mini GUI/Watchdog.
- Do not collapse exact battle surfaces into generic multiplayer logic.
- Do not reset a diagnostic session to verified.
- Do not use published attack maximums as live remaining quotas.
- Do not store credentials in account queues, plans, events, or UI.
- Do not mark adapters or features supported from static validation alone.
- Do not overlay the older xbebenk tree over v8.2.0.
- Do not copy or decompile Clash-AutoLoot.
- Do not move the legacy source tree broadly before path-sensitive behavior is covered.
- Do not write unreviewed wiki output directly into runtime JSON.
- Do not silently choose between conflicting official/wiki values.
- Do not redo stale-branch cleanup; the owner explicitly deprioritized it.
- Do not assume `tools/capture_fixture.py` or the web-to-AutoIt plan bridge already exists.

## Limitations of this handoff pass

This pass intentionally made no runtime changes. It did not:

- delete or rewrite stale branches;
- correct the source-ledger bugs;
- run a live Fandom crawl;
- import comprehensive game values;
- implement canonical entity/level/assertion schemas;
- implement `tools/capture_fixture.py`;
- replace the native UI;
- add the web-to-AutoIt plan loader;
- complete fresh interactive screenshot QA;
- run the Windows desktop application locally;
- run either emulator locally;
- capture current-client fixtures;
- produce runtime-evidence records;
- establish inherited-binary provenance.

The reliable validation evidence is static/local Linux validation plus the successful GitHub Windows
matrix on commit `62cf8b0`.

## Immediate Claude kickoff

Start from current `master` and run:

```bash
git checkout master
git pull --ff-only
python tools/repo_audit.py
python tools/lint_autoit.py --all
python tools/validate_game_catalog.py
python tools/planner_ui.py --selftest
```

Then verify:

```bash
git rev-parse HEAD
```

The first implementation slice should be **authority-layer fixes plus the real web-plan bridge**.
Keep it reviewable and do not mix it with the full wiki crawl or a broad source-tree move.

Recommended first slice:

```text
1. Fix Guardian/canonical-source/taxonomy issues.
2. Harden tools/planner_ui.py.
3. Add tests for strict input handling and atomic writes.
4. Add an AutoIt loader that converts run-plan.local.json into validated engine objects.
5. Correct PLANNER_UI.md to match the actual integration.
6. Run all local validators and the Windows matrix.
```

After that slice is green, proceed to the web-primary native replacement and the authorized wiki
trial as separate commits.
