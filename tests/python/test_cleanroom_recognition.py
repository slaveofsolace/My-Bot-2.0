from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from PIL import Image

from tools.cleanroom_recognition import (
    CAPTURE_OWNER,
    CleanRoomRecognitionAdapter,
    RecognitionExport,
    RecognitionPolicyError,
    RecognitionRequest,
    RecognitionStatus,
    ROOT_MARKER_NAME,
    _sha256_normalized_text_file,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "current-client" / "images" / "home.daily-reward.png"
CLAIMED_FIXTURE = ROOT / "tests" / "fixtures" / "current-client" / "images" / "home.daily-reward.claimed.png"
MANIFEST = ROOT / "config" / "cleanroom-recognition.json"


class CleanRoomRecognitionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.capture_root = Path(self.temp.name)
        self.session_id = "unit-cleanroom-session"
        self._write_json(
            self.capture_root / ROOT_MARKER_NAME,
            {
                "schema_version": 1,
                "owner": CAPTURE_OWNER,
                "session_id": self.session_id,
                "created_at_utc": self._now(),
            },
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    def _receipt(self, relative: str, fixture_id: str | None, source_kind: str) -> str:
        path = self.capture_root / relative
        with Image.open(path) as image:
            width, height = image.size
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self._write_json(
            path.with_name(path.name + ".capture.json"),
            {
                "schema_version": 1,
                "owner": CAPTURE_OWNER,
                "session_id": self.session_id,
                "relative_path": relative,
                "sha256": sha,
                "width": width,
                "height": height,
                "captured_at_utc": self._now(),
                "source_kind": source_kind,
                "source_fixture_id": fixture_id,
            },
        )
        return sha

    def _fixture_capture(self) -> str:
        relative = "home.daily-reward.png"
        shutil.copyfile(FIXTURE, self.capture_root / relative)
        self._receipt(relative, "home.daily-reward", "fixture-replay")
        return relative

    def _adapter(self) -> CleanRoomRecognitionAdapter:
        return CleanRoomRecognitionAdapter(self.capture_root, self.session_id)

    def test_manifest_inventories_exact_17_export_families(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        exports = manifest["legacy_exports"]
        names = [item["name"] for item in exports]
        self.assertEqual(17, len(names))
        self.assertEqual(17, len(set(names)))
        self.assertEqual({item.value for item in RecognitionExport}, set(names))
        self.assertEqual(3, sum(item["clean_room_status"] == "implemented" for item in exports))

    def test_metadata_hash_is_checkout_newline_invariant(self) -> None:
        lf_path = self.capture_root / "metadata-lf.json"
        crlf_path = self.capture_root / "metadata-crlf.json"
        lf_path.write_bytes(b'{"fixture_id":"sample"}\n')
        crlf_path.write_bytes(b'{"fixture_id":"sample"}\r\n')
        self.assertEqual(
            _sha256_normalized_text_file(lf_path, 1024),
            _sha256_normalized_text_file(crlf_path, 1024),
        )
        crlf_path.write_bytes(b'{"fixture_id":"changed"}\r\n')
        self.assertNotEqual(
            _sha256_normalized_text_file(lf_path, 1024),
            _sha256_normalized_text_file(crlf_path, 1024),
        )

    def test_find_tile_matches_verified_current_client_fixture(self) -> None:
        relative = self._fixture_capture()
        result = self._adapter().recognize(
            RecognitionRequest(
                export="FindTile",
                screenshot_relative_path=relative,
                asset_id="current-client.daily-reward.claim",
                max_results=1,
            )
        )
        self.assertEqual(RecognitionStatus.PASS, result.status)
        self.assertTrue(result.available)
        self.assertEqual(1, result.result_count)
        item = result.payload["items"][0]
        self.assertEqual([239, 305, 356, 345], item["box"])
        self.assertEqual((297, 325), (item["x"], item["y"]))
        self.assertEqual(1.0, item["score"])

    def test_unimplemented_export_is_truthfully_unavailable_without_opening_capture(self) -> None:
        result = self._adapter().recognize(
            RecognitionRequest(export="DoOCR", screenshot_relative_path="does-not-exist.png")
        )
        self.assertEqual(RecognitionStatus.UNAVAILABLE, result.status)
        self.assertFalse(result.available)
        self.assertEqual("EXPORT_UNAVAILABLE", result.reason_code)
        self.assertIsNone(result.screenshot_sha256)

    def test_pillow_unavailable_is_a_truthful_fail_closed_result(self) -> None:
        relative = self._fixture_capture()
        with mock.patch("tools.cleanroom_recognition.Image", None):
            result = self._adapter().recognize(
                RecognitionRequest(
                    export="FindTile",
                    screenshot_relative_path=relative,
                    asset_id="current-client.daily-reward.claim",
                )
            )
        self.assertEqual(RecognitionStatus.REJECTED, result.status)
        self.assertFalse(result.available)
        self.assertEqual("PILLOW_UNAVAILABLE", result.reason_code)

    def test_claimed_current_client_fixture_does_not_match_claim_button(self) -> None:
        relative = "home.daily-reward.claimed.png"
        shutil.copyfile(CLAIMED_FIXTURE, self.capture_root / relative)
        self._receipt(relative, None, "owned-runtime-capture")
        result = self._adapter().recognize(
            RecognitionRequest(
                export="FindTile",
                screenshot_relative_path=relative,
                asset_id="current-client.daily-reward.claim",
            )
        )
        self.assertEqual(RecognitionStatus.NO_MATCH, result.status)
        self.assertTrue(result.available)
        self.assertEqual(0, result.result_count)

    def test_unknown_operation_is_rejected_as_non_enum(self) -> None:
        result = self._adapter().recognize(
            RecognitionRequest(export="RunFunction", screenshot_relative_path="does-not-exist.png")
        )
        self.assertEqual(RecognitionStatus.REJECTED, result.status)
        self.assertEqual("UNKNOWN_EXPORT", result.reason_code)

    def test_black_frame_is_rejected(self) -> None:
        relative = "black.png"
        Image.new("RGB", (860, 732), (0, 0, 0)).save(self.capture_root / relative)
        self._receipt(relative, None, "owned-runtime-capture")
        result = self._adapter().recognize(
            RecognitionRequest(export="GetOffSetRedline", screenshot_relative_path=relative, params={"points": [[100, 100]], "area": "TL", "distance": 3})
        )
        self.assertEqual(RecognitionStatus.REJECTED, result.status)
        self.assertEqual("BLACK_FRAME", result.reason_code)

    def test_stale_hash_is_rejected(self) -> None:
        relative = self._fixture_capture()
        digest = hashlib.sha256((self.capture_root / relative).read_bytes()).hexdigest()
        result = self._adapter().recognize(
            RecognitionRequest(
                export="FindTile",
                screenshot_relative_path=relative,
                asset_id="current-client.daily-reward.claim",
                previous_screenshot_sha256=digest,
            )
        )
        self.assertEqual(RecognitionStatus.REJECTED, result.status)
        self.assertEqual("STALE_SCREENSHOT", result.reason_code)

    def test_receipt_hash_mismatch_is_rejected(self) -> None:
        relative = self._fixture_capture()
        receipt_path = (self.capture_root / relative).with_name(Path(relative).name + ".capture.json")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["sha256"] = "0" * 64
        self._write_json(receipt_path, receipt)
        result = self._adapter().recognize(
            RecognitionRequest(export="FindTile", screenshot_relative_path=relative, asset_id="current-client.daily-reward.claim")
        )
        self.assertEqual("CAPTURE_HASH_MISMATCH", result.reason_code)

    def test_path_traversal_and_arbitrary_asset_are_rejected(self) -> None:
        relative = self._fixture_capture()
        traversal = self._adapter().recognize(
            RecognitionRequest(export="FindTile", screenshot_relative_path="../home.daily-reward.png", asset_id="current-client.daily-reward.claim")
        )
        self.assertEqual("INVALID_SCREENSHOT_PATH", traversal.reason_code)
        unknown = self._adapter().recognize(
            RecognitionRequest(export="FindTile", screenshot_relative_path=relative, asset_id="C:/arbitrary.png")
        )
        self.assertEqual("UNKNOWN_ASSET", unknown.reason_code)

    def test_result_count_is_bounded(self) -> None:
        relative = self._fixture_capture()
        result = self._adapter().recognize(
            RecognitionRequest(export="FindTile", screenshot_relative_path=relative, asset_id="current-client.daily-reward.claim", max_results=33)
        )
        self.assertEqual("INVALID_RESULT_LIMIT", result.reason_code)

    def test_dimension_receipt_mismatch_is_rejected(self) -> None:
        relative = self._fixture_capture()
        receipt_path = (self.capture_root / relative).with_name(Path(relative).name + ".capture.json")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["width"] = 859
        self._write_json(receipt_path, receipt)
        result = self._adapter().recognize(
            RecognitionRequest(export="FindTile", screenshot_relative_path=relative, asset_id="current-client.daily-reward.claim")
        )
        self.assertEqual("CAPTURE_DIMENSION_MISMATCH", result.reason_code)

    def test_deadline_expiry_is_fail_closed(self) -> None:
        relative = self._fixture_capture()
        with mock.patch("tools.cleanroom_recognition.time.monotonic", side_effect=[0.0, 1.0, 1.0]):
            result = self._adapter().recognize(
                RecognitionRequest(export="FindTile", screenshot_relative_path=relative, asset_id="current-client.daily-reward.claim", deadline_ms=1)
            )
        self.assertEqual(RecognitionStatus.DEADLINE_EXCEEDED, result.status)
        self.assertEqual("DEADLINE_EXCEEDED", result.reason_code)

    def test_offset_redline_is_pure_bounded_coordinate_operation(self) -> None:
        relative = self._fixture_capture()
        result = self._adapter().recognize(
            RecognitionRequest(
                export="GetOffSetRedline",
                screenshot_relative_path=relative,
                params={"points": [[100, 100], [760, 100], [100, 650]], "area": "TL", "distance": 10},
            )
        )
        self.assertEqual(RecognitionStatus.PASS, result.status)
        self.assertEqual(1, result.result_count)
        self.assertLess(result.payload["items"][0]["x"], 100)
        self.assertLess(result.payload["items"][0]["y"], 100)

    def test_deployable_next_to_is_deterministic_and_has_no_path_surface(self) -> None:
        relative = self._fixture_capture()
        request = RecognitionRequest(
            export="GetDeployableNextTo",
            screenshot_relative_path=relative,
            params={"targets": [[300, 300]], "redline_points": [[280, 300], [500, 500]], "distance": 5},
        )
        first = self._adapter().recognize(request)
        second = self._adapter().recognize(request)
        self.assertEqual(RecognitionStatus.PASS, first.status)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual([{"x": 275, "y": 300}], first.payload["items"])
        self.assertFalse(first.payload["legacy_wire_compatible"])

    def test_capture_root_marker_is_required_and_session_bound(self) -> None:
        with self.assertRaises(RecognitionPolicyError):
            CleanRoomRecognitionAdapter(self.capture_root, "different-session")

    def test_adapter_source_has_no_process_dll_or_emulator_surface(self) -> None:
        source = (ROOT / "tools" / "cleanroom_recognition.py").read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "os.system",
            "DllCall(",
            "MyBot.run.dll",
            "HD-Player",
            "adb.exe",
            "WinActivate",
            "Click(",
        ):
            self.assertNotIn(forbidden, source)

    def test_fixture_asset_makes_no_live_or_runtime_compatibility_claim(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        asset = manifest["assets"]["current-client.daily-reward.claim"]
        self.assertEqual("verified-fixture-replay-only", asset["evidence_scope"])
        self.assertFalse(asset["live_tolerance_proven"])
        self.assertFalse(asset["bot_start_wired"])
        self.assertFalse(asset["legacy_wire_compatible"])


if __name__ == "__main__":
    unittest.main()
