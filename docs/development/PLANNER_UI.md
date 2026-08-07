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

- **Left**: one entry per section — Battle, Heroes, Army, Search, Limits, Loot, Donate, Events,
  Upkeep, Notify, Debug. The chosen section lives in the URL, so a refresh keeps your place.
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
        ^
        |  the engine appends events
logs/run-events.jsonl  --(GET /api/events)-->  live activity feed
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

## Where this is going

The AutoIt tab stays as the in-window fallback. The web UI is the path to the polished interface,
and because it talks to the engine only through the plan file and the event stream, it can grow —
charts, run history, multi-account dashboards — without touching the recognition code at all.

That boundary is deliberate. The valuable, fragile part of this project is the screen recognition
and the image templates. Keeping the UI on the far side of a plain file-and-events interface means
the interface can be rebuilt, restyled, or replaced without risking any of it.
