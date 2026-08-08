# My Bot 2.0 — handoff

Updated 2026-08-07, after the two divergent trees were reconciled.

**Current line: `claude/coc-bot-merge-ui-kobgds` @ `11c27c36`.** Pushed, CI green on all three checks.
PR #7 tracks it.

---

## 1. The trees are merged

The earlier split is resolved. `sol/coc-bot-merge-ui` took the cloud branch as its base and layered the
Windows work on top — option 1 from the previous handoff. That line was then continued here.

```
11c27c36  Parse the health payload, and write the events the Activity panel reads   <- this session
82fd38b7  Add native web control center            \
565eab61  Fix planner state and startup            |  Windows work (Codex)
9ff2af11  Preserve Windows planner and Guardians work /
aa9ccb3f  Add a combined handoff
7c7f5062  Reject unknown settings on save instead of dropping them   \
29cbc366  Add Run Planner interface screenshots                      |
0a0cf296  Rebuild the planner UI and give the Hero picker four slots |  cloud work (Claude)
0aa9ae6b  Make the pacing settings actually take effect              |
26561f3d  Bridge the web planner to the AutoIt tab, add pacing       /
f1a0e2c3  (shared base)
```

`sol/windows-planner-guardians` @ `141bd963` is the Windows work alone on master — a preservation
branch, safe to delete once the merged line is accepted. `master` is still at `f1a0e2c3`. The six
stale integration branches are gone.

**The merge was done well.** All 16 repository validators pass on the combined line, and both Windows
CI jobs (AutoIt 3.3.16.1 and 3.3.18.0) run Au3Check on every entry point *and execute* the three
contract test scripts.

---

## 2. What this session changed

Both were open gaps from the previous handoff, both real in the merged tree.

**Gap 3 — health handshake.** `_RunPlannerServiceHealthy()` pattern-matched the `/api/health` payload,
including `'"service": "my-bot-control-center"'` with the exact spacing `json.dumps` happens to emit.
Compact separators or an indent on the server would have reported a perfectly healthy service as
unavailable, with nothing anywhere to say why. It now decodes the payload with `Json.au3` and compares
fields. The service name and bridge version are named constants.

**Gap 2 — the Activity panel had no source.** `RunEventAppendJsonLine` had exactly one caller and it
was a test, so the panel read `logs/run-events.jsonl` — a file nothing in production ever wrote.
`COCBot/functions/Run/RunEventLog.au3` adds the writers, called at seven sites: plan applied, plan
blocked, plan file loaded, rest started, rest ended. Writing is best-effort throughout; a run must
never fail because its diagnostics could not be written.

**Two new drift guards in `check_plan_bridge.py`**, both confirmed by breaking the code and watching
the check fail:

- The health handshake is compared **in both directions**. A bridge version bumped on one side only
  leaves the GUI reporting "unavailable" forever in front of a healthy service.
- The event log path is compared. Drift there puts the Activity panel straight back to empty.

### A trap worth knowing about

While negative-testing the health guard, a mutation went undetected because of a **stale
`__pycache__`**: `"...-v1"` and `"...-v2"` are the same byte length, and the rewrite landed in the same
second, so Python's `(mtime, size)` invalidation kept the old `.pyc`. `check_plan_bridge.py` imports
`planner_ui`, so any harness that mutates a tool between runs must clear `tools/__pycache__` or it will
silently test stale bytecode. CI is unaffected — a fresh checkout has no cache.

---

## 3. Open gaps

| # | Gap | Status |
|---|---|---|
| 1 | `g_oRunPlannerIntent` is assigned but nothing outside the planner tab consumes it — no Start path | **open — the big one** |
| 2 | Production event writers | **fixed** (`11c27c36`) |
| 3 | Health check parses JSON, requires `ok`, service and bridge | **fixed** (`11c27c36`) |
| 4 | `plan_status()` mislabelling corrupt files | fixed on the Windows side — reports `unreadable` |
| 5 | Unknown fields: docs vs behaviour | **fixed** (`7c7f5062`) — POST returns 400, writes nothing |
| 6 | Stale README claims | no stale section/setting counts found; re-read before release |
| 7 | Real browser acceptance | partial — headless screenshots only |
| 8 | Full round trip browser → file → native Load | file half proven, native half needs Windows |
| 9 | Nonclaims kept explicit | held |

