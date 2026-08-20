#!/usr/bin/env python3
"""Verify current-client adapter, orchestration, diagnostics, and evidence integration."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

AUTOIT_CONTRACT_FILES = [
    "COCBot/functions/Other/CurrentClientCompat.au3",
    "COCBot/functions/Android/AndroidBluestacks5.au3",
    "COCBot/functions/Android/AndroidMEmu.au3",
    "COCBot/functions/Android/AndroidLDPlayer9.au3",
    "COCBot/functions/Android/AndroidMumu.au3",
    "COCBot/functions/Android/ZoomOut.au3",
    "COCBot/functions/Main Screen/checkObstacles.au3",
    "COCBot/functions/Village/GetVillageSize.au3",
    "COCBot/functions/Run/RunPlan.au3",
    "COCBot/functions/Run/AccountQueue.au3",
    "COCBot/functions/Run/BattleRoute.au3",
    "COCBot/functions/Run/RunSession.au3",
    "COCBot/functions/Run/RunEvent.au3",
]

REQUIRED_FILES = AUTOIT_CONTRACT_FILES + [
    "config/current-client-capabilities.json",
    "config/run-plan.schema.json",
    "config/account-queue.schema.json",
    "config/battle-route.schema.json",
    "config/run-session.schema.json",
    "config/run-event.schema.json",
    "config/runtime-evidence.schema.json",
    "config/ui/settings.schema.json",
    "config/ui/run-planner.settings.json",
    "tests/autoit/RunContractsTest.au3",
    "tests/python/test_runtime_evidence.py",
    "tests/python/test_capture_check_engine_evidence.py",
    "tests/fixtures/current-client/manifest.json",
    "tests/evidence/runtime/README.md",
    "tools/Test-AutoIt.ps1",
    "tools/validate_current_client_fixtures.py",
    "tools/validate_ui_metadata.py",
    "tools/validate_runtime_evidence.py",
    "tools/capture_check_engine_evidence.py",
    "tools/evaluate_support_readiness.py",
    ".github/workflows/windows-autoit.yml",
]


class VerificationError(RuntimeError):
    pass


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def require(condition: bool, message: str, findings: list[dict[str, Any]]) -> None:
    if not condition:
        raise VerificationError(message)
    findings.append({"check": message, "status": "passed"})


def verify_autoit_balance(path: str, findings: list[dict[str, Any]]) -> None:
    content = text(path)
    function_count = len(re.findall(r"(?im)^\s*Func\s+[A-Za-z_]\w*\s*\(", content))
    end_count = len(re.findall(r"(?im)^\s*EndFunc\b", content))
    require(function_count == end_count, f"{path}: Func/EndFunc balance ({function_count})", findings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    findings: list[dict[str, Any]] = []
    for relative in REQUIRED_FILES:
        require((ROOT / relative).is_file(), f"required file exists: {relative}", findings)

    # The entry point must be reachable from the main build and from nowhere else: the Mini GUI and Watchdog
    # builds omit the Android core, so pulling the adapters into them breaks Au3Check.
    main_entry = text("MyBot.run.au3")
    require(
        main_entry.count('#include "COCBot\\functions\\Other\\CurrentClientCompat.au3"') == 1,
        "main entry point includes the compatibility layer exactly once",
        findings,
    )
    api = text("COCBot/functions/Other/Api.au3")
    require(
        "CurrentClientCompat.au3" not in api,
        "shared Api.au3 does not pull the Android adapters into smaller builds",
        findings,
    )

    compatibility = text("COCBot/functions/Other/CurrentClientCompat.au3")
    for include_name in ("BattleRoute.au3", "RunSession.au3", "RunEvent.au3"):
        require(include_name in compatibility, f"compatibility entry point includes {include_name}", findings)

    gui = text("COCBot/GUI/MBR GUI Control Android.au3")
    require("Current client emulator adapters" in gui, "emulator discovery is integrated", findings)
    require("Current client emulator instance roots" in gui, "emulator instance discovery is integrated", findings)

    android = text("COCBot/functions/Android/Android.au3")
    require("Current client emulator ADB paths" in android, "generic ADB resolution includes new adapters", findings)

    obstacles = text("COCBot/functions/Main Screen/checkObstacles.au3")
    safe_reload = re.search(
        r'If \$g_sAndroidEmulator = "BlueStacks5" And \(\$i = 0 Or \$i = 1\) Then\s+'
        r'SetLog\("BlueStacks5 reload screen detected; restarting Clash of Clans safely", \$COLOR_INFO\)\s+'
        r'Return checkObstacles_ReloadCoC\(\$bRecursive\)\s+'
        r'EndIf',
        obstacles,
    )
    require(
        safe_reload is not None and obstacles.index("BlueStacks5 reload screen detected") < obstacles.index("PureClickP($aiButtonType[$Ref][0])"),
        "BlueStacks5 restarts only Clash of Clans before the unstable reload button path for obstacle types 0/1",
        findings,
    )

    village_size = text("COCBot/functions/Village/GetVillageSize.au3")
    require(
        "_VillageAnchorPromote($aStoneFiles, $g_aVillageSize[6])" in village_size
        and "_VillageAnchorPromote($aTreeFiles, $g_aVillageSize[9])" in village_size,
        "village measurement prioritizes the last proven exact anchors",
        findings,
    )
    for cache_guard in (
        'Number($g_aVillageSize[0]) > 0',
        '$g_aVillageSize[6] <> ""',
        '$g_aVillageSize[9] <> ""',
        "For $i = 1 To $aFiles[0]",
        "For $j = $i To 2 Step -1",
        "$aFiles[$j] = $aFiles[$j - 1]",
        "$aFiles[1] = $sMatch",
        "If Not $g_bRunState And Not $bMeasureOnly Then Return $aResult",
        "Return False",
    ):
        require(cache_guard in village_size, f"village anchor cache retains fail-safe guard: {cache_guard}", findings)

    zoom_out = text("COCBot/functions/Android/ZoomOut.au3")
    require(
        not re.search(r"(?<!_)TimerDiff\(\$hTimer\)", zoom_out),
        "zoom timing uses the matching high-resolution timer API",
        findings,
    )

    ldplayer = text("COCBot/functions/Android/AndroidLDPlayer9.au3")
    require("5554 + (2 * _LDPlayer9InstanceIndex())" in ldplayer, "LDPlayer multi-instance ADB port formula is correct", findings)
    require("$g_iGAME_WIDTH" in ldplayer and "$g_iGAME_HEIGHT" in ldplayer, "LDPlayer resolution follows the engine dimensions", findings)

    mumu = text("COCBot/functions/Android/AndroidMumu.au3")
    require("ADB_PORT_EX" in mumu, "MuMu ADB endpoint is read from instance configuration", findings)
    require("$g_iGAME_WIDTH" in mumu and "$g_iGAME_HEIGHT" in mumu, "MuMu resolution follows the engine dimensions", findings)

    memu = text("COCBot/functions/Android/AndroidMEmu.au3")
    for contract in (
        "GetMEmuPath()",
        "GetMEmuAdbPath()",
        "GetAndroidVMinfo($__VBoxVMinfo, $MEmu_Manage_Path)",
        'StringRegExp($__VBoxVMinfo, "name = ADB.*host ip = ([^,]+),"',
        'StringRegExp($__VBoxVMinfo, "name = ADB.*host port = (\\d{3,5}),"',
        '$g_sAndroidAdbDevice = $g_sAndroidAdbDeviceHost & ":" & $g_sAndroidAdbDevicePort',
        "GetMEmuBackgroundMode()",
        "Name: graphics_render_mode",
    ):
        require(contract in memu, f"MEmu adapter retains current static contract: {contract}", findings)

    run_plan = text("COCBot/functions/Run/RunPlan.au3")
    require("ByRef $sError = Default" not in run_plan, "run-plan validation uses an explicit error output", findings)
    queue = text("COCBot/functions/Run/AccountQueue.au3")
    require("password" not in queue.lower() and "token" not in queue.lower(), "account queue contains no credential fields", findings)

    route = text("COCBot/functions/Run/BattleRoute.au3")
    require('Case "ranked"' in route and 'Case "legend"' in route, "ranked and legend routes remain distinct", findings)
    require('"recognition_ready", False' in route and '"execution_ready", False' in route, "battle routes default to closed readiness gates", findings)

    session = text("COCBot/functions/Run/RunSession.au3")
    require('Case "ready", "running", "stopping", "completed", "failed"' in session, "run-session states are explicitly bounded", findings)
    require("RunPlanShouldStop" in session, "run session delegates stop decisions to the run plan", findings)

    event = text("COCBot/functions/Run/RunEvent.au3")
    require("RunEventAppendJsonLine" in event and "RunEventToJson" in event, "run events support JSONL diagnostics", findings)
    lowered_event = event.lower()
    require("password" not in lowered_event and "token" not in lowered_event and "supercell_id" not in lowered_event, "run-event contract excludes sensitive fields", findings)

    for autoit_path in AUTOIT_CONTRACT_FILES:
        verify_autoit_balance(autoit_path, findings)

    capabilities = json.loads(text("config/current-client-capabilities.json"))
    require(capabilities.get("as_of") == "2026-08-20", "capability catalog has a fixed audit date", findings)
    capability_ids = {item["id"] for item in capabilities["capabilities"]}
    for capability_id in {
        "emulator.bluestacks5",
        "emulator.memu",
        "emulator.ldplayer9",
        "emulator.mumu",
        "orchestration.run-plan",
        "orchestration.account-queue",
        "orchestration.battle-route",
        "orchestration.run-session",
        "orchestration.run-event",
        "orchestration.engine-initialization",
        "battle.regular-ranked-split",
        "village.town-hall-18",
        "heroes.six-slot-layout",
        "village.collectors",
        "village.loot-cart",
        "village.treasury",
        "events.daily-reward",
        "village.donations",
        "village.clan-request",
        "army.training",
        "village.upgrades-home",
        "builder-base.upgrades",
        "builder-base.battles",
        "village.laboratory",
        "events.clan-games",
        "orchestration.multi-account",
        "runtime.recovery",
        "clan-capital.upgrades",
        "village.pets",
        "village.hero-equipment",
        "rewards.achievements",
        "rewards.personal-challenges",
        "village.obstacles",
        "clan-capital.forge",
        "village.helper-hut",
        "builder-base.star-laboratory",
        "builder-base.resources",
        "rewards.magic-items",
        "rewards.streak-star-bonus",
        "village.boosts",
        "heroes.upgrades",
        "builder-base.hero-upgrades",
        "battle.trophy-drop",
        "battle.smart-zap",
        "village.replay-share",
        "village.profile-report",
    }:
        require(capability_id in capability_ids, f"capability catalog contains {capability_id}", findings)

    require(all(item.get("runtime_evidence") == "required" for item in capabilities["capabilities"]), "every documented capability requires runtime evidence", findings)
    evidence_policy = capabilities.get("runtime_evidence_policy", {})
    require(
        set(evidence_policy.get("capabilities", {})) == capability_ids,
        "every documented capability has a runtime evidence policy",
        findings,
    )
    require(
        evidence_policy.get("require_commit_ancestor") is True
        and evidence_policy.get("require_binary_provenance") is True
        and evidence_policy.get("require_tracked_artifacts") is True,
        "runtime evidence policy fails closed on commit, binary, and artifact integrity",
        findings,
    )
    require(
        all(item.get("required_tests") for item in evidence_policy["capabilities"].values()),
        "every capability policy names required test types and checks",
        findings,
    )
    capabilities_by_id = {item["id"]: item for item in capabilities["capabilities"]}
    bluestacks_capability = capabilities_by_id["emulator.bluestacks5"]
    bluestacks_policy = evidence_policy["capabilities"]["emulator.bluestacks5"]
    require(
        bluestacks_capability.get("implementation") == "COCBot/functions/Android/AndroidBluestacks5.au3"
        and bluestacks_capability.get("status") == "adapter-added",
        "BlueStacks 5 capability points at the bounded native adapter",
        findings,
    )
    require(
        bluestacks_policy.get("environment_patterns", {}).get("emulator") == r"(?i)^bluestacks\s*5$"
        and bluestacks_policy.get("required_tests") == [
            {
                "test_type": "emulator-smoke",
                "required_checks": ["emulator.detected", "adb.connected", "game.ready"],
            }
        ],
        "BlueStacks 5 evidence requires exact emulator, ADB, and game readiness",
        findings,
    )
    memu_capability = capabilities_by_id["emulator.memu"]
    memu_policy = evidence_policy["capabilities"]["emulator.memu"]
    require(
        memu_capability.get("implementation") == "COCBot/functions/Android/AndroidMEmu.au3"
        and memu_capability.get("status") == "adapter-added",
        "MEmu capability points at the inherited bounded native adapter",
        findings,
    )
    require(
        memu_policy.get("environment_patterns", {}).get("emulator") == r"(?i)^memu(?:\s|$)"
        and memu_policy.get("required_tests") == [
            {
                "test_type": "emulator-smoke",
                "required_checks": ["emulator.detected", "instance.bound", "adb.connected", "background.capture", "game.ready"],
            }
        ],
        "MEmu evidence requires exact instance, ADB, background capture, and game readiness",
        findings,
    )
    require(
        all(capabilities_by_id[item].get("fixture_status") == "required" for item in ("model.current-game", "model.screen-state-registry")),
        "runtime game models require an explicit fixture mapping",
        findings,
    )

    run_schema = json.loads(text("config/run-plan.schema.json"))
    required_run_fields = set(run_schema["required"])
    require(
        {
            "schema_version", "mode", "strategy", "army_manage_training", "duration_minutes", "max_battles",
            "stop_on_star_bonus", "max_failures", "upgrade_policy",
        }.issubset(required_run_fields),
        "run-plan schema covers the engine contract",
        findings,
    )

    account_schema = json.loads(text("config/account-queue.schema.json"))
    serialized_account = json.dumps(account_schema).lower()
    require("password" not in serialized_account and "token" not in serialized_account, "account schema excludes credentials and tokens", findings)

    route_schema = json.loads(text("config/battle-route.schema.json"))
    require(set(route_schema["properties"]["mode"]["enum"]) == {"regular", "ranked", "legend", "builder"}, "battle-route schema keeps all battle surfaces distinct", findings)

    session_schema = json.loads(text("config/run-session.schema.json"))
    require(set(session_schema["properties"]["state"]["enum"]) == {"ready", "running", "stopping", "completed", "failed"}, "run-session schema matches the state machine", findings)
    require(
        {"verification_state", "verification_reason"} <= set(session_schema["required"])
        and {"verification_state", "verification_reason"} <= set(session_schema["properties"]),
        "run-session schema accepts every verification field emitted by RunSessionSnapshot",
        findings,
    )
    require(
        set(session_schema["properties"]["verification_state"]["enum"])
        == {"verified", "unverified-diagnostic"},
        "run-session schema preserves the verification-state latch",
        findings,
    )

    event_schema = json.loads(text("config/run-event.schema.json"))
    require("battle.completed" in event_schema["properties"]["type"]["enum"], "run-event schema includes completed battle events", findings)
    serialized_event = json.dumps(event_schema).lower()
    require("password" not in serialized_event and "token" not in serialized_event and "email" not in serialized_event, "run-event schema excludes sensitive fields", findings)

    evidence_schema = json.loads(text("config/runtime-evidence.schema.json"))
    require(evidence_schema["properties"]["redacted"].get("const") is True, "runtime evidence requires redaction", findings)
    require(evidence_schema["properties"]["commit_sha"]["pattern"] == "^[0-9a-f]{40}$", "runtime evidence is pinned to an exact commit", findings)
    require("instance_name" in evidence_schema["properties"]["environment"]["properties"], "runtime evidence supports named emulator instances", findings)
    require("binary" in evidence_schema["properties"] and "integrityArtifact" in evidence_schema["$defs"], "passed runtime evidence carries binary and artifact integrity", findings)

    evidence_validator = text("tools/validate_runtime_evidence.py")
    require(
        all(token in evidence_validator for token in ("_is_ancestor_of_head", "_verify_binary_at_commit", "_verify_repository_artifact", "evidence file must match committed HEAD contents")),
        "runtime evidence validator verifies commit ancestry, binary provenance, and committed evidence artifacts",
        findings,
    )
    readiness_evaluator = text("tools/evaluate_support_readiness.py")
    require(
        "validate_registry" in readiness_evaluator and "trusted_for_readiness" in readiness_evaluator,
        "support readiness imports validation and trusts only validated evidence",
        findings,
    )
    require("required fixture mapping missing" in readiness_evaluator, "support readiness fails closed when a required fixture mapping is absent", findings)

    fixture_manifest = json.loads(text("tests/fixtures/current-client/manifest.json"))
    require(len(fixture_manifest["required_fixtures"]) >= 10, "current-client fixture inventory is populated", findings)

    ui_metadata = json.loads(text("config/ui/run-planner.settings.json"))
    require(ui_metadata.get("surface") == "run-planner", "run-planner metadata identifies its surface", findings)

    windows_workflow = text(".github/workflows/windows-autoit.yml")
    require('"3.3.16.1"' in windows_workflow and '"3.3.18.0"' in windows_workflow, "Windows CI covers baseline and current AutoIt releases", findings)
    require("Get-AuthenticodeSignature" in windows_workflow, "Windows CI verifies the AutoIt executable signature", findings)

    ci_workflow = text(".github/workflows/ci.yml")
    for report_name in ("fixture-validation.json", "ui-metadata-validation.json", "runtime-evidence-validation.json", "support-readiness.json"):
        require(report_name in ci_workflow, f"CI retains {report_name}", findings)
    require("test_runtime_evidence.py" in ci_workflow or "tests/python" in ci_workflow, "CI runs the runtime evidence trust-contract tests", findings)

    payload = {"schema_version": 1, "checks": len(findings), "findings": findings}
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        raise SystemExit(f"current-client verification failed: {exc}") from exc
