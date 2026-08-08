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

    # The parser and the tab have to agree on how a list is delimited, since one writes it and the other splits it.
    if 'RUN_PLAN_FILE_LIST_SEPARATOR = "|"' not in parser_source:
        errors.append("the plan file list separator is no longer a pipe; the Hero list would not split")
    if "$RUN_PLAN_FILE_LIST_SEPARATOR" not in applier_source:
        errors.append("the tab splits Hero lists on something other than the parser's separator")

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
