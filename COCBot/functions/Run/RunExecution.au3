; #FUNCTION# ====================================================================================================================
; Name ..........: Run execution
; Description ...: Crosses the explicit planner Apply/Start boundary and adapts supported values to the inherited engine.
; Remarks .......: Planner overrides are in-memory for one run. Profile INI files remain untouched.
; ===============================================================================================================================
#include-once
#include "RunExecutionContract.au3"
#include "RunPlanFile.au3"
#include "RunPacingGate.au3"
#include "RunEventLog.au3"
#include "RunProfileWriteGuard.au3"

Global $g_oRunExecutionIntent = 0
Global $g_oRunExecutionSession = 0
Global $g_bRunExecutionPrepared = False
Global $g_bRunExecutionActive = False
Global $g_hRunExecutionStarted = 0
Global $g_iRunExecutionBattleBaseline = 0
Global $g_iRunExecutionBattleObserved = 0
Global $g_iRunExecutionGoldBaseline = 0
Global $g_iRunExecutionElixirBaseline = 0
Global $g_iRunExecutionDarkBaseline = 0
Global $g_sRunExecutionMessage = "Legacy profile mode"
Global $g_sRunExecutionDailyRewardState = "not-seen"
Global $g_sRunExecutionDailyRewardDetail = ""
Global $g_iRunExecutionDailyRewardAttempts = 0
Global $g_bRunExecutionDailyRewardClickIssued = False
; A standard planned attack is successful only after the live attack bar proves that the main
; deployable troops disappeared. Sending click commands is not deployment evidence.
Global $g_bRunExecutionDeploymentVerified = False
Global $g_iRunExecutionDeployableBefore = 0
Global $g_iRunExecutionDeployableAfter = -1
; True outside a planned override. A plan may turn this off for one already-trained army; every
; completion/cancellation path restores True before the inherited loop can train again.
Global $g_bRunExecutionManageTraining = True
Global $g_bRunExecutionProfileSnapshotCaptured = False
Global $g_bRunExecutionEmulatorChanged = False
Global $g_iRunExecutionSnapshotAndroidConfig = 0
Global $g_sRunExecutionSnapshotAndroidEmulator = ""
Global $g_sRunExecutionSnapshotAndroidInstance = ""
Global $g_asRunExecutionSnapshotAttackScript[$g_iModeCount]
Global $g_abRunExecutionSnapshotAttackTypeEnable[$g_iModeCount + 1]
Global $g_aiRunExecutionSnapshotAttackAlgorithm[$g_iModeCount]
Global $g_aiRunExecutionSnapshotAttackStdDropSides[$g_iModeCount + 1]
Global $g_abRunExecutionSnapshotAttackStdSmartAttack[$g_iModeCount + 1]
Global $g_aiRunExecutionSnapshotAttackUseHeroes[$g_iModeCount]
Global $g_abRunExecutionSnapshotAttackDropCC[$g_iModeCount]
Global $g_abRunExecutionSnapshotAttackUseRageSpell[$g_iModeCount]
Global $g_abRunExecutionSnapshotAttackUseFreezeSpell[$g_iModeCount]
Global $g_aiRunExecutionSnapshotSearchHeroWaitEnable[$g_iModeCount]
Global $g_abRunExecutionSnapshotSearchSpellsWaitEnable[$g_iModeCount]
Global $g_abRunExecutionSnapshotSearchSiegeWaitEnable[$g_iModeCount]
Global $g_aiRunExecutionSnapshotFilterMeetGE[$g_iModeCount]
Global $g_aiRunExecutionSnapshotFilterMinGold[$g_iModeCount]
Global $g_aiRunExecutionSnapshotFilterMinElixir[$g_iModeCount]
Global $g_abRunExecutionSnapshotFilterMeetDEEnable[$g_iModeCount]
Global $g_aiRunExecutionSnapshotFilterMeetDEMin[$g_iModeCount]
Global $g_aiRunExecutionSnapshotArmyCompSpells[$eSpellCount]
Global $g_aiRunExecutionSnapshotArmyCompSiegeMachines[$eSiegeMachineCount]
Global $g_bRunExecutionSnapshotChkDonate = False
Global $g_bRunExecutionSnapshotDonateLikeCrazy = False
Global $g_bRunExecutionSnapshotRequestTroopsEnable = False
Global $g_bRunExecutionSnapshotChkClanGamesEnabled = False
Global $g_bRunExecutionSnapshotChkCollect = False
Global $g_bRunExecutionSnapshotChkCollectCartFirst = False
Global $g_bRunExecutionSnapshotChkTreasuryCollect = False
Global $g_bRunExecutionSnapshotChkCollectAchievements = False
Global $g_bRunExecutionSnapshotChkCollectFreeMagicItems = False
Global $g_bRunExecutionSnapshotChkCollectRewards = False
Global $g_bRunExecutionSnapshotChkSellRewards = False
Global $g_bRunExecutionSnapshotAutoLabUpgradeEnable = False
Global $g_bRunExecutionSnapshotAutoUpgradeWallsEnable = False
Global $g_bRunExecutionSnapshotAutoUpgradeEnabled = False
Global $g_bRunExecutionSnapshotChkSwitchAcc = False
Global $g_bRunExecutionSnapshotPlannedDropCCHoursEnable = False
Global $g_bRunExecutionSnapshotUseCCBalanced = False

Func RunExecutionPlanActive()
	Return $g_bRunExecutionActive
EndFunc   ;==>RunExecutionPlanActive

; True as soon as a reviewed plan owns the Start attempt, including the screen-readiness phase before
; RunExecutionBegin(). Popup handlers use this to avoid inheriting reward clicks from the legacy profile.
Func RunExecutionManagedPlanPrepared()
	Return ($g_bRunExecutionPrepared Or $g_bRunExecutionActive) And IsObj($g_oRunExecutionIntent)
EndFunc   ;==>RunExecutionManagedPlanPrepared

Func RunExecutionDailyRewardClaimAllowed()
	If Not RunExecutionManagedPlanPrepared() Or Not HomeMaintenanceRouteSelected($g_oRunExecutionIntent) Then Return False
	Local $oPlan = $g_oRunExecutionIntent.Item("plan")
	Return IsObj($oPlan) And $oPlan.Exists("events_collect_daily_reward") And $oPlan.Item("events_collect_daily_reward")
EndFunc   ;==>RunExecutionDailyRewardClaimAllowed

Func RunExecutionRecordDailyReward($sState, $iAttempts, $bClickIssued, $sDetail = "")
	$g_sRunExecutionDailyRewardState = StringLower(StringStripWS(String($sState), $STR_STRIPALL))
	$g_iRunExecutionDailyRewardAttempts = Int($iAttempts)
	$g_bRunExecutionDailyRewardClickIssued = $bClickIssued ? True : False
	$g_sRunExecutionDailyRewardDetail = String($sDetail)
	Return True
EndFunc   ;==>RunExecutionRecordDailyReward

Func RunExecutionPreparedIntent()
	If Not IsObj($g_oRunExecutionIntent) Then Return SetError(1, 0, 0)
	Return $g_oRunExecutionIntent
EndFunc   ;==>RunExecutionPreparedIntent

Func HomeMaintenanceRouteActive()
	Return $g_bRunExecutionActive And IsObj($g_oRunExecutionIntent) And HomeMaintenanceRouteSelected($g_oRunExecutionIntent)
EndFunc   ;==>HomeMaintenanceRouteActive

Func ClanRequestRouteActive()
	Return $g_bRunExecutionActive And IsObj($g_oRunExecutionIntent) And ClanRequestRouteSelected($g_oRunExecutionIntent)
EndFunc   ;==>ClanRequestRouteActive

