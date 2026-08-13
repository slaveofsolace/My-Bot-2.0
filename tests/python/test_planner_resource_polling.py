import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLANNER = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")


class PlannerResourcePollingTests(unittest.TestCase):
    def test_idle_and_hidden_views_use_slow_polling(self):
        control = PLANNER.split("function controlPollDelay()", 1)[1].split("}", 1)[0]
        events = PLANNER.split("function eventPollDelay()", 1)[1].split("}", 1)[0]
        self.assertIn("document.hidden ? 5000 : 2000", control)
        self.assertIn("document.hidden ? 15000 : 5000", events)

    def test_active_control_stays_responsive(self):
        control = PLANNER.split("function controlPollDelay()", 1)[1].split("}", 1)[0]
        events = PLANNER.split("function eventPollDelay()", 1)[1].split("}", 1)[0]
        self.assertIn("CONTROL_PENDING", control)
        self.assertIn("document.hidden ? 1500 : 500", control)
        self.assertIn("document.hidden ? 5000 : 1500", events)

    def test_visibility_transition_restarts_pollers(self):
        self.assertIn("document.addEventListener('visibilitychange'", PLANNER)
        self.assertIn("if (BOOT_READY) startPolls();", PLANNER)


if __name__ == "__main__":
    unittest.main()
