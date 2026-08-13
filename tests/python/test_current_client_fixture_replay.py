from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from tools.replay_current_client_fixtures import (
    FixtureReplayError,
    RecognitionResult,
    SafeRegion,
    UnsafeActionAttempt,
    replay_verified_fixtures,
)


def write_rgb_png(
    path: Path,
    width: int,
    height: int,
    overrides: dict[tuple[int, int], bytes] | None = None,
) -> None:
    overrides = overrides or {}
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend(overrides.get((x, y), b"\x20\x30\x40"))
        rows.append(b"\x00" + bytes(row))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


class FixtureRepository:
    width = 4
    height = 3
    fixture_id = "home.synthetic.ready"
    adapter = "test.pixel-probe"
    expected_state = "home.synthetic"
    expected_region = SafeRegion(id="passive-panel", x=1, y=1, width=2, height=1)

    def __init__(self, root: Path, *, status: str = "verified", include_contract: bool = True) -> None:
        self.root = root
        self.base = root / "tests/fixtures/current-client"
        self.image_path = self.base / "images" / f"{self.fixture_id}.png"
        self.metadata_path = self.base / "metadata" / f"{self.fixture_id}.json"
        self.manifest_path = self.base / "manifest.json"
        self.image_path.parent.mkdir(parents=True)
        self.metadata_path.parent.mkdir(parents=True)
        write_rgb_png(self.image_path, self.width, self.height, {(1, 1): b"\xFF\x00\x00"})
        metadata = {
            "schema_version": 2,
            "fixture_id": self.fixture_id,
            "width": self.width,
            "height": self.height,
            "sha256": hashlib.sha256(self.image_path.read_bytes()).hexdigest(),
            "reviewed_by": "offline-test-reviewer",
            "reviewed_at": "2026-08-13T00:00:00Z",
        }
        if include_contract:
            metadata["replay_contract"] = {
                "schema_version": 1,
                "adapter": self.adapter,
                "expected_state": self.expected_state,
                "safe_regions": [
                    {
                        "id": self.expected_region.id,
                        "x": self.expected_region.x,
                        "y": self.expected_region.y,
                        "width": self.expected_region.width,
                        "height": self.expected_region.height,
                    }
                ],
            }
        self.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        self.manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "capture_contract": {"width": self.width, "height": self.height, "format": "png"},
                    "required_fixtures": [
                        {
                            "id": self.fixture_id,
                            "status": status,
                            "image_path": str(self.image_path.relative_to(root)).replace("\\", "/"),
                            "metadata_path": str(self.metadata_path.relative_to(root)).replace("\\", "/"),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def recognizer(self, image, _sink):
        offset = (1 * image.width + 1) * image.channels
        if image.pixels[offset:offset + 3] != b"\xFF\x00\x00":
            return None
        return RecognitionResult(self.expected_state, (self.expected_region,))


class CurrentClientFixtureReplayTests(unittest.TestCase):
    def test_verified_fixture_replays_pixels_regions_and_unknown_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary))
            report = replay_verified_fixtures(
                repository.manifest_path,
                root=repository.root,
                recognizers={repository.adapter: repository.recognizer},
                require_verified=True,
            )

            self.assertEqual(report.verified_entries, 1)
            self.assertEqual(report.replayed_entries, 1)
            self.assertEqual(report.replayed_fixture_ids, (repository.fixture_id,))
            self.assertEqual(report.unknown_checks, 1)

    def test_missing_and_redacted_entries_are_skipped_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary), status="missing")
            original = repository.manifest_path.read_bytes()

            report = replay_verified_fixtures(repository.manifest_path, root=repository.root, recognizers={})

            self.assertEqual(report.verified_entries, 0)
            self.assertEqual(report.replayed_entries, 0)
            self.assertEqual(report.skipped_fixture_ids, (repository.fixture_id,))
            self.assertEqual(repository.manifest_path.read_bytes(), original)

    def test_require_verified_refuses_zero_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary), status="redacted")
            with self.assertRaisesRegex(FixtureReplayError, "would prove nothing"):
                replay_verified_fixtures(
                    repository.manifest_path,
                    root=repository.root,
                    recognizers={},
                    require_verified=True,
                )

    def test_verified_fixture_without_replay_contract_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary), include_contract=False)
            with self.assertRaisesRegex(FixtureReplayError, "missing replay_contract"):
                replay_verified_fixtures(
                    repository.manifest_path,
                    root=repository.root,
                    recognizers={repository.adapter: repository.recognizer},
                )

    def test_missing_recognizer_adapter_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary))
            with self.assertRaisesRegex(FixtureReplayError, "no passive production recognizer"):
                replay_verified_fixtures(repository.manifest_path, root=repository.root, recognizers={})

    def test_adapter_action_attempt_is_rejected_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary))
            captured_sinks = []

            def unsafe_recognizer(_image, sink):
                captured_sinks.append(sink)
                sink.click(10, 10)
                return None

            with self.assertRaisesRegex(UnsafeActionAttempt, "rejected action attempt: click"):
                replay_verified_fixtures(
                    repository.manifest_path,
                    root=repository.root,
                    recognizers={repository.adapter: unsafe_recognizer},
                )
            self.assertEqual(len(captured_sinks), 1)
            self.assertEqual(captured_sinks[0].attempts, ("click",))
            self.assertEqual(captured_sinks[0].executed_count, 0)

    def test_adapter_that_recognizes_unknown_black_frame_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary))

            def overbroad_recognizer(_image, _sink):
                return RecognitionResult(repository.expected_state, (repository.expected_region,))

            with self.assertRaisesRegex(FixtureReplayError, "unknown-black-frame.*instead of failing closed"):
                replay_verified_fixtures(
                    repository.manifest_path,
                    root=repository.root,
                    recognizers={repository.adapter: overbroad_recognizer},
                )

    def test_out_of_bounds_reviewed_region_fails_before_recognition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = FixtureRepository(Path(temporary))
            metadata = json.loads(repository.metadata_path.read_text(encoding="utf-8"))
            metadata["replay_contract"]["safe_regions"][0]["width"] = repository.width
            repository.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(FixtureReplayError, "exceeds 4x3 capture bounds"):
                replay_verified_fixtures(
                    repository.manifest_path,
                    root=repository.root,
                    recognizers={repository.adapter: repository.recognizer},
                )


if __name__ == "__main__":
    unittest.main()