; Bind request-only work at the last native boundary that knows the actually loaded profile. The
; browser plan intentionally carries no account identifier; using the live profile prevents a stale
; saved plan from naming or switching another account. Repeated Apply/Load accepts only the same id.
Func RunExecutionBindCurrentProfileForHomeRoute(ByRef $oIntent, ByRef $sError)
	$sError = ""
	Local $bClanRequest = ClanRequestRouteSelected($oIntent)
	Local $bCollectors = HomeMaintenanceRouteSelected($oIntent)
	If Not $bClanRequest And Not $bCollectors Then Return True
	Local $sRouteName = $bClanRequest ? "Clan request" : "Home maintenance"
	Local $sActiveProfile = StringStripWS(String($g_sProfileCurrentName), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sActiveProfile = "" Or StringLen($sActiveProfile) > 64 Or _
			Not StringRegExp($sActiveProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = $sRouteName & " cannot bind an empty or unsafe active profile/account"
		Return SetError(1, 0, False)
	EndIf
	Local $sBound = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sBound = "" Then
		If Not RunIntentSetProfile($oIntent, $sActiveProfile) Then
			$sError = $sRouteName & " could not bind the active profile/account at Start"
			Return SetError(2, 0, False)
		EndIf
		Return True
	EndIf
	Local $bMatches = $bClanRequest ? ClanRequestRouteAccountMatches($oIntent, $sActiveProfile) : _
			HomeMaintenanceRouteAccountMatches($oIntent, $sActiveProfile)
	If Not $bMatches Then
		$sError = $sRouteName & " plan is bound to a different active profile/account"
		Return SetError(3, 0, False)
	EndIf
	Return True
EndFunc   ;==>RunExecutionBindCurrentProfileForHomeRoute

Func RunExecutionMessage()
	Return $g_sRunExecutionMessage
EndFunc   ;==>RunExecutionMessage

Func RunExecutionSessionId()
	If Not IsObj($g_oRunExecutionSession) Then Return ""
	Return String($g_oRunExecutionSession.Item("session_id"))
EndFunc   ;==>RunExecutionSessionId

Func RunExecutionShouldManageTraining()
	Return $g_bRunExecutionManageTraining
EndFunc   ;==>RunExecutionShouldManageTraining

; A bounded current-army plan performs no own-village building work. Current scenery may not have
; inherited stone/tree zoom anchors, so requiring legacy village calibration would restart CoC even
; after the main-screen pixel and chat image have already proven readiness.
Func RunExecutionSkipVillageZoomCalibration()
	If Not $g_bRunExecutionPrepared Or $g_bRunExecutionManageTraining Then Return False
	Return True
EndFunc   ;==>RunExecutionSkipVillageZoomCalibration

; Passive combat and both single-purpose Home routes suppress profile-owned pending actions and do
; not consume own-building coordinates. Exact profile/emulator binding plus a pixel-proven Home
; screen is their safe identity boundary; protected template recognition remains outside the fork.
Func RunExecutionSkipPendingNotifications()
	Return $g_bRunExecutionPrepared And Not $g_bRunExecutionManageTraining
EndFunc   ;==>RunExecutionSkipPendingNotifications

Func _LootCartLiveStopRequested()
	Return RunControlStopRequested() Or Not $g_bRunState
EndFunc   ;==>_LootCartLiveStopRequested

Func _LootCartLiveParseCart(ByRef $aMatches)
	If Not IsArray($aMatches) Then Return LootCartObservationCreate($LOOT_CART_STATE_ABSENT)
	If UBound($aMatches, 1) = 0 Then Return LootCartObservationCreate($LOOT_CART_STATE_ABSENT)
	; Multiple matches are ambiguous and must not grant an input coordinate.
	If UBound($aMatches, 1) <> 1 Then Return 0
	Local $aResult = $aMatches[0]
	If Not IsArray($aResult) Or UBound($aResult) < 2 Then Return 0
	Local $aPoint = StringSplit(String($aResult[1]), ",", $STR_NOCOUNT)
	If Not IsArray($aPoint) Or UBound($aPoint) <> 2 Then Return 0
	Return LootCartObservationCreate($LOOT_CART_STATE_AVAILABLE, Int($aPoint[0]), Int($aPoint[1]))
EndFunc   ;==>_LootCartLiveParseCart

Func _LootCartLiveDetectCart()
	If _LootCartLiveStopRequested() Then Return 0
	If Not IsMainPage(1) Then Return 0
	; Search only the union of the inherited default/custom-scenery cart regions. Widening this to the
	; whole village creates scenery false positives; opening chat to expose the region is forbidden.
	Local $sSearchArea = GetDiamondFromRect("0," & (180 + $g_iMidOffsetY) & ",150," & (320 + $g_iMidOffsetY))
	; One fresh framebuffer and exactly one cart match are required. Two returned points are enough to
	; prove ambiguity and fail closed without scanning an unbounded result set.
	Local $aCart = findMultiple($g_sImgCollectLootCart, $sSearchArea, $sSearchArea, 0, 1000, 2, _
			"objectname,objectpoints", True)
	Return _LootCartLiveParseCart($aCart)
EndFunc   ;==>_LootCartLiveDetectCart

Func _LootCartLiveIssueCart($iX, $iY)
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#LootCartOpen")
	If $bIssued Then RunEventLogMaintenanceLootCartOpenIssued(1)
	Return $bIssued
EndFunc   ;==>_LootCartLiveIssueCart

Func _LootCartLiveDetectCollect()
	For $iAttempt = 1 To 6
		If _LootCartLiveStopRequested() Then Return 0
		; findButton receives True so a cached button can never authorize Collect.
		Local $aCollect = findButton("CollectLootCart", Default, 1, True)
		If IsArray($aCollect) And UBound($aCollect, 1) = 2 Then _
			Return LootCartObservationCreate($LOOT_CART_STATE_COLLECT_READY, Int($aCollect[0]), Int($aCollect[1]))
		If $iAttempt < 6 Then
			If _Sleep(250, True, True, False) Then Return 0
			If _LootCartLiveStopRequested() Then Return 0
		EndIf
	Next
	Return LootCartObservationCreate($LOOT_CART_STATE_COLLECT_MISSING)
EndFunc   ;==>_LootCartLiveDetectCollect

Func _LootCartLiveIssueCollect($iX, $iY)
	; LootCartRouteRunAdapter performs the immediate Stop poll and one-attempt latch.
	; This callback is exactly one input command: no Okay, confirmation, gem conversion, retry, or fallback.
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#LootCartCollect")
	If $bIssued Then RunEventLogMaintenanceLootCartCollectIssued(1)
	Return $bIssued
EndFunc   ;==>_LootCartLiveIssueCollect

Func _LootCartLiveProveHome()
	; Observation-only: never close a window or issue cleanup input. A Stop authorizes no more capture.
	For $iAttempt = 1 To 8
		If _LootCartLiveStopRequested() Then Return False
		ForceCaptureRegion()
		_CaptureRegions()
		If IsMainPage(1) Then Return True
		If $iAttempt < 8 Then
			If _Sleep(250, True, True, False) Then Return False
			If _LootCartLiveStopRequested() Then Return False
		EndIf
	Next
	Return False
EndFunc   ;==>_LootCartLiveProveHome

Func _TreasuryLiveStopRequested()
	Return RunControlStopRequested() Or Not $g_bRunState
EndFunc   ;==>_TreasuryLiveStopRequested

Func _TreasuryLiveDetectCastle()
	If _TreasuryLiveStopRequested() Then Return 0
	If Not IsMainPage(1) Then Return 0

	; Refuse a transfer when any Home resource storage is already visibly full. One shared fresh frame
	; feeds all three decisions so a later input is never authorized from mixed geometry.
	ForceCaptureRegion()
	_CaptureRegions()
	Local $aGoldFull = _FullResPixelSearch($aIsGoldFull[0], $aIsGoldFull[0] + 4, $aIsGoldFull[1], 1, _
			Hex(0x0D0D0D, 6), $aIsGoldFull[2], $aIsGoldFull[3], $g_bNoCapturePixel)
	Local $aElixirFull = _FullResPixelSearch($aIsElixirFull[0], $aIsElixirFull[0] + 4, $aIsElixirFull[1], 1, _
			Hex(0x0D0D0D, 6), $aIsElixirFull[2], $aIsElixirFull[3], $g_bNoCapturePixel)
	Local $aDarkFull = _FullResPixelSearch($aIsDarkElixirFull[0], $aIsDarkElixirFull[0] + 4, $aIsDarkElixirFull[1], 1, _
			Hex(0x0D0D0D, 6), $aIsDarkElixirFull[2], $aIsDarkElixirFull[3], $g_bNoCapturePixel)
	If IsArray($aGoldFull) Or IsArray($aElixirFull) Or IsArray($aDarkFull) Then _
		Return TreasuryObservationCreate($TREASURY_STATE_HOME_STORAGE_FULL)

	If Not IsArray($g_aiClanCastlePos) Or UBound($g_aiClanCastlePos) < 2 Then _
		Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_MISSING)
	If Int($g_aiClanCastlePos[0]) < 0 Or Int($g_aiClanCastlePos[1]) < 0 Or Not isInsideDiamond($g_aiClanCastlePos) Then _
		Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_MISSING)
	Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_READY, Int($g_aiClanCastlePos[0]), Int($g_aiClanCastlePos[1]))
EndFunc   ;==>_TreasuryLiveDetectCastle

Func _TreasuryLiveIssueCastle($iX, $iY)
	If _TreasuryLiveStopRequested() Then Return False
	Local $bIssued = BuildingClick(Int($iX), Int($iY), "#TreasuryCastle")
	If $bIssued Then RunEventLogMaintenanceTreasuryCastleIssued()
	Return $bIssued
EndFunc   ;==>_TreasuryLiveIssueCastle

Func _TreasuryLiveDetectEntry()
	For $iAttempt = 1 To 6
		If _TreasuryLiveStopRequested() Then Return 0
		Local $aClanCastleInfo = BuildingInfo(242, 475 + $g_iBottomOffsetY)
		If IsArray($aClanCastleInfo) And UBound($aClanCastleInfo) >= 3 And _
				StringInStr(String($aClanCastleInfo[1]), "clan") > 0 Then
			Local $aTreasury = findButton("Treasury", Default, 1, True)
			If IsArray($aTreasury) And UBound($aTreasury, 1) = 2 Then _
				Return TreasuryObservationCreate($TREASURY_STATE_ENTRY_READY, Int($aTreasury[0]), Int($aTreasury[1]))
		EndIf
		If $iAttempt < 6 Then
			If _Sleep(250, True, True, False) Then Return 0
			If _TreasuryLiveStopRequested() Then Return 0
		EndIf
	Next
	Return TreasuryObservationCreate($TREASURY_STATE_ENTRY_MISSING)
EndFunc   ;==>_TreasuryLiveDetectEntry

Func _TreasuryLiveIssueEntry($iX, $iY)
	If _TreasuryLiveStopRequested() Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#TreasuryEntry")
	If $bIssued Then RunEventLogMaintenanceTreasuryEntryIssued()
	Return $bIssued
EndFunc   ;==>_TreasuryLiveIssueEntry

Func _TreasuryLiveDetectCollect()
	Local $bWindowSeen = False
	Local $bFullSeen = False
	For $iAttempt = 1 To 8
		If _TreasuryLiveStopRequested() Then Return 0
		If _CheckPixel($aTreasuryWindow, True) Then
			$bWindowSeen = True
			Local $aFull = _PixelSearch(695, 195 + $g_iMidOffsetY, 700, 320 + $g_iMidOffsetY, _
					Hex(0x50BD10, 6), 20)
			If IsArray($aFull) Then
				$bFullSeen = True
				Local $aCollect = findButton("Collect", Default, 1, True)
				If IsArray($aCollect) And UBound($aCollect, 1) = 2 Then _
					Return TreasuryObservationCreate($TREASURY_STATE_COLLECT_READY, Int($aCollect[0]), Int($aCollect[1]))
			EndIf
		EndIf
		If $iAttempt < 8 Then
			If _Sleep(250, True, True, False) Then Return 0
			If _TreasuryLiveStopRequested() Then Return 0
		EndIf
	Next
	If Not $bWindowSeen Then Return 0
	If Not $bFullSeen Then Return TreasuryObservationCreate($TREASURY_STATE_NOT_FULL)
	Return TreasuryObservationCreate($TREASURY_STATE_COLLECT_MISSING)
EndFunc   ;==>_TreasuryLiveDetectCollect

Func _TreasuryLiveIssueCollect($iX, $iY)
	If _TreasuryLiveStopRequested() Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 130, "#TreasuryCollect")
	If $bIssued Then RunEventLogMaintenanceTreasuryCollectIssued()
	Return $bIssued
EndFunc   ;==>_TreasuryLiveIssueCollect

