# Runtime resource budget

The lowest-resource configuration is the docked background path: one BlueStacks instance, the exact Mini controller, one native backend, one launcher strip and one standard-library Control Center service. Extra browsers, duplicate controllers and overlapping ADB servers are not part of the supported stack.

## Dated local baseline

Observed on the 2026-08-12 BlueStacks 5/Pie64 test session while the engine was idle:

| Process | Approximate working set | Role |
| --- | ---: | --- |
| BlueStacks `HD-Player.exe` | 1.30 GiB | Android VM and game; dominant cost |
| `MyBot.run.MiniGui.exe` | 53 MiB | Pinned native safety controller |
| Control Center `pythonw.exe` | 34 MiB | Loopback-only planner service |
| `My Bot 2.0.exe` | 28 MiB | docking/recovery/background controller |
| `MyBot.run.exe` | 11 MiB | native automation backend working set |

These are observations, not universal promises. Driver, emulator, game and browser versions change them.

## Current low-power behavior

- The planner uses slower status/event polling when idle and much slower polling while the tab is hidden.
- Active or pending Start/Stop work keeps the short polling interval so safety controls remain responsive.
- Returning to the tab triggers an immediate refresh instead of waiting for the hidden-tab interval.
- ADB capture and input keep working while the exact controller and emulator are minimized together.
- The launcher refuses duplicate owned stacks and recovery targets exact installation paths rather than scanning broadly.
- Recognition code should reuse a fresh frame across related checks and avoid repeated disk decode. This is the preferred direction for future clean-room vision work.

## Release budgets

| Component | Budget/gate |
| --- | --- |
| Control Center service | Keep idle working set below 50 MiB on the reference machine; standard library only unless a measured dependency replaces more cost than it adds |
| Launcher + backend | No duplicate long-lived instance; no busy polling; idle CPU should settle near zero |
| Status polling | Hidden idle interval at least 5 seconds; active Stop path no slower than 1.5 seconds |
| Event polling | Hidden idle interval at least 15 seconds; fetch only bounded recent activity |
| Capture | One bounded capture per recognition cycle where possible; cache invalidated immediately after input |
| Emulator | One selected exact instance; do not launch a second VM to perform background work |

Resource optimization must not weaken exact-instance binding, Stop responsiveness, capture freshness after clicks, error detection or evidence logging.
