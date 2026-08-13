# My Bot 2.0 control center

The browser UI is the primary operator surface. It shows a live native-engine heartbeat and sends
acknowledged Start, Stop, Pause, and Resume commands. The AutoIt window remains the background
engine, recovery surface, and in-window fallback.

There are also two front-ends for the same run planner. Both read the same generated metadata.
The product is My Bot 2.0 v2.0.0; MyBot.run v8.2.0 is the upstream engine compatibility version.
The compiled native host retains the upstream MyBot.run v8.2.0 resource identity because the
combined engine validates that identity before enabling image recognition. Visible native and
browser titles continue to use the My Bot 2.0 product name and version.

The official MyBot.run engine retired its forum-login prerequisite in v7.8.1, and v8.2.0 retains that
behavior. My Bot 2.0 therefore never asks for forum credentials or creates a local forum token. The
managed-engine probe, emulator attachment, ADB connection, and game-screen proof remain fail-closed
Start prerequisites.

Both read the **same** generated metadata (`config/ui/run-planner.settings.json`), so they always
offer the same settings, options, defaults and disabled reasons. Neither can drift from the other,
because changing what the planner offers means editing the catalog and regenerating — which updates
both.

---

## Running it

Normal My Bot 2.0 startup begins with `My Bot 2.0.exe`, which elevates and minimizes the native
compatibility host. That host owns the loopback service and opens the browser automatically. The
command below is the standalone development entry point.

```bash
python tools/planner_ui.py
```

It serves on `http://127.0.0.1:8765` and opens your browser. `Ctrl-C` stops it.

The four-step health rail separates Control Center readiness, the native heartbeat, managed-engine
probe readiness, and the emulator path. The last step distinguishes a found
window, a ready ADB connection, and a recognized game screen instead of treating them as equivalent.
**Export diagnostics** downloads a redacted JSON support
bundle containing only allowlisted operational state, recent event summaries, and executable
hashes. It never includes plan values, credentials, screenshots, or game data, and it does not query
Windows Security or system event logs.

- `--port N` — use a different port.
- `--no-browser` — start the server without opening a browser.
- `--selftest` — check the server contract and exit. No browser, no network. CI runs this.

It binds to loopback only, so nothing is reachable from outside the machine.

The page shell, stylesheet and script are separate files: `ui/planner.html`, `ui/planner.css` and
`ui/planner.js`. The server's Content Security Policy allows only same-origin styles and scripts;
inline blocks are intentionally absent. Requests also require a local Host/Origin, JSON writes are
limited to 256 KB, and plan replacement is atomic.

Pacing controls live in `config/ui/run-planner.pacing.json`; game-derived choices still come from
the catalogs. `python tools/generate_run_planner_settings.py --check` verifies that the committed
browser metadata matches both sources without rewriting it.

---

## What it does

- **Command deck**: live native state, heartbeat age, profile, emulator, and engine compatibility,
  with Start, Pause, Resume, and Stop enabled only when the current state permits them.
- **Native acknowledgement**: distinguishes a queued request from the engine accepting, rejecting,
  or treating it as a no-op.
- **Town Hall presets**: one compatibility-first starting point for TH2 through TH18. Selecting one
  immediately loads every preset-owned field, including the complete Hero loadout, into the unsaved
  form. **Apply plan** remains the only write. Emulator choice and diagnostic acknowledgement are
  always preserved.

- **Left**: one entry per section — Battle, Heroes, Emulator, Army, Search, Pacing, Limits, Loot,
  Donate, Events, Upkeep, Notify, Debug. The chosen section lives in the URL, so a refresh keeps
  your place.
- **Middle**: the controls for that section. Each carries its summary under the label, and select
  controls distinguish runtime verified, implemented but unverified, gated, and not implemented.
  Choices with no native execution adapter are disabled instead of failing only after Start.
- **Right**: a detail panel that expands on the focused control, and a live activity feed that
  tails the run's event log.
- **Bottom**: Apply writes the plan; Reset returns every control to its default.

