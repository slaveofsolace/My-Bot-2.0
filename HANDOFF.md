# My Bot 2.0 — total handoff

Written 2026-08-07. Combines two independent work streams that do not yet know about each other.

**Read this first: there are two divergent working copies.** Neither is a superset of the other, and
the next session's first job is to decide what happens to them. Everything else depends on that call.

---

## 1. The two trees

| | **Cloud tree (Claude, Linux)** | **Windows tree (Codex, local)** |
|---|---|---|
| Location | remote container, `/home/user/My-Bot-2.0` | `C:\Users\suhai\Documents\ChatGPT\My Bot 2.0` |
| Base | `f1a0e2c3` | `f1a0e2c3` |
| State | **5 commits, pushed**, PR #7 open, CI green | **uncommitted worktree**, nothing pushed |
| Planner | 13 sections / 42 settings | 12 sections / 37 settings |
| UI files | single-file `ui/planner.html` | `ui/planner.html` + `planner.css` + `planner.js` |
| Guardians | facts in `current-client.json` only | `config/game/guardians.json` + schema |
| Native app | never launched (no Windows) | launches but **hangs** — see §5 |

Both branched from the same commit and edited the same files. A merge will conflict in
`tools/planner_ui.py`, `ui/planner.html`, `config/ui/run-planner.settings.json`,
`tools/validate_ui_metadata.py`, `tools/preview_run_planner.py`, `docs/development/PLANNER_UI.md`,
`COCBot/functions/Run/RunPlanFile.au3`, and the native Run Planner design/control files.

### The decision to make

1. **Take the cloud tree as the base**, then port the Windows-only additions onto it: Guardians
   catalog, the split CSS/JS, the security headers, `/api/health`, and the launch-fault hardening.
   Argued for: it is committed, pushed, and has green CI including real Au3Check on two AutoIt
   versions. Argued against: the Windows tree has work the cloud tree lacks.
2. **Take the Windows tree as the base**, then port the cloud additions: pacing (engine + gate +
   UI), the plan-file bridge with its six pinned invariants, the Hero chips, the UI rebuild, the
   strict-rejection contract.
3. **Reconcile file by file.** Most accurate, most work.

There is no way to avoid this. Both trees are real work.

---

## 2. Cloud tree — what is in it

Branch `claude/coc-bot-merge-ui-kobgds`, PR #7 (draft, open, mergeable clean, CI green).

```
7c7f5062  Reject unknown settings on save instead of dropping them
29cbc366  Add Run Planner interface screenshots
0a0cf296  Rebuild the planner UI and give the Hero picker its four slots
0aa9ae6b  Make the pacing settings actually take effect
26561f3d  Bridge the web planner to the AutoIt tab and add pacing controls
f1a0e2c3  (shared base)
```

**Web-to-AutoIt bridge.** `config/run-plan.local.json` is the single source of truth, one direction
only: the AutoIt tab reads it, nothing on the AutoIt side writes it. Re-read at bot startup, on tab
switch, and before Apply builds an intent. `COCBot/functions/Run/RunPlanFile.au3` parses the JSON
subset the file can hold (strings, numbers, booleans, null, lists); nested objects are refused by
name rather than flattened.

**Pacing.** `RunPacing.au3` (pure arithmetic, clock passed in, testable) plus `RunPacingGate.au3`
(reads the clock, does the waiting). The gate sits in `Click()` and is opt-in: with no pacing
installed it returns on an `IsObj` check. Applying a plan installs it; Reset removes it. Only
`Click()` is gated — `PureClick`/`PureClickTrain` drive training loops that already space themselves.

Two load-bearing details, both pinned by CI:
- `_Sleep` is always called with `$CheckRunState = False`. At its default it returns True whenever
  `$g_bRunState` is False — an idle bot — so the gate would report "stopped" for every click made
  outside a run and `Click()` would swallow it. This bug was caught pre-merge.
- A static reentrancy guard, because `_Sleep` pumps the message loop.

**UI rebuild.** Filter across all 42 settings, per-section changed counts, per-setting revert, Apply
disabled when nothing is unsaved, switches, Hero chips with the four-slot ceiling enforced in three
places (browser, `validate_ui_metadata`, server). Screenshots in `docs/ui/screenshots/`.

**Strict rejection.** POST with an unknown setting returns 400 and writes nothing. Adjustable values
(out of range, boolean-as-word, over-ceiling Hero list) still save and are reported. The AutoIt
reader deliberately stays lenient — different direction, different concern; documented.

**`tools/check_plan_bridge.py`.** The AutoIt side cannot run on Linux, so the two halves are checked
statically: shapes the writer emits, keys naming real controls, types having apply branches, engine
bounds against UI bounds, and the six pacing-gate invariants. Every check was verified by
reintroducing the defect and confirming failure.

### Verified in cloud CI

