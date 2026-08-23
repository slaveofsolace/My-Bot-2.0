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
import hashlib
import json
import re
import subprocess
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
UPSTREAMS_PATH = ROOT / "upstreams.lock.json"
TEST_ROOTS = (ROOT / "tests/python", ROOT / "tests/autoit")

OG_GUI_RE = re.compile(
    r"^(?:COCBot/GUI/.+\.au3|COCBot/MBR GUI (?:Design|Control)\.au3)$"
)
OG_CONFIG_PATHS = {
    "COCBot/functions/Config/readConfig.au3",
    "COCBot/functions/Config/saveConfig.au3",
    "COCBot/functions/Config/applyConfig.au3",
}
OG_ENTRYPOINTS = {"MyBot.run.au3"}

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


def _git(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise ValueError(proc.stderr.decode("utf-8", errors="replace").strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _pinned_og_commit() -> str:
    upstreams = _load(UPSTREAMS_PATH)
    matches = [item for item in upstreams.get("sources", []) if item.get("id") == "mybotrun-v8"]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{40}", str(matches[0].get("commit", ""))):
        raise ValueError("upstreams.lock.json must pin exactly one mybotrun-v8 commit")
    return str(matches[0]["commit"])


def _og_family(path: str) -> str:
    folded = path.casefold()
    if path in OG_ENTRYPOINTS:
        return "runtime.entrypoint"
    if path in OG_CONFIG_PATHS:
        return "profile.settings"
    if OG_GUI_RE.fullmatch(path):
        if "bot - android" in folded:
            return "emulator.configuration"
        if "bot - profiles" in folded:
            return "profile.management"
        if "bot - stats" in folded:
            return "diagnostics.reports"
        if "bot - options" in folded:
            return "runtime.configuration"
        if "army" in folded or "troops" in folded:
            return "army.configuration"
        if "attack" in folded:
            return "battle.configuration"
        if "donate" in folded:
            return "village.donate-request"
        if "achievement" in folded:
            return "village.rewards"
        if "upgrade" in folded:
            return "village.upgrades"
        if "notify" in folded:
            return "notifications"
        if "misc" in folded:
            return "village.maintenance"
        if "collector" in folded:
            return "village.maintenance"
        if "preset" in folded:
            return "profile.settings"
        if any(name in folded for name in ("about", "bottom", "log", "splash")):
            return "native.shell"
        return "native.configuration"
    if not path.startswith("COCBot/functions/"):
        return ""
    relative = path.removeprefix("COCBot/functions/")
    top = relative.split("/", 1)[0]
    if top == "Android":
        return "emulator.runtime"
    if top == "Attack":
        return "builder-base.battles" if relative.startswith("Attack/BuilderBase/") else "battle.runtime"
    if top == "Config":
        return "profile.settings"
    if top == "CreateArmy":
        return "army.runtime"
    if top == "GUI":
        return "native.infrastructure"
    if top in {"Image Search", "Pixels", "Read Text", "Search"}:
        return "recognition"
    if top == "Main Screen":
        return "runtime.recovery"
    if top == "Other":
        return "shared.infrastructure"
    if top == "Village":
        if relative.startswith("Village/BuilderBase/"):
            return "builder-base.runtime"
        if relative.startswith("Village/Clan Games/"):
            return "village.clan-games"
        return "village.runtime"
    return ""


def _og_parity_rows(actuator_report: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[str]]:
    commit = _pinned_og_commit()
    tree: dict[str, str] = {}
    raw_tree = _git("ls-tree", "-r", "-z", commit, "--", "COCBot", "MyBot.run.au3")
    for raw_entry in raw_tree.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", 1)
        fields = metadata.decode("ascii").split()
        if len(fields) != 3 or fields[1] != "blob":
            continue
        tree[raw_path.decode("utf-8", errors="strict")] = fields[2]
    selected = sorted(
        path
        for path in tree
        if OG_GUI_RE.fullmatch(path)
        or path in OG_CONFIG_PATHS
        or path in OG_ENTRYPOINTS
        or path.startswith("COCBot/functions/")
    )

    current_actuators: dict[str, list[dict[str, Any]]] = {}
    for owner, classification in actuator_report["classifications"].items():
        owner_path = owner.rsplit("::", 1)[0]
        current_actuators.setdefault(owner_path, []).append(classification)

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in selected:
        family = _og_family(path)
        if not family:
            errors.append(f"unclassified pinned OG source: {path}")
        current_path = ROOT / path
        current_exists = current_path.is_file()
        current_bytes = current_path.read_bytes() if current_exists else b""
        current_blob = (
            hashlib.sha1(f"blob {len(current_bytes)}\0".encode("ascii") + current_bytes).hexdigest()
            if current_exists
            else None
        )
        classifications = current_actuators.get(path, [])
        policies = sorted({str(item.get("policy")) for item in classifications})
        capability_ids = sorted(
            {
                str(capability_id)
                for item in classifications
                for capability_id in item.get("capability_ids", [])
            }
        )
        role = (
            "user-visible-configuration"
            if OG_GUI_RE.fullmatch(path)
            else "persisted-settings"
            if path in OG_CONFIG_PATHS
            else "runtime-entrypoint"
            if path in OG_ENTRYPOINTS
            else "automation-or-infrastructure"
        )
        rows.append(
            {
                "path": path,
                "family": family,
                "role": role,
                "og_git_blob": tree[path],
                "current_sha256": hashlib.sha256(current_bytes).hexdigest() if current_exists else None,
                "current_git_blob": current_blob,
                "current_source_state": (
                    "missing" if not current_exists else "unchanged" if current_blob == tree[path] else "adapted"
                ),
                "current_actuator_policies": policies,
                "current_capability_ids": capability_ids,
                "source_contract": "PASS" if current_exists else "FAIL",
                "exact_current_runtime_status": "DEFERRED",
            }
        )
        if not current_exists:
            errors.append(f"pinned OG source is missing from current master: {path}")
    if len(selected) != len(set(selected)):
        errors.append("pinned OG source inventory contains duplicates")
    return commit, rows, errors


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
    og_commit, og_parity, og_errors = _og_parity_rows(actuators)
    errors.extend(og_errors)
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
            "og_parity_sources": len(og_parity),
            "og_gui_sources": sum(item["role"] == "user-visible-configuration" for item in og_parity),
            "og_function_sources": sum(item["path"].startswith("COCBot/functions/") for item in og_parity),
            "og_unclassified_sources": sum(not item["family"] for item in og_parity),
        },
        "pinned_og_commit": og_commit,
        "og_parity": og_parity,
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
