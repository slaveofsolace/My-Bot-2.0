#!/usr/bin/env python3
"""Generate the fail-closed, non-duplicated My Bot full-system inventory.

Capabilities remain the canonical user-facing workflow count. Planner settings,
fixtures, binaries, control actions, infrastructure routes, and actuator owners
are facets of that system, not extra capabilities. The report deliberately
separates source-contract coverage from exact-current runtime proof.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from tools import build_release, evaluate_support_readiness, validate_actuator_registry
except ModuleNotFoundError:  # Direct execution from tools/.
    import build_release  # type: ignore[no-redef]
    import evaluate_support_readiness  # type: ignore[no-redef]
    import validate_actuator_registry  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
SETTINGS_PATH = ROOT / "config/ui/run-planner.settings.json"
FIXTURES_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
PLANNER_SERVER_PATH = ROOT / "tools/planner_ui.py"
TEST_ROOTS = (ROOT / "tests/python", ROOT / "tests/autoit")

INFRASTRUCTURE = (
    {
        "id": "package.localruntime",
        "source_owners": ["tools/build_release.py", "tools/Build-Release.ps1"],
        "runtime_check": "deterministic package set, hashes, provenance, and rights gate",
    },
    {
        "id": "installer.localruntime",
        "source_owners": ["tools/install_local_runtime.py", "tools/Install-LocalRuntime.ps1"],
        "runtime_check": "isolated install, rollback, registration, Profiles preservation, and uninstall",
    },
    {
        "id": "launcher.controller",
        "source_owners": ["My Bot 2.0.au3", "MyBot.run.MiniGui.au3"],
        "runtime_check": "exact process lineage, controller readiness, and clean exit",
    },
    {
        "id": "launcher.watchdog",
        "source_owners": ["MyBot.run.Watchdog.au3"],
        "runtime_check": "bounded owned-process hang detection and restart/recovery",
    },
    {
        "id": "control-center.web",
        "source_owners": ["tools/planner_ui.py", "ui/planner.html", "ui/planner.js", "ui/planner.css"],
        "runtime_check": "browser bridge, persistence, cancellation, responsive UI, and accessibility",
    },
    {
        "id": "control-center.native",
        "source_owners": [
            "COCBot/GUI/MBR GUI Control Run Planner.au3",
            "COCBot/functions/Run/RunControlBridge.au3",
        ],
        "runtime_check": "native planner, command ownership, truthful status, and cancellation",
    },
    {
        "id": "engine.adapter",
        "source_owners": ["COCBot/functions/Other/MBRFunc.au3", "MyBot.run.EngineProbe.au3"],
        "runtime_check": "supervised managed initialization and exact backend identity",
    },
    {
        "id": "diagnostics.events",
        "source_owners": [
            "COCBot/functions/Run/RunEvent.au3",
            "COCBot/functions/Run/RunEventLog.au3",
        ],
        "runtime_check": "correlated monotonic events, diagnostics, and failure receipts",
    },
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _test_files() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for root in TEST_ROOTS:
        for path in sorted(root.glob("**/*")):
            if not path.is_file() or path.suffix.lower() not in {".py", ".au3"}:
                continue
            for encoding in ("utf-8-sig", "cp1252"):
                try:
                    text = path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                continue
            result.append((path.relative_to(ROOT).as_posix(), text.casefold()))
    return result


def _test_references(test_files: list[tuple[str, str]], *needles: object) -> list[str]:
    values = [str(value).casefold() for value in needles if isinstance(value, str) and value.strip()]
    if not values:
        return []
    return [path for path, text in test_files if any(value in text for value in values)]


def _control_actions() -> list[str]:
    tree = ast.parse(PLANNER_SERVER_PATH.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "CONTROL_ACTIONS" for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, set) or not all(isinstance(item, str) for item in value):
            raise ValueError("CONTROL_ACTIONS must be a literal set of strings")
        return sorted(value)
    raise ValueError("CONTROL_ACTIONS was not found")


def _planner_settings(document: dict[str, Any], test_files: list[tuple[str, str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section in document.get("sections", []):
        if not isinstance(section, dict):
            continue
        for setting in section.get("settings", []):
            if not isinstance(setting, dict):
                continue
            setting_id = setting.get("id")
            if not isinstance(setting_id, str) or not setting_id:
                raise ValueError("planner setting id must be non-empty")
            if setting_id in seen:
                raise ValueError(f"duplicate planner setting: {setting_id}")
            seen.add(setting_id)
            result.append(
                {
                    "id": setting_id,
                    "section": section.get("id"),
                    "type": setting.get("type"),
                    "source_owner": "config/ui/run-planner.settings.json",
                    "automated_tests": _test_references(test_files, setting_id),
                    "source_contract": "PASS",
                    "runtime_status": "DEFERRED",
                }
            )
    return result


def build_report(root: Path = ROOT) -> dict[str, Any]:
    if root.resolve() != ROOT.resolve():
        raise ValueError("the inventory generator must run against its own repository root")
    capabilities_document = _load(CAPABILITIES_PATH)
    settings_document = _load(SETTINGS_PATH)
    fixtures_document = _load(FIXTURES_PATH)
    capabilities = capabilities_document.get("capabilities", [])
    fixtures = fixtures_document.get("required_fixtures", [])
    if not isinstance(capabilities, list) or not isinstance(fixtures, list):
        raise ValueError("capability and fixture inventories must be lists")

    capability_ids = [item.get("id") for item in capabilities if isinstance(item, dict)]
    if len(capability_ids) != len(capabilities) or any(not isinstance(item, str) or not item for item in capability_ids):
        raise ValueError("every capability requires a non-empty id")
    duplicates = sorted(item for item, count in Counter(capability_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate capabilities: {duplicates}")

    test_files = _test_files()
    readiness = evaluate_support_readiness.evaluate_readiness(root=ROOT)
    readiness_by_id = {row["id"]: row for row in readiness["results"]}
    fixture_by_capability: dict[str, list[dict[str, Any]]] = {item: [] for item in capability_ids}
    fixture_rows: list[dict[str, Any]] = []
    fixture_ids: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("id"), str):
            raise ValueError("every fixture requires an id")
        fixture_id = fixture["id"]
        if fixture_id in fixture_ids:
            raise ValueError(f"duplicate fixture: {fixture_id}")
        fixture_ids.add(fixture_id)
        mapped = fixture.get("capability_ids", [])
        if not isinstance(mapped, list) or any(item not in fixture_by_capability for item in mapped):
            raise ValueError(f"fixture {fixture_id} references an unknown capability")
        row = {
            "id": fixture_id,
            "status": fixture.get("status"),
            "capability_ids": mapped,
            "image_path": fixture.get("image_path"),
            "metadata_path": fixture.get("metadata_path"),
            "final_status": "PASS" if fixture.get("status") == "verified" else "DEFERRED",
        }
        fixture_rows.append(row)
        for capability_id in mapped:
            fixture_by_capability[capability_id].append(row)

    policies = capabilities_document.get("runtime_evidence_policy", {}).get("capabilities", {})
    capability_rows: list[dict[str, Any]] = []
    for capability in capabilities:
        capability_id = capability["id"]
        readiness_row = readiness_by_id.get(capability_id)
        if readiness_row is None:
            raise ValueError(f"readiness evaluator omitted capability: {capability_id}")
        policy = policies.get(capability_id, {})
        required_tests = policy.get("required_tests", []) if isinstance(policy, dict) else []
        implementation = capability.get("implementation")
        automatic = _test_references(test_files, capability_id, Path(str(implementation)).stem)
        capability_rows.append(
            {
                "id": capability_id,
                "declared_status": capability.get("status"),
                "source_owner": implementation,
                "verification_contract": capability.get("verification", []),
                "automated_tests": automatic,
                "fixtures": [item["id"] for item in fixture_by_capability[capability_id]],
                "runtime_checks": required_tests,
                "historical_ready": readiness_row["ready_for_support_review"],
                "exact_current_ready": readiness_row["current_binary_ready"],
                "blockers": readiness_row["current_binary_blockers"],
                "final_status": "PASS" if readiness_row["current_binary_ready"] else "DEFERRED",
            }
        )

    planner_settings = _planner_settings(settings_document, test_files)
    control_rows = [
        {
            "id": action,
            "source_owner": "tools/planner_ui.py",
            "automated_tests": _test_references(test_files, action),
            "source_contract": "PASS",
            "runtime_status": "DEFERRED",
        }
        for action in _control_actions()
    ]
    compile_rows = [
        {
            "source": target.source,
            "output": target.output,
            "subsystem": target.subsystem,
            "pragma_output": target.pragma_output,
            "automated_tests": _test_references(test_files, target.output, target.source),
            "source_contract": "PASS",
            "installed_runtime_status": "DEFERRED",
        }
        for target in build_release.DEFAULT_CONTRACT.compile_targets
    ]
    infrastructure_rows = [
        {
            **item,
            "automated_tests": _test_references(
                test_files,
                item["id"],
                *item["source_owners"],
                *(Path(owner).stem for owner in item["source_owners"]),
            ),
            "source_contract": "PASS",
            "runtime_status": "DEFERRED",
        }
        for item in INFRASTRUCTURE
    ]

    actuators = validate_actuator_registry.build_report()
    actuator_rows = [
        {
            "owner": owner,
            **classification,
            "final_status": "PASS" if classification["policy"] in {"blocked", "infrastructure", "test-only"} else "DEFERRED",
        }
        for owner, classification in sorted(actuators["classifications"].items())
    ]
    errors = list(readiness["errors"]) + list(actuators["errors"])
    if len(capability_rows) != len(readiness_by_id):
        errors.append("capability/readiness cardinality mismatch")
    if len(actuator_rows) != actuators["owners"]:
        errors.append("actuator owner cardinality mismatch")

    return {
        "schema_version": 1,
        "scope_rule": "Capabilities are canonical; every other collection is a non-additive system facet.",
        "counts": {
            "capabilities": len(capability_rows),
            "planner_settings": len(planner_settings),
            "fixtures": len(fixture_rows),
            "compile_targets": len(compile_rows),
            "control_actions": len(control_rows),
            "infrastructure_routes": len(infrastructure_rows),
            "actuator_owners": len(actuator_rows),
            "actuator_sites": actuators["sites"],
            "exact_current_capabilities_ready": sum(item["final_status"] == "PASS" for item in capability_rows),
        },
        "capabilities": capability_rows,
        "planner_settings": planner_settings,
        "fixtures": fixture_rows,
        "compile_targets": compile_rows,
        "control_actions": control_rows,
        "infrastructure_routes": infrastructure_rows,
        "actuator_owners": actuator_rows,
        "errors": errors,
        "warnings": list(readiness["evidence_validation"]["warnings"]) + list(actuators["warnings"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    try:
        report = build_report()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"full-system inventory failed: {exc}")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
