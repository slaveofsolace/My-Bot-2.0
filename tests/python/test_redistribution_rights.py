import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_redistribution_rights import validate


ROOT = Path(__file__).resolve().parents[2]


class RedistributionRightsTests(unittest.TestCase):
    def fixture_root(self) -> tuple[tempfile.TemporaryDirectory, Path, dict]:
        temporary = tempfile.TemporaryDirectory(prefix="mybot-rights-")
        root = Path(temporary.name)
        (root / "config").mkdir()
        (root / "lib").mkdir()
        payload = b"fixture-managed-engine"
        (root / "lib/MyBot.run.dll").write_bytes(payload)
        artifact = {
            "path": "lib/MyBot.run.dll",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        (root / "config/binary-provenance.json").write_text(
            json.dumps({"schema_version": 1, "artifacts": [{**artifact, "provenance": {"kind": "fixture"}}]}),
            encoding="utf-8",
        )
        return temporary, root, artifact

    def test_repository_record_is_valid_but_public_release_is_blocked(self):
        errors, warnings, record = validate(ROOT)
        self.assertEqual([], errors)
        self.assertEqual("pending", record["status"])
        self.assertTrue(any("remains blocked" in warning for warning in warnings))
        errors, _, _ = validate(ROOT, require_public=True)
        self.assertTrue(any("requires a granted" in error for error in errors))

    def test_private_evidence_hash_and_public_scope_are_mandatory(self):
        temporary, root, artifact = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        record = {
            "schema_version": 1,
            "component_id": "inherited-imgloc",
            "status": "granted",
            "release_allowed": True,
            "artifact": artifact,
            "authorization": {
                "basis": "written-permission",
                "grantor_role": "verified-rights-holder",
                "authorized_at": "2026-08-20",
                "scope": ["public-binary-redistribution"],
                "private_evidence": {
                    "sha256": "a" * 64,
                    "bytes": 1234,
                    "custodian_reference": "private-rights:2026-08-20:imgloc"
                },
            },
            "review": {
                "reviewed_at": "2026-08-20",
                "reviewer_role": "release-rights-reviewer",
                "conclusion": "Written permission and the private evidence identity were reviewed."
            },
        }
        path = root / "config/redistribution-rights.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        errors, _, _ = validate(root, require_public=True)
        self.assertEqual([], errors)

        invalid = copy.deepcopy(record)
        invalid["authorization"]["private_evidence"]["sha256"] = "not-a-hash"
        invalid["authorization"]["scope"] = ["local-runtime"]
        path.write_text(json.dumps(invalid), encoding="utf-8")
        errors, _, _ = validate(root, require_public=True)
        self.assertTrue(any("private evidence SHA-256" in error for error in errors))
        self.assertTrue(any("authorization.scope" in error for error in errors))

    def test_artifact_and_provenance_must_match_exact_bytes(self):
        temporary, root, artifact = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        record = {
            "schema_version": 1,
            "component_id": "inherited-imgloc",
            "status": "pending",
            "release_allowed": False,
            "artifact": {**artifact, "sha256": "0" * 64},
            "authorization": None,
            "review": {
                "reviewed_at": "2026-08-20",
                "reviewer_role": "release-rights-reviewer",
                "conclusion": "No verified public redistribution authorization is recorded."
            },
        }
        (root / "config/redistribution-rights.json").write_text(json.dumps(record), encoding="utf-8")
        errors, _, _ = validate(root)
        self.assertTrue(any("repository binary" in error for error in errors))
        self.assertTrue(any("binary provenance" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
