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
EXECUTION_CONTRACT = ROOT / "COCBot/functions/Run/RunExecutionContract.au3"
TRAIN_SYSTEM = ROOT / "COCBot/functions/CreateArmy/TrainSystem.au3"
ACTION = ROOT / "COCBot/MBR GUI Action.au3"
BOTTOM = ROOT / "COCBot/GUI/MBR GUI Control Bottom.au3"
CHECK_MAIN_SCREEN = ROOT / "COCBot/functions/Main Screen/checkMainScreen.au3"
VILLAGE_READINESS = ROOT / "COCBot/functions/Run/RunVillageReadiness.au3"
VILLAGE_DETECTOR = ROOT / "COCBot/functions/Village/BotDetectFirstTime.au3"
TOWN_HALL_SEARCH = ROOT / "COCBot/functions/Image Search/imglocTHSearch.au3"
CONTROL = ROOT / "COCBot/functions/Run/RunControlBridge.au3"
API_CLIENT = ROOT / "COCBot/functions/Other/ApiClient.au3"
MAIN = ROOT / "MyBot.run.au3"
LAUNCHER = ROOT / "My Bot 2.0.au3"
ENGINE_PROBE = ROOT / "MyBot.run.EngineProbe.au3"
ENGINE_PROBE_CONFIG = ROOT / "MyBot.run.EngineProbe.exe.config"
MBR_FUNC = ROOT / "COCBot/functions/Other/MBRFunc.au3"
COLLECTOR_RECOGNIZER = ROOT / "COCBot/functions/Run/CollectorBubbleRecognizer.au3"

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


