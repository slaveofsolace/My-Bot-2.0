#!/usr/bin/env python3
"""Create an owner-local zero-copy profile record for unlaunched inherited-runtime proof.

The source profile is never modified and none of its files or values are copied.
The tool hashes it before and after creating a minimal inert config below the fixed
LocalInheritedRuntime/ProofProfiles root, then records both digests locally.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid


SCHEMA = "my-bot-local-inherited-proof-profile-v2"
PROOF_PROFILE_NAME = "Proof"
RECEIPT_NAME = "proof-profile.local.json"
PROOF_MODE = "unlaunched-static-only"
SOURCE_DATA_POLICY = "hash-source-copy-zero-files"
PROOF_CONFIG_SHA256 = "66fb27b395bbac645c825410a383053786aeb1f2194d51b6b7a6d6e3df993a45"
PROFILE_SELECTOR_SHA256 = "8290b2a419da32531c29ec1068dbc7f4c6761adf6f85c1a9f2b7c11d68991ba1"
ALLOWED_PROOF_RELATIVE_PATHS = ("Profiles/profile.ini", "Profiles/Proof/config.ini")
REQUIRED_PROFILE_VALUES = [
    "general|AutoStart|0",
    "general|Restarted|0",
    "general|ChkVersion|0",
    "general|AutoStartDelay|0",
    "general|DisposeWindows|0",
    "other|ChkSellRewards|0",
    "other|ChkAutoResume|0",
    "other|ChkDisableNotifications|1",
    "SuperTroopsBoost|SuperTroopsEnable|0",
    "android|shared_prefs.update|0",
    "android|emulator|",
    "android|instance|",
    "notify|TGEnabled|0",
    "notify|TGToken|",
    "notify|PBRemote|0",
    "notify|Origin|",
    "ProfileSCID|OnlySCIDAccounts|0",
    "ProfileSCID|WhatSCIDAccount2Use|0",
]
SAFETY_PATH = Path(__file__).resolve().parents[1] / "config" / "local-inherited-runtime-safety.json"
PROFILE_NAME_PATTERN = re.compile(r'^[^\\/:*?"<>|\r\n]{1,80}$')
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PROOF_DIRECTORY_PATTERN = re.compile(r"^proof-[0-9a-f]{16}-[0-9a-f]{16}-[0-9a-f]{8}$")


class ProofProfileError(RuntimeError):
    """A source profile, safety contract, or fixed proof copy failed closed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_identity(source_root: Path, profile_name: str) -> str:
    """Bind a proof destination to one canonical local source/profile pair."""
    canonical_root = source_root.resolve(strict=True)
    payload = json.dumps(
        {
            "profile_name": os.path.normcase(profile_name),
            "source_root": os.path.normcase(str(canonical_root)),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def directory_digest(root: Path, *, excluded: frozenset[str] = frozenset()) -> tuple[int, str]:
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if root.is_symlink() or is_junction(root):
        raise ProofProfileError(f"Profile tree is redirected: {root}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ProofProfileError(f"Profile tree is not a regular directory: {root}")
    files: list[Path] = []
    for directory, names, entries in os.walk(root, topdown=True, followlinks=False):
        parent = Path(directory)
        for name in names:
            child = parent / name
            if child.is_symlink() or is_junction(child):
                raise ProofProfileError(f"Profile tree contains a redirected directory: {child.relative_to(root)}")
        for name in entries:
            child = parent / name
            relative = child.relative_to(root).as_posix().casefold()
            if relative in excluded:
                continue
            if child.is_symlink() or not child.is_file():
                raise ProofProfileError(f"Profile tree contains a redirected or non-file entry: {relative}")
            if "\\" in relative or any(ord(character) < 32 for character in relative):
                raise ProofProfileError(f"Profile tree contains an unsafe file name: {relative!r}")
            files.append(child)
    files.sort(key=lambda value: value.relative_to(root).as_posix().casefold().encode("utf-8"))
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().casefold()
        digest.update(f"{relative}\t{path.stat().st_size}\t{_sha256_file(path)}\n".encode("utf-8"))
    return len(files), digest.hexdigest()


def fixed_proof_parent(environment: dict[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    local_app_data = values.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        raise ProofProfileError("LOCALAPPDATA is unavailable; the fixed proof-profile root cannot be resolved")
    return (Path(local_app_data) / "My Bot 2.0" / "LocalInheritedRuntime" / "ProofProfiles").absolute()


def load_safety_contract(path: Path = SAFETY_PATH) -> tuple[list[tuple[str, str, str]], str]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProofProfileError(f"Safety contract is unreadable: {error}") from error
    if set(document) != {
        "allowed_proof_relative_paths", "profile_copy_policy", "profile_selector_sha256", "proof_config_sha256",
        "proof_mode", "required_profile_values", "schema"
    } or document["schema"] != "my-bot-local-inherited-profile-safety-v2":
        raise ProofProfileError("Safety contract schema is invalid")
    values = document["required_profile_values"]
    if (
        not isinstance(values, list)
        or values != REQUIRED_PROFILE_VALUES
        or document["allowed_proof_relative_paths"] != list(ALLOWED_PROOF_RELATIVE_PATHS)
        or document["profile_copy_policy"] != SOURCE_DATA_POLICY
        or document["profile_selector_sha256"] != PROFILE_SELECTOR_SHA256
        or document["proof_config_sha256"] != PROOF_CONFIG_SHA256
        or document["proof_mode"] != PROOF_MODE
    ):
        raise ProofProfileError("Safety contract does not contain the complete unlaunched static-proof boundary")
    parsed = [tuple(value.split("|", 2)) for value in values]
    return parsed, hashlib.sha256(raw).hexdigest()


def _find_casefold(values: list[str], expected: str) -> str | None:
    matches = [value for value in values if value.casefold() == expected.casefold()]
    if len(matches) > 1:
        raise ProofProfileError(f"Profile config contains ambiguous duplicate names for {expected!r}")
    return matches[0] if matches else None


def write_minimal_config(config_path: Path, requirements: list[tuple[str, str, str]]) -> None:
    """Write only reviewed boundary values; no owner setting or secret is copied."""
    parser = configparser.RawConfigParser(strict=True, interpolation=None)
    parser.optionxform = str
    for expected_section, expected_key, value in requirements:
        section = _find_casefold(parser.sections(), expected_section)
        if section is None:
            parser.add_section(expected_section)
            section = expected_section
        parser.set(section, expected_key, value)
    config_path.parent.mkdir(parents=True, exist_ok=False)
    with config_path.open("w", encoding="utf-8", newline="\n") as stream:
        parser.write(stream, space_around_delimiters=False)
    if _sha256_file(config_path) != PROOF_CONFIG_SHA256:
        raise ProofProfileError("Generated static proof config bytes do not match the reviewed contract")


def verify_config_requirements(config_path: Path, requirements: list[tuple[str, str, str]]) -> None:
    parser = configparser.RawConfigParser(strict=True, interpolation=None)
    parser.optionxform = str
    try:
        with config_path.open("r", encoding="utf-8-sig", errors="strict") as stream:
            parser.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as error:
        raise ProofProfileError(f"Proof profile config cannot be verified safely: {error}") from error
    for expected_section, expected_key, expected_value in requirements:
        section = _find_casefold(parser.sections(), expected_section)
        if section is None:
            raise ProofProfileError(f"Proof profile is missing required section {expected_section!r}")
        key = _find_casefold(list(parser[section].keys()), expected_key)
        if key is None or parser.get(section, key).strip() != expected_value:
            raise ProofProfileError(
                f"Proof profile does not explicitly set [{expected_section}] {expected_key}={expected_value}"
            )


def _receipt_document(
    *, source_root: Path, source_profile: str, source_count: int, source_digest: str,
    proof_count: int, proof_digest: str, safety_hash: str,
) -> dict[str, object]:
    return {
        "proof_mode": PROOF_MODE,
        "proof_profile_name": PROOF_PROFILE_NAME,
        "proof_tree_file_count": proof_count,
        "proof_tree_sha256": proof_digest,
        "safety_contract_sha256": safety_hash,
        "schema": SCHEMA,
        "source_data_policy": SOURCE_DATA_POLICY,
        "source_files_copied": 0,
        "source_profile_file_count": source_count,
        "source_profile_name": source_profile,
        "source_profile_root": str(source_root),
        "source_profile_sha256": source_digest,
        "source_verified_unchanged": True,
    }


def validate_proof_root(
    root: Path,
    *,
    expected_parent: Path | None = None,
    expected_source_root: Path | None = None,
    expected_profile_name: str | None = None,
    expected_source_count: int | None = None,
    expected_source_digest: str | None = None,
) -> dict[str, object]:
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if root.is_symlink() or is_junction(root):
        raise ProofProfileError("Proof-profile root is redirected")
    root = root.resolve(strict=True)
    if not root.is_dir() or not PROOF_DIRECTORY_PATTERN.fullmatch(root.name):
        raise ProofProfileError("Proof-profile root name or type is invalid")
    if expected_parent is not None:
        expected_parent = expected_parent.resolve(strict=True)
        if root.parent != expected_parent:
            raise ProofProfileError("Proof-profile root is outside the fixed owner-local proof parent")
    receipt = root / RECEIPT_NAME
    if not receipt.is_file() or receipt.is_symlink() or receipt.stat().st_size > 64 * 1024:
        raise ProofProfileError("Proof-profile receipt is missing, redirected, or unexpectedly large")
    try:
        document = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProofProfileError(f"Proof-profile receipt is unreadable: {error}") from error
    required = {
        "proof_mode",
        "proof_profile_name", "proof_tree_file_count", "proof_tree_sha256", "safety_contract_sha256", "schema",
        "source_data_policy", "source_files_copied",
        "source_profile_file_count", "source_profile_name", "source_profile_root", "source_profile_sha256",
        "source_verified_unchanged",
    }
    if (
        set(document) != required
        or document.get("schema") != SCHEMA
        or document.get("proof_mode") != PROOF_MODE
        or document.get("proof_profile_name") != PROOF_PROFILE_NAME
        or document.get("source_data_policy") != SOURCE_DATA_POLICY
        or document.get("source_files_copied") != 0
    ):
        raise ProofProfileError("Proof-profile receipt schema is invalid")
    if (
        type(document.get("proof_tree_file_count")) is not int
        or document["proof_tree_file_count"] <= 0
        or type(document.get("source_profile_file_count")) is not int
        or document["source_profile_file_count"] <= 0
        or document.get("source_verified_unchanged") is not True
        or not isinstance(document.get("source_profile_root"), str)
        or not isinstance(document.get("source_profile_name"), str)
        or not PROFILE_NAME_PATTERN.fullmatch(document["source_profile_name"])
        or document["source_profile_name"] in {".", ".."}
        or not isinstance(document.get("proof_tree_sha256"), str)
        or not HASH_PATTERN.fullmatch(document["proof_tree_sha256"])
        or not isinstance(document.get("source_profile_sha256"), str)
        or not HASH_PATTERN.fullmatch(document["source_profile_sha256"])
        or not isinstance(document.get("safety_contract_sha256"), str)
        or not HASH_PATTERN.fullmatch(document["safety_contract_sha256"])
    ):
        raise ProofProfileError("Proof-profile receipt values are invalid")
    proof_count, proof_digest = directory_digest(root, excluded=frozenset({RECEIPT_NAME.casefold()}))
    if proof_count != document["proof_tree_file_count"] or proof_digest != document["proof_tree_sha256"]:
        raise ProofProfileError("Sanitized proof-profile copy has an extra, missing, or modified file")
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != RECEIPT_NAME
    }
    if actual_paths != set(ALLOWED_PROOF_RELATIVE_PATHS) or proof_count != len(ALLOWED_PROOF_RELATIVE_PATHS):
        raise ProofProfileError("Static proof contains a source, credential, cache, log, or unknown file")
    requirements, safety_hash = load_safety_contract()
    if document["safety_contract_sha256"] != safety_hash:
        raise ProofProfileError("Safety contract changed after the proof-profile copy was prepared")
    source_root_supplied = Path(document["source_profile_root"])
    if source_root_supplied.is_symlink() or is_junction(source_root_supplied):
        raise ProofProfileError("Owner source profile root is redirected")
    source_root = source_root_supplied.resolve(strict=True)
    source_profile = str(document["source_profile_name"])
    expected_values = (
        expected_source_root,
        expected_profile_name,
        expected_source_count,
        expected_source_digest,
    )
    if any(value is not None for value in expected_values):
        if any(value is None for value in expected_values):
            raise ProofProfileError("Expected source identity must include root, profile, file count, and digest")
        canonical_expected_root = expected_source_root.resolve(strict=True)
        if (
            os.path.normcase(str(source_root)) != os.path.normcase(str(canonical_expected_root))
            or os.path.normcase(source_profile) != os.path.normcase(expected_profile_name)
            or document["source_profile_file_count"] != expected_source_count
            or document["source_profile_sha256"] != expected_source_digest
        ):
            raise ProofProfileError("Existing proof-profile receipt belongs to a different canonical source/profile identity")
    expected_directory_name = (
        f"proof-{source_identity(source_root, source_profile)[:16]}-"
        f"{document['source_profile_sha256'][:16]}-{document['safety_contract_sha256'][:8]}"
    )
    if root.name != expected_directory_name:
        raise ProofProfileError("Proof-profile directory does not match its canonical source/profile identity")
    source_profile_path = (source_root / source_profile).resolve(strict=True)
    if source_profile_path.parent != source_root or source_profile_path.is_symlink() or is_junction(source_profile_path):
        raise ProofProfileError("Owner source profile no longer resolves to one regular child")
    source_count, source_digest = directory_digest(source_profile_path)
    if source_count != document["source_profile_file_count"] or source_digest != document["source_profile_sha256"]:
        raise ProofProfileError("Owner source profile changed after the proof copy was prepared; prepare a new isolated copy")
    proof_profiles = root / "Profiles"
    proof_config = proof_profiles / PROOF_PROFILE_NAME / "config.ini"
    if _sha256_file(proof_config) != PROOF_CONFIG_SHA256:
        raise ProofProfileError("Static proof config contains an owner value or unreviewed setting")
    if _sha256_file(proof_profiles / "profile.ini") != PROFILE_SELECTOR_SHA256:
        raise ProofProfileError("Proof profile selector changed after preparation")
    verify_config_requirements(proof_config, requirements)
    return document


def prepare(source_root: Path, profile_name: str, destination_parent: Path) -> tuple[Path, dict[str, object]]:
    if not PROFILE_NAME_PATTERN.fullmatch(profile_name) or profile_name in {".", ".."}:
        raise ProofProfileError("Source profile name is invalid")
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if source_root.is_symlink() or is_junction(source_root):
        raise ProofProfileError("Source profile root is redirected; supply its canonical owner-local target")
    source_root = source_root.resolve(strict=True)
    source_profile = (source_root / profile_name).resolve(strict=True)
    if source_profile.parent != source_root or not source_profile.is_dir() or source_profile.is_symlink() or is_junction(source_profile):
        raise ProofProfileError("Source profile does not resolve to one regular child of the supplied profile root")
    source_config = source_profile / "config.ini"
    if not source_config.is_file() or source_config.is_symlink():
        raise ProofProfileError("Source profile config.ini is missing or redirected")
    requirements, safety_hash = load_safety_contract()
    source_count_before, source_digest_before = directory_digest(source_profile)
    if destination_parent.is_symlink() or is_junction(destination_parent):
        raise ProofProfileError("Proof-profile destination parent is redirected")
    destination_parent = destination_parent.absolute()
    identity = source_identity(source_root, profile_name)
    destination = destination_parent / f"proof-{identity[:16]}-{source_digest_before[:16]}-{safety_hash[:8]}"
    if destination.exists():
        return destination, validate_proof_root(
            destination,
            expected_parent=destination_parent,
            expected_source_root=source_root,
            expected_profile_name=profile_name,
            expected_source_count=source_count_before,
            expected_source_digest=source_digest_before,
        )
    destination_parent.mkdir(parents=True, exist_ok=True)
    stage = destination_parent / f".{destination.name}.stage-{uuid.uuid4().hex}"
    stage.mkdir(parents=False)
    try:
        proof_profiles = stage / "Profiles"
        proof_profile = proof_profiles / PROOF_PROFILE_NAME
        write_minimal_config(proof_profile / "config.ini", requirements)
        (proof_profiles / "profile.ini").write_text("[general]\ndefaultprofile=Proof\n", encoding="utf-8", newline="\n")
        source_count_after, source_digest_after = directory_digest(source_profile)
        if (source_count_after, source_digest_after) != (source_count_before, source_digest_before):
            raise ProofProfileError("Owner source profile changed while the isolated proof copy was being prepared")
        proof_count, proof_digest = directory_digest(stage)
        document = _receipt_document(
            source_root=source_root,
            source_profile=profile_name,
            source_count=source_count_before,
            source_digest=source_digest_before,
            proof_count=proof_count,
            proof_digest=proof_digest,
            safety_hash=safety_hash,
        )
        (stage / RECEIPT_NAME).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        stage.replace(destination)
        return destination, validate_proof_root(
            destination,
            expected_parent=destination_parent,
            expected_source_root=source_root,
            expected_profile_name=profile_name,
            expected_source_count=source_count_before,
            expected_source_digest=source_digest_before,
        )
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-profile-root", required=True, type=Path)
    parser.add_argument("--profile-name", required=True)
    arguments = parser.parse_args()
    try:
        path, document = prepare(arguments.source_profile_root, arguments.profile_name, fixed_proof_parent())
    except (OSError, ProofProfileError) as error:
        print(f"FAIL: {error}")
        return 1
    print(json.dumps({"proof_root": str(path), "receipt": document}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
