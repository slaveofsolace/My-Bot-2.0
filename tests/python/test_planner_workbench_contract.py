import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
HTML = (ROOT / "ui" / "planner.html").read_text(encoding="utf-8")
JS = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
METADATA = json.loads((ROOT / "config" / "ui" / "run-planner.settings.json").read_text(encoding="utf-8"))


class PlannerWorkbenchContract(unittest.TestCase):
    def test_five_views_and_five_plan_groups_are_stable(self):
        self.assertEqual(re.findall(r'data-view="([^"]+)"', HTML), ["run", "plan", "village", "activity", "diagnostics"])
        self.assertIn("const VIEW_IDS = ['run', 'plan', 'village', 'activity', 'diagnostics'];", JS)
        self.assertIn("renderCapabilities();", JS)
        prefix = JS.split("const $ =", 1)[0]
        self.assertEqual(re.findall(r"id: '([^']+)'", prefix), ["match", "runtime", "targets", "between", "advanced"])

        grouped = [
            section_id
            for declaration in re.findall(r"sections:\s*\[([^]]*)\]", prefix)
            for section_id in re.findall(r"'([^']+)'", declaration)
        ]
        metadata_sections = [section["id"] for section in METADATA["sections"]]
        self.assertCountEqual(grouped, metadata_sections)
        self.assertEqual(len(grouped), len(set(grouped)))

    def test_all_settings_survive_and_free_text_types_are_explicit(self):
        settings = {setting["id"]: setting for section in METADATA["sections"] for setting in section["settings"]}
        self.assertEqual(len(settings), 46)
        self.assertEqual(settings["events.collect_daily_reward"]["default"], False)
        self.assertEqual(settings["events.collect_daily_reward"]["type"], "boolean")
        self.assertEqual(settings["run.town_hall"]["default"], 0)
        self.assertEqual(settings["runtime.instance"]["type"], "instance-select")
        self.assertEqual(settings["army.recipe_name"]["type"], "text")
        self.assertEqual(settings["run.diagnostic_note"]["type"], "text")
        self.assertIn("control.type = 'text'", JS)

    def test_apply_then_start_is_enforced_in_both_render_and_command_paths(self):
        render = JS.split("function renderControl()", 1)[1].split("function recoverControlPending", 1)[0]
        send = JS.split("async function sendControl(action)", 1)[1].split("function eventDate", 1)[0]
        self.assertIn("clientProblems(SAVED)", render)
        self.assertIn("allSettings().some(isUnsaved)", send)
        self.assertIn("!PLAN_WRITTEN", send)
        self.assertIn("clientProblems(SAVED).length", send)
        self.assertNotIn("savePlan()", send)
        self.assertIn("CONTROL_PENDING = { action, request_id: null", send)
        self.assertIn('id="savedPlanHash"', HTML)
        self.assertIn('id="visiblePlanHash"', HTML)
        self.assertIn("crypto.subtle.digest('SHA-256'", JS)
        self.assertIn("The applied plan is locked until the active run stops.", JS)

    def test_conditional_invalid_combinations_are_recoverable(self):
        self.assertIn("emulator === 'auto' && instance", JS)
        self.assertIn("emulator !== 'auto' && !instance", JS)
        self.assertIn("plan['run.strategy'] === 'smart.local' && !plan['run.diagnostic_mode']", JS)
        self.assertIn("PLAN[id] === defaultFor(setting)", JS)
        self.assertIn("PLAN[id] === 'profile-current'", JS)
        self.assertIn("Number.isInteger(number)", JS)
        self.assertIn("must use increments of ${rules.step}", JS)

    def test_native_activity_is_proof_friendly_not_a_fake_wall_clock(self):
        event_date = JS.split("function eventDate(event)", 1)[1].split("function humanizeEventType", 1)[0]
        self.assertNotIn("timestamp_ms ??", event_date)
        self.assertIn("function elapsedEventTime(event)", event_date)
        self.assertIn("+${Math.round(elapsed)}ms", event_date)
        self.assertIn("time.dateTime = `PT${elapsed / 1000}S`", JS)
        self.assertIn("['error', 'warning', 'info', 'debug']", JS)


if __name__ == "__main__":
    unittest.main()
