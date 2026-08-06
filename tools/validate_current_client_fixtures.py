#!/usr/bin/env python3
"""Validate current-client fixture inventory, image dimensions, hashes, and privacy metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_STATUS = {"missing", "captured", "redacted", "verified"}


def safe_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise ValueError(f"path escapes repository root: {relative}")
    return candidate


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("not a valid PNG with an IHDR header")
    return struct.unpack(">II", header[16:24])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    fixture_results: list[dict[str, Any]] = []

    manifest = load_json(MANIFEST_PATH)
    capabilities = load_json(CAPABILITIES_PATH)
    capability_ids = {item["id"] for item in capabilities.get("capabilities", [])}

    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must be 1")

    contract = manifest.get("capture_contract", {})
    expected_width = contract.get("width")
    expected_height = contract.get("height")
    if expected_width != 860 or expected_height != 732:
        errors.append("capture contract must remain 860x732")
    if contract.get("format") != "png":
        errors.append("capture format must be png")

    entries = manifest.get("required_fixtures")
    if not isinstance(entries, list) or not entries:
        errors.append("required_fixtures must be a non-empty list")
        entries = []

    seen_ids: set[str] = set()
    missing_count = 0
    complete_count = 0

    for index, entry in enumerate(entries):
        fixture_id = entry.get("id", "")
        status = entry.get("status", "")
        result: dict[str, Any] = {"id": fixture_id or f"index-{index}", "status": status, "checks": []}
        fixture_results.append(result)

        if not isinstance(fixture_id, str) or not ID_PATTERN.fullmatch(fixture_id):
            errors.append(f"fixture[{index}] has invalid id: {fixture_id!r}")
            continue
        if fixture_id in seen_ids:
            errors.append(f"duplicate fixture id: {fixture_id}")
        seen_ids.add(fixture_id)

        if status not in ALLOWED_STATUS:
            errors.append(f"{fixture_id}: unsupported status {status!r}")
            continue
        if not isinstance(entry.get("purpose"), str) or len(entry["purpose"].strip()) < 10:
            errors.append(f"{fixture_id}: purpose is missing or too short")

        referenced_capabilities = entry.get("capability_ids")
        if not isinstance(referenced_capabilities, list) or not referenced_capabilities:
            errors.append(f"{fixture_id}: capability_ids must be a non-empty list")
            referenced_capabilities = []
        for capability_id in referenced_capabilities:
            if capability_id not in capability_ids:
                errors.append(f"{fixture_id}: unknown capability id {capability_id}")

        try:
            image_path = safe_path(entry.get("image_path", ""))
            metadata_path = safe_path(entry.get("metadata_path", ""))
        except (TypeError, ValueError) as exc:
            errors.append(f"{fixture_id}: {exc}")
            continue

        expected_image = ROOT / "tests/fixtures/current-client/images" / f"{fixture_id}.png"
        expected_metadata = ROOT / "tests/fixtures/current-client/metadata" / f"{fixture_id}.json"
        if image_path != expected_image.resolve():
            errors.append(f"{fixture_id}: image_path does not match the fixture id")
        if metadata_path != expected_metadata.resolve():
            errors.append(f"{fixture_id}: metadata_path does not match the fixture id")

        image_exists = image_path.is_file()
        metadata_exists = metadata_path.is_file()

        if status == "missing":
            missing_count += 1
            if image_exists or metadata_exists:
                errors.append(f"{fixture_id}: files exist while manifest status is missing")
            result["checks"].append("files-absent")
            continue

        complete_count += 1
        if not image_exists:
            errors.append(f"{fixture_id}: image file is missing")
        if not metadata_exists:
            errors.append(f"{fixture_id}: metadata file is missing")
        if not image_exists or not metadata_exists:
            continue

        try:
            width, height = png_dimensions(image_path)
        except ValueError as exc:
            errors.append(f"{fixture_id}: {exc}")
            continue
        if width != expected_width or height != expected_height:
            errors.append(f"{fixture_id}: expected {expected_width}x{expected_height}, found {width}x{height}")
        result["checks"].append("png-dimensions")

        try:
            metadata = load_json(metadata_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{fixture_id}: invalid metadata JSON: {exc}")
            continue

        required_metadata = {
            "schema_version",
            "fixture_id",
            "captured_at",
            "game_version",
            "source_type",
            "width",
            "height",
            "sha256",
            "redacted",
            "redaction_notes",
            "assertions",
            "reviewed_by",
            "reviewed_at",
            "notes",
        }
        missing_fields = sorted(required_metadata - set(metadata))
        if missing_fields:
            errors.append(f"{fixture_id}: metadata fields missing: {', '.join(missing_fields)}")
            continue

        if metadata.get("schema_version") != 1:
            errors.append(f"{fixture_id}: metadata schema_version must be 1")
        if metadata.get("fixture_id") != fixture_id:
            errors.append(f"{fixture_id}: metadata fixture_id does not match")
        if metadata.get("width") != width or metadata.get("height") != height:
            errors.append(f"{fixture_id}: metadata dimensions do not match the PNG")

        actual_hash = sha256(image_path)
        declared_hash = metadata.get("sha256")
        if not isinstance(declared_hash, str) or not SHA256_PATTERN.fullmatch(declared_hash):
            errors.append(f"{fixture_id}: metadata sha256 must be lowercase hexadecimal")
        elif declared_hash != actual_hash:
            errors.append(f"{fixture_id}: metadata sha256 does not match the PNG")
        result["sha256"] = actual_hash
        result["checks"].append("sha256")

        assertions = metadata.get("assertions")
        if not isinstance(assertions, list) or not assertions or not all(isinstance(item, str) and item.strip() for item in assertions):
            errors.append(f"{fixture_id}: assertions must contain at least one non-empty statement")

        if status in {"redacted", "verified"} and metadata.get("redacted") is not True:
            errors.append(f"{fixture_id}: {status} fixtures require redacted=true")
        if metadata.get("redacted") is True and not str(metadata.get("redaction_notes", "")).strip():
            warnings.append(f"{fixture_id}: redacted fixture has no redaction notes")
        if status == "verified":
            if not str(metadata.get("reviewed_by", "")).strip() or not str(metadata.get("reviewed_at", "")).strip():
                errors.append(f"{fixture_id}: verified fixtures require reviewed_by and reviewed_at")
        result["checks"].append("metadata")

    if args.require_complete and missing_count:
        errors.append(f"release fixture gate requires all captures; {missing_count} remain missing")

    report = {
        "schema_version": 1,
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "total": len(entries),
        "complete": complete_count,
        "missing": missing_count,
        "errors": errors,
        "warnings": warnings,
        "fixtures": fixture_results,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
