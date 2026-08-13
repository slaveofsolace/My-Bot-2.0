# Development installation

This guide sets up the current source baseline for development and controlled compatibility testing. It does not claim that the August 2026 game client is fully supported.

## Supported setup status

| Item | Current status |
| --- | --- |
| Operating system | Windows 10/11 desktop is the development target. Windows Server editions, including Server 2019 and 2022, and older Windows versions in the inherited README are outside the support plan. |
| Source language | AutoIt 3.3.16.1 and 3.3.18.0 are checked by the Windows CI matrix. |
| Elevation | The main script contains `#RequireAdmin` and will request elevation. |
| BlueStacks 5 | Present in the v8.2.0 source. Current-version smoke test still required. |
| MEmu | Exact-instance adapter is present and statically checked. Current MEmu 9.5.3 instance/ADB/background/click/zoom/recovery smoke evidence is still required. |
| Nox | Present in the v8.2.0 source. Current-version smoke test still required. |
| MuMu Player 12 / LDPlayer 9 | Adapter code is present. A dated current-version smoke test is still required. |
| Google Play Games on PC | A future clean-room platform target. It is not implemented by the current AutoIt baseline. |

Do not advertise an emulator/version as supported until a dated smoke-test record is attached to a release.

## 1. Prepare Windows

Use a dedicated Windows 10 or Windows 11 test machine or virtual machine with:

- current Windows updates
- current graphics drivers
- Microsoft Visual C++ 2010 Redistributable **x86**
- .NET Framework 4.5 or later Windows-provided compatibility
- Python 3.13 with `py.exe` or `python.exe` available for the Control Center and non-CLR installer
- AutoIt 3.3.16.x
- SciTE for AutoIt, recommended for source work
- one supported Android environment installed separately

Restart Windows after installing runtime components.

## 2. Get the source

`master` carries the complete runnable source, so a plain clone is all you need.

With Git:

```powershell
git clone https://github.com/slaveofsolace/My-Bot-2.0.git
cd My-Bot-2.0
```

Without Git, download the archive from GitHub and extract it to a simple local path such as:

```text
C:\Tools\My-Bot-2.0
```

Avoid protected folders, cloud-synced folders, unusual Unicode paths, and deeply nested directories during initial testing.

## 3. Start with a clean profile

Installed releases keep mutable profiles outside the replaceable program directory at
`%LOCALAPPDATA%\My Bot 2.0\Profiles`. A first install creates the safe `MyVillage` starting profile
and selects it in `profile.ini`. Program upgrades and uninstall leave this per-user data in place.

The installer can make a one-time, non-destructive copy of a profile directory from this same source
baseline. From the extracted release directory, run:

```powershell
& ".\Install My Bot 2.0.cmd" -ProfileSourceDirectory "C:\path\to\My-Bot-2.0\Profiles"
```

The source must contain `[general] defaultprofile=...` in `profile.ini`, and the selected profile
folder must exist. The selected name is limited to letters, numbers, dot, underscore, and hyphen so
the exact pinned Mini GUI can forward it safely. Migration refuses to overwrite anything already in
the per-user Profiles directory. It copies the source; it never moves or deletes it.

Do not use this copy option for configuration folders from an older MyBot version. The inherited
code warns against old configs, and this project does not claim schema migration from older releases.
Keep the original folder untouched until the copied profile has passed controlled startup checks.

## 4. Run the application or source

For an extracted, internally reviewed LocalRuntime package, double-click `Install My Bot 2.0.cmd`.
It installs for the current Windows user under `%LOCALAPPDATA%\Programs\My Bot 2.0` and creates a
Start-menu entry. Afterward, press the Windows key and type `My Bot 2.0`. Use Windows Installed apps
or the Start-menu uninstall shortcut to remove it. The installer deliberately refuses source-tree
folders and packages whose release manifest, marker, or launcher provenance is invalid. Uninstall
removes the application and its registration but retains `%LOCALAPPDATA%\My Bot 2.0\Profiles`.
The command launcher uses the standard-library Python installer so validation, registration, and
rollback do not depend on Windows PowerShell or the CLR. The reviewed PowerShell implementation is
retained as a separately testable compatibility reference, but is not the default install path.

For normal use, run:

```text
My Bot 2.0.exe
```

