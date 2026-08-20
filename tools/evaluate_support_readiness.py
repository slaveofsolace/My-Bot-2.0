#!/usr/bin/env python3
"""Report fixture and trusted runtime-evidence readiness by capability."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from validate_runtime_evidence import _git_blob, _matches_head, parse_utc, validate_registry
except ModuleNotFoundError:  # Imported as tools.evaluate_support_readiness.
    from tools.validate_runtime_evidence import _git_blob, _matches_head, parse_utc, validate_registry

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
FIXTURE_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
EVIDENCE_DIR = ROOT / "tests/evidence/runtime"
BINARY_PROVENANCE_PATH = ROOT / "config/binary-provenance.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalized_repository_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("\\", "/").removeprefix("./")
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate.as_posix()


def _current_binary_index(
    root: Path,
    evidence_records: dict[str, dict[str, Any]],
) -> tuple[dict[str, tuple[str, int]], list[str]]:
    """Return exact current binary integrity for paths named by evidence records."""

    referenced_paths = {
        normalized
        for record in evidence_records.values()
        if isinstance(record.get("binary"), dict)
        for normalized in [_normalized_repository_path(record["binary"].get("path"))]
        if normalized is not None
    }
    if not referenced_paths:
        return {}, []

    index: dict[str, tuple[str, int]] = {}
    errors: list[str] = []
    provenance_relative = "config/binary-provenance.json"
    provenance_blob = _git_blob(root, "HEAD", provenance_relative)
    if provenance_blob is None:
        return {}, ["current binary provenance is not committed at HEAD"]
    provenance_clean = _matches_head(root, provenance_relative)
    if not provenance_clean:
        errors.append(f"current binary provenance has uncommitted changes: {provenance_relative}")
    try:
        provenance = json.loads(provenance_blob.decode("utf-8-sig"))
        artifacts = provenance.get("artifacts", [])
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
        return {}, errors + [f"committed current binary provenance is invalid: {exc}"]

    for relative in sorted(referenced_paths):
        records = [
            item
            for item in artifacts
            if isinstance(item, dict)
            and _normalized_repository_path(item.get("path")) == relative
        ]
        if len(records) != 1:
            errors.append(f"current binary has no unique provenance record: {relative}")
            continue
        record = records[0]
        expected_sha = record.get("sha256")
        expected_bytes = record.get("bytes")
        binary_clean = _matches_head(root, relative)
        if not binary_clean:
            errors.append(f"current binary has uncommitted changes: {relative}")
        content = _git_blob(root, "HEAD", relative)
        if content is None:
            errors.append(f"current binary is not committed at HEAD: {relative}")
            continue
        actual = (hashlib.sha256(content).hexdigest(), len(content))
        if actual != (expected_sha, expected_bytes):
            errors.append(f"committed current binary does not match committed provenance: {relative}")
            continue
        if provenance_clean and binary_clean:
            index[relative] = actual
    return index, errors


def _binary_matches_current(binary: object, index: dict[str, tuple[str, int]]) -> bool:
    if not isinstance(binary, dict):
        return False
    relative = _normalized_repository_path(binary.get("path"))
    return relative is not None and index.get(relative) == (
        binary.get("sha256"),
        binary.get("bytes"),
    )


def evaluate_readiness(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    require_ready: Iterable[str] = (),
    require_all_current: bool = False,
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
    evidence_records: dict[str, dict[str, Any]] = {}
    duplicate_evidence_ids: set[str] = set()
    evidence_record_errors: list[str] = []
    if evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("*.json")):
            try:
                record = load(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(record, dict) and isinstance(record.get("evidence_id"), str):
                evidence_id = record["evidence_id"]
                if evidence_id in evidence_records or evidence_id in duplicate_evidence_ids:
                    duplicate_evidence_ids.add(evidence_id)
                    evidence_records.pop(evidence_id, None)
                    evidence_record_errors.append(
                        f"duplicate evidence_id cannot be evaluated as exact-current: {evidence_id}"
                    )
                else:
                    evidence_records[evidence_id] = record
    current_binary_index, current_binary_errors = _current_binary_index(root, evidence_records)
    current_binary_errors = evidence_record_errors + current_binary_errors
    exact_current_evidence_ids = {
        item["evidence_id"]
        for item in trusted_evidence
        if isinstance(item.get("evidence_id"), str)
        and _binary_matches_current(
            evidence_records.get(item["evidence_id"], {}).get("binary"),
            current_binary_index,
        )
    }
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
        current_binary_evidence = [
            item for item in related_evidence if item.get("evidence_id") in exact_current_evidence_ids
        ]
        current_binary_passing_evidence = [item.get("evidence_id") for item in current_binary_evidence]
        current_binary_passing_test_types = sorted({item.get("test_type") for item in current_binary_evidence})
        required_test_types = sorted({
            item.get("test_type")
            for item in policy_by_capability.get(capability_id, {}).get("required_tests", [])
            if isinstance(item, dict) and isinstance(item.get("test_type"), str)
        })
        missing_test_types = sorted(set(required_test_types) - set(passing_test_types))
        current_binary_missing_test_types = sorted(
            set(required_test_types) - set(current_binary_passing_test_types)
        )
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
        current_binary_runtime_ready = not requires_runtime or (
            bool(required_test_types) and not current_binary_missing_test_types
        )
        current_binary_ready = fixture_ready and current_binary_runtime_ready
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
        current_binary_blockers: list[str] = []
        if fixture_mapping_missing:
            current_binary_blockers.append("required fixture mapping missing")
        elif missing_fixtures:
            current_binary_blockers.append("unverified fixtures: " + ", ".join(missing_fixtures))
        if requires_runtime and not required_test_types:
            current_binary_blockers.append("runtime evidence policy is missing")
        elif current_binary_missing_test_types:
            current_binary_blockers.append(
                "missing exact-current-binary test types: "
                + ", ".join(current_binary_missing_test_types)
            )

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
            "exact_current_binary_evidence": current_binary_passing_evidence,
            "current_binary_passing_test_types": current_binary_passing_test_types,
            "current_binary_missing_test_types": current_binary_missing_test_types,
            "current_binary_runtime_ready": current_binary_runtime_ready,
            "current_binary_ready": current_binary_ready,
            "rejected_evidence": rejected_evidence,
            "ready_for_support_review": ready,
            "blockers": blockers,
            "current_binary_blockers": current_binary_blockers,
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

    if require_all_current:
        for row in rows:
            if row["current_binary_ready"]:
                continue
            errors.append(
                f"capability lacks exact-current completion proof: {row['id']}: "
                + "; ".join(row["current_binary_blockers"])
            )

    return {
        "schema_version": 3,
        "capabilities": len(rows),
        "ready": sum(item["ready_for_support_review"] for item in rows),
        "not_ready": sum(not item["ready_for_support_review"] for item in rows),
        "exact_current_binary_records": len(exact_current_evidence_ids),
        "current_binary_ready": sum(item["current_binary_ready"] for item in rows),
        "current_binary_not_ready": sum(not item["current_binary_ready"] for item in rows),
        "evidence_validation": {
            "records": validation["records"],
            "trusted_records": sum(item["trusted_for_readiness"] for item in validation["evidence"]),
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        },
        "current_binary_validation": {
            "referenced_paths": len({
                _normalized_repository_path(record.get("binary", {}).get("path"))
                for record in evidence_records.values()
                if isinstance(record.get("binary"), dict)
                and _normalized_repository_path(record["binary"].get("path")) is not None
            }),
            "verified_paths": len(current_binary_index),
            "errors": current_binary_errors,
        },
        "errors": errors,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-ready", action="append", default=[])
    parser.add_argument(
        "--require-all-current",
        action="store_true",
        help="fail unless every catalogued capability is ready on the exact committed binary",
    )
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

    report = evaluate_readiness(
        now=now,
        require_ready=args.require_ready,
        require_all_current=args.require_all_current,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
