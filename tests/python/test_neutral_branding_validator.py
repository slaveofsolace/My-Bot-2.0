from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import validate_neutral_branding


def decoded(value: str) -> str:
    return bytes.fromhex(value).decode("ascii")


class NeutralBrandingValidatorTest(unittest.TestCase):
    def test_detects_path_utf8_utf16_and_standalone_origin_acronym(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / f"notes-{decoded('63 6f 64 65 78')}.md"
            first.write_text(decoded("63 68 61 74 67 70 74"), encoding="utf-8")
            second = root / "wide.ini"
            second.write_text(decoded("6f 70 65 6e 61 69") + "\n" + "".join(chr(v) for v in (65, 73)), encoding="utf-16")
            third = root / "origin.txt"
            third.write_text(decoded("6c 6c 6d"), encoding="utf-8")
            report = validate_neutral_branding.scan_paths(root, [first, second, third])
        self.assertEqual(5, len(report["findings"]))
        self.assertEqual({"content", "path"}, {item["surface"] for item in report["findings"]})

    def test_does_not_flag_lowercase_identifier_or_binary_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "safe.py"
            text.write_text("ai = 1\npair = ai + 1\n", encoding="utf-8")
            binary = root / "safe.bin"
            binary.write_bytes(b"\x00" + decoded("63 6c 61 75 64 65").encode("ascii"))
            report = validate_neutral_branding.scan_paths(root, [text, binary])
        self.assertEqual([], report["findings"])
        self.assertEqual(1, report["binary_or_oversize_files"])

    def test_generated_thai_codec_character_names_are_not_origin_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codec = root / "codec.py"
            origin = validate_neutral_branding.PROHIBITED_ACRONYM
            codec.write_text(
                f"    '\\u0e43'   #  0xE3 -> THAI CHARACTER SARA {origin} MAIMUAN\n"
                f"    '\\u0e44'   #  0xE4 -> THAI CHARACTER SARA {origin} MAIMALAI\n",
                encoding="utf-8",
            )
            report = validate_neutral_branding.scan_paths(root, [codec])
        self.assertEqual([], report["findings"])

    def test_origin_acronym_exception_is_narrow_and_named_brands_remain_strict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "review.txt"
            origin = validate_neutral_branding.PROHIBITED_ACRONYM
            named_brands = "\n".join(word.swapcase() for word in validate_neutral_branding.PROHIBITED_CASEFOLD)
            text.write_text(
                f"{origin}\n"
                f"THAI CHARACTER SARA {origin} MAIMUAN\n"
                f"    '\\u0e43'   #  0xE3 -> THAI CHARACTER SARA {origin} MAIMUAN plus commentary\n"
                + named_brands,
                encoding="utf-8",
            )
            report = validate_neutral_branding.scan_paths(root, [text])
        self.assertEqual(8, len(report["findings"]))
        self.assertEqual(
            {"brand-term", "technology-origin"},
            {kind for item in report["findings"] for kind in item["kinds"]},
        )

    def test_validator_source_does_not_embed_the_prohibited_words(self) -> None:
        source = Path(validate_neutral_branding.__file__).read_text(encoding="utf-8")
        for word in validate_neutral_branding.PROHIBITED_CASEFOLD:
            self.assertNotIn(word.casefold(), source.casefold())

    def test_publish_exclusion_is_generic_and_not_vendor_named(self) -> None:
        prefix = decoded("63 6c 61 75 64 65").upper()
        self.assertTrue(validate_neutral_branding._is_publish_excluded(prefix + "_HANDOFF_PROMPT.md"))
        self.assertFalse(validate_neutral_branding._is_publish_excluded(prefix + "_NOTES.md"))
        for word in validate_neutral_branding.PROHIBITED_CASEFOLD:
            self.assertNotIn(word.casefold(), " ".join(validate_neutral_branding.PUBLISH_EXCLUDE_GLOBS).casefold())

    def test_extracted_package_mode_scans_the_actual_payload_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload"
            payload.mkdir()
            (payload / "readme.txt").write_text(decoded("61 72 74 69 66 69 63 69 61 6c 20 69 6e 74 65 6c 6c 69 67 65 6e 63 65"), encoding="utf-8")
            report = validate_neutral_branding.build_report(root, root)
        self.assertEqual("extracted-package", report["mode"])
        self.assertEqual(1, len(report["findings"]))
        self.assertEqual("payload/readme.txt", report["findings"][0]["path"])


if __name__ == "__main__":
    unittest.main()
