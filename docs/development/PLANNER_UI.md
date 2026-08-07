# The Run Planner web UI

There are two front-ends for the same run planner. The AutoIt tab lives inside the bot window and
is what ships. The web UI is a nicer way to build a plan, and it is where visual work happens
without fighting AutoIt's control limits.

Both read the **same** generated metadata (`config/ui/run-planner.settings.json`), so they always
offer the same settings, options, defaults and disabled reasons. Neither can drift from the other,
because changing what the planner offers means editing the catalog and regenerating — which updates
both.

---

## Running it

```bash
python tools/planner_ui.py
```

It serves on `http://127.0.0.1:8765` and opens your browser. `Ctrl-C` stops it.

- `--port N` — use a different port.
- `--no-browser` — start the server without opening a browser.
- `--selftest` — check the server contract and exit. No browser, no network. CI runs this.

It binds to loopback only, so nothing is reachable from outside the machine.

---

## What it does

- **Left**: one entry per section — Battle, Heroes, Emulator, Army, Search, Pacing, Limits, Loot,
  Donate, Events, Upkeep, Notify, Debug. The chosen section lives in the URL, so a refresh keeps
  your place.
- **Middle**: the controls for that section. Each carries its summary under the label, and select
  controls show an availability pill — verified, unverified, not implemented — plus the specific
  reason a choice is unavailable.
- **Right**: a detail panel that expands on the focused control, and a live activity feed that
  tails the run's event log.
- **Bottom**: Apply writes the plan; Reset returns every control to its default.

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
        +--> RunPlanFile.au3 --> the AutoIt tab's controls, on startup and whenever the file changes
```

- **`config/run-plan.local.json`** is what the UI writes and the engine reads. It is local to each
  machine and git-ignored.
- **`logs/run-events.jsonl`** is the JSONL event stream the engine appends to during a run — the
  same contract `RunEvent.au3` produces. Also git-ignored.

The UI validates a submitted plan the way the engine will — coercing types, clamping integers to
their range, rejecting unknown settings and invalid options — so a stale browser tab cannot write a
file the engine chokes on. The engine still re-validates; the UI is a convenience, not the
authority.

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

A value the tab cannot represent costs that one setting, not the whole file:

- **out of range** — clamped to the nearest legal value and reported
- **not one of the offered options** — refused, that control left alone
- **a setting this build does not have** — ignored, so an older or newer plan file still loads

Reset is still yours. It puts the controls back to their defaults and the file does not immediately
undo it; the file re-asserts itself the next time it actually changes.

`tools/check_plan_bridge.py` is what keeps the two halves honest. The AutoIt side cannot be executed
off Windows, so it checks the agreement statically: that the plan the server writes only uses shapes
the parser accepts, that every key names a control, that every setting type has a branch that applies
it, and that the pacing bounds the engine enforces are the ones the controls offer. CI runs it on
every push.

---

## Pacing

The **Pacing** section is about how hard a run drives the emulator. Every value trades throughput for
fewer misread screens.

| Control | Default | What it does |
|---|---|---|
| Gap between actions | 120 ms | Floor on the wait between two taps. Only taken when the previous action finished more recently than this |
| Screen settle wait | 400 ms | How long to let an animation finish before reading pixels. The largest single source of wrong decisions is reading a frame that is still moving |
| Retries per action | 2 | A tap that produced no visible change is usually a dropped input; repeating it is cheaper than abandoning the step |
| Rest after | off | Pause the run once it has been going this long |
| Rest for | 5 min | How long each pause lasts. Nothing is closed and no progress is lost |

`COCBot/functions/Run/RunPacing.au3` holds the arithmetic. The clock is passed in rather than read
inside, so the whole module is decidable from its arguments and the contract tests check it without
waiting for real milliseconds to pass. Every run intent carries pacing — defaulted, never absent — so
nothing downstream has to check whether it is there.

---

## Where this is going

The AutoIt tab stays as the in-window fallback. The web UI is the path to the polished interface,
and because it talks to the engine only through the plan file and the event stream, it can grow —
charts, run history, multi-account dashboards — without touching the recognition code at all.

That boundary is deliberate. The valuable, fragile part of this project is the screen recognition
and the image templates. Keeping the UI on the far side of a plain file-and-events interface means
the interface can be rebuilt, restyled, or replaced without risking any of it.
