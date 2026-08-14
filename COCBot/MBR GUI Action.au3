; #FUNCTION# ====================================================================================================================
; Name ..........: MBR GUI Action
; Description ...: This file Includes all functions to current GUI
; Syntax ........:
; Parameters ....: None
; Return values .: None
; Author ........: cosote (2016)
; Modified ......: CodeSlinger69 (2017)
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

Func _BotStartReject($sReason)
	If $sReason = "" Then $sReason = "Start cancelled"
	RunExecutionCancelPrepared($sReason)
	If $g_iBotAction <> $eBotClose Then btnStop()
	RunControlReportStartOutcome(False, $sReason)
	Return False
EndFunc   ;==>_BotStartReject

Func _BotOpenCollectorsReject($sReason, $sOutcome = "rejected")
	If $sReason = "" Then $sReason = "Template-free collectors were not started"
	RunExecutionCancelPrepared($sReason)
	RunControlReportOneShotOutcome($sOutcome, $sReason)
	Return False
EndFunc   ;==>_BotOpenCollectorsReject

; Run one collectors-only pass without loading the restricted managed image engine. The emulator must
; already be running and exactly match the bound BlueStacks 5 instance; this path never launches,
; reboots, resizes, zooms, authenticates, searches, trains, donates, upgrades, or spends.
Func _BotStartOpenHomeCollectors(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free collectors cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	If WinGetAndroidHandle() = 0 Then Return _BotOpenCollectorsReject("The exact BlueStacks 5 instance is not already running")
	If Not $g_bAndroidAdbScreencap Or Not $g_bAndroidAdbClick Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 ADB capture/click surface is not available")
	If Not OpenHomeCollectorsProveHome() Then Return _BotOpenCollectorsReject("The current screen is not the proven Home Village")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free collectors cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Template-free Home collectors started")
	RunEventLogMaintenanceCollectorsStarted()

	Local $bCollected = OpenHomeCollectorsCollectOnePass()
	Local $iCollectError = @error
	Local $iCollectorClicks = @extended
	If Not $bCollected Then
		If $iCollectError = 2 Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Template-free collectors stopped")
			Return False
		EndIf
		$sStartError = "Template-free collectors failed"
		Switch $iCollectError
			Case 3
				$sStartError &= ": Home Village was not proven before input"
			Case 4
				$sStartError &= ": the selected collector click was not accepted"
			Case 5
				$sStartError &= ": Home Village was not re-proven after " & $iCollectorClicks & " accepted clicks; inputs will not be retried"
			Case Else
				$sStartError &= ": the bounded adapter returned an unknown outcome"
		EndSwitch
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	RunEventLogMaintenanceHomeVerified($iCollectorClicks, "disabled", "disabled", "disabled")
	If $iCollectorClicks > 0 Then
		RunEventLogMaintenanceCollectorsCompleted($iCollectorClicks)
	Else
		RunEventLogMaintenanceCollectorsNoneActionable()
	EndIf
	Local $sReason = $iCollectorClicks > 0 ? "home-collectors-open-complete" : "home-collectors-open-none-actionable"
	RunExecutionComplete($sReason)
	Local $sMessage = "Template-free Home collectors completed; collector_clicks=" & $iCollectorClicks
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartOpenHomeCollectors

Func _BotEngineCheckFinish($bPassed, $sMessage)
	If $sMessage = "" Then $sMessage = $bPassed ? "Managed engine check passed" : "Managed engine check failed"
	; Native terminalization is the linearization point. A Stop accepted before it changes the
	; effective result to cancelled; a Stop after it sees an idle engine and is a truthful no-op.
	Local $sOutcome = RunControlReportEngineCheckOutcome($bPassed, $sMessage)
	Switch $sOutcome
		Case "passed"
			RunEventLogEngineCheckPassed()
		Case "cancelled"
			RunEventLogEngineCheckCancelled($sMessage)
		Case Else
			RunEventLogEngineCheckFailed($sMessage)
	EndSwitch
	Return $sOutcome = "passed"
EndFunc   ;==>_BotEngineCheckFinish

; Initialize the real in-process managed engine under launcher supervision, then return idle before
; plan preparation, authentication, emulator activation, ADB, recognition, or game input. The DLL
; intentionally remains resident: unloading a mixed-mode CLR image is not a safe readiness test.
Func _BotCheckManagedEngine()
	Local $sError = ""
	RunEventLogEngineCheckStarted()
	If RunControlStopRequested() Then Return _BotEngineCheckFinish(False, "Managed engine check cancelled before initialization")
	If Not MBRFuncProbeEngine($sError) Then
		If $sError = "" Then $sError = "Managed engine static validation failed"
		Return _BotEngineCheckFinish(False, $sError)
	EndIf
	If RunControlStopRequested() Then Return _BotEngineCheckFinish(False, "Managed engine check cancelled before initialization")
	If Not MBRFuncInitialize(False) Then
		$sError = MBRFuncEngineError()
		If $sError = "" Then $sError = "Managed engine initialization failed"
		Return _BotEngineCheckFinish(False, $sError)
	EndIf
	If RunControlStopRequested() Then Return _BotEngineCheckFinish(False, "Managed engine check cancelled after initialization")
	Return _BotEngineCheckFinish(True, "Managed engine initialized in the real backend; no emulator or game action was attempted")
EndFunc   ;==>_BotCheckManagedEngine

Func BotStart($bAutostartDelay = 0)
	FuncEnter(BotStart)
	RunControlBeginStart()
	If RunControlEngineCheckRequested() Then Return FuncReturn(_BotCheckManagedEngine())

	Local $sStartError = ""
	If Not RunExecutionPrepareStart($sStartError) Then
		SetLog("Run Planner cannot start: " & $sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	Local $oPreparedIntent = RunExecutionPreparedIntent()
	Local $iOpenCollectorsMode = OpenHomeCollectorsPreparedMode($oPreparedIntent, $sStartError)
	If $iOpenCollectorsMode = 1 Then Return FuncReturn(_BotStartOpenHomeCollectors($sStartError))
	If $iOpenCollectorsMode = -1 Then Return FuncReturn(_BotOpenCollectorsReject($sStartError))

	If Not MBRFuncProbeEngine($sStartError) Then
		SetLog("Engine unavailable: " & $sStartError, $COLOR_ERROR)
		GUICtrlSetState($g_hBtnStart, $GUI_DISABLE)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf

	If Not MBRFuncInitialize() Then
		$sStartError = MBRFuncEngineError()
		If $sStartError = "" Then
			$sStartError = "Unable to initialize " & $g_sMBRLib & "."
			MBRFuncMarkUnavailable($sStartError)
		EndIf
		SetLog($sStartError, $COLOR_ERROR)
		GUICtrlSetState($g_hBtnStart, $GUI_DISABLE)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf

	If Not ForumAuthentication() Then
		$sStartError = "Upstream engine authorization was cancelled or rejected"
		SetLog($sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	RunControlWriteStatus(True)

	If Not $g_bSearchMode Then
		If $g_hLogFile = 0 Then CreateLogFile() ; only create new log file when doesn't exist yet
		CreateAttackLogFile()
		If $g_iFirstRun = -1 Then $g_iFirstRun = 1
	EndIf
	SetLogCentered(" BOT LOG ", Default, Default, True)

	ResumeAndroid()
	CleanSecureFiles()
	;CalCostCamp()
	;CalCostSpell()
	;CalCostSiege()
	sldAdditionalClickDelay(True)

	; Readiness belongs to this Start attempt. A previous run may have left the
	; main-screen flag true even though the current emulator view has changed.
	$g_bMainWindowOk = False
	$g_bRunState = True
	$g_bTogglePauseAllowed = True
	$g_bSkipFirstZoomout = False
	$g_bIsSearchLimit = False
	$g_bIsClientSyncError = False
	$g_bZoomoutFailureNotRestartingAnything = False
	$g_bRestart = False
	$g_bStayOnBuilderBase = False

	EnableControls($g_hFrmBotBottom, False, $g_aFrmBotBottomCtrlState)
	;$g_iFirstAttack = 0

	$g_bTrainEnabled = True
	$g_bDonationEnabled = True
	$g_bMeetCondStop = False
	$g_bIsClientSyncError = False
	$g_bFirstStart = True

	SaveConfig()
	readConfig()
	applyConfig(False) ; bot window redraw stays disabled!
	If Not RunExecutionApplyPrepared($sStartError) Then
		SetLog("Run Planner cannot apply: " & $sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	CreaTableDB()

	; Initial ObjEvents for the Autoit objects errors
	__ObjEventIni()

	If BitAND($g_iAndroidSupportFeature, 1 + 2) = 0 And $g_bChkBackgroundMode = True Then
		GUICtrlSetState($g_hChkBackgroundMode, $GUI_UNCHECKED)
		UpdateChkBackground() ; Invoke Event manually
		SetLog("Background Mode not supported for " & $g_sAndroidEmulator & " and has been disabled", $COLOR_ERROR)
	EndIf

	; update bottom buttons
	GUICtrlSetState($g_hBtnStart, $GUI_HIDE)
	GUICtrlSetState($g_hBtnStop, $GUI_SHOW)
	GUICtrlSetState($g_hBtnPause, $GUI_SHOW)
	GUICtrlSetState($g_hBtnResume, $GUI_HIDE)
	GUICtrlSetState($g_hBtnSearchMode, $GUI_HIDE)
	GUICtrlSetState($g_hChkBackgroundMode, $GUI_DISABLE)

	; update task bar buttons
	_ITaskBar_UpdateTBButton($g_hTblStop, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblStart, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblPause, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblResume, $THBF_DISABLED)

	; update try items
	TrayItemSetText($g_hTiStartStop, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Stop", "Stop bot"))
	TrayItemSetState($g_hTiPause, $TRAY_ENABLE)
	TrayItemSetText($g_hTiPause, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Pause", "Pause bot"))

	EnableControls($g_hFrmBotBottom, Default, $g_aFrmBotBottomCtrlState)

	DisableGuiControls()

	SetRedrawBotWindow(True, Default, Default, Default, "BotStart")

	If $bAutostartDelay Then
		SetLog("Bot Auto Starting in " & Round($bAutostartDelay / 1000, 0) & " seconds", $COLOR_ERROR)
		_SleepStatus($bAutostartDelay)
	EndIf

	$g_sClanGamesScore = "N/A"
	$g_sClanGamesTimeRemaining = "N/A"
	$YourAccScore[0] = -1
	$YourAccScore[1] = True
	$IsCGEventRunning = 0
	$g_bIsBBevent = 0
	$g_bClanGamesCompleted = 0
	CloseCGSettings()
	CloseHeroEquipment()
	$g_bFirstStartBarrel = 1
	$g_sAvailableAppBuilder = 0
	$g_sAvailableLabAssistant = 0
	$g_iBuilderBoostDiscount = 0
	$g_bFirstStartForHiddenHero = 1
	$g_iHeroAvailable = $eHeroNone
	For $i = 0 To 4
		$g_aiHeroUpgradeFinishDate[$i] = 0
	Next
	For $i = 0 To 4
		$g_aiHeroNeededResource[$i] = 0
	Next
	For $i = 0 To 7
		$bCheckHeroOrder[$i] = False
	Next
	$g_aiAttackedCountPause = 0
	$g_aiAttackedCount = 0
	For $i = 0 To $g_iModeCount - 1
		$g_aiAttackedVillageCount[$i] = 0
	Next

	CleanSuperchargeTemplates()

	; wait for slot
	LockBotSlot(True)
	If $g_bRunState = False Then Return FuncReturn(_BotStartReject("Start cancelled while waiting for the bot slot"))

	Local $Result = False
	If WinGetAndroidHandle() = 0 Then
		$Result = OpenAndroid(False)
	EndIf
	SetDebugLog("Android Window Handle: " & WinGetAndroidHandle())
	If $g_hAndroidWindow <> 0 Then ;Is Android open?
		If Not $g_bRunState Then Return FuncReturn(_BotStartReject("Start cancelled while opening Android"))
		If $g_bAndroidBackgroundLaunched = True Or AndroidControlAvailable() Then ; Really?
			If Not $Result Then
				$Result = InitiateLayout()
			EndIf
		Else
			; Not really
			SetLog("Current " & $g_sAndroidEmulator & " Window not supported by " & $g_sProductName, $COLOR_ERROR)
			$Result = RebootAndroid(False)
		EndIf
		If Not $g_bRunState Then Return FuncReturn(_BotStartReject("Start cancelled while initializing Android"))
		; A modern BlueStacks 5 instance that has an exact Qt window binding plus ADB capture and
		; ADB click support does not need to steal foreground focus. Requiring WinActivate here made
		; otherwise healthy background runs fail whenever the Control Center or another app was active.
		Local $bFocusIndependentControl = $g_bAndroidBackgroundLaunched Or IsArray(GetBlueStacks5ModernAdbSurfacePosition())
		Local $hWndActive = $g_hAndroidWindow
		; check if window can be activated
		If Not $bFocusIndependentControl And $g_bNoFocusTampering = False And $g_bAndroidEmbedded = False Then
			Local $hTimer = __TimerInit()
			$hWndActive = -1
			Local $activeHWnD = WinGetHandle("")
			While __TimerDiff($hTimer) < 1000 And $hWndActive <> $g_hAndroidWindow And Not _Sleep(100)
				$hWndActive = WinActivate($g_hAndroidWindow) ; ensure bot has window focus
			WEnd
			WinActivate($activeHWnD) ; restore current active window
		EndIf
		If Not $g_bRunState Then Return FuncReturn(_BotStartReject("Start cancelled while activating Android"))
		If ($bFocusIndependentControl Or $hWndActive = $g_hAndroidWindow) And ($g_bAndroidBackgroundLaunched = True Or AndroidControlAvailable()) Then  ; Really?
			If Not Initiate($sStartError) Then
				If $sStartError = "" Then $sStartError = "Android and Clash of Clans initialization did not complete"
				SetLog("Bot cannot start: " & $sStartError, $COLOR_ERROR)
				Return FuncReturn(_BotStartReject($sStartError))
			EndIf
		Else
			$sStartError = "Cannot use " & $g_sAndroidEmulator & "; check the Android log"
			SetLog($sStartError, $COLOR_ERROR)
			Return FuncReturn(_BotStartReject($sStartError))
		EndIf
	Else
		$sStartError = "Cannot start " & $g_sAndroidEmulator & "; check the Android log"
		SetLog($sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	Return FuncReturn(True)
EndFunc   ;==>BotStart

Func BotStop()
	CleanSuperchargeTemplates()
	FuncEnter(BotStop)
	; release bot slot
	LockBotSlot(False)

	; release other switch accounts
	releaseProfilesMutex()

	ResumeAndroid()

	$g_bRunState = False
	$g_bBotPaused = False
	$g_bTogglePauseAllowed = True
	$g_bRestart = False

	;WinSetState($g_hFrmBotBottom, "", @SW_DISABLE)
	Local $aCtrlState
	EnableControls($g_hFrmBotBottom, False, $g_aFrmBotBottomCtrlState)
	;$g_bFirstStart = true

	EnableGuiControls()

	;DistributorsUpdateGUI()
	AndroidBotStopEvent() ; signal android that bot is now stopping
	If $g_bTerminateAdbShellOnStop Then
		AndroidAdbTerminateShellInstance() ; terminate shell instance
	EndIf
	AndroidShield("btnStop", Default)
	; Keep an explicit one-run emulator selected until its stop/shield callbacks have completed,
	; then restore the exact captured profile fields.
	RunExecutionComplete("stopped")

	EnableControls($g_hFrmBotBottom, Default, $g_aFrmBotBottomCtrlState)

	; update bottom buttons
	GUICtrlSetState($g_hChkBackgroundMode, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnStart, $GUI_SHOW)
	GUICtrlSetState($g_hBtnStart, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnStop, $GUI_HIDE)
	GUICtrlSetState($g_hBtnPause, $GUI_HIDE)
	GUICtrlSetState($g_hBtnResume, $GUI_HIDE)
	If $g_iTownHallLevel > 2 Then GUICtrlSetState($g_hBtnSearchMode, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnSearchMode, $GUI_SHOW)
	;GUICtrlSetState($g_hBtnMakeScreenshot, $GUI_ENABLE)

	; update task bar buttons
	_ITaskBar_UpdateTBButton($g_hTblStart, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblStop, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblPause, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblResume, $THBF_DISABLED)

	; hide attack buttons if show
	GUICtrlSetState($g_hBtnAttackNowDB, $GUI_HIDE)
	GUICtrlSetState($g_hBtnAttackNowLB, $GUI_HIDE)
	GUICtrlSetState($g_hBtnAttackNowTS, $GUI_HIDE)
	HideShields(False)
	;GUICtrlSetState($g_hLblVersion, $GUI_SHOW)
	$g_bBtnAttackNowPressed = False

	; update try items
	TrayItemSetText($g_hTiStartStop, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Start", "Start bot"))
	TrayItemSetState($g_hTiPause, $TRAY_DISABLE)

	SetLogCentered(" Bot Stop ", Default, $COLOR_ACTION)
	If Not $g_bSearchMode Then
		If Not $g_bBotPaused Then $g_iTimePassed += Int(__TimerDiff($g_hTimerSinceStarted))
		If ProfileSwitchAccountEnabled() And Not $g_bBotPaused Then $g_aiRunTime[$g_iCurAccount] += Int(__TimerDiff($g_ahTimerSinceSwitched[$g_iCurAccount]))
		;AdlibUnRegister("SetTime")
		;$g_bRestart = True

		If $g_hLogFile <> 0 Then
			FileClose($g_hLogFile)
			$g_hLogFile = 0
		EndIf

		If $g_hAttackLogFile <> 0 Then
			FileClose($g_hAttackLogFile)
			$g_hAttackLogFile = 0
		EndIf
	Else
		$g_bSearchMode = False
	EndIf

	; Ends ObjEvents for the Autoit objects errors
	__ObjEventEnds()

	ReduceBotMemory()
	If $g_iBotAction <> $eBotClose Then $g_iBotAction = $eBotNoAction
	RunControlReportStopComplete()
	FuncReturn()
EndFunc   ;==>BotStop

Func BotSearchMode()
	FuncEnter(BotSearchMode)
	$g_bSearchMode = True
	$g_bRestart = False
	$g_bIsClientSyncError = False
	If $g_iFirstRun = 1 Then $g_iFirstRun = -1
	btnStart()
	checkMainScreen(False)
	If _Sleep(100) Then Return FuncReturn()
	$g_aiCurrentLoot[$eLootTrophy] = getTrophyMainScreen($aTrophies[0], $aTrophies[1]) ; get OCR to read current Village Trophies
	If _Sleep(100) Then Return FuncReturn()
	CheckIfArmyIsReady()
	ClickAway()
	If _Sleep(100) Then Return FuncReturn()
	If IsSearchModeActive($DB) Or IsSearchModeActive($LB) Then
		If _Sleep(100) Then Return FuncReturn()
		PrepareSearch()
		If $g_bOutOfGold Then Return ; Check flag for enough gold to search
		If $g_bRestart Then
			CleanSuperchargeTemplates()
			Return
		EndIf
		If _Sleep(1000) Then Return FuncReturn()
		VillageSearch()
		If $g_bOutOfGold Then Return ; Check flag for enough gold to search
		If _Sleep(100) Then Return FuncReturn()
		CleanSuperchargeTemplates()
	Else
		SetLog("Your Army is not prepared, check the Attack/train options")
	EndIf
	btnStop()
	FuncReturn()
EndFunc   ;==>BotSearchMode
