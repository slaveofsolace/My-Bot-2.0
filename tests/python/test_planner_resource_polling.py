import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLANNER = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")


class PlannerResourcePollingTests(unittest.TestCase):
    def test_idle_hidden_views_suspend_status_and_event_polling(self):
        control = PLANNER.split("function controlPollDelay()", 1)[1].split("}", 1)[0]
        events = PLANNER.split("function eventPollDelay()", 1)[1].split("}", 1)[0]
        hidden = PLANNER.split("function hiddenIdlePollingSuspended()", 1)[1].split("}", 1)[0]
        poll_control = PLANNER.split("async function pollControl()", 1)[1].split("const previousInstanceSignature", 1)[0]
        poll_events = PLANNER.split("async function pollEvents()", 1)[1].split("try {", 1)[0]
        self.assertIn("document.hidden && !controlActivityIsActive()", hidden)
        self.assertIn("document.hidden ? null : 5000", control)
        self.assertIn("document.hidden ? null : 15000", events)
        self.assertIn("if (hiddenIdlePollingSuspended())", poll_control)
        self.assertIn("CONTROL_TIMER = null", poll_control)
        self.assertIn("if (hiddenIdlePollingSuspended())", poll_events)
        self.assertIn("EVENTS_TIMER = null", poll_events)

    def test_active_control_stays_responsive(self):
        control = PLANNER.split("function controlPollDelay()", 1)[1].split("}", 1)[0]
        events = PLANNER.split("function eventPollDelay()", 1)[1].split("}", 1)[0]
        active = PLANNER.split("function controlActivityIsActive()", 1)[1].split("}", 1)[0]
        self.assertIn("CONTROL_PENDING", active)
        self.assertIn("document.hidden ? 1500 : 500", control)
        self.assertIn("document.hidden ? 5000 : 1500", events)

    def test_command_submission_wakes_control_polling_immediately(self):
        sender = PLANNER.split("async function sendControl(action)", 1)[1].split("$('controlStart').onclick", 1)[0]
        self.assertIn("clearTimeout(CONTROL_TIMER)", sender)
        self.assertIn("CONTROL_TIMER = setTimeout(pollControl, 0)", sender)
        self.assertIn("clearTimeout(EVENTS_TIMER)", sender)
        self.assertIn("EVENTS_TIMER = setTimeout(pollEvents, 0)", sender)

    def test_visibility_transition_stops_hidden_idle_and_resumes_immediately(self):
        listener = PLANNER.split("document.addEventListener('visibilitychange'", 1)[1].split("boot();", 1)[0]
        starter = PLANNER.split("function startPolls()", 1)[1].split("}", 1)[0]
        self.assertIn("if (hiddenIdlePollingSuspended()) stopPolls()", listener)
        self.assertIn("else startPolls()", listener)
        self.assertIn("if (hiddenIdlePollingSuspended()) return", starter)
        self.assertIn("pollControl()", starter)
        self.assertIn("pollEvents()", starter)


if __name__ == "__main__":
    unittest.main()
