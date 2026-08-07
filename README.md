# My Bot 2.0

A Clash of Clans automation bot for Windows, built on the MyBot.run v8.2.0 source tree, with a
rebuilt run engine and a planner interface for describing what a session should actually do.

This is a working repository, not a finished release. The parts that have been written and tested
are listed below, and so are the parts that have not. Nothing here claims to work against the live
game until somebody has actually watched it work against the live game.

---

## Contents

- [What this is](#what-this-is)
- [Status at a glance](#status-at-a-glance)
- [Installing](#installing)
- [Using the Run Planner](#using-the-run-planner)
- [Verified vs diagnostic runs](#verified-vs-diagnostic-runs)
- [Where things live](#where-things-live)
- [Working on the code](#working-on-the-code)
- [What still needs doing](#what-still-needs-doing)
- [Where the code came from](#where-the-code-came-from)
- [Account safety](#account-safety)
- [Licence](#licence)

---

## What this is

The starting point is MyBot.run v8.2.0, a long-running open source Clash of Clans bot written in
AutoIt. That codebase does a lot well and has years of accumulated screen-recognition work in it.
What it does not have is a clear description of *what a run should do* — the settings are spread
across a dozen tabs, and the bot's idea of "attack" is whatever the code path happens to reach.

The work here adds that missing layer:

<details>
<summary><b>A run engine that models a session explicitly</b></summary>

<br>

Instead of settings scattered across tabs, a run is described by four objects that validate
independently and can be tested without launching the game:

| Object | What it holds |
| --- | --- |
| `RunPlan` | Strategy, stop conditions, resource targets, upgrade policy |
| `RunIntent` | Binds a plan to one **exact** battle surface, a Hero loadout, and that surface's attack quota |
| `RunSession` | The state machine for a running session: counters, loot, stop reason, verification state |
| `AccountQueue` | Which local bot profiles to rotate through, in order |

The important word is *exact*. Regular and Ranked Battles are separate surfaces with separate
rules. Legend III, Legend II and Legend I have different attack budgets on different schedules.
The old model had one "multiplayer" path, which meant selecting one thing and running another
whenever the coordinates happened to still respond. A `RunIntent` carries the exact surface from
the moment you pick it, and refuses to open a session if the surface and the plan disagree.

</details>

<details>
<summary><b>Attack budgets that distinguish published limits from what you actually have left</b></summary>

<br>

Legend I publishes a budget of 8 attacks per League Day. That is not the same as *you have 8
attacks left right now*, and treating the two as interchangeable is how a bot ends up hammering a
surface that has nothing left.

A `BattleQuota` starts unobserved. Until the remaining count has actually been read off the
client, a finite surface will not start:

```
remaining   = -1
verified    = false
observed_at = -1
```

Once observed, consumption decrements the real count and refuses to over-consume. Regular Battles
are catalogued as unlimited and skip this entirely.

</details>

<details>
<summary><b>Six Heroes, four slots</b></summary>

<br>

The Hero Hall holds six Heroes — Barbarian King, Archer Queen, Minion Prince, Grand Warden, Royal
Champion, and Dragon Duke — but only four can be active at once. So the loadout is a bounded
selection, not a fixed array.

Membership is checked against the generated catalog rather than a hard-coded list, and Town Hall
gating is enforced both ways: adding a Hero you have not unlocked is rejected, and lowering your
Town Hall level releases any Hero that would no longer be available instead of leaving a selection
you cannot field.

</details>

<details>
<summary><b>A Run Planner tab that explains itself</b></summary>

<br>

Every control carries a summary, a full description, its prerequisites, and — when it is greyed
out — the specific reason it is unavailable. Not "unavailable", but *which capture is missing*.

The tab renders from a generated descriptor rather than a hand-written layout, so adding a battle
surface or changing a disabled reason is a catalog edit. The metadata is validated against the
game catalogs in CI, which means the planner cannot quietly fall out of step with the engine.

</details>

---

## Status at a glance

| Area | State |
| --- | --- |
| Run engine (plan, intent, session, quota, loadout, events) | Written, contract-tested |
| Run Planner tab | Written, renders from generated metadata |
| LDPlayer 9 and MuMu Player 12 adapters | Written, **not run against real hardware** |
| Game model through July 2026 | Catalogued from official sources |
| Screen recognition for current client | **Not started** — needs captures |
| Attack execution on any surface | **Not demonstrated** |
| Windows compile (Au3Check) | Runs in CI; see the badge on the Actions tab |

The honest summary: the planning and orchestration layer is real code with real tests. The layer
that actually recognises what is on screen and clicks things has not been re-confirmed against the
current client, and cannot be until somebody supplies captures from a running game.

---

## Installing

You need Windows 10 or 11, an Android emulator, and AutoIt if you want to run from source.

<details>
<summary><b>Step 1 — Install AutoIt</b></summary>

<br>

Download AutoIt from [autoitscript.com](https://www.autoitscript.com/site/autoit/downloads/).
Version 3.3.16.1 or 3.3.18.0 both work; CI tests against both.

Install the full package, not just the runtime — you need `Au3Check.exe` if you plan to make
changes, and the SciTE editor is a genuinely pleasant way to work on AutoIt.

</details>

<details>
<summary><b>Step 2 — Install an emulator</b></summary>

<br>

The bot drives Clash of Clans inside an Android emulator over ADB. Any of these will do:

| Emulator | Notes |
| --- | --- |
| **LDPlayer 9** | New adapter. Multi-instance ADB addressing is implemented (port 5554 + 2×index). Untested on hardware. |
| **MuMu Player 12** | New adapter. Reads each instance's ADB port from the emulator rather than assuming one. Untested on hardware. |
| **BlueStacks 5** | Inherited from upstream. Works against the versions upstream supported. |
| **MEmu** | Inherited from upstream. |
| **Nox** | Inherited from upstream. |

Set the emulator to **860×732** resolution before first use. The bot's screen coordinates assume
it, and a different resolution is the single most common cause of "the bot clicks the wrong
thing".

Start the emulator once and let it finish setting up before pointing the bot at it — several
emulators do not register their instances until they have run at least once.

</details>

<details>
<summary><b>Step 3 — Get the source</b></summary>

<br>

```
git clone https://github.com/slaveofsolace/My-Bot-2.0.git
cd My-Bot-2.0
```

</details>

<details>
<summary><b>Step 4 — Check the clone is intact</b></summary>

<br>

This needs Python 3.11 or newer, and takes a few seconds:

```
python tools/repo_audit.py
python tools/lint_autoit.py --all
```

The audit reports one warning about inherited binary artifacts (`.exe` and `.dll` files carried
over from upstream). That warning is expected and deliberate — their provenance has not been
established, and it stays visible until it is.

Anything else reported as an error means the clone is incomplete or something is genuinely broken.

</details>

<details>
<summary><b>Step 5 — Run it</b></summary>

<br>

Right-click `MyBot.run.au3` and choose **Run Script (x86)**.

Use the 32-bit option. The bot will refuse to start under x64 and tell you so, but it saves a
confusing minute to get it right first time.

On first launch the bot creates a profile and writes its configuration under your Windows user
profile. Nothing is written outside that and the repository directory.

</details>

<details>
<summary><b>If something goes wrong</b></summary>

<br>

| Symptom | Usual cause |
| --- | --- |
| "Don't Run/Compile the Script as (x64)" | Started with the 64-bit interpreter. Use Run Script (x86). |
| Bot starts but sees nothing | Emulator is not at 860×732, or ADB is not connected. |
| Bot attaches to the wrong window | More than one emulator instance running. Pick the instance explicitly on the Run Planner's Emulator tab. |
| Clicks land in the wrong place | Resolution mismatch, or emulator DPI scaling is not at its default. |
| Include errors on startup | Incomplete clone. Re-run `python tools/repo_audit.py` — it lists any include that does not resolve. |

`docs/INSTALL.md` goes into more detail on each of these.

</details>

---

## Using the Run Planner

The **Run Planner** tab is the last tab in the main window. It has seven sections:

| Section | What you set |
| --- | --- |
| **Destination** | The exact battle surface, and which attack strategy runs once a base is found |
| **Heroes** | Up to four active Heroes from the six in the Hero Hall |
| **Emulator** | Which emulator and which instance to drive |
| **Stop conditions** | Time limit, battle limit, Star Bonus, failure limit |
| **Resource targets** | Stop once a Gold, Elixir, or Dark Elixir total has been collected |
| **Between battles** | Upgrade policy and the account rotation queue |
| **Diagnostics** | Whether unverified surfaces are allowed to run |

Set what you want and press **Apply plan**. The planner builds a run intent through the engine and
tells you one of three things: *Ready*, *Ready as a diagnostic run*, or *Blocked* with the specific
reason. It never silently accepts a configuration the engine would reject.

Choices that are not available are marked in the dropdown and explained in the panel underneath.
The panel says what the choice does, what it needs, and what specifically is missing — so
"unverified" is always accompanied by *which capture has not been taken*.

---

## Verified vs diagnostic runs

Most surfaces in this repository are currently **unverified**: the game model says they exist and
the engine knows how to route to them, but nobody has captured what they look like on the current
client, so the bot cannot claim to recognise them.

An unverified surface will not start by default. That is deliberate — the worst failure mode for a
bot like this is confidently doing the wrong thing.

But a route that refuses to start also cannot be debugged, so **Diagnostics → Allow unverified
surfaces to run** lets it proceed anyway. Turning it on requires a note saying who is watching the
run, and that note is stored with the session.

What diagnostic mode does *not* do is change what the bot has been shown to do:

- the session is marked `unverified-diagnostic` from the moment the route is attached
- the mark is a one-way latch — nothing in the codebase moves a session back to verified
- every session snapshot and every JSONL event carries the mark
- the planner shows a banner for as long as an unverified surface is selected

So you can run something to find out how it behaves, and the record still says plainly that it was
an observation rather than a demonstration.

The quota gate is *not* relaxed by diagnostic mode. A surface with no attacks left is a fact about
the game, not a missing capture, and attacking anyway is just a bug.

---

## Where things live

```
COCBot/
  functions/
    Run/          run engine: plan, intent, session, quota, loadout, events, verification
    Game/         generated game catalog and screen-state registry
    Android/      emulator backends, including the LDPlayer 9 and MuMu adapters
  GUI/            AutoIt GUI, including the Run Planner tab and its generated metadata
config/
  game/           source-of-truth catalogs: battle surfaces, Heroes, screen states
  ui/             Run Planner metadata, generated from the catalogs
docs/             audit, architecture, compatibility matrix, install guide, UI handoff
tests/
  autoit/         contract tests that run under AutoIt on Windows
  fixtures/       current-client capture manifest (captures not yet supplied)
tools/            validators, linter, and generators — all Python, no dependencies
imgxml/ images/   screen-recognition templates inherited from upstream
```

Two files are generated and should never be hand-edited:

- `COCBot/functions/Game/GameCatalog.generated.au3` — from `config/game/*.json`
- `COCBot/GUI/RunPlannerMetadata.generated.au3` — from `config/ui/run-planner.settings.json`

CI fails if either drifts from its source.

---

## Working on the code

Everything in `tools/` is plain Python 3.11+ with no dependencies, so it runs anywhere:

| Command | What it checks |
| --- | --- |
| `python tools/lint_autoit.py --all` | AutoIt block balance, ByRef defaults, parameter order, duplicate functions, unresolved includes and calls |
| `python tools/repo_audit.py` | Required files, include resolution, secret patterns, upstream pins |
| `python tools/validate_game_catalog.py` | Game catalogs against their schemas |
| `python tools/validate_ui_metadata.py` | Planner metadata against the game catalogs |
| `python tools/verify_current_game_model.py` | That the generated catalog is actually wired into the runtime |
| `python tools/generate_game_catalog_autoit.py --check` | Generated catalog drift |
| `python tools/generate_run_planner_autoit.py --check` | Generated planner metadata drift |

The AutoIt linter is worth explaining: `Au3Check` only runs on Windows, so the linter catches the
structural mistakes that would otherwise wait for a Windows CI job — unbalanced blocks, `ByRef`
parameters carrying defaults, required parameters after optional ones, duplicate definitions,
includes that do not resolve. It correctly parses all 366 AutoIt files in the tree, including
line continuations and `#cs`/`#ce` comment regions.

The AutoIt contract tests in `tests/autoit/` run on Windows via `tools/Test-AutoIt.ps1`, which CI
executes against both supported AutoIt versions.

To change what the planner offers, edit the catalogs and regenerate:

```
python tools/generate_run_planner_settings.py
python tools/generate_run_planner_autoit.py
python tools/validate_ui_metadata.py
```

---

## What still needs doing

Everything below is blocked on something that cannot be produced without a Windows machine running
the actual game. Listing it honestly is more useful than a progress bar.

<details>
<summary><b>Screen captures (blocks almost everything else)</b></summary>

<br>

`tests/fixtures/current-client/manifest.json` lists 20 required captures, all currently missing.
They cover Town Hall 18, Guardians, the six-Hero Hero Hall, Dragon Duke, each battle surface entry
screen, Hero Journey, Global Chat, battle fast-forward, the Builder Base changes, and the current
army screens.

The manifest specifies the capture contract: 860×732, PNG, sRGB, with player names, clan names,
chat text, and account identifiers redacted before committing.

Until these exist there is no way to build recognition templates, and no way to move any surface
from unverified to verified.

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

The LDPlayer 9 and MuMu adapters need a controlled run on real hardware: instance zero and a
non-zero instance, ADB attachment, background capture, clicks and drags, zoom, restart, shutdown.

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

The 17 inherited binary artifacts (`.exe` and `.dll` files from upstream) need provenance
established and hashes recorded before any release is published. Reproducible compilation and a
signed release manifest are not set up.

</details>

---

## Where the code came from

`upstreams.lock.json` pins every source to an exact commit with its licence and import policy.

| Source | Role |
| --- | --- |
| [MyBotRun/MyBot](https://github.com/MyBotRun/MyBot) v8.2.0 | The base. Complete runnable AutoIt source tree. |
| [xbebenk/MBR_xbebenkMod](https://github.com/xbebenk/MBR_xbebenkMod) | Recent community compatibility work, adapted per-change. |
| [muratcandegirmenci78-lab/canmurat](https://github.com/muratcandegirmenci78-lab/canmurat) | Pinned for lineage comparison; no unique changes adopted. |
| [clashautoloot/Clash-AutoLoot](https://github.com/clashautoloot/Clash-AutoLoot) | Behaviour reference only. |

Two of those need explaining:

**xbebenk** is the most useful recent community source, but its core derives from MyBot v7.9.9
while this project is on v8.2.0. Overlaying it wholesale would regress the newer architecture, so
changes are adapted individually. The LDPlayer 9 multi-instance ADB correction was ported this
way — the fix was real, but v8.2.0 has no equivalent of the file it patched, so it became a proper
adapter instead of a copied file. Its chest and Builder Base patches target code paths that do not
exist in v8.2.0 and were deliberately not copied; equivalent fixes will be written when a capture
reproduces the underlying problem.

**Clash-AutoLoot** publishes documentation and compiled releases, not source under a licence that
permits reuse. No binary was unpacked or decompiled. Its externally visible product behaviour —
run dashboards, stop conditions, multi-account queues, Star Bonus mode — informed the requirements
for the run engine, which was then written from scratch. Any claim of that project's centred on
being undetectable or surviving enforcement was explicitly excluded.

---

## Account safety

Supercell's terms prohibit unapproved third-party software, and using a bot can get an account
permanently banned. That is a real consequence and this repository does not pretend otherwise.

This project deliberately does not implement detection evasion, ban avoidance, behaviour
disguising, or anything else whose purpose is to make automated play harder to identify. Feature
requests along those lines will be declined. `SECURITY.md` covers reporting; `CONTRIBUTING.md`
covers what is in and out of scope.

Use accounts you are willing to lose.

---

## Licence

GNU General Public License v3, inherited from MyBot.run. See `License.txt`.

The upstream project is the work of a large group of contributors over many years, and the
recognition code in particular represents an enormous amount of accumulated effort. Credits are in
the About tab and in the upstream repository.
