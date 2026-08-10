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
Global $g_bRunExecutionProfileSnapshotCaptured = False
Global $g_bRunExecutionEmulatorChanged = False
Global $g_iRunExecutionSnapshotAndroidConfig = 0
Global $g_sRunExecutionSnapshotAndroidEmulator = ""
Global $g_sRunExecutionSnapshotAndroidInstance = ""
Global $g_asRunExecutionSnapshotAttackScript[$g_iModeCount]
Global $g_abRunExecutionSnapshotAttackTypeEnable[$g_iModeCount + 1]
Global $g_aiRunExecutionSnapshotAttackAlgorithm[$g_iModeCount]
Global $g_aiRunExecutionSnapshotAttackUseHeroes[$g_iModeCount]
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
Global $g_bRunExecutionSnapshotAutoLabUpgradeEnable = False
Global $g_bRunExecutionSnapshotAutoUpgradeWallsEnable = False
Global $g_bRunExecutionSnapshotAutoUpgradeEnabled = False

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

Func _RunExecutionCaptureProfileSnapshot()
	If $g_bRunExecutionProfileSnapshotCaptured Then Return False

	$g_iRunExecutionSnapshotAndroidConfig = $g_iAndroidConfig
	$g_sRunExecutionSnapshotAndroidEmulator = $g_sAndroidEmulator
	$g_sRunExecutionSnapshotAndroidInstance = $g_sAndroidInstance
	For $iMode = 0 To $g_iModeCount - 1
		$g_asRunExecutionSnapshotAttackScript[$iMode] = $g_sAttackScrScriptName[$iMode]
		$g_aiRunExecutionSnapshotAttackAlgorithm[$iMode] = $g_aiAttackAlgorithm[$iMode]
		$g_aiRunExecutionSnapshotAttackUseHeroes[$iMode] = $g_aiAttackUseHeroes[$iMode]
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
	$g_bRunExecutionSnapshotAutoLabUpgradeEnable = $g_bAutoLabUpgradeEnable
	$g_bRunExecutionSnapshotAutoUpgradeWallsEnable = $g_bAutoUpgradeWallsEnable
	$g_bRunExecutionSnapshotAutoUpgradeEnabled = $g_bAutoUpgradeEnabled
	$g_bRunExecutionEmulatorChanged = False
	$g_bRunExecutionProfileSnapshotCaptured = True
	Return RunProfileOverrideBegin($g_bRunExecutionSnapshotChkClanGamesEnabled, $g_bRunExecutionSnapshotAutoLabUpgradeEnable, _
			$g_bRunExecutionSnapshotDonateLikeCrazy)
EndFunc   ;==>_RunExecutionCaptureProfileSnapshot

Func RunExecutionPrepareStart(ByRef $sError)
	$sError = ""
	_RunExecutionRestoreProfile()
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
	RunEventLogBindSession($sSessionId)
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

	Local $iAlgorithm = (StringLower(String($oPlan.Item("strategy"))) = "legacy.csv") ? 1 : 0
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
	$g_bRunExecutionActive = True
	$g_sRunExecutionMessage = "Planned run active"

	Local $sState = RunIntentVerificationState($g_oRunExecutionIntent)
	RunEventLogRunStarted($g_oRunExecutionIntent.Item("surface_id"), $sState, RunIntentDescribe($g_oRunExecutionIntent))
	SetLog("Run Planner: execution active - " & RunIntentDescribe($g_oRunExecutionIntent), $COLOR_SUCCESS)
	Return True
EndFunc   ;==>RunExecutionBegin

Func _RunExecutionRestoreProfile()
	If Not $g_bRunExecutionProfileSnapshotCaptured Then
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
		$g_aiAttackUseHeroes[$iMode] = $g_aiRunExecutionSnapshotAttackUseHeroes[$iMode]
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
	$g_bAutoLabUpgradeEnable = $g_bRunExecutionSnapshotAutoLabUpgradeEnable
	$g_bAutoUpgradeWallsEnable = $g_bRunExecutionSnapshotAutoUpgradeWallsEnable
	$g_bAutoUpgradeEnabled = $g_bRunExecutionSnapshotAutoUpgradeEnabled
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
EndFunc   ;==>RunExecutionComplete