Func _TreasuryLiveDetectConfirm()
	For $iAttempt = 1 To 6
		If _TreasuryLiveStopRequested() Then Return 0
		; A generic Okay target is accepted only while the exact Treasury window remains underneath it.
		If _CheckPixel($aTreasuryWindow, True) Then
			Local $aOkay = findButton("Okay", Default, 1, True)
			If IsArray($aOkay) And UBound($aOkay, 1) = 2 Then _
				Return TreasuryObservationCreate($TREASURY_STATE_CONFIRM_READY, Int($aOkay[0]), Int($aOkay[1]))
		EndIf
		If $iAttempt < 6 Then
			If _Sleep(250, True, True, False) Then Return 0
			If _TreasuryLiveStopRequested() Then Return 0
		EndIf
	Next
	Return TreasuryObservationCreate($TREASURY_STATE_CONFIRM_MISSING)
EndFunc   ;==>_TreasuryLiveDetectConfirm

Func _TreasuryLiveIssueConfirm($iX, $iY)
	If _TreasuryLiveStopRequested() Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 130, "#TreasuryConfirm")
	If $bIssued Then RunEventLogMaintenanceTreasuryConfirmIssued()
	Return $bIssued
EndFunc   ;==>_TreasuryLiveIssueConfirm

Func _TreasuryLiveCleanup()
	If _TreasuryLiveStopRequested() Then Return TreasuryCleanupCreate(0, False, False)
	; Test the Treasury marker before the permissive main-page predicate: the underlying village remains
	; visible beneath some modals and must not be misreported as a clean Home state.
	If Not _CheckPixel($aTreasuryWindow, True) Then
		Return TreasuryCleanupCreate(0, False, IsMainPage(1))
	EndIf

	; Close only a still-recognized Treasury window, once. CloseWindow2 has no ClickAway fallback.
	If _TreasuryLiveStopRequested() Then Return TreasuryCleanupCreate(0, False, False)
	Local $bCloseIssued = CloseWindow2(1, 200)
	If $bCloseIssued Then RunEventLogMaintenanceTreasuryCloseIssued()
	If Not $bCloseIssued Or _TreasuryLiveStopRequested() Then Return TreasuryCleanupCreate(1, $bCloseIssued, False)

	For $iAttempt = 1 To 8
		If _TreasuryLiveStopRequested() Then Return TreasuryCleanupCreate(1, True, False)
		If IsMainPage(1) Then Return TreasuryCleanupCreate(1, True, True)
		If $iAttempt < 8 Then
			If _Sleep(250, True, True, False) Then Return TreasuryCleanupCreate(1, True, False)
		EndIf
	Next
	Return TreasuryCleanupCreate(1, True, False)
EndFunc   ;==>_TreasuryLiveCleanup

Func _HomeMaintenanceRouteFail($sReason, $bIrreversibleOutcome = False)
	If (RunControlStopRequested() Or Not $g_bRunState) And Not $bIrreversibleOutcome Then Return False
	Local $sFailure = "Home maintenance failed: " & $sReason
	SetLog("Run Planner: " & $sFailure, $COLOR_ERROR)
	RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sFailure)
	RunExecutionCancelPrepared($sFailure)
	btnStop()
	RunControlReportRunFailure($sFailure)
	Return False
EndFunc   ;==>_HomeMaintenanceRouteFail

Func HomeMaintenanceRouteExecute()
	If Not HomeMaintenanceRouteActive() Then Return False
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	If Not HomeMaintenanceRouteAccountMatches($g_oRunExecutionIntent, $g_sProfileCurrentName) Then _
		Return _HomeMaintenanceRouteFail("the active profile no longer matches the account bound at Start")

	Local $oPlan = $g_oRunExecutionIntent.Item("plan")
	Local $bCollectResources = $oPlan.Item("events_collect_resources")
	Local $bCollectDailyReward = $oPlan.Item("events_collect_daily_reward")
	Local $bCollectLootCart = $oPlan.Item("events_collect_loot_cart")
	Local $bCollectTreasury = $oPlan.Item("events_collect_treasury")
	SetLog("Run Planner: starting one bounded Home Village maintenance pass", $COLOR_ACTION)
	If $bCollectResources Then RunEventLogMaintenanceCollectorsStarted()
	If $bCollectLootCart Then RunEventLogMaintenanceLootCartStarted()
	If $bCollectTreasury Then RunEventLogMaintenanceTreasuryStarted()
	If Not _RunExecutionRequireOwnVillageReady() Then Return False

	If $bCollectDailyReward Then
		Switch $g_sRunExecutionDailyRewardState
			Case "click-issued"
				; The issued-input receipt was written at the Click acceptance boundary. Do not duplicate it.
			Case "not-seen", "none-actionable"
				RunEventLogMaintenanceDailyRewardUnavailable($g_sRunExecutionDailyRewardState)
			Case "cancelled"
				Return False
			Case Else
				RunEventLogMaintenanceDailyRewardUnconfirmed($g_bRunExecutionDailyRewardClickIssued, _
						$g_sRunExecutionDailyRewardDetail)
				Return _HomeMaintenanceRouteFail("startup Daily Reward outcome was unconfirmed: " & $g_sRunExecutionDailyRewardState)
		EndSwitch
	EndIf

	Local $sLootCartState = "disabled"
	Local $bLootCartInputIssued = False
	If $bCollectLootCart Then
		Local $oLootCart = LootCartRouteRunAdapter("_LootCartLiveDetectCart", "_LootCartLiveIssueCart", _
				"_LootCartLiveDetectCollect", "_LootCartLiveIssueCollect", "_LootCartLiveStopRequested", _
				"_LootCartLiveProveHome")
		If Not IsObj($oLootCart) Then Return _HomeMaintenanceRouteFail("the Loot Cart adapter returned no bounded outcome")
		$sLootCartState = String($oLootCart.Item("state"))
		$bLootCartInputIssued = $oLootCart.Item("cart_issued") Or $oLootCart.Item("collect_issued")
		If $sLootCartState = $LOOT_CART_OUTCOME_CANCELLED Then Return False
		If Not $oLootCart.Item("home_proven") Then
			RunEventLogMaintenanceLootCartUnconfirmed($oLootCart.Item("cart_issued"), _
					$oLootCart.Item("collect_issued"), $oLootCart.Item("detail") & "; Home Village was not re-proven")
			Return _HomeMaintenanceRouteFail("Home Village could not be passively re-proven after the Loot Cart", _
					$oLootCart.Item("collect_issued"))
		EndIf
		RunEventLogMaintenanceLootCartHomeVerified($sLootCartState)
		Switch $sLootCartState
			Case $LOOT_CART_OUTCOME_COLLECT_ISSUED
				; The accepted Collect receipt was emitted by the input callback. Do not duplicate it.
			Case $LOOT_CART_OUTCOME_UNAVAILABLE
				RunEventLogMaintenanceLootCartUnavailable($oLootCart.Item("cart_state"))
			Case $LOOT_CART_OUTCOME_UNCONFIRMED
				RunEventLogMaintenanceLootCartUnconfirmed($oLootCart.Item("cart_issued"), _
						$oLootCart.Item("collect_issued"), $oLootCart.Item("detail"))
				Return _HomeMaintenanceRouteFail($oLootCart.Item("detail") & "; Loot Cart inputs will not be retried", _
						$oLootCart.Item("collect_issued"))
			Case Else
				Return _HomeMaintenanceRouteFail("the Loot Cart adapter returned an unknown terminal state", _
						$oLootCart.Item("collect_issued"))
		EndSwitch
	EndIf

	Local $sTreasuryState = "disabled"
	Local $bTreasuryInputIssued = False
	If $bCollectTreasury Then
		Local $oTreasury = TreasuryRouteRunAdapter("_TreasuryLiveDetectCastle", "_TreasuryLiveIssueCastle", _
				"_TreasuryLiveDetectEntry", "_TreasuryLiveIssueEntry", "_TreasuryLiveDetectCollect", _
				"_TreasuryLiveIssueCollect", "_TreasuryLiveDetectConfirm", "_TreasuryLiveIssueConfirm", _
				"_TreasuryLiveStopRequested", "_TreasuryLiveCleanup")
		If Not IsObj($oTreasury) Then Return _HomeMaintenanceRouteFail("the Treasury adapter returned no bounded outcome")
		$sTreasuryState = String($oTreasury.Item("state"))
		$bTreasuryInputIssued = $oTreasury.Item("castle_issued") Or $oTreasury.Item("entry_issued") Or _
				$oTreasury.Item("collect_issued") Or $oTreasury.Item("confirm_issued") Or $oTreasury.Item("close_issued")
		If $sTreasuryState = $TREASURY_OUTCOME_CANCELLED Then Return False
		If Not $oTreasury.Item("home_proven") Then
			RunEventLogMaintenanceTreasuryUnconfirmed($oTreasury.Item("collect_issued"), _
					$oTreasury.Item("confirm_issued"), $oTreasury.Item("detail") & "; Home Village was not re-proven")
			Return _HomeMaintenanceRouteFail("Home Village could not be re-proven after Treasury", _
					$oTreasury.Item("confirm_issued"))
		EndIf
		RunEventLogMaintenanceTreasuryHomeVerified($sTreasuryState)
		Switch $sTreasuryState
			Case $TREASURY_OUTCOME_CONFIRM_ISSUED
				; The contextual confirmation receipt was emitted at the accepted input boundary.
			Case $TREASURY_OUTCOME_UNAVAILABLE
				RunEventLogMaintenanceTreasuryUnavailable($oTreasury.Item("detail"))
			Case $TREASURY_OUTCOME_UNCONFIRMED
				RunEventLogMaintenanceTreasuryUnconfirmed($oTreasury.Item("collect_issued"), _
						$oTreasury.Item("confirm_issued"), $oTreasury.Item("detail"))
				Return _HomeMaintenanceRouteFail($oTreasury.Item("detail") & "; Treasury inputs will not be retried", _
						$oTreasury.Item("confirm_issued"))
			Case Else
				Return _HomeMaintenanceRouteFail("the Treasury adapter returned an unknown terminal state", _
						$oTreasury.Item("confirm_issued"))
		EndSwitch
	EndIf

	Local $iCollectorClicks = 0
	If $bCollectResources Then
		; Home-maintenance collector mode suppresses Loot Cart and Treasury even if the legacy profile enables them.
		; Collect returns True only after it re-proves the own-village main screen following every click.
		Local $bCollectorScreenReady = Collect(False, True)
		$iCollectorClicks = @extended
		If Not $bCollectorScreenReady Then
			If RunControlStopRequested() Or Not $g_bRunState Then Return False
			Return _HomeMaintenanceRouteFail("collector recognition did not return to a proven Home Village screen")
		EndIf
	EndIf
	If RunControlStopRequested() Or Not $g_bRunState Then Return False

	RunEventLogMaintenanceHomeVerified($iCollectorClicks, $bCollectDailyReward ? $g_sRunExecutionDailyRewardState : "disabled", _
			$sLootCartState, $sTreasuryState)
	If $bCollectResources Then
		If $iCollectorClicks > 0 Then
			RunEventLogMaintenanceCollectorsCompleted($iCollectorClicks)
		Else
			RunEventLogMaintenanceCollectorsNoneActionable()
		EndIf
	EndIf
	Local $bAnyInput = $iCollectorClicks > 0 Or $g_bRunExecutionDailyRewardClickIssued Or $bLootCartInputIssued Or $bTreasuryInputIssued
	Local $sReason = $bAnyInput ? "home-maintenance-complete" : "home-maintenance-none-actionable"
	If Not RunSessionRequestStop($g_oRunExecutionSession, $sReason) Then _
		Return _HomeMaintenanceRouteFail("the run session refused its one-pass completion")
	RunEventLogRunStopping("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sReason)
	$g_sRunExecutionMessage = "Completed Home maintenance; collector_clicks=" & $iCollectorClicks & _
			"; daily_reward=" & ($bCollectDailyReward ? $g_sRunExecutionDailyRewardState : "disabled") & _
			"; loot_cart=" & $sLootCartState & "; treasury=" & $sTreasuryState
	btnStop()
	Return True
EndFunc   ;==>HomeMaintenanceRouteExecute

Func _ClanRequestRouteFail($sReason, $bIrreversibleOutcome = False)
	If (RunControlStopRequested() Or Not $g_bRunState) And Not $bIrreversibleOutcome Then Return False
	Local $sFailure = "Clan request failed: " & $sReason
	SetLog("Run Planner: " & $sFailure, $COLOR_ERROR)
	RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sFailure)
	RunExecutionCancelPrepared($sFailure)
	btnStop()
	RunControlReportRunFailure($sFailure)
	Return False