- 16 repository validators
- Windows jobs on AutoIt **3.3.16.1 and 3.3.18.0**: Au3Check on all six entry points, **plus actual
  execution** of `RunContractsTest`, `GameCatalogTest`, `RunEngineTest` (9 checks per version)

---

## 3. Windows tree — what is in it

Preserved verbatim in intent from the Codex handoff.

**Browser Run Planner.** 12 sections / 37 settings, four-slot Hero multi-select, responsive
three-column layout, light/dark and density modes, Host/Origin protection, CSP and security headers,
strict types/bounds/selection limits, request-size cap, atomic fsync/replace writes, bounded JSONL
tail, `/api/health` reporting bridge `autoit-plan-file-v1`, 18-check server selftest. Added
`ui/planner.css`, `ui/planner.js`.

**Saved-plan AutoIt bridge.** `RunPlanFile.au3` as a strict 37-field flat loader with exact
keys/types/enums/bounds/Hero limit/diagnostic-note validation, surface mapping, and full
RunPlan/HeroLoadout/quota/route/RunIntent construction. Native bridge has Open control center, Load
saved plan, Refresh. Loading prepares an intent and deliberately does not press Start.

**Guardian model.** `config/game/guardians.json` + schema; Smasher, Longshot, Logger; one-active
rule, Builder requirement, upgrade unavailability, previous-level defense rules. Catalog, generator,
validators, verifier and AutoIt tests updated.

**Startup change.** `MyBot.run.au3` restores only the configured emulator; full discovery moved to a
Detect button. **Preserve this** — the scan was slow but was not the freeze cause.

### Worktree hygiene (from the Codex handoff)

- `Languages/English.ini` — runtime translation writes. Exclude.
- `COCBot/functions/Other/CheckPrerequisites.au3` — differs only by a trailing newline. Remove the noise.
- `COCBot/functions/Other/MBRFunc.au3` — worktree hash equals index hash `08e7a0a4`; treat as unchanged.
- Tracked `MyBot.run.exe` restored to the untouched HEAD binary. **Do not recompile until §5 is fixed.**
- Preserve the dirty worktree. Do not reset, clean, or stash.

---

## 4. Why the cloud session could not finish the Windows task

Not caution — capability. The cloud session runs `Linux 6.18.5 x86_64` in an ephemeral container:

