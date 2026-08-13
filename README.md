<div align="center">

# My Bot 2.0

**A Clash of Clans automation bot for Windows**

My Bot 2.0 v2.0.0: a local browser control center backed by the
MyBot.run v8.2.0 native automation engine.

The GPL notice covers the source code described below. The inherited compiled ImgLoc component has
separate, unclear or restrictive terms and is not represented here as GPL-licensed or open source;
see [Licence](#licence).

[![CI](https://github.com/slaveofsolace/My-Bot-2.0/actions/workflows/ci.yml/badge.svg)](https://github.com/slaveofsolace/My-Bot-2.0/actions/workflows/ci.yml)
[![Windows AutoIt](https://github.com/slaveofsolace/My-Bot-2.0/actions/workflows/windows-autoit.yml/badge.svg)](https://github.com/slaveofsolace/My-Bot-2.0/actions/workflows/windows-autoit.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](License.txt)
[![AutoIt](https://img.shields.io/badge/AutoIt-3.3.16%20%7C%203.3.18-5D83AC.svg)](https://www.autoitscript.com/)

</div>

---

> **Read this first.** This is a working repository, not a finished release.
> The planning and orchestration layer is real, tested code. The layer that
> recognises what is on screen and clicks things has **not** been confirmed
> against the current game client. Nothing here claims to work until somebody
> has watched it work.

---

## Contents

| Section | What's in it |
|---|---|
| **[What this is](#what-this-is)** | The problem it solves, and how |
| **[Status](#status)** | What works, what does not |
| **[Install](#install)** | Five steps, Windows |
| **[The Run Planner](#the-run-planner)** | How you describe a session |
| **[Verified vs diagnostic](#verified-vs-diagnostic-runs)** | Why unverified runs are allowed |
| **[Layout](#layout)** | Where things live |
| **[Developing](#developing)** | Tooling and checks |
| **[What's left](#whats-left)** | What is blocked, and on what |
| **[Credits](#where-the-code-came-from)** | Upstream sources |

---

## What this is

The source starting point is [MyBot.run](https://github.com/MyBotRun/MyBot) v8.2.0, a long-running
GPL-licensed Clash of Clans bot written in AutoIt. It does a lot well, and its AutoIt source carries
years of accumulated automation work. The inherited compiled ImgLoc component used by screen
recognition is a separate dependency; recording its origin and hash does not establish
redistribution rights.

What it never had was a clear description of *what a run should do*. Settings are scattered across
a dozen tabs, and the bot's idea of "attack" is whatever code path happens to get reached. This
project adds that missing layer.

<details>
<summary><b>A run engine that models a session explicitly</b></summary>

<br>

A run is four objects that validate independently and can be tested without launching the game:

| Object | Holds |
|---|---|
| `RunPlan` | Strategy, stop conditions, resource targets, upgrade policy |
| `RunIntent` | Binds a plan to one **exact** battle surface, a Hero loadout, and that surface's attack quota |
| `RunSession` | State machine: counters, loot, stop reason, verification state |
| `AccountQueue` | Which local profiles to rotate through, in order |

The load-bearing word is *exact*. Regular and Ranked are separate surfaces with separate rules.
Legend III, II and I have different attack budgets on different schedules. The old model had one
"multiplayer" path, which meant you could select one thing and run another whenever the old
coordinates happened to still respond.

A `RunIntent` carries the exact surface from the moment you pick it, and refuses to open a session
if the surface and the plan disagree.

</details>

<details>
<summary><b>Attack budgets that know what you actually have left</b></summary>

<br>

Legend I publishes a budget of 8 attacks per League Day. That is **not** the same as *you have 8
attacks left right now* — and treating the two as interchangeable is how a bot ends up hammering a
surface that has nothing left.

A `BattleQuota` starts unobserved:

```
remaining   = -1      <- unknown
verified    = false   <- nobody has looked
observed_at = -1
```

A finite surface will not start until that count has been read off the client. Once observed,
consumption decrements the real number and refuses to over-consume. Regular Battles are catalogued
as unlimited and skip all of it.

</details>

<details>
<summary><b>Six Heroes, four slots</b></summary>

<br>

The Hero Hall holds six — Barbarian King, Archer Queen, Minion Prince, Grand Warden, Royal
Champion, Dragon Duke — but only four can be active at once. So a loadout is a bounded selection,
not a fixed array.

Membership is checked against the generated catalog rather than a hard-coded list, and Town Hall
gating runs both directions: adding a Hero you have not unlocked is rejected, and *lowering* your
Town Hall releases any Hero that would no longer be available, instead of leaving you with a
selection you cannot field.

</details>

<details>
<summary><b>A planner that explains itself</b></summary>

<br>

Every control carries a summary, a full description, its prerequisites, and — when greyed out —
the specific reason. Not "unavailable", but *which capture is missing*.

The tab renders from a generated descriptor rather than a hand-written layout, so adding a battle
surface or changing a disabled reason is a catalog edit. CI validates the metadata against the game
catalogs, so the planner cannot quietly drift away from the engine.

The Control Center also offers TH2-TH18 compatibility presets. A preset is only a reviewed starting
point: selecting it immediately loads the exact script, Heroes, limits, and every other preset-owned
field into the visible form. It does not save or start anything until **Apply plan** is pressed. The
active profile still owns the trained army, and the preview says when a bundled script requires that
army to match.

</details>

---

## Status

| Area | State |
|---|---|
| Run engine — plan, intent, session, quota, loadout, events | Written, contract-tested |
| Run Planner tab | Written, renders from generated metadata |
| My Bot 2.0 launcher and local Control Center | Source-tested; the current source revision still needs a fresh binary/runtime receipt |
| Windows compile — Au3Check, both AutoIt versions | Green |
| Game model through July 2026 | Catalogued from official sources |
| LDPlayer 9 and MuMu Player 12 adapters | Written, **never run on real hardware** |
| Screen recognition for the current client | Historical TH17 observations exist; all required current-client fixtures remain missing for the current source revision |
| Attack execution | Older binaries completed bounded Standard and Smart TH17 observations; neither proves the current source revision or general strategy quality |

**The honest summary:** older reviewed binaries produced bounded TH17 observations for zoom,
red-line geometry, troop and Hero deployment, battle accounting, Return Home, automatic stop, and
part of the Smart spell policy. Those receipts are useful regression references, but they do not
verify a binary built from the current source revision, every required current-client fixture, or an
improvement in strategy quality. Other Town Halls, armies, surfaces, and most gameplay scopes remain
unverified; CI does not substitute for those runs.

---

## Install

You need **Windows 10 or 11**, **Python 3.13**, an **Android emulator**, and **AutoIt**.

For an internally reviewed LocalRuntime ZIP, extract it and double-click **`Install My Bot 2.0.cmd`**.
The per-user installer verifies the package, installs it under `%LOCALAPPDATA%\Programs\My Bot 2.0`,
and registers **My Bot 2.0** in the Start menu and Windows Installed apps. You can then press the
Windows key, type `My Bot 2.0`, and launch it normally. The LocalRuntime package is not a public
distribution grant for inherited ImgLoc binaries; see the redistribution boundary below.

<details>
<summary><b>Step 1 &nbsp;·&nbsp; Install AutoIt</b></summary>

<br>

Grab it from [autoitscript.com](https://www.autoitscript.com/site/autoit/downloads/). Either
3.3.16.1 or 3.3.18.0 works — CI tests both.

Install the full package rather than just the runtime. You need `Au3Check.exe` if you plan to make
changes, and the SciTE editor is a genuinely pleasant way to work on AutoIt.

</details>

<details>
<summary><b>Step 2 &nbsp;·&nbsp; Install an emulator</b></summary>

<br>

The bot drives Clash of Clans inside an Android emulator over ADB. Any of these:

| Emulator | Notes |
|---|---|
| **LDPlayer 9** | New adapter. Multi-instance ADB addressing implemented (`5554 + 2×index`). Untested on hardware. |
| **MuMu Player 12** | New adapter. Reads each instance's ADB port from the emulator instead of assuming one. Untested on hardware. |
| **BlueStacks 5** | Exact Pie64 binding and historical local smoke evidence exist. The current source revision still needs a fresh capture/input/Start-Stop receipt. |
| **MEmu** | Inherited exact-instance adapter with VM-provided ADB addressing and renderer-aware background mode. Static checks pass; a current MEmu 9.5.3 hardware smoke test is still required. |
| **Nox** | Inherited source only; it is not in the current supported-capability ledger and must be treated as unavailable until catalogued and tested. |

> Set the emulator to **860 × 732** before first use. The bot's coordinates assume it, and a
> mismatch is by far the most common cause of "the bot clicks the wrong thing".

Start the emulator once and let it finish setting up before pointing the bot at it — several
emulators do not register their instances until they have run at least once.

</details>

<details>
<summary><b>Step 3 &nbsp;·&nbsp; Get the source</b></summary>

<br>

```bash
git clone https://github.com/slaveofsolace/My-Bot-2.0.git
cd My-Bot-2.0
```

</details>

<details>
<summary><b>Step 4 &nbsp;·&nbsp; Check the clone is intact</b></summary>

<br>

Needs Python 3.11 or newer. Takes a few seconds:

```bash
python tools/repo_audit.py
python tools/lint_autoit.py --all
```

The audit also verifies every shipped executable, DLL, and archive against
[`config/binary-provenance.json`](config/binary-provenance.json). Missing records, byte-size drift,
and SHA-256 mismatches are release-blocking errors.

Anything reported as an *error* means the clone is incomplete or something is genuinely broken.

</details>

<details>
<summary><b>Step 5 &nbsp;·&nbsp; Run it</b></summary>

<br>

For the built application, double-click **`My Bot 2.0.exe`**. It starts the exact pinned MyBot.run
v8.2 **`MyBot.run.MiniGui.exe`** with the required administrator permission and opens the local
Control Center in your browser. The Mini GUI remains visible and functional as the native safety
controller for Start, Stop, Pause and Resume. It launches the modern **`MyBot.run.exe`** backend in
`/ng` mode with `/guipid` set to that exact Mini GUI process. The browser Control Center remains the
primary planner while the backend performs the automation work.

The launcher snaps the Mini GUI beside the selected exact BlueStacks top-level window. This is a
side-by-side layout of two independent windows: it does not embed, reparent or rename BlueStacks.

For source development, right-click `MyBot.run.au3` and choose **Run Script (x86)**.

> Use the **32-bit** option. The bot refuses to start under x64 and will tell you so, but it saves
> a confusing minute to get it right the first time.

The built launcher, exact pinned `MyBot.run.MiniGui.exe`, `MyBot.run.exe`,
`MyBot.run.exe.config`, and empty `MyBot.run.txt` compatibility marker must remain beside each
other. The marker is required and must remain zero bytes. The Mini GUI and backend keep their
upstream filenames and resource identities because the inherited image engine validates them; the
configuration loads managed dependencies from `lib`. These are internal compatibility details,
not the product name.

On first launch the bot creates a profile and writes its configuration under your Windows user
profile. Nothing is written outside that and the repository directory.

</details>

<details>
<summary><b>If something goes wrong</b></summary>

<br>

| Symptom | Usual cause |
|---|---|
| `Don't Run/Compile the Script as (x64)` | Started with the 64-bit interpreter. Use Run Script (x86). |
| Bot starts but sees nothing | Emulator is not at 860 × 732, or ADB is not connected. |
| Bot attaches to the wrong window | More than one instance running. Pick the instance explicitly on the planner's Emulator tab. |
| Clicks land in the wrong place | Resolution mismatch, or emulator DPI scaling is off its default. |
| Start reports `Managed engine did not answer` | The isolated DLL probe timed out. Check `.NET Framework` and Windows Security health, resolve any Defender `5008`/`3002` failures, then restart My Bot 2.0. Do not add a broad antivirus exclusion. |
| Include errors on startup | Incomplete clone. Run `python tools/repo_audit.py` — it lists every include that fails to resolve. |

[`docs/INSTALL.md`](docs/INSTALL.md) goes deeper on each.

</details>

---

## The Run Planner

The **Run Planner** is the last tab in the main window. Thirteen focused sections:

| Section | What you set |
|---|---|
| **Destination** | The exact battle surface, and which strategy runs once a base is found |
| **Heroes** | Up to four active Heroes from the six in the Hero Hall |
| **Army** | Which troop, spell, and siege groups are available to the selected strategy |
| **Search** | Minimum loot and base filters used before an attack is accepted |
| **Emulator** | Which emulator, and which instance |
| **Pacing** | Action delay, settle time, and scheduled rest windows |
| **Donations** | Whether to request or donate, and the supported donation policy |
| **Events** | Clan Games, collectors, walls, and the supported lab policy |
| **Notifications** | Run lifecycle messages written to the event stream |
| **Stop conditions** | Time limit, battle limit, Star Bonus, failure limit |
| **Resource targets** | Stop once a Gold, Elixir, or Dark Elixir total is collected |
| **Between battles** | Supported upgrade policy and account-rotation settings |
| **Diagnostics** | Whether unverified surfaces are allowed to run |

Above those sections, the Town Hall dropdown covers TH2 through TH18. A saved plan that exactly
matches a preset reopens with that preset identified; otherwise it shows **Custom plan — your settings**
and lists the exact selected Heroes at the top.
TH6-TH15 recommendations use shipped scripts only where the script declares that Town Hall. Levels
without a declared script use the engine's Standard deployment and retain the active profile army;
they are compatibility fallbacks, not claims about the current attack meta. A scripted preset selects
deployment only: it does not import the CSV training table, so the active profile army must match.
Fallbacks explicitly select a four-Hero loadout instead of inheriting a stale manual choice. Selecting
a preset loads a complete unsaved plan, and **Apply plan** is still required to write it. Emulator
selection and diagnostic consent are never supplied by a preset.

The broader product goal is the complete repeatable game loop: attacks, training, collectors,
donation/request, Home and Builder Base upgrades, Laboratory, Clan Games, account rotation and
recovery. Existing source is not the same as current-client support. The machine-readable gates and
the per-scope proof still required are listed in
[`GAMEPLAY_SCOPE_MATRIX.md`](docs/development/GAMEPLAY_SCOPE_MATRIX.md).

Set what you want, press **Apply plan**, and you get one of three answers:

```
Ready
Ready as a diagnostic run
Blocked  ->  <the specific reason>
```

It never silently accepts a configuration the engine would reject. Unavailable choices are marked
in the dropdown and explained in the panel underneath: what the choice does, what it needs, and
what specifically is missing.

**Apply plan** validates and prepares the intent; it does not start the bot. **Start Bot** re-reads
the saved plan, applies every supported value to the native engine, opens the run session, and only
then activates pacing. Unsupported strategy, search, donation, event, notification, or account
rotation values are blocked with a specific reason instead of being silently ignored.

---

## Verified vs diagnostic runs

Most surfaces here are currently **unverified**. The game model says they exist and the engine
knows how to route to them, but nobody has captured what they look like on the current client, so
the bot cannot honestly claim to recognise them.

By default an unverified surface will not start. That is deliberate — the worst failure mode for a
bot like this is confidently doing the wrong thing.

But a route that refuses to start also cannot be debugged. So **Diagnostics → Allow unverified
surfaces to run** lets it proceed. Turning it on requires a note saying who is watching, and that
note is stored with the session.

What diagnostic mode does **not** do is change what the bot has been shown to do:

- the session is marked `unverified-diagnostic` the moment the route is attached
- the mark is a **one-way latch** — nothing in the codebase clears it
- every snapshot and every JSONL event carries it
- the planner shows a banner while an unverified surface is selected

So you can run something to find out how it behaves, and the record still says plainly that it was
an observation rather than a demonstration.

> The quota gate is **not** relaxed by diagnostic mode. No attacks left is a fact about the game,
> not a missing capture, and attacking anyway is just a bug.

---

## Layout

```
COCBot/
├── functions/
│   ├── Run/          run engine - plan, intent, session, quota, loadout, events, verification
│   ├── Game/         generated game catalog and screen-state registry
│   └── Android/      emulator backends, including the LDPlayer 9 and MuMu adapters
└── GUI/              AutoIt GUI, including the Run Planner browser bridge

config/
├── game/             source of truth - battle surfaces, Guardians, Heroes, screen states
└── ui/               Run Planner metadata, generated from the catalogs

docs/                 audit, architecture, engineering notes, compatibility matrix, install guide
tests/
├── autoit/           contract tests, run under AutoIt on Windows
└── fixtures/         current-client capture manifest (captures not yet supplied)
tools/                validators, linter, generators - plain Python, no dependencies
imgxml/  images/      screen-recognition templates inherited from upstream
```

Two files are **generated** and must never be hand-edited:

| Generated file | Source |
|---|---|
| `COCBot/functions/Game/GameCatalog.generated.au3` | `config/game/*.json` |
| `COCBot/GUI/RunPlannerMetadata.generated.au3` | `config/ui/run-planner.settings.json` |

CI fails if either drifts from its source.

---

## Developing

Everything in `tools/` is standard-library Python 3.11+, so it runs anywhere:

| Command | Checks |
|---|---|
| `python tools/lint_autoit.py --all` | Block balance, `ByRef` misuse, parameter order, duplicate functions, undeclared globals, unresolved includes and calls |
| `python tools/validate_translation_keys.py` | Conflicting translation defaults and duplicate English catalog keys |
| `python tools/repo_audit.py` | Required files, include resolution, secret patterns, upstream pins, binary provenance and hashes |
| `python tools/validate_game_catalog.py` | Game catalogs against their schemas |
| `python tools/validate_ui_metadata.py` | Planner metadata against the game catalogs |
| `python tools/check_town_hall_presets.py` | TH2-TH18 coverage, source-backed script choices, complete Hero gates, selection-time loading, and explicit save separation |
| `powershell -File tools/run_supervised_battle_acceptance.ps1 -AuthorizeOneBattle` | One explicitly authorized Smart battle; exact zoom and troop depletion, deterministic side/start events, one issued ability per selected Hero, proven Rage and Freeze inventory decreases, internal one-battle stop, preserved plan/process identity, and operator-visible confirmation |
| `python tools/verify_current_game_model.py` | That the generated catalog is actually wired into the runtime |
| `python tools/generate_game_catalog_autoit.py --check` | Generated catalog drift |
| `python tools/generate_run_planner_autoit.py --check` | Generated planner drift |

**About the linter.** `Au3Check` only runs on Windows, so `lint_autoit.py` catches the same classes
of mistake on any machine: unbalanced blocks, `ByRef` parameters carrying defaults or bound to
expressions, required parameters after optional ones, duplicate definitions, undeclared globals,
and functions a build calls but never includes.

It resolves each entry point's include graph the way AutoIt does — case-insensitively, skipping
`#cs`/`#ce` regions, handling `_` line continuations — which is how it catches a module that
compiles in one build and not another. It parses the complete AutoIt source tree cleanly.

To change what the planner offers, edit the catalogs and regenerate:

```bash
python tools/generate_run_planner_settings.py
python tools/generate_run_planner_autoit.py
python tools/validate_ui_metadata.py
python tools/check_town_hall_presets.py
```

---

## What's left

Everything below is blocked on something that cannot be produced without a Windows machine running
the actual game. Listing it honestly beats a progress bar.

<details>
<summary><b>Screen captures — blocks nearly everything else</b></summary>

<br>

[`tests/fixtures/current-client/manifest.json`](tests/fixtures/current-client/manifest.json) lists
**20 required captures**, all currently missing: Town Hall 18, Guardians, the six-Hero Hero Hall,
Dragon Duke, each battle surface entry screen, Hero Journey, Global Chat, battle fast-forward, the
Builder Base changes, and the current army screens.

The manifest specifies the capture contract — 860 × 732, PNG, sRGB, with player names, clan names,
chat text and account identifiers redacted before committing.

Until these exist there is no way to build recognition templates, and no way to move any surface
from unverified to verified.

Regular Battle with Standard deployment has bounded TH17 live proof. A later Smart run from the
reviewed `10bef479` binary/source chain exercised the current role-specific phase policy: three enemy
zoom gestures produced 240 red-line points, the local policy selected the BL side nearest the Town
Hall, 23 deployable troops reached zero, all four selected Heroes received phase commands, Rage was
quantity-proved from three to zero, and Freeze was quantity-proved from five to four before a later
unconfirmed Freeze disabled further clicks. The battle completed at two stars/55 percent, returned
home, and stopped on the one-battle limit. This is one automated mechanics observation without a
stored human visual receipt—not strategy superiority, every base layout, every Town Hall policy,
other battle surfaces, CSV scripts, or the still-missing fixture matrix.

</details>

<details>
<summary><b>Recognition and execution</b></summary>

<br>

Image templates, OCR regions, safe-click regions, route entry confirmation, and reading the
remaining-attack count off each limited surface. All of it depends on the captures above.

</details>

<details>
<summary><b>Emulator testing</b></summary>

<br>

The MEmu, LDPlayer 9 and MuMu adapters need a controlled run on real hardware: instance zero and a
non-zero instance, exact ADB attachment, background capture, clicks and drags, zoom, restart and
shutdown. MEmu is statically wired and was compared against the separately licensed MyBotPy design,
but MEmu is not installed on the current test machine.

</details>

<details>
<summary><b>Data completion</b></summary>

<br>

Town Hall 18 building costs, levels and durations; Guardian data; current equipment; Dragon Duke
upgrade data; the current Army Recipe and Cookbook structures.

</details>

<details>
<summary><b>Release engineering</b></summary>

<br>

All shipped executables, DLLs and archives are recorded in
[`config/binary-provenance.json`](config/binary-provenance.json) with exact SHA-256 hashes, sizes,
and either their repository-introduction commit or local AutoIt build chain. The repository audit
fails if a publishable binary is missing from that manifest or changes without review. Reproducible
compilation and a signed release manifest are still not set up.

Integrity records are not redistribution permission. Public binary redistribution remains on hold
for the inherited ImgLoc component until written permission is obtained from its rights holder or it
is replaced with a clearly licensed open implementation and the replacement is revalidated.

</details>

---

## Where the code came from

[`upstreams.lock.json`](upstreams.lock.json) pins every source to an exact commit with its licence
and import policy.

| Source | Role |
|---|---|
| [MyBotRun/MyBot](https://github.com/MyBotRun/MyBot) v8.2.0 | The base. Complete runnable AutoIt source tree. |
| [xbebenk/MBR_xbebenkMod](https://github.com/xbebenk/MBR_xbebenkMod) | Recent community compatibility work, adapted change by change. |
| [muratcandegirmenci78-lab/canmurat](https://github.com/muratcandegirmenci78-lab/canmurat) | Pinned for lineage comparison. No unique changes adopted. |
| [clashautoloot/Clash-AutoLoot](https://github.com/clashautoloot/Clash-AutoLoot) | Behaviour reference only. |
| [evgmalkov/mybot-py](https://github.com/evgmalkov/mybot-py) | MIT MEmu, cached-frame, batched-input and gameplay-loop reference. No executable or templates imported. |

This is an independent downstream project. Listing an upstream source documents lineage and does
not imply endorsement, sponsorship, affiliation, support, or approval by that project or its
contributors.

Two of those need explaining:

**xbebenk** is the most useful recent community source, but its core derives from MyBot v7.9.9
while this project sits on v8.2.0. Overlaying it wholesale would regress the newer architecture, so
changes are adapted individually. The LDPlayer 9 multi-instance ADB correction came across this
way — the fix was real, but v8.2.0 has no equivalent of the file it patched, so it became a proper
adapter rather than a copied file. Its chest and Builder Base patches target code paths that do not
exist here and were deliberately left alone; equivalent fixes get written when a capture reproduces
the underlying problem.

**Clash-AutoLoot** publishes documentation and compiled releases, not source under a licence that
permits reuse. No binary was unpacked or decompiled. Its externally visible behaviour — run
dashboards, stop conditions, multi-account queues, Star Bonus mode — informed the requirements for
the run engine, which was then written from scratch. Anything centred on being undetectable or
surviving enforcement was excluded.

---

## Account safety

Supercell's terms prohibit unapproved third-party software, and using a bot can get an account
permanently banned. That is a real consequence and this repository does not pretend otherwise.

This project deliberately does **not** implement detection evasion, ban avoidance, behaviour
disguising, or anything else whose purpose is to make automated play harder to identify. Feature
requests along those lines will be declined. See [`SECURITY.md`](SECURITY.md) for reporting and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for scope.

**Use accounts you are willing to lose.**

---

## Licence

[GNU General Public License v3](License.txt) applies to the source code derived from MyBot.run.

That statement does not cover every compiled file in this repository. In particular, the inherited
compiled ImgLoc component has no accompanying source or licence here that establishes GPL status,
open-source status, or public redistribution rights. Treat that component as separately governed
with unresolved or restrictive redistribution terms; do not describe the complete binary bundle as
wholly GPL-licensed or open source. Before publicly redistributing it, obtain written permission
from the rights holder or replace it with a clearly licensed open implementation and revalidate the
result.

Publishing source does not surrender copyright. MIT-licensed source keeps its copyright while
granting broad reuse rights subject to preserving the copyright and permission notice in copies or
substantial portions; MIT does not itself require a backlink on every screen. This repository is not
uniformly MIT licensed. The exact licence and protected-resource boundary, including why encrypted
recognition data is not bypassed, is documented in
[`OPEN_SOURCE_RIGHTS.md`](docs/development/OPEN_SOURCE_RIGHTS.md).

The low-power/background design and dated process measurements are recorded in
[`RUNTIME_RESOURCE_BUDGET.md`](docs/development/RUNTIME_RESOURCE_BUDGET.md). BlueStacks is the dominant
memory cost; the planner now slows status/event polling when idle or hidden without slowing the active
Stop path.

The upstream project is the work of a large group of contributors over many years, and the
recognition code in particular represents an enormous amount of accumulated effort. Credits are in
the About tab and in the upstream repository.
