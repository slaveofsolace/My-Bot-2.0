#!/usr/bin/env python3
"""Report fixture and runtime-evidence readiness for every documented capability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
FIXTURE_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
EVIDENCE_DIR = ROOT / "tests/evidence/runtime"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-ready", action="append", default=[])
    args = parser.parse_args()

    capabilities = load(CAPABILITIES_PATH).get("capabilities", [])
    fixtures = load(FIXTURE_PATH).get("required_fixtures", [])
    evidence: list[dict[str, Any]] = []
    for path in sorted(EVIDENCE_DIR.glob("*.json")):
        try:
            evidence.append(load(path))
        except (OSError, json.JSONDecodeError):
            continue

    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        capability_id = capability["id"]
        related_fixtures = [item for item in fixtures if capability_id in item.get("capability_ids", [])]
        verified_fixtures = [item["id"] for item in related_fixtures if item.get("status") == "verified"]
        missing_fixtures = [item["id"] for item in related_fixtures if item.get("status") != "verified"]
        passing_evidence = [item.get("evidence_id") for item in evidence if item.get("capability_id") == capability_id and item.get("result") == "passed"]

        requires_fixture = bool(related_fixtures)
        requires_runtime = capability.get("runtime_evidence") == "required" or capability.get("status") in {"adapter-added", "catalogued", "fixture-required"}
        if capability.get("status") == "engine-added":
            requires_runtime = True

        fixture_ready = not requires_fixture or not missing_fixtures
        runtime_ready = not requires_runtime or bool(passing_evidence)
        ready = fixture_ready and runtime_ready
        blockers: list[str] = []
        if missing_fixtures:
            blockers.append("unverified fixtures: " + ", ".join(missing_fixtures))
        if requires_runtime and not passing_evidence:
            blockers.append("passing runtime evidence required")

        row = {
            "id": capability_id,
            "declared_status": capability.get("status"),
            "requires_fixture": requires_fixture,
            "fixture_ready": fixture_ready,
            "verified_fixtures": verified_fixtures,
            "requires_runtime": requires_runtime,
            "runtime_ready": runtime_ready,
            "passing_evidence": passing_evidence,
            "ready_for_support_review": ready,
            "blockers": blockers,
        }
        rows.append(row)
        by_id[capability_id] = row

    errors: list[str] = []
    for capability_id in args.require_ready:
        if capability_id not in by_id:
            errors.append(f"required capability does not exist: {capability_id}")
        elif not by_id[capability_id]["ready_for_support_review"]:
            errors.append(f"capability is not ready: {capability_id}: {'; '.join(by_id[capability_id]['blockers'])}")

    report = {
        "schema_version": 1,
        "capabilities": len(rows),
        "ready": sum(item["ready_for_support_review"] for item in rows),
        "not_ready": sum(not item["ready_for_support_review"] for item in rows),
        "errors": errors,
        "results": rows,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
