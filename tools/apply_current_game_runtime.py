#!/usr/bin/env python3
"""Generate and wire the sourced current-game runtime layer.

The transformation is exact and idempotent. It edits only the compatibility
entry point and the Windows AutoIt test list; the generated descriptor table is
produced separately by generate_game_catalog_autoit.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
COMPAT_PATH = ROOT / "COCBot/functions/Other/CurrentClientCompat.au3"
AUTOIT_TEST_PATH = ROOT / "tools/Test-AutoIt.ps1"


class PatchError(RuntimeError):
    pass


def insert_once(content: str, anchor: str, insertion: str, marker: str) -> str:
    if marker in content:
        return content
    count = content.count(anchor)
    if count != 1:
        raise PatchError(f"expected one anchor for {marker!r}, found {count}")
    return content.replace(anchor, anchor + insertion, 1)


def replace_once(content: str, old: str, new: str, marker: str) -> str:
    if marker in content:
        return content
    count = content.count(old)
    if count != 1:
        raise PatchError(f"expected one replacement anchor for {marker!r}, found {count}")
    return content.replace(old, new, 1)


def patch_compatibility(content: str) -> str:
    content = insert_once(
        content,
        '#include "..\\Run\\RunEvent.au3"',
        '\n#include "..\\Game\\GameCatalog.au3"\n#include "..\\Game\\ScreenStateRegistry.au3"',
        '#include "..\\Game\\GameCatalog.au3"',
    )

    debug_anchor = '\tSetDebugLog("Current client adapters registered: LDPlayer9=" & $__LDPlayer9_Idx & ", MuMu=" & $__Mumu_Idx)'
    startup_block = (
        '\tLocal $sCatalogError\n'
        '\tIf Not CurrentGameCatalogValidate($sCatalogError) Then\n'
        '\t\tSetLog("Current game catalog validation failed: " & $sCatalogError, $COLOR_ERROR)\n'
        '\tElse\n'
        '\t\tSetDebugLog("Current game catalog loaded: TH" & $CURRENT_GAME_MAX_TOWN_HALL & ", Heroes=" & $CURRENT_GAME_HOME_HERO_COUNT)\n'
        '\tEndIf\n'
    )
    if "Current game catalog loaded:" not in content:
        count = content.count(debug_anchor)
        if count != 1:
            raise PatchError(f"expected one adapter debug anchor, found {count}")
        content = content.replace(debug_anchor, startup_block + debug_anchor, 1)

    reference_marker = '\tCurrentGameCatalogValidate($sCatalogError)'
    if reference_marker not in content:
        end_anchor = 'EndFunc   ;==>ReferenceCurrentClientCompat'
        reference_block = (
            '\tLocal $sCatalogError\n'
            '\tCurrentGameCatalogValidate($sCatalogError)\n'
            '\tCurrentGameGetHeroUnlockTH("dragon-duke")\n'
            '\tLocal $sBudgetKind, $iBudgetValue, $sBudgetUnit\n'
            '\tCurrentGameGetBattleAttackBudget("legend-i", $sBudgetKind, $iBudgetValue, $sBudgetUnit)\n'
            '\tLocal $sGameReason\n'
            '\tCurrentGameBattleSurfaceReady("ranked", $sGameReason)\n'
            '\tCurrentGameScreenCanHandle("heroes.journey", $sGameReason)\n'
            '\tCurrentGameScreenDefaultAction("chat.global.open")\n'
        )
        count = content.count(end_anchor)
        if count != 1:
            raise PatchError(f"expected one compatibility reference end marker, found {count}")
        content = content.replace(end_anchor, reference_block + end_anchor, 1)
    return content


def patch_autoit_test_list(content: str) -> str:
    if '"tests\\autoit\\GameCatalogTest.au3"' in content:
        return content

    candidates = (
        (
            '    "tests\\autoit\\RunContractsTest.au3"\n)',
            '    "tests\\autoit\\RunContractsTest.au3",\n    "tests\\autoit\\GameCatalogTest.au3"\n)',
        ),
        (
            '    "tests\\autoit\\RunContractsTest.au3"\r\n)',
            '    "tests\\autoit\\RunContractsTest.au3",\r\n    "tests\\autoit\\GameCatalogTest.au3"\r\n)',
        ),
    )
    for old, new in candidates:
        if old in content:
            return content.replace(old, new, 1)
    raise PatchError("RunContractsTest.au3 was not found in the AutoIt contract-test list")


def transform(path: Path, patcher: Callable[[str], str]) -> tuple[str, str]:
    original = path.read_text(encoding="utf-8-sig")
    updated = patcher(original)
    return original, updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    operations = [
        (COMPAT_PATH, patch_compatibility, "current-client compatibility entry point"),
        (AUTOIT_TEST_PATH, patch_autoit_test_list, "Windows AutoIt test list"),
    ]
    report: list[dict[str, str]] = []
    pending = False

    for path, patcher, label in operations:
        original, updated = transform(path, patcher)
        changed = original != updated
        pending = pending or changed
        report.append(
            {
                "path": str(path.relative_to(ROOT)),
                "label": label,
                "status": "pending" if changed else "current",
            }
        )
        if changed and not args.check:
            path.write_text(updated, encoding="utf-8", newline="\n")
            report[-1]["status"] = "applied"

    payload = {"schema_version": 1, "changes_pending": pending, "files": report}
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")

    if args.check and pending:
        raise SystemExit("current-game runtime integration is not applied")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PatchError as exc:
        raise SystemExit(f"current-game runtime patch failed: {exc}") from exc
