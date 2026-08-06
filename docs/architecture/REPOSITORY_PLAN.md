# Repository reorganization plan

The current tree is a mature AutoIt application with a wide include graph and many path-sensitive image, OCR, language, profile, and library references. Moving folders first would create a large, hard-to-review break. Reorganization will therefore be incremental: establish boundaries and automated checks, introduce adapters, then move implementation behind those boundaries.

## Design goals

- Keep the v8.2.0 baseline runnable while current-client support is added.
- Make game data, recognition, navigation, strategies, profiles, and UI separable.
- Replace fixed-size and fixed-version assumptions with versioned catalogs.
- Give every setting a clear label, description, default, validation rule, and dependency.
- Make unexpected screens recoverable through one interruption system.
- Allow a modern UI to consume engine state without directly editing legacy globals.
- Make releases traceable to source, dependencies, assets, and test evidence.

## Current logical layers

Although the files are not cleanly separated, the existing application already contains recognizable responsibilities:

1. **Bootstrap and process lifecycle** — `MyBot.run.au3`, command-line options, initialization, watchdog, shutdown.
2. **Global state and configuration** — global variables, INI profile reads/writes, language detection, delays, coordinates, directories.
3. **Android and emulator integration** — discovery, ADB, window control, embedding, background input, screen setup, restart handling.
4. **Vision and OCR** — screenshots, image matching, colors, OCR libraries, templates, coordinate regions.
5. **Game state and navigation** — page checks, village transitions, popup handling, menu opening, retries.
6. **Features and strategies** — attacks, training, donations, upgrades, Clan Games, Builder Base, account switching, notifications.
7. **GUI** — control definitions, event handlers, profile binding, status/log views.
8. **Reporting and diagnostics** — logs, statistics, screenshots, watchdog messages, notifications.

The first refactor will formalize these boundaries without rewriting all behavior.

## Target tree

The target layout is directional. Existing paths remain until their consumers have adapters and tests.

```text
/
├─ src/
│  ├─ bootstrap/              # process entry points and lifecycle
│  ├─ core/                   # scheduler, run plan, cancellation, result types
│  ├─ game/
│  │  ├─ catalog/             # versioned units, buildings, levels, costs, screens
│  │  ├─ state/               # recognized states and transitions
│  │  ├─ navigation/          # actions that move between states
│  │  └─ interruptions/       # popup/event/reward dispatcher
│  ├─ vision/
│  │  ├─ capture/
│  │  ├─ matching/
│  │  ├─ ocr/
│  │  └─ regions/
│  ├─ platforms/
│  │  ├─ android/
│  │  ├─ google-play-games/
│  │  └─ emulators/
│  ├─ features/
│  │  ├─ farming/
│  │  ├─ builder-base/
│  │  ├─ upgrades/
│  │  ├─ donations/
│  │  ├─ clan-games/
│  │  └─ accounts/
│  ├─ profiles/               # schema, migration, validation, secrets boundary
│  ├─ telemetry/              # events, counters, run history, diagnostics
│  ├─ ui-adapter/             # stable interface presented to any UI shell
│  └─ legacy/                 # temporary compatibility wrappers for AutoIt modules
├─ ui/
│  ├─ shell/                  # future modern desktop shell
│  ├─ components/
│  ├─ assets/
│  └─ design-tokens/
├─ assets/
│  ├─ game/<client-family>/   # templates grouped by game/client family
│  ├─ ocr/
│  ├─ locales/
│  └─ third-party/
├─ config/
│  ├─ schemas/
│  ├─ defaults/
│  └─ examples/
├─ tests/
│  ├─ unit/
│  ├─ fixtures/screens/
│  ├─ transitions/
│  ├─ profiles/
│  └─ smoke/
├─ tools/
├─ docs/
├─ packaging/
├─ third_party/
└─ upstreams.lock.json
```

## Stable interfaces to introduce first

### Run plan

A run should be described by one validated object instead of scattered GUI globals.

```text
RunPlan
  profileId
  accountQueue[]
  villageMode
  strategyId
  durationLimit
  attackLimit
  stopConditions[]
  resourceRules
  upgradeRules
  safetyRules
  diagnosticsLevel
```

The engine should receive a frozen run plan when Start is pressed. Mid-run UI edits should either apply to the next run or use an explicit, supported command.

### Capability registry

Every environment and game feature should report capabilities rather than relying on emulator-name or Town Hall conditionals throughout the code.

```text
Capability
  id
  status: supported | experimental | unavailable
  reason
  requirements[]
  detectedVersion
  lastVerifiedAt
```

Examples: background input, multi-instance discovery, Builder Base, Ranked mode, six-Hero model, current card-event guard.

### Screen registry

Each recognized screen or interruption needs one record:

```text
ScreenDefinition
  id
  category
  priority
  recognizers[]
  safeActions[]
  defaultRecovery
  retryLimit
  evidenceCapture
  introducedIn
  retiredIn
```

