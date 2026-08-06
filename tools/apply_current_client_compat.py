#!/usr/bin/env python3
"""Apply the first current-client compatibility integration slice.

The script is deliberately idempotent. It patches only exact, reviewed anchors and
fails before writing when an expected legacy structure has changed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class PatchError(RuntimeError):
    """Raised when a reviewed source anchor can no longer be located."""


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def write_text(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.write_text(content, encoding="utf-8", newline="\n")


def insert_after_once(
    relative_path: str,
    anchor: str,
    insertion: str,
    marker: str,
    report: list[dict[str, Any]],
) -> None:
    content = read_text(relative_path)
    if marker in content:
        report.append({"path": relative_path, "change": marker, "status": "already-applied"})
        return
    count = content.count(anchor)
    if count != 1:
        raise PatchError(f"{relative_path}: expected one anchor for {marker!r}, found {count}")
    content = content.replace(anchor, anchor + insertion, 1)
    write_text(relative_path, content)
    report.append({"path": relative_path, "change": marker, "status": "applied"})


def replace_once(
    relative_path: str,
    old: str,
    new: str,
    marker: str,
    report: list[dict[str, Any]],
) -> None:
    content = read_text(relative_path)
    if new in content:
        report.append({"path": relative_path, "change": marker, "status": "already-applied"})
        return
    count = content.count(old)
    if count != 1:
        raise PatchError(f"{relative_path}: expected one replacement anchor for {marker!r}, found {count}")
    write_text(relative_path, content.replace(old, new, 1))
    report.append({"path": relative_path, "change": marker, "status": "applied"})


def patch_api_include(report: list[dict[str, Any]]) -> None:
    path = "COCBot/functions/Other/Api.au3"
    marker = '#include "CurrentClientCompat.au3"'
    content = read_text(path)
    if marker in content:
        report.append({"path": path, "change": "compatibility include", "status": "already-applied"})
        return
    block = (
        "\n\n; Current client adapters and run orchestration\n"
        '#include "CurrentClientCompat.au3"\n'
    )
    write_text(path, content.rstrip() + block)
    report.append({"path": path, "change": "compatibility include", "status": "applied"})


def patch_run_plan_signature(report: list[dict[str, Any]]) -> None:
    replace_once(
        "COCBot/functions/Run/RunPlan.au3",
        'Func RunPlanValidate(ByRef $oPlan, ByRef $sError = Default)\n\tIf $sError = Default Then Local $sError = ""\n',
        'Func RunPlanValidate(ByRef $oPlan, ByRef $sError)\n',
        "explicit validation error output",
        report,
    )
    replace_once(
        "COCBot/functions/Other/CurrentClientCompat.au3",
        'Local $oPlan = RunPlanCreateDefault()\n\tRunPlanValidate($oPlan)\n',
        'Local $oPlan = RunPlanCreateDefault(), $sPlanError\n\tRunPlanValidate($oPlan, $sPlanError)\n',
        "run-plan reference arguments",
        report,
    )


def patch_emulator_discovery(report: list[dict[str, Any]]) -> None:
    path = "COCBot/GUI/MBR GUI Control Android.au3"
    insert_after_once(
        path,
        '\tIf FileExists($MEmuEmulator) Then $sEmulatorString &= "MEmu|"',
        (
            "\n\n\t; Current client emulator adapters\n"
            '\tLocal $sLDPlayer9Version = RegRead($g_sHKLM & "\\SOFTWARE" & $g_sWow6432Node & "\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LDPlayer9\\", "DisplayVersion")\n'
            "\tLocal $iLDPlayer9RegError = @error\n"
            '\tIf $iLDPlayer9RegError = 0 And GetVersionNormalized($sLDPlayer9Version) >= GetVersionNormalized("9.0") Then $sEmulatorString &= "LDPlayer9|"\n\n'
            '\tLocal $sMumuVersion = RegRead($g_sHKLM & "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MuMuPlayerGlobal\\", "DisplayVersion")\n'
            "\tLocal $iMumuRegError = @error\n"
            '\tIf $iMumuRegError <> 0 Then\n'
            '\t\t$sMumuVersion = RegRead($g_sHKLM & "\\SOFTWARE" & $g_sWow6432Node & "\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MuMuPlayerGlobal\\", "DisplayVersion")\n'
            "\t\t$iMumuRegError = @error\n"
            "\tEndIf\n"
            '\tIf $iMumuRegError = 0 And GetVersionNormalized($sMumuVersion) >= GetVersionNormalized("5.0") Then $sEmulatorString &= "MuMu|"'
        ),
        "Current client emulator adapters",
        report,
    )
    insert_after_once(
        path,
        '\t\t\tIf StringInStr($aEmulator[$i], "nox") Then $emuVer = $__Nox_Version',
        (
            "\n\t\t\t; Current client emulator versions\n"
            '\t\t\tIf StringInStr($aEmulator[$i], "LDPlayer9") Then $emuVer = $sLDPlayer9Version\n'
            '\t\t\tIf StringInStr($aEmulator[$i], "MuMu") Then $emuVer = $sMumuVersion'
        ),
        "Current client emulator versions",
        report,
    )
    insert_after_once(
        path,
        '\t\tCase "MEmu"\n\t\t\t$sEmulatorPath = GetMEmuPath() & "\\MemuHyperv VMs"',
        (
            "\n\t\t; Current client emulator instance roots\n"
            '\t\tCase "LDPlayer9"\n'
            '\t\t\tLocal $sLDPlayerPath = RegRead($g_sHKLM & "\\SOFTWARE\\XuanZhi\\LDPlayer9\\", "InstallDir")\n'
            '\t\t\t$sEmulatorPath = $sLDPlayerPath & "vms\\"\n'
            '\t\tCase "MuMu"\n'
            '\t\t\tLocal $sMumuUninstall = RegRead($g_sHKLM & "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MuMuPlayerGlobal\\", "UninstallString")\n'
            '\t\t\tIf @error Then $sMumuUninstall = RegRead($g_sHKLM & "\\SOFTWARE" & $g_sWow6432Node & "\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MuMuPlayerGlobal\\", "UninstallString")\n'
            '\t\t\t$sEmulatorPath = StringReplace(StringReplace($sMumuUninstall, "uninstall.exe", "vms"), Chr(34), "")'
        ),
        "Current client emulator instance roots",
        report,
    )


def patch_adb_resolver(report: list[dict[str, Any]]) -> None:
    path = "COCBot/functions/Android/Android.au3"
    insert_after_once(
        path,
        '\t\tCase "Nox"\n\t\t\t$sAdbPath = GetNoxAdbPath()',
        (
            "\n\t\t; Current client emulator ADB paths\n"
            '\t\tCase "LDPlayer9"\n'
            "\t\t\t$sAdbPath = GetLDPlayer9AdbPath()\n"
            '\t\tCase "MuMu"\n'
            "\t\t\t$sAdbPath = GetMumuAdbPath()"
        ),
        "Current client emulator ADB paths",
        report,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    report: list[dict[str, Any]] = []
    patch_run_plan_signature(report)
    patch_api_include(report)
    patch_emulator_discovery(report)
    patch_adb_resolver(report)

    payload = {
        "schema_version": 1,
        "changes": report,
        "applied": sum(item["status"] == "applied" for item in report),
        "already_applied": sum(item["status"] == "already-applied" for item in report),
        "reviewed_not_ported": [
            {
                "upstream_commit": "a477cbaf50ac8247da935a921f6de0dd5ca9a5e7",
                "reason": "v8.2.0 already uses a newer Treasure Hunt interruption path; the older PlacedOnLeague flow is absent",
            },
            {
                "upstream_commit": "84c9115021f0b2c55d38a351086466ec61afa3dd",
                "reason": "v8.2.0 uses GetIconPosition for Builder Base suggestions; the older FindUpgradeBB resource-icon branch is absent",
            },
        ],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PatchError as exc:
        raise SystemExit(f"compatibility patch failed: {exc}") from exc
