import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class RuntimeElevationContractTest(unittest.TestCase):
    def test_per_user_runtime_hosts_do_not_request_elevation(self) -> None:
        runtime_hosts = (
            "My Bot 2.0.au3",
            "MyBot.run.MiniGui.au3",
            "MyBot.run.au3",
            "MyBot.run.Watchdog.au3",
            "MyBot.run.Wmi.au3",
            "MyBot.run.EngineProbe.au3",
        )
        for relative_path in runtime_hosts:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn(
                "#RequireAdmin",
                source,
                msg=f"{relative_path} must remain a per-user, unelevated runtime host",
            )

    def test_install_documentation_states_fail_closed_elevation_boundary(self) -> None:
        install_doc = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("runs per-user without elevation", install_doc)
        self.assertIn("an elevated emulator is not attached or controlled", install_doc)


if __name__ == "__main__":
    unittest.main()