The registry prevents individual features from independently clicking through the same popup with different assumptions.

### Feature descriptor

The UI should generate consistent dropdowns, descriptions, and validation from feature metadata.

```text
FeatureDescriptor
  id
  displayName
  shortDescription
  longDescription
  category
  status
  prerequisites[]
  conflicts[]
  settings[]
  defaults
  documentationLink
```

A dropdown option must never be an unexplained label. Disabled choices should show the exact unmet prerequisite.

### Game catalog

Troops, spells, Heroes, pets, equipment, sieges, buildings, defenses, walls, currencies, screens, and level ranges should be data records keyed by a stable ID. Source code should not rely on display text or array position as identity.

## Migration phases

### Phase A — protect the legacy baseline

- Add upstream pinning and source-provenance rules.
- Add static include, secret, and artifact checks.
- Create a current-client compatibility matrix.
- Record a clean Windows build procedure.
- Capture the startup include graph and required runtime files.

No broad moves occur in this phase.

### Phase B — introduce catalogs and adapters

- Add stable IDs for Heroes, troops, spells, equipment, buildings, and screens.
- Wrap legacy arrays behind catalog lookup functions.
- Add profile schema versioning and a read-only migration report.
- Add a central interruption dispatcher alongside existing popup checks.
- Add a telemetry event writer with redaction and bounded retention.

Legacy code can keep its existing data while adapters are verified.

### Phase C — extract current-client compatibility

- Add the TH18/six-Hero catalog.
- Add current screen fixtures and recognition regions.
- Port current emulator and popup fixes selectively.
- Split regular, Ranked, Legend, Revenge, War, Friendly, and Builder Base battle routes.
- Move event-specific recognition into versioned interruption definitions.

### Phase D — extract run orchestration

- Build `RunPlan`, `StopCondition`, `AccountQueue`, and cancellation primitives.
- Convert feature loops to return structured results rather than only logs/global flags.
- Add bounded retries and typed failure reasons.
- Make Stop deterministic and observable.

### Phase E — modern UI shell

- Implement the separate design system and navigation shell.
- Bind controls to descriptors and schema validation.
- Stream read-only engine state and telemetry to the UI.
- Keep all destructive or spending actions explicit and separately enabled.
- Retain a diagnostic legacy UI path until feature parity is demonstrated.

### Phase F — physical file moves

Only after include checks and tests are reliable:

1. move documentation and development tools
2. move versioned game assets
3. move emulator modules
4. move feature modules
5. move shared core and profile code
6. retire compatibility wrappers

Each move must be mechanical, isolated, and behavior-neutral.

### Phase G — release pipeline

- Compile from source in a controlled Windows workflow.
- produce checksums, a dependency manifest, and a source commit record
- sign releases where a trusted certificate is available
- do not publish inherited or unverifiable executables as new project builds
- attach static checks, fixture results, and environment smoke-test evidence

## Configuration rules

- Every profile has a schema version.
- Defaults live in one documented source.
- Unknown keys are preserved during migration but reported.
- Removed keys are never silently repurposed.
- Secrets and account credentials are never written to logs or committed examples.
- Settings use stable IDs; localized display text is presentation only.
- A setting can declare dependencies, conflicts, minimum/maximum values, and reset behavior.
- The UI shows the effective value and whether it comes from a default, profile, account override, or temporary run override.

## Error model

The engine should distinguish at least:

- environment unavailable
- unsupported game version
- screen not recognized
- transition timed out
- interruption blocked progress
- account switch failed
- strategy prerequisites not met
- resource or builder condition not met
- action cancelled by operator
- action stopped by run rule
- recoverable platform fault
- unrecoverable platform fault

A generic retry loop without a reason should be treated as technical debt.

## Diagnostics

For every failed transition, capture a bounded diagnostic bundle:

- timestamp and run ID
- profile/account alias, never credentials
- expected state and recognized candidates
- source and target action
- retry count
- emulator/platform capability report
- screenshot with configurable redaction
- relevant log window
- game catalog/client family

Diagnostic retention must be configurable and default to a reasonable local limit.

## UI boundary

The UI must not call pixel-click functions directly. It sends commands such as `StartRun`, `StopRun`, `ValidatePlan`, `SwitchProfile`, or `CaptureDiagnostic`. The engine publishes state such as `Idle`, `Preparing`, `Attacking`, `Recovering`, or `Stopping`, plus structured activity events and metrics.

This boundary makes it possible to retain the AutoIt engine during the UI transition and later replace individual subsystems without rebuilding the interface again.

## Explicit exclusions

The reorganization will not add:

- detection-evasion or stealth modules
- fingerprint spoofing
- ban-avoidance logic
- credential interception
- automatic purchasing or Gem spending without a narrow, explicit, off-by-default feature
- claims of compatibility that are not backed by current-client evidence
