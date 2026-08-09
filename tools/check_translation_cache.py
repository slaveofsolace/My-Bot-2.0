#!/usr/bin/env python3
"""Validate the AutoIt translation-cache and read-only catalog contract."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "COCBot" / "functions" / "Other" / "Multilanguage.au3"
GLOBALS_SOURCE = ROOT / "COCBot" / "MBR Global Variables.au3"
LANGUAGES = ROOT / "Languages"
RUNTIME_FUNCTIONS = (
    "GetTranslatedParsedText",
    "_LanguageCacheEnsure",
    "_LanguageCacheKey",
    "_LanguageCacheLoadFile",
    "_LanguageCacheRead",
    "_TranslationSourceTextRequired",
    "GetTranslatedFileIni",
    "_ReadFullIni",
)


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ims)^Func\s+{re.escape(name)}\s*\(.*?^EndFunc(?:\s*;[^\r\n]*)?",
        source,
    )
    if not match:
        raise AssertionError(f"missing AutoIt function: {name}")
    return match.group(0)


def assert_static_contract(source: str, globals_source: str) -> None:
    cache_read = function_body(source, "_LanguageCacheRead")
    cache_load = function_body(source, "_LanguageCacheLoadFile")
    source_required = function_body(source, "_TranslationSourceTextRequired")
    translate = function_body(source, "GetTranslatedFileIni")
    preload = function_body(source, "_ReadFullIni")

    assert globals_source.count('Global $g_oLanguageFileCache = ObjCreate("Scripting.Dictionary")') == 1
    assert globals_source.count('Global $g_oLanguageFileCacheLoaded = ObjCreate("Scripting.Dictionary")') == 1
    assert "Global $g_oLanguageFileCache" not in source
    assert "Global $g_oLanguageFileCacheLoaded" not in source
    assert "IniReadSectionNames" in cache_load and "IniReadSection" in cache_load
    assert ".Exists(" in cache_load and ".Add(" in cache_load
    assert "_LanguageCacheLoadFile($sLanguage)" in cache_read
    assert ".Exists(" in cache_read and ".Item(" in cache_read
    assert translate.count("_LanguageCacheRead(") >= 3

    normalize = '$sText = StringReplace($sText, @CRLF, "\\r\\n")'
    english_fast_path = (
        'If $g_sLanguage = $g_sDefaultLanguage And $sText <> "" And $sText <> "-1" Then '
        "Return GetTranslatedParsedText($sText, $var1, $var2, $var3)"
    )
    assert normalize in translate
    assert english_fast_path in translate
    assert translate.index(normalize) < translate.index(english_fast_path)
    assert translate.index(english_fast_path) < translate.index("_LanguageCacheRead(")
    assert "$g_sProductName" in source_required
    assert "mbr authentication" in source_required
    assert "_TranslationSourceTextRequired($iSection, $iKey, $sText)" in translate

    assert "_LanguageCacheLoadFile($g_sDefaultLanguage)" in preload
    assert "_LanguageCacheLoadFile($g_sLanguage)" in preload
    assert preload.count(".RemoveAll") == 2

    # Normal translation lookup may read catalogs, but it must never repair or
    # rewrite a shipped INI. That belongs to the build-time catalog validator.
    for name in ("GetTranslated", "GetTranslatedFileIni", "_ReadFullIni"):
        body = function_body(source, name)
        assert not re.search(r"\bIniWrite(?:Section)?\s*\(", body), name

    managed_markers = ("DllCall(", "MBRFunc(", "MBRFuncInitialize(")
    runtime_source = "\n".join(function_body(source, name) for name in RUNTIME_FUNCTIONS)
    for marker in managed_markers:
        assert marker not in runtime_source, marker


def file_hashes() -> dict[Path, str]:
    return {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(LANGUAGES.glob("*.ini"))
    }


def discover_autoit(explicit: Path | None) -> Path | None:
    candidates = [
        explicit,
        Path(r"C:\Program Files (x86)\AutoIt3\AutoIt3.exe"),
        Path(r"C:\Program Files\AutoIt3\AutoIt3.exe"),
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def autoit_string(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def run_autoit_contract(source: str, autoit: Path) -> str:
    extracted = "\n\n".join(function_body(source, name) for name in RUNTIME_FUNCTIONS)
    with tempfile.TemporaryDirectory(prefix="mybot-translation-cache-") as temp_name:
        temp = Path(temp_name)
        language_dir = temp / "Languages"
        language_dir.mkdir()
        (language_dir / "English.ini").write_text(
            "[Text]\n"
            "Greeting=Hello %s\n"
            "Mismatch=Catalog stale\n"
            "EnglishOnly=English fallback %s\n"
            "Pair=%s/%s\n",
            encoding="utf-16",
        )
        (language_dir / "Spanish.ini").write_text(
            "[Text]\nGreeting=Hola %s\n"
            "[Brand]\nTitle=My Bot v8.2.0\n"
            "[MBR Authentication]\nAuthenticationFailed1=Old continue-anyway text\n",
            encoding="utf-16",
        )

        directory_literal = autoit_string(str(language_dir) + "\\")
        harness = f'''#NoTrayIcon
Opt("MustDeclareVars", 1)

Global $g_sLanguage = "English"
Global $g_sDefaultLanguage = "English"
Global $g_sProductName = "My Bot 2.0"
Global $g_sDirLanguages = {directory_literal}
Global $g_oLanguageFileCache = ObjCreate("Scripting.Dictionary")
Global $g_oLanguageFileCacheLoaded = ObjCreate("Scripting.Dictionary")
Global $g_iAssertions = 0

Func AssertEqual($vActual, $vExpected, $sMessage)
    $g_iAssertions += 1
    If $vActual <> $vExpected Then
        ConsoleWriteError("ASSERTION FAILED: " & $sMessage & " expected=[" & $vExpected & "] actual=[" & $vActual & "]" & @CRLF)
        Exit 20
    EndIf
EndFunc

{extracted}

Local $sEnglishPath = $g_sDirLanguages & "English.ini"
Local $sSpanishPath = $g_sDirLanguages & "Spanish.ini"
AssertEqual(_ReadFullIni(), True, "preload default language")
AssertEqual(GetTranslatedFileIni("Text", "Greeting", "-1", "Ada"), "Hello Ada", "catalog placeholder")
AssertEqual(GetTranslatedFileIni("text", "greeting", "-1", "Ada"), "Hello Ada", "case-insensitive key")
AssertEqual(GetTranslatedFileIni("Text", "Mismatch", "Source wins"), "Source wins", "stale English fallback")
AssertEqual(GetTranslatedFileIni("Text", "Missing", "Fallback %s", "Ada"), "Fallback Ada", "missing English fallback")
AssertEqual(GetTranslatedFileIni("Text", "Missing", "-1"), "-3", "missing repeated English key")
AssertEqual(GetTranslatedFileIni("Text", "Pair", "%s/%s", "A", "B"), "A/B", "two placeholders")
AssertEqual(GetTranslatedFileIni("Text", "Inline", "Line 1" & @CRLF & "Line 2"), "Line 1" & @CRLF & "Line 2", "English literal preserves line breaks")

Local $sEnglishBefore = FileRead($sEnglishPath)
AssertEqual(FileRead($sEnglishPath), $sEnglishBefore, "English catalog remains unchanged")
IniWrite($sEnglishPath, "Text", "Greeting", "Changed %s")
AssertEqual(GetTranslatedFileIni("Text", "Greeting", "-1", "Ada"), "Hello Ada", "cache reused after disk change")
AssertEqual(_ReadFullIni(), True, "explicit reload")
AssertEqual(GetTranslatedFileIni("Text", "Greeting", "-1", "Ada"), "Changed Ada", "reload refreshes cache")

$g_sLanguage = "Spanish"
AssertEqual(_ReadFullIni(), True, "preload selected language")
Local $sEnglishReadOnly = FileRead($sEnglishPath)
Local $sSpanishReadOnly = FileRead($sSpanishPath)
AssertEqual(GetTranslatedFileIni("Text", "Greeting", "Hello %s", "Ada"), "Hola Ada", "selected translation")
AssertEqual(GetTranslatedFileIni("Brand", "Title", "My Bot 2.0 v2.0.0"), "My Bot 2.0 v2.0.0", "product branding stays source authoritative")
AssertEqual(GetTranslatedFileIni("MBR Authentication", "AuthenticationFailed1", "Engine authorization is required; the bot remains stopped."), "Engine authorization is required; the bot remains stopped.", "security-sensitive auth copy stays source authoritative")
AssertEqual(GetTranslatedFileIni("Text", "EnglishOnly", "-1", "Ada"), "English fallback Ada", "default-language fallback")
AssertEqual(GetTranslatedFileIni("Text", "Absent", "Fallback %s", "Ada"), "Fallback Ada", "missing selected fallback")
AssertEqual(GetTranslatedFileIni("Text", "Absent", "-1"), "-1", "missing repeated selected key")
AssertEqual(FileRead($sEnglishPath), $sEnglishReadOnly, "English catalog is read-only")
AssertEqual(FileRead($sSpanishPath), $sSpanishReadOnly, "selected catalog is read-only")

ConsoleWrite("Translation cache tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
'''
        harness_path = temp / "TranslationCacheContract.au3"
        harness_path.write_text(harness, encoding="utf-8-sig")
        completed = subprocess.run(
            [str(autoit), "/ErrorStdOut", str(harness_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            raise AssertionError(
                f"AutoIt cache contract failed with {completed.returncode}:\n{output}"
            )
        return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--autoit", type=Path, help="path to AutoIt3.exe")
    parser.add_argument("--require-autoit", action="store_true")
    args = parser.parse_args()

    source = SOURCE.read_text(encoding="utf-8")
    globals_source = GLOBALS_SOURCE.read_text(encoding="utf-8")
    before = file_hashes()
    assert_static_contract(source, globals_source)

    autoit = discover_autoit(args.autoit)
    if not autoit:
        if args.require_autoit:
            raise SystemExit("AutoIt3.exe was not found")
        runtime = "AutoIt runtime contract skipped (AutoIt3.exe not found)"
    else:
        runtime = run_autoit_contract(source, autoit)

    assert file_hashes() == before, "shipped language catalogs changed during validation"
    print("Translation cache static contract passed")
    print(runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
