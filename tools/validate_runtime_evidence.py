#!/usr/bin/env python3
"""Validate redacted runtime evidence records without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "tests/evidence/runtime"
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_TEST_TYPES = {"windows-static", "emulator-smoke", "game-surface-recognition", "route-execution", "end-to-end"}
ALLOWED_RESULTS = {"passed", "failed", "blocked"}
PROHIBITED_KEYS = {
    "password", "token", "secret", "email", "player_id", "supercell_id", "account_id",
    "machine_name", "computer_name", "username", "serial_number", "ip_address", "chat_text",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def walk_keys(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in PROHIBITED_KEYS:
                findings.append(f"{prefix}{key}")
            findings.extend(walk_keys(child, f"{prefix}{key}."))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(walk_keys(child, f"{prefix}{index}."))
    return findings


def parse_utc(value: str) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-capability", action="append", default=[])
    args = parser.parse_args()

    capabilities = load(CAPABILITIES_PATH)
    capability_ids = {item["id"] for item in capabilities.get("capabilities", [])}
    errors: list[str] = []
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    passed_by_capability: dict[str, int] = {}

    for path in sorted(EVIDENCE_DIR.glob("*.json")):
        try:
            record = load(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue

        evidence_id = record.get("evidence_id", "")
        prefix = evidence_id or path.stem
        record_errors: list[str] = []
        if record.get("schema_version") != 1:
            record_errors.append("schema_version must be 1")
        if not isinstance(evidence_id, str) or not ID_PATTERN.fullmatch(evidence_id):
            record_errors.append("invalid evidence_id")
        elif path.name != f"{evidence_id}.json":
            record_errors.append("file name must match evidence_id")

        capability_id = record.get("capability_id")
        if capability_id not in capability_ids:
            record_errors.append(f"unknown capability_id {capability_id!r}")
        test_type = record.get("test_type")
        if test_type not in ALLOWED_TEST_TYPES:
            record_errors.append(f"unsupported test_type {test_type!r}")
        result = record.get("result")
        if result not in ALLOWED_RESULTS:
            record_errors.append(f"unsupported result {result!r}")
        if not parse_utc(record.get("captured_at")):
            record_errors.append("captured_at must be an ISO-8601 UTC timestamp ending in Z")
        if not isinstance(record.get("commit_sha"), str) or not SHA_PATTERN.fullmatch(record["commit_sha"]):
            record_errors.append("commit_sha must be 40 lowercase hexadecimal characters")
        if record.get("redacted") is not True:
            record_errors.append("redacted must be true")

        prohibited = walk_keys(record)
        if prohibited:
            record_errors.append("prohibited fields: " + ", ".join(prohibited))

        environment = record.get("environment")
        environment_fields = {"os", "os_version", "autoit_version", "emulator", "emulator_version", "instance_index", "game_version"}
        if not isinstance(environment, dict):
            record_errors.append("environment must be an object")
        else:
            if set(environment) != environment_fields:
                record_errors.append("environment fields do not match the evidence contract")
            if not isinstance(environment.get("instance_index"), int) or environment.get("instance_index", -1) < 0:
                record_errors.append("environment.instance_index must be a non-negative integer")

        checks = record.get("checks")
        if not isinstance(checks, list) or not checks:
            record_errors.append("checks must be a non-empty list")
            checks = []
        seen_checks: set[str] = set()
        for index, check in enumerate(checks):
            if not isinstance(check, dict) or set(check) != {"id", "result", "details"}:
                record_errors.append(f"check[{index}] fields do not match the contract")
                continue
            check_id = check.get("id", "")
            if not isinstance(check_id, str) or not ID_PATTERN.fullmatch(check_id):
                record_errors.append(f"check[{index}] has invalid id")
            elif check_id in seen_checks:
                record_errors.append(f"duplicate check id {check_id}")
            seen_checks.add(check_id)
            if check.get("result") not in ALLOWED_RESULTS:
                record_errors.append(f"check[{index}] has invalid result")
            if len(str(check.get("details", "")).strip()) < 5:
                record_errors.append(f"check[{index}] details are missing or too short")

        reviewer = record.get("reviewer")
        if not isinstance(reviewer, dict) or set(reviewer) != {"name", "reviewed_at"}:
            record_errors.append("reviewer fields do not match the contract")
            reviewer = {}
        artifact_refs = record.get("artifact_refs")
        if not isinstance(artifact_refs, list) or not all(isinstance(item, str) and len(item.strip()) >= 3 for item in artifact_refs):
            record_errors.append("artifact_refs must be a list of non-empty references")
            artifact_refs = []
        if len(artifact_refs) != len(set(artifact_refs)):
            record_errors.append("artifact_refs must be unique")

        if result == "passed":
            if any(check.get("result") != "passed" for check in checks if isinstance(check, dict)):
                record_errors.append("passed evidence requires every check to pass")
            if not str(reviewer.get("name", "")).strip() or not parse_utc(reviewer.get("reviewed_at", "")):
                record_errors.append("passed evidence requires reviewer name and UTC reviewed_at")
            if not artifact_refs:
                record_errors.append("passed evidence requires at least one artifact reference")

        if record_errors:
            errors.extend(f"{prefix}: {message}" for message in record_errors)
        elif result == "passed":
            passed_by_capability[capability_id] = passed_by_capability.get(capability_id, 0) + 1

        records.append({"file": path.name, "evidence_id": evidence_id, "capability_id": capability_id, "result": result, "errors": record_errors})

    for capability_id in args.require_capability:
        if capability_id not in capability_ids:
            errors.append(f"required capability does not exist: {capability_id}")
        elif passed_by_capability.get(capability_id, 0) < 1:
            errors.append(f"no passing runtime evidence exists for required capability: {capability_id}")

    if not records:
        warnings.append("no runtime evidence records are committed yet")

    report = {
        "schema_version": 1,
        "records": len(records),
        "passing_capabilities": passed_by_capability,
        "errors": errors,
        "warnings": warnings,
        "evidence": records,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
