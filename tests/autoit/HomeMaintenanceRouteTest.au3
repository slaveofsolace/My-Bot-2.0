#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\RunExecutionContract.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Func CreateCollectorsIntent($bDiagnostic = True)
	Local $oPlan = RunPlanCreateDefault("regular", $HOME_MAINTENANCE_COLLECTORS_STRATEGY, "profile-current")
	$oPlan.Item("max_battles") = 0
	$oPlan.Item("max_failures") = 0
	$oPlan.Item("army_wait_for_full") = False
	$oPlan.Item("events_collect_resources") = True
	$oPlan.Item("emulator") = "bluestacks5"
	$oPlan.Item("emulator_instance") = "Pie64"

	Local $oLoadout = HeroLoadoutCreate(0)
	Local $sError = ""
	Local $oIntent = RunIntentCreate($oPlan, "regular", $oLoadout, $sError)
	If Not IsObj($oIntent) Then Return SetError(1, 0, 0)
	If Not RunIntentSetProfile($oIntent, "MyVillage") Then Return SetError(1, 1, 0)
	If $bDiagnostic And Not RunIntentEnableDiagnostic($oIntent, "supervised collectors fixture", $sError) Then _
		Return SetError(2, 0, 0)
	Return $oIntent
EndFunc   ;==>CreateCollectorsIntent

Local $sError = ""
Local $oIntent = CreateCollectorsIntent()
AssertTrue(IsObj($oIntent), "collectors-only intent is created")
AssertTrue(HomeMaintenanceRouteSelected($oIntent), "collectors-only route is explicitly selected")
AssertTrue(HomeMaintenanceRouteValidate($oIntent, $sError), "collectors-only route contract validates: " & $sError)
AssertTrue(RunExecutionContractValidate($oIntent, $sError), "execution contract dispatches to the collectors route: " & $sError)

Local $oNoProfile = CreateCollectorsIntent()
RunIntentSetProfile($oNoProfile, "")
AssertTrue(Not HomeMaintenanceRouteValidate($oNoProfile, $sError), "collectors-only route rejects an empty account binding")
Local $oUnsafeProfile = CreateCollectorsIntent()
RunIntentSetProfile($oUnsafeProfile, "wrong|account")
AssertTrue(Not HomeMaintenanceRouteValidate($oUnsafeProfile, $sError), "collectors-only route rejects an unsafe account binding")

Local $oAutoEmulator = CreateCollectorsIntent()
$oAutoEmulator.Item("plan").Item("emulator") = "auto"
AssertTrue(Not HomeMaintenanceRouteValidate($oAutoEmulator, $sError), "collectors-only route rejects automatic emulator selection")
Local $oBlankInstance = CreateCollectorsIntent()
$oBlankInstance.Item("plan").Item("emulator_instance") = ""
AssertTrue(Not HomeMaintenanceRouteValidate($oBlankInstance, $sError), "collectors-only route rejects a blank instance")
Local $oUnsafeInstance = CreateCollectorsIntent()
$oUnsafeInstance.Item("plan").Item("emulator_instance") = "Pie64|other"
AssertTrue(Not HomeMaintenanceRouteValidate($oUnsafeInstance, $sError), "collectors-only route rejects an unsafe instance")

Local $oNoDiagnostic = CreateCollectorsIntent(False)
AssertTrue(Not RunExecutionContractValidate($oNoDiagnostic, $sError), "collectors-only route rejects missing diagnostic acknowledgement")
AssertTrue(StringInStr($sError, "supervised diagnostic") > 0, "diagnostic rejection explains the required supervision")

Local $oNoCollectors = CreateCollectorsIntent()
Local $oNoCollectorsPlan = $oNoCollectors.Item("plan")
$oNoCollectorsPlan.Item("events_collect_resources") = False
AssertTrue(Not RunExecutionContractValidate($oNoCollectors, $sError), "collectors-only route rejects a disabled collector actuator")

Local $oBattleShaped = CreateCollectorsIntent()
Local $oBattlePlan = $oBattleShaped.Item("plan")
$oBattlePlan.Item("max_battles") = 1
AssertTrue(Not RunExecutionContractValidate($oBattleShaped, $sError), "collectors-only route rejects any battle quota")
AssertTrue(StringInStr($sError, "exactly one pass") > 0, "battle-shaped rejection explains the one-pass boundary")

Local $oGenericPlan = RunPlanCreateDefault("regular", "legacy.standard", "profile-current")
$oGenericPlan.Item("events_collect_resources") = True
Local $oGenericLoadout = HeroLoadoutCreate(0)
Local $oGenericIntent = RunIntentCreate($oGenericPlan, "regular", $oGenericLoadout, $sError)
AssertTrue(IsObj($oGenericIntent), "generic battle intent is created")
AssertTrue(Not RunExecutionContractValidate($oGenericIntent, $sError), "generic battle route rejects collector work")
AssertTrue(StringInStr($sError, "Home maintenance") > 0, "generic rejection points to the explicit collectors route")

Local $oHomeEvent = RunEventCreate("maintenance.home-verified", 1, 1000, "home-fixture", "info", _
		"Home Village main screen re-proven", "profile-a", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oHomeEvent), "home verification lifecycle event is accepted")
Local $oNoneActionableEvent = RunEventCreate("maintenance.collectors.none-actionable", 2, 1100, "home-fixture", "warning", _
		"No collector click was issued; collector_clicks=0", "profile-a", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oNoneActionableEvent), "zero-click collector outcome is explicit")

ConsoleWrite("Home maintenance route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