EndFunc   ;==>_ClanRequestRouteFail

Func _ClanRequestLiveStopRequested()
	Return RunControlStopRequested() Or Not $g_bRunState
EndFunc   ;==>_ClanRequestLiveStopRequested

Func _ClanRequestLiveOpenArmyOverview()
	If _ClanRequestLiveStopRequested() Then Return False
	If Not checkMainScreen(False) Then Return False
	; The third argument is deliberately False: Hero-order inspection enters Hero Hall/zoom/building paths.
	If Not OpenArmyOverview(True, "ClanRequestRoute", False) Then Return False
	If _Sleep(400, True, True, False) Then Return False
	If _ClanRequestLiveStopRequested() Then Return False
	Return True
EndFunc   ;==>_ClanRequestLiveOpenArmyOverview

Func _ClanRequestLiveParseObservation(ByRef $aMatches, $bSendButton = False)
	If Not IsArray($aMatches) Or UBound($aMatches, 1) <> 1 Then Return 0
	Local $aResult = $aMatches[0]
	If Not IsArray($aResult) Or UBound($aResult) < 2 Then Return 0
	Local $aPoint = StringSplit(String($aResult[1]), ",", $STR_NOCOUNT)
	If Not IsArray($aPoint) Or UBound($aPoint) <> 2 Then Return 0
	If $bSendButton Then Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_SEND_READY, Int($aPoint[0]), Int($aPoint[1]))

	Local $sObject = StringLower(String($aResult[0]))
	If StringInStr($sObject, "available", 0) > 0 Then _
		Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_AVAILABLE, Int($aPoint[0]), Int($aPoint[1]))
	If StringInStr($sObject, "alreadymade", 0) > 0 Or StringInStr($sObject, "already", 0) > 0 Then _
		Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_ALREADY_MADE, Int($aPoint[0]), Int($aPoint[1]))
	If StringInStr($sObject, "fullorunavail", 0) > 0 Or StringInStr($sObject, "full", 0) > 0 Then _
		Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_FULL_OR_UNAVAILABLE, Int($aPoint[0]), Int($aPoint[1]))
	Return 0
EndFunc   ;==>_ClanRequestLiveParseObservation

Func _ClanRequestLiveDetectState($sPhase)
	Local $sSearchDiamond = GetDiamondFromRect2(734, 455 + $g_iMidOffsetY, 773, 485 + $g_iMidOffsetY)
	Local $iAttempts = (StringLower(String($sPhase)) = "after") ? 8 : 1
	For $iAttempt = 1 To $iAttempts
		; findMultiple receives True so every decision is made from a new framebuffer, never a cached request state.
		Local $aRequestButton = findMultiple($g_sImgRequestCCButton, $sSearchDiamond, $sSearchDiamond, 0, 1000, 1, _
				"objectname,objectpoints", True)
		Local $oObservation = _ClanRequestLiveParseObservation($aRequestButton)
		If IsObj($oObservation) Then Return $oObservation
		If $iAttempt < $iAttempts Then
			If _ClanRequestLiveStopRequested() Then ExitLoop
			If _Sleep(250, True, True, False) Then ExitLoop
			If _ClanRequestLiveStopRequested() Then ExitLoop
		EndIf
	Next
	Return 0
EndFunc   ;==>_ClanRequestLiveDetectState

Func _ClanRequestLiveOpenDialog($iRequestX, $iRequestY)
	If _ClanRequestLiveStopRequested() Then Return 0
	Click(Int($iRequestX), Int($iRequestY), 1, 120, "#ClanRequestOpen")
	Local $sSendArea = GetDiamondFromRect("220,150,650,650")
	For $iAttempt = 1 To 6
		If _ClanRequestLiveStopRequested() Then Return 0
		Local $aSendButton = findMultiple($g_sImgSendRequestButton, $sSendArea, $sSendArea, 0, 1000, 1, _
				"objectname,objectpoints", True)
		Local $oSend = _ClanRequestLiveParseObservation($aSendButton, True)
		If IsObj($oSend) Then Return $oSend
		If $iAttempt < 6 Then
			If _Sleep(250, True, True, False) Then Return 0
			If _ClanRequestLiveStopRequested() Then Return 0
		EndIf
	Next
	Return 0
EndFunc   ;==>_ClanRequestLiveOpenDialog

Func _ClanRequestLiveIssueSend($iSendX, $iSendY)
	; ClanRequestRouteRunAdapter performs the immediate Stop poll and latches Send before this callback.
	; Keep this callback to one command: no request text, no OCR, no retry, and no fallback coordinates.
	Return Click(Int($iSendX), Int($iSendY), 1, 120, "#ClanRequestSend")
EndFunc   ;==>_ClanRequestLiveIssueSend

Func _ClanRequestLiveCloseAndProveHome()
	; The Send dialog may still be open on an error; successful Send leaves Army Overview open.
	; At most two close commands are permitted, with a fresh Home screen proof after each boundary.
	If _ClanRequestLiveStopRequested() Then Return False
	If checkMainScreen(False) Then Return _RunExecutionRequireOwnVillageReady()
	For $iClose = 1 To 2
		If _ClanRequestLiveStopRequested() Then Return False
		CloseWindow2()
		; Cleanup remains bounded even if Stop arrived after Send; disabling the run-state early return
		; lets this one close settle without re-entering any planner or village work.
		_Sleep(300, True, False, False)
		If _ClanRequestLiveStopRequested() Then Return False
		If checkMainScreen(False) Then Return _RunExecutionRequireOwnVillageReady()
	Next
	Return False
EndFunc   ;==>_ClanRequestLiveCloseAndProveHome

Func _ClanRequestRouteRequestStop($sReason, $sMessage)
	If Not RunSessionRequestStop($g_oRunExecutionSession, $sReason) Then _
		Return _ClanRequestRouteFail("the run session refused its request-only completion")
	RunEventLogRunStopping("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sReason)
	$g_sRunExecutionMessage = $sMessage
	btnStop()
	Return True
EndFunc   ;==>_ClanRequestRouteRequestStop

Func ClanRequestRouteExecute()
	If Not ClanRequestRouteActive() Then Return False
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	If Not ClanRequestRouteAccountMatches($g_oRunExecutionIntent, $g_sProfileCurrentName) Then _
		Return _ClanRequestRouteFail("the active profile no longer matches the account bound at Start")

	SetLog("Run Planner: starting one request-only Home Village pass", $COLOR_ACTION)
	RunEventLogClanRequestStarted()
	If Not _RunExecutionRequireOwnVillageReady() Then Return False

	Local $oOutcome = ClanRequestRouteRunAdapter("_ClanRequestLiveOpenArmyOverview", "_ClanRequestLiveDetectState", _
			"_ClanRequestLiveOpenDialog", "_ClanRequestLiveIssueSend", "_ClanRequestLiveStopRequested", _
			"_ClanRequestLiveCloseAndProveHome")
	If Not IsObj($oOutcome) Then Return _ClanRequestRouteFail("the request adapter returned no bounded outcome")
	Local $sOutcome = String($oOutcome.Item("state"))
	If $sOutcome = $CLAN_REQUEST_OUTCOME_CANCELLED Then Return False
	If Not $oOutcome.Item("home_proven") Then
		RunEventLogClanRequestUnconfirmed($oOutcome.Item("send_issued"), _
				$oOutcome.Item("detail") & "; Home Village was not re-proven")
		Return _ClanRequestRouteFail("Home Village could not be re-proven after the request dialog", $oOutcome.Item("send_issued"))
	EndIf
	RunEventLogClanRequestHomeVerified($sOutcome)

	Switch $sOutcome
		Case $CLAN_REQUEST_OUTCOME_COMMITTED
			RunEventLogClanRequestCommitted()
			Return _ClanRequestRouteRequestStop("clan-request-committed", _
					"Completed request-only Home maintenance; one Send verified Available -> AlreadyMade")
		Case $CLAN_REQUEST_OUTCOME_UNAVAILABLE
			RunEventLogClanRequestUnavailable($oOutcome.Item("before_state"))
			Return _ClanRequestRouteRequestStop("clan-request-unavailable", _
					"Completed request-only Home maintenance; no request was available and no Send was issued")
		Case $CLAN_REQUEST_OUTCOME_UNCONFIRMED
			RunEventLogClanRequestUnconfirmed($oOutcome.Item("send_issued"), $oOutcome.Item("detail"))
			Return _ClanRequestRouteFail($oOutcome.Item("detail") & "; Send will not be retried", $oOutcome.Item("send_issued"))
	EndSwitch
	Return _ClanRequestRouteFail("the request adapter returned an unknown terminal state")
EndFunc   ;==>ClanRequestRouteExecute

Func RunExecutionStandardDeploymentProofRequired()
	If Not $g_bRunExecutionActive Or Not IsObj($g_oRunExecutionIntent) Then Return False
	Local $oPlan = $g_oRunExecutionIntent.Item("plan")
	Local $sStrategy = StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL))
	Return $sStrategy = "legacy.standard" Or $sStrategy = "smart.local"
