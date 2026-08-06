# Unified UI handoff

This document defines the product and engineering contract for the separate UI design-system pass. It is intentionally independent from visual styling so the design work can be creative without changing engine behavior.

## Product direction

The interface should feel like one deliberate desktop application, not a collection of legacy tabs or a reskinned script. It should retain the useful density of the original UI while improving hierarchy, explanation, discoverability, status visibility, and safe control.

The UI must be usable by someone setting up the project for the first time and efficient for an experienced operator managing several authorized test profiles.

## Reference material

Use these as inspiration, not as assets to copy without confirming their licenses and attribution requirements:

- Smart Charts Kit: https://www.figma.com/community/file/986513506555744040/smart-charts-kit
- Free Icon Pack — 1,800 Icons: https://www.figma.com/community/file/886554014393250663/free-icon-pack-1800-icons
- Ant Design Open Source: https://www.figma.com/community/file/831698976089873405/ant-design-open-source

The final design should also study the existing MyBot interface so every current setting has a destination. No setting may disappear merely because the old layout is dense.

## Information architecture

### Overview

The first screen answers five questions immediately:

1. Is the environment ready?
2. Which profile/account is selected?
3. What will run?
4. What is happening now?
5. Why did the last run stop?

Recommended regions:

- environment health strip
- active run card
- current account and queue
- resource and builder snapshot
- recent activity timeline
- run summary metrics
- warnings and required actions

### Run planner

Build a validated run before Start is enabled.

Sections:

- profile and account queue
- village mode
- strategy
- duration/attack limits
- stop conditions
- resource and upgrade rules
- schedule, when supported
- diagnostics level
- final validation summary

The summary should use plain language, for example:

> Run Home Village farming on Profile 3 for up to 45 minutes or 20 attacks. Stop after Star Bonus completion, three consecutive recovery failures, or operator request. Keep at least 4,000,000 Gold and never spend Gems.

### Farming

- strategy library
- troop/spell/Hero prerequisites
- acceptable target rules
- loot thresholds
- battle mode eligibility
- deployment summary
- end-battle policy
- version and verification status

### Builder Base

- attack strategy
- elixir-cart collection
- builder and storage status
- upgrade rules
- battle-stage handling
- capability and emulator warnings

### Upgrades

- builders and current tasks
- wall rules
- building priorities
- Hero/pet/equipment rules
- reserve thresholds
- dry-run preview
- audit history

Any action that spends premium currency must be separately implemented, explicit, off by default, and visually distinct.

### Accounts

- ordered account queue
- profile mapping
- enabled state
- detected account alias
- last verified switch
- failure policy
- per-account overrides

Never display, store, or request account credentials in this interface.

### Activity and diagnostics

- chronological event stream
- filters by account, feature, severity, and run
- structured failure reasons
- screenshot evidence where enabled
- exportable diagnostic bundle
- bounded retention controls

### Settings

Group by operator intent rather than implementation file:

- application
- environment and emulator
- capture and input
- profiles and storage
- notifications
- accessibility
- privacy and diagnostics
- advanced/developer

### About and notices

- project version and source commit
- game compatibility status
- supported environments and last verification dates
- open-source licenses and third-party notices
- source provenance
- links to documentation and issue reporting

## Navigation model

Use a stable left navigation rail or sidebar with a compact mode. Recommended top-level entries:

- Overview
- Run Planner
- Farming
- Builder Base
- Upgrades
- Accounts
- Activity
- Settings
- About

Secondary pages should use local tabs or a details pane. Avoid three levels of nested tabs.

## Component requirements

### Detailed select/dropdown

Every meaningful dropdown supports:

- display name
- one-line explanation
- status badge
- optional icon
- prerequisites
- disabled reason
- recommended/default marker
- searchable list when there are more than eight choices
- keyboard navigation
- persistent selected-value description below the field

Examples include emulator, account, strategy, village mode, stop rule, wall target, and notification provider.

### Setting row

A setting row contains:

- clear label
- short description
- control
- effective value/source where relevant
- validation message
- reset action
- documentation link for complex settings

Do not rely on tooltips as the only explanation.

### Status badge

Use a small, consistent vocabulary:

- Ready
- Running
- Paused
- Stopping
- Needs attention
- Experimental
- Unsupported
- Failed
- Not verified

Color cannot be the only signal.

### Metric card

A metric card must state the unit and time range. It may show a small trend only when the underlying data is meaningful. Decorative charts with no decision value should be removed.

