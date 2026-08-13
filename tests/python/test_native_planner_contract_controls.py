import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR = (ROOT / "tools" / "generate_run_planner_autoit.py").read_text(encoding="utf-8")
GENERATED = (ROOT / "COCBot" / "GUI" / "RunPlannerMetadata.generated.au3").read_text(encoding="utf-8")
DESIGN = (ROOT / "COCBot" / "GUI" / "MBR GUI Design Run Planner.au3").read_text(encoding="utf-8")
CONTROL = (ROOT / "COCBot" / "GUI" / "MBR GUI Control Run Planner.au3").read_text(encoding="utf-8")
SETTINGS = json.loads((ROOT / "config" / "ui" / "run-planner.settings.json").read_text(encoding="utf-8"))


class NativePlannerContractControls(unittest.TestCase):
    def test_generator_carries_native_fixed_contract(self):
        self.assertIn("eRunPlannerSettingNativeFixedValue", GENERATOR)
        self.assertIn("eRunPlannerSettingNativeFixedReason", GENERATOR)
        self.assertIn("eRunPlannerSettingNativeFixedValue", GENERATED)
        self.assertIn("eRunPlannerSettingNativeFixedReason", GENERATED)

    def test_every_catalog_fixed_value_is_rendered(self):
        fixed = {
            setting["id"]: setting["native_fixed_value"]
            for section in SETTINGS["sections"]
            for setting in section["settings"]
            if "native_fixed_value" in setting
        }
        self.assertEqual(
            fixed,
            {
                "account.queue": "",
                "army.manage_training": False,
                "army.recipe_name": "",
                "search.max_seconds": 0,
                "donate.keep_army": True,
                "donate.max_per_run": 0,
                "events.clan_games_point_cap": 0,
                "pacing.retry_attempts": 0,
            },
        )
        for setting_id in fixed:
            self.assertIn(f'$eRunPlannerSettingId] = "{setting_id}"', GENERATED)

    def test_native_controls_are_disabled_and_hand_edits_are_overridden(self):
        self.assertIn("Func _RunPlannerApplyNativeFixedState", DESIGN)
        self.assertIn("GUICtrlSetState($hControl, $GUI_DISABLE)", DESIGN)
        self.assertIn("_RunPlannerApplyAllNativeFixedStates()", CONTROL)
        self.assertIn("$vValue = $vFixed", CONTROL)
        self.assertIn("Fixed by native contract:", CONTROL)

    def test_unimplemented_combo_rows_are_not_selectable(self):
        self.assertIn("Func _RunPlannerOptionSelectable", DESIGN)
        self.assertIn('Case "planned", "unsupported"', DESIGN)
        label_list = DESIGN[DESIGN.index("Func _RunPlannerOptionLabelList"):DESIGN.index("EndFunc   ;==>_RunPlannerOptionLabelList")]
        self.assertIn("If Not _RunPlannerOptionSelectable($i) Then ContinueLoop", label_list)


if __name__ == "__main__":
    unittest.main()