EndFunc   ;==>RunExecutionStandardDeploymentProofRequired

Func RunExecutionResetDeploymentProof($iDeployableBefore = 0)
	$g_bRunExecutionDeploymentVerified = False
	$g_iRunExecutionDeployableBefore = Int($iDeployableBefore)
	$g_iRunExecutionDeployableAfter = -1
EndFunc   ;==>RunExecutionResetDeploymentProof

Func RunExecutionRecordDeploymentProof($iDeployableAfter)
	$g_iRunExecutionDeployableAfter = Int($iDeployableAfter)
	$g_bRunExecutionDeploymentVerified = $g_iRunExecutionDeployableBefore > 0 And $g_iRunExecutionDeployableAfter = 0
	If $g_bRunExecutionDeploymentVerified Then
		SetLog("Run Planner deployment verified: " & $g_iRunExecutionDeployableBefore & " deployable troops reduced to zero", $COLOR_SUCCESS)
		RunEventLogCombatDeploymentVerified($g_iRunExecutionDeployableBefore, $g_iRunExecutionDeployableAfter)
	Else
		SetLog("Run Planner deployment verification failed: " & $g_iRunExecutionDeployableBefore & _
				" deployable troops before, " & $g_iRunExecutionDeployableAfter & " still visible after the drop routine", $COLOR_ERROR)
	EndIf
	Return $g_bRunExecutionDeploymentVerified
EndFunc   ;==>RunExecutionRecordDeploymentProof

Func RunExecutionDeploymentVerified()
	If Not RunExecutionStandardDeploymentProofRequired() Then Return True
	Return $g_bRunExecutionDeploymentVerified
EndFunc   ;==>RunExecutionDeploymentVerified

; The inherited working attack path uses the emulator-specific AndroidZoomOut primitive before it
; trusts deployment geometry. Do not run the legacy stone/tree scenery search before the first
; pinch: current scenery has no matching anchors and that scan can consume the entire 30-second
; deployment countdown. Apply a small, bounded pinch sequence immediately, then prove the current
; attack page and its deployable red line from a fresh framebuffer before any resource read or drop.
Func RunExecutionPrepareEnemyDeploymentView()
	If Not $g_bRunExecutionActive Then Return True
	If Not $g_bRunState Or Not IsAttackPage() Then
		SetLog("Run Planner cannot zoom: the live attack page is not visible", $COLOR_ERROR)
		Return False
	EndIf

	SetLog("Run Planner: applying the original enemy zoom-out gesture before deployment", $COLOR_ACTION)
	For $iZoom = 0 To 2
		; Use the inherited Normal2 pinch transport, but keep its vertical axis above the current
		; client's bottom battle controls. The randomized zoom helper selects Normal0..6; Normal0/5/6
		; cross the Boost Heroes row and can be interpreted as a tap when the gesture collapses.
		; Mode 2 deliberately disables minitouch and retains AndroidAdbScript's normal fallback.
		AndroidZoomOut($iZoom, Default, ($g_iAndroidZoomoutMode <> 2), Default, "Normal2")
		Local $iZoomError = @error
		If $iZoomError Then
			SetLog("Run Planner could not send enemy zoom-out gesture " & ($iZoom + 1) & "/3 (error " & $iZoomError & _
					"); refusing to deploy troops", $COLOR_ERROR)
			Return False
		EndIf
		SetDebugLog("Run Planner: enemy zoom-out gesture " & ($iZoom + 1) & "/3 accepted")
		If _Sleep(250) Then Return False
	Next

	; IsAttackPage reads $g_hBitmap while red-line detection reads $g_hHBitmap2.
	; Refresh both from the same framebuffer so the post-zoom proof cannot compare
	; a fresh image-search frame against a stale pixel frame.
	ForceCaptureRegion()
	_CaptureRegions()
	If Not IsAttackPage(False) Then
		SetLog("Run Planner lost the attack page after zoom-out; refusing to deploy troops", $COLOR_ERROR)
		Return False
	EndIf

	; Red-line detection is the same current-frame geometry consumed by SmartAttackStrategy and the
	; inherited DropTroop routines. The inherited working path samples several frames because the
	; perimeter can be absent for one render immediately after a pinch. Keep that resilience, but
	; stop at the first proven frame and cap the work at three attempts. Use the DLL's full-diamond
	; token here: $CocDiamondECD is rebuilt later by the original VillageSearch measurement path and
	; can still contain own-village calibration when current-army mode intentionally skips that scan.
	Local $sRedline = ""
	Local $iRedlinePoints = 0
	For $iRedlineAttempt = 1 To 3
		If $iRedlineAttempt > 1 Then
			If _Sleep(300) Then Return False
			ForceCaptureRegion()
			_CaptureRegions()
			If Not IsAttackPage(False) Then
				SetLog("Run Planner lost the attack page while refreshing red-line geometry; refusing to deploy troops", $COLOR_ERROR)
				Return False
			EndIf
		EndIf

		$g_sImglocRedline = ""
		$sRedline = SearchRedLines("ECD")
		$iRedlinePoints = 0
		If IsString($sRedline) And $sRedline <> "" And $sRedline <> "ECD" Then _
			$iRedlinePoints = UBound(StringSplit($sRedline, "|", $STR_NOCOUNT))
		SetDebugLog("Run Planner: red-line proof attempt " & $iRedlineAttempt & "/3 returned " & $iRedlinePoints & " points")
		If $iRedlinePoints >= 50 Then ExitLoop
	Next
	If $iRedlinePoints < 50 Then
		SetLog("Run Planner could not prove deployable red-line geometry after zoom-out; refusing to click the base", $COLOR_ERROR)
		Return False
	EndIf

	SetLog("Run Planner: enemy zoom-out and " & $iRedlinePoints & " deployable red-line points verified", $COLOR_SUCCESS)
	RunEventLogCombatZoomVerified($iRedlinePoints)
	Return True
EndFunc   ;==>RunExecutionPrepareEnemyDeploymentView

Func _RunExecutionBattleTotal()
	Return Int($g_aiAttackedVillageCount[$DB]) + Int($g_aiAttackedVillageCount[$LB])
EndFunc   ;==>_RunExecutionBattleTotal

Func _RunExecutionLootTotal(ByRef $aValues)
	Return Int($aValues[$DB]) + Int($aValues[$LB])
EndFunc   ;==>_RunExecutionLootTotal

Func _RunExecutionHeroMask(ByRef $oLoadout)
	Local $iMask = $eHeroNone
	If HeroLoadoutContains($oLoadout, "barbarian-king") Then $iMask = BitOR($iMask, $eHeroKing)
	If HeroLoadoutContains($oLoadout, "archer-queen") Then $iMask = BitOR($iMask, $eHeroQueen)
	If HeroLoadoutContains($oLoadout, "minion-prince") Then $iMask = BitOR($iMask, $eHeroPrince)
	If HeroLoadoutContains($oLoadout, "grand-warden") Then $iMask = BitOR($iMask, $eHeroWarden)
	If HeroLoadoutContains($oLoadout, "royal-champion") Then $iMask = BitOR($iMask, $eHeroChampion)
	Return $iMask
EndFunc   ;==>_RunExecutionHeroMask

Func RunExecutionSmartAttackEnabled()
	If Not ($g_bRunExecutionPrepared Or $g_bRunExecutionActive) Or Not IsObj($g_oRunExecutionIntent) Then Return False
	Local $oPlan = $g_oRunExecutionIntent.Item("plan")
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = "smart.local"
EndFunc   ;==>RunExecutionSmartAttackEnabled

Func RunExecutionConfigureSmartAttackForMode($iMode)
	If Not RunExecutionSmartAttackEnabled() Then Return False
	If $iMode < 0 Or $iMode >= $g_iModeCount Then Return False
	$g_abAttackStdSmartAttack[$iMode] = True
	$g_aiAttackStdDropSides[$iMode] = RunExecutionSmartDropSides($g_iTownHallLevel, $iMode = $LB)
	SetLog("Smart Attack local policy: TH" & $g_iTownHallLevel & _
			", one concentrated side selected from the current red line", $COLOR_INFO)
	Return True
EndFunc   ;==>RunExecutionConfigureSmartAttackForMode

Func _RunExecutionEmulatorName($sId)
	Switch StringLower(StringStripWS(String($sId), $STR_STRIPALL))
		Case "bluestacks5"
			Return "BlueStacks5"
		Case "memu"
			Return "MEmu"
		Case "nox"
			Return "Nox"
		Case "ldplayer9"
			Return "LDPlayer9"
		Case "mumu"
			Return "Mumu"
	EndSwitch
	Return ""
EndFunc   ;==>_RunExecutionEmulatorName

