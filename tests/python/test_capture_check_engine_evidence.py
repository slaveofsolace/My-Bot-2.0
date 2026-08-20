import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import capture_check_engine_evidence as capture_tool  # noqa: E402
from validate_runtime_evidence import validate_engine_initialization_artifact  # noqa: E402


class CheckEngineCaptureTests(unittest.TestCase):
    def make_fixture(self, root: Path):
        install = root / "installed" / "My Bot 2.0"
        profiles = root / "user-data" / "Profiles"
        output = root / "evidence"
        for path in (install / "config", install / "Languages", install / "logs", install / "lib", profiles):
            path.mkdir(parents=True, exist_ok=True)
        (install / "MyBot.run.exe").write_bytes(b"backend-reviewed")
        (install / "Languages" / "English.ini").write_bytes(b"language-reviewed")
        (profiles / "profile.ini").write_bytes(b"[general]\r\ndefaultprofile=MyVillage\r\n")
        provenance = {
            "artifacts": [{
                "path": "MyBot.run.exe",
                "sha256": capture_tool.sha256_file(install / "MyBot.run.exe"),
                "bytes": (install / "MyBot.run.exe").stat().st_size,
                "provenance": {"tool_version": "3.3.16.1"},
            }]
        }
        (install / "config" / "binary-provenance.json").write_text(
            json.dumps(provenance), encoding="utf-8"
        )
        records = []
        for relative in ("MyBot.run.exe", "Languages/English.ini", "config/binary-provenance.json"):
            path = install / Path(relative)
            records.append({
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": capture_tool.sha256_file(path),
            })
        manifest = {
            "schema_version": 1,
            "mode": "LocalRuntime",
            "version": "2.0.0",
            "architecture": "x86",
            "source_commit": "1" * 40,
            "source_tree_clean": True,
            "files": records,
        }
        manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        (install / "release-manifest.json").write_bytes(manifest_bytes)
        package = root / "reviewed.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("MyBot-2.0.0-win-x86/release-manifest.json", manifest_bytes)

        initial = dict(capture_tool.EXPECTED_INITIAL)
        initial["bot_pid"] = 30
        initial["session_id"] = ""
        final = dict(capture_tool.EXPECTED_FINAL)
        final["bot_pid"] = 30
        final["session_id"] = ""
        health = {
            "ok": True,
            "repo_root": str(install.resolve()),
            "profiles_root": str(profiles.resolve()),
            "service_pid": 40,
            "engine": initial,
        }
        processes = {
            10: capture_tool.ProcessIdentity(10, 1, "0000000000000010", str(install / "My Bot 2.0.exe")),
            20: capture_tool.ProcessIdentity(20, 10, "0000000000000020", str(install / "MyBot.run.MiniGui.exe")),
            30: capture_tool.ProcessIdentity(30, 20, "0000000000000030", str(install / "MyBot.run.exe")),
            40: capture_tool.ProcessIdentity(40, 30, "0000000000000040", str(root / "pythonw.exe")),
        }
        config = capture_tool.CaptureConfig(
            install_root=install,
            profiles_root=profiles,
            package_zip=package,
            output_directory=output,
            host="127.0.0.1",
            port=8765,
            emulator_version="5.22.252.1008",
            game_version="18.400.9",
            instance_name="Pie64",
            instance_index=0,
            reviewer_name="My Bot 2.0 runtime review",
            execute=True,
            timeout_seconds=135.0,
        )
        receipt = {
            "schema": "engine-init-supervisor-v1",
            "token": "a" * 64,
            "launcher_pid": 10,
            "launcher_created": processes[10].created,
            "controller_pid": 20,
            "controller_created": processes[20].created,
            "backend_pid": 30,
            "backend_created": processes[30].created,
            "parent_pid": 20,
            "phase": "initialized",
            "start_request_id": "check.owned-1",
            "sequence": 9,
            "phase_history": list(capture_tool.PHASES),
        }
        return config, health, initial, final, processes, receipt

    def test_manifest_integrity_detects_byte_and_hash_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            config, health, initial, final, processes, receipt = self.make_fixture(Path(folder))
            manifest = capture_tool.json_file(config.install_root / "release-manifest.json")
            self.assertEqual(
                {"records": 3, "missing": 0, "size_mismatches": 0, "hash_mismatches": 0},
                capture_tool.manifest_integrity(config.install_root, manifest),
            )
            (config.install_root / "MyBot.run.exe").write_bytes(b"same-size-tamper")
            result = capture_tool.manifest_integrity(config.install_root, manifest)
            self.assertEqual(0, result["size_mismatches"])
            self.assertEqual(1, result["hash_mismatches"])

    def test_receipt_requires_exact_history_and_process_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            config, health, initial, final, processes, receipt = self.make_fixture(Path(folder))
            with mock.patch.object(capture_tool, "api_json", return_value=(200, health)):
                pre = capture_tool.preflight(config, lambda: processes)
            samples = capture_tool.validate_receipt(receipt, "check.owned-1", pre, processes)
            self.assertEqual(
                [{"sequence": index + 1, "phase": phase} for index, phase in enumerate(capture_tool.PHASES)],
                samples,
            )
            receipt["phase_history"] = ["prepared", "initialized"]
            with self.assertRaisesRegex(capture_tool.CaptureError, "exact monotonic phase history"):
                capture_tool.validate_receipt(receipt, "check.owned-1", pre, processes)

    def test_successful_capture_is_redacted_and_semantically_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            config, health, initial, final, processes, receipt = self.make_fixture(Path(folder))
            events_path = config.install_root / "logs" / "run-events.jsonl"
            launcher_log = config.profiles_root.parent / "launcher-recovery.log"
            calls = []

            def fake_api(_config, method, path, body=None):
                calls.append((method, path, body))
                if method == "GET" and path == "/api/health":
                    return 200, health
                if method == "POST" and body == {"action": "check-engine"}:
                    events_path.write_text(
                        json.dumps({"type": "engine.check.started", "verification_state": "unverified-diagnostic"}) + "\n"
                        + json.dumps({"type": "engine.check.passed", "verification_state": "unverified-diagnostic"}) + "\n",
                        encoding="utf-8",
                    )
                    launcher_log.write_text(
                        "engine init supervision finalized; outcome=initialized; receipt_removed=True; cancel_removed=True\n",
                        encoding="utf-8",
                    )
                    return 202, {
                        "ok": True,
                        "accepted": True,
                        "request_id": "check.owned-1",
                        "native_command_queued": True,
                    }
                if method == "GET" and path == "/api/control/status":
                    return 200, final
                raise AssertionError((method, path, body))

            receipt_reads = iter((receipt, None))
            with (
                mock.patch.object(capture_tool, "api_json", side_effect=fake_api),
                mock.patch.object(capture_tool, "read_receipt", side_effect=lambda _path: next(receipt_reads, None)),
                mock.patch.object(capture_tool, "backend_has_outbound_tcp", return_value=False),
            ):
                artifact, record = capture_tool.capture(config, snapshot=lambda: processes, sleep=lambda _: None)

            self.assertEqual(2, artifact["schema_version"])
            self.assertTrue(artifact["redacted"])
            serialized = json.dumps(artifact).lower()
            for prohibited in ("check.owned-1", "aaaaaaaaaaaaaaaa", '"backend_pid"', '"launcher_pid"'):
                self.assertNotIn(prohibited, serialized)
            self.assertEqual([], validate_engine_initialization_artifact(record, artifact, expected_artifact_id=artifact["artifact_id"]))
            self.assertEqual(1, sum(method == "POST" and body == {"action": "check-engine"} for method, _, body in calls))
            self.assertEqual(2, len(list(config.output_directory.glob("*.json"))))

    def test_failure_after_accept_queues_one_bound_stop_and_writes_no_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            config, health, initial, final, processes, receipt = self.make_fixture(Path(folder))
            calls = []

            def fake_api(_config, method, path, body=None):
                calls.append((method, path, body))
                if method == "GET" and path == "/api/health":
                    return 200, health
                if method == "POST" and body == {"action": "check-engine"}:
                    return 202, {"ok": True, "accepted": True, "request_id": "check.owned-1", "native_command_queued": True}
                if method == "POST" and body == {"action": "stop", "expected_start_request_id": "check.owned-1"}:
                    return 202, {"ok": True, "accepted": True}
                raise AssertionError((method, path, body))

            with (
                mock.patch.object(capture_tool, "api_json", side_effect=fake_api),
                mock.patch.object(capture_tool, "read_receipt", side_effect=capture_tool.CaptureError("invalid live receipt")),
                mock.patch.object(capture_tool, "backend_has_outbound_tcp", return_value=False),
            ):
                with self.assertRaisesRegex(capture_tool.CaptureError, "invalid live receipt"):
                    capture_tool.capture(config, snapshot=lambda: processes, sleep=lambda _: None)
            self.assertIn(
                ("POST", "/api/control/command", {"action": "stop", "expected_start_request_id": "check.owned-1"}),
                calls,
            )
            self.assertFalse(config.output_directory.exists())

    def test_cli_is_dry_run_unless_execute_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "package.zip"
            package.write_bytes(b"placeholder")
            config = capture_tool.parse_args([
                "--package-zip", str(package),
                "--emulator-version", "5.22.252.1008",
                "--game-version", "18.400.9",
            ])
            self.assertFalse(config.execute)
            self.assertIsNone(config.output_directory)
            with self.assertRaises(SystemExit):
                capture_tool.parse_args([
                    "--package-zip", str(package),
                    "--emulator-version", "5.22.252.1008",
                    "--game-version", "18.400.9",
                    "--execute",
                ])


if __name__ == "__main__":
    unittest.main()
