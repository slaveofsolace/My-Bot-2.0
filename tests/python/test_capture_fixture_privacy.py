from __future__ import annotations

import json
import io
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from tools import capture_fixture
from tools import validate_current_client_fixtures
from tools.fixture_png import decode_png, verify_recognition_frame, verify_redaction


def write_rgb_png(
    path: Path,
    width: int,
    height: int,
    overrides: dict[tuple[int, int], bytes] | None = None,
    *,
    base: bytes = b"\x20\x30\x40",
) -> None:
    overrides = overrides or {}
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend(overrides.get((x, y), base))
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


class FixturePrivacyTests(unittest.TestCase):
    def test_blank_or_predominantly_black_frame_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            black = Path(temporary) / "black.png"
            write_rgb_png(black, 860, 732, base=b"\x00\x00\x00")
            with self.assertRaisesRegex(ValueError, "predominantly black"):
                verify_recognition_frame(decode_png(black))

    def test_solid_mask_preserves_every_pixel_outside_rectangle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.png"
            redacted = root / "redacted.png"
            write_rgb_png(raw, 8, 6)
            changed = {(x, y): b"\x00\x00\x00" for y in range(2, 4) for x in range(3, 6)}
            write_rgb_png(redacted, 8, 6, changed)

            result = verify_redaction(
                decode_png(raw),
                decode_png(redacted),
                [{"x": 3, "y": 2, "width": 3, "height": 2}],
            )

            self.assertEqual(result["changed_pixels"], 6)
            self.assertEqual(result["masks"][0]["fill_hex"], "#000000")

    def test_change_outside_declared_mask_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.png"
            redacted = root / "redacted.png"
            write_rgb_png(raw, 8, 6)
            write_rgb_png(redacted, 8, 6, {(7, 5): b"\x00\x00\x00"})

            with self.assertRaisesRegex(ValueError, "outside declared masks"):
                verify_redaction(
                    decode_png(raw),
                    decode_png(redacted),
                    [{"x": 1, "y": 1, "width": 1, "height": 1}],
                )

    def test_nonuniform_mask_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.png"
            redacted = root / "redacted.png"
            write_rgb_png(raw, 8, 6)
            write_rgb_png(redacted, 8, 6, {(1, 1): b"\x00\x00\x00", (2, 1): b"\xFF\xFF\xFF"})

            with self.assertRaisesRegex(ValueError, "not a solid-color replacement"):
                verify_redaction(
                    decode_png(raw),
                    decode_png(redacted),
                    [{"x": 1, "y": 1, "width": 2, "height": 1}],
                )

    def test_no_redaction_attestation_requires_identical_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.png"
            same = root / "same.png"
            changed = root / "changed.png"
            write_rgb_png(raw, 8, 6)
            write_rgb_png(same, 8, 6)
            write_rgb_png(changed, 8, 6, {(2, 2): b"\x00\x00\x00"})

            result = verify_redaction(decode_png(raw), decode_png(same), [], no_redaction_needed=True)
            self.assertEqual(result["changed_pixels"], 0)
            with self.assertRaisesRegex(ValueError, "byte-identical"):
                verify_redaction(decode_png(raw), decode_png(changed), [], no_redaction_needed=True)

    def test_import_copies_only_redacted_derivative_and_never_records_raw_path(self) -> None:
        original_constants = {
            name: getattr(capture_fixture, name)
            for name in ("ROOT", "BASE", "MANIFEST", "IMAGES", "METADATA")
        }
        try:
            with tempfile.TemporaryDirectory() as temporary:
                temp = Path(temporary)
                repo = temp / "repo"
                private = temp / "private"
                private.mkdir()
                base = repo / "tests/fixtures/current-client"
                images = base / "images"
                metadata = base / "metadata"
                base.mkdir(parents=True)
                manifest_path = base / "manifest.json"
                manifest_path.write_text(json.dumps({
                    "schema_version": 1,
                    "capture_contract": {"width": 8, "height": 6},
                    "required_fixtures": [{
                        "id": "home.maintenance.ready",
                        "status": "missing",
                        "purpose": "Maintenance controls",
                    }],
                }), encoding="utf-8")
                for name, value in {
                    "ROOT": repo,
                    "BASE": base,
                    "MANIFEST": manifest_path,
                    "IMAGES": images,
                    "METADATA": metadata,
                }.items():
                    setattr(capture_fixture, name, value)

                raw = private / "raw-account.png"
                redacted = private / "redacted.png"
                write_rgb_png(raw, 8, 6)
                write_rgb_png(redacted, 8, 6, {(1, 1): b"\x00\x00\x00"})
                arguments = SimpleNamespace(
                    fixture_id="home.maintenance.ready",
                    raw_png=str(raw),
                    redacted_png=str(redacted),
                    mask=["1,1,1,1"],
                    no_redaction_needed=False,
                    game_version="18.400.9",
                    source_type="authorized-test-account",
                    privacy_notes="Player label replaced with one opaque solid mask.",
                    notes="offline test",
                )

                with redirect_stdout(io.StringIO()):
                    self.assertEqual(capture_fixture.cmd_add(arguments), 0)
                committed_image = images / "home.maintenance.ready.png"
                committed_metadata = metadata / "home.maintenance.ready.json"
                self.assertEqual(committed_image.read_bytes(), redacted.read_bytes())
                metadata_text = committed_metadata.read_text(encoding="utf-8")
                self.assertNotIn(str(raw), metadata_text)
                metadata_object = json.loads(metadata_text)
                self.assertEqual(metadata_object["schema_version"], 2)
                self.assertEqual(metadata_object["privacy_review_method"], "decoded-pixel-diff-v1")
                self.assertEqual(metadata_object["redaction_pixel_changes"], 1)
                self.assertEqual(metadata_object["frame_content"]["total_pixels"], 48)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["required_fixtures"][0]["status"], "redacted")
        finally:
            for name, value in original_constants.items():
                setattr(capture_fixture, name, value)

    def test_import_never_overwrites_a_verified_fixture(self) -> None:
        original_constants = {
            name: getattr(capture_fixture, name)
            for name in ("ROOT", "BASE", "MANIFEST", "IMAGES", "METADATA")
        }
        try:
            with tempfile.TemporaryDirectory() as temporary:
                temp = Path(temporary)
                repo = temp / "repo"
                private = temp / "private"
                private.mkdir()
                base = repo / "tests/fixtures/current-client"
                images = base / "images"
                metadata = base / "metadata"
                images.mkdir(parents=True)
                metadata.mkdir()
                fixture_id = "home.maintenance.ready"
                manifest_path = base / "manifest.json"
                manifest_path.write_text(json.dumps({
                    "schema_version": 1,
                    "capture_contract": {"width": 8, "height": 6},
                    "required_fixtures": [{
                        "id": fixture_id,
                        "status": "verified",
                        "purpose": "Maintenance controls",
                    }],
                }), encoding="utf-8")
                for name, value in {
                    "ROOT": repo,
                    "BASE": base,
                    "MANIFEST": manifest_path,
                    "IMAGES": images,
                    "METADATA": metadata,
                }.items():
                    setattr(capture_fixture, name, value)

                committed = images / f"{fixture_id}.png"
                write_rgb_png(committed, 8, 6, {(1, 1): b"\x10\x20\x30"})
                original_bytes = committed.read_bytes()
                raw = private / "raw.png"
                redacted = private / "redacted.png"
                write_rgb_png(raw, 8, 6)
                write_rgb_png(redacted, 8, 6, {(1, 1): b"\x00\x00\x00"})
                arguments = SimpleNamespace(
                    fixture_id=fixture_id,
                    raw_png=str(raw),
                    redacted_png=str(redacted),
                    mask=["1,1,1,1"],
                    no_redaction_needed=False,
                    game_version="18.400.9",
                    source_type="authorized-test-account",
                    privacy_notes="Opaque player-label mask.",
                    notes="",
                    replace_redacted=True,
                )
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(capture_fixture.cmd_add(arguments), 2)
                self.assertIn("already verified", output.getvalue())
                self.assertEqual(committed.read_bytes(), original_bytes)
        finally:
            for name, value in original_constants.items():
                setattr(capture_fixture, name, value)

    def test_validator_accepts_schema_two_redaction_evidence(self) -> None:
        capture_constants = {
            name: getattr(capture_fixture, name)
            for name in ("ROOT", "BASE", "MANIFEST", "IMAGES", "METADATA")
        }
        validator_constants = {
            name: getattr(validate_current_client_fixtures, name)
            for name in ("ROOT", "MANIFEST_PATH", "CAPABILITIES_PATH")
        }
        original_argv = sys.argv
        try:
            with tempfile.TemporaryDirectory() as temporary:
                temp = Path(temporary)
                repo = temp / "repo"
                private = temp / "private"
                private.mkdir()
                base = repo / "tests/fixtures/current-client"
                images = base / "images"
                metadata = base / "metadata"
                base.mkdir(parents=True)
                manifest_path = base / "manifest.json"
                capability_path = repo / "config/current-client-capabilities.json"
                capability_path.parent.mkdir(parents=True)
                fixture_id = "home.maintenance.ready"
                manifest_path.write_text(json.dumps({
                    "schema_version": 1,
                    "capture_contract": {"width": 860, "height": 732, "format": "png"},
                    "required_fixtures": [{
                        "id": fixture_id,
                        "status": "missing",
                        "purpose": "Maintenance controls recognition",
                        "capability_ids": ["village.collectors"],
                        "image_path": f"tests/fixtures/current-client/images/{fixture_id}.png",
                        "metadata_path": f"tests/fixtures/current-client/metadata/{fixture_id}.json",
                    }],
                }), encoding="utf-8")
                capability_path.write_text(json.dumps({
                    "capabilities": [{"id": "village.collectors"}],
                }), encoding="utf-8")

                for name, value in {
                    "ROOT": repo,
                    "BASE": base,
                    "MANIFEST": manifest_path,
                    "IMAGES": images,
                    "METADATA": metadata,
                }.items():
                    setattr(capture_fixture, name, value)

                raw = private / "raw.png"
                redacted = private / "redacted.png"
                write_rgb_png(raw, 860, 732)
                write_rgb_png(redacted, 860, 732, {(2, 2): b"\x00\x00\x00"})
                arguments = SimpleNamespace(
                    fixture_id=fixture_id,
                    raw_png=str(raw),
                    redacted_png=str(redacted),
                    mask=["2,2,1,1"],
                    no_redaction_needed=False,
                    game_version="18.400.9",
                    source_type="authorized-test-account",
                    privacy_notes="Synthetic account label mask.",
                    notes="offline validator test",
                )
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(capture_fixture.cmd_add(arguments), 0)

                validate_current_client_fixtures.ROOT = repo
                validate_current_client_fixtures.MANIFEST_PATH = manifest_path
                validate_current_client_fixtures.CAPABILITIES_PATH = capability_path
                sys.argv = ["validate_current_client_fixtures.py"]
                output = io.StringIO()
                with redirect_stdout(output):
                    result = validate_current_client_fixtures.main()
                self.assertEqual(result, 0, output.getvalue())
                report = json.loads(output.getvalue())
                self.assertEqual(report["complete"], 1)
                self.assertEqual(report["errors"], [])
                self.assertIn("png-decode", report["fixtures"][0]["checks"])
        finally:
            sys.argv = original_argv
            for name, value in capture_constants.items():
                setattr(capture_fixture, name, value)
            for name, value in validator_constants.items():
                setattr(validate_current_client_fixtures, name, value)


if __name__ == "__main__":
    unittest.main()