The launcher requests elevation and starts the exact pinned MyBot.run v8.2
`MyBot.run.MiniGui.exe`. The Mini GUI stays visible and functional as the native safety controller
for Start, Stop, Pause and Resume. It launches `MyBot.run.exe` as the modern `/ng` backend and
passes its exact process ID through `/guipid`. The launcher also selects the validated per-user
default profile and passes only that profile plus `/nowatchdog` to the exact Mini GUI. The installer
creates `Profiles` beside the installed executables as a verified directory junction to
`%LOCALAPPDATA%\My Bot 2.0\Profiles`, so the unchanged Mini and backend read the same persistent
tree. Launcher and compiled backend resolve the junction and refuse startup unless its canonical
target is exactly that per-user directory. The backend passes that same resolved root explicitly to
the browser Control Center. The upstream `/profiles=` switch remains available only for compatible
direct source launches.

The launcher snaps the Mini GUI beside the selected exact BlueStacks top-level window. It keeps
both windows independent and does not embed, reparent, or rename BlueStacks. This external
side-by-side placement is the supported docked layout.

Use **MINIMIZE BOTH - BACKGROUND** on the companion strip to minimize the bound Mini controller and
the exact BlueStacks instance together. Minimizing either member of the docked pair also minimizes
the other; restoring either restores and re-docks both. The bot continues through verified ADB
capture and input without requiring BlueStacks to take foreground focus. Command-line automation
may use `/background` and `/foreground` for the same paired transition.

Keep `My Bot 2.0.exe`, the exact pinned `MyBot.run.MiniGui.exe`, `MyBot.run.exe`,
`MyBot.run.exe.config`, and the empty `MyBot.run.txt` compatibility marker together. The marker is
required and must remain zero bytes. The Mini GUI and backend names and identities are retained
because the inherited image engine validates them; the configuration lets the backend load its
managed dependencies from `lib`.

Closing the Mini GUI stops the native controller/backend pair. This independent downstream layout
is not endorsed, sponsored, supported, or approved by the upstream MyBot.run project.

If an owned AutoIt error or stale controller prevents a normal restart, run the installed launcher
with `/recover` (or `/repair`) from an existing shortcut or deployment entry. The elevated launcher
logs the full owned error text to `artifacts/launcher-recovery.log`, closes only dialogs whose process
image is inside this installation, then closes only the exact-path Mini GUI, backend, and duplicate
launcher processes. It never targets BlueStacks, Clash of Clans, Windows security prompts, or an
unrelated AutoIt application. Re-run `My Bot 2.0.exe` normally after recovery completes.

For development, the source entry point is:

```text
MyBot.run.au3
```

Recommended development flow:

1. Right-click `MyBot.run.au3` and open it in SciTE.
2. Run the AutoIt syntax check.
3. Start the script from SciTE or use AutoIt's `Run Script` action.
4. Accept the Windows elevation prompt only when the source path and commit are trusted.
5. Review the startup log before enabling any run feature.

The repository contains inherited and locally compiled executable files. Source-first execution is
preferred during development. `config/binary-provenance.json` records the exact shipped hashes and
build origins; a release still requires its runtime smoke-test evidence.

## 5. Configure the Android environment

1. Start the chosen emulator manually.
2. Create or select a dedicated test instance.
3. Use the resolution and DPI expected by the existing MyBot documentation for that emulator.
4. Launch Clash of Clans manually and finish all first-run, update, consent, tutorial, and account dialogs.
5. Return to the Home Village.
6. In the application, select the detected emulator and instance.
7. Verify that capture, window positioning, and a known Home Village state are recognized before starting a feature.

Do not assume that successful ADB connection means screen recognition is current.

The MEmu adapter uses the selected VM's reported ADB host/port and prefers an emulator-compatible
ADB executable. Do not copy MyBotPy's 1600x900 coordinates into this AutoIt engine: this project uses
its own 860x732 coordinate contract. Select the exact MEmu instance and keep the first run non-spending
until capture, input, drag, zoom and recovery are visually confirmed.

## 6. First controlled check

Before a normal run, record this minimum check:

- application starts without an unhandled dialog
- selected emulator and instance are correct
- game window is found
- screenshot capture succeeds
- Home Village is recognized
- Stop returns the engine to Idle
- application exits cleanly
- watchdog exits or reconnects as designed
- no credentials or login codes appear in logs

Keep the first run short and disable upgrade, spending, donation, chat, and account-rotation features until their current-client flows are verified.

## 7. Compile locally

The repository has repeatable source and contract validation, but the release-packaging workflow is
still being established. For local development:

1. Use the AutoIt version recorded for the branch.
2. Open `MyBot.run.au3` in SciTE.
3. run syntax checking first
4. compile with the existing wrapper directives
5. keep the source commit SHA beside the output
6. do not publish the output as an official project release without dependency and smoke-test evidence

Related development entry points such as Watchdog should be compiled from their matching source at
the same commit. A locally compiled or rebranded Mini GUI is not a drop-in replacement for the exact
pinned v8.2 Mini GUI used by the normal compatibility path unless that identity-sensitive path has
been separately proved.

### Redistribution boundary

The GPL notice applies to the source code derived from MyBot.run. It does not establish GPL or
open-source status for the inherited compiled ImgLoc component, whose redistribution terms remain
separate and unclear or restrictive. Hash and provenance records establish identity, not permission.
Do not describe the complete binary bundle as wholly GPL-licensed or open source. Obtain written
permission from the rights holder or replace ImgLoc with a clearly licensed open implementation and
revalidate it before public binary redistribution.

## Command-line options

The current entry point includes options such as:

```text
/autostart
/nowatchdog
/dpiaware
/dock1
/dock2
/nobotslot
/debug
/minigui
/nogui
/hideandroid
/minimizebot
/console
/help
```

Use `/help` for the source-defined list. Developer and no-watchdog modes should not be the default for ordinary testing.
The inherited `/dock1` and `/dock2` switches are not used to create the supported Mini GUI layout.
The launcher positions the Mini GUI and exact BlueStacks window side by side without reparenting
either window.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Script immediately fails | Confirm AutoIt 3.3.16.x, required runtimes, a simple local path, and elevation. Run syntax check from SciTE. |
| Emulator is not listed | Start it first. Confirm the source currently contains an adapter for that product. A recent xbebenk adapter is not automatically present in this branch. |
| ADB connects to the wrong instance | Stop testing and record emulator name, version, instance index, reported device, and ADB port. Do not change formulas without an adapter-level review. |
| Window is found but nothing is recognized | Verify resolution, DPI, zoom, scenery, current game screen, and whether the client is newer than the available image set. Capture a redacted screenshot fixture. |
| Repeated unknown popup | Stop the run. Save the screenshot and log. Add the screen to the interruption inventory instead of adding a blind click. |
| Settings behave unexpectedly | Confirm `profile.ini` and the selected folder under `%LOCALAPPDATA%\My Bot 2.0\Profiles`. Reproduce with a fresh current-version profile; do not reuse an older-version INI. |
| Stop takes too long | Capture the current engine state and last action. A blocked input or unbounded retry must be fixed rather than hidden by force-closing. |
| An AutoIt error dialog blocks restart | Preserve `artifacts/launcher-recovery.log`, then run `My Bot 2.0.exe /recover`. Recovery logs and closes only checkout-owned AutoIt errors and exact-path bot processes; it does not click through arbitrary Windows dialogs. |
| Mini GUI opens but the backend closes or ImgLoc blocks the run | Confirm the exact pinned v8.2 Mini GUI and backend are unmodified, `MyBot.run.exe.config` is beside them, and `MyBot.run.txt` exists as a zero-byte file. Do not rename or patch the protected binaries. |
| Managed engine does not answer within 15 seconds | The isolated probe has already stopped the hung helper. Confirm Windows Security protection is running and review its Operational log. If Defender or the 32-bit CLR is stalled, restart Windows once, then relaunch the app. Do not add antivirus exclusions or disable tamper protection. |
| Start reports `Managed engine did not answer` | The x86 helper contained a mixed-mode DLL startup stall. Inspect Windows Security and `.NET Framework` health. Defender Operational events `5008` followed by `3002` indicate an engine/filter failure that must be repaired before retrying; restart My Bot 2.0 afterward. Do not disable Defender or add a broad exclusion. |
| Antivirus warning | Build from reviewed source. Verify any native DLL or inherited executable independently. Do not disable endpoint protection as an installation step. |
| Game account warning or penalty | Stop using the environment. Supercell prohibits unapproved gameplay bots on live accounts. Use only environments and accounts for which explicit authorization exists. |

## Diagnostic report template

Include this information with a compatibility report:

```text
Project commit:
Windows version:
AutoIt version:
Emulator/product version:
Instance name/index:
Android version:
Game client version:
Display resolution and scale:
Selected input/capture mode:
Profile created fresh: yes/no
Expected screen/action:
Observed result:
Last 100 relevant log lines:
Redacted screenshot attached: yes/no
Reproduction steps:
```

Never include login codes, passwords, recovery details, payment information, or personal chat content.