def read_autoit_source(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


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
    default_preflight = planner_ui.engine_preflight(plan)
    if not any("supervised diagnostic acknowledgement" in problem for problem in default_preflight):
        errors.append("the browser default plan can bypass diagnostic acknowledgement for gated routes")
    acknowledged_plan = dict(plan)
    acknowledged_plan["run.diagnostic_mode"] = True
    acknowledged_plan["run.diagnostic_note"] = "bridge audit acknowledgement"
    acknowledged_problems = planner_ui.engine_preflight(acknowledged_plan)
    if not any("inherited ImgLoc runtime rejected exact-current" in problem for problem in acknowledged_problems):
        errors.append("diagnostic acknowledgement can bypass the exact-current ImgLoc battle blocker")
    for setting_id, bad_value in (
        ("run.surface", "builder"),
        ("run.strategy", "legacy.smart-farm"),
        ("search.max_seconds", 15),
        ("pacing.retry_attempts", 1),
        ("notify.channel", "telegram"),
    ):
        impossible = dict(plan)
        impossible[setting_id] = bad_value
        if not planner_ui.engine_preflight(impossible):
            errors.append(f"browser preflight would save native-incompatible {setting_id}={bad_value}")

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
    # Explicit text settings and the two legacy free-text metadata kinds share the native fallback.
    fallback = {"instance-select", "profile-queue", "text"}
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

        for required in (
            "$g_bRunExecutionManageTraining = RunIntentManagesTraining($g_oRunExecutionIntent)",
            "Func RunExecutionShouldManageTraining()",
            "Func RunExecutionSkipVillageZoomCalibration()",
        ):
            if required not in execution_source:
                errors.append(f"one-run training management no longer reaches RunExecution via {required}")

        skip_zoom = execution_source.split("Func RunExecutionSkipVillageZoomCalibration()", 1)
        skip_zoom_body = skip_zoom[1].split("EndFunc", 1)[0] if len(skip_zoom) > 1 else ""
        for required in (
            "If Not $g_bRunExecutionPrepared Or $g_bRunExecutionManageTraining Then Return False",
            "Return True",
        ):
            if required not in skip_zoom_body:
                errors.append(f"village zoom bypass lost its bounded-route boundary via {required}")
        for forbidden in ("HomeMaintenanceRouteSelected", "ClanRequestRouteSelected"):
            if forbidden in skip_zoom_body:
                errors.append(f"bounded Home route still falls through legacy village calibration via {forbidden}")

        skip_notifications = execution_source.split("Func RunExecutionSkipPendingNotifications()", 1)
        skip_notifications_body = skip_notifications[1].split("EndFunc", 1)[0] if len(skip_notifications) > 1 else ""
        if "$g_bRunExecutionPrepared And Not $g_bRunExecutionManageTraining" not in skip_notifications_body:
            errors.append("pending-action suppression is not limited to a prepared bounded run")

        main_screen_source = CHECK_MAIN_SCREEN.read_text(encoding="utf-8-sig")
        main_screen = main_screen_source.split("Func _checkMainScreen(", 1)
        main_screen_body = main_screen[1].split("EndFunc", 1)[0] if len(main_screen) > 1 else ""
        zoom_guard = main_screen_body.find("RunExecutionSkipVillageZoomCalibration()")
        zoom_call = main_screen_body.find("ZoomOut()")
        if zoom_guard < 0 or zoom_call < zoom_guard:
            errors.append("checkMainScreen still requires unsupported scenery anchors in current-army mode")
        notification_guard = (
            'If RunExecutionSkipPendingNotifications() Then\n'
            '\t\tSetDebugLog("Run Planner bounded mode: skipped legacy pending notifications during screen proof")\n'
            '\tElse\n'
            '\t\tNotifyPendingActions()\n'
            '\tEndIf'
        )
        if notification_guard not in main_screen_body:
            errors.append("current-army screen proof can still invoke legacy pending notifications")
        restore_training = execution_source.split("Func _RunExecutionRestoreProfile()", 1)
        restore_training_body = restore_training[1].split("EndFunc", 1)[0] if len(restore_training) > 1 else ""
        if restore_training_body.count("$g_bRunExecutionManageTraining = True") < 2:
            errors.append("RunExecution restore does not clear current-army mode on both snapshot paths")

    # Current-army mode must still inspect readiness, but it may not cross into any inherited path
    # that can delete a mismatched troop or queue the stale profile army.
    if not TRAIN_SYSTEM.is_file():
        errors.append("TrainSystem.au3 is missing; current-army safety cannot be verified")
    else:
        train_source = TRAIN_SYSTEM.read_text(encoding="utf-8-sig")
        train = train_source.split("Func TrainSystem()", 1)
        train_body = train[1].split("EndFunc", 1)[0] if len(train) > 1 else ""
        ordered_training_boundary = [
            train_body.find("If Not RunExecutionShouldManageTraining() Then"),
            train_body.find("CheckPassiveCurrentArmyReady()"),
            train_body.find("EndGainCost(\"Train\")"),
            train_body.find("Return", train_body.find("EndGainCost(\"Train\")")),
            train_body.find("BoostSuperTroop()"),
            train_body.find("CheckQuickTrainTroop()"),
            train_body.find("QuickTrain()"),
            train_body.find("TrainCustomArmy()"),
            train_body.find("TrainSiege()"),
        ]
        if any(offset < 0 for offset in ordered_training_boundary) or ordered_training_boundary != sorted(ordered_training_boundary):
            errors.append("current-army mode no longer returns after a passive readiness check and before every training mutation path")

        passive = train_source.split("Func CheckPassiveCurrentArmyReady()", 1)
        passive_body = passive[1].split("EndFunc", 1)[0] if len(passive) > 1 else ""
        for required in (
            'OpenArmyOverview(False, "CheckPassiveCurrentArmyReady()", False)',
            "PassiveCurrentArmyCapacityProof(",
            "$g_bIsFullArmywithHeroesAndSpells = True",
        ):
            if required not in passive_body:
                errors.append(f"passive current-army observer no longer proves fresh readiness via {required}")
        for forbidden in ("CheckArmyCamp(", "BuildingClick(", "BuildingClickP(", "HiddenSlotstatus(", "RemoveExtraTroops("):
            if forbidden in passive_body:
                errors.append(f"passive current-army observer reaches forbidden legacy work via {forbidden}")

        readiness = train_source.split("Func CheckIfArmyIsReady(", 1)
        readiness_body = readiness[1].split("EndFunc", 1)[0] if len(readiness) > 1 else ""
        mutation_guard = readiness_body.find("If $bAllowArmyMutation And")
        removal = readiness_body.find("RemoveExtraTroops(")
        if mutation_guard < 0 or removal < mutation_guard:
            errors.append("CheckIfArmyIsReady can remove mismatched troops during the passive current-army check")

    action_source = ACTION.read_text(encoding="utf-8-sig")
    bot_start = action_source.split("Func BotStart(", 1)
    bot_start_body = bot_start[1].split("EndFunc", 1)[0] if len(bot_start) > 1 else ""
    ordered_calls = [
        "RunExecutionPrepareStart",
        "RunExecutionApplyPreparedTransport($sStartError)",
        "MBRFuncProbeEngine",
        "MBRFuncInitialize",
        "ForumAuthentication",
        "applyConfig(False)",
        "RunExecutionApplyPrepared($sStartError)",
    ]
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
    if 'StringInStr(@OSVersion, "WIN_11"' in initiate_body:
        errors.append("Initiate still classifies supported Windows 11 desktop as an unsupported operating system")
    for server_version in ("WIN_2019", "WIN_2022"):
        if f'StringInStr(@OSVersion, "{server_version}"' not in initiate_body:
            errors.append(f"Initiate no longer identifies unsupported Windows Server target {server_version}")
    if "Windows 10/11 desktop is supported; Windows Server 2019/2022 is outside the supported target" not in initiate_body:
        errors.append("Initiate no longer explains the Windows desktop and Server support boundary accurately")

    # A current-army run deliberately skips legacy village zoom calibration. It must prove the
    # current main-screen TH from raw framebuffer data, then bypass every coordinate conversion.
    village_readiness_source = VILLAGE_READINESS.read_text(encoding="utf-8-sig")
    village_detector_source = VILLAGE_DETECTOR.read_text(encoding="utf-8-sig")
    town_hall_search_source = TOWN_HALL_SEARCH.read_text(encoding="utf-8-sig")
    identity_detector = town_hall_search_source.split("Func imglocOwnVillageTownHallIdentity(", 1)
    identity_detector_body = identity_detector[1].split("EndFunc", 1)[0] if len(identity_detector) > 1 else ""
    for forbidden in (
        "ResetTHsearch",
        "ConvertFromVillagePos",
        "_ObjPutValue",
        "$g_iSearchTH",
        "$g_iTHx",
        "$g_iTHy",
        "BuildingClick",
        "SaveConfig",
    ):
        if forbidden in identity_detector_body:
            errors.append(f"raw Town Hall identity detector crosses a forbidden legacy side effect: {forbidden}")
    for required in ("findMultiple(", '"objectname,objectlevel,objectpoints"', "$g_iGAME_WIDTH", "$g_iGAME_HEIGHT"):
        if required not in identity_detector_body:
            errors.append(f"raw Town Hall identity detector no longer validates {required}")
    for required in (
        "$iExpectedTownHallLevel = 0",
        "$iMinimumLevel = ($iExpectedLevel > 0 ? $iExpectedLevel : 2)",
        "$iMaximumLevel = ($iExpectedLevel > 0 ? $iExpectedLevel : $g_iMaxTHLevel)",
        "conflicting matches; identity was not accepted",
    ):
        if required not in town_hall_search_source:
            errors.append(f"raw Town Hall identity detector no longer fails closed via {required}")

    planned_detector = village_detector_source.split("Func BotDetectFirstTime(", 1)
    planned_detector_body = planned_detector[1].split("EndFunc", 1)[0] if len(planned_detector) > 1 else ""
    planned_detection_order = [
        planned_detector_body.find("RunVillageReadinessResetIdentity()"),
        planned_detector_body.find("imglocOwnVillageTownHallIdentity("),
        planned_detector_body.find("RunVillageReadinessMarkIdentityVerified("),
        planned_detector_body.find("If RunExecutionSkipVillageZoomCalibration() Then Return"),
    ]
    if any(offset < 0 for offset in planned_detection_order) or planned_detection_order != sorted(planned_detection_order):
        errors.append("planned Town Hall detection no longer resets, proves, latches, and exits identity-only mode in order")
    if "$g_iTownHallLevel) Then" not in planned_detector_body:
        errors.append("planned Town Hall detection no longer constrains visual matching to a valid loaded profile level")
    for required in (
        "RunExecutionSkipVillageZoomCalibration()",
        "RunVillageReadinessMarkMainScreenProfileAttested(",
        "without building coordinates",
    ):
        if required not in planned_detector_body:
            errors.append(f"current-army Town Hall fallback is no longer explicitly bounded by {required}")
    fallback_attestation = planned_detector_body.find("RunVillageReadinessMarkMainScreenProfileAttested(")
    strict_identity_failure = planned_detector_body.find("Own-village Town Hall identity could not be verified")
    if fallback_attestation < 0 or strict_identity_failure < fallback_attestation:
        errors.append("building-managing planned runs no longer fail closed after the bounded current-army TH fallback")

    validator = village_readiness_source.split("Func RunVillageReadinessValidate(", 1)
    validator_body = validator[1].split("EndFunc", 1)[0] if len(validator) > 1 else ""
    for required in ("$bTownHallIdentityVerified", "If Not $bTownHallIdentityVerified Then", "$bTownHallCoordinatesRequired"):
        if required not in validator_body:
            errors.append(f"own-village readiness validator no longer fails closed via {required}")

    planned_ready_order = [
        initiate_body.find("BotDetectFirstTime(True)"),
        initiate_body.find("$bTownHallIdentityVerified = RunVillageReadinessIdentityVerified("),
        initiate_body.find("RunVillageReadinessValidate("),
        initiate_body.find("AndroidBotStartEvent()"),
        initiate_body.find("RunExecutionBegin("),
        initiate_body.find("RunControlReportStartOutcome(True"),
    ]
    if any(offset < 0 for offset in planned_ready_order) or planned_ready_order != sorted(planned_ready_order):
        errors.append("planned Start no longer proves fresh Town Hall identity before its readiness and running boundaries")
    if "RunVillageReadinessValidate($g_iTownHallLevel, isInsideDiamond(" in initiate_body:
        errors.append("planned Start eagerly evaluates legacy village coordinates in identity-only mode")

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

    run_bot = main_source.split("Func runBot()", 1)
    run_bot_body = run_bot[1].split("EndFunc", 1)[0] if len(run_bot) > 1 else ""
    current_army_boundary = [
        run_bot_body.find("If RunExecutionPlanActive() And Not RunExecutionShouldManageTraining() Then"),
        run_bot_body.find("_RunExecutionRunCurrentArmyOneBattle()"),
        run_bot_body.find("Return", run_bot_body.find("_RunExecutionRunCurrentArmyOneBattle()")),
        run_bot_body.find("InitiateSwitchAcc()"),
        run_bot_body.find("FirstCheck()"),
        run_bot_body.find("While 1"),
    ]
    if any(offset < 0 for offset in current_army_boundary) or current_army_boundary != sorted(current_army_boundary):
        errors.append("current-army one-shot no longer returns before account switching, FirstCheck, and the generic maintenance loop")

    current_army = main_source.split("Func _RunExecutionRunCurrentArmyOneBattle()", 1)
    current_army_body = current_army[1].split("EndFunc", 1)[0] if len(current_army) > 1 else ""
    current_army_order = [
        current_army_body.find("$g_bIsFullArmywithHeroesAndSpells = False"),
        current_army_body.find("TrainSystem()"),
        current_army_body.find("If Not $g_bIsFullArmywithHeroesAndSpells Then"),
        current_army_body.find("current trained army is not ready"),
        current_army_body.find("$g_bRestart = False"),
        current_army_body.find("AttackMain(True)"),
        current_army_body.find("RunExecutionCheckStop()"),
        current_army_body.find("single attack attempt returned without completing the planned battle"),
    ]
    if any(offset < 0 for offset in current_army_order) or current_army_order != sorted(current_army_order):
        errors.append("current-army terminal path no longer refreshes readiness, fails closed, attacks once, and checks its stop in order")
    main_screen_proof = current_army_body.find("Local $bMainScreenReady = checkMainScreen(False)")
    stop_after_proof = current_army_body.find("If $g_bRunControlStopRequested Or Not $g_bRunState Then Return False", main_screen_proof)
    proof_failure = current_army_body.find("If Not $bMainScreenReady Then", stop_after_proof)
    if min(main_screen_proof, stop_after_proof, proof_failure) < 0 or not (main_screen_proof < stop_after_proof < proof_failure):
        errors.append("current-army screen proof can relabel an accepted Stop as a readiness failure")
    if current_army_body.count("AttackMain(True)") != 1 or current_army_body.count("RunExecutionCheckStop()") != 1:
        errors.append("current-army terminal path must contain exactly one AttackMain and one post-attack stop check")
    if current_army_body.count("$g_bRestart = False") != 1:
        errors.append("current-army terminal path no longer clears the inherited per-loop restart latch exactly once before attack")
    for forbidden in (
        "ZoomOut(",
        "SearchZoomOut(",
        "GetVillageSize(",
        "BuildingClick(",
        "BuildingClickP(",
        "HiddenSlotstatus(",
        "BotDetectFirstTime(",
        "imglocTHSearch(",
        "VillageReport(",
        "_RunFunction(",
        "Idle(",
        "Unbreakable(",
        "BuilderBase(",
        "TakeWardenValues(",
    ):
        if forbidden in current_army_body:
            errors.append(f"current-army terminal path reaches forbidden legacy work via {forbidden}")

    attack_main = main_source.split("Func AttackMain(", 1)
    attack_main_body = attack_main[1].split("EndFunc", 1)[0] if len(attack_main) > 1 else ""
    planner_attack_offset = attack_main_body.find("If $bPlannerTerminalOneBattle Then")
    legacy_schedule_offset = attack_main_body.find("If IsSearchAttackEnabled() Then")
    if planner_attack_offset < 0 or legacy_schedule_offset < 0 or planner_attack_offset > legacy_schedule_offset:
        errors.append("planner terminal attack no longer bypasses inherited schedules before the legacy branch")
    else:
        planner_attack_body = attack_main_body[planner_attack_offset:legacy_schedule_offset]
        if "Return _AttackMainExecuteRegularBattle()" not in planner_attack_body:
            errors.append("planner terminal attack does not enter the bounded regular-battle core")
        for forbidden in ("SmartPause(", "IsSearchAttackEnabled(", "UniversalCloseWaitOpenCoC(", "_ClanGames(", "DropTrophy(", "ProfileReport(", "checkSwitchAcc("):
            if forbidden in planner_attack_body:
                errors.append(f"planner terminal attack can still execute inherited diversion: {forbidden}")

    battle_core = main_source.split("Func _AttackMainExecuteRegularBattle()", 1)
    battle_core_body = battle_core[1].split("EndFunc", 1)[0] if len(battle_core) > 1 else ""
    battle_core_order = [
        battle_core_body.find("PrepareSearch()"),
        battle_core_body.find("VillageSearch()"),
        battle_core_body.find("PrepareAttack($g_iMatchMode)"),
        battle_core_body.find("Attack()"),
        battle_core_body.find("ReturnHome($g_bTakeLootSnapShot)"),
        battle_core_body.find("Return True"),
    ]
    if any(offset < 0 for offset in battle_core_order) or battle_core_order != sorted(battle_core_order):
        errors.append("bounded regular-battle core no longer searches, attacks, returns home, and succeeds in order")
    for forbidden in ("SmartPause(", "UniversalCloseWaitOpenCoC(", "_ClanGames(", "DropTrophy("):
        if forbidden in battle_core_body:
            errors.append(f"bounded regular-battle core contains inherited diversion: {forbidden}")

    execution_contract_source = EXECUTION_CONTRACT.read_text(encoding="utf-8-sig")
    managed_contract = execution_contract_source.split("If RunIntentManagesTraining($oIntent) Then", 1)
    managed_contract_body = managed_contract[1].split("EndIf", 1)[0] if len(managed_contract) > 1 else ""
    for required in (
        "Managed training is disabled",
        "inherited profile training path is not closed-world",
        "turn Manage training off and use the current trained army for one battle",
        "Return SetError(5, 9, False)",
    ):
        if required not in managed_contract_body:
            errors.append(f"managed training no longer fails closed via {required}")
    if "$bDiagnostic" in managed_contract_body:
        errors.append("diagnostic acknowledgement can bypass the managed-training fail-closed gate")
    managed_guard_offset = execution_contract_source.find("If RunIntentManagesTraining($oIntent) Then")
    passive_guard_offset = execution_contract_source.find('If Int($oPlan.Item("max_battles")) <> 1 Then')
    if managed_guard_offset < 0 or passive_guard_offset < 0 or managed_guard_offset > passive_guard_offset:
        errors.append("managed training is not rejected before the bounded current-army contract")

    passive_contract = execution_contract_source.split('If Int($oPlan.Item("max_battles")) <> 1 Then', 1)
    passive_contract_body = passive_contract[1].split('If Int($oPlan.Item("search_max_seconds"))', 1)[0] if len(passive_contract) > 1 else ""
    for required in (
        'If Not $oPlan.Item("army_wait_for_full") Then',
        '$oPlan.Item("donate_request_when_short")',
        'If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or $oPlan.Item("events_collect_loot_cart") Or _',
        '$oPlan.Item("events_collect_treasury") Then',
        'If $oPlan.Item("events_clan_games") Then',
        'Home collection work requires the explicit Home maintenance strategy',
        '$oPlan.Item("events_laboratory")',
        '$oPlan.Item("upgrade_policy")',
    ):
        if required not in passive_contract_body:
            errors.append(f"current-army contract no longer rejects pre-battle side effects via {required}")

    control_source = CONTROL.read_text(encoding="utf-8-sig")
    report_failure = control_source.split("Func RunControlReportRunFailure(", 1)
    report_failure_body = report_failure[1].split("EndFunc", 1)[0] if len(report_failure) > 1 else ""
    stop_guard_offset = report_failure_body.find("If $g_bRunControlStopRequested Then")
    failure_outcome_offset = report_failure_body.find('$g_sRunControlLastOutcome = "failed"')
    if stop_guard_offset < 0 or failure_outcome_offset < 0 or stop_guard_offset > failure_outcome_offset:
        errors.append("run failures can overwrite an accepted Stop before BotStop completes")
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
    collector_recognizer_source = COLLECTOR_RECOGNIZER.read_text(encoding="utf-8-sig")
    engine_probe_source = ENGINE_PROBE.read_text(encoding="utf-8-sig")
    engine_probe_config = ENGINE_PROBE_CONFIG.read_text(encoding="utf-8-sig")
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
    if "DllOpen($g_sLibMyBotPath)" in mbr_open_body or "_MBRFuncOpenEngineLibrary()" in mbr_open_body:
        errors.append("MBRFunc can open the managed engine outside the supervised initialization boundary")

    public_imgloc = mbr_source.split("Func DllCallMyBot(", 1)
    public_imgloc_body = public_imgloc[1].split("EndFunc", 1)[0] if len(public_imgloc) > 1 else ""
    recognition_available = mbr_source.split("Func MBRFuncRecognitionAvailable()", 1)
    recognition_available_body = recognition_available[1].split("EndFunc", 1)[0] if len(recognition_available) > 1 else ""
    managed_bound = mbr_source.split("Func MBRFuncManagedLaunchBound()", 1)
    managed_bound_body = managed_bound[1].split("EndFunc", 1)[0] if len(managed_bound) > 1 else ""
    for required in (
        "$g_bMBRFuncBackendHost",
        "$g_bMBRFuncEngineSupervisorValid",
        "ProcessExists($iLauncherPid)",
        "_MBRFuncProcessCreationId($iLauncherPid)",
    ):
        if required not in managed_bound_body:
            errors.append(f"managed inherited recognition ownership no longer requires {required}")
    for required in ("MBRFuncManagedLaunchBound()", "$g_bMBRFuncEngineAvailable"):
        if required not in recognition_available_body:
            errors.append(f"managed inherited recognition availability no longer requires {required}")
    public_guard = public_imgloc_body.find("Not MBRFuncRecognitionAvailable()")
    public_dispatch = public_imgloc_body.find("_DllCallMyBot($sFunc")
    if public_guard < 0 or public_dispatch < 0 or public_guard >= public_dispatch:
        errors.append("public inherited recognition is not gated before its single managed dispatch")
    for required in (
        "Return SetError(1, 0, $aUnavailable)",
        "Not MBRFuncManagedLaunchBound()",
        "Managed recognition timed out or lost launcher ownership",
    ):
        if required not in public_imgloc_body:
            errors.append(f"managed inherited recognition no longer fails closed via {required}")

    for source_path in (ROOT / "COCBot").rglob("*.au3"):
        if source_path == MBR_FUNC:
            continue
        source_text = read_autoit_source(source_path)
        if 'DllCall($g_hLibMyBot' in source_text:
            errors.append(
                "managed recognition bypasses the fail-closed wrapper: "
                + str(source_path.relative_to(ROOT)).replace("\\", "/")
            )
    for forbidden in ("DllCallMyBot", "FindTile", "SearchMultipleTiles", "ShellExecute", ".html"):
        if forbidden in collector_recognizer_source:
            errors.append(f"clean-room collector recognizer reached protected runtime behavior: {forbidden}")

    private_open = mbr_source.split("Func _MBRFuncOpenEngineLibrary()", 1)
    private_open_body = private_open[1].split("EndFunc", 1)[0] if len(private_open) > 1 else ""
    if private_open_body.count("DllOpen($g_sLibMyBotPath)") != 1 or mbr_source.count("DllOpen($g_sLibMyBotPath)") != 1:
        errors.append("managed engine loading is not confined to the single private supervised helper")

    mbr_initialize = mbr_source.split("Func MBRFuncInitialize(", 1)
    mbr_initialize_body = mbr_initialize[1].split("EndFunc", 1)[0] if len(mbr_initialize) > 1 else ""
    initialize_marker_offset = mbr_initialize_body.find("MBRFuncValidateEngineMarker(")
    prepared_offset = mbr_initialize_body.find('_MBRFuncPublishEngineReceipt("prepared")')
    private_open_offset = mbr_initialize_body.find("_MBRFuncOpenEngineLibrary()")
    first_export_offset = mbr_initialize_body.find("setAndroidPID(")
    if (
        initialize_marker_offset < 0
        or prepared_offset < 0
        or private_open_offset < 0
        or first_export_offset < 0
        or not (initialize_marker_offset < prepared_offset < private_open_offset < first_export_offset)
    ):
        errors.append("MBRFuncInitialize does not publish supervised ownership before loading or calling the managed engine")

    expected_phases = (
        "prepared", "pool-entered", "pool-returned", "max-entered", "max-returned",
        "android-entered", "android-returned", "gui-entered", "initialized",
    )
    phase_calls = [mbr_initialize_body.find(f'_MBRFuncPublishEngineReceipt("{phase}")') for phase in expected_phases]
    skip_calls = [mbr_initialize_body.find(name) for name in ("inherited processing-pool initialization skipped", "inherited max-degree initialization skipped")]
    real_calls = [mbr_initialize_body.find(name) for name in ("setAndroidPID(", "SetBotGuiPID(")]
    expected_order = [phase_calls[0], phase_calls[1], skip_calls[0], phase_calls[2], phase_calls[3], skip_calls[1], phase_calls[4], phase_calls[5], real_calls[0], phase_calls[6], phase_calls[7], real_calls[1], phase_calls[8]]
    if any(offset < 0 for offset in expected_order) or expected_order != sorted(expected_order):
        errors.append("real-host managed initialization no longer publishes monotonic phases around every synchronous export")
    if mbr_initialize_body.count("setProcessingPoolSize(") != 0:
        errors.append("real host supervised initializer must not call the blocking processing-pool export")
    if mbr_initialize_body.count("setMaxDegreeOfParallelism(") != 0:
        errors.append("real host supervised initializer must not call the blocking max-degree export")

    probe = mbr_source.split("Func MBRFuncProbeEngine(", 1)
    probe_body = probe[1].split("EndFunc", 1)[0] if len(probe) > 1 else ""
    for forbidden in ("Run(", "DllCall(", "MyBot.run.EngineProbe.exe", "setProcessingPoolSize("):
        if forbidden in probe_body:
            errors.append(f"static managed-engine gate still performs stateful helper work: {forbidden}")
    for required in ("MBRFuncValidateEngineMarker(", "$g_bMBRFuncEngineSupervisorValid"):
        if required not in probe_body:
            errors.append(f"static managed-engine gate no longer fails closed via {required}")

    for required in (
        'Global Const $g_sMBRFuncEngineSupervisorSchema = "engine-init-supervisor-v1"',
        'Global Const $g_sMBRFuncRuntimeLocalAppData = _MBRFuncRuntimeLocalAppDataDir()',
        'Global Const $g_sMBRFuncEngineReceiptPath = $g_sMBRFuncRuntimeLocalAppData & "\\My Bot 2.0\\engine-init-owner-v1.json"',
        'If EnvGet("MYBOT_RUN_PYTHON_INTEGRATION") <> "1" Then Return @LocalAppDataDir',
        'EnvGet("MYBOT_INSTALL_TEST_ROOT")',
        'Return @ScriptDir & "\\.invalid-test-localappdata"',
        '"^[0-9a-f]{64}$"',
        '"^[0-9a-f]{16}$"',
        'EnvSet($g_sMBRFuncEngineTokenEnv, "")',
        'EnvSet($g_sMBRFuncEngineLauncherPidEnv, "")',
        'EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, "")',
        '^mybot\\.run(?:\\.minigui)?\\.(?:exe|au3)$',
        "If $g_bMBRFuncEngineContextHost Then",
        "$g_bMBRFuncEngineContextHost And StringRegExp",
    ):
        if required not in mbr_source:
            errors.append(f"managed-engine supervisor context no longer enforces {required}")
    publish = mbr_source.split("Func _MBRFuncPublishEngineReceipt(", 1)
    publish_body = publish[1].split("EndFunc", 1)[0] if len(publish) > 1 else ""
    for field in ("schema", "token", "launcher_pid", "launcher_created", "controller_pid", "controller_created", "backend_pid", "backend_created", "parent_pid", "phase", "start_request_id", "sequence"):
        if f'\\"{field}\\"' not in publish_body.replace('"', '\\"'):
            errors.append(f"managed-engine ownership receipt no longer binds {field}")
    publish_offsets = [publish_body.find(required) for required in ("FileOpen(", "FileWrite(", "FileFlush(", "FileClose(", "FileMove(", "FileRead(")]
    if any(offset < 0 for offset in publish_offsets) or publish_offsets != sorted(publish_offsets):
        errors.append("managed-engine ownership receipt is no longer flushed, atomically replaced, and read back")
    for required in ("_MBRFuncEngineReceiptPathSafe(False)", "_MBRFuncEngineReceiptPathSafe(True)"):
        if required not in publish_body:
            errors.append(f"managed-engine ownership receipt no longer checks non-reparse safety via {required}")
    if "$sLauncherCreated <> $g_sMBRFuncEngineLauncherCreated" not in publish_body:
        errors.append("managed-engine ownership receipt no longer verifies the live launcher creation identity")

    if "useLegacyV2RuntimeActivationPolicy" in engine_probe_config:
        errors.append("managed engine probe still enables the unnecessary legacy CLR v2 activation policy")
    if 'supportedRuntime version="v4.0"' not in engine_probe_config:
        errors.append("managed engine probe no longer pins CLR v4")
    if '<probing privatePath="lib" />' not in engine_probe_config:
        errors.append("managed engine probe no longer probes the private lib directory")
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
            'Global Const $g_sBinaryProvenancePath = @ScriptDir & "\\config\\binary-provenance.json"',
            'Func _ControllerProvenanceMatches()',
            '"kind"\\s*:\\s*"local-build"',
            '"source"\\s*:\\s*"MyBot\\.run\\.MiniGui\\.au3"',
            'UBound($aIdentity) <> 2',
            'Global Const $g_sControllerTitlePattern = "^My Bot 2\\.0 Mini v2\\.0\\.0(?: \\([A-Za-z0-9_. -]{1,64}\\))?$"',
            'Global Const $g_sRecoveryLogPath = $g_sUserDataRoot & "\\launcher-recovery.log"',
            'Global Const $g_iDockGap = 8',
        ):
            if required not in launcher_source:
                errors.append(f"launcher provenance/docking identity is no longer fail-closed via {required}")

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
            "_FindBlueStacksWindow($hController)",
            "_WindowCanDock($hController)",
            "_WindowCanDock($hBlueStacks)",
            "_DockController($hController, $hBlueStacks, False)",
            "_AdaptiveDockPollDelay($sDockState, $sPreviousDockState, $bNeedsFastPoll)",
        ):
            if required not in keep_body:
                errors.append(f"persistent docking no longer revalidates and follows window geometry via {required}")

        adaptive_delay = launcher_source.split("Func _AdaptiveDockPollDelay(", 1)
        adaptive_delay_body = adaptive_delay[1].split("EndFunc", 1)[0] if len(adaptive_delay) > 1 else ""
        for required in (
            "Global Const $g_iDockTransitionPollMs = 1000",
            "Global Const $g_iDockStablePollMs = 5000",
            "$bStateChanged = $sState <> $sPreviousState",
            "If $bNeedsFastPoll Or $bStateChanged Then Return $g_iDockTransitionPollMs",
            "Return $g_iDockStablePollMs",
        ):
            target = launcher_source if required.startswith("Global Const") else adaptive_delay_body
            if required not in target:
                errors.append(f"launcher adaptive docking backoff is no longer bounded via {required}")

        controller_match = launcher_source.split("Func _ControllerWindowMatches(", 1)
        controller_match_body = controller_match[1].split("EndFunc", 1)[0] if len(controller_match) > 1 else ""
        for required in ("WinGetTitle($hWindow)", "WinGetProcess($hWindow)", "_ProcessImagePath($iPid)", "$g_sControllerPath"):
            if required not in controller_match_body:
                errors.append(f"launcher no longer re-proves the Mini controller identity via {required}")

        startup_timeout = launcher_entry.split("$hController = _WaitForControllerWindow($iControllerPid, 60000)", 1)
        startup_timeout_body = startup_timeout[1] if len(startup_timeout) > 1 else ""
        for required in (
            '_EngineSupervisorDisarm("controller window readiness timed out;',
            "controller stack left intact for recovery",
            "Do not press Start. Run My Bot 2.0 Recovery",
        ):
            if required not in startup_timeout_body:
                errors.append(f"launcher readiness timeout no longer preserves the descendant stack and fails visibly via {required}")
        if "ProcessClose(" in startup_timeout_body:
            errors.append("launcher readiness timeout can partially close the controller stack instead of requiring exact recovery")

        recovery_log = launcher_source.split("Func _RecoveryLog(", 1)
        recovery_log_body = recovery_log[1].split("EndFunc", 1)[0] if len(recovery_log) > 1 else ""
        if "DirCreate($g_sUserDataRoot)" not in recovery_log_body:
            errors.append("launcher recovery logging no longer creates its per-user parent directory")

        controller_instance = launcher_source.split("Func _ControllerBlueStacksTitle($hController)", 1)
        controller_instance_body = controller_instance[1].split("EndFunc", 1)[0] if len(controller_instance) > 1 else ""
        for required in (
            "WinGetTitle($hController)",
            '"^My Bot 2\\.0 Mini v2\\.0\\.0 \\(([A-Za-z0-9_. -]{1,64})\\)$"',
            'Return "BlueStacks5-" & $aMatch[0]',
        ):
            if required not in controller_instance_body:
                errors.append(f"launcher no longer derives the exact BlueStacks instance from the claimed controller via {required}")
        if 'BlueStacks5-Pie64' in launcher_source:
            errors.append("launcher docking is hard-coded to Pie64 instead of following the controller-bound instance")

        blue_stacks = launcher_source.split("Func _FindBlueStacksWindow($hController)", 1)
        blue_stacks_body = blue_stacks[1].split("EndFunc", 1)[0] if len(blue_stacks) > 1 else ""
        for required in ("_ControllerBlueStacksTitle($hController)", "$sBlueStacksTitle", '"^Qt[0-9]+QWindowIcon$"', '"\\\\hd-player\\.exe$"'):
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
        for required in (
            "RunEventLogBindSession",
            "RunEventLogReleaseSession",
            "$g_iRunEventSequence = 0",
            "Global $g_hRunEventClock = TimerInit()",
            "$g_hRunEventClock = TimerInit()",
            "TimerDiff($g_hRunEventClock)",
        ):
            if required not in log_source:
                errors.append(f"Activity events are no longer bounded to one canonical run session by {required}")
        bind_body = log_source.split("Func RunEventLogBindSession", 1)
        bind_body = bind_body[1].split("EndFunc", 1)[0] if len(bind_body) > 1 else ""
        sequence_reset = bind_body.find("$g_iRunEventSequence = 0")
        clock_reset = bind_body.find("$g_hRunEventClock = TimerInit()")
        if sequence_reset < 0 or clock_reset < sequence_reset:
            errors.append("binding a planned run no longer resets its event timestamp origin with its sequence")
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
        stop_transition = complete_body.find("RunSessionRequestStop(")
        stopping_event = complete_body.find("RunEventLogRunStopping(")
        session_complete = complete_body.find("RunSessionComplete(")
        completed_event = complete_body.find("RunEventLogRunCompleted(")
        completed_release = complete_body.find("RunEventLogReleaseSession($sCompletedSessionId)")
        session_reset = complete_body.find("$g_oRunExecutionSession = 0")
        intent_reset = complete_body.find("$g_oRunExecutionIntent = 0")
        prepared_reset = complete_body.find("$g_bRunExecutionPrepared = False")
        active_reset = complete_body.find("$g_bRunExecutionActive = False")
        pacing_reset = complete_body.find("RunPacingDeactivate()")
        if min(stop_transition, stopping_event, session_complete, completed_event, completed_release) < 0 or not (
            stop_transition < stopping_event < session_complete < completed_event < completed_release
        ):
            errors.append("manual planned-run Stop no longer transitions and emits stopping/completed before releasing the Activity session")
        if "$bIntentReady = IsObj($g_oRunExecutionIntent)" not in complete_body or "If $bSessionCompleted And $bIntentReady Then" not in complete_body:
            errors.append("planned-run completion can dereference a missing intent or publish completion after a failed state transition")
        if min(session_reset, intent_reset, prepared_reset, active_reset, pacing_reset) < completed_release:
            errors.append("completed planned runs keep a stale session or intent in idle Control Center status")
        cancel_session_reset = cancel_body.find("$g_oRunExecutionSession = 0")
        cancel_intent_reset = cancel_body.find("$g_oRunExecutionIntent = 0")
        if cancel_session_reset < 0 or cancel_intent_reset < 0:
            errors.append("cancelled prepared runs keep a stale session or intent in idle Control Center status")
        validator_block = event_source.split('Switch $oEvent.Item("type")', 1)[-1].split("EndSwitch", 1)[0]
        case_lines = "\n".join(re.findall(r"^\s*Case\s+(.+)$", validator_block, re.MULTILINE))
        accepted_types = set(re.findall(r'"([a-z]+(?:[._-][a-z]+)*)"', case_lines))
        emitted_types = set(re.findall(r'RunEventLogWrite\("([a-z]+(?:[._-][a-z]+)*)"', log_source))
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

    execution_source = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8-sig")
    contract_source = (ROOT / "COCBot/functions/Run/RunExecutionContract.au3").read_text(encoding="utf-8-sig")
    for required in (
        "Func RunExecutionHeroWaitMask(",
        "If Not $bWaitForFullArmy Or Not $bManageTraining Then Return 0",
    ):
        if required not in contract_source:
            errors.append(f"Hero deployment/readiness separation lost contract invariant: {required}")
    for required in (
        "RunExecutionHeroWaitMask($iHeroMask, $bWaitForFull, $g_bRunExecutionManageTraining)",
        "$g_aiAttackUseHeroes[$iMode] = $iHeroMask",
        "$g_aiSearchHeroWaitEnable[$iMode] = $iHeroWaitMask",
    ):
        if required not in execution_source:
            errors.append(f"selected Heroes are not independently bound for deploy/readiness: {required}")

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
    send_control = planner_js.split("async function sendControl(action)", 1)
    send_control_body = send_control[1].split("async function pollEvents()", 1)[0] if len(send_control) > 1 else ""
    if "savePlan()" in send_control_body:
        errors.append("browser Start silently saves an unapplied draft instead of requiring Apply plan")
    for required in ("allSettings().some(isUnsaved)", "!PLAN_WRITTEN", "Apply the visible plan before Start"):
        if required not in send_control_body:
            errors.append(f"browser Start lost its explicit Apply-plan gate via {required}")

    bluestacks_source = (ROOT / "COCBot/functions/Android/AndroidBluestacks5.au3").read_text(encoding="utf-8-sig")
    if "bstk/su root" in bluestacks_source:
        errors.append("BlueStacks 5 still invokes the obsolete bstk/su root shell wrapper")
    if 'bst.enable_adb_access="1"' not in bluestacks_source:
        errors.append("BlueStacks 5 setup does not enable its required non-root ADB access setting")
    android_source = (ROOT / "COCBot/functions/Android/Android.au3").read_text(encoding="utf-8-sig")
    open_android = android_source.split("Func _OpenAndroid(", 1)
    open_android_body = open_android[1].split("EndFunc", 1)[0] if len(open_android) > 1 else ""
    guarded_open_zoom = "If Not RunExecutionSkipVillageZoomCalibration() Then ZoomOut()"
    if open_android_body.count(guarded_open_zoom) != 2 or re.search(r"(?m)^\s*ZoomOut\(\)\s*$", open_android_body):
        errors.append("opening or recovering Android can still run legacy village zoom calibration in current-army mode")
    handle_body = android_source.split("Func _WinGetAndroidHandle", 1)[-1].split("EndFunc", 1)[0]
    fallback_offset = handle_body.find("FindBlueStacks5WindowFallback()")
    legacy_title_offset = handle_body.find("If $bFindByTitle = True Then")
    if fallback_offset < 0 or legacy_title_offset < 0 or fallback_offset > legacy_title_offset:
        errors.append("modern BlueStacks discovery no longer precedes the legacy title path's early return")
    surface_body = bluestacks_source.split("Func GetBlueStacks5ModernAdbSurfacePosition()", 1)
    surface_body = surface_body[1].split("EndFunc", 1)[0] if len(surface_body) > 1 else ""
    for required in (
        "_WinAPI_EnumWindows(False)",
        "_BlueStacks5ConfiguredAdbOwnerPid()",
        "_BlueStacks5ModernWindowMatchesInstance($hWindow, $iAdbOwnerPid)",
        'StringCompare($sTitle, "BlueStacks5-" & $g_sAndroidInstance, 0)',
        '$sTitle = ""',
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
        "_BlueStacks5ModernWindowMatchesInstance($hWindow, _BlueStacks5ConfiguredAdbOwnerPid())",
        "$g_iAndroidClientWidth",
        "$g_iAndroidClientHeight",
    ):
        if required not in surface_body:
            errors.append(f"modern BlueStacks framebuffer geometry is no longer guarded by {required}")
    check_screen_body = bluestacks_source.split("Func CheckScreenBlueStacks5(", 1)
    check_screen_body = check_screen_body[1].split("EndFunc", 1)[0] if len(check_screen_body) > 1 else ""
    for required in (
        "IsArray(GetBlueStacks5ModernAdbSurfacePosition())",
        "$abSettingFound[3] = True",
        "If $bModernAdbSurface And $iSearch = 3 Then ContinueLoop",
        "fb_width",
        "fb_height",
        "dpi",
        "display_name",
        "bst.enable_adb_access",
    ):
        if required not in check_screen_body:
            errors.append(f"modern BlueStacks screen validation lost required contract: {required}")
    position_source = (ROOT / "COCBot/functions/Android/getBSPos.au3").read_text(encoding="utf-8-sig")
    position_body = position_source.split("Func getAndroidPos(", 1)[-1].split("EndFunc", 1)[0]
    surface_offset = position_body.find("GetBlueStacks5ModernAdbSurfacePosition()")
    control_offset = position_body.find("ControlGetPos(")
    if surface_offset < 0 or control_offset < 0 or surface_offset > control_offset:
        errors.append("modern BlueStacks ADB geometry no longer bypasses generic shell resizing")

    viewport_body = bluestacks_source.split("Func GetBlueStacks5ModernManualViewportPosition(", 1)
    viewport_body = viewport_body[1].split("EndFunc", 1)[0] if len(viewport_body) > 1 else ""
    mapping_source = (ROOT / "COCBot/functions/Other/ManualViewportMapping.au3").read_text(encoding="utf-8-sig")
    discovery_body = mapping_source.split("Func ManualViewportFindBlueStacks5Surface(", 1)
    discovery_body = discovery_body[1].split("EndFunc", 1)[0] if len(discovery_body) > 1 else ""
    if "ManualViewportFindBlueStacks5Surface(" not in viewport_body:
        errors.append("modern BlueStacks manual viewport no longer delegates to exact child-surface discovery")
    for required in (
        "_WinAPI_EnumChildWindows($hWindow, False)",
        'StringCompare(_WinAPI_GetClassName($hChild), "BlueStacksApp", 0)',
        "WinGetProcess($hChild) <> $iRootPid",
        "BitAND(WinGetState($hChild), 2) = 0",
        "Abs(($aCandidate[2] / $aCandidate[3]) - $fExpectedRatio) > 0.01",
        "If $iFound <> 1 Then",
    ):
        if required not in discovery_body:
            errors.append(f"modern BlueStacks manual viewport lost required proof: {required}")
    find_pos_source = (ROOT / "COCBot/functions/Other/FindPos.au3").read_text(encoding="utf-8-sig")
    find_pos_body = find_pos_source.split("Func FindPos(", 1)
    find_pos_body = find_pos_body[1].split("EndFunc", 1)[0] if len(find_pos_body) > 1 else ""
    mapping_body = mapping_source.split("Func ManualViewportMapToFramebuffer(", 1)
    mapping_body = mapping_body[1].split("EndFunc", 1)[0] if len(mapping_body) > 1 else ""
    for required in (
        "$iViewportX < 0 Or $iViewportY < 0",
        "$iViewportX >= $aViewport[2]",
        "(($iViewportX + 0.5) * $iFramebufferWidth) / $aViewport[2]",
        "(($iViewportY + 0.5) * $iFramebufferHeight) / $aViewport[3]",
    ):
        if required not in mapping_body:
            errors.append(f"modern BlueStacks manual click mapping lost required contract: {required}")
    mapping_offset = find_pos_body.find("ManualViewportMapToFramebuffer(")
    village_offset = find_pos_body.find("ConvertFromVillagePos($Pos[0], $Pos[1])")
    if mapping_offset < 0 or village_offset < 0 or mapping_offset > village_offset:
        errors.append("manual BlueStacks viewport mapping no longer precedes village-coordinate conversion")

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