The preset preview separates two kinds of evidence. **Script-declared** means the selected bundled
CSV names that Town Hall in its own header or source table. The adapter selects the deployment file
only; it does not import that CSV's training table, so the active profile army must already match.
**Engine fallback** means no shipped CSV makes that claim, so the preset uses the wired Standard
deployment and the active profile army. Neither label claims a current competitive meta or
current-client runtime proof. Named recipes are not wired. Scripted presets choose Heroes only from
current Town Hall unlocks that also have CSV DROP actions; fallback presets explicitly choose their
four-Hero loadout instead of silently retaining an unrelated manual selection.

Custom plans display an explicit Hero receipt. In current-trained-army mode those Heroes are deployed
when their attack-bar slots exist, but Hero Hall and Hero training are not opened or changed. Managed
training mode may additionally wait for the selected Heroes.

The diagnostic banner across the top says, for the selected surface, whether the bot has actually
been shown working on the current client.

---

## How it connects to the engine

```
config/ui/run-planner.settings.json   <-- both front-ends read this
        |
        v
tools/planner_ui.py  --(GET /api/metadata)-->  browser renders controls
        ^                                              |
        |  (POST /api/plan)                            |  you press Apply
        v                                              v
config/run-plan.local.json   <-- the engine reads this to run
        |    ^
        |    |  the engine appends events
        |   logs/run-events.jsonl  --(GET /api/events)-->  live activity feed
        |
        +--> RunPlanFile.au3 --> flat JSON parser --> tab synchronization
                                      |
                                      +--> exact 44-key validator --> prepared RunIntent
```

- **`config/run-plan.local.json`** is what the UI writes and the engine reads. It is local to each
  machine and git-ignored.
- **`logs/run-events.jsonl`** is the JSONL event stream the engine appends to during a run — the
  same contract `RunEvent.au3` produces. Also git-ignored.

The lifecycle bridge uses two other git-ignored files:

- `config/control-command.local.json` is an atomic, single-use command envelope. A pending command
  is never overwritten.
- `config/control-status.local.json` is the native heartbeat and last-command acknowledgement. The
  service marks stale status offline instead of presenting old state as live. The
  `authorization_ready` field remains in the v1 status schema for client compatibility and is
  always `true`, matching the official MyBot.run v8.2.0 behavior after forum login was retired.
  A run cannot become active until engine probing, emulator attachment, ADB setup, and game-screen
  recognition all succeed.

`POST /api/control/command` queues `start`, `stop`, `pause`, or `resume`. `GET /api/control/status`
returns the current native state. Applying a plan and starting a run remain separate explicit acts.

A submitted plan is checked before anything reaches disk, and the two outcomes are different:

- **Adjusted** — a value the server could repair: an integer past its bound, a boolean written as a
  word, a Hero list over its ceiling. The plan is written and the repairs are reported back.
- **Rejected** — a key that names no setting at all. Nothing is written and the response is `400`.
  The browser loaded its controls from this same server, so a key it does not recognise means the tab
  is stale or something else is writing. Saving the rest would leave you looking at a plan the file
  does not contain.

The AutoIt file layer has two deliberate stages. The parser accepts any flat JSON object made from
strings, numbers, booleans, nulls and scalar lists. The constructor is strict: before it prepares a
`RunIntent`, the document must contain exactly the 44 metadata keys and every value must satisfy the
engine contract. Parsing remains reusable while an incomplete or mixed-version plan cannot reach the
engine.

The two preceding contracts migrate without changing their meaning. A 43-key plan receives
`army.manage_training=true`, matching the training behavior that build always used. The older
42-key plan also receives `run.attack_script=profile-current`. Any other missing, extra, or unknown
field still fails the exact-shape gate.

Loading prepares an intent; it never presses Start. The engine still re-validates everything, so the
UI is a convenience rather than an authority boundary.

---

## The plan file wins

The two front-ends do not negotiate. **The plan file is the single source of truth, and traffic runs
one way**: the AutoIt tab reads it and shows what it says. Nothing on the AutoIt side writes it.

That is what makes it safe to leave the browser open next to the bot window — a tab that has been
sitting there since this morning can never quietly overwrite the plan you just built.

The AutoIt side re-reads the file at three moments:

| When | Why |
|---|---|
| Bot startup | So the tab already agrees with the file before anyone opens it |
| Switching to the Run Planner tab | So looking at it shows the current plan, not a stale one |
| Pressing **Apply plan** | So a change made in the browser a second ago is the one that runs |