Func _RunExecutionCaptureProfileSnapshot()
	If $g_bRunExecutionProfileSnapshotCaptured Then Return False

	$g_iRunExecutionSnapshotAndroidConfig = $g_iAndroidConfig
	$g_sRunExecutionSnapshotAndroidEmulator = $g_sAndroidEmulator
	$g_sRunExecutionSnapshotAndroidInstance = $g_sAndroidInstance
	For $iMode = 0 To $g_iModeCount - 1
		$g_asRunExecutionSnapshotAttackScript[$iMode] = $g_sAttackScrScriptName[$iMode]
		$g_aiRunExecutionSnapshotAttackAlgorithm[$iMode] = $g_aiAttackAlgorithm[$iMode]
		$g_aiRunExecutionSnapshotAttackStdDropSides[$iMode] = $g_aiAttackStdDropSides[$iMode]
		$g_abRunExecutionSnapshotAttackStdSmartAttack[$iMode] = $g_abAttackStdSmartAttack[$iMode]
		$g_aiRunExecutionSnapshotAttackUseHeroes[$iMode] = $g_aiAttackUseHeroes[$iMode]
		$g_abRunExecutionSnapshotAttackDropCC[$iMode] = $g_abAttackDropCC[$iMode]
		$g_abRunExecutionSnapshotAttackUseRageSpell[$iMode] = $g_abAttackUseRageSpell[$iMode]
		$g_abRunExecutionSnapshotAttackUseFreezeSpell[$iMode] = $g_abAttackUseFreezeSpell[$iMode]
		$g_aiRunExecutionSnapshotSearchHeroWaitEnable[$iMode] = $g_aiSearchHeroWaitEnable[$iMode]
		$g_abRunExecutionSnapshotSearchSpellsWaitEnable[$iMode] = $g_abSearchSpellsWaitEnable[$iMode]
		$g_abRunExecutionSnapshotSearchSiegeWaitEnable[$iMode] = $g_abSearchSiegeWaitEnable[$iMode]
		$g_aiRunExecutionSnapshotFilterMeetGE[$iMode] = $g_aiFilterMeetGE[$iMode]
		$g_aiRunExecutionSnapshotFilterMinGold[$iMode] = $g_aiFilterMinGold[$iMode]
		$g_aiRunExecutionSnapshotFilterMinElixir[$iMode] = $g_aiFilterMinElixir[$iMode]
		$g_abRunExecutionSnapshotFilterMeetDEEnable[$iMode] = $g_abFilterMeetDEEnable[$iMode]
		$g_aiRunExecutionSnapshotFilterMeetDEMin[$iMode] = $g_aiFilterMeetDEMin[$iMode]
	Next
	For $iMode = 0 To $g_iModeCount
		$g_abRunExecutionSnapshotAttackTypeEnable[$iMode] = $g_abAttackTypeEnable[$iMode]
		If $iMode = $g_iModeCount Then
			$g_aiRunExecutionSnapshotAttackStdDropSides[$iMode] = $g_aiAttackStdDropSides[$iMode]
			$g_abRunExecutionSnapshotAttackStdSmartAttack[$iMode] = $g_abAttackStdSmartAttack[$iMode]
		EndIf
	Next
	For $iSpell = 0 To $eSpellCount - 1
		$g_aiRunExecutionSnapshotArmyCompSpells[$iSpell] = $g_aiArmyCompSpells[$iSpell]
	Next
	For $iSiege = 0 To $eSiegeMachineCount - 1
		$g_aiRunExecutionSnapshotArmyCompSiegeMachines[$iSiege] = $g_aiArmyCompSiegeMachines[$iSiege]
	Next

	$g_bRunExecutionSnapshotChkDonate = $g_bChkDonate
	$g_bRunExecutionSnapshotDonateLikeCrazy = $g_bDonateLikeCrazy
	$g_bRunExecutionSnapshotRequestTroopsEnable = $g_bRequestTroopsEnable
	$g_bRunExecutionSnapshotChkClanGamesEnabled = $g_bChkClanGamesEnabled
	$g_bRunExecutionSnapshotChkCollect = $g_bChkCollect
	$g_bRunExecutionSnapshotChkCollectCartFirst = $g_bChkCollectCartFirst
	$g_bRunExecutionSnapshotChkTreasuryCollect = $g_bChkTreasuryCollect
	$g_bRunExecutionSnapshotChkCollectAchievements = $g_bChkCollectAchievements
	$g_bRunExecutionSnapshotChkCollectFreeMagicItems = $g_bChkCollectFreeMagicItems
	$g_bRunExecutionSnapshotChkCollectRewards = $g_bChkCollectRewards
	$g_bRunExecutionSnapshotChkSellRewards = $g_bChkSellRewards
	$g_bRunExecutionSnapshotAutoLabUpgradeEnable = $g_bAutoLabUpgradeEnable
	$g_bRunExecutionSnapshotAutoUpgradeWallsEnable = $g_bAutoUpgradeWallsEnable
	$g_bRunExecutionSnapshotAutoUpgradeEnabled = $g_bAutoUpgradeEnabled
	$g_bRunExecutionSnapshotChkSwitchAcc = $g_bChkSwitchAcc
	$g_bRunExecutionSnapshotPlannedDropCCHoursEnable = $g_bPlannedDropCCHoursEnable
	$g_bRunExecutionSnapshotUseCCBalanced = $g_bUseCCBalanced
	$g_bRunExecutionEmulatorChanged = False
	$g_bRunExecutionProfileSnapshotCaptured = True
	Return RunProfileOverrideBegin($g_bRunExecutionSnapshotChkClanGamesEnabled, $g_bRunExecutionSnapshotAutoLabUpgradeEnable, _
			$g_bRunExecutionSnapshotDonateLikeCrazy)
EndFunc   ;==>_RunExecutionCaptureProfileSnapshot

Func RunExecutionPrepareStart(ByRef $sError)
	$sError = ""
	_RunExecutionRestoreProfile()
	RunExecutionResetDeploymentProof()
	$g_bRunExecutionPrepared = False
	$g_bRunExecutionActive = False
	$g_oRunExecutionIntent = 0
	$g_oRunExecutionSession = 0
	$g_bRunExecutionManageTraining = True
	$g_sRunExecutionDailyRewardState = "not-seen"
	$g_sRunExecutionDailyRewardDetail = ""
	$g_iRunExecutionDailyRewardAttempts = 0
	$g_bRunExecutionDailyRewardClickIssued = False
	$g_sRunExecutionMessage = "Legacy profile mode"

	Local $oIntent = 0
	Local $sPlanPath = RunPlanFileDefaultPath()
	If FileExists($sPlanPath) Then
		$oIntent = RunPlanFileLoadIntent($sPlanPath, $sError)
		If Not IsObj($oIntent) Then Return SetError(1, 0, False)
	ElseIf IsObj($g_oRunPlannerIntent) Then
		$oIntent = $g_oRunPlannerIntent
	Else
		Return True
	EndIf
	If Not RunExecutionBindCurrentProfileForHomeRoute($oIntent, $sError) Then
		RunEventLogPlanBlocked($oIntent.Item("surface_id"), $sError)
		Return SetError(1, 1, False)
	EndIf

	Local $sGateReason = ""
	If Not RunIntentCanStart($oIntent, $sGateReason) Then
		$sError = $sGateReason
		RunEventLogPlanBlocked($oIntent.Item("surface_id"), $sError)
		Return SetError(2, 0, False)
	EndIf
	If Not RunExecutionContractValidate($oIntent, $sError) Then
		RunEventLogPlanBlocked($oIntent.Item("surface_id"), $sError)
		Return SetError(3, 0, False)
	EndIf

	Local $sSessionId = @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & "-" & @AutoItPID
	Local $oSession = RunIntentOpenSession($oIntent, $sSessionId, $sError)
	If Not IsObj($oSession) Then Return SetError(4, 0, False)

	$g_oRunPlannerIntent = $oIntent
	$g_oRunExecutionIntent = $oIntent
	$g_oRunExecutionSession = $oSession
	RunEventLogBindSession($sSessionId)
	$g_bRunExecutionPrepared = True
	$g_sRunExecutionMessage = "Prepared " & $oIntent.Item("surface_label")
	RunEventLogPreflightStarted($oIntent.Item("surface_id"), RunIntentVerificationState($oIntent), RunIntentDescribe($oIntent))
	Return True
EndFunc   ;==>RunExecutionPrepareStart

