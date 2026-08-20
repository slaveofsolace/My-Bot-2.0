#!/usr/bin/env python3
"""Validate the fail-closed public redistribution rights record."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD_PATH = Path("config/redistribution-rights.json")
PROVENANCE_PATH = Path("config/binary-provenance.json")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ROLE = re.compile(r"^[a-z0-9.-]{3,80}$")
REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{3,160}$")
SCOPE_ITEM = re.compile(r"^[a-z0-9.-]+$")
PUBLIC_SCOPE = "public-binary-redistribution"
EXPECTED_COMPONENT = "inherited-imgloc"
EXPECTED_ARTIFACT = "lib/MyBot.run.dll"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate(root: Path, *, require_public: bool = False) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    record_file = root / RECORD_PATH
    provenance_file = root / PROVENANCE_PATH
    try:
        record = json.loads(record_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"rights record is unreadable: {exc}"], warnings, {}
    try:
        provenance = json.loads(provenance_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"binary provenance is unreadable: {exc}"], warnings, record

    expected_top = {"schema_version", "component_id", "status", "release_allowed", "artifact", "authorization", "review"}
    if set(record) != expected_top:
        errors.append("rights record fields must match the closed schema exactly")
    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if record.get("component_id") != EXPECTED_COMPONENT:
        errors.append(f"component_id must be {EXPECTED_COMPONENT}")
    status = record.get("status")
    if status not in {"pending", "granted"}:
        errors.append("status must be pending or granted")
    if not isinstance(record.get("release_allowed"), bool):
        errors.append("release_allowed must be boolean")

    artifact = record.get("artifact")
    if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256", "bytes"}:
        errors.append("artifact must contain only path, sha256, and bytes")
        artifact = {}
    if artifact.get("path") != EXPECTED_ARTIFACT:
        errors.append(f"artifact.path must be {EXPECTED_ARTIFACT}")
    if not isinstance(artifact.get("sha256"), str) or not HEX64.fullmatch(artifact.get("sha256", "")):
        errors.append("artifact.sha256 must be lowercase SHA-256")
    if not isinstance(artifact.get("bytes"), int) or isinstance(artifact.get("bytes"), bool) or artifact.get("bytes", 0) < 1:
        errors.append("artifact.bytes must be a positive integer")

    binary = root / EXPECTED_ARTIFACT
    if not binary.is_file():
        errors.append(f"rights-bound artifact is missing: {EXPECTED_ARTIFACT}")
    else:
        actual_bytes = binary.stat().st_size
        actual_sha = sha256_file(binary)
        if artifact.get("bytes") != actual_bytes:
            errors.append("rights record artifact byte count does not match the repository binary")
        if artifact.get("sha256") != actual_sha:
            errors.append("rights record artifact SHA-256 does not match the repository binary")

    provenance_matches = [item for item in provenance.get("artifacts", []) if item.get("path") == EXPECTED_ARTIFACT]
    if len(provenance_matches) != 1:
        errors.append("binary provenance must contain exactly one rights-bound artifact record")
    elif any(provenance_matches[0].get(key) != artifact.get(key) for key in ("sha256", "bytes")):
        errors.append("rights record artifact does not match binary provenance")

    review = record.get("review")
    if not isinstance(review, dict) or set(review) != {"reviewed_at", "reviewer_role", "conclusion"}:
        errors.append("review must contain only reviewed_at, reviewer_role, and conclusion")
        review = {}
    if not is_date(review.get("reviewed_at")):
        errors.append("review.reviewed_at must be an ISO date")
    if not isinstance(review.get("reviewer_role"), str) or not ROLE.fullmatch(review.get("reviewer_role", "")):
        errors.append("review.reviewer_role must be a neutral bounded role")
    conclusion = review.get("conclusion")
    if not isinstance(conclusion, str) or not 12 <= len(conclusion) <= 500:
        errors.append("review.conclusion must contain 12 to 500 characters")

    authorization = record.get("authorization")
    if status == "pending":
        if authorization is not None:
            errors.append("pending rights record cannot carry an authorization object")
        if record.get("release_allowed") is not False:
            errors.append("pending rights record must set release_allowed=false")
        warnings.append("public redistribution remains blocked: verified authorization evidence is pending")
    elif status == "granted":
        if record.get("release_allowed") is not True:
            errors.append("granted rights record must set release_allowed=true")
        if not isinstance(authorization, dict):
            errors.append("granted rights record requires an authorization object")
            authorization = {}
        expected_auth = {"basis", "grantor_role", "authorized_at", "scope", "private_evidence"}
        if set(authorization) != expected_auth:
            errors.append("authorization fields must match the closed schema exactly")
        if authorization.get("basis") not in {"written-permission", "licensed-replacement"}:
            errors.append("authorization.basis is not an accepted legal basis")
        grantor_role = authorization.get("grantor_role")
        if not isinstance(grantor_role, str) or not 3 <= len(grantor_role) <= 120:
            errors.append("authorization.grantor_role must be a bounded non-empty role")
        if not is_date(authorization.get("authorized_at")):
            errors.append("authorization.authorized_at must be an ISO date")
        scope = authorization.get("scope")
        if not isinstance(scope, list) or PUBLIC_SCOPE not in scope or len(scope) != len(set(scope)) or not all(isinstance(item, str) and SCOPE_ITEM.fullmatch(item) for item in scope):
            errors.append(f"authorization.scope must uniquely include {PUBLIC_SCOPE}")
        evidence = authorization.get("private_evidence")
        if not isinstance(evidence, dict) or set(evidence) != {"sha256", "bytes", "custodian_reference"}:
            errors.append("authorization.private_evidence fields must match the closed schema exactly")
        else:
            if not isinstance(evidence.get("sha256"), str) or not HEX64.fullmatch(evidence.get("sha256", "")):
                errors.append("private evidence SHA-256 is invalid")
            if not isinstance(evidence.get("bytes"), int) or isinstance(evidence.get("bytes"), bool) or evidence.get("bytes", 0) < 1:
                errors.append("private evidence byte count must be positive")
            if not isinstance(evidence.get("custodian_reference"), str) or not REFERENCE.fullmatch(evidence.get("custodian_reference", "")):
                errors.append("private evidence custodian reference is invalid")

    if require_public and (status != "granted" or record.get("release_allowed") is not True):
        errors.append("public distribution requires a granted, release-allowed rights record")

    return errors, warnings, record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-public", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    errors, warnings, record = validate(args.root.resolve(), require_public=args.require_public)
    report = {
        "schema_version": 1,
        "component_id": record.get("component_id") if record else None,
        "status": record.get("status") if record else None,
        "public_release_ready": not errors and record.get("status") == "granted" and record.get("release_allowed") is True,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
