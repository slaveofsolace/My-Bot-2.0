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

Func RunExecutionPlanActive()
	Return $g_bRunExecutionActive
EndFunc   ;==>RunExecutionPlanActive

Func RunExecutionMessage()
	Return $g_sRunExecutionMessage
EndFunc   ;==>RunExecutionMessage

Func RunExecutionSessionId()
	If Not IsObj($g_oRunExecutionSession) Then Return ""
	Return String($g_oRunExecutionSession.Item("session_id"))
EndFunc   ;==>RunExecutionSessionId

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

Func RunExecutionPrepareStart(ByRef $sError)
	$sError = ""
	$g_bRunExecutionPrepared = False
	$g_bRunExecutionActive = False
	$g_oRunExecutionIntent = 0
	$g_oRunExecutionSession = 0
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
	$g_bRunExecutionPrepared = True
	$g_sRunExecutionMessage = "Prepared " & $oIntent.Item("surface_label")
	Return True
EndFunc   ;==>RunExecutionPrepareStart

Func _RunExecutionApplyIntent(ByRef $sError)
	$sError = ""
	If Not $g_bRunExecutionPrepared Or Not IsObj($g_oRunExecutionIntent) Then Return True
	If Not RunExecutionContractValidate($g_oRunExecutionIntent, $sError) Then Return False

	Local $oPlan = $g_oRunExecutionIntent.Item("plan")
	Local $sEmulator = StringLower(String($oPlan.Item("emulator")))
	If $sEmulator <> "auto" Then
		$g_sAndroidEmulator = _RunExecutionEmulatorName($sEmulator)
		$g_sAndroidInstance = String($oPlan.Item("emulator_instance"))
	EndIf

	Local $iAlgorithm = (StringLower(String($oPlan.Item("strategy"))) = "legacy.csv") ? 1 : 0
	Local $oLoadout = $g_oRunExecutionIntent.Item("loadout")
	Local $iHeroMask = _RunExecutionHeroMask($oLoadout)
	Local $bWaitForFull = $oPlan.Item("army_wait_for_full")
	For $iMode = $DB To $LB
		$g_abAttackTypeEnable[$iMode] = True
		$g_aiAttackAlgorithm[$iMode] = $iAlgorithm
		$g_aiAttackUseHeroes[$iMode] = $iHeroMask
		$g_aiSearchHeroWaitEnable[$iMode] = $bWaitForFull ? $iHeroMask : $eHeroNone
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
	$g_bChkClanGamesEnabled = $oPlan.Item("events_clan_games") ? 1 : 0
	$g_bChkCollect = $oPlan.Item("events_collect_resources")
	$g_bAutoLabUpgradeEnable = False
	$g_bAutoUpgradeWallsEnable = (StringLower(String($oPlan.Item("upgrade_policy"))) = "walls")
	$g_bAutoUpgradeEnabled = False
	Return True
EndFunc   ;==>_RunExecutionApplyIntent

Func RunExecutionBegin(ByRef $sError)
	$sError = ""
	If Not $g_bRunExecutionPrepared Then Return True
	If Not _RunExecutionApplyIntent($sError) Then Return SetError(1, 0, False)

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
	$g_bRunExecutionActive = True
	$g_sRunExecutionMessage = "Planned run active"

	Local $sState = RunIntentVerificationState($g_oRunExecutionIntent)
	RunEventLogRunStarted($g_oRunExecutionIntent.Item("surface_id"), $sState, RunIntentDescribe($g_oRunExecutionIntent))
	SetLog("Run Planner: execution active - " & RunIntentDescribe($g_oRunExecutionIntent), $COLOR_SUCCESS)
	Return True
EndFunc   ;==>RunExecutionBegin

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
	If IsObj($g_oRunExecutionIntent) Then
		Local $oPlan = $g_oRunExecutionIntent.Item("plan")
		If $oPlan.Item("notify_on_error") Then SetLog("Run notification: " & $sReason, $COLOR_ERROR)
	EndIf
	If $g_bRunExecutionActive And IsObj($g_oRunExecutionSession) Then RunSessionFail($g_oRunExecutionSession, $sReason)
	$g_bRunExecutionPrepared = False
	$g_bRunExecutionActive = False
	$g_oRunExecutionSession = 0
	RunPacingDeactivate()
	$g_sRunExecutionMessage = $sReason
EndFunc   ;==>RunExecutionCancelPrepared

Func RunExecutionComplete($sFallbackReason = "stopped")
	If Not $g_bRunExecutionPrepared Then Return
	If $g_bRunExecutionActive And IsObj($g_oRunExecutionSession) Then
		_RunExecutionSyncSession()
		If $g_oRunExecutionSession.Item("state") = "running" Then RunSessionRequestStop($g_oRunExecutionSession, $sFallbackReason)
		Local $sReason = String($g_oRunExecutionSession.Item("stop_reason"))
		If $sReason = "" Then $sReason = $sFallbackReason
		RunSessionComplete($g_oRunExecutionSession)
		RunEventLogRunCompleted($g_oRunExecutionIntent.Item("surface_id"), RunIntentVerificationState($g_oRunExecutionIntent), $sReason)
		Local $oPlan = $g_oRunExecutionIntent.Item("plan")
		If $oPlan.Item("notify_on_stop") Then SetLog("Run notification: " & $sReason, $COLOR_SUCCESS)
		$g_sRunExecutionMessage = "Completed: " & $sReason
	EndIf
	$g_bRunExecutionPrepared = False
	$g_bRunExecutionActive = False
	RunPacingDeactivate()
EndFunc   ;==>RunExecutionComplete
