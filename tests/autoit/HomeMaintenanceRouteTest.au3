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

Local $oDailyOnly = CreateCollectorsIntent()
Local $oDailyOnlyPlan = $oDailyOnly.Item("plan")
$oDailyOnlyPlan.Item("events_collect_resources") = False
$oDailyOnlyPlan.Item("events_collect_daily_reward") = True
AssertTrue(RunExecutionContractValidate($oDailyOnly, $sError), "Home maintenance accepts an explicit Daily Reward-only pass: " & $sError)

Local $oLootOnly = CreateCollectorsIntent()
Local $oLootOnlyPlan = $oLootOnly.Item("plan")
$oLootOnlyPlan.Item("events_collect_resources") = False
$oLootOnlyPlan.Item("events_collect_loot_cart") = True
AssertTrue(RunExecutionContractValidate($oLootOnly, $sError), "Home maintenance accepts an explicit Loot Cart-only pass: " & $sError)

Local $oTreasuryOnly = CreateCollectorsIntent()
Local $oTreasuryOnlyPlan = $oTreasuryOnly.Item("plan")
$oTreasuryOnlyPlan.Item("events_collect_resources") = False
$oTreasuryOnlyPlan.Item("events_collect_treasury") = True
AssertTrue(RunExecutionContractValidate($oTreasuryOnly, $sError), "Home maintenance accepts an explicit Treasury-only pass: " & $sError)

Local $oNoMaintenance = CreateCollectorsIntent()
Local $oNoMaintenancePlan = $oNoMaintenance.Item("plan")
$oNoMaintenancePlan.Item("events_collect_resources") = False
$oNoMaintenancePlan.Item("events_collect_daily_reward") = False
$oNoMaintenancePlan.Item("events_collect_loot_cart") = False
$oNoMaintenancePlan.Item("events_collect_treasury") = False
AssertTrue(Not RunExecutionContractValidate($oNoMaintenance, $sError), "Home maintenance rejects a pass with no selected work")

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
Local $oDailyIssuedEvent = RunEventCreate("maintenance.daily-reward.claim-issued", 3, 1200, "home-fixture", "warning", _
		"One Daily Reward Claim input was issued; claim_attempts=1", "profile-a", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oDailyIssuedEvent), "Daily Reward input is reported as issued rather than falsely confirmed")
Local $oLootIssuedEvent = RunEventCreate("maintenance.loot-cart.collect-issued", 4, 1300, "home-fixture", "warning", _
		"One Loot Cart Collect input was issued; collect_attempts=1", "profile-a", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oLootIssuedEvent), "Loot Cart input is reported as issued rather than falsely confirmed")
Local $oTreasuryIssuedEvent = RunEventCreate("maintenance.treasury.confirm-issued", 5, 1400, "home-fixture", "warning", _
		"One contextual Treasury confirmation input was issued; confirm_attempts=1", "profile-a", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oTreasuryIssuedEvent), "Treasury input is reported as issued rather than falsely confirmed")

ConsoleWrite("Home maintenance route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
