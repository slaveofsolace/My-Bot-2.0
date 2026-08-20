#!/usr/bin/env python3
"""Validate redacted runtime evidence and its repository provenance.

The module intentionally has no third-party dependencies.  The readiness
evaluator imports :func:`validate_registry`, which keeps invalid records from
being interpreted differently by the two command-line tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "tests/evidence/runtime"
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
BINARY_PROVENANCE_PATH = "config/binary-provenance.json"

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_TEST_TYPES = {
    "windows-static",
    "emulator-smoke",
    "game-surface-recognition",
    "route-execution",
    "end-to-end",
}
ALLOWED_RESULTS = {"passed", "failed", "blocked"}
ENVIRONMENT_FIELDS = {
    "os",
    "os_version",
    "autoit_version",
    "emulator",
    "emulator_version",
    "instance_index",
    "instance_name",
    "game_version",
}
BASE_ENVIRONMENT_FIELDS = ENVIRONMENT_FIELDS - {"instance_name"}
REQUIRED_RECORD_FIELDS = {
    "schema_version",
    "evidence_id",
    "capability_id",
    "test_type",
    "result",
    "captured_at",
    "commit_sha",
    "redacted",
    "environment",
    "checks",
    "reviewer",
    "artifact_refs",
    "notes",
}
ALLOWED_RECORD_FIELDS = REQUIRED_RECORD_FIELDS | {"binary"}
PROHIBITED_KEYS = {
    "password",
    "token",
    "secret",
    "email",
    "player_id",
    "supercell_id",
    "account_id",
    "machine_name",
    "computer_name",
    "username",
    "serial_number",
    "ip_address",
    "chat_text",
}

ENGINE_INITIALIZATION_CAPABILITY = "orchestration.engine-initialization"
ENGINE_INITIALIZATION_ARTIFACT_PATTERN = re.compile(
    r"^check-engine\.pie64\.\d{8}(?:-\d{6})?$"
)
ENGINE_INITIALIZATION_PHASES = {
    1: "prepared",
    2: "pool-entered",
    3: "pool-returned",
    4: "max-entered",
    5: "max-returned",
    6: "android-entered",
    7: "android-returned",
    8: "gui-entered",
    9: "initialized",
}
NO_GEM_TEST_TYPES = {"end-to-end", "route-execution"}
NO_GEM_PROOF_FIELDS = {
    "schema_version",
    "balance_before",
    "balance_after",
    "balance_before_observed_at",
    "balance_after_observed_at",
    "balance_before_frame_sha256",
    "balance_after_frame_sha256",
    "gem_surface_observed",
    "gem_surface_stop_armed",
    "gem_inputs_issued",
    "gem_completion_inputs_issued",
    "purchase_inputs_issued",
    "shop_offer_inputs_issued",
    "route_inputs_issued",
    "issued_vs_confirmed_separated",
    "exact_profile_bound",
    "exact_emulator_instance_bound",
    "exact_account_bound",
    "route_return_proved",
    "capture_method",
    "source_frames_redacted_or_unretained",
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
            findings.extend(walk_keys(child, f"{prefix}{index}.") )
    return findings


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _git_text(root: Path, *args: str) -> str | None:
    result = _run_git(root, *args)
    if result.returncode:
        return None
    return result.stdout.decode("utf-8", errors="strict").strip()


def _git_blob(root: Path, commit_sha: str, relative_path: str) -> bytes | None:
    result = _run_git(root, "show", f"{commit_sha}:{relative_path}")
    return result.stdout if result.returncode == 0 else None


def _is_commit(root: Path, commit_sha: str) -> bool:
    return _run_git(root, "cat-file", "-e", f"{commit_sha}^{{commit}}").returncode == 0


def _is_ancestor_of_head(root: Path, commit_sha: str) -> bool:
    return _run_git(root, "merge-base", "--is-ancestor", commit_sha, "HEAD").returncode == 0


def _matches_head(root: Path, relative_path: str) -> bool:
    """Honor Git text filters while detecting staged or unstaged changes."""
    return _run_git(root, "diff", "--quiet", "HEAD", "--", relative_path).returncode == 0


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_relative_path(root: Path, raw_path: Any) -> tuple[str | None, Path | None]:
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        return None, None
    normalized = raw_path.strip().replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", normalized):
        return None, None
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None, None
    relative = pure.as_posix()
    candidate = (root / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, None
    return relative, candidate


def _policy_errors(catalog: Any) -> tuple[list[str], dict[str, Any], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["capability catalog must be an object"], {}, {}
    capabilities = catalog.get("capabilities")
    if not isinstance(capabilities, list):
        return ["capability catalog must contain a capabilities list"], {}, {}
    capability_ids = {
        item.get("id") for item in capabilities
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(capability_ids) != len(capabilities):
        errors.append("capability ids must be present and unique")

    policy = catalog.get("runtime_evidence_policy")
    if not isinstance(policy, dict):
        return errors + ["runtime_evidence_policy must be an object"], {}, {}
    max_age = policy.get("max_age_days")
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 1:
        errors.append("runtime_evidence_policy.max_age_days must be a positive integer")
    clock_skew = policy.get("clock_skew_minutes")
    if isinstance(clock_skew, bool) or not isinstance(clock_skew, int) or not 0 <= clock_skew <= 60:
        errors.append("runtime_evidence_policy.clock_skew_minutes must be between 0 and 60")
    required_environment = policy.get("required_environment_fields")
    if (
        not isinstance(required_environment, list)
        or not required_environment
        or len(required_environment) != len(set(required_environment))
        or not set(required_environment) <= ENVIRONMENT_FIELDS
    ):
        errors.append("runtime_evidence_policy.required_environment_fields is invalid")
    for flag in ("require_commit_ancestor", "require_binary_provenance", "require_tracked_artifacts"):
        if policy.get(flag) is not True:
            errors.append(f"runtime_evidence_policy.{flag} must be true")

    no_gem = policy.get("no_gem_contract")
    if no_gem is not None and (
        not isinstance(no_gem, dict)
        or set(no_gem) != {"effective_at", "required_check", "capabilities"}
    ):
        errors.append("runtime_evidence_policy.no_gem_contract fields do not match the contract")
    elif isinstance(no_gem, dict):
        if parse_utc(no_gem.get("effective_at")) is None:
            errors.append("runtime_evidence_policy.no_gem_contract.effective_at must be UTC")
        if no_gem.get("required_check") != "gems.not-spent":
            errors.append("runtime_evidence_policy.no_gem_contract.required_check must be gems.not-spent")
        no_gem_capabilities = no_gem.get("capabilities")
        if (
            not isinstance(no_gem_capabilities, list)
            or not no_gem_capabilities
            or len(no_gem_capabilities) != len(set(no_gem_capabilities))
            or not set(no_gem_capabilities) <= capability_ids
        ):
            errors.append("runtime_evidence_policy.no_gem_contract.capabilities is invalid")
        else:
            no_gem_capability_set = set(no_gem_capabilities)
            missing_guarded_capabilities: list[str] = []
            policy_capability_map = policy.get("capabilities")
            if not isinstance(policy_capability_map, dict):
                policy_capability_map = {}
            for capability_id, capability_policy in policy_capability_map.items():
                if capability_id == "safety.no-gem-guard" or not isinstance(capability_policy, dict):
                    continue
                required_tests = capability_policy.get("required_tests")
                if not isinstance(required_tests, list):
                    continue
                requires_untouched_balance = any(
                    isinstance(test, dict)
                    and isinstance(test.get("required_checks"), list)
                    and "gems.untouched" in test["required_checks"]
                    for test in required_tests
                )
                if requires_untouched_balance and capability_id not in no_gem_capability_set:
                    missing_guarded_capabilities.append(capability_id)
            if missing_guarded_capabilities:
                errors.append(
                    "runtime_evidence_policy.no_gem_contract is missing guarded capabilities: "
                    + ", ".join(sorted(missing_guarded_capabilities))
                )

    for field, pattern in (policy.get("environment_patterns") or {}).items():
        if field not in ENVIRONMENT_FIELDS or not isinstance(pattern, str):
            errors.append(f"runtime_evidence_policy.environment_patterns.{field} is invalid")
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"runtime_evidence_policy.environment_patterns.{field} is invalid: {exc}")

    capability_policies = policy.get("capabilities")
    if not isinstance(capability_policies, dict):
        return errors + ["runtime_evidence_policy.capabilities must be an object"], policy, {}
    missing = sorted(capability_ids - set(capability_policies))
    extra = sorted(set(capability_policies) - capability_ids)
    if missing:
        errors.append("runtime evidence policy missing capabilities: " + ", ".join(missing))
    if extra:
        errors.append("runtime evidence policy has unknown capabilities: " + ", ".join(extra))

    for capability_id, capability_policy in capability_policies.items():
        prefix = f"runtime_evidence_policy.capabilities.{capability_id}"
        if not isinstance(capability_policy, dict):
            errors.append(f"{prefix} must be an object")
            continue
        tests = capability_policy.get("required_tests")
        if not isinstance(tests, list) or not tests:
            errors.append(f"{prefix}.required_tests must be a non-empty list")
            continue
        seen_test_types: set[str] = set()
        for index, requirement in enumerate(tests):
            if not isinstance(requirement, dict) or set(requirement) != {"test_type", "required_checks"}:
                errors.append(f"{prefix}.required_tests[{index}] fields do not match the contract")
                continue
            test_type = requirement.get("test_type")
            checks = requirement.get("required_checks")
            if test_type not in ALLOWED_TEST_TYPES:
                errors.append(f"{prefix}.required_tests[{index}] has unsupported test_type")
            elif test_type in seen_test_types:
                errors.append(f"{prefix} repeats test_type {test_type}")
            seen_test_types.add(test_type)
            if (
                not isinstance(checks, list)
                or not checks
                or len(checks) != len(set(checks))
                or not all(isinstance(item, str) and ID_PATTERN.fullmatch(item) for item in checks)
            ):
                errors.append(f"{prefix}.required_tests[{index}].required_checks is invalid")
        for field, pattern in (capability_policy.get("environment_patterns") or {}).items():
            if field not in ENVIRONMENT_FIELDS or not isinstance(pattern, str):
                errors.append(f"{prefix}.environment_patterns.{field} is invalid")
                continue
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{prefix}.environment_patterns.{field} is invalid: {exc}")
    return errors, policy, capability_policies


def _integrity_object_errors(
    value: Any,
    *,
    prefix: str,
    require_kind: bool,
) -> tuple[list[str], str | None, str | None, int | None]:
    errors: list[str] = []
    expected_fields = {"path", "sha256", "bytes"} | ({"kind"} if require_kind else set())
    if not isinstance(value, dict) or set(value) != expected_fields:
        return [f"{prefix} fields do not match the integrity contract"], None, None, None
    if require_kind and value.get("kind") != "repository":
        errors.append(f"{prefix}.kind must be repository")
    raw_path = value.get("path")
    digest = value.get("sha256")
    byte_count = value.get("bytes")
    if not isinstance(raw_path, str) or not raw_path.strip():
        errors.append(f"{prefix}.path must be non-empty")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        errors.append(f"{prefix}.sha256 must be 64 lowercase hexadecimal characters")
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
        errors.append(f"{prefix}.bytes must be a positive integer")
    return errors, raw_path if isinstance(raw_path, str) else None, digest if isinstance(digest, str) else None, byte_count if isinstance(byte_count, int) and not isinstance(byte_count, bool) else None


def _verify_repository_artifact(root: Path, value: Any, prefix: str) -> list[str]:
    errors, raw_path, digest, byte_count = _integrity_object_errors(value, prefix=prefix, require_kind=True)
    if errors or raw_path is None or digest is None or byte_count is None:
        return errors
    relative, resolved = _safe_relative_path(root, raw_path)
    if relative is None or resolved is None:
        return [f"{prefix}.path must stay inside the repository"]
    if not resolved.is_file():
        return [f"{prefix}.path is missing: {relative}"]
    committed = _git_blob(root, "HEAD", relative)
    if committed is None:
        return [f"{prefix}.path is not committed at HEAD: {relative}"]
    if not _matches_head(root, relative):
        errors.append(f"{prefix}.path has uncommitted changes: {relative}")
    if len(committed) != byte_count:
        errors.append(f"{prefix}.bytes does not match {relative}")
    if _sha256(committed) != digest:
        errors.append(f"{prefix}.sha256 does not match {relative}")
    return errors


def validate_no_gem_proof(value: Any) -> list[str]:
    """Validate a future mutating-route artifact's explicit no-spend proof."""

    if not isinstance(value, dict) or set(value) != NO_GEM_PROOF_FIELDS:
        return ["no_gem_proof fields do not match the closed contract"]
    errors: list[str] = []
    if value.get("schema_version") != 2:
        errors.append("no_gem_proof.schema_version must be 2")
    before = value.get("balance_before")
    after = value.get("balance_after")
    if isinstance(before, bool) or not isinstance(before, int) or before < 0:
        errors.append("no_gem_proof.balance_before must be a non-negative integer")
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        errors.append("no_gem_proof.balance_after must be a non-negative integer")
    if isinstance(before, int) and not isinstance(before, bool) and isinstance(after, int) and not isinstance(after, bool) and after < before:
        errors.append("no_gem_proof shows a decreased gem balance")
    before_at = parse_utc(value.get("balance_before_observed_at"))
    after_at = parse_utc(value.get("balance_after_observed_at"))
    if before_at is None:
        errors.append("no_gem_proof.balance_before_observed_at must be UTC")
    if after_at is None:
        errors.append("no_gem_proof.balance_after_observed_at must be UTC")
    if before_at is not None and after_at is not None and after_at < before_at:
        errors.append("no_gem_proof balance observations are out of order")
    for field in ("balance_before_frame_sha256", "balance_after_frame_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            errors.append(f"no_gem_proof.{field} must be a SHA-256 digest")
    if value.get("gem_surface_observed") is not False:
        errors.append("no_gem_proof must show no gem surface")
    if value.get("gem_surface_stop_armed") is not True:
        errors.append("no_gem_proof must show the gem-surface hard stop was armed")
    if value.get("gem_inputs_issued") != 0:
        errors.append("no_gem_proof must show zero gem inputs")
    if value.get("gem_completion_inputs_issued") != 0:
        errors.append("no_gem_proof must show zero gem-completion inputs")
    if value.get("purchase_inputs_issued") != 0:
        errors.append("no_gem_proof must show zero purchase inputs")
    if value.get("shop_offer_inputs_issued") != 0:
        errors.append("no_gem_proof must show zero shop-offer inputs")
    route_inputs = value.get("route_inputs_issued")
    if isinstance(route_inputs, bool) or not isinstance(route_inputs, int) or route_inputs < 0:
        errors.append("no_gem_proof.route_inputs_issued must be a non-negative integer")
    for field, description in (
        ("issued_vs_confirmed_separated", "issued and confirmed receipts"),
        ("exact_profile_bound", "exact profile binding"),
        ("exact_emulator_instance_bound", "exact emulator-instance binding"),
        ("exact_account_bound", "exact account binding"),
        ("route_return_proved", "route return proof"),
    ):
        if value.get(field) is not True:
            errors.append(f"no_gem_proof must show {description}")
    if value.get("capture_method") not in {"clean-room-recognizer", "reviewed-redacted-frames"}:
        errors.append("no_gem_proof.capture_method is unsupported")
    if value.get("source_frames_redacted_or_unretained") is not True:
        errors.append("no_gem_proof must preserve the privacy boundary")
    return errors


def _verify_no_gem_artifact(root: Path, artifact_refs: list[Any]) -> list[str]:
    proofs: list[Any] = []
    for item in artifact_refs:
        if not isinstance(item, dict) or item.get("kind") != "repository":
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.lower().endswith(".json"):
            continue
        relative, _ = _safe_relative_path(root, raw_path)
        if relative is None:
            continue
        committed = _git_blob(root, "HEAD", relative)
        if committed is None:
            continue
        try:
            artifact = json.loads(committed.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(artifact, dict) and "no_gem_proof" in artifact:
            proofs.append(artifact["no_gem_proof"])
    if len(proofs) != 1:
        return ["post-contract mutating evidence must reference exactly one semantic no_gem_proof"]
    return validate_no_gem_proof(proofs[0])


def validate_engine_initialization_artifact(
    record: Any,
    artifact: Any,
    *,
    expected_artifact_id: str | None = None,
) -> list[str]:
    """Validate the semantic claims behind the no-input engine-init receipt.

    Generic evidence validation proves Git, hash, binary, reviewer, and policy
    integrity.  This capability also needs a mechanical check that the retained
    artifact actually says the backend stayed idle and detached, the supervisor
    finalized sequence 9, and the two diagnostic events are exact.
    """

    errors: list[str] = []
    if not isinstance(record, dict) or not isinstance(artifact, dict):
        return ["engine initialization artifact and record must be objects"]
    artifact_schema = artifact.get("schema_version")
    if artifact_schema not in {1, 2}:
        errors.append("engine initialization artifact schema_version must be 1 or 2")
    artifact_id = artifact.get("artifact_id")
    if not isinstance(artifact_id, str) or not ENGINE_INITIALIZATION_ARTIFACT_PATTERN.fullmatch(artifact_id):
        errors.append("engine initialization artifact_id is not canonical")
    elif expected_artifact_id is not None and artifact_id != expected_artifact_id:
        errors.append("engine initialization artifact_id does not match its repository path")
    if artifact.get("redacted") is not True:
        errors.append("engine initialization artifact must be redacted")
    if artifact.get("commit_sha") != record.get("commit_sha"):
        errors.append("engine initialization artifact commit does not match its record")
    if artifact.get("binary") != record.get("binary"):
        errors.append("engine initialization artifact binary does not match its record")
    if artifact.get("environment") != record.get("environment"):
        errors.append("engine initialization artifact environment does not match its record")

    install = artifact.get("reviewed_install")
    if not isinstance(install, dict):
        errors.append("engine initialization artifact reviewed_install must be an object")
    else:
        if install.get("source_commit") != record.get("commit_sha"):
            errors.append("reviewed install source commit does not match the evidence commit")
        if not isinstance(install.get("manifest_records"), int) or install.get("manifest_records", 0) < 1:
            errors.append("reviewed install must retain a positive manifest record count")
        if install.get("manifest_missing_after_check") != 0:
            errors.append("reviewed install has missing manifest records after the check")
        if artifact_schema == 2 and install.get("manifest_size_mismatches_after_check") != 0:
            errors.append("reviewed install has manifest size mismatches after the check")
        if install.get("manifest_hash_mismatches_after_check") != 0:
            errors.append("reviewed install has manifest hash mismatches after the check")
        for field in ("release_manifest_sha256", "package_sha256"):
            if not isinstance(install.get(field), str) or not SHA256_PATTERN.fullmatch(install[field]):
                errors.append(f"reviewed install {field} must be a SHA-256 digest")

    command = artifact.get("command")
    if not isinstance(command, dict) or any(
        (
            command.get("action") != "check-engine",
            command.get("http_status") != 202,
            command.get("accepted") is not True,
            command.get("native_command_queued") is not True,
            command.get("request_identifier_retained") is not False,
        )
    ):
        errors.append("engine initialization command receipt is not an accepted redacted check-engine command")

    initial = artifact.get("initial_state")
    required_initial = {
        "state": "idle",
        "run_state": False,
        "plan_active": False,
        "engine_available": True,
        "engine_probe_state": "not-run",
        "emulator_attached": False,
        "window_attached": False,
        "adb_ready": False,
        "game_ready": False,
    }
    if not isinstance(initial, dict) or any(initial.get(key) != value for key, value in required_initial.items()):
        errors.append("engine initialization baseline was not idle, detached, and plan-free")
    elif artifact_schema == 1 and initial.get("plan_exists") is not False:
        errors.append("schema-1 engine initialization baseline must temporarily omit the saved plan")
    elif artifact_schema == 2 and not isinstance(initial.get("plan_exists"), bool):
        errors.append("schema-2 engine initialization baseline must record whether a saved plan exists")

    supervision = artifact.get("supervision")
    if not isinstance(supervision, dict):
        errors.append("engine initialization supervision receipt must be an object")
    else:
        required_supervision = {
            "lineage_verified": True,
            "same_backend_identity_before_and_after": True,
            "terminal_sequence": 9,
            "terminal_phase": "initialized",
            "finalization_outcome": "initialized",
            "receipt_removed": True,
            "cancel_removed": True,
            "command_removed": True,
        }
        if artifact_schema == 2:
            required_supervision["request_receipt_identity_matched"] = True
        if any(supervision.get(key) != value for key, value in required_supervision.items()):
            errors.append("engine initialization supervisor did not finalize the exact backend at initialized sequence 9")
        samples = supervision.get("sampled_receipt_phases")
        if not isinstance(samples, list) or not samples:
            errors.append("engine initialization receipt samples are missing")
        else:
            observed: list[tuple[int, str]] = []
            for sample in samples:
                if not isinstance(sample, dict) or set(sample) != {"sequence", "phase"}:
                    errors.append("engine initialization receipt sample fields are invalid")
                    continue
                sequence = sample.get("sequence")
                phase = sample.get("phase")
                if not isinstance(sequence, int) or ENGINE_INITIALIZATION_PHASES.get(sequence) != phase:
                    errors.append("engine initialization receipt sample has an invalid phase/sequence pair")
                    continue
                observed.append((sequence, phase))
            sequences = [sequence for sequence, _ in observed]
            if sequences != sorted(set(sequences)):
                errors.append("engine initialization receipt samples are not strictly monotonic")
            if artifact_schema == 2:
                expected_observed = list(ENGINE_INITIALIZATION_PHASES.items())
                if observed != expected_observed:
                    errors.append("engine initialization receipt samples must contain the complete phase sequence in exact order")
            elif not observed or observed[0] != (1, "prepared") or observed[-1] != (9, "initialized"):
                errors.append("engine initialization receipt samples must span prepared through initialized")

    final = artifact.get("final_state")
    required_final = {
        "state": "idle",
        "run_state": False,
        "plan_active": False,
        "session_cleared": True,
        "engine_available": True,
        "engine_probe_state": "passed",
        "last_command": "check-engine",
        "last_outcome": "passed",
        "emulator_attached": False,
        "window_attached": False,
        "adb_ready": False,
        "game_ready": False,
    }
    if not isinstance(final, dict) or any(final.get(key) != value for key, value in required_final.items()):
        errors.append("engine initialization final state was not idle, passed, and detached")

    events = artifact.get("events")
    expected_events = [(1, "engine.check.started"), (2, "engine.check.passed")]
    actual_events = []
    if isinstance(events, list):
        actual_events = [
            (item.get("sequence"), item.get("type"))
            for item in events
            if isinstance(item, dict)
        ]
    if not isinstance(events, list) or len(events) != 2 or actual_events != expected_events:
        errors.append("engine initialization diagnostic event delta is not exact")

    preservation = artifact.get("preservation")
    if not isinstance(preservation, dict):
        errors.append("engine initialization preservation receipt must be an object")
    else:
        for prefix in ("external_profile", "installed_english"):
            before = preservation.get(f"{prefix}_before_sha256")
            after = preservation.get(f"{prefix}_after_sha256")
            if not isinstance(before, str) or not SHA256_PATTERN.fullmatch(before) or before != after:
                errors.append(f"engine initialization did not preserve {prefix.replace('_', ' ')}")
        if artifact_schema == 1:
            if preservation.get("plan_absent_before_and_after") is not True:
                errors.append("schema-1 engine initialization did not preserve the absent plan state")
        elif artifact_schema == 2:
            manifest_before = preservation.get("release_manifest_before_sha256")
            manifest_after = preservation.get("release_manifest_after_sha256")
            if (
                not isinstance(manifest_before, str)
                or not SHA256_PATTERN.fullmatch(manifest_before)
                or manifest_before != manifest_after
            ):
                errors.append("schema-2 engine initialization did not preserve the release manifest")
            if preservation.get("emulator_process_identity_preserved") is not True:
                errors.append("schema-2 engine initialization did not preserve emulator process identity")
            if preservation.get("adb_daemon_identity_preserved") is not True:
                errors.append("schema-2 engine initialization did not preserve ADB process identity")
            plan_exists = initial.get("plan_exists") if isinstance(initial, dict) else None
            if plan_exists is True:
                plan_before = preservation.get("saved_plan_before_sha256")
                plan_after = preservation.get("saved_plan_after_sha256")
                if (
                    not isinstance(plan_before, str)
                    or not SHA256_PATTERN.fullmatch(plan_before)
                    or plan_before != plan_after
                ):
                    errors.append("schema-2 engine initialization did not preserve the saved plan")
                if "plan_absent_before_and_after" in preservation:
                    errors.append("schema-2 saved-plan evidence cannot also claim the plan was absent")
            elif plan_exists is False:
                if preservation.get("plan_absent_before_and_after") is not True:
                    errors.append("schema-2 engine initialization did not preserve the absent plan state")
                if "saved_plan_before_sha256" in preservation or "saved_plan_after_sha256" in preservation:
                    errors.append("schema-2 absent-plan evidence cannot contain saved-plan digests")

    assertions = artifact.get("assertions")
    required_true = {
        "check_engine_accepted",
        "backend_identity_preserved",
        "engine_initialized",
        "idle_restored",
        "supervisor_finalized",
        "diagnostic_events_exact",
        "game_input_absent",
        "configuration_preserved",
    }
    if artifact_schema == 2:
        required_true.update({"warning_html_absent", "browser_child_absent"})
    if not isinstance(assertions, dict) or any(assertions.get(key) is not True for key in required_true):
        errors.append("engine initialization artifact assertions are incomplete")
    elif assertions.get("new_adb_processes") != 0:
        errors.append("engine initialization artifact observed a new ADB process")
    elif artifact_schema == 2 and assertions.get("outbound_backend_connections") != 0:
        errors.append("schema-2 engine initialization artifact observed an outbound backend connection")
    privacy = artifact.get("privacy")
    if not isinstance(privacy, str) or len(privacy.strip()) < 20:
        errors.append("engine initialization artifact privacy statement is missing")
    prohibited = walk_keys(artifact)
    if prohibited:
        errors.append("engine initialization artifact contains prohibited keys: " + ", ".join(prohibited))
    return errors


def _verify_engine_initialization_artifact(root: Path, record: dict[str, Any], artifact_refs: list[Any]) -> list[str]:
    candidates = [
        item for item in artifact_refs
        if isinstance(item, dict)
        and ENGINE_INITIALIZATION_ARTIFACT_PATTERN.fullmatch(
            PurePosixPath(str(item.get("path", "")).replace("\\", "/")).stem
        )
    ]
    if len(candidates) != 1:
        return ["engine initialization evidence must reference its one canonical semantic artifact"]
    relative, _ = _safe_relative_path(root, candidates[0].get("path"))
    if relative is None:
        return ["engine initialization artifact path must stay inside the repository"]
    blob = _git_blob(root, "HEAD", relative)
    if blob is None:
        return ["engine initialization artifact is not committed at HEAD"]
    try:
        artifact = json.loads(blob.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ["engine initialization artifact is not valid UTF-8 JSON"]
    expected_artifact_id = PurePosixPath(relative).stem
    return validate_engine_initialization_artifact(
        record,
        artifact,
        expected_artifact_id=expected_artifact_id,
    )


def _verify_binary_at_commit(root: Path, value: Any, commit_sha: str) -> list[str]:
    errors, raw_path, digest, byte_count = _integrity_object_errors(value, prefix="binary", require_kind=False)
    if errors or raw_path is None or digest is None or byte_count is None:
        return errors
    relative, _ = _safe_relative_path(root, raw_path)
    if relative is None:
        return ["binary.path must stay inside the repository"]
    blob = _git_blob(root, commit_sha, relative)
    if blob is None:
        return [f"binary.path is not tracked at commit {commit_sha}: {relative}"]
    if len(blob) != byte_count:
        errors.append(f"binary.bytes does not match {relative} at commit {commit_sha}")
    if _sha256(blob) != digest:
        errors.append(f"binary.sha256 does not match {relative} at commit {commit_sha}")

    provenance_blob = _git_blob(root, commit_sha, BINARY_PROVENANCE_PATH)
    if provenance_blob is None:
        errors.append(f"binary provenance is missing at commit {commit_sha}")
        return errors
    try:
        provenance = json.loads(provenance_blob.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"binary provenance is invalid at commit {commit_sha}")
        return errors
    matches = [
        item for item in provenance.get("artifacts", [])
        if isinstance(item, dict) and str(item.get("path", "")).replace("\\", "/") == relative
    ]
    if len(matches) != 1:
        errors.append(f"binary.path has no unique provenance record at commit {commit_sha}: {relative}")
    elif matches[0].get("sha256") != digest or matches[0].get("bytes") != byte_count:
        errors.append(f"binary integrity does not match provenance at commit {commit_sha}: {relative}")
    return errors


def _required_test_map(capability_policy: dict[str, Any]) -> dict[str, set[str]]:
    return {
        item["test_type"]: set(item["required_checks"])
        for item in capability_policy.get("required_tests", [])
        if isinstance(item, dict)
        and item.get("test_type") in ALLOWED_TEST_TYPES
        and isinstance(item.get("required_checks"), list)
    }


def validate_registry(
    *,
    root: Path = ROOT,
    evidence_dir: Path | None = None,
    capabilities_path: Path | None = None,
    now: datetime | None = None,
    require_capabilities: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a complete validation report; only trusted records count as passes."""

    root = root.resolve()
    evidence_dir = (evidence_dir or root / "tests/evidence/runtime").resolve()
    capabilities_path = (capabilities_path or root / "config/current-client-capabilities.json").resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    errors: list[str] = []
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    passed_by_capability: dict[str, int] = {}

    try:
        catalog = load(capabilities_path)
    except (OSError, json.JSONDecodeError) as exc:
        catalog = {}
        errors.append(f"capability catalog is invalid: {exc}")
    policy_errors, policy, capability_policies = _policy_errors(catalog)
    errors.extend(policy_errors)
    capability_ids = {
        item.get("id") for item in catalog.get("capabilities", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    max_age_days = policy.get("max_age_days", 0) if isinstance(policy, dict) else 0
    clock_skew_minutes = policy.get("clock_skew_minutes", 0) if isinstance(policy, dict) else 0
    required_environment = set(policy.get("required_environment_fields", [])) if isinstance(policy, dict) else set()
    global_environment_patterns = policy.get("environment_patterns", {}) if isinstance(policy, dict) else {}
    seen_evidence_ids: set[str] = set()

    if not evidence_dir.is_dir():
        errors.append(f"runtime evidence directory is missing: {evidence_dir}")
        evidence_paths: list[Path] = []
    else:
        evidence_paths = sorted(evidence_dir.glob("*.json"))

    for path in evidence_paths:
        try:
            record = load(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            records.append({
                "file": path.name,
                "evidence_id": "",
                "capability_id": None,
                "test_type": None,
                "result": None,
                "valid": False,
                "trusted_for_readiness": False,
                "errors": [f"invalid JSON: {exc}"],
            })
            continue

        evidence_id = record.get("evidence_id", "") if isinstance(record, dict) else ""
        prefix = evidence_id or path.stem
        record_errors: list[str] = []
        if not isinstance(record, dict):
            record_errors.append("record must be an object")
            record = {}
        relative_record, _ = _safe_relative_path(root, str(path.relative_to(root)).replace("\\", "/"))
        committed_record = _git_blob(root, "HEAD", relative_record) if relative_record is not None else None
        if committed_record is None:
            record_errors.append("evidence file must be committed at HEAD")
        elif not _matches_head(root, relative_record):
            record_errors.append("evidence file must match committed HEAD contents")
        missing_fields = sorted(REQUIRED_RECORD_FIELDS - set(record))
        extra_fields = sorted(set(record) - ALLOWED_RECORD_FIELDS)
        if missing_fields:
            record_errors.append("missing fields: " + ", ".join(missing_fields))
        if extra_fields:
            record_errors.append("unexpected fields: " + ", ".join(extra_fields))
        if record.get("schema_version") != 1:
            record_errors.append("schema_version must be 1")
        if not isinstance(evidence_id, str) or not ID_PATTERN.fullmatch(evidence_id):
            record_errors.append("invalid evidence_id")
        elif path.name != f"{evidence_id}.json":
            record_errors.append("file name must match evidence_id")
        elif evidence_id in seen_evidence_ids:
            record_errors.append("evidence_id must be unique")
        seen_evidence_ids.add(evidence_id)

        capability_id = record.get("capability_id")
        capability_policy = capability_policies.get(capability_id, {})
        if capability_id not in capability_ids:
            record_errors.append(f"unknown capability_id {capability_id!r}")
        test_type = record.get("test_type")
        if test_type not in ALLOWED_TEST_TYPES:
            record_errors.append(f"unsupported test_type {test_type!r}")
        required_tests = _required_test_map(capability_policy)
        if capability_id in capability_ids and test_type in ALLOWED_TEST_TYPES and test_type not in required_tests:
            record_errors.append(f"test_type {test_type!r} is not accepted for {capability_id}")
        result = record.get("result")
        if result not in ALLOWED_RESULTS:
            record_errors.append(f"unsupported result {result!r}")
        captured_at = parse_utc(record.get("captured_at"))
        if captured_at is None:
            record_errors.append("captured_at must be an ISO-8601 UTC timestamp ending in Z")
        commit_sha = record.get("commit_sha")
        if not isinstance(commit_sha, str) or not SHA_PATTERN.fullmatch(commit_sha):
            record_errors.append("commit_sha must be 40 lowercase hexadecimal characters")
        if record.get("redacted") is not True:
            record_errors.append("redacted must be true")

        prohibited = walk_keys(record)
        if prohibited:
            record_errors.append("prohibited fields: " + ", ".join(prohibited))

        environment = record.get("environment")
        if not isinstance(environment, dict):
            record_errors.append("environment must be an object")
            environment = {}
        else:
            missing_environment = sorted(BASE_ENVIRONMENT_FIELDS - set(environment))
            extra_environment = sorted(set(environment) - ENVIRONMENT_FIELDS)
            if missing_environment:
                record_errors.append("environment missing fields: " + ", ".join(missing_environment))
            if extra_environment:
                record_errors.append("environment has unexpected fields: " + ", ".join(extra_environment))
            instance_index = environment.get("instance_index")
            if isinstance(instance_index, bool) or not isinstance(instance_index, int) or not 0 <= instance_index <= 1000:
                record_errors.append("environment.instance_index must be an integer between 0 and 1000")
            if "instance_name" in environment and (
                not isinstance(environment["instance_name"], str)
                or not 1 <= len(environment["instance_name"].strip()) <= 80
            ):
                record_errors.append("environment.instance_name must be a non-empty string up to 80 characters")
            for field in BASE_ENVIRONMENT_FIELDS - {"instance_index"}:
                value = environment.get(field)
                if not isinstance(value, str) or len(value.strip()) > 80:
                    record_errors.append(f"environment.{field} must be a string up to 80 characters")
            if result == "passed":
                for field in sorted(required_environment):
                    value = environment.get(field)
                    if not isinstance(value, str) or not value.strip():
                        record_errors.append(f"passed evidence requires environment.{field}")
                patterns = dict(global_environment_patterns) if isinstance(global_environment_patterns, dict) else {}
                capability_patterns = capability_policy.get("environment_patterns", {}) if isinstance(capability_policy, dict) else {}
                if isinstance(capability_patterns, dict):
                    patterns.update(capability_patterns)
                for field, pattern in patterns.items():
                    value = environment.get(field)
                    if isinstance(pattern, str) and (not isinstance(value, str) or re.search(pattern, value) is None):
                        record_errors.append(f"environment.{field} does not satisfy the {capability_id} policy")

        checks = record.get("checks")
        if not isinstance(checks, list) or not checks:
            record_errors.append("checks must be a non-empty list")
            checks = []
        seen_checks: set[str] = set()
        passed_checks: set[str] = set()
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
            elif check.get("result") == "passed" and isinstance(check_id, str):
                passed_checks.add(check_id)
            if not isinstance(check.get("details"), str) or not 5 <= len(check["details"].strip()) <= 2000:
                record_errors.append(f"check[{index}] details must contain 5 to 2000 characters")

        reviewer = record.get("reviewer")
        if not isinstance(reviewer, dict) or set(reviewer) != {"name", "reviewed_at"}:
            record_errors.append("reviewer fields do not match the contract")
            reviewer = {}
        reviewed_at = parse_utc(reviewer.get("reviewed_at"))
        if reviewer and (not isinstance(reviewer.get("name"), str) or len(reviewer["name"].strip()) > 128):
            record_errors.append("reviewer.name must be a string up to 128 characters")

        artifact_refs = record.get("artifact_refs")
        if not isinstance(artifact_refs, list):
            record_errors.append("artifact_refs must be a list")
            artifact_refs = []
        canonical_refs = [json.dumps(item, sort_keys=True) for item in artifact_refs]
        if len(canonical_refs) != len(set(canonical_refs)):
            record_errors.append("artifact_refs must be unique")
        for index, artifact in enumerate(artifact_refs):
            if isinstance(artifact, str):
                if len(artifact.strip()) < 3:
                    record_errors.append(f"artifact_refs[{index}] is too short")
                if result == "passed":
                    record_errors.append(f"artifact_refs[{index}] is a legacy reference without verifiable integrity")
            else:
                record_errors.extend(_verify_repository_artifact(root, artifact, f"artifact_refs[{index}]"))
        if capability_id == ENGINE_INITIALIZATION_CAPABILITY:
            record_errors.extend(_verify_engine_initialization_artifact(root, record, artifact_refs))
        no_gem_contract = policy.get("no_gem_contract", {}) if isinstance(policy, dict) else {}
        no_gem_effective = parse_utc(no_gem_contract.get("effective_at")) if isinstance(no_gem_contract, dict) else None
        no_gem_capabilities = set(no_gem_contract.get("capabilities", [])) if isinstance(no_gem_contract, dict) else set()
        no_gem_required_check = no_gem_contract.get("required_check") if isinstance(no_gem_contract, dict) else None
        requires_no_gem = (
            result == "passed"
            and test_type in NO_GEM_TEST_TYPES
            and capability_id in no_gem_capabilities
            and captured_at is not None
            and no_gem_effective is not None
            and captured_at >= no_gem_effective
        )
        if requires_no_gem:
            if no_gem_required_check not in passed_checks:
                record_errors.append(f"post-contract mutating evidence requires passed check {no_gem_required_check}")
            record_errors.extend(_verify_no_gem_artifact(root, artifact_refs))

        if result == "passed":
            skew = timedelta(minutes=clock_skew_minutes)
            if captured_at is not None:
                if captured_at > now + skew:
                    record_errors.append("captured_at is in the future")
                elif isinstance(max_age_days, int) and max_age_days > 0 and now - captured_at > timedelta(days=max_age_days):
                    record_errors.append(f"evidence is older than {max_age_days} days")
            if any(check.get("result") != "passed" for check in checks if isinstance(check, dict)):
                record_errors.append("passed evidence requires every check to pass")
            required_checks = required_tests.get(test_type, set())
            missing_checks = sorted(required_checks - passed_checks)
            if missing_checks:
                record_errors.append("missing required passed checks: " + ", ".join(missing_checks))
            if not isinstance(reviewer.get("name"), str) or not reviewer["name"].strip() or reviewed_at is None:
                record_errors.append("passed evidence requires reviewer name and UTC reviewed_at")
            elif captured_at is not None and reviewed_at < captured_at:
                record_errors.append("reviewer.reviewed_at cannot precede captured_at")
            elif reviewed_at > now + skew:
                record_errors.append("reviewer.reviewed_at is in the future")
            if not artifact_refs:
                record_errors.append("passed evidence requires at least one artifact reference")
            if isinstance(commit_sha, str) and SHA_PATTERN.fullmatch(commit_sha):
                if not _is_commit(root, commit_sha):
                    record_errors.append(f"commit_sha does not resolve to a local commit: {commit_sha}")
                elif policy.get("require_commit_ancestor") is True and not _is_ancestor_of_head(root, commit_sha):
                    record_errors.append(f"commit_sha is not an ancestor of HEAD: {commit_sha}")
                elif policy.get("require_binary_provenance") is True:
                    record_errors.extend(_verify_binary_at_commit(root, record.get("binary"), commit_sha))
            elif policy.get("require_binary_provenance") is True:
                record_errors.append("passed evidence requires a verifiable binary")

        valid = not record_errors and not policy_errors
        trusted = valid and result == "passed"
        if record_errors:
            errors.extend(f"{prefix}: {message}" for message in record_errors)
        if trusted:
            passed_by_capability[capability_id] = passed_by_capability.get(capability_id, 0) + 1
        records.append({
            "file": path.name,
            "evidence_id": evidence_id,
            "capability_id": capability_id,
            "test_type": test_type,
            "result": result,
            "valid": valid,
            "trusted_for_readiness": trusted,
            "errors": record_errors,
        })

    for capability_id in require_capabilities:
        if capability_id not in capability_ids:
            errors.append(f"required capability does not exist: {capability_id}")
        elif passed_by_capability.get(capability_id, 0) < 1:
            errors.append(f"no trusted passing runtime evidence exists for required capability: {capability_id}")

    if not records:
        warnings.append("no runtime evidence records are committed yet")

    return {
        "schema_version": 2,
        "records": len(records),
        "passing_capabilities": passed_by_capability,
        "errors": errors,
        "warnings": warnings,
        "evidence": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-capability", action="append", default=[])
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
    report = validate_registry(now=now, require_capabilities=args.require_capability)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