Func _RunExecutionApplyIntent(ByRef $sError)
	$sError = ""
	If Not $g_bRunExecutionPrepared Or Not IsObj($g_oRunExecutionIntent) Then Return True
	If Not RunExecutionContractValidate($g_oRunExecutionIntent, $sError) Then Return False

	Local $oPlan = $g_oRunExecutionIntent.Item("plan")
	$g_bRunExecutionManageTraining = RunIntentManagesTraining($g_oRunExecutionIntent)
	Local $sEmulator = StringLower(String($oPlan.Item("emulator")))
	If $sEmulator <> "auto" Then
		Local $sResolvedEmulator = _RunExecutionEmulatorName($sEmulator)
		If $sResolvedEmulator = "" Then
			$sError = "Run Planner emulator '" & $sEmulator & "' is not supported"
			Return False
		EndIf
		Local $sResolvedInstance = String($oPlan.Item("emulator_instance"))
		$g_bRunExecutionEmulatorChanged = ($g_sAndroidEmulator <> $sResolvedEmulator Or $g_sAndroidInstance <> $sResolvedInstance)
		If $g_bRunExecutionEmulatorChanged Then UpdateHWnD(0, False)
		If Not UpdateAndroidConfig($sResolvedInstance, $sResolvedEmulator) Then
			$sError = "Run Planner emulator '" & $sResolvedEmulator & "' is not installed or unavailable"
			Return False
		EndIf
	EndIf

	Local $sStrategy = StringLower(String($oPlan.Item("strategy")))
	; A reviewed plan is closed-world. Reward and collection actuators that are not represented in the
	; plan must never leak in from the active legacy profile. In particular, selling a full magic item
	; for gems is prohibited for every managed run. Explicit bounded routes may re-enable only the
	; actuator they own after this common safety reset.
	$g_bChkCollectCartFirst = False
	$g_bChkTreasuryCollect = False
	$g_bChkCollectAchievements = False
	$g_bChkCollectFreeMagicItems = False
	$g_bChkCollectRewards = False
	$g_bChkSellRewards = False
	If $sStrategy = $HOME_MAINTENANCE_COLLECTORS_STRATEGY Then
		; This exact route owns no attack, training, donation, upgrade, account-switch, or event actuator.
		; Apply only the collector flag and explicit safety disables; the captured profile snapshot
		; restores every overridden field through the normal Stop lifecycle.
		$g_bChkDonate = False
		$g_bDonateLikeCrazy = False
		$g_bRequestTroopsEnable = False
		$g_bChkSwitchAcc = False
		$g_bChkClanGamesEnabled = 0
		$g_bChkCollect = $oPlan.Item("events_collect_resources")
		$g_bAutoLabUpgradeEnable = False
		$g_bAutoUpgradeWallsEnable = False
		$g_bAutoUpgradeEnabled = False
		Return True
	EndIf
	If $sStrategy = $CLAN_REQUEST_ROUTE_STRATEGY Then
		; Request-only means exactly that: no donations, training, collectors, upgrades, events,
		; matchmaking, or account switching may be inherited from the active profile.
		$g_bChkDonate = False
		$g_bDonateLikeCrazy = False
		$g_bRequestTroopsEnable = True
		$g_bChkSwitchAcc = False
		$g_bChkClanGamesEnabled = 0
		$g_bChkCollect = False
		$g_bAutoLabUpgradeEnable = False
		$g_bAutoUpgradeWallsEnable = False
		$g_bAutoUpgradeEnabled = False
		Return True
	EndIf
	Local $iAlgorithm = ($sStrategy = "legacy.csv") ? 1 : 0
	Local $sAttackScript = StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $iAlgorithm = 1 And StringLower($sAttackScript) <> "profile-current" Then
		Local $sAttackScriptPath = $g_sCSVAttacksPath & "\" & $sAttackScript & ".csv"
		If Not FileExists($sAttackScriptPath) Then
			$sError = "Run Planner attack script is not installed: " & $sAttackScript
			Return False
		EndIf
		; This is deliberately an in-memory override. _RunExecutionRestoreProfile() reloads both values
		; after Stop or a refused Start, and no profile INI is written here.
		For $iMode = $DB To $LB
			$g_sAttackScrScriptName[$iMode] = $sAttackScript
		Next
	EndIf
	Local $oLoadout = $g_oRunExecutionIntent.Item("loadout")
	Local $iHeroMask = _RunExecutionHeroMask($oLoadout)
	Local $bWaitForFull = $oPlan.Item("army_wait_for_full")
	Local $iHeroWaitMask = RunExecutionHeroWaitMask($iHeroMask, $bWaitForFull, $g_bRunExecutionManageTraining)
	For $iMode = $DB To $LB
		$g_abAttackTypeEnable[$iMode] = True
		$g_aiAttackAlgorithm[$iMode] = $iAlgorithm
		$g_aiAttackUseHeroes[$iMode] = $iHeroMask
		; A named planner strategy must not silently inherit unrelated legacy profile tactics. Both
		; planned standard and smart attacks use the freshly proven current-client red line; the old
		; fixed edge coordinates predate the current zoom geometry and can click buildings instead of
		; deploying. Standard remains deterministic by retaining its one-side selector.
		If $sStrategy = "legacy.standard" Then
			$g_abAttackStdSmartAttack[$iMode] = True
			$g_aiAttackStdDropSides[$iMode] = 0
		ElseIf $sStrategy = "smart.local" Then
			$g_abAttackStdSmartAttack[$iMode] = True
			; Smart owns its tactical spell decision. Training management and battle use are separate:
			; an already-trained Rage or Freeze is retained for the bounded Smart caster even when this
			; one-run plan deliberately does not train or mutate the army.
			$g_abAttackUseRageSpell[$iMode] = True
			$g_abAttackUseFreezeSpell[$iMode] = True
		EndIf
		; A planned one-battle run owns every visible combat actor. If a siege/Clan Castle slot is
		; present, deploy it; an absent slot remains a harmless no-op. The captured profile value is
		; restored after the run.
		If $sStrategy = "legacy.standard" Or $sStrategy = "smart.local" Then $g_abAttackDropCC[$iMode] = True
		$g_aiSearchHeroWaitEnable[$iMode] = $iHeroWaitMask
		$g_abSearchSpellsWaitEnable[$iMode] = $bWaitForFull And $oPlan.Item("army_train_spells")
		$g_abSearchSiegeWaitEnable[$iMode] = $bWaitForFull And $oPlan.Item("army_train_sieges")
		$g_aiFilterMeetGE[$iMode] = 0
		$g_aiFilterMinGold[$iMode] = Int($oPlan.Item("search_min_gold"))
		$g_aiFilterMinElixir[$iMode] = Int($oPlan.Item("search_min_elixir"))
		$g_abFilterMeetDEEnable[$iMode] = Int($oPlan.Item("search_min_dark")) > 0
		$g_aiFilterMeetDEMin[$iMode] = Int($oPlan.Item("search_min_dark"))
	Next

	If Not $oPlan.Item("army_train_spells") Then
		For $iSpell = 0 To $eSpellCount - 1
			$g_aiArmyCompSpells[$iSpell] = 0
		Next
	EndIf
	If Not $oPlan.Item("army_train_sieges") Then
		For $iSiege = 0 To $eSiegeMachineCount - 1
			$g_aiArmyCompSiegeMachines[$iSiege] = 0
		Next
	EndIf

	Switch StringLower(String($oPlan.Item("donate_mode")))
		Case "off"
			$g_bChkDonate = False
			$g_bDonateLikeCrazy = False
		Case "matching"
			$g_bChkDonate = True
			$g_bDonateLikeCrazy = False
		Case "anything"
			$g_bChkDonate = True
			$g_bDonateLikeCrazy = True
	EndSwitch
	$g_bRequestTroopsEnable = $oPlan.Item("donate_request_when_short")
	If $sStrategy = "legacy.standard" Or $sStrategy = "smart.local" Then
		$g_bPlannedDropCCHoursEnable = False
		$g_bUseCCBalanced = False
	EndIf
	; A planner run targets the currently inspected village. Never inherit the legacy profile's
	; autonomous account rotation, which could switch to an uninspected army/account before FirstCheck.
	$g_bChkSwitchAcc = False
	$g_bChkClanGamesEnabled = $oPlan.Item("events_clan_games") ? 1 : 0
	$g_bChkCollect = $oPlan.Item("events_collect_resources")
	$g_bAutoLabUpgradeEnable = False
	$g_bAutoUpgradeWallsEnable = (StringLower(String($oPlan.Item("upgrade_policy"))) = "walls")
	$g_bAutoUpgradeEnabled = False
	Return True
EndFunc   ;==>_RunExecutionApplyIntent

Func RunExecutionApplyPrepared(ByRef $sError)
	$sError = ""
	If Not $g_bRunExecutionPrepared Then Return True
	If $g_bRunExecutionOverridesApplied Then Return True
	; Capture every planner-owned field before applying. The write guard begins here so a partial
	; emulator/config failure is also restored by RunExecutionCancelPrepared().
	If Not _RunExecutionCaptureProfileSnapshot() Then
		$sError = "Run Planner could not capture the active profile settings"
		Return SetError(1, 0, False)
	EndIf
	If Not _RunExecutionApplyIntent($sError) Then Return SetError(1, 0, False)

	$g_sRunExecutionMessage = "Starting " & $g_oRunExecutionIntent.Item("surface_label")
	Return True
EndFunc   ;==>RunExecutionApplyPrepared

Func RunExecutionBegin(ByRef $sError)
	$sError = ""
	If Not $g_bRunExecutionPrepared Then Return True
	If Not $g_bRunExecutionOverridesApplied Then
		$sError = "Prepared run settings were not applied"
		Return SetError(1, 0, False)
	EndIf

	Local $oPacing = $g_oRunExecutionIntent.Item("pacing")
	If Not RunPacingActivate($oPacing, $sError) Then Return SetError(2, 0, False)
	If Not RunSessionStart($g_oRunExecutionSession) Then
		$sError = "Prepared run session could not start"
		RunPacingDeactivate()
		Return SetError(3, 0, False)
	EndIf

	$g_iRunExecutionBattleBaseline = _RunExecutionBattleTotal()
	$g_iRunExecutionBattleObserved = 0
	$g_iRunExecutionGoldBaseline = _RunExecutionLootTotal($g_aiTotalGoldGain)
	$g_iRunExecutionElixirBaseline = _RunExecutionLootTotal($g_aiTotalElixirGain)
	$g_iRunExecutionDarkBaseline = _RunExecutionLootTotal($g_aiTotalDarkGain)
	$g_hRunExecutionStarted = __TimerInit()
	RunExecutionResetDeploymentProof()
	$g_bRunExecutionActive = True
	$g_sRunExecutionMessage = "Planned run active"

	Local $sState = RunIntentVerificationState($g_oRunExecutionIntent)
	RunEventLogRunStarted($g_oRunExecutionIntent.Item("surface_id"), $sState, RunIntentDescribe($g_oRunExecutionIntent))
	SetLog("Run Planner: execution active - " & RunIntentDescribe($g_oRunExecutionIntent), $COLOR_SUCCESS)
	Return True
EndFunc   ;==>RunExecutionBegin

