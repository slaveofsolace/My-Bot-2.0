from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "MyBot.run.au3"
MBR_FUNC = ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3"

SENSITIVE_WRAPPERS = (
    "setProcessingPoolSize",
    "setMaxDegreeOfParallelism",
    "setAndroidPID",
    "SetBotGuiPID",
)


def function_body(source: str, name: str) -> str:
    start = source.index(f"Func {name}(")
    end = source.index("EndFunc", start)
    return source[start:end]


def read_autoit_source(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def source_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for path in ROOT.rglob("*.au3"):
        relative = path.relative_to(ROOT)
        if any(part.lower() in {".git", "artifacts", "tests"} for part in relative.parts):
            continue
        files.append(path)
    return tuple(sorted(files))


@dataclass(frozen=True)
class Callsite:
    path: Path
    line_number: int
    function: str
    code: str


def wrapper_calls(wrapper: str) -> tuple[Callsite, ...]:
    call = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(wrapper)}\s*\(", re.IGNORECASE)
    function_start = re.compile(r"^\s*Func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.IGNORECASE)
    sites: list[Callsite] = []
    for path in source_files():
        current_function = "<top-level>"
        for line_number, line in enumerate(read_autoit_source(path).splitlines(), 1):
            code = line.split(";", 1)[0].strip()
            start = function_start.match(code)
            if start:
                current_function = start.group(1)
                continue
            if re.match(r"^\s*EndFunc\b", code, re.IGNORECASE):
                current_function = "<top-level>"
                continue
            if code and call.search(code):
                sites.append(Callsite(path.relative_to(ROOT), line_number, current_function, code))
    return tuple(sites)


class ManagedExportSupervisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = read_autoit_source(MAIN)
        cls.mbr_func = read_autoit_source(MBR_FUNC)

    def test_final_initialization_neither_loads_nor_initializes_managed_engine(self) -> None:
        final_initialization = function_body(self.main, "FinalInitialization")
        self.assertNotIn("MBRFunc(", final_initialization)
        self.assertNotIn("DllOpen(", final_initialization)
        self.assertIn("deferred until supervised Start", final_initialization)

    def test_engine_library_open_is_inside_the_supervised_initialization_boundary(self) -> None:
        initializer = function_body(self.mbr_func, "MBRFuncInitialize")
        prepared = initializer.index('_MBRFuncPublishEngineReceipt("prepared")')
        opened = initializer.index("_MBRFuncOpenEngineLibrary()")
        pool_entered = initializer.index('_MBRFuncPublishEngineReceipt("pool-entered")')
        self.assertLess(prepared, opened)
        self.assertLess(opened, pool_entered)

        open_helper = function_body(self.mbr_func, "_MBRFuncOpenEngineLibrary")
        self.assertEqual(open_helper.count("DllOpen($g_sLibMyBotPath)"), 1)
        self.assertNotIn("DllOpen($g_sLibMyBotPath)", function_body(self.mbr_func, "MBRFunc"))

        combined_source = "\n".join(read_autoit_source(path) for path in source_files())
        self.assertEqual(combined_source.count("DllOpen($g_sLibMyBotPath)"), 1)
        self.assertNotIn("MBRFunc(True, False)", combined_source)

    def test_every_sensitive_wrapper_callsite_is_initialized_or_the_initializer(self) -> None:
        expected_initializer_calls = set(SENSITIVE_WRAPPERS)
        observed_initializer_calls: set[str] = set()
        guard = re.compile(
            r"^If\s+\$g_bLibMyBotInitialized\s+Then\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            re.IGNORECASE,
        )

        for wrapper in SENSITIVE_WRAPPERS:
            for site in wrapper_calls(wrapper):
                if site.path == MBR_FUNC.relative_to(ROOT) and site.function == "MBRFuncInitialize":
                    observed_initializer_calls.add(wrapper)
                    continue
                match = guard.match(site.code)
                self.assertIsNotNone(
                    match,
                    f"{site.path}:{site.line_number} calls {wrapper} outside the supervised initializer "
                    "without an explicit initialized-library guard",
                )
                self.assertEqual(match.group(1).lower(), wrapper.lower())

        self.assertEqual(observed_initializer_calls, expected_initializer_calls)

    def test_public_image_call_wrapper_fails_closed_until_initialization_completed(self) -> None:
        public_wrapper = function_body(self.mbr_func, "DllCallMyBot")
        guard = public_wrapper.index("$g_bLibMyBotInitialized")
        blocked = public_wrapper.index("Inherited ImgLoc recognition is disabled", guard)
        self.assertLess(guard, blocked)
        self.assertNotIn("_DllCallMyBot(", public_wrapper)


if __name__ == "__main__":
    unittest.main()