Checking is cheap — a timestamp and a size — so a file that has not moved costs nothing.

`COCBot/functions/Run/RunPlanFile.au3` does the reading. AutoIt has no JSON parser in its standard
library, so it parses the subset the plan file can contain: strings, numbers, booleans, null, and
lists of those. **Nested objects are refused by name** rather than flattened, because a plan that
grew a nested shape is a contract change and should fail loudly.

A value the tab cannot represent costs that one control during synchronization:

- **out of range** — clamped to the nearest legal value and reported
- **not one of the offered options** — refused, that control left alone
- **a setting this build does not have** — ignored by the visual synchronization pass

Preparing an intent is stricter. **Load saved plan** and **Apply plan** reread the document through
the composed parser and validator, require all 44 keys exactly once, validate types and engine
bounds, construct the Hero loadout, and attach pacing. Any unknown, missing or malformed setting
rejects the complete intent rather than preparing a partial run.

Reset is still yours. It puts the controls back to their defaults and the file does not immediately
undo it; the file re-asserts itself the next time it actually changes.

The browser also saves its complete visible plan before it queues **Start**. This makes the first run
with untouched defaults explicit and prevents a stale tab or missing plan file from silently falling
back to legacy-profile behavior.

`tools/check_plan_bridge.py` keeps the two halves honest. It checks that the plan uses shapes the
parser accepts, every key names a control, the AutoIt constructor's required-key list matches all 44
metadata settings in both directions, every setting type has an apply branch, and the pacing bounds
match the engine. CI runs it on every push; Windows additionally executes the AutoIt contract tests.

---

## Pacing

The **Pacing** section is about how hard a run drives the emulator. Every value trades throughput for
fewer misread screens.

| Control | Default | What it does |
|---|---|---|
| Gap between actions | 120 ms | Floor on the wait between two taps. Only taken when the previous action finished more recently than this |
| Screen settle wait | 400 ms | How long to let an animation finish before reading pixels. The largest single source of wrong decisions is reading a frame that is still moving |
| Retries per action | 0 | Reserved until a screen-specific handler can prove the first action was dropped; generic repeats are unsafe |
| Rest after | off | Pause the run once it has been going this long |
| Rest for | 5 min | How long each pause lasts. Nothing is closed and no progress is lost |

### How it takes effect

Two files, split on purpose:

- **`RunPacing.au3`** is pure. It reads no clock and sleeps for nobody — the time is an argument. That
  is what lets the contract tests check the arithmetic without waiting for real milliseconds, and it is
  why the test scripts can compile it without dragging in half the bot.
- **`RunPacingGate.au3`** is the half that reads a clock and does the waiting. It holds the active
  pacing and sits in `Click()`.

**Pressing Start is what turns pacing on.** Apply only validates and prepares the intent. Until a
run begins the gate is inert: it returns on an `IsObj` check, so a bot that never opens this tab
behaves exactly as it did before the feature existed. That matters because `Click()` is the
most-travelled function in the program. Reset and Stop turn the gate back off.

Only `Click()` is gated — not `PureClick` or `PureClickTrain`. Those drive troop training in tight
loops that already space themselves with their own speed argument, and a second delay on top would
double-space something already tuned.

Two things in the gate are load-bearing and easy to undo by accident, so `check_plan_bridge.py` pins
both:

- **`_Sleep` is always called with `$CheckRunState = False`.** Left at its default it returns True
  whenever `$g_bRunState` is False — the ordinary state of an idle bot — so a gate built on it would
  report "stopped" for every click made outside a run and the caller would swallow the action. The gate
  watches for a bot that *was* running and has since stopped instead.
- **A static reentrancy guard.** `_Sleep` pumps the message loop, so a GUI handler that clicks would
  otherwise re-enter the gate and wait against a timestamp that had not been written yet.

Waits are taken in 250 ms slices so Stop stays responsive — a run resting for ten minutes should not
take ten minutes to notice it was stopped.

---

## Current execution boundary

