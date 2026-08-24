from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_installed_acceptance_ledger as ledger_tool  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstalledAcceptanceLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mybot-installed-ledger-")
        self.root = Path(self.temporary.name)
        self.ui_proof = self.root / "ui-proof.json"
        self.passive_proof = self.root / "passive-proof.json"
        self.receipt = self.root / "receipt.md"
        self.readiness_path = self.root / "readiness.json"
        self.ui_proof.write_text(
            json.dumps(
                {
                    "final_status": {
                        "document": {
                            "last_command": "launch-game",
                            "last_outcome": "passed",
                            "last_command_message": "Daily Reward overlay recognized at (445,485)",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        self.passive_proof.write_text(
            json.dumps(
                {
                    "final_status": {
                        "document": {
                            "last_command": "launch-game",
                            "last_outcome": "passed",
                        }
                    },
                    "adb_package": {"version_name": "18.400.22"},
                }
            ),
            encoding="utf-8",
        )
        self.receipt.write_text("receipt\n", encoding="utf-8")
        self.readiness = {
            "capabilities": 8,
            "ready": 2,
            "not_ready": 6,
            "current_binary_ready": 0,
            "current_binary_not_ready": 8,
            "results": [
                self.row("emulator.bluestacks5", current_blockers=["missing exact-current-binary test types: emulator-smoke"]),
                self.row("events.daily-reward", blockers=["missing trusted test types: end-to-end"]),
                self.row("village.collectors", passing=["collectors.historical"]),
                self.row("safety.no-gem-guard", blockers=["unverified fixtures: safety.gem-window"]),
                self.row("battle.revenge", blockers=["missing trusted test types: route-execution"]),
                self.row("army.training", blockers=["missing trusted test types: end-to-end"]),
                self.row("village.treasury", blockers=["unverified fixtures: home.treasury.full"]),
                self.row("runtime.recovery", current_blockers=["missing exact-current-binary test types: end-to-end"]),
            ],
        }
        self.readiness_path.write_text(json.dumps(self.readiness), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def row(
        capability_id: str,
        *,
        blockers: list[str] | None = None,
        current_blockers: list[str] | None = None,
        passing: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "id": capability_id,
            "declared_status": "engine-added",
            "ready_for_support_review": not blockers,
            "current_binary_ready": False,
            "verified_fixtures": [],
            "passing_evidence": passing or [],
            "blockers": blockers or [],
            "current_binary_blockers": current_blockers or blockers or [],
        }

    def build(self) -> dict[str, object]:
        return ledger_tool.build_ledger(
            readiness=self.readiness,
            ui_proof=json.loads(self.ui_proof.read_text(encoding="utf-8")),
            passive_proof=json.loads(self.passive_proof.read_text(encoding="utf-8")),
            source_master="96bd85517a918f8f6826efc02bfcfcc113dd817d",
            local_binary_commit="d6b308ef1e48032862e062c1887568559591bb5a",
            package_sha256="b" * 64,
            installed_manifest_sha256="c" * 64,
            installed_entrypoint_sha256="d" * 64,
            proof_paths={
                "actual_web_ui_launch_game": self.ui_proof,
                "passive_installed_launch_game": self.passive_proof,
                "support_readiness": self.readiness_path,
                "receipt": self.receipt,
            },
            now=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
        )

    def test_builds_truthful_statuses_without_live_claims(self) -> None:
        ledger = self.build()
        statuses = {item["capability_id"]: item["status"] for item in ledger["capabilities"]}
        self.assertEqual("RUNTIME_PASS", statuses["emulator.bluestacks5"])
        self.assertEqual("RUNTIME_PASS", statuses["events.daily-reward"])
        self.assertEqual("DETERMINISTIC_PASS", statuses["village.collectors"])
        self.assertEqual("DETERMINISTIC_PASS", statuses["safety.no-gem-guard"])
        self.assertEqual("RIGHTS_BLOCKED", statuses["battle.revenge"])
        self.assertEqual("UNSAFE_BLOCKED", statuses["army.training"])
        self.assertEqual("STATE_BLOCKED", statuses["village.treasury"])
        self.assertEqual("DETERMINISTIC_PASS", statuses["runtime.recovery"])
        self.assertNotIn("LIVE_PASS", set(statuses.values()))
        self.assertEqual(len(statuses), sum(ledger["counts"].values()))
        self.assertEqual([], ledger_tool.validate_ledger(ledger, self.readiness))

    def test_records_proof_hashes(self) -> None:
        ledger = self.build()
        proofs = ledger["proofs"]
        self.assertEqual(digest(self.ui_proof), proofs["actual_web_ui_launch_game"]["sha256"])
        self.assertEqual(digest(self.passive_proof), proofs["passive_installed_launch_game"]["sha256"])
        self.assertEqual("18.400.22", proofs["passive_installed_launch_game"]["game_version"])
        self.assertIn("Daily Reward", proofs["actual_web_ui_launch_game"]["message"])

    def test_validator_rejects_missing_or_live_claiming_ledgers(self) -> None:
        ledger = self.build()
        ledger["capabilities"].pop()
        self.assertTrue(ledger_tool.validate_ledger(ledger, self.readiness))
        ledger = self.build()
        ledger["capabilities"][0]["status"] = "LIVE_PASS"
        self.assertTrue(any("LIVE_PASS" in error for error in ledger_tool.validate_ledger(ledger, self.readiness)))

    def test_cli_writes_valid_ledger(self) -> None:
        output = self.root / "ledger.json"
        argv = [
            "--readiness", str(self.readiness_path),
            "--actual-web-ui-proof", str(self.ui_proof),
            "--passive-launch-proof", str(self.passive_proof),
            "--receipt", str(self.receipt),
            "--source-master", "96bd85517a918f8f6826efc02bfcfcc113dd817d",
            "--local-binary-commit", "d6b308ef1e48032862e062c1887568559591bb5a",
            "--package-sha256", "b" * 64,
            "--installed-manifest-sha256", "c" * 64,
            "--installed-entrypoint-sha256", "d" * 64,
            "--output", str(output),
        ]
        original = sys.argv
        try:
            sys.argv = ["build_installed_acceptance_ledger.py", *argv]
            self.assertEqual(0, ledger_tool.main())
        finally:
            sys.argv = original
        written = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual([], ledger_tool.validate_ledger(written, self.readiness))
        self.assertEqual("RUNTIME_PASS", written["capabilities"][0]["status"])


if __name__ == "__main__":
    unittest.main()
