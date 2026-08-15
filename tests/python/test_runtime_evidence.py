from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

from evaluate_support_readiness import evaluate_readiness  # noqa: E402
from validate_runtime_evidence import validate_engine_initialization_artifact, validate_registry  # noqa: E402


NOW = datetime(2026, 8, 9, 23, 59, tzinfo=timezone.utc)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class RuntimeEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        self.temporary = tempfile.TemporaryDirectory(prefix="mybot-runtime-evidence-")
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir(parents=True)
        (self.root / "tests/evidence/runtime").mkdir(parents=True)
        (self.root / "tests/fixtures/current-client").mkdir(parents=True)
        (self.root / "artifacts/evidence").mkdir(parents=True)
        (self.root / "bin").mkdir(parents=True)

        self.binary_content = b"deterministic-autoit-binary\x00"
        self.report_content = b'{"result":"passed","redacted":true}\n'
        (self.root / "bin/MyBot.run.exe").write_bytes(self.binary_content)
        (self.root / "artifacts/evidence/report.json").write_bytes(self.report_content)
        self.catalog = {
            "schema_version": 1,
            "runtime_evidence_policy": {
                "max_age_days": 30,
                "clock_skew_minutes": 5,
                "required_environment_fields": [
                    "os",
                    "os_version",
                    "autoit_version",
                    "emulator",
                    "emulator_version",
                    "game_version",
                ],
                "environment_patterns": {"os": "(?i)^windows(?:\\s|$)"},
                "require_commit_ancestor": True,
                "require_binary_provenance": True,
                "require_tracked_artifacts": True,
                "capabilities": {
                    "orchestration.run-plan": {
                        "required_tests": [
                            {
                                "test_type": "end-to-end",
                                "required_checks": ["plan.accepted", "run.started"],
                            }
                        ]
                    }
                },
            },
            "capabilities": [
                {
                    "id": "orchestration.run-plan",
                    "status": "engine-added",
                    "runtime_evidence": "required",
                }
            ],
        }
        self.write_json("config/current-client-capabilities.json", self.catalog)
        self.write_json(
            "tests/fixtures/current-client/manifest.json",
            {"schema_version": 1, "required_fixtures": []},
        )
        self.write_json(
            "config/binary-provenance.json",
            {
                "schema_version": 1,
                "artifacts": [
                    {
                        "path": "bin/MyBot.run.exe",
                        "sha256": digest(self.binary_content),
                        "bytes": len(self.binary_content),
                    }
                ],
            },
        )
        self.git("init", "-q")
        self.git("config", "user.name", "Runtime Evidence Test")
        self.git("config", "user.email", "runtime-evidence@example.invalid")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "runtime under test")
        self.runtime_commit = self.git("rev-parse", "HEAD").stdout.strip()

        self.record = {
            "schema_version": 1,
            "evidence_id": "run-plan.valid",
            "capability_id": "orchestration.run-plan",
            "test_type": "end-to-end",
            "result": "passed",
            "captured_at": "2026-08-09T22:00:00Z",
            "commit_sha": self.runtime_commit,
            "redacted": True,
            "environment": {
                "os": "Windows",
                "os_version": "11",
                "autoit_version": "3.3.16.1",
                "emulator": "BlueStacks 5",
                "emulator_version": "5.22",
                "instance_index": 0,
                "instance_name": "Pie64",
                "game_version": "current-client",
            },
            "binary": {
                "path": "bin/MyBot.run.exe",
                "sha256": digest(self.binary_content),
                "bytes": len(self.binary_content),
            },
            "checks": [
                {"id": "plan.accepted", "result": "passed", "details": "Plan accepted by the engine."},
                {"id": "run.started", "result": "passed", "details": "Run reached the started state."},
            ],
            "reviewer": {"name": "Test Reviewer", "reviewed_at": "2026-08-09T22:05:00Z"},
            "artifact_refs": [
                {
                    "kind": "repository",
                    "path": "artifacts/evidence/report.json",
                    "sha256": digest(self.report_content),
                    "bytes": len(self.report_content),
                }
            ],
            "notes": "Synthetic deterministic evidence.",
        }
        self.save_and_commit_record()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write_json(self, relative: str, value: object) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def save_and_commit_record(self) -> None:
        self.write_json("tests/evidence/runtime/run-plan.valid.json", self.record)
        self.git("add", "tests/evidence/runtime/run-plan.valid.json")
        self.git("commit", "-q", "-m", "reviewed runtime evidence")

    def save_record(self) -> None:
        self.write_json("tests/evidence/runtime/run-plan.valid.json", self.record)

    def validate(self) -> dict[str, object]:
        return validate_registry(root=self.root, now=NOW)

    def assert_untrusted(self, expected: str) -> None:
        report = self.validate()
        self.assertTrue(report["errors"])
        self.assertFalse(report["evidence"][0]["trusted_for_readiness"])
        self.assertIn(expected, "\n".join(report["errors"]))

    def test_valid_named_instance_record_is_trusted(self) -> None:
        report = self.validate()
        self.assertEqual([], report["errors"])
        self.assertTrue(report["evidence"][0]["trusted_for_readiness"])

    def test_instance_name_is_optional_for_existing_records(self) -> None:
        del self.record["environment"]["instance_name"]
        self.save_and_commit_record()
        report = self.validate()
        self.assertEqual([], report["errors"])
        self.assertTrue(report["evidence"][0]["trusted_for_readiness"])

    def test_missing_capability_check_is_untrusted(self) -> None:
        self.record["checks"] = self.record["checks"][:1]
        self.save_record()
        self.assert_untrusted("missing required passed checks: run.started")

    def test_unaccepted_test_type_is_untrusted(self) -> None:
        self.record["test_type"] = "emulator-smoke"
        self.save_record()
        self.assert_untrusted("is not accepted for orchestration.run-plan")

    def test_stale_evidence_is_untrusted(self) -> None:
        self.record["captured_at"] = "2026-06-01T22:00:00Z"
        self.save_record()
        self.assert_untrusted("evidence is older than 30 days")

    def test_unknown_commit_is_untrusted(self) -> None:
        self.record["commit_sha"] = "a" * 40
        self.save_record()
        self.assert_untrusted("commit_sha does not resolve to a local commit")

    def test_binary_hash_must_match_commit_and_provenance(self) -> None:
        self.record["binary"]["sha256"] = "b" * 64
        self.save_record()
        self.assert_untrusted("binary.sha256 does not match")

    def test_missing_artifact_fails_closed(self) -> None:
        self.record["artifact_refs"][0]["path"] = "artifacts/evidence/missing.json"
        self.save_record()
        self.assert_untrusted("path is missing")

    def test_untracked_artifact_fails_closed(self) -> None:
        content = b"untracked but otherwise valid\n"
        path = self.root / "artifacts/evidence/untracked.json"
        path.write_bytes(content)
        self.record["artifact_refs"][0] = {
            "kind": "repository",
            "path": "artifacts/evidence/untracked.json",
            "sha256": digest(content),
            "bytes": len(content),
        }
        self.save_record()
        self.assert_untrusted("path is not committed at HEAD")

    def test_modified_evidence_record_fails_closed(self) -> None:
        self.record["notes"] = "This otherwise valid record is not committed."
        self.save_record()
        self.assert_untrusted("evidence file must match committed HEAD contents")

    def test_modified_artifact_fails_closed(self) -> None:
        (self.root / "artifacts/evidence/report.json").write_bytes(b"dirty report\n")
        self.assert_untrusted("path has uncommitted changes")

    def test_legacy_artifact_reference_cannot_prove_a_pass(self) -> None:
        self.record["artifact_refs"] = ["github-actions:unverifiable"]
        self.save_record()
        self.assert_untrusted("legacy reference without verifiable integrity")

    def test_readiness_imports_validation_and_rejects_invalid_pass(self) -> None:
        valid = evaluate_readiness(root=self.root, now=NOW)
        self.assertEqual(3, valid["schema_version"])
        self.assertEqual(1, valid["ready"])
        self.assertEqual(1, valid["exact_current_binary_records"])
        self.assertEqual(1, valid["current_binary_ready"])
        self.assertTrue(valid["results"][0]["current_binary_ready"])
        self.record["checks"] = self.record["checks"][:1]
        self.save_record()
        invalid = evaluate_readiness(root=self.root, now=NOW)
        self.assertEqual(0, invalid["ready"])
        self.assertEqual(0, invalid["exact_current_binary_records"])
        self.assertEqual(0, invalid["current_binary_ready"])
        self.assertTrue(invalid["errors"])
        self.assertIn("run-plan.valid", invalid["results"][0]["rejected_evidence"])

    def test_paired_dirty_binary_and_provenance_cannot_claim_exact_current(self) -> None:
        dirty_binary = b"new-current-binary\x00"
        (self.root / "bin/MyBot.run.exe").write_bytes(dirty_binary)
        self.write_json(
            "config/binary-provenance.json",
            {
                "schema_version": 1,
                "artifacts": [
                    {
                        "path": "bin/MyBot.run.exe",
                        "sha256": digest(dirty_binary),
                        "bytes": len(dirty_binary),
                    }
                ],
            },
        )
        report = evaluate_readiness(root=self.root, now=NOW)
        self.assertEqual(1, report["ready"])
        self.assertEqual(0, report["exact_current_binary_records"])
        self.assertEqual(0, report["current_binary_ready"])
        self.assertFalse(report["results"][0]["current_binary_ready"])
        self.assertIn(
            "missing exact-current-binary test types: end-to-end",
            report["results"][0]["current_binary_blockers"],
        )
        self.assertIn(
            "current binary provenance has uncommitted changes: config/binary-provenance.json",
            report["current_binary_validation"]["errors"],
        )
        self.assertIn(
            "current binary has uncommitted changes: bin/MyBot.run.exe",
            report["current_binary_validation"]["errors"],
        )

    def test_duplicate_evidence_ids_are_rejected_for_exact_current_reporting(self) -> None:
        self.write_json("tests/evidence/runtime/duplicate.json", self.record)
        report = evaluate_readiness(root=self.root, now=NOW)
        self.assertEqual(0, report["ready"])
        self.assertEqual(0, report["exact_current_binary_records"])
        self.assertEqual(0, report["current_binary_ready"])
        self.assertIn(
            "duplicate evidence_id cannot be evaluated as exact-current: run-plan.valid",
            report["current_binary_validation"]["errors"],
        )

    def test_required_fixture_without_mapping_is_not_ready(self) -> None:
        self.catalog["capabilities"][0]["fixture_status"] = "required"
        self.write_json("config/current-client-capabilities.json", self.catalog)
        report = evaluate_readiness(root=self.root, now=NOW)
        self.assertEqual(0, report["ready"])
        self.assertIn("required fixture mapping missing", report["results"][0]["blockers"])


class EngineInitializationArtifactContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (REPOSITORY_ROOT / "tests/evidence/runtime/orchestration.engine-initialization.pie64.20260814.json")
            .read_text(encoding="utf-8")
        )
        cls.artifact = json.loads(
            (REPOSITORY_ROOT / "tests/evidence/runtime/artifacts/check-engine.pie64.20260814.json")
            .read_text(encoding="utf-8")
        )

    def validate(self, artifact: dict[str, object]) -> str:
        return "\n".join(validate_engine_initialization_artifact(self.record, artifact))

    def test_exact_current_engine_artifact_semantics_are_valid(self) -> None:
        self.assertEqual("", self.validate(deepcopy(self.artifact)))

    def test_engine_artifact_id_must_be_dated_and_match_its_path(self) -> None:
        artifact = deepcopy(self.artifact)
        artifact["artifact_id"] = "check-engine.latest"
        self.assertIn("artifact_id is not canonical", self.validate(artifact))
        self.assertIn(
            "artifact_id does not match its repository path",
            "\n".join(
                validate_engine_initialization_artifact(
                    self.record,
                    self.artifact,
                    expected_artifact_id="check-engine.pie64.20990101",
                )
            ),
        )

    def test_engine_artifact_id_allows_collision_safe_timestamp(self) -> None:
        artifact = deepcopy(self.artifact)
        artifact["artifact_id"] = "check-engine.pie64.20260815-053443"
        self.assertEqual(
            [],
            validate_engine_initialization_artifact(
                self.record,
                artifact,
                expected_artifact_id="check-engine.pie64.20260815-053443",
            ),
        )

    def test_engine_artifact_id_rejects_malformed_timestamp(self) -> None:
        artifact = deepcopy(self.artifact)
        artifact["artifact_id"] = "check-engine.pie64.20260815-05344"
        self.assertIn("artifact_id is not canonical", self.validate(artifact))

    def test_attached_or_running_final_state_is_rejected(self) -> None:
        artifact = deepcopy(self.artifact)
        artifact["final_state"]["run_state"] = True
        artifact["final_state"]["adb_ready"] = True
        errors = self.validate(artifact)
        self.assertIn("final state was not idle, passed, and detached", errors)

    def test_missing_terminal_phase_or_exact_event_is_rejected(self) -> None:
        artifact = deepcopy(self.artifact)
        artifact["supervision"]["sampled_receipt_phases"].pop()
        artifact["events"].pop()
        errors = self.validate(artifact)
        self.assertIn("must span prepared through initialized", errors)
        self.assertIn("diagnostic event delta is not exact", errors)

    def test_configuration_or_manifest_drift_is_rejected(self) -> None:
        artifact = deepcopy(self.artifact)
        artifact["reviewed_install"]["manifest_hash_mismatches_after_check"] = 1
        artifact["preservation"]["installed_english_after_sha256"] = "0" * 64
        errors = self.validate(artifact)
        self.assertIn("manifest hash mismatches", errors)
        self.assertIn("did not preserve installed english", errors)


if __name__ == "__main__":
    unittest.main()
