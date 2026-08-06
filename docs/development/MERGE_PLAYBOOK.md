# Merge playbook

This project combines compatible open-source work and independently implements selected public product behaviors. It does not use a repository overlay. Every change enters through a small, attributable port or a clean-room feature specification.

## Source classes

### Class A — baseline source

`MyBotRun/MyBot` v8.2.0 `develop` is the runnable foundation. Existing GPL notices and attribution remain intact.

### Class B — compatible open-source ports

`xbebenk/MBR_xbebenkMod` is GPLv3-compatible and actively maintained, but its main code line is based on MyBot v7.9.9. A recent patch can still be valuable; it must be adapted to the v8.2.0 implementation rather than copied as a directory replacement.

### Class C — public behavior references

`clashautoloot/Clash-AutoLoot` publishes product descriptions and compiled releases without application source or a source license. Its public descriptions may inform requirements. Its executable, assets, protocol, licensing code, and internal implementation are out of scope.

### Class D — lineage or duplicate references

`muratcandegirmenci78-lab/canmurat` currently matches the official v8.2.0 release lineage closely enough that no unique import is planned.

## Port record

Every imported or adapted open-source change must include this information in the pull request or commit notes:

```text
Source repository:
Source commit:
Source path(s):
License:
Original problem:
Why the change applies to v8.2.0:
Adaptation made:
Affected subsystems:
Regression risk:
Validation performed:
Fixtures or logs attached:
```

A source link without an exact commit is not sufficient.

## xbebenk port order

### Tier 1 — low-risk platform and recovery fixes

Review first:

- emulator discovery and ADB addressing
- MEmu and MuMu support
- SCID switch-failure handling
- generic loading, chest, reward, survey, and shop interruption handling
- safe Builder Base navigation fixes
- invalid upgrade-list guards
- current wall and scenery image additions

These are still not blind cherry-picks. For example, xbebenk's July 2026 LDPlayer9 port fix lives in a dedicated module that the v8.2.0 baseline does not have. The behavior must be integrated through the newer emulator architecture or introduced as a complete, referenced adapter.

### Tier 2 — feature-level compatibility

Review after fixtures exist:

- Hero Journey message handling
- saved-army selection
- current daily challenge collection
- current Trader Medal controls
- Builder Base shop and Pet House upgrade paths
- fast-forward battle control
- obstacle/chest handling after loading

These changes interact with navigation and can hide deeper state errors if added without screenshot evidence.

### Tier 3 — data and strategy changes

Review only after the current catalog exists:

- new troops, spells, Heroes, pets, equipment, buildings, and walls
- attack bar changes
- upgraded strategy scripts
- new cost and level tables
- TH18 recognition
- Ranked and Legend behavior

Do not transplant older arrays or globals merely because they contain a newer entry. Add the entry to the v8.2.0 data model and update every consumer deliberately.

## Clean-room feature process

A feature inspired by a public description follows this sequence:

1. Record only externally visible behavior and user intent.
2. Write acceptance criteria without referring to hidden implementation details.
3. Design the feature against this repository's architecture.
4. Implement using original code and project-owned assets.
5. Test against documented states and operator-visible outcomes.
6. Record that no closed binary, decompilation output, private protocol, or protected asset was used.

### Initial clean-room requirements

#### Run dashboard

- Start, Pause where safely supported, Stop, and emergency diagnostic capture.
- Current profile, account alias, village mode, strategy, elapsed time, and stop reason.
- Current engine state and last completed action.
- Readable warnings for unmet prerequisites.

#### Village mode

- Home Village, Builder Base, or a validated rotation plan.
- Mode-specific settings are hidden or disabled outside their context.
- Switching modes during a run requires an engine-supported transition, not direct UI clicks.

#### Strategy selection

- Strategies are identified by stable IDs.
- Each strategy declares required troops, spells, Heroes, Town Hall range, battle modes, and unsupported conditions.
- The selector explains why an option is unavailable.
- Presets are versioned and do not promise results.

#### Session and stop rules

- Maximum duration.
- Maximum attacks.
- Resource target.
- Star Bonus completion.
- Builder availability.
- Account queue completion.
- Consecutive-failure limit.
- Operator stop.

Every run records the exact rule that ended it.

#### Account queue

- Ordered accounts with enabled/disabled state.
- Per-account profile mapping and mode.
- Explicit switch verification using non-secret identity markers.
- Failure policy: retry, skip, or stop.
- No credentials in logs.

#### Upgrade rules

- Wall level and resource type.
- Minimum reserve.
- Builder requirements.
- Maximum upgrades per pass.
- Dry-run preview.
- No automatic premium-currency spending.

#### Builder Base collection

- Detect whether the cart exists and is collectible.
- Respect storage-full states.
- Record collected amount when OCR confidence permits.
- Return to a known screen on failure.

## UI and engine merge rule

The UI redesign and game-compatibility changes must remain separate until an engine adapter exists. UI code may read descriptors, validation results, engine state, and telemetry. It must not duplicate game coordinates or perform direct input.

A compatibility patch that changes an engine behavior should be reviewable without visual redesign noise. A design-system commit should not modify battle logic.

## Required validation

### Static

- all local `#include` paths resolve
- no new secret patterns or private keys
- source provenance is recorded
- required notices remain present
- new binary artifacts are rejected unless explicitly reviewed
- config keys and feature IDs are unique

### Fixture

- positive and negative recognition samples
- scale/DPI variants where relevant
- expected state transition
- expected safe recovery when the target is absent
- event and popup overlap cases

### Windows build

- AutoIt syntax check
- source compilation
- clean-profile launch
- watchdog launch/stop
- no unhandled startup dialog
- log and profile paths created correctly

### Emulator smoke test

For each advertised platform/version:

- discover instance
- connect through the expected input/capture path
- verify resolution and DPI
- start and close the game
- reach Home Village
- capture and recognize a known state
- stop cleanly

Feature smoke tests are added only after the platform test passes.

## Commit structure

Preferred sequence for a compatibility feature:

1. fixture or failing static check
2. catalog/schema change
3. recognition or platform adapter
4. state transition/recovery
5. UI descriptor, if needed
6. documentation and evidence

Avoid commits named `update`, `fix stuff`, `latest support`, or `misc changes`. State the subsystem and outcome.

## Prohibited merge shortcuts

- replacing the v8.2.0 tree with xbebenk's older base
- copying a closed executable or extracting its resources
- importing code without preserving its license and origin
- merging image folders without identifying client family and expected recognizer
- changing global array sizes without auditing every consumer
- adding broad click-through behavior for unknown popups
- using random timing or cursor behavior as a detection-evasion feature
- marking a feature supported before a controlled current-client test is recorded
