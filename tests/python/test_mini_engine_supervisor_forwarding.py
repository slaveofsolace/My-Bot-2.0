from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
MINI_SOURCE = ROOT / "MyBot.run.MiniGui.au3"


def launch_backend_source() -> str:
    source = MINI_SOURCE.read_text(encoding="utf-8")
    match = re.search(
        r"Func LaunchBotBackend\([^\r\n]*\)(.*?)EndFunc\s*;==>LaunchBotBackend",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("LaunchBotBackend function was not found")
    return match.group(1)


class MiniEngineSupervisorForwardingTests(unittest.TestCase):
    def test_forwards_only_valid_captured_context_around_single_backend_run(self) -> None:
        launch = launch_backend_source()
        run_line = "$pid = Run($cmd, @ScriptDir)"

        self.assertEqual(launch.count(run_line), 1)
        self.assertIn("If $g_bMBRFuncEngineSupervisorValid Then", launch)

        ordered_lines = (
            "EnvSet($g_sMBRFuncEngineTokenEnv, $g_sMBRFuncEngineSupervisorToken)",
            "EnvSet($g_sMBRFuncEngineLauncherPidEnv, $g_sMBRFuncEngineLauncherPidText)",
            "EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, $g_sMBRFuncEngineLauncherCreated)",
            run_line,
            "Local $iRunError = @error",
            'EnvSet($g_sMBRFuncEngineTokenEnv, "")',
            'EnvSet($g_sMBRFuncEngineLauncherPidEnv, "")',
            'EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, "")',
        )
        offsets = [launch.index(line) for line in ordered_lines]
        self.assertEqual(offsets, sorted(offsets))

        after_run = launch[offsets[3] :]
        self.assertRegex(after_run, r"^\$pid = Run\(\$cmd, @ScriptDir\)\s*\r?\n\s*Local \$iRunError = @error")

    def test_supervisor_secret_is_never_added_to_backend_arguments(self) -> None:
        launch = launch_backend_source()
        command_construction = launch[: launch.index("$pid = Run($cmd, @ScriptDir)")]

        for secret_symbol in (
            "$g_sMBRFuncEngineSupervisorToken",
            "$g_sMBRFuncEngineLauncherPidText",
            "$g_sMBRFuncEngineLauncherCreated",
        ):
            symbol_lines = [line for line in command_construction.splitlines() if secret_symbol in line]
            self.assertEqual(len(symbol_lines), 1)
            self.assertIn("EnvSet(", symbol_lines[0])
            self.assertNotIn("$cmd", symbol_lines[0])
            self.assertNotIn("$sParam", symbol_lines[0])


if __name__ == "__main__":
    unittest.main()
