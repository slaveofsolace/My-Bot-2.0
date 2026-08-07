# Engineering notes

Why some things in this repository are built the way they are. Decisions that took an argument to
settle are written down here so they do not get re-litigated or quietly reversed.

## Emulator adapters

LDPlayer 9 and MuMu Player 12 have adapter modules that plug into the existing v8.2.0 Android
dispatch layer rather than replacing the Android core.

LDPlayer 9 assigns ADB ports to multiple instances by formula:

```text
emulator-(5554 + 2 × instance index)
```

MuMu does not follow a formula. Each instance records its own endpoint, so the adapter reads
`ADB_PORT_EX` from the instance configuration instead of guessing.

Both adapters cover installation discovery, instance addressing, launch and shutdown, ADB
selection, shared-folder discovery, resolution and DPI configuration, background mode, window
lookup, reboot configuration, and zoom-out.

None of that is a support claim. Writing an adapter is not the same as watching it drive a real
emulator, and neither has been through a controlled test covering instance zero and a non-zero
instance, ADB reconnect, window recreation, background capture, clicks, zoom, restart, and
shutdown.

## Which build gets the compatibility layer

The compatibility entry point is included from `MyBot.run.au3` and nowhere else.

This matters more than it looks. There are three compiled entry points, and only the main one
includes the Android core. An earlier version included the compatibility layer from `Api.au3`,
which all three reach, so the Android adapters were compiled into the Mini GUI and Watchdog builds
where the functions they call do not exist. The Watchdog build does not even load the global
variables file, so the Android config array was undeclared there too.

`tools/lint_autoit.py` resolves each entry point's include graph and fails if a build uses a
function or global that is not defined anywhere in that build's own graph, which is what catches
this class of mistake without a Windows runner.

## Ports that were deliberately not taken

Two July 2026 changes from `xbebenk/MBR_xbebenkMod` were reviewed and left alone:

| Commit | Why not |
| --- | --- |
| `a477cbaf50ac8247da935a921f6de0dd5ca9a5e7` | Its chest handling patches an older `PlacedOnLeague` path. v8.2.0 already uses a newer Treasure Hunt interruption path and does not contain that control flow. |
| `84c9115021f0b2c55d38a351086466ec61afa3dd` | Its resource-icon guard patches `FindUpgradeBB`. v8.2.0 uses the reorganised `GetIconPosition` pipeline instead. |

Copying either literally would swap newer logic for older structure. If a current-client capture
reproduces the underlying defect, it gets fixed against the code that is actually here.

The LDPlayer multi-instance ADB correction went the other way: the fix was real, but v8.2.0 has no
equivalent of the file it patched, so it became a proper adapter rather than a copied file.

## Catalogs are the source of truth

`config/game/*.json` describes the current game. Two AutoIt files are generated from it and from
the planner metadata:

- `COCBot/functions/Game/GameCatalog.generated.au3`
- `COCBot/GUI/RunPlannerMetadata.generated.au3`

Neither should be hand-edited. CI fails if either drifts from its source.

The point of generating rather than hand-writing is that the planner cannot fall out of step with
the engine. Adding a battle surface to the catalog adds it to the dropdown, to the validator's
expectations, and to the engine's routing in one edit.

## Capability states

A capability is in exactly one of four states, and the difference is load-bearing:

| State | Means |
| --- | --- |
| `catalogued` | The game has this feature and we have described it from an official source. Nothing recognises it yet. |
| `adapter-added` | Code exists that would drive it. It has not been run against the real thing. |
| `engine-added` | Contract and tests exist and pass. No client interaction involved. |
| `supported` | Fixtures and controlled runtime evidence both pass. |

Nothing reaches `supported` without evidence. A catalog entry is a description, not a
demonstration.

## Verified and diagnostic runs

Unverified surfaces can run, because a route that refuses to start cannot be debugged. What they
cannot do is claim to have worked.

The verification state is a one-way latch. `RunSessionMarkDiagnostic` sets it; nothing clears it.
It is stamped on the session, on the snapshot, and on every JSONL event, and the planner shows a
banner for as long as an unverified surface is selected.

