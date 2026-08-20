from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import repo_audit


ROOT = Path(__file__).resolve().parents[2]


class WarningHtmlBoundaryTests(unittest.TestCase):
    def test_repository_audit_rejects_generated_lib_html_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            warning = root / "LiB" / "30852.HTML"
            warning.parent.mkdir(parents=True)
            warning.write_text("legacy warning", encoding="utf-8")
            findings: list[repo_audit.Finding] = []

            repo_audit.check_generated_warning_html(root, [], findings)

        self.assertEqual(1, len(findings))
        self.assertEqual("error", findings[0].severity)
        self.assertEqual("generated-warning-html-forbidden", findings[0].code)
        self.assertEqual("LiB/30852.HTML", findings[0].path)

    def test_repository_audit_does_not_reject_product_ui_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product_ui = root / "ui" / "planner.html"
            product_ui.parent.mkdir(parents=True)
            product_ui.write_text("product UI", encoding="utf-8")
            findings: list[repo_audit.Finding] = []

            repo_audit.check_generated_warning_html(root, [product_ui], findings)

        self.assertEqual([], findings)

    def test_current_tree_has_no_generated_lib_html(self) -> None:
        generated = [
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "lib").glob("*.html")
            if path.is_file()
        ]
        self.assertEqual([], generated)

    def test_public_managed_recognizer_wrapper_fails_before_dispatch(self) -> None:
        source = (ROOT / "COCBot/functions/Other/MBRFunc.au3").read_text(
            encoding="utf-8-sig", errors="replace"
        )
        body = source.split("Func DllCallMyBot(", 1)[1].split("EndFunc", 1)[0]
        rejection = body.index("Return SetError")
        self.assertNotIn("_DllCallMyBot", body[:rejection])
        self.assertNotIn("DllCall(", body[:rejection])
        self.assertNotIn("ShellExecute", body)

    def test_launcher_automatic_browser_open_is_loopback_only(self) -> None:
        source = (ROOT / "My Bot 2.0.au3").read_text(
            encoding="utf-8-sig", errors="replace"
        )
        automatic = [
            line.strip()
            for line in source.splitlines()
            if "ShellExecute(" in line and not line.lstrip().startswith(";")
        ]
        self.assertTrue(automatic)
        for line in automatic:
            self.assertNotRegex(line.casefold(), r"\.html(?:[\"'])?")
            if "http" in line.casefold():
                self.assertIn("127.0.0.1", line)


if __name__ == "__main__":
    unittest.main()