Func _RunExecutionRestoreProfile()
	If Not $g_bRunExecutionProfileSnapshotCaptured Then
		$g_bRunExecutionManageTraining = True
		RunProfileOverrideEnd()
		Return
	EndIf

	; An explicit emulator/instance plan reinitializes emulator-specific paths and capabilities.
	; Restore that configuration through the same adapter, then assign the exact captured selectors.
	If $g_bRunExecutionEmulatorChanged Then
		UpdateHWnD(0, False)
		If Not UpdateAndroidConfig($g_sRunExecutionSnapshotAndroidInstance, $g_sRunExecutionSnapshotAndroidEmulator) Then _
			SetDebugLog("Run Planner: could not reinitialize the captured emulator configuration", $COLOR_ERROR)
	EndIf
	$g_iAndroidConfig = $g_iRunExecutionSnapshotAndroidConfig
	$g_sAndroidEmulator = $g_sRunExecutionSnapshotAndroidEmulator
	$g_sAndroidInstance = $g_sRunExecutionSnapshotAndroidInstance

	For $iMode = 0 To $g_iModeCount - 1
		$g_sAttackScrScriptName[$iMode] = $g_asRunExecutionSnapshotAttackScript[$iMode]
		$g_aiAttackAlgorithm[$iMode] = $g_aiRunExecutionSnapshotAttackAlgorithm[$iMode]
		$g_aiAttackStdDropSides[$iMode] = $g_aiRunExecutionSnapshotAttackStdDropSides[$iMode]
		$g_abAttackStdSmartAttack[$iMode] = $g_abRunExecutionSnapshotAttackStdSmartAttack[$iMode]
		$g_aiAttackUseHeroes[$iMode] = $g_aiRunExecutionSnapshotAttackUseHeroes[$iMode]
		$g_abAttackDropCC[$iMode] = $g_abRunExecutionSnapshotAttackDropCC[$iMode]
		$g_abAttackUseRageSpell[$iMode] = $g_abRunExecutionSnapshotAttackUseRageSpell[$iMode]
		$g_abAttackUseFreezeSpell[$iMode] = $g_abRunExecutionSnapshotAttackUseFreezeSpell[$iMode]
		$g_aiSearchHeroWaitEnable[$iMode] = $g_aiRunExecutionSnapshotSearchHeroWaitEnable[$iMode]
		$g_abSearchSpellsWaitEnable[$iMode] = $g_abRunExecutionSnapshotSearchSpellsWaitEnable[$iMode]
		$g_abSearchSiegeWaitEnable[$iMode] = $g_abRunExecutionSnapshotSearchSiegeWaitEnable[$iMode]
		$g_aiFilterMeetGE[$iMode] = $g_aiRunExecutionSnapshotFilterMeetGE[$iMode]
		$g_aiFilterMinGold[$iMode] = $g_aiRunExecutionSnapshotFilterMinGold[$iMode]
		$g_aiFilterMinElixir[$iMode] = $g_aiRunExecutionSnapshotFilterMinElixir[$iMode]
		$g_abFilterMeetDEEnable[$iMode] = $g_abRunExecutionSnapshotFilterMeetDEEnable[$iMode]
		$g_aiFilterMeetDEMin[$iMode] = $g_aiRunExecutionSnapshotFilterMeetDEMin[$iMode]
	Next
	For $iMode = 0 To $g_iModeCount
		$g_abAttackTypeEnable[$iMode] = $g_abRunExecutionSnapshotAttackTypeEnable[$iMode]
		If $iMode = $g_iModeCount Then
			$g_aiAttackStdDropSides[$iMode] = $g_aiRunExecutionSnapshotAttackStdDropSides[$iMode]
			$g_abAttackStdSmartAttack[$iMode] = $g_abRunExecutionSnapshotAttackStdSmartAttack[$iMode]
		EndIf
	Next
	For $iSpell = 0 To $eSpellCount - 1
		$g_aiArmyCompSpells[$iSpell] = $g_aiRunExecutionSnapshotArmyCompSpells[$iSpell]
	Next
	For $iSiege = 0 To $eSiegeMachineCount - 1
		$g_aiArmyCompSiegeMachines[$iSiege] = $g_aiRunExecutionSnapshotArmyCompSiegeMachines[$iSiege]
	Next

	$g_bChkDonate = $g_bRunExecutionSnapshotChkDonate
	$g_bDonateLikeCrazy = $g_bRunExecutionSnapshotDonateLikeCrazy
	$g_bRequestTroopsEnable = $g_bRunExecutionSnapshotRequestTroopsEnable
	$g_bChkClanGamesEnabled = $g_bRunExecutionSnapshotChkClanGamesEnabled
	$g_bChkCollect = $g_bRunExecutionSnapshotChkCollect
	$g_bChkCollectCartFirst = $g_bRunExecutionSnapshotChkCollectCartFirst
	$g_bChkTreasuryCollect = $g_bRunExecutionSnapshotChkTreasuryCollect
	$g_bChkCollectAchievements = $g_bRunExecutionSnapshotChkCollectAchievements
	$g_bChkCollectFreeMagicItems = $g_bRunExecutionSnapshotChkCollectFreeMagicItems
	$g_bChkCollectRewards = $g_bRunExecutionSnapshotChkCollectRewards
	$g_bChkSellRewards = $g_bRunExecutionSnapshotChkSellRewards
	$g_bAutoLabUpgradeEnable = $g_bRunExecutionSnapshotAutoLabUpgradeEnable
	$g_bAutoUpgradeWallsEnable = $g_bRunExecutionSnapshotAutoUpgradeWallsEnable
	$g_bAutoUpgradeEnabled = $g_bRunExecutionSnapshotAutoUpgradeEnabled
	$g_bChkSwitchAcc = $g_bRunExecutionSnapshotChkSwitchAcc
	$g_bPlannedDropCCHoursEnable = $g_bRunExecutionSnapshotPlannedDropCCHoursEnable
	$g_bUseCCBalanced = $g_bRunExecutionSnapshotUseCCBalanced
	$g_bRunExecutionManageTraining = True
	$g_bRunExecutionEmulatorChanged = False
	$g_bRunExecutionProfileSnapshotCaptured = False
	RunProfileOverrideEnd()
	SetDebugLog("Run Planner: restored the captured profile fields after one-run overrides")
EndFunc   ;==>_RunExecutionRestoreProfile

Func _RunExecutionSyncSession()
	If Not $g_bRunExecutionActive Or Not IsObj($g_oRunExecutionSession) Then Return
	Local $iBattles = _RunExecutionBattleTotal() - $g_iRunExecutionBattleBaseline
	If $iBattles <= $g_iRunExecutionBattleObserved Then Return

	Local $iNewBattles = $iBattles - $g_iRunExecutionBattleObserved
	Local $iGold = _RunExecutionLootTotal($g_aiTotalGoldGain) - $g_iRunExecutionGoldBaseline - Int($g_oRunExecutionSession.Item("gold"))
	Local $iElixir = _RunExecutionLootTotal($g_aiTotalElixirGain) - $g_iRunExecutionElixirBaseline - Int($g_oRunExecutionSession.Item("elixir"))
	Local $iDark = _RunExecutionLootTotal($g_aiTotalDarkGain) - $g_iRunExecutionDarkBaseline - Int($g_oRunExecutionSession.Item("dark_elixir"))
	If $iGold < 0 Then $iGold = 0
	If $iElixir < 0 Then $iElixir = 0
	If $iDark < 0 Then $iDark = 0

	For $i = 1 To $iNewBattles
		Local $bSuccess = Number($g_sStarsEarned) > 0
		Local $sRecordError = ""
		If Not RunIntentRecordBattle($g_oRunExecutionIntent, $g_oRunExecutionSession, $bSuccess, $sRecordError, _
				($i = 1 ? $iGold : 0), ($i = 1 ? $iElixir : 0), ($i = 1 ? $iDark : 0)) Then
			SetLog("Run Planner: battle accounting failed - " & $sRecordError, $COLOR_ERROR)
			ExitLoop
		EndIf
	Next
	$g_iRunExecutionBattleObserved = $iBattles
EndFunc   ;==>_RunExecutionSyncSession

Func RunExecutionCheckStop()
	If Not $g_bRunExecutionActive Or Not IsObj($g_oRunExecutionSession) Then Return False
	If RunPacingRestIfDue() Then
		btnStop()
		Return True
	EndIf
	_RunExecutionSyncSession()
	Local $sReason = RunSessionEvaluateStop($g_oRunExecutionSession, __TimerDiff($g_hRunExecutionStarted), ($StarBonusReceived = 1))
	If $sReason = "" Then Return False

	$g_sRunExecutionMessage = "Stopping: " & $sReason
	SetLog("Run Planner: stop condition reached - " & $sReason, $COLOR_SUCCESS)
	RunEventLogRunStopping($g_oRunExecutionIntent.Item("surface_id"), RunIntentVerificationState($g_oRunExecutionIntent), $sReason)
	btnStop()
	Return True
EndFunc   ;==>RunExecutionCheckStop

Func RunExecutionCancelPrepared($sReason)
	Local $sCancelledSessionId = RunExecutionSessionId()
	; Prepared sessions can already have performed explicit readiness/recovery work. If they never
	; reached running, close the recorded session as failed rather than silently releasing its ID.
	If $g_bRunExecutionPrepared And Not $g_bRunExecutionActive And IsObj($g_oRunExecutionSession) Then
		RunSessionFail($g_oRunExecutionSession, $sReason)
		If IsObj($g_oRunExecutionIntent) Then _
			RunEventLogRunFailed($g_oRunExecutionIntent.Item("surface_id"), RunIntentVerificationState($g_oRunExecutionIntent), _
					"Preflight failed: " & $sReason)
	EndIf
	If IsObj($g_oRunExecutionIntent) Then
		Local $oPlan = $g_oRunExecutionIntent.Item("plan")
		If $oPlan.Item("notify_on_error") Then SetLog("Run notification: " & $sReason, $COLOR_ERROR)
	EndIf
	If $g_bRunExecutionActive And IsObj($g_oRunExecutionSession) Then RunSessionFail($g_oRunExecutionSession, $sReason)
	_RunExecutionRestoreProfile()
	$g_bRunExecutionPrepared = False
	$g_bRunExecutionActive = False
	$g_oRunExecutionSession = 0
	$g_oRunExecutionIntent = 0
	If $sCancelledSessionId <> "" Then RunEventLogReleaseSession($sCancelledSessionId)
	RunPacingDeactivate()
	RunExecutionResetDeploymentProof()
	$g_sRunExecutionMessage = $sReason
EndFunc   ;==>RunExecutionCancelPrepared

Func RunExecutionComplete($sFallbackReason = "stopped")
	If Not $g_bRunExecutionPrepared Then Return
	Local $sCompletedSessionId = RunExecutionSessionId()
	If $g_bRunExecutionActive And IsObj($g_oRunExecutionSession) Then
		_RunExecutionSyncSession()
		Local $bIntentReady = IsObj($g_oRunExecutionIntent)
		Local $bStopRequested = False
		If $g_oRunExecutionSession.Item("state") = "running" Then $bStopRequested = RunSessionRequestStop($g_oRunExecutionSession, $sFallbackReason)
		Local $sReason = String($g_oRunExecutionSession.Item("stop_reason"))
		If $sReason = "" Then $sReason = $sFallbackReason
		If $bStopRequested And $bIntentReady Then RunEventLogRunStopping($g_oRunExecutionIntent.Item("surface_id"), RunIntentVerificationState($g_oRunExecutionIntent), $sReason)
		Local $bSessionCompleted = RunSessionComplete($g_oRunExecutionSession)
		If $bSessionCompleted And $bIntentReady Then
			RunEventLogRunCompleted($g_oRunExecutionIntent.Item("surface_id"), RunIntentVerificationState($g_oRunExecutionIntent), $sReason)
			Local $oPlan = $g_oRunExecutionIntent.Item("plan")
			If $oPlan.Item("notify_on_stop") Then SetLog("Run notification: " & $sReason, $COLOR_SUCCESS)
			$g_sRunExecutionMessage = "Completed: " & $sReason
		Else
			Local $sCompletionError = ($bIntentReady ? "Run session could not transition to completed" : "Run completion lost its execution intent")
			RunEventLogWrite("error", "error", $sCompletionError, "", $RUN_VERIFICATION_DIAGNOSTIC)
			SetLog("Run Planner: " & $sCompletionError, $COLOR_ERROR)
			$g_sRunExecutionMessage = "Stopped with lifecycle error: " & $sCompletionError
		EndIf
	EndIf
	If $sCompletedSessionId <> "" Then RunEventLogReleaseSession($sCompletedSessionId)
	_RunExecutionRestoreProfile()
	$g_bRunExecutionPrepared = False
	$g_bRunExecutionActive = False
	$g_oRunExecutionSession = 0
	$g_oRunExecutionIntent = 0
	RunPacingDeactivate()
	RunExecutionResetDeploymentProof()
EndFunc   ;==>RunExecutionComplete
