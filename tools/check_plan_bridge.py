#!/usr/bin/env python3
"""Check that what the web planner writes is what the AutoIt side can read.

Two programs meet at config/run-plan.local.json: tools/planner_ui.py writes it, and
COCBot/functions/Run/RunPlanFile.au3 reads it. Nothing else forces them to agree, and the AutoIt half
cannot be executed off Windows, so this checks the agreement statically:

  * the plan the server writes only uses shapes the AutoIt parser accepts
  * every key in it names a setting the AutoIt tab has a control for
  * every setting type in the metadata has a branch in the code that applies it
  * the pacing bounds the engine enforces are the ones the controls offer

Standard library only. Runs anywhere, including CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

METADATA = ROOT / "config/ui/run-planner.settings.json"
PARSER = ROOT / "COCBot/functions/Run/RunPlanFile.au3"
APPLIER = ROOT / "COCBot/GUI/MBR GUI Control Run Planner.au3"
PACING = ROOT / "COCBot/functions/Run/RunPacing.au3"
EXECUTION = ROOT / "COCBot/functions/Run/RunExecution.au3"
ACTION = ROOT / "COCBot/MBR GUI Action.au3"
BOTTOM = ROOT / "COCBot/GUI/MBR GUI Control Bottom.au3"
CONTROL = ROOT / "COCBot/functions/Run/RunControlBridge.au3"
API_CLIENT = ROOT / "COCBot/functions/Other/ApiClient.au3"
MAIN = ROOT / "MyBot.run.au3"
LAUNCHER = ROOT / "My Bot 2.0.au3"

# The value shapes RunPlanFileParse produces. Anything else in a written plan would reach the AutoIt side
# as a parse failure, which costs the whole file rather than one setting.
SCALARS = (str, int, float, bool)

# Bounds in RunPacing.au3, paired with the planner setting each one guards.
PACING_BOUNDS = {
    "RUN_PACING_MAX_ACTION_DELAY_MS": "pacing.action_delay_ms",
    "RUN_PACING_MAX_SETTLE_MS": "pacing.settle_ms",
    "RUN_PACING_MAX_RETRY_ATTEMPTS": "pacing.retry_attempts",
    "RUN_PACING_MAX_BREAK_EVERY_MINUTES": "pacing.break_every_minutes",
    "RUN_PACING_MAX_BREAK_MINUTES": "pacing.break_minutes",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def autoit_constants(source: str) -> dict[str, int]:
    """Global Const $NAME = 123, as a lookup."""
    found = {}
    for name, value in re.findall(r"^\s*Global\s+Const\s+\$(\w+)\s*=\s*(-?\d+)\s*$", source, re.MULTILINE):
        found[name] = int(value)
    return found


def applied_types(source: str) -> set[str]:
    """The setting types _RunPlannerApplySetting has an explicit branch for."""
    body = source.split("Func _RunPlannerApplySetting", 1)
    if len(body) < 2:
        return set()
    body = body[1].split("EndFunc", 1)[0]
    types: set[str] = set()
    for line in body.splitlines():
        match = re.match(r'^\s*Case\s+(.+)$', line)
        if not match or match.group(1).strip().lower() == "else":
            continue
        types.update(item.strip().strip('"').lower() for item in match.group(1).split(","))
    return types


def autoit_required_keys(source: str) -> list[str] | None:
    """Return the exact keys enforced by _RunPlanFileRequiredKeys()."""
    match = re.search(
        r"Func\s+_RunPlanFileRequiredKeys\s*\(\s*\).*?EndFunc",
        source,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None
    body = re.sub(r"_\s*\r?\n\s*", " ", match.group(0))
    array = re.search(r"\[(.*?)\]", body, re.DOTALL)
    return re.findall(r'"([^"]*)"', array.group(1)) if array else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    metadata = load(METADATA)
    settings = {s["id"]: s for section in metadata["sections"] for s in section["settings"]}

    parser_source = PARSER.read_text(encoding="utf-8-sig")
    required_keys = autoit_required_keys(parser_source)
    if required_keys is None:
        errors.append("_RunPlanFileRequiredKeys could not be read from RunPlanFile.au3")
    else:
        required_set = set(required_keys)
        for key in sorted(set(settings) - required_set):
            errors.append(f"_RunPlanFileRequiredKeys is missing {key!r}")
        for key in sorted(required_set - set(settings)):
            errors.append(f"_RunPlanFileRequiredKeys requires unknown setting {key!r}")
        duplicates = sorted({key for key in required_keys if required_keys.count(key) > 1})
        if duplicates:
            errors.append(f"_RunPlanFileRequiredKeys lists duplicate keys: {', '.join(duplicates)}")
        if len(required_keys) != len(settings):
            errors.append(
                f"_RunPlanFileRequiredKeys has {len(required_keys)} entries; metadata declares {len(settings)}"
            )

    # ---------------------------------------------------------------------------------------------
    # The plan the server writes, checked against what the AutoIt parser accepts.
    # ---------------------------------------------------------------------------------------------
    import planner_ui  # noqa: E402  - the writer itself, so this checks the real thing

    plan = planner_ui.default_plan()
    for key, value in sorted(plan.items()):
        if key not in settings:
            errors.append(f"plan key {key} is not a planner setting, so no control could receive it")
        if isinstance(value, dict):
            errors.append(f"{key}: the AutoIt parser refuses nested objects")
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, SCALARS):
                    errors.append(f"{key}: list items must be scalars, found {type(item).__name__}")
        elif not isinstance(value, SCALARS) and value is not None:
            errors.append(f"{key}: {type(value).__name__} is not a shape the AutoIt parser reads")

    # A submitted plan goes through the same validator, so check the post-validation shape too: that is
    # what actually reaches disk.
    written, _, _ = planner_ui.validate_plan({"run.max_battles": "9", "run.diagnostic_mode": "false"})
    if set(written) != set(settings):
        errors.append("a validated plan does not cover exactly the declared settings")
    if written.get("run.diagnostic_mode") is not False:
        errors.append("the writer would put a true diagnostic flag on disk for the string 'false'")

    serialized = json.dumps(written)
    reparsed = json.loads(serialized)
    if reparsed != written:
        errors.append("a written plan does not survive its own JSON round trip")

    # ---------------------------------------------------------------------------------------------
    # Every setting type the metadata uses needs somewhere to land in the tab.
    # ---------------------------------------------------------------------------------------------
    applier_source = APPLIER.read_text(encoding="utf-8-sig")
    branches = applied_types(applier_source)
    if not branches:
        errors.append("could not find _RunPlannerApplySetting; the bridge check is not seeing the real code")
    # instance-select and profile-queue are plain text boxes and share the fallback branch, which is
    # deliberate: they carry free text either way.
    fallback = {"instance-select", "profile-queue"}
    for setting_id, setting in sorted(settings.items()):
        kind = setting["type"]
        if kind not in branches and kind not in fallback:
            errors.append(f"{setting_id}: type {kind!r} has no branch in _RunPlannerApplySetting")

    if "Case Else" not in applier_source.split("Func _RunPlannerApplySetting", 1)[-1].split("EndFunc", 1)[0]:
        errors.append("_RunPlannerApplySetting has no fallback branch for free-text settings")

    # ---------------------------------------------------------------------------------------------
    # The engine must accept exactly what the controls can produce.
    # ---------------------------------------------------------------------------------------------
    constants = autoit_constants(PACING.read_text(encoding="utf-8-sig"))
    for constant, setting_id in sorted(PACING_BOUNDS.items()):
        setting = settings.get(setting_id)
        if setting is None:
            errors.append(f"{setting_id} is missing from the planner metadata")
            continue
        declared = constants.get(constant)
        if declared is None:
            errors.append(f"{constant} is not declared in RunPacing.au3")
            continue
        offered = setting["validation"]["maximum"]
        if declared != offered:
            errors.append(
                f"{setting_id}: the control offers up to {offered} but the engine accepts up to {declared}"
            )

    # ---------------------------------------------------------------------------------------------
    # Two invariants of the pacing gate. Both are easy to undo by accident and neither shows up until
    # a real run on Windows, which is the worst place to find them.
    # ---------------------------------------------------------------------------------------------
    gate_path = ROOT / "COCBot/functions/Run/RunPacingGate.au3"
    if not gate_path.is_file():
        errors.append("RunPacingGate.au3 is missing; the pacing settings would be inert")
    else:
        gate = gate_path.read_text(encoding="utf-8-sig")

        # _Sleep's third argument is $CheckRunState, and it defaults to True. Left at the default it
        # returns True whenever $g_bRunState is False - the ordinary state of an idle bot - so the gate
        # would report "stopped" for every click made outside a run and the caller would swallow it.
        for line_number, line in enumerate(gate.splitlines(), 1):
            for call in re.finditer(r"_Sleep\(([^)]*)\)", line):
                arguments = [a.strip() for a in call.group(1).split(",")]
                if len(arguments) < 3 or arguments[2].lower() != "false":
                    errors.append(
                        f"RunPacingGate.au3:{line_number}: _Sleep must pass $CheckRunState=False "
                        f"explicitly, or an idle bot's actions get swallowed: {call.group(0)}"
                    )

        # Both remaining invariants live inside RunPacingGateAction, so they are checked against that
        # function's own body. The short-circuit line appears in several functions here, and looking for
        # it anywhere in the file would let it be deleted from the one that matters.
        action = gate.split("Func RunPacingGateAction()", 1)
        body = action[1].split("EndFunc", 1)[0] if len(action) > 1 else ""
        if not body:
            errors.append("RunPacingGateAction is missing; the pacing settings would be inert")
        else:
            # Click() calls the gate, and _Sleep pumps the message loop. Without the guard a GUI handler
            # that clicks re-enters the gate and waits against a timestamp not yet written.
            if "Static $bInside" not in body:
                errors.append("RunPacingGateAction has lost its reentrancy guard")
            # The whole no-risk-when-unused argument rests on this early return.
            if "If Not IsObj($g_oRunPacingActive) Then Return False" not in body:
                errors.append("the pacing gate no longer short-circuits when no run has installed pacing")

    # Gating the training clicks would double-space loops that already space themselves.
    click_path = ROOT / "COCBot/functions/Other/Click.au3"
    click = click_path.read_text(encoding="utf-8-sig")
    for function in ("PureClick", "PureClickTrain"):
        body = click.split(f"Func {function}(", 1)
        if len(body) > 1 and "RunPacingGateAction" in body[1].split("EndFunc", 1)[0]:
            errors.append(f"{function} is gated; training loops already space themselves")
    if "RunPacingGateAction" not in click.split("Func Click(", 1)[-1].split("EndFunc", 1)[0]:
        errors.append("Click() no longer calls the pacing gate, so the pacing settings do nothing")
    if "RunPacingSettle()" not in click.split("Func Click(", 1)[-1].split("EndFunc", 1)[0]:
        errors.append("Click() no longer takes the planned screen-settle wait")

    # A prepared intent is only useful if Start crosses an explicit, ordered execution boundary.
    execution_source = ""
    if not EXECUTION.is_file():
        errors.append("RunExecution.au3 is missing; prepared plans never reach the legacy engine")
    else:
        execution_source = EXECUTION.read_text(encoding="utf-8-sig")
        for function in ("RunExecutionPrepareStart", "RunExecutionBegin", "RunExecutionCheckStop", "RunExecutionComplete"):
            if f"Func {function}(" not in execution_source:
                errors.append(f"{function} is missing from RunExecution.au3")
        if "RunPacingRestIfDue()" not in execution_source:
            errors.append("planned rests are not consumed by the execution loop")

    action_source = ACTION.read_text(encoding="utf-8-sig")
    bot_start = action_source.split("Func BotStart(", 1)
    bot_start_body = bot_start[1].split("EndFunc", 1)[0] if len(bot_start) > 1 else ""
    ordered_calls = ["RunExecutionPrepareStart", "MBRFuncProbeEngine", "MBRFuncInitialize", "ForumAuthentication", "applyConfig(False)", "RunExecutionApplyPrepared"]
    call_offsets = [bot_start_body.find(call) for call in ordered_calls]
    if any(offset < 0 for offset in call_offsets):
        errors.append("BotStart no longer prepares, probes, initializes, applies compatibility authorization, loads the profile, and applies the plan in the required order")
    elif call_offsets != sorted(call_offsets):
        errors.append("BotStart execution boundary is out of order; the isolated probe and main engine initialization must precede authorization, and profile loading must precede planner application")

    bottom_source = BOTTOM.read_text(encoding="utf-8-sig")
    initiate = bottom_source.split("Func Initiate(", 1)
    initiate_body = initiate[1].split("EndFunc", 1)[0] if len(initiate) > 1 else ""
    ready_calls = ["checkMainScreen()", "AndroidBotStartEvent()", "RunExecutionBegin", "RunControlReportStartOutcome(True"]
    ready_offsets = [initiate_body.find(call) for call in ready_calls]
    if any(offset < 0 for offset in ready_offsets):
        errors.append("Initiate no longer proves the CoC main screen, activates the session, and reports terminal Start readiness")
    elif ready_offsets != sorted(ready_offsets):
        errors.append("Initiate reports the run started before the CoC main screen and planned session are ready")
    main_ready_offset = initiate_body.find("$g_bMainWindowOk = True")
    if main_ready_offset < ready_offsets[0] or main_ready_offset > ready_offsets[-1]:
        errors.append("Initiate no longer publishes game readiness between the successful main-screen proof and terminal Start outcome")
    bot_stop = action_source.split("Func BotStop(", 1)
    bot_stop_body = bot_stop[1].split("EndFunc", 1)[0] if len(bot_stop) > 1 else ""
    if "RunExecutionComplete" not in bot_stop_body:
        errors.append("BotStop no longer completes the planned run session")

    main_source = MAIN.read_text(encoding="utf-8-sig")
    if '#include "COCBot\\functions\\Run\\RunExecution.au3"' not in main_source:
        errors.append("MyBot.run.au3 does not include the run execution boundary")
    if main_source.count("RunExecutionCheckStop()") < 4:
        errors.append("the run loop has lost planner stop checks around one or more attack paths")
    if "RunPlannerSyncPlanFile(True)" in main_source:
        errors.append("startup eagerly hydrates the hidden native Run Planner controls")
    if "RunPlanFileLoadIntent($sPlanPath, $sError)" not in execution_source:
        errors.append("browser Start no longer reloads the saved plan at its execution boundary")

    control_source = CONTROL.read_text(encoding="utf-8-sig")
    consume = control_source.split("Func _RunControlConsumeCommand()", 1)
    consume_body = consume[1].split("EndFunc", 1)[0] if len(consume) > 1 else ""
    claim_offset = consume_body.find("FileMove($sPath, $sClaimPath)")
    load_offset = consume_body.find("RunPlanFileLoad($sPath, $sError)")
    claim_delete_offset = consume_body.find("FileDelete($sPath)", load_offset)
    claim_delete_guard_offset = consume_body.find("If FileExists($sPath) Then", claim_delete_offset)
    dispatch_offset = consume_body.find("Switch $sAction")
    if claim_offset < 0 or dispatch_offset < 0 or claim_offset > dispatch_offset:
        errors.append("native control commands are no longer atomically claimed before dispatch")
    if (
        load_offset < 0
        or claim_delete_offset < load_offset
        or claim_delete_guard_offset < claim_delete_offset
        or dispatch_offset < claim_delete_guard_offset
    ):
        errors.append("native control no longer deletes and verifies its claimed command before dispatch")
    if "Local $iLoadError = @error" not in consume_body or "If $iLoadError Or Not IsObj($oCommand) Then" not in consume_body:
        errors.append("native control does not preserve command parse failure across claim cleanup")
    initialize = control_source.split("Func RunControlInitialize()", 1)
    initialize_body = initialize[1].split("EndFunc", 1)[0] if len(initialize) > 1 else ""
    owner_offset = initialize_body.find("CreateMutex(_RunControlOwnerMutexName())")
    ready_offset = initialize_body.find("$g_bRunControlReady = True")
    if owner_offset < 0 or ready_offset < 0 or owner_offset > ready_offset:
        errors.append("native control no longer acquires single-owner checkout scope before publishing status")
    shutdown = control_source.split("Func RunControlShutdown()", 1)
    shutdown_body = shutdown[1].split("EndFunc", 1)[0] if len(shutdown) > 1 else ""
    for required in ('AdlibUnRegister("RunControlPoll")', "FileDelete(RunControlStatusPath())", "ReleaseMutex($g_hRunControlOwnerMutex)"):
        if required not in shutdown_body:
            errors.append(f"RunControlShutdown no longer performs required ownership cleanup: {required}")

    mbr_source = (ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3").read_text(encoding="utf-8-sig")
    marker = mbr_source.split("Func MBRFuncValidateEngineMarker(", 1)
    marker_body = marker[1].split("EndFunc", 1)[0] if len(marker) > 1 else ""
    if 'Global Const $g_sMBRFuncEngineMarkerName = "MyBot.run.txt"' not in mbr_source:
        errors.append("managed engine release marker name is no longer pinned to MyBot.run.txt")
    for required in (
        '@ScriptDir & "\\" & $g_sMBRFuncEngineMarkerName',
        "If Not FileExists($sMarkerPath) Then",
        "FileGetSize($sMarkerPath)",
        "$iMarkerSize <> 0",
        "MBRFuncMarkUnavailable($sError)",
    ):
        if required not in marker_body:
            errors.append(f"managed engine marker validation no longer fails closed via {required}")

    mbr_open = mbr_source.split("Func MBRFunc(", 1)
    mbr_open_body = mbr_open[1].split("EndFunc", 1)[0] if len(mbr_open) > 1 else ""
    open_marker_offset = mbr_open_body.find("MBRFuncValidateEngineMarker(")
    dll_open_offset = mbr_open_body.find("DllOpen($g_sLibMyBotPath)")
    if open_marker_offset < 0 or dll_open_offset < 0 or open_marker_offset > dll_open_offset:
        errors.append("MBRFunc can open the managed engine before validating its release marker")

    mbr_initialize = mbr_source.split("Func MBRFuncInitialize()", 1)
    mbr_initialize_body = mbr_initialize[1].split("EndFunc", 1)[0] if len(mbr_initialize) > 1 else ""
    initialize_marker_offset = mbr_initialize_body.find("MBRFuncValidateEngineMarker(")
    first_export_offset = mbr_initialize_body.find("setProcessingPoolSize(")
    if (
        initialize_marker_offset < 0
        or first_export_offset < 0
        or initialize_marker_offset > first_export_offset
    ):
        errors.append("managed image exports can start before validating the release marker")

    probe = mbr_source.split("Func MBRFuncProbeEngine(", 1)
    probe_body = probe[1].split("EndFunc", 1)[0] if len(probe) > 1 else ""
    probe_marker_offset = probe_body.find("MBRFuncValidateEngineMarker(")
    probe_launch_offset = probe_body.find("Run('")
    if probe_marker_offset < 0 or probe_launch_offset < 0 or probe_marker_offset > probe_launch_offset:
        errors.append("managed engine probe helper can launch before validating the release marker")
    if "Random(100000, 999999, 1)" not in probe_body or "If FileExists($sToken) Then" not in probe_body:
        errors.append("managed engine probe tokens are no longer unique and fail-closed before launch")
    probe_read_offset = probe_body.find("FileRead($sToken)")
    probe_delete_offset = probe_body.find("FileDelete($sToken)", probe_read_offset)
    probe_delete_guard_offset = probe_body.find("If FileExists($sToken) Then", probe_delete_offset)
    probe_passed_offset = probe_body.find('$g_sMBRFuncEngineProbeState = "passed"', probe_delete_guard_offset)
    if (
        probe_read_offset < 0
        or probe_delete_offset < probe_read_offset
        or probe_delete_guard_offset < probe_delete_offset
        or probe_passed_offset < probe_delete_guard_offset
    ):
        errors.append("managed engine probe can pass without proving its success token was consumed")
    native_tab = applier_source.split("Func tabRunPlanner()", 1)
    native_tab_body = native_tab[1].split("EndFunc", 1)[0] if len(native_tab) > 1 else ""
    if "RunPlannerSyncPlanFile()" not in native_tab_body:
        errors.append("the native Run Planner tab no longer hydrates its saved plan when opened")
    final_initialization = main_source.split("Func FinalInitialization(", 1)
    final_initialization_body = final_initialization[1].split("EndFunc", 1)[0] if len(final_initialization) > 1 else ""
    if "ForumAuthentication()" in final_initialization_body:
        errors.append("FinalInitialization still blocks the UI and Control Center on forum authorization")
    startup_calls = ["RunControlInitialize()", "_RunPlannerStartService("]
    startup_offsets = [final_initialization_body.find(call) for call in startup_calls]
    if any(offset < 0 for offset in startup_offsets) or startup_offsets != sorted(startup_offsets):
        errors.append("FinalInitialization no longer brings the native control bridge online before launching the Control Center")
    if "If RunControlInitialize() Then" not in final_initialization_body:
        errors.append("FinalInitialization no longer gates the Control Center service on native bridge ownership")
    control_success = final_initialization_body.split("If RunControlInitialize() Then", 1)
    control_success_body = control_success[1].split("Else", 1)[0] if len(control_success) > 1 else ""
    if "_RunPlannerStartService(" not in control_success_body or "ShellExecute($RUN_PLANNER_URL)" not in control_success_body:
        errors.append("Control Center service/browser launch can escape the successful native bridge branch")

    main_control = (ROOT / "COCBot" / "MBR GUI Control.au3").read_text(encoding="utf-8-sig")
    close = main_control.split("Func BotClose(", 1)
    close_body = close[1].split("EndFunc", 1)[0] if len(close) > 1 else ""
    close_finalize_offset = close_body.find('RunExecutionComplete("closed")')
    close_save_offset = close_body.find("SaveConfig()")
    if close_finalize_offset < 0 or close_save_offset < 0 or close_finalize_offset > close_save_offset:
        errors.append("BotClose no longer finalizes one-run execution before close-time profile serialization")
    if close_body.count('RunExecutionComplete("closed")') != 1:
        errors.append("BotClose must finalize one-run execution exactly once")
    complete = execution_source.split("Func RunExecutionComplete(", 1)
    complete_body = complete[1].split("EndFunc", 1)[0] if len(complete) > 1 else ""
    if "If Not $g_bRunExecutionPrepared Then Return" not in complete_body:
        errors.append("RunExecutionComplete is no longer idempotent for repeated close/stop cleanup")
    shutdown_offset = close_body.find("RunControlShutdown()")
    service_stop_offset = close_body.find("RunPlannerStopOwnedService()")
    if shutdown_offset < 0 or service_stop_offset < 0 or shutdown_offset > service_stop_offset:
        errors.append("BotClose no longer releases native Control Center ownership before stopping its service")

    api_client = API_CLIENT.read_text(encoding="utf-8-sig")
    if "Global $g_iManagedMyBotControllerPID = 0" not in api_client or "Global $g_hManagedMyBotController = 0" not in api_client:
        errors.append("Mini GUI controller ownership is no longer pinned to a verified PID and window")
    ownership_gate = api_client.find("$wParamLo >= 0x1000 And $wParamLo <= 0x1050 And Not _ApiClientControllerOwns($hWind)")
    dispatch = api_client.find("Switch $wParamLo")
    if ownership_gate < 0 or dispatch < 0 or ownership_gate > dispatch:
        errors.append("state-changing Mini GUI commands are no longer owner-gated before dispatch")
    claim = api_client.split("Func _ApiClientClaimController(", 1)
    claim_body = claim[1].split("EndFunc", 1)[0] if len(claim) > 1 else ""
    for required in (
        "_ApiClientControllerPID($hWindow)",
        "Not _ApiClientControllerIsLive()",
        "$iPID <> $g_iManagedMyBotControllerPID",
        "$g_iManagedMyBotControllerPID = $iPID",
        "$g_hManagedMyBotController = $hWindow",
    ):
        if required not in claim_body:
            errors.append(f"Mini GUI controller claim no longer enforces live first-owner semantics via {required}")

    stop_case = api_client.split("Case 0x1010", 1)
    stop_body = stop_case[1].split("Case 0x1020", 1)[0] if len(stop_case) > 1 else ""
    for required in ("$g_iBotAction = $eBotStart", 'Eval("g_bRunControlStartInProgress")', 'Assign("g_bRunControlStopRequested", True, $ASSIGN_FORCEGLOBAL)', "btnStop()"):
        if required not in stop_body:
            errors.append(f"Mini GUI Stop no longer latches queued/in-progress startup through {required}")

    gui_pid_case = api_client.split("Case 0x1060", 1)
    gui_pid_body = gui_pid_case[1].split("Case Else", 1)[0] if len(gui_pid_case) > 1 else ""
    gui_claim_offset = gui_pid_body.find("_ApiClientClaimController($hWind, $pid)")
    gui_assign_offset = gui_pid_body.find("$g_iGuiPID = $pid")
    gui_guard_offset = gui_pid_body.find("If $g_bLibMyBotInitialized Then SetBotGuiPID($pid)")
    if min(gui_claim_offset, gui_assign_offset, gui_guard_offset) < 0 or not (gui_claim_offset < gui_assign_offset < gui_guard_offset):
        errors.append("0x1060 no longer claims the Mini controller before storing its PID and conditionally updating an initialized engine")
    if gui_pid_body.count("SetBotGuiPID($pid)") != 1 or "If $g_bLibMyBotInitialized Then SetBotGuiPID($pid)" not in gui_pid_body:
        errors.append("0x1060 can call the first managed DLL export before MBRFuncInitialize")

    # The launcher keeps the exact native Mini controller beside the exact BlueStacks shell. The
    # relationship must survive BlueStacks' delayed resize without embedding, renaming, or sending
    # commands to either inherited window.
    if not LAUNCHER.is_file():
        errors.append("My Bot 2.0.au3 is missing; persistent safe docking cannot be verified")
    else:
        launcher_source = LAUNCHER.read_text(encoding="utf-8-sig")
        launcher_entry = launcher_source.split("Func _DockKeeperMutexName()", 1)[0]
        for required in (
            'Global Const $g_sControllerSha256 = "ae26c098ceb3c74e3d7f567834d9135257e094172e32140f4a5b615eaf90ceda"',
            'Global Const $g_iControllerBytes = 1634304',
            'Global Const $g_sControllerTitlePattern = "^My Bot Mini v8\\.2\\.0(?: \\(.+\\))?$"',
            'Global Const $g_sBlueStacksTitle = "BlueStacks5-Pie64"',
            'Global Const $g_iDockGap = 8',
        ):
            if required not in launcher_source:
                errors.append(f"launcher provenance/docking identity is no longer pinned via {required}")

        acquire = launcher_source.split("Func _AcquireDockKeeper()", 1)
        acquire_body = acquire[1].split("EndFunc", 1)[0] if len(acquire) > 1 else ""
        if "_Singleton(_DockKeeperMutexName(), 1)" not in acquire_body:
            errors.append("launcher docking is no longer protected by a non-exiting singleton probe")
        mutex_name = launcher_source.split("Func _DockKeeperMutexName()", 1)
        mutex_name_body = mutex_name[1].split("EndFunc", 1)[0] if len(mutex_name) > 1 else ""
        for required in ('"Local\\MyBot2DockKeeper_"', "StringLower(@ScriptDir)"):
            if required not in mutex_name_body:
                errors.append(f"launcher dock-keeper ownership is no longer checkout-scoped via {required}")

        keep = launcher_source.split("Func _KeepDocked(", 1)
        keep_body = keep[1].split("EndFunc", 1)[0] if len(keep) > 1 else ""
        for required in (
            "While ProcessExists($iControllerPid)",
            "_ControllerWindowMatches($hController, $iControllerPid)",
            "_FindControllerWindow($iControllerPid)",
            "_FindBlueStacksWindow()",
            "_WindowCanDock($hController)",
            "_WindowCanDock($hBlueStacks)",
            "_DockController($hController, $hBlueStacks, False)",
            "Sleep($g_iDockPollMs)",
        ):
            if required not in keep_body:
                errors.append(f"persistent docking no longer revalidates and follows window geometry via {required}")

        controller_match = launcher_source.split("Func _ControllerWindowMatches(", 1)
        controller_match_body = controller_match[1].split("EndFunc", 1)[0] if len(controller_match) > 1 else ""
        for required in ("WinGetTitle($hWindow)", "WinGetProcess($hWindow)", "_ProcessImagePath($iPid)", "$g_sControllerPath"):
            if required not in controller_match_body:
                errors.append(f"launcher no longer re-proves the Mini controller identity via {required}")

        blue_stacks = launcher_source.split("Func _FindBlueStacksWindow()", 1)
        blue_stacks_body = blue_stacks[1].split("EndFunc", 1)[0] if len(blue_stacks) > 1 else ""
        for required in ("$g_sBlueStacksTitle", '"^Qt[0-9]+QWindowIcon$"', '"\\\\hd-player\\.exe$"'):
            if required not in blue_stacks_body:
                errors.append(f"launcher no longer re-proves the BlueStacks shell identity via {required}")

        dock = launcher_source.split("Func _DockController(", 1)
        dock_body = dock[1].split("EndFunc", 1)[0] if len(dock) > 1 else ""
        stable_offset = dock_body.find("If Abs($aController[0] - $iX) <= 2")
        move_offset = dock_body.find('WinMove($hController, "", $iX, $iY)')
        if stable_offset < 0 or move_offset < 0 or stable_offset > move_offset:
            errors.append("persistent docking no longer avoids needless controller moves")
        if "WinMove($hBlueStacks" in launcher_source:
            errors.append("launcher docking can move BlueStacks instead of only following its geometry")
        for forbidden in ("SetParent", "ControlClick", "ControlSend"):
            if forbidden in launcher_source:
                errors.append(f"launcher docking crossed the no-embed/no-command boundary via {forbidden}")

        browser_open_offset = launcher_entry.find("_OpenControlCenter()")
        owner_guard_offset = launcher_entry.find("If Not $bOwnDockKeeper Then Exit 0")
        if browser_open_offset < 0 or owner_guard_offset < browser_open_offset:
            errors.append("repeat launcher runs no longer open the Control Center before yielding to the singleton keeper")
        if "_OpenControlCenter()" in keep_body:
            errors.append("the persistent dock loop can repeatedly open Control Center tabs")

    # ---------------------------------------------------------------------------------------------
    # The health handshake. The GUI refuses to talk to a service whose /api/health does not name the
    # expected service, bridge, health protocol, repository root, and loaded build. If one side is
    # bumped or a stale process from another checkout owns the port, the GUI refuses to reuse it
    # instead of reporting that an unrelated listener is healthy.
    # ---------------------------------------------------------------------------------------------
    served = planner_ui.health_payload()
    expected = {
        "service": "RUN_PLANNER_SERVICE_NAME",
        "bridge": "RUN_PLANNER_BRIDGE_VERSION",
        "protocol": "RUN_PLANNER_HEALTH_PROTOCOL",
    }
    for field, constant in sorted(expected.items()):
        declared = re.search(rf'Global\s+Const\s+\${constant}\s*=\s*"([^"]*)"', applier_source)
        if not declared:
            errors.append(f"{constant} is not declared in the Run Planner control file")
            continue
        if declared.group(1) != served.get(field):
            errors.append(
                f"health handshake mismatch on {field!r}: the service serves "
                f"{served.get(field)!r} but the GUI requires {declared.group(1)!r}"
            )
    if served.get("ok") is not True:
        errors.append("health_payload does not report ok=true, so the GUI would never accept it")
    if served.get("repo_root") != str(ROOT.resolve()):
        errors.append("health_payload does not identify the exact repository root")
    expected_build = hashlib.sha256((ROOT / "tools/planner_ui.py").read_bytes()).hexdigest()
    if served.get("build_sha256") != expected_build:
        errors.append("health_payload does not identify the exact loaded planner_ui.py build")
    if not isinstance(served.get("service_pid"), int) or served["service_pid"] <= 0:
        errors.append("health_payload does not identify the serving process id")

    # Pattern-matching the payload made the handshake depend on json.dumps spacing. The reader and
    # build-hash helpers are split out so shutdown can verify ownership without accepting a stale
    # build as reusable.
    reader = applier_source.split("Func _RunPlannerReadHealth(", 1)
    reader_body = reader[1].split("EndFunc", 1)[0] if len(reader) > 1 else ""
    if "Json_Decode" not in reader_body:
        errors.append("_RunPlannerReadHealth no longer parses the payload as JSON")
    if "StringInStr" in reader_body:
        errors.append("_RunPlannerReadHealth is substring-matching the health payload again")

    build_hash = applier_source.split("Func _RunPlannerScriptBuildHash()", 1)
    build_hash_body = build_hash[1].split("EndFunc", 1)[0] if len(build_hash) > 1 else ""
    for required in ("_Crypt_HashFile", "$CALG_SHA_256"):
        if required not in build_hash_body:
            errors.append(f"_RunPlannerScriptBuildHash no longer uses {required}")

    healthy = applier_source.split("Func _RunPlannerServiceHealthy()", 1)
    if len(healthy) > 1:
        body = healthy[1].split("EndFunc", 1)[0]
        if "StringInStr" in body:
            errors.append("_RunPlannerServiceHealthy is substring-matching the health payload again")
        for required in ("_RunPlannerReadHealth", "repo_root", "build_sha256", "service_pid", "_RunPlannerScriptBuildHash", "ProcessExists"):
            if required not in body:
                errors.append(f"_RunPlannerServiceHealthy no longer verifies {required}")

    start = applier_source.split("Func _RunPlannerStartService(", 1)
    start_body = start[1].split("EndFunc", 1)[0] if len(start) > 1 else ""
    for required in ("--owner-token", "$g_iRunPlannerOwnedServicePid", "$g_sRunPlannerOwnedServiceToken"):
        if required not in start_body:
            errors.append(f"_RunPlannerStartService no longer records launch ownership via {required}")

    stop = applier_source.split("Func RunPlannerStopOwnedService()", 1)
    stop_body = stop[1].split("EndFunc", 1)[0] if len(stop) > 1 else ""
    if not stop_body:
        errors.append("RunPlannerStopOwnedService is missing from the native planner bridge")
    else:
        for required in ("service_pid", "owner_token", "repo_root", "ProcessClose($iPid)"):
            if required not in stop_body:
                errors.append(f"RunPlannerStopOwnedService no longer bounds shutdown by {required}")

    # Production writers and the Activity panel have to point at the same file. Until RunEventLog.au3
    # existed the only caller of RunEventAppendJsonLine was a test, so the panel read a file nothing
    # ever wrote; a path that drifts would put it straight back to empty.
    log_path = ROOT / "COCBot/functions/Run/RunEventLog.au3"
    if not log_path.is_file():
        errors.append("RunEventLog.au3 is missing; nothing in production writes the Activity feed")
    else:
        log_source = log_path.read_text(encoding="utf-8-sig")
        event_source = (ROOT / "COCBot/functions/Run/RunEvent.au3").read_text(encoding="utf-8-sig")
        event_schema = json.loads((ROOT / "config/run-event.schema.json").read_text(encoding="utf-8-sig"))
        declared = re.search(r'Global\s+Const\s+\$RUN_EVENT_LOG_NAME\s*=\s*"([^"]*)"', log_source)
        served = planner_ui.EVENTS_PATH.relative_to(ROOT).as_posix()
        if not declared:
            errors.append("RUN_EVENT_LOG_NAME is not declared in RunEventLog.au3")
        elif declared.group(1).replace("\\", "/") != served:
            errors.append(
                f"event log path mismatch: the UI reads {served!r} but AutoIt writes {declared.group(1)!r}"
            )
        if "RunEventAppendJsonLine" not in log_source:
            errors.append("RunEventLog.au3 never appends an event, so the Activity feed stays empty")
        for required in ("RunEventLogBindSession", "RunEventLogReleaseSession", "$g_iRunEventSequence = 0"):
            if required not in log_source:
                errors.append(f"Activity events are no longer bounded to one canonical run session by {required}")
        prepare_body = execution_source.split("Func RunExecutionPrepareStart", 1)
        prepare_body = prepare_body[1].split("EndFunc", 1)[0] if len(prepare_body) > 1 else ""
        session_assign = prepare_body.find("$g_oRunExecutionSession = $oSession")
        session_bind = prepare_body.find("RunEventLogBindSession($sSessionId)")
        if session_assign < 0 or session_bind < session_assign:
            errors.append("RunExecution no longer binds Activity events after establishing the canonical session")
        cancel_body = execution_source.split("Func RunExecutionCancelPrepared", 1)
        cancel_body = cancel_body[1].split("EndFunc", 1)[0] if len(cancel_body) > 1 else ""
        if "RunEventLogReleaseSession($sCancelledSessionId)" not in cancel_body:
            errors.append("cancelled prepared runs can strand the Activity logger on a dead session id")
        complete_body = execution_source.split("Func RunExecutionComplete", 1)
        complete_body = complete_body[1].split("EndFunc", 1)[0] if len(complete_body) > 1 else ""
        completed_event = complete_body.find("RunEventLogRunCompleted(")
        completed_release = complete_body.find("RunEventLogReleaseSession(RunExecutionSessionId())")
        if completed_event < 0 or completed_release < completed_event:
            errors.append("completed planned runs do not release the Activity logger after the terminal event")
        validator_block = event_source.split('Switch $oEvent.Item("type")', 1)[-1].split("EndSwitch", 1)[0]
        case_lines = "\n".join(re.findall(r"^\s*Case\s+(.+)$", validator_block, re.MULTILINE))
        accepted_types = set(re.findall(r'"([a-z]+(?:\.[a-z]+)*)"', case_lines))
        emitted_types = set(re.findall(r'RunEventLogWrite\("([a-z]+(?:\.[a-z]+)*)"', log_source))
        schema_types = set(event_schema["properties"]["type"]["enum"])
        rejected_types = sorted(emitted_types - accepted_types)
        if rejected_types:
            errors.append("Activity logger emits event types rejected by RunEventValidate: " + ", ".join(rejected_types))
        if accepted_types != schema_types:
            errors.append("RunEventValidate and config/run-event.schema.json accept different event types")
        serialized_fields = set(re.findall(r'_RunEventJsonString\("([a-z_]+)"\)', event_source))
        schema_fields = set(event_schema["properties"])
        if serialized_fields != schema_fields:
            errors.append("RunEventToJson and config/run-event.schema.json expose different fields")

    # The parser and the tab have to agree on how a list is delimited, since one writes it and the other splits it.
    if 'RUN_PLAN_FILE_LIST_SEPARATOR = "|"' not in parser_source:
        errors.append("the plan file list separator is no longer a pipe; the Hero list would not split")
    if "$RUN_PLAN_FILE_LIST_SEPARATOR" not in applier_source:
        errors.append("the tab splits Hero lists on something other than the parser's separator")

    bridge_source = (ROOT / "COCBot/functions/Run/RunControlBridge.au3").read_text(encoding="utf-8-sig")
    if '"authorization_ready"' not in bridge_source or "ForumAuthorizationReady()" not in bridge_source:
        errors.append("native control status no longer preserves the v1 authorization compatibility field")
    forum_source = (ROOT / "COCBot/functions/Other/ForumAuthentication.au3").read_text(encoding="utf-8-sig")
    forum_auth = forum_source.split("Func ForumAuthentication()", 1)
    forum_auth_body = forum_auth[1].split("EndFunc", 1)[0] if len(forum_auth) > 1 else ""
    if "$g_bForumAuthorizationReady = True" not in forum_source or "Return True" not in forum_auth_body:
        errors.append("forum authorization no longer matches the official v8.2.0 compatibility return")
    for retired_call in ("CheckForumAuthentication", "ForumLogin", "CreateSplashScreen", "GUICtrlCreateInput"):
        if retired_call in forum_auth_body:
            errors.append(f"retired network forum authorization returned via {retired_call}")
    planner_js_auth = (ROOT / "ui/planner.js").read_text(encoding="utf-8-sig")
    if "Sign in & start" in planner_js_auth or "Sign-in needed" in planner_js_auth:
        errors.append("Control Center still presents the retired forum-login flow")
    gui_action_source = (ROOT / "COCBot/MBR GUI Action.au3").read_text(encoding="utf-8-sig")
    if "g_bRunControlStopRequested" not in bridge_source:
        errors.append("browser Stop is not latched while native startup is still running")
    if "RunControlReportStopComplete()" not in gui_action_source:
        errors.append("BotStop does not release the browser Stop latch")

    initialize = bridge_source.split("Func RunControlInitialize()", 1)
    initialize_body = initialize[1].split("EndFunc", 1)[0] if len(initialize) > 1 else ""
    initialize_order = [
        initialize_body.find("_RunControlRejectOrphanedCommand()"),
        initialize_body.find("RunControlWriteStatus(True)"),
    ]
    if any(offset < 0 for offset in initialize_order) or initialize_order != sorted(initialize_order):
        errors.append("RunControlInitialize no longer rejects an orphaned command before publishing its heartbeat")
    orphan_reject = bridge_source.split("Func _RunControlRejectOrphanedCommand()", 1)
    orphan_reject_body = orphan_reject[1].split("EndFunc", 1)[0] if len(orphan_reject) > 1 else ""
    for required in ("FileDelete($sPath)", '$g_sRunControlLastOutcome = "rejected"'):
        if required not in orphan_reject_body:
            errors.append(f"orphaned native commands are no longer cleared and rejected via {required}")

    readiness_reset = bot_start_body.find("$g_bMainWindowOk = False")
    run_state_start = bot_start_body.find("$g_bRunState = True")
    if readiness_reset < 0 or run_state_start < 0 or readiness_reset > run_state_start:
        errors.append("BotStart no longer resets cached game readiness before entering the current Start attempt")

    planner_js = (ROOT / "ui/planner.js").read_text(encoding="utf-8-sig")
    saving_guard_order = [
        planner_js.find("CONTROL_PENDING = savingStart;"),
        planner_js.find("const saved = await savePlan();"),
        planner_js.find("CONTROL_PENDING !== savingStart"),
    ]
    if any(offset < 0 for offset in saving_guard_order) or saving_guard_order != sorted(saving_guard_order):
        errors.append("browser Start no longer locks before saving or rejects an invalidated asynchronous save")
    if "if (!saved) {\n      CONTROL_PENDING = null;" not in planner_js:
        errors.append("browser Start can strand its pending guard after a plan-save failure")

    bluestacks_source = (ROOT / "COCBot/functions/Android/AndroidBluestacks5.au3").read_text(encoding="utf-8-sig")
    if "bstk/su root" in bluestacks_source:
        errors.append("BlueStacks 5 still invokes the obsolete bstk/su root shell wrapper")
    if 'bst.enable_adb_access="1"' not in bluestacks_source:
        errors.append("BlueStacks 5 setup does not enable its required non-root ADB access setting")
    android_source = (ROOT / "COCBot/functions/Android/Android.au3").read_text(encoding="utf-8-sig")
    handle_body = android_source.split("Func _WinGetAndroidHandle", 1)[-1].split("EndFunc", 1)[0]
    fallback_offset = handle_body.find("FindBlueStacks5WindowFallback()")
    legacy_title_offset = handle_body.find("If $bFindByTitle = True Then")
    if fallback_offset < 0 or legacy_title_offset < 0 or fallback_offset > legacy_title_offset:
        errors.append("modern BlueStacks discovery no longer precedes the legacy title path's early return")
    surface_body = bluestacks_source.split("Func GetBlueStacks5ModernAdbSurfacePosition()", 1)
    surface_body = surface_body[1].split("EndFunc", 1)[0] if len(surface_body) > 1 else ""
    for required in (
        "_WinAPI_EnumWindows(False)",
        'StringCompare($sTitle, "BlueStacks5-" & $g_sAndroidInstance, 0)',
        "BitAND(WinGetState($hWindow), 16) = 0",
    ):
        if required not in bluestacks_source:
            errors.append(f"modern BlueStacks hidden-window discovery is no longer bounded by {required}")
    open_blusestacks_body = bluestacks_source.split("Func _OpenBlueStacks5(", 1)
    open_blusestacks_body = open_blusestacks_body[1].split("EndFunc", 1)[0] if len(open_blusestacks_body) > 1 else ""
    for required in (
        "LaunchAndroid($g_sAndroidProgramPath, $cmdPar, $g_sAndroidPath, 0, False)",
        "If $PID = 0 And WinGetAndroidHandle() = 0 Then",
    ):
        if required not in open_blusestacks_body:
            errors.append(f"BlueStacks duplicate-launch recovery no longer requires {required}")
    for required in (
        "$g_bChkBackgroundMode",
        "$g_bAndroidAdbScreencap",
        "$g_bAndroidAdbClick",
        "^Qt[0-9]+QWindowIcon$",
        'StringCompare(WinGetTitle($hWindow), "BlueStacks5-" & $g_sAndroidInstance, 0)',
        "$g_iAndroidClientWidth",
        "$g_iAndroidClientHeight",
    ):
        if required not in surface_body:
            errors.append(f"modern BlueStacks framebuffer geometry is no longer guarded by {required}")
    position_source = (ROOT / "COCBot/functions/Android/getBSPos.au3").read_text(encoding="utf-8-sig")
    position_body = position_source.split("Func getAndroidPos(", 1)[-1].split("EndFunc", 1)[0]
    surface_offset = position_body.find("GetBlueStacks5ModernAdbSurfacePosition()")
    control_offset = position_body.find("ControlGetPos(")
    if surface_offset < 0 or control_offset < 0 or surface_offset > control_offset:
        errors.append("modern BlueStacks ADB geometry no longer bypasses generic shell resizing")

    bottom_controls = BOTTOM.read_text(encoding="utf-8-sig")
    background_sync = bottom_controls.split("Func UpdateChkBackground()", 1)
    background_sync_body = background_sync[1].split("EndFunc", 1)[0] if len(background_sync) > 1 else ""
    remote_guard_offset = background_sync_body.find("$g_iGuiMode = 0 Or $g_hChkBackgroundMode <= 0")
    checkbox_read_offset = background_sync_body.find("GUICtrlRead($g_hChkBackgroundMode)")
    if remote_guard_offset < 0 or checkbox_read_offset < 0 or remote_guard_offset > checkbox_read_offset:
        errors.append("remote /ng startup can overwrite the loaded Background setting from a missing native checkbox")

    # The plan file must stay out of version control: it is machine-local and can name an emulator instance.
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8-sig") if (ROOT / ".gitignore").exists() else ""
    if "run-plan.local.json" not in ignore:
        errors.append(".gitignore does not exclude config/run-plan.local.json")

    report = {
        "schema_version": 1,
        "settings": len(settings),
        "plan_keys": len(plan),
        "applied_types": sorted(branches),
        "errors": errors,
        "warnings": warnings,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
