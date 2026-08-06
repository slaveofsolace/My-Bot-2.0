#!/usr/bin/env python3
"""Verify current-client adapter and orchestration integration."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "COCBot/functions/Other/CurrentClientCompat.au3",
    "COCBot/functions/Android/AndroidLDPlayer9.au3",
    "COCBot/functions/Android/AndroidMumu.au3",
    "COCBot/functions/Run/RunPlan.au3",
    "COCBot/functions/Run/AccountQueue.au3",
    "config/current-client-capabilities.json",
    "config/run-plan.schema.json",
    "config/account-queue.schema.json",
    "tests/fixtures/current-client/manifest.json",
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

    api = text("COCBot/functions/Other/Api.au3")
    require(api.count('#include "CurrentClientCompat.au3"') == 1, "compatibility entry point is included exactly once", findings)

    gui = text("COCBot/GUI/MBR GUI Control Android.au3")
    require("Current client emulator adapters" in gui, "emulator discovery is integrated", findings)
    require("Current client emulator instance roots" in gui, "emulator instance discovery is integrated", findings)

    android = text("COCBot/functions/Android/Android.au3")
    require("Current client emulator ADB paths" in android, "generic ADB resolution includes new adapters", findings)

    ldplayer = text("COCBot/functions/Android/AndroidLDPlayer9.au3")
    require("5554 + (2 * _LDPlayer9InstanceIndex())" in ldplayer, "LDPlayer multi-instance ADB port formula is correct", findings)
    require("$g_iGAME_WIDTH" in ldplayer and "$g_iGAME_HEIGHT" in ldplayer, "LDPlayer resolution follows the engine dimensions", findings)

    mumu = text("COCBot/functions/Android/AndroidMumu.au3")
    require("ADB_PORT_EX" in mumu, "MuMu ADB endpoint is read from instance configuration", findings)
    require("$g_iGAME_WIDTH" in mumu and "$g_iGAME_HEIGHT" in mumu, "MuMu resolution follows the engine dimensions", findings)

    run_plan = text("COCBot/functions/Run/RunPlan.au3")
    require("ByRef $sError = Default" not in run_plan, "run-plan validation uses an explicit error output", findings)
    queue = text("COCBot/functions/Run/AccountQueue.au3")
    require("Credentials" not in queue and "password" not in queue.lower(), "account queue contains no credential fields", findings)

    for autoit_path in REQUIRED_FILES[:5]:
        verify_autoit_balance(autoit_path, findings)

    capabilities = json.loads(text("config/current-client-capabilities.json"))
    require(capabilities.get("as_of") == "2026-08-06", "capability catalog has a fixed audit date", findings)
    capability_ids = {item["id"] for item in capabilities["capabilities"]}
    for capability_id in {
        "emulator.ldplayer9",
        "emulator.mumu",
        "orchestration.run-plan",
        "orchestration.account-queue",
        "battle.regular-ranked-split",
        "village.town-hall-18",
        "heroes.six-slot-layout",
    }:
        require(capability_id in capability_ids, f"capability catalog contains {capability_id}", findings)

    run_schema = json.loads(text("config/run-plan.schema.json"))
    required_run_fields = set(run_schema["required"])
    require(
        {
            "schema_version",
            "mode",
            "strategy",
            "duration_minutes",
            "max_battles",
            "stop_on_star_bonus",
            "max_failures",
            "upgrade_policy",
        }.issubset(required_run_fields),
        "run-plan schema covers the engine contract",
        findings,
    )
    account_schema = json.loads(text("config/account-queue.schema.json"))
    serialized = json.dumps(account_schema).lower()
    require("password" not in serialized and "token" not in serialized, "account schema excludes credentials and tokens", findings)

    fixture_manifest = json.loads(text("tests/fixtures/current-client/manifest.json"))
    require(len(fixture_manifest["required_fixtures"]) >= 10, "current-client fixture inventory is populated", findings)

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