### Activity event

Each event has:

- timestamp
- account/profile alias
- feature
- action
- outcome
- short reason
- expandable details
- optional evidence link

### Confirmation dialog

Use confirmations for destructive profile actions, queue replacement, diagnostics deletion, and any spending feature. The dialog must state the exact effect and affected profile/account.

### Empty state

Every empty state should explain why the area is empty and provide one direct next action. Avoid generic `No data` panels.

## Chart guidance

Charts should support operational decisions:

- loot by run and account
- attacks and outcomes over time
- recovery/failure rates
- resource change
- run duration and stop reasons
- builder utilization
- recognition confidence distribution during diagnostics

Requirements:

- readable axis labels and units
- selectable time range
- accessible text summary
- no 3D effects
- no animation that obscures exact values
- reduced-motion support
- tooltips available by mouse and keyboard
- clear missing-data treatment

## Motion

Motion should confirm state changes rather than decorate every interaction.

Recommended:

- 120–180 ms control transitions
- 180–240 ms panel transitions
- subtle number interpolation for live metrics
- progress indicators only for real work
- a brief state transition when Start becomes Running or Stop becomes Idle

Avoid:

- looping background effects
- parallax
- large spring animations
- animated gradients behind dense controls
- motion that delays access to a setting

Respect the system reduced-motion preference.

## Accessibility

- complete keyboard navigation
- visible focus states
- logical focus order
- text scaling without clipped controls
- minimum target size suitable for desktop touch use where practical
- contrast that remains readable in light and dark themes
- labels exposed to assistive technology
- non-color status indicators
- reduced motion
- chart summaries and table alternatives
- error messages linked to their controls

## Responsive desktop behavior

The primary target is Windows desktop, but the interface must adapt cleanly from a compact 1,024-pixel-wide window to large monitors.

- Sidebar collapses before content becomes cramped.
- Dense configuration pages use a details pane or two-column layout only when width allows.
- Tables retain key columns and move secondary information into row details.
- No horizontal scrolling for ordinary forms.
- The live run state remains visible when navigating between pages.

## Theme and tokens

The design system should define, at minimum:

- neutral and semantic color scales
- surface hierarchy
- typography roles
- spacing scale
- radius scale
- border and divider rules
- elevation rules
- icon sizes
- control heights
- motion durations/easing
- chart tokens
- focus style
- density modes

Tokens should be named by purpose, not by literal color. The interface should support both light and dark themes without maintaining separate component implementations.

## Copy rules

- Use direct labels: `Start run`, `Stop after Star Bonus`, `Keep Gold reserve`.
- Explain consequences before implementation details.
- Do not use unexplained abbreviations in primary UI.
- Use sentence case.
- Avoid novelty language in errors.
- Never describe functionality as undetectable, safe from bans, or human-like.
- Do not mention content-generation tooling in product copy, documentation prose, commit messages, or assets.
- Clearly distinguish `Unsupported`, `Not verified`, and `Temporarily unavailable`.

## Engine boundary

The modern shell receives:

- feature descriptors
- profile schema and effective values
- validation results
- environment capabilities
- engine state
- structured activity events
- telemetry snapshots
- supported commands

The shell sends commands such as:

- `ValidateRunPlan`
- `StartRun`
- `StopRun`
- `SelectProfile`
- `UpdateDraftSetting`
- `SaveProfile`
- `CaptureDiagnostic`
- `ExportRunReport`

It must not own game coordinates, image templates, ADB commands, account-switch clicks, or attack logic.

## Legacy UI migration

1. Inventory every existing control and config key.
2. Map each control to a feature descriptor and new destination.
3. Add read/write adapters around legacy profile values.
4. Build the new shell in read-only mode against live engine state.
5. Enable editing one feature group at a time.
6. Keep a compatibility view for unmigrated settings.
7. Retire old controls only after round-trip profile tests and feature parity review.

## Required design deliverables

- navigation map
- screen inventory
- component inventory
- token specification
- light and dark themes
- compact and comfortable density
- interaction states for every component
- validation and error patterns
- run-state transitions
- detailed dropdown pattern
- activity timeline
- chart patterns and text alternatives
- accessibility annotations
- empty/loading/error examples
- migration map from every legacy tab/control

A polished dashboard mockup alone is not sufficient; the handoff must cover configuration depth, live operation, failure recovery, and first-time setup.