The control bridge runs the real native Start, Stop, Pause, and Resume lifecycle and publishes a
fresh browser heartbeat. Start now owns the complete configuration boundary: browser save → plan
file → native parse → validated `RunIntent` → explicit execution contract → legacy configuration
→ live session.

`RunExecution.au3` applies the supported Regular Battles values to the native engine, activates
pacing only after the engine is initialized, and feeds real battle and loot counters back into the
session stop checks. The adapter contract rejects settings that do not yet have a safe legacy
consumer: named recipes, non-default Town Hall filters and search timeouts, Dragon Duke, advanced
donation policies, capped Clan Games points, automatic laboratory modes, non-supported upgrade
policies, account rotation, non-log notification channels, and action retries without a visual
change observer.

`Manage training` is a one-run safety boundary. Its default is off: the engine opens the Army
Overview and evaluates readiness, but skips Super Troop boosting, Quick Train inspection/editing,
troop removal, troop/spell queueing, and siege building. This current-army mode is accepted only
with `Max battles` set to exactly 1 and donations off. Turning it on restores the inherited profile
training flow for that run. Stop, cancellation, and close all clear the override before the legacy
loop can train again.

Before the GUI enters the mixed-mode DLL, a separate x86 helper performs the first export call with
a bounded timeout. That contains the known startup hang and produces a clear unavailable state; it
does not count as current-client combat evidence. Live client validation is still required before a
surface can be promoted from diagnostic to verified.

An early 2026-08-12 Regular Battle reached matchmaking but did not prove troop deployment. After the
enemy-view and actor-slot fixes, a later supervised Standard run did prove visible deployment, battle
telemetry, Return Home, and a clean one-battle stop. A separate Smart run proved troop and selected-Hero
deployment, but it used a different opponent and issued no Hero abilities or spells. A later Smart run
did issue all selected Hero abilities and Rage/Freeze commands, but the policy has since changed to a
role-specific phase quorum plus deadline fallback. Those runs are observations, not a strategy-quality
comparison or proof of the revised policy.
The permanent `tools/run_supervised_battle_acceptance.ps1` gate now accepts only Smart mode and
refuses to pass unless the current binary matches provenance, exactly one battle is recorded, the
native log proves enemy zoom plus two independent empty troop-bar reads, deterministic side/start
events exist, every selected Hero has one issued ability event, Rage and Freeze each have a proven
inventory decrease, no spell is retained, the engine stops itself on `battle-limit`, the saved plan
and BlueStacks process are preserved, and the supervising operator explicitly confirms the visible
deployment, abilities, and spells. An event-only or click-only run is not accepted.
The current Treasure Hunt screen uses a proof-gated three-tap chest sequence before the inherited
Continue-button path; that separate recovery does not count as attack evidence.

`Smart Attack (research-guided)` is a deterministic local option. Its dated source catalog lives in
`config/game/smart-attack-strategies.json`; the runtime never browses, downloads coordinates, or
calls an LLM. The current adapter scores the four current-frame red-line sides itself. A live base
with one detected Town Hall chooses the nearest valid side; dead or uncertain bases choose the
longest valid side with a fixed tie order. The protected legacy selector-5 branch is not used.
The tactical Hero policy now requires both the role's elapsed and destruction milestones for its
normal phase trigger; a later deadline can prevent an otherwise usable ability being wasted. Rage and
Freeze retain safe-target and inventory-decrement gates. The revised rules have static contract tests
but remain diagnostic until a fresh supervised battle records the phase reasons and confirms spell
inventory changes.

The browser header includes a bounded, sanitized **Native log** modal with refresh and tail download.
The pinned upstream Mini GUI cannot be rebuilt without tripping the inherited ImgLoc identity guard,
so the modern launcher owns a small companion AutoIt control strip directly beneath it with an
**OPEN BROWSER CONTROL CENTER** button.

---

## Where this is going

The AutoIt tab stays as the in-window fallback. The web UI is the path to the polished interface,
and because it talks to the engine only through the plan file and the event stream, it can grow —
charts, run history, multi-account dashboards — without touching the recognition code at all.

That boundary is deliberate. The valuable, fragile part of this project is the screen recognition
and the image templates. Keeping the UI on the far side of a plain file-and-events interface means
the interface can be rebuilt, restyled, or replaced without risking any of it.