### Gap 1 is what unblocks the product

Everything else in the planner is scaffolding until this exists. The planner builds a `RunIntent`;
the legacy engine never reads it. Pacing is the sole exception, because it is hooked directly into
`Click()`. So Army, Search, Donate, Events, Limits and Loot are stored, validated, round-tripped and
displayed — and drive nothing.

The work is an explicit Apply/Start boundary: a place where a prepared intent becomes the thing the
main loop obeys, with the verification gate and quota gate enforced at the crossing, and no path that
starts an attack implicitly.

---

## 4. Windows-only, still outstanding

Nothing below can be done from a Linux container. Run Claude Code **on the Windows machine** for these.

**The launch fault.** Evidence points at a machine-level Defender fault, not a bot defect: Defender
Event 5008 (engine `Hang`, code 16422), then 3002 (filter driver unloaded); WER classifies every
failure as `AppHangXProcB1` naming `MsMpEng.exe`; and decisively, `powershell.exe -NoProfile
-NonInteractive -Command "exit 0"` also hangs. The untouched tracked binary hangs too, so compilation
did not cause it. `lib/MyBot.run.dll` matches HEAD and upstream `8ad6e5a5`, SHA-256
`347b204a15fd56800130740aff639c7608621206482f07298c595a363e328699`. The hang lands on the first
managed export / JIT.

Recovery: terminate only the stale `MyBot.run.exe` (was PID 22436), **ask before rebooting**, then
`Get-MpComputerStatus`, `Get-Service WinDefend,WdNisSvc`, check for fresh 5008/3002, `Update-MpSignature`.
Launch the untouched tracked binary once before compiling anything. If 5008 recurs:
`MpCmdRun.exe -ResetPlatform`, reboot, update, retest. Do not force-kill `MsMpEng`, disable Defender,
or add a broad exclusion.

**⚠ The tracked binaries were recompiled and committed** in `82fd38b7` (`MyBot.run.exe`,
`MyBot.run.Wmi.exe`), which the earlier plan said to hold until the launch fault was repaired. Confirm
whether that binary was ever launched and observed responsive. If not, treat it as untested and retest
the untouched HEAD binary first.

**Source hardening, still not done.** Never call mixed-mode DLL exports synchronously on the GUI
startup thread. Enter the event loop first; probe the engine in a separate x86 helper with a bounded
timeout; on stall kill only the helper, keep the GUI alive, show `Engine unavailable` and disable
Start. Moving the same unbounded call to Start is not sufficient. This is right regardless of Defender
— it is the difference between a hung antivirus freezing the app and a hung antivirus showing a
message.

---

## 5. What must not be claimed

- **20 required current-client fixtures are missing.** Recognition is unverified.
- **Runtime evidence is empty. 0 of 24 support capabilities are ready.**
- **LDPlayer, MuMu and current-client combat have never been hardware-validated.**
- **No battle surface is verified.** Nothing in this line moves one.
- **Pacing is the only planner setting that reaches the bot** (see gap 1).
- **Pacing defaults are reasoned, not measured.** 400 ms settle is a starting point, not a finding.
- The native app has **never been launched from this environment**, and no claim about its
  responsiveness originates here.

**Inherited, easy to mistake for new work:** upstream v8.2.0 already ships `$g_bUseRandomClick`, a BOT
Options checkbox that scatters click coordinates by ±5px and speed by ±15%. It predates both work
streams and is untouched. The pacing work is a separate mechanism and does not extend it.

---

## 6. Suggested next order

1. Fix the launch fault, untouched binary first, before any compile (§4).
2. Land the source hardening so an engine stall can never freeze the GUI again.
3. **Gap 1** — the Apply/Start boundary. This is what makes the other 41 settings mean something.
4. Gap 7/8 — real browser acceptance and the full native round trip, on Windows.
5. The recognition fixtures. This is the actual blocker on the whole project, and no amount of
   planner work substitutes for it.

Validation once Windows is healthy: Python compileall, repo audit, AutoIt lint, catalog and UI
validators, generator `--check`s, model and client verifiers, planner preview and selftest, fixture,
evidence and readiness validators, Au3Check on every entry point, then execute RunContracts,
GameCatalog and RunEngine under x86 AutoIt.

Do not report completion from tests or a background process alone. The native app has to be seen
running and responsive.
