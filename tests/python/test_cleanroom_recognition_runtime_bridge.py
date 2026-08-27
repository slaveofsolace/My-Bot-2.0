from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.generate_cleanroom_recognition_autoit import render_contract


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "config" / "cleanroom-recognition.json"
GENERATED_PATH = ROOT / "COCBot" / "functions" / "Run" / "CleanRoomRecognitionContract.generated.au3"
BRIDGE_PATH = ROOT / "COCBot" / "functions" / "Run" / "CleanRoomRecognitionBridge.au3"


class CleanRoomRecognitionRuntimeBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.generated = GENERATED_PATH.read_text(encoding="utf-8")
        self.bridge = BRIDGE_PATH.read_text(encoding="utf-8")

    def test_generated_native_contract_is_current(self) -> None:
        self.assertEqual(render_contract(self.manifest), self.generated)

    def test_runtime_contract_is_inert_and_closed_world(self) -> None:
        providers = self.manifest["providers"]
        self.assertEqual(["CleanRoomLocal", "InheritedAuthorized", "Unavailable"], providers["states"])
        self.assertEqual("Unavailable", providers["default_state"])
        self.assertEqual("Unavailable", providers["full_profile_state"])
        self.assertFalse(providers["clean_room_local"]["published_assets"])
        self.assertFalse(providers["clean_room_local"]["supports_bot_start"])
        self.assertFalse(providers["inherited_authorized"]["enabled"])
        self.assertIn("written permission", providers["inherited_authorized"]["reason"])

        runtime = self.manifest["runtime_bridge"]
        self.assertEqual("read-only", runtime["mode"])
        self.assertFalse(runtime["legacy_dispatch_wired"])
        self.assertFalse(runtime["bot_start_wired"])
        self.assertEqual("verified-fixture-attestation-only-no-coordinate", runtime["find_tile_behavior"])
        self.assertFalse(runtime["python_adapter_packaged"])

        exports = self.manifest["legacy_exports"]
        self.assertEqual(17, len(exports))
        self.assertEqual(14, sum(item["clean_room_status"] == "unavailable" for item in exports))
        self.assertEqual(
            {"FindTile", "GetDeployableNextTo", "GetOffSetRedline"},
            {item["name"] for item in exports if item["clean_room_status"] == "implemented"},
        )

    def test_bridge_has_no_process_dll_capture_or_input_surface(self) -> None:
        for forbidden in (
            "DllCall(",
            "ShellExecute",
            "FileOpen(",
            "FileRead(",
            "FileWrite(",
            "WinActivate(",
            "Click(",
            "AndroidAdb",
            "HD-Player",
            "MyBot.run.dll",
        ):
            self.assertNotIn(forbidden, self.bridge)

    def test_find_tile_native_bridge_attests_only_and_returns_no_coordinate(self) -> None:
        start = self.bridge.index("Func CleanRoomRecognitionFixtureReplayAttested(")
        end = self.bridge.index("Func _CleanRoomRecognitionDimensionsValid(", start)
        body = self.bridge[start:end]
        self.assertNotIn("ByRef", body)
        self.assertNotIn("$aOutput", body)
        self.assertNotIn("template", body.casefold())
        self.assertNotIn("candidate", body.casefold())
        self.assertNotIn("box", body.casefold())
        self.assertIn("Return SetError(0, 0, True)", body)
        self.assertIn(
            'If StringCompare($sExport, "FindTile", 1) = 0 Then',
            self.bridge,
        )
        self.assertIn(
            "Return CleanRoomRecognitionRuntimeStatus($sExport) = $CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE",
            self.bridge,
        )

    def test_provider_state_is_typed_and_never_enables_inherited_dispatch(self) -> None:
        for token in (
            "$CLEANROOM_RECOGNITION_PROVIDER_CLEANROOMLOCAL",
            "$CLEANROOM_RECOGNITION_PROVIDER_INHERITEDAUTHORIZED",
            "$CLEANROOM_RECOGNITION_PROVIDER_UNAVAILABLE",
            "$CLEANROOM_RECOGNITION_PROVIDER_STATES",
            "$CLEANROOM_RECOGNITION_DEFAULT_PROVIDER",
            "$CLEANROOM_RECOGNITION_FULL_PROFILE_PROVIDER",
            "$CLEANROOM_RECOGNITION_CLEANROOMLOCAL_SUPPORTS_BOT_START",
            "$CLEANROOM_RECOGNITION_INHERITEDAUTHORIZED_ENABLED",
        ):
            self.assertIn(token, self.generated)
        self.assertIn('"CleanRoomLocal|InheritedAuthorized|Unavailable"', self.generated)
        self.assertIn('$CLEANROOM_RECOGNITION_INHERITEDAUTHORIZED_ENABLED = False', self.generated)
        self.assertIn('$CLEANROOM_RECOGNITION_CLEANROOMLOCAL_SUPPORTS_BOT_START = False', self.generated)

        provider = self.bridge[
            self.bridge.index("Func CleanRoomRecognitionProviderState(") :
            self.bridge.index("EndFunc   ;==>CleanRoomRecognitionProviderState")
        ]
        self.assertIn("$CLEANROOM_RECOGNITION_DEFAULT_PROVIDER", provider)
        self.assertIn("$CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE", provider)
        self.assertIn("$CLEANROOM_RECOGNITION_STATUS_FIXTURE_REPLAY_ONLY", provider)
        self.assertIn("$CLEANROOM_RECOGNITION_PROVIDER_CLEANROOMLOCAL", provider)
        self.assertIn("$CLEANROOM_RECOGNITION_PROVIDER_UNAVAILABLE", provider)
        self.assertNotIn("$CLEANROOM_RECOGNITION_PROVIDER_INHERITEDAUTHORIZED", provider)

    def test_legacy_recognition_dispatch_stays_blocked(self) -> None:
        mbr = (ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3").read_text(encoding="utf-8-sig")
        availability_start = mbr.index("Func MBRFuncRecognitionAvailable()")
        availability_end = mbr.index("EndFunc", availability_start)
        self.assertIn("Return False", mbr[availability_start:availability_end])
        dispatch_start = mbr.index("Func DllCallMyBot(")
        dispatch_end = mbr.index("EndFunc", dispatch_start)
        dispatch = mbr[dispatch_start:dispatch_end]
        self.assertIn("Inherited ImgLoc recognition is disabled", dispatch)
        self.assertNotIn("CleanRoomRecognition", dispatch)
        provider_start = mbr.index("Func MBRFuncRecognitionProviderState()")
        provider_end = mbr.index("EndFunc", provider_start)
        self.assertIn('Return "Unavailable"', mbr[provider_start:provider_end])

        control = (ROOT / "COCBot" / "functions" / "Run" / "RunControlBridge.au3").read_text(encoding="utf-8-sig")
        self.assertIn('"recognition_provider"', control)
        self.assertIn("MBRFuncRecognitionProviderState()", control)
        self.assertIn('"recognition_provider_reason"', control)
        self.assertIn("MBRFuncRecognitionProviderReason()", control)

    def test_main_runtime_includes_bridge_without_startup_call(self) -> None:
        main = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
        mbr_include = main.index('#include "COCBot\\functions\\Other\\MBRFunc.au3"')
        bridge_include = main.index('#include "COCBot\\functions\\Run\\CleanRoomRecognitionBridge.au3"')
        references_include = main.index('#include "COCBot\\MBR References.au3"')
        self.assertLess(mbr_include, bridge_include)
        self.assertLess(bridge_include, references_include)
        without_include = main.replace('#include "COCBot\\functions\\Run\\CleanRoomRecognitionBridge.au3"', "")
        self.assertNotIn("CleanRoomRecognition", without_include)

    def test_runtime_keeps_python_adapter_and_pillow_outside_package_contract(self) -> None:
        python_release = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        powershell_release = (ROOT / "tools" / "Build-Release.ps1").read_text(encoding="utf-8-sig")
        planner = (ROOT / "tools" / "planner_ui.py").read_text(encoding="utf-8")
        for source in (python_release, powershell_release, planner):
            self.assertNotIn("cleanroom_recognition.py", source)
            self.assertNotIn("cleanroom-recognition.json", source)
            self.assertNotIn("Pillow", source)
        self.assertIn('"COCBot",', python_release)
        self.assertIn('"COCBot"', powershell_release)


if __name__ == "__main__":
    unittest.main()
