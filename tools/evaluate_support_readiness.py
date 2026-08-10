#!/usr/bin/env python3
"""Report fixture and trusted runtime-evidence readiness by capability."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from validate_runtime_evidence import parse_utc, validate_registry

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
FIXTURE_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
EVIDENCE_DIR = ROOT / "tests/evidence/runtime"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def evaluate_readiness(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    require_ready: Iterable[str] = (),
) -> dict[str, Any]:
    """Evaluate readiness using only records trusted by the shared validator."""

    root = root.resolve()
    capabilities_path = root / "config/current-client-capabilities.json"
    fixture_path = root / "tests/fixtures/current-client/manifest.json"
    evidence_dir = root / "tests/evidence/runtime"
    errors: list[str] = []
    try:
        catalog = load(capabilities_path)
        capabilities = catalog.get("capabilities", [])
    except (OSError, json.JSONDecodeError) as exc:
        catalog = {}
        capabilities = []
        errors.append(f"capability catalog is invalid: {exc}")
    try:
        fixtures = load(fixture_path).get("required_fixtures", [])
    except (OSError, json.JSONDecodeError) as exc:
        fixtures = []
        errors.append(f"fixture manifest is invalid: {exc}")

    validation = validate_registry(
        root=root,
        evidence_dir=evidence_dir,
        capabilities_path=capabilities_path,
        now=now,
    )
    errors.extend(f"runtime evidence: {message}" for message in validation["errors"])
    trusted_evidence = [item for item in validation["evidence"] if item["trusted_for_readiness"]]
    invalid_evidence = [item for item in validation["evidence"] if not item["valid"]]
    policy_by_capability = (
        catalog.get("runtime_evidence_policy", {}).get("capabilities", {})
        if isinstance(catalog, dict)
        else {}
    )

    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        capability_id = capability["id"]
        related_fixtures = [item for item in fixtures if capability_id in item.get("capability_ids", [])]
        verified_fixtures = [item["id"] for item in related_fixtures if item.get("status") == "verified"]
        missing_fixtures = [item["id"] for item in related_fixtures if item.get("status") != "verified"]
        related_evidence = [item for item in trusted_evidence if item.get("capability_id") == capability_id]
        passing_evidence = [item.get("evidence_id") for item in related_evidence]
        passing_test_types = sorted({item.get("test_type") for item in related_evidence})
        required_test_types = sorted({
            item.get("test_type")
            for item in policy_by_capability.get(capability_id, {}).get("required_tests", [])
            if isinstance(item, dict) and isinstance(item.get("test_type"), str)
        })
        missing_test_types = sorted(set(required_test_types) - set(passing_test_types))
        rejected_evidence = [
            item.get("evidence_id") or item.get("file")
            for item in invalid_evidence
            if item.get("capability_id") == capability_id
        ]

        fixture_mapping_required = capability.get("fixture_status") == "required"
        requires_fixture = fixture_mapping_required or bool(related_fixtures)
        fixture_mapping_missing = fixture_mapping_required and not related_fixtures
        requires_runtime = capability.get("runtime_evidence") == "required"
        fixture_ready = not requires_fixture or (not fixture_mapping_missing and not missing_fixtures)
        runtime_ready = not requires_runtime or (bool(required_test_types) and not missing_test_types)
        ready = fixture_ready and runtime_ready
        blockers: list[str] = []
        if fixture_mapping_missing:
            blockers.append("required fixture mapping missing")
        elif missing_fixtures:
            blockers.append("unverified fixtures: " + ", ".join(missing_fixtures))
        if requires_runtime and not required_test_types:
            blockers.append("runtime evidence policy is missing")
        elif missing_test_types:
            blockers.append("missing trusted test types: " + ", ".join(missing_test_types))
        if rejected_evidence:
            blockers.append("invalid runtime evidence: " + ", ".join(rejected_evidence))

        row = {
            "id": capability_id,
            "declared_status": capability.get("status"),
            "requires_fixture": requires_fixture,
            "fixture_ready": fixture_ready,
            "verified_fixtures": verified_fixtures,
            "requires_runtime": requires_runtime,
            "required_test_types": required_test_types,
            "runtime_ready": runtime_ready,
            "passing_test_types": passing_test_types,
            "missing_test_types": missing_test_types,
            "passing_evidence": passing_evidence,
            "rejected_evidence": rejected_evidence,
            "ready_for_support_review": ready,
            "blockers": blockers,
        }
        rows.append(row)
        by_id[capability_id] = row

    for capability_id in require_ready:
        if capability_id not in by_id:
            errors.append(f"required capability does not exist: {capability_id}")
        elif not by_id[capability_id]["ready_for_support_review"]:
            errors.append(
                f"capability is not ready: {capability_id}: "
                + "; ".join(by_id[capability_id]["blockers"])
            )

    return {
        "schema_version": 2,
        "capabilities": len(rows),
        "ready": sum(item["ready_for_support_review"] for item in rows),
        "not_ready": sum(not item["ready_for_support_review"] for item in rows),
        "evidence_validation": {
            "records": validation["records"],
            "trusted_records": sum(item["trusted_for_readiness"] for item in validation["evidence"]),
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        },
        "errors": errors,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-ready", action="append", default=[])
    parser.add_argument(
        "--as-of",
        help="validation clock as an ISO-8601 UTC timestamp ending in Z (for deterministic audits)",
    )
    args = parser.parse_args()
    now = None
    if args.as_of:
        now = parse_utc(args.as_of)
        if now is None:
            parser.error("--as-of must be an ISO-8601 UTC timestamp ending in Z")

    report = evaluate_readiness(now=now, require_ready=args.require_ready)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
