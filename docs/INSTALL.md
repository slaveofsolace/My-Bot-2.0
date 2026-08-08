# Development installation

This guide sets up the current source baseline for development and controlled compatibility testing. It does not claim that the August 2026 game client is fully supported.

## Supported setup status

| Item | Current status |
| --- | --- |
| Operating system | Windows 10/11 is the development target. Older Windows versions in the inherited README are not part of the new support plan. |
| Source language | AutoIt 3.3.16.1 and 3.3.18.0 are checked by the Windows CI matrix. |
| Elevation | The main script contains `#RequireAdmin` and will request elevation. |
| BlueStacks 5 | Present in the v8.2.0 source. Current-version smoke test still required. |
| MEmu | Present in the v8.2.0 source. Current-version smoke test still required. |
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

Do not copy profile or configuration folders from an older MyBot installation. The inherited code already warns against old configs, and the unified project does not yet have a complete migration layer.

Keep the original folder untouched. Use a separate copy for each experimental branch until profile migration tests exist.

## 4. Run from source

The source entry point is:

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
preferred during development; published binaries still require provenance and release smoke-test evidence.

## 5. Configure the Android environment

1. Start the chosen emulator manually.
2. Create or select a dedicated test instance.
3. Use the resolution and DPI expected by the existing MyBot documentation for that emulator.
4. Launch Clash of Clans manually and finish all first-run, update, consent, tutorial, and account dialogs.
5. Return to the Home Village.
6. In the application, select the detected emulator and instance.
7. Verify that capture, window positioning, and a known Home Village state are recognized before starting a feature.

Do not assume that successful ADB connection means screen recognition is current.

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

Related entry points such as Mini GUI and Watchdog should be compiled from their matching source at the same commit.

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

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Script immediately fails | Confirm AutoIt 3.3.16.x, required runtimes, a simple local path, and elevation. Run syntax check from SciTE. |
| Emulator is not listed | Start it first. Confirm the source currently contains an adapter for that product. A recent xbebenk adapter is not automatically present in this branch. |
| ADB connects to the wrong instance | Stop testing and record emulator name, version, instance index, reported device, and ADB port. Do not change formulas without an adapter-level review. |
| Window is found but nothing is recognized | Verify resolution, DPI, zoom, scenery, current game screen, and whether the client is newer than the available image set. Capture a redacted screenshot fixture. |
| Repeated unknown popup | Stop the run. Save the screenshot and log. Add the screen to the interruption inventory instead of adding a blind click. |
| Settings behave unexpectedly | Reproduce with a fresh profile. Do not reuse an older INI until migration is implemented. |
| Stop takes too long | Capture the current engine state and last action. A blocked input or unbounded retry must be fixed rather than hidden by force-closing. |
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