The attack-quota gate is deliberately not relaxed by diagnostic mode. Having no attacks left is a
fact about the game rather than a missing capture, and attacking anyway is just a bug.

## The plan file is one-way

The web planner and the AutoIt tab both describe a run, and something had to decide what happens when
they disagree. The answer is that `config/run-plan.local.json` is the source of truth and the traffic
runs one direction: the tab reads it, and nothing on the AutoIt side writes it.

Two-way sync was the obvious alternative and it is the wrong shape here. Whichever surface wrote last
would win, and the surface that writes last is usually the one nobody is looking at — a browser tab
left open since the morning, or a bot window that has been idle. One-way means a stale view can only
ever be wrong about itself.

The cost is that the tab is a viewer for anything the browser sets. That is the intended trade: the
tab keeps working as the in-window fallback, and the web UI is where the plan actually gets built.

`RunPlanFile.au3` reads the file because AutoIt has no JSON parser in its standard library and one
flat object does not justify a UDF dependency. It handles strings, numbers, booleans, null, and lists
of those. Nested objects are refused rather than flattened — a plan file that grew a nested shape is a
contract change, and failing loudly beats guessing at it.

`tools/check_plan_bridge.py` is what stops the two halves drifting. The AutoIt side cannot run off
Windows, so the agreement is checked statically instead: the shapes the writer emits, the setting ids
it uses, the types the tab has branches for, and the bounds the engine enforces against the ones the
controls offer.

## Pacing is a reliability control

`RunPacing.au3` holds the gaps between actions, the settle wait before reading a screen, the retry
count, and the rest schedule. Every one of them exists because an emulator redraws slower than the bot
taps, and reading a frame that is still moving is where wrong decisions come from.

It is deliberately not a disguise layer. There is no tap-position scatter, no randomised timing
envelope, and no scheduling built around what a watcher would infer — those exist to defeat
enforcement, which is a different goal with a different failure mode, and this project does not carry
it. `tools/validate_ui_metadata.py` enforces that in the wording too: a control description that
reframes a timing as looking human, avoiding detection, or being undetectable fails validation, since
a control's description is what a user ends up believing about it.

The clock is a parameter rather than something the module reads, which keeps the whole thing decidable
from its arguments and lets the contract tests check the arithmetic without waiting for real time.
`RunPacingGate.au3` is the other half: the one place that reads a clock and does the sleeping, so the
module underneath stays testable and the test scripts can compile it without dragging in `_Sleep`.

The gate sits in `Click()`, which is the most-travelled function in the program, so it is opt-in at
runtime: with no pacing installed it returns on an `IsObj` check and the untouched path is unchanged.
Applying a plan installs it; Reset removes it.

Note what is **not** gated. `PureClick` and `PureClickTrain` drive troop training in tight loops that
already space themselves with their own speed argument, and stacking a second delay on top would
double-space something someone already tuned.

One inherited behaviour is worth knowing about, because it is easy to mistake for this work.
Upstream v8.2.0 already ships `$g_bUseRandomClick` — a BOT Options checkbox that scatters click
coordinates by ±5px and click speed by ±15%. It predates this project, it is wired through
`saveConfig`/`readConfig`/`applyConfig`, and it is not something added here. It is left as it was
found; nothing in the pacing work extends it, and the two are unrelated mechanisms that happen to
both affect timing.

## What still has to happen

Before any surface moves to `supported`:

1. Au3Check and the AutoIt contract tests pass on Windows. *(Currently passing.)*
2. Clean-profile startup with no inherited configuration.
3. LDPlayer 9 on instance zero and a non-zero instance.
4. MuMu Player 12 on instance zero and a non-zero instance.
5. Current-client captures taken and redacted.
6. Recognition assertions for each catalogued surface.
7. Route separation proven for Regular, Ranked, Legend, and Builder Base.
8. End-to-end sessions with deterministic stop-condition evidence.