- No `C:\`, so `C:\Users\suhai\Documents\ChatGPT\My Bot 2.0` is unreachable
- No PowerShell — `Get-MpComputerStatus`, `Update-MpSignature`, `MpCmdRun.exe` cannot run
- No Windows Defender, no event log, no reboot, no access to PID 22436 or PID 18728
- No AutoIt toolchain — `Aut2Exe` and `Au3Check` are Windows-only, so `MyBot.run.exe` cannot be built
- The three skills at `C:\Users\suhai\.codex\skills\...` cannot be read
- The native app cannot be launched, so "visibly launched and responsive" cannot be confirmed

Checked: the account has exactly one environment, `anthropic_cloud`. There is no self-hosted or
Windows pool, so spawning another cloud session would land in an identical Linux container.

**To get a session that can do the Windows work, run Claude Code on the Windows machine** — the
`claude` CLI in a terminal there, or the desktop app opened on that folder. That is the only path.

---

## 5. The launch fault (Windows, unresolved)

Evidence says this is a **machine-level Defender fault, not a My Bot bug**:

- Defender Operational **Event 5008** at `2026-08-07 15:32:41`: engine terminated, reason `Hang`,
  engine code 16422. Then **Event 3002**: On Access, Behavior Monitoring and NIS failed because the
  filter driver unloaded unexpectedly.
- WER classifies every My Bot failure as `AppHangXProcB1`, naming **`MsMpEng.exe`** as the process
  being waited on. `MsMpEng.exe` was at ~812 MB and several hours of CPU. `WinDefend` is protected.
- **`powershell.exe -NoProfile -NonInteractive -Command "exit 0"` also hangs.** That is the decisive
  fact: the damage is system-wide, not app-specific.
- The **untouched tracked** `MyBot.run.exe` hangs too, so local compilation did not cause it.
- `lib/MyBot.run.dll` matches HEAD and pinned upstream `8ad6e5a5`; SHA-256
  `347b204a15fd56800130740aff639c7608621206482f07298c595a363e328699`. Expected x86 mixed-mode
  .NET Framework 4.5 DLL.
- Original binary hangs after `MyBot.run.dll opened` and the first pool export. A diagnostic build
  skipping those setters hung after `setAndroidPID: $pid=0`. So the **first managed export / JIT** is
  what blocks — not emulator enumeration, not that setter.
- Evidence log: `Profiles\MyVillage\Logs\2026-08-07_17.32.41.log`
- Stale process holding the launch mutex: `MyBot.run.exe` PID 22436

Already done: AutoIt 3.3.16.1 installed; MSVC 2010 x86 Redistributable 10.0.40219 installed. Neither
followed by a clean Defender restart.

### Recovery sequence

1. Preserve open work, terminate **only** PID 22436, reboot Windows. **Ask the user before
   rebooting.** Do not force-kill `MsMpEng`, disable Defender, or add a broad exclusion.
2. After reboot: `Get-MpComputerStatus`, `Get-Service WinDefend,WdNisSvc`, check for fresh 5008/3002,
   then `Update-MpSignature`.
3. Launch the **untouched tracked** `MyBot.run.exe` once, before compiling anything. Confirm it stays
   responsive and logs past `FinalInitialization` into the event loop.
4. If 5008 recurs: latest platform `MpCmdRun.exe -ResetPlatform`, reboot, Windows Update + signatures,
   retest. Only consider a temporary fully-qualified file exclusion after Defender is healthy **and**
   a fresh trace still shows app-specific scanning.

### Source hardening (do regardless of Defender)

Never call mixed-mode DLL exports synchronously on the GUI startup thread. Enter the event loop
first; probe and initialise the engine in a **separate x86 helper process with a bounded timeout**.
On stall, kill only the helper, keep the GUI alive, show `Engine unavailable` with actionable
diagnostics, and disable Start. **Moving the same unbounded call to Start is not sufficient.** This
is correct engineering independent of the current fault, and it is the difference between "a hung
antivirus freezes the app" and "a hung antivirus shows a message".

---

## 6. Open gaps

Status is per tree, because they differ.

| # | Gap | Cloud | Windows |
|---|---|---|---|
| 1 | `g_oRunPlannerIntent` assigned, nothing consumes it — no Start path | **open** (confirmed) | open |
| 2 | `RunEventAppendJsonLine` has only a test callsite, so the Activity panel is always empty | **open** (confirmed) | open |
| 3 | `_RunPlannerServiceHealthy` uses substring checks; parse JSON, require `ok==true` and `bridge==autoit-plan-file-v1` | n/a — function does not exist | open |
| 4 | `plan_status()` can label a corrupt file Saved while AutoIt rejects it | n/a — function does not exist | open |
| 5 | Docs said unknown fields rejected, POST normalised and returned 200 | **fixed** (`7c7f5062`) | open |
| 6 | Stale README claims (seven sections, native metadata, Guardian absence) | needs a pass | open |
| 7 | Real browser acceptance: responsive, zoom, keyboard/focus, a11y, light/dark, density, Hero cap, offline/save-error, console/network | partial — headless shots only | open |
| 8 | Full round trip: browser Save → plan file → native Load → Prepared/blocked, never auto-starting | file half done, native half needs Windows | open |
| 9 | Keep the nonclaims explicit | held | hold it |

**Gap 7 note:** sections rerender after a control change, so watch for focus loss. The cloud tree's
`refresh()` replaces only the changed row rather than the whole panel, which reduces but may not
eliminate this.

---

## 7. What must not be claimed

These are true in both trees and must survive any rewrite:

- **20 required current-client fixtures are missing.** Recognition is unverified.
- **Runtime evidence is empty. 0 of 24 support capabilities are ready.**
- **LDPlayer, MuMu and current-client combat have never been hardware-validated.**
- **No battle surface is verified.** Nothing here moves one.
- In the cloud tree, **pacing is the only planner setting that reaches the bot.** Army, Search,
  Donate, Events, Limits, Loot and the rest are stored and validated but drive nothing, because the
  legacy engine does not consume the run intent (gap 1).
- **Pacing defaults are reasoned, not measured.** Nobody has timed how long this client's screens take
  to settle. 400 ms is a starting point.

### Inherited feature, easy to mistake for new work

Upstream v8.2.0 already ships `$g_bUseRandomClick` — a BOT Options checkbox that scatters click
coordinates by ±5px and click speed by ±15%, wired through `saveConfig`/`readConfig`/`applyConfig`.
It predates both work streams and is untouched by them. The pacing work is a separate mechanism and
does not extend it.

---

## 8. Suggested order for the next session

1. Decide the tree question (§1). Nothing else is safe until this is settled.
2. Fix the launch fault (§5), untouched binary first, before any compile.
3. Land the source hardening so an engine stall can never freeze the GUI again.
4. Then gap 1 — an explicit Apply/Start boundary — which unblocks most of the planner.
5. Then gap 2, so the Activity panel shows something real.
6. Then the recognition fixtures, which is the actual blocker on the whole project.

### Validation to run once Windows is healthy

Python compileall; repo audit; AutoIt lint; catalog and UI validators; generator `--check`s; current
model and client verifiers; planner preview and selftest; fixture, evidence and readiness validators;
Au3Check on every entry point; then execute RunContracts, GameCatalog and RunEngine under x86 AutoIt.

Do not report completion from tests or a background process alone. The native app must be seen
running and responsive.
