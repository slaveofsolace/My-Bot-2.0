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
	; Publish the terminal Start outcome before btnStop() can tear down the backend/planner process.
	; Otherwise the web UI can remain stuck on the earlier accepted command after a controlled reject.
	RunControlReportStartOutcome(False, $sReason)
	; A general Start owns the shared bot slot before emulator or managed-engine work. Release it at
	; the rejection linearization point instead of waiting for the later Stop action to be dispatched.
	; Terminal one-shot routes hold the same slot in their wrapper, so this is also a harmless no-op
	; after that wrapper has already released it.
	LockBotSlot(False)
	If $g_iBotAction <> $eBotClose Then btnStop()
	ReleaseExactAndroidInstanceLock()
	Return False
EndFunc   ;==>_BotStartReject

Func _BotOpenCollectorsReject($sReason, $sOutcome = "rejected")
	If $sReason = "" Then $sReason = "Template-free collectors were not started"
	RunExecutionCancelPrepared($sReason)
	RunControlReportOneShotOutcome($sOutcome, $sReason)
	Return False
EndFunc   ;==>_BotOpenCollectorsReject

Func _BotOpenDailyRewardFail($sReason)
	If $sReason = "" Then $sReason = "Template-free Daily Reward failed"
	RunExecutionCancelPrepared($sReason)
	RunControlReportOneShotOutcome("failed", $sReason)
	Return False
EndFunc   ;==>_BotOpenDailyRewardFail

Func _BotOpenHomeRequireExactBlueStacks(ByRef $sReason)
	$sReason = ""
	If BlueStacks5ExactInstanceWindowHung() Then
		$sReason = "The exact BlueStacks 5 instance is not responding; use Recovery and restart that instance before retrying"
		Return False
	EndIf
	If WinGetAndroidHandle() = 0 Then
		$sReason = "The exact BlueStacks 5 instance is not already running"
		Return False
	EndIf
	Return True
EndFunc   ;==>_BotOpenHomeRequireExactBlueStacks

; A normal Start owns emulator and game startup. The exact-attachment gate remains fail-closed for
; a hung or foreign window, but an absent verified BlueStacks 5 instance is launched through the
; bounded, stop-aware adapter before the one-shot Home route continues.
Func _BotOpenHomeEnsureExactBlueStacks(ByRef $sReason)
	$sReason = ""
	Local $sAcceptanceToken = ""
	Local $sAcceptanceReason = ""
	Local $iAcceptanceMode = BlueStacks5AcceptanceStopBeforeHomeContract($sAcceptanceReason, $sAcceptanceToken)
	If $iAcceptanceMode < 0 Then
		$sReason = $sAcceptanceReason
		Return False
	EndIf
	Local $bAlreadyAttached = _BotOpenHomeRequireExactBlueStacks($sReason)
	If $bAlreadyAttached Then
		; Acceptance must prove one fresh, product-owned Pie64 generation. Reject an inherited window
		; before any framebuffer recognition or reviewed startup-overlay input can run.
		If $iAcceptanceMode = 1 Then
			$sReason = "The stop-before-Home acceptance barrier requires a fresh product-owned Pie64 launch"
			Return False
		EndIf
		; A BlueStacks window alone does not prove that Clash is running. Avoid relaunching a game that
		; is already at Home or a reviewed startup overlay; otherwise issue the one bounded activity start.
		If OpenHomeCollectorsProveHome() Or OpenHomeDailyRewardOverlayReady() Or _
				OpenHomeDailyRewardClaimedOverlayReady() Or OpenHomeInactivityReloadDialogReady() Or _
				OpenHomeWelcomeBackOverlayReady() Then Return True
	ElseIf $sReason <> "The exact BlueStacks 5 instance is not already running" Then
		Return False
	EndIf
	If RunControlStopRequested() Then
		$sReason = "BlueStacks and Clash of Clans launch cancelled before initialization"
		Return False
	EndIf

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	Local $sLaunchReason = ""
	RunEventLogGameLaunchStarted()
	If Not LaunchBlueStacks5CoCOnly($sLaunchReason) Then
		$sReason = $sLaunchReason = "" ? "BlueStacks and Clash of Clans launch failed" : $sLaunchReason
		If RunControlStopRequested() Or Not $g_bRunState Then
			RunEventLogGameLaunchCancelled($sReason)
		Else
			RunEventLogGameLaunchFailed($sReason)
		EndIf
		Return False
	EndIf
	If RunControlStopRequested() Or Not $g_bRunState Then
		$sReason = "BlueStacks and Clash of Clans launch cancelled after passive game-ready proof"
		RunEventLogGameLaunchCancelled($sReason)
		Return False
	EndIf
	If Not _BotOpenHomeRequireExactBlueStacks($sReason) Then Return False
	$sReason = $sLaunchReason
	RunEventLogGameLaunchPassed($sReason)
	Return True
EndFunc   ;==>_BotOpenHomeEnsureExactBlueStacks

; Bootstrap the configured emulator and the Clash activity before managed Android binding. BlueStacks
; keeps its stronger exact-instance/passive-Home adapter. Other planner-supported emulators use their
; existing configured Open adapter, then one bounded ADB activity launch: no Home-button input,
; shared-preference push, restart/retry loop, recognition, or gameplay actuator is entered here.
Func _BotEnsureConfiguredAndroidAndGame(ByRef $sReason)
	$sReason = ""
	If $g_sAndroidEmulator = "BlueStacks5" Then Return _BotOpenHomeEnsureExactBlueStacks($sReason)

	Switch $g_sAndroidEmulator
		Case "MEmu", "LDPlayer9", "Mumu"
		Case Else
			$sReason = "The configured emulator " & $g_sAndroidEmulator & " has no bounded cold-start adapter"
			Return False
	EndSwitch
	If RunControlStopRequested() Or Not $g_bRunState Then
		$sReason = $g_sAndroidEmulator & " and Clash of Clans launch cancelled before initialization"
		Return False
	EndIf
	If Not InitAndroid() Then
		$sReason = "The configured " & $g_sAndroidEmulator & " adapter could not be initialized"
		Return False
	EndIf

	Local $bStartedEmulator = False
	If WinGetAndroidHandle() = 0 Then
		If Not OpenAndroid(False, True) Then
			$sReason = "The configured " & $g_sAndroidEmulator & " instance did not accept the bounded launch request"
			Return False
		EndIf
		$bStartedEmulator = True
	EndIf
	If RunControlStopRequested() Or Not $g_bRunState Then
		$sReason = $g_sAndroidEmulator & " and Clash of Clans launch cancelled before the game activity"
		Return False
	EndIf
	If WinGetAndroidHandle() = 0 Or Not AndroidControlAvailable() Then
		$sReason = "The configured " & $g_sAndroidEmulator & " instance has no owned window/control surface"
		Return False
	EndIf
	If Not StringRegExp($g_sAndroidGamePackage, "^[A-Za-z0-9._]+$") Or _
			Not StringRegExp($g_sAndroidGameClass, "^[A-Za-z0-9._]+$") Then
		$sReason = "The configured Clash of Clans activity identity is unsafe"
		Return False
	EndIf
	If Not ConnectAndroidAdb(False, True, 15000) Then
		$sReason = "ADB did not bind to the configured " & $g_sAndroidEmulator & " instance"
		Return False
	EndIf
	AndroidAdbLaunchShellInstance($g_bRunState, False)
	If @error Then
		$sReason = "ADB shell ownership could not be established for the configured " & $g_sAndroidEmulator & " instance"
		Return False
	EndIf

	Local $sLaunchOutput = AndroidAdbSendShellCommand("am start -n " & $g_sAndroidGamePackage & "/" & _
			$g_sAndroidGameClass, 15000, $g_bRunState, False)
	If @error Or StringInStr($sLaunchOutput, "Error:") Or StringInStr($sLaunchOutput, "Exception") Then
		$sReason = "Clash of Clans did not accept the one bounded Android activity launch"
		Return False
	EndIf

	Local $hGameTimer = __TimerInit()
	While __TimerDiff($hGameTimer) <= 90000
		If RunControlStopRequested() Or Not $g_bRunState Then
			$sReason = $g_sAndroidEmulator & " and Clash of Clans launch cancelled while waiting for the game process"
			Return False
		EndIf
		; The inherited generic game-PID observer increments a miss counter and eventually restarts the bot.
		; This cold-start observer must be side-effect free: read the exact validated package PID from
		; the already-owned ADB shell and accept only a numeric pidof response.
		Local $sGamePids = AndroidAdbSendShellCommand("pidof " & $g_sAndroidGamePackage, 3000, $g_bRunState, False)
		Local $iPidReadError = @error
		$sGamePids = StringStripWS($sGamePids, $STR_STRIPLEADING + $STR_STRIPTRAILING)
		If $iPidReadError = 0 And StringRegExp($sGamePids, "^[0-9]+([ \t]+[0-9]+)*$") Then
			$sReason = $g_sAndroidEmulator & " and Clash of Clans launched; emulator_started=" & _
					($bStartedEmulator ? "true" : "false")
			Return True
		EndIf
		If _Sleep(1000) Then
			$sReason = $g_sAndroidEmulator & " and Clash of Clans launch cancelled while waiting for the game process"
			Return False
		EndIf
	WEnd
	$sReason = "Clash of Clans did not expose its process before the bounded deadline on " & $g_sAndroidEmulator
	Return False
EndFunc   ;==>_BotEnsureConfiguredAndroidAndGame

; Every terminal Home route can issue account-mutating input. Serialize the whole prepared route on
; the same cross-process ActiveBot slot as a general run, but keep invalid/non-route rejection outside
; the lock. Route functions return to this wrapper rather than returning from BotStart directly, so
; the slot is released after every completed, failed, cancelled, or unavailable terminal outcome.
Func _BotStartRunOneShot($iRoute, ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Terminal Home route cancelled before waiting for the bot slot", "cancelled")
	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	LockBotSlot(True)
	If Not $g_bRunState Or (Not $g_bBotLaunchOption_NoBotSlot And Not LockBotSlot(Default)) Then
		LockBotSlot(False)
		Return _BotOpenCollectorsReject("Terminal Home route cancelled while waiting for the bot slot", "cancelled")
	EndIf
	If Not RunExecutionApplyPreparedTransport($sStartError) Then
		LockBotSlot(False)
		Return _BotOpenCollectorsReject($sStartError)
	EndIf
	If Not AcquireExactAndroidInstanceLock($g_sAndroidEmulator, $g_sAndroidInstance, $sStartError) Then
		LockBotSlot(False)
		Return _BotOpenCollectorsReject($sStartError, $g_bRunState ? "rejected" : "cancelled")
	EndIf

	Local $bResult = False
	Switch $iRoute
		Case 1
			$bResult = _BotStartOpenHomeCollectors($sStartError)
		Case 2
			$bResult = _BotStartOpenHomeLootCart($sStartError)
		Case 3
			$bResult = _BotStartOpenDailyReward($sStartError)
		Case 4
			$bResult = _BotStartOpenHomeTreasury($sStartError)
		Case 5
			$bResult = _BotStartOpenClanRequest($sStartError)
		Case 6
			$bResult = _BotStartExactRecipeTraining($sStartError)
		Case 7
			$bResult = _BotStartOpenBuilderCollectors($sStartError)
		Case 8
			$bResult = _BotStartRegularBattleEntryProof($sStartError)
		Case 9
			$bResult = _BotStartBuilderBattleEntryProof($sStartError)
		Case 10
			$bResult = _BotStartRegularBattleScout($sStartError)
		Case Else
			$bResult = _BotOpenCollectorsReject("Terminal Home/Builder route selection changed before execution")
	EndSwitch
	ReleaseExactAndroidInstanceLock()
	LockBotSlot(False)
	Return $bResult
EndFunc   ;==>_BotStartRunOneShot

; Run one collectors-only pass without loading the restricted managed image engine. Start launches
; the exact plan-bound BlueStacks 5 instance and Clash of Clans when absent; the route never reboots,
; resizes, zooms, authenticates, searches, trains, donates, upgrades, or spends.
Func _BotStartOpenHomeCollectors(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free collectors cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then Return _BotOpenCollectorsReject("The current screen is not the proven Home Village")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free collectors cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Template-free Home collectors started")
	RunEventLogMaintenanceCollectorsStarted()

	Local $bCollected = OpenHomeCollectorsCollectOnePass(1)
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
			Case 6
				$sStartError &= ": passive no-gem guard recognized a gem surface; no further input was issued"
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

; Run one Builder Base collection pass without loading the restricted managed image engine. The route
; may start from Home Village or an already-open Builder Base, but it must finish by re-proving Home.
Func _BotStartOpenBuilderCollectors(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Builder Base collectors cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not BuilderMaintenanceRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
			Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
			Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	Local $bReloadIssued = OpenHomeInactivityReloadIssue(False)
	If @error Then Return _BotOpenCollectorsReject("Inactivity reload dialog could not be handled before Builder collection")
	If $bReloadIssued And Not OpenHomeStartupRecoveryWait(False) Then _
			Return _BotOpenCollectorsReject("Clash reload did not reach a recognized Home or startup overlay before Builder collection")
	If Not OpenHomeCollectorsProveHome() And Not OpenBuilderBaseCollectorsProveBuilder() Then _
			Return _BotOpenCollectorsReject("Neither Home Village nor Builder Base could be proven before Builder collection")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Builder Base collectors cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Template-free Builder Base collectors started")
	RunEventLogBuilderMaintenanceStarted()

	Local $bCollected = OpenBuilderBaseCollectorsCollectOnePass(2)
	Local $iCollectError = @error
	Local $iCollectorClicks = @extended
	If Not $bCollected Then
		If $iCollectError = 2 Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Template-free Builder Base collectors stopped")
			Return False
		EndIf
		$sStartError = "Template-free Builder Base collectors failed"
		Switch $iCollectError
			Case 1
				$sStartError &= ": starting village state was not proven"
			Case 3
				$sStartError &= ": Builder Base was not proven before input"
			Case 4
				$sStartError &= ": the selected Builder resource click was not accepted"
			Case 5
				$sStartError &= ": Builder Base did not become visible after the switch"
			Case 6
				$sStartError &= ": passive no-gem guard recognized a gem surface; no further input was issued"
			Case 7
				$sStartError &= ": Home Village was not re-proven after Builder Base collection; inputs will not be retried"
			Case Else
				$sStartError &= ": the bounded adapter returned an unknown outcome"
		EndSwitch
		RunEventLogBuilderMaintenanceUnconfirmed($iCollectorClicks, $sStartError)
		RunEventLogRunFailed("builder", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	RunEventLogBuilderMaintenanceHomeVerified($iCollectorClicks)
	If $iCollectorClicks > 0 Then
		RunEventLogBuilderMaintenanceCompleted($iCollectorClicks)
	Else
		RunEventLogBuilderMaintenanceNoneActionable()
	EndIf
	Local $sReason = $iCollectorClicks > 0 ? "builder-collectors-open-complete" : "builder-collectors-open-none-actionable"
	RunExecutionComplete($sReason)
	Local $sMessage = "Template-free Builder Base collectors completed; builder_resource_clicks=" & $iCollectorClicks
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartOpenBuilderCollectors

Func _BotStartRegularBattleEntryProof(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Regular battle entry proof cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not RegularBattleEntryRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
			Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
			Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then
		Local $bReloadIssued = OpenHomeInactivityReloadIssue(False)
		If $bReloadIssued Then
			If Not OpenHomeStartupRecoveryWait(False) Then _
					Return _BotOpenCollectorsReject("Startup recovery did not reach Home before Regular battle entry proof")
		EndIf
	EndIf
	If Not OpenHomeCollectorsProveHome() Then _
			Return _BotOpenCollectorsReject("Home Village was not proven before Regular battle entry proof")
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Regular battle entry proof started")
	Local $bResult = RegularBattleEntryRouteExecute()
	If $bResult Then
		Local $sMessage = RunExecutionMessage()
		If $sMessage = "" Then $sMessage = "Completed Regular battle entry proof"
		RunControlReportOneShotOutcome("completed", $sMessage)
		SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	EndIf
	Return $bResult
EndFunc   ;==>_BotStartRegularBattleEntryProof

Func _BotStartRegularBattleScout(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Regular battle scout cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not RegularBattleEntryRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
			Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
			Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then
		Local $bReloadIssued = OpenHomeInactivityReloadIssue(False)
		If $bReloadIssued Then
			If Not OpenHomeStartupRecoveryWait(False) Then _
					Return _BotOpenCollectorsReject("Startup recovery did not reach Home before Regular battle scout")
		EndIf
	EndIf
	If Not OpenHomeCollectorsProveHome() Then _
			Return _BotOpenCollectorsReject("Home Village was not proven before Regular battle scout")
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Regular battle scout started")
	Local $bResult = RegularBattleScoutRouteExecute()
	If $bResult Then
		Local $sMessage = RunExecutionMessage()
		If $sMessage = "" Then $sMessage = "Completed Regular battle scout"
		RunControlReportOneShotOutcome("completed", $sMessage)
		SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	EndIf
	Return $bResult
EndFunc   ;==>_BotStartRegularBattleScout

Func _BotStartBuilderBattleEntryProof(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Builder battle entry proof cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not BuilderBattleEntryRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
			Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
			Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	Local $bReloadIssued = OpenHomeInactivityReloadIssue(False)
	If @error Then Return _BotOpenCollectorsReject("Inactivity reload dialog could not be handled before Builder battle entry proof")
	If $bReloadIssued And Not OpenHomeStartupRecoveryWait(False) Then _
			Return _BotOpenCollectorsReject("Clash reload did not reach a recognized Home or startup overlay before Builder battle entry proof")
	If Not OpenHomeCollectorsProveHome() And Not OpenBuilderBaseCollectorsProveBuilder() Then _
			Return _BotOpenCollectorsReject("Neither Home Village nor Builder Base could be proven before Builder battle entry proof")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Builder battle entry proof cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Builder battle entry proof started")
	Local $bResult = BuilderBattleEntryRouteExecute()
	If $bResult Then
		Local $sMessage = RunExecutionMessage()
		If $sMessage = "" Then $sMessage = "Completed Builder battle entry proof"
		RunControlReportOneShotOutcome("completed", $sMessage)
		SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	EndIf
	Return $bResult
EndFunc   ;==>_BotStartBuilderBattleEntryProof

Func _BotStartOpenHomeLootCart(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Loot Cart cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then Return _BotOpenCollectorsReject("The current screen is not the proven Home Village")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Loot Cart cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Template-free Loot Cart pass started")
	RunEventLogMaintenanceLootCartStarted()
	If Not OpenHomeClearSelectedActionPanel() Then
		Local $iClearError = @error
		$sStartError = $iClearError = 6 ? _
				"Passive no-gem guard recognized a gem surface before clearing the selected Home object; no Loot Cart input was issued" : _
				"The selected Home object panel could not be cleared before Loot Cart recognition"
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	Local $oLootCart = LootCartRouteRunAdapter("OpenHomeLootCartDetectCue", "OpenHomeLootCartIssueOpen", _
			"OpenHomeLootCartDetectCollect", "OpenHomeLootCartIssueCollect", "_LootCartLiveStopRequested", _
			"OpenHomeLootCartProveHome")
	If Not IsObj($oLootCart) Then
		$sStartError = "Template-free Loot Cart returned no bounded outcome"
	Else
		Local $sLootCartState = String($oLootCart.Item("state"))
		If $sLootCartState = $LOOT_CART_OUTCOME_CANCELLED Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Template-free Loot Cart stopped")
			Return False
		EndIf
		If Not $oLootCart.Item("home_proven") Then
			RunEventLogMaintenanceLootCartUnconfirmed($oLootCart.Item("cart_issued"), _
					$oLootCart.Item("collect_issued"), $oLootCart.Item("detail") & "; Home Village was not re-proven")
			$sStartError = "Template-free Loot Cart could not re-prove Home; inputs will not be retried"
		Else
			RunEventLogMaintenanceLootCartHomeVerified($sLootCartState)
			Switch $sLootCartState
				Case $LOOT_CART_OUTCOME_COLLECT_ISSUED
					; The accepted-input callback already emitted the irreversible receipt.
				Case $LOOT_CART_OUTCOME_UNAVAILABLE
					RunEventLogMaintenanceLootCartUnavailable($oLootCart.Item("cart_state"))
				Case $LOOT_CART_OUTCOME_UNCONFIRMED
					RunEventLogMaintenanceLootCartUnconfirmed($oLootCart.Item("cart_issued"), _
							$oLootCart.Item("collect_issued"), $oLootCart.Item("detail"))
					$sStartError = $oLootCart.Item("detail") & "; Loot Cart inputs will not be retried"
				Case Else
					$sStartError = "Template-free Loot Cart returned an unknown terminal state"
			EndSwitch
		EndIf
	EndIf

	If $sStartError <> "" Then
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	RunEventLogMaintenanceHomeVerified(0, "disabled", $sLootCartState, "disabled")
	Local $sReason = $sLootCartState = $LOOT_CART_OUTCOME_COLLECT_ISSUED ? "home-loot-cart-complete" : "home-loot-cart-none-actionable"
	RunExecutionComplete($sReason)
	Local $sMessage = "Template-free Loot Cart completed; state=" & $sLootCartState
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartOpenHomeLootCart

; Run a Treasury pass on the exact BlueStacks framebuffer without entering the managed engine or
; inherited image recognizer. This build proves the empty/not-full terminal state and closes the exact
; Treasury window; an actionable/full state remains fail-closed until Collect/confirm proof is reviewed.
Func _BotStartOpenHomeTreasury(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Treasury cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then Return _BotOpenCollectorsReject("The current screen is not the proven Home Village")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Treasury cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Template-free Treasury pass started")
	RunEventLogMaintenanceTreasuryStarted()

	Local $oTreasury = TreasuryRouteRunAdapter("OpenHomeTreasuryDetectCastle", "OpenHomeTreasuryIssueCastle", _
			"OpenHomeTreasuryDetectEntry", "OpenHomeTreasuryIssueEntry", "OpenHomeTreasuryDetectCollect", _
			"OpenHomeTreasuryIssueCollect", "OpenHomeTreasuryDetectConfirm", "OpenHomeTreasuryIssueConfirm", _
			"_OpenHomeTreasuryStopRequested", "OpenHomeTreasuryCleanup")
	If Not IsObj($oTreasury) Then
		$sStartError = "Template-free Treasury returned no bounded outcome"
	Else
		Local $sTreasuryState = String($oTreasury.Item("state"))
		If $sTreasuryState = $TREASURY_OUTCOME_CANCELLED Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Template-free Treasury stopped")
			Return False
		EndIf
		If Not $oTreasury.Item("home_proven") Then
			RunEventLogMaintenanceTreasuryUnconfirmed($oTreasury.Item("collect_issued"), _
					$oTreasury.Item("confirm_issued"), $oTreasury.Item("detail") & "; Home Village was not re-proven")
			$sStartError = "Template-free Treasury could not re-prove Home; inputs will not be retried"
		Else
			RunEventLogMaintenanceTreasuryHomeVerified($sTreasuryState)
			Switch $sTreasuryState
				Case $TREASURY_OUTCOME_CONFIRM_ISSUED
					; The accepted confirmation callback already emitted the irreversible receipt.
				Case $TREASURY_OUTCOME_UNAVAILABLE
					RunEventLogMaintenanceTreasuryUnavailable($oTreasury.Item("detail"))
				Case $TREASURY_OUTCOME_UNCONFIRMED
					RunEventLogMaintenanceTreasuryUnconfirmed($oTreasury.Item("collect_issued"), _
							$oTreasury.Item("confirm_issued"), $oTreasury.Item("detail"))
					$sStartError = $oTreasury.Item("detail") & "; Treasury inputs will not be retried"
				Case Else
					$sStartError = "Template-free Treasury returned an unknown terminal state"
			EndSwitch
		EndIf
	EndIf

	If $sStartError <> "" Then
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	RunEventLogMaintenanceHomeVerified(0, "disabled", "disabled", $sTreasuryState)
	Local $sReason = $sTreasuryState = $TREASURY_OUTCOME_CONFIRM_ISSUED ? "home-treasury-complete" : "home-treasury-none-actionable"
	RunExecutionComplete($sReason)
	Local $sMessage = "Template-free Treasury completed; state=" & $sTreasuryState
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartOpenHomeTreasury

; Run the startup Daily Reward on the already-running exact BlueStacks instance. Recognition and
; input are framebuffer/ADB-only; no managed engine, ImgLoc, OCR, authentication, or generic obstacle
; handler is entered. The only irreversible input is one freshly re-proven Claim button.
Func _BotStartOpenDailyReward(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Template-free Daily Reward cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not $g_bAndroidAdbClick Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/ADB input surface is not available")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Template-free Daily Reward pass started")
	RunEventLogMaintenanceDailyRewardStarted()
	If Not OpenHomeClearSelectedActionPanel() Then
		Local $iClearError = @error
		$sStartError = $iClearError = 6 ? _
				"Passive no-gem guard recognized a gem surface before clearing the selected Home object; no Daily Reward input was issued" : _
				"The selected Home object panel could not be cleared before Daily Reward recognition"
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		Return _BotOpenDailyRewardFail($sStartError)
	EndIf

	Local $bReloadIssued = OpenHomeInactivityReloadIssue()
	Local $iReloadError = @error
	If $bReloadIssued Then
		SetLog("Run Planner: Daily Reward inactivity dialog recognized; reload issued before Claim recognition", $COLOR_INFO)
		If Not OpenHomeStartupRecoveryWait() Then
			$sStartError = "Daily Reward reload recovery did not reach Home or a reviewed startup overlay; error=" & @error
			RunExecutionRecordDailyReward("reload-unconfirmed", 0, False, $sStartError)
			RunEventLogMaintenanceDailyRewardUnconfirmed(False, $sStartError)
			RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
			Return _BotOpenDailyRewardFail($sStartError)
		EndIf
	ElseIf $iReloadError <> 0 Then
		$sStartError = $iReloadError = 6 ? _
				"Passive no-gem guard recognized a gem surface before Daily Reward reload; no input was issued" : _
				"Daily Reward inactivity reload recovery was rejected; error=" & $iReloadError
		RunExecutionRecordDailyReward("reload-rejected", 0, False, $sStartError)
		RunEventLogMaintenanceDailyRewardUnconfirmed(False, $sStartError)
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		Return _BotOpenDailyRewardFail($sStartError)
	EndIf

	Local $aClaim[2]
	Local $iClaimButtons = OpenHomeDailyRewardCaptureClaim($aClaim)
	If @error Then Return _BotOpenDailyRewardFail("The Daily Reward framebuffer could not be captured")
	Local $bOverlayReady = OpenHomeDailyRewardOverlayReady()
	If RunControlStopRequested() Then Return _BotOpenDailyRewardFail("Template-free Daily Reward cancelled before execution")

	If Not $bOverlayReady Then
		RunExecutionRecordDailyReward("not-seen", 0, False, "The startup Daily Reward overlay was not present")
		RunEventLogMaintenanceDailyRewardUnavailable("not-seen")
		If Not OpenHomeCollectorsProveHome() Then
			$sStartError = "Daily Reward was not present and the current screen was not the proven Home Village"
			RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
			Return _BotOpenDailyRewardFail($sStartError)
		EndIf
		RunEventLogMaintenanceHomeVerified(0, "not-seen", "disabled", "disabled")
		RunExecutionComplete("home-daily-reward-none-actionable")
		RunControlReportOneShotOutcome("completed", "Template-free Daily Reward completed; state=not-seen; claim_attempts=0")
		Return True
	EndIf

	If $iClaimButtons = 0 Then
		RunExecutionRecordDailyReward("none-actionable", 0, False, "Daily Reward overlay had no actionable Claim button")
		RunEventLogMaintenanceDailyRewardUnavailable("none-actionable")
		Local $bNoClaimCloseIssued = False
		If Not OpenHomeDailyRewardCloseAndProveHome($bNoClaimCloseIssued) Then
			$sStartError = "Daily Reward had no Claim button and Home Village was not re-proven; close_issued=" & String($bNoClaimCloseIssued)
			RunEventLogMaintenanceDailyRewardUnconfirmed(False, $sStartError)
			RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
			Return _BotOpenDailyRewardFail($sStartError)
		EndIf
		RunEventLogMaintenanceHomeVerified(0, "none-actionable", "disabled", "disabled")
		RunExecutionComplete("home-daily-reward-none-actionable")
		RunControlReportOneShotOutcome("completed", "Template-free Daily Reward completed; state=none-actionable; claim_attempts=0; close_issued=" & String($bNoClaimCloseIssued))
		Return True
	EndIf

	If $iClaimButtons <> 1 Then
		$sStartError = "Daily Reward recognition was ambiguous; claim_buttons=" & $iClaimButtons
		RunExecutionRecordDailyReward("ambiguous", 0, False, $sStartError)
		RunEventLogMaintenanceDailyRewardUnconfirmed(False, $sStartError)
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		Return _BotOpenDailyRewardFail($sStartError)
	EndIf

	If RunControlStopRequested() Or Not $g_bRunState Then
		RunExecutionComplete("stopped")
		RunControlReportOneShotOutcome("stopped", "Template-free Daily Reward stopped before Claim")
		Return False
	EndIf
	Local $bClaimIssued = OpenHomeDailyRewardIssueClaim($aClaim[0], $aClaim[1])
	Local $iClaimError = @error
	If Not $bClaimIssued Then
		If $iClaimError = 2 Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Template-free Daily Reward stopped before Claim")
			Return False
		EndIf
		$sStartError = $iClaimError = 6 ? _
				"Passive no-gem guard recognized a gem surface; no Daily Reward Claim input was issued" : _
				"The one Daily Reward Claim attempt was rejected after fresh recognition"
		RunExecutionRecordDailyReward("click-rejected", 1, False, $sStartError)
		RunEventLogMaintenanceDailyRewardUnconfirmed(False, $sStartError)
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		Return _BotOpenDailyRewardFail($sStartError)
	EndIf

	RunExecutionRecordDailyReward("click-issued", 1, True, _
			"One Claim input was accepted; no Okay, Confirm, sell, or gem-conversion input was attempted")
	RunEventLogMaintenanceDailyRewardClickIssued(1)
	Local $bCloseIssued = False
	If Not OpenHomeDailyRewardCloseAndProveHome($bCloseIssued) Then
		$sStartError = "Daily Reward Claim was issued but Home Village was not re-proven; the Claim will not be retried"
		RunEventLogMaintenanceDailyRewardUnconfirmed(True, $sStartError)
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		Return _BotOpenDailyRewardFail($sStartError)
	EndIf

	RunEventLogMaintenanceHomeVerified(0, "click-issued", "disabled", "disabled")
	RunExecutionComplete("home-daily-reward-complete")
	Local $sMessage = "Template-free Daily Reward completed; claim_attempts=1; close_issued=" & String($bCloseIssued)
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartOpenDailyReward

; Run the request-only terminal route on the already-running exact BlueStacks instance. Requesting
; troops does not require the mixed-mode attack engine; keeping this route ahead of MBRFuncInitialize
; prevents an unrelated CLR startup failure from turning a bounded request into a 90-second stall.
Func _BotStartOpenClanRequest(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Clan request cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not ClanRequestRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then Return _BotOpenCollectorsReject("The current screen is not the proven Home Village")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Clan request cancelled before execution", "cancelled")

	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Clan request-only pass started")
	RunEventLogClanRequestStarted()

	Local $oOutcome = ClanRequestRouteRunAdapter("OpenClanRequestOpenArmyOverview", "OpenClanRequestDetectState", _
			"OpenClanRequestOpenDialog", "OpenClanRequestIssueSend", "_ClanRequestLiveStopRequested", _
			"OpenClanRequestCloseAndProveHome")
	If Not IsObj($oOutcome) Then
		$sStartError = "Clan request adapter returned no bounded outcome"
	Else
		Local $sOutcome = String($oOutcome.Item("state"))
		If $sOutcome = $CLAN_REQUEST_OUTCOME_CANCELLED Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Clan request stopped")
			Return False
		EndIf
		If Not $oOutcome.Item("home_proven") Then
			RunEventLogClanRequestUnconfirmed($oOutcome.Item("send_issued"), _
					$oOutcome.Item("detail") & "; Home Village was not re-proven")
			$sStartError = "Home Village could not be re-proven after the request dialog; Send will not be retried"
		Else
			RunEventLogClanRequestHomeVerified($sOutcome)
			Switch $sOutcome
				Case $CLAN_REQUEST_OUTCOME_COMMITTED
					RunEventLogClanRequestCommitted()
				Case $CLAN_REQUEST_OUTCOME_UNAVAILABLE
					RunEventLogClanRequestUnavailable($oOutcome.Item("before_state"))
				Case $CLAN_REQUEST_OUTCOME_UNCONFIRMED
					RunEventLogClanRequestUnconfirmed($oOutcome.Item("send_issued"), $oOutcome.Item("detail"))
					$sStartError = $oOutcome.Item("detail") & "; Send will not be retried"
				Case Else
					$sStartError = "Clan request adapter returned an unknown terminal state"
			EndSwitch
		EndIf
	EndIf

	If $sStartError <> "" Then
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	Local $sReason = $sOutcome = $CLAN_REQUEST_OUTCOME_COMMITTED ? "clan-request-committed" : "clan-request-unavailable"
	RunExecutionComplete($sReason)
	Local $sMessage = $sOutcome = $CLAN_REQUEST_OUTCOME_COMMITTED ? _
			"Clan request committed and Home Village re-proven" : "Clan request unavailable; no Send input was issued"
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartOpenClanRequest

Func _ExactTrainingLiveStopRequested()
	Return RunControlStopRequested() Or Not $g_bRunState
EndFunc   ;==>_ExactTrainingLiveStopRequested

; The route is wired before saved-recipe framebuffer fixtures exist. It must first prove the
; task-owned Army Overview frame, then return the reviewed unavailable observation: no inherited
; training routine, no queue input, no retry, and a visible Activity/control receipt until a
; clean-room recognizer supplies recipe-ready.
Func _ExactTrainingLiveDetect($sPhase)
	If Not OpenClanRequestArmyOverviewReady(False) Then Return SetError(2, 0, 0)
	Return ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_UNAVAILABLE)
EndFunc   ;==>_ExactTrainingLiveDetect

Func _ExactTrainingLiveIssueQueue($iX, $iY)
	Return SetError(1, 0, False)
EndFunc   ;==>_ExactTrainingLiveIssueQueue

Func _BotStartExactRecipeTraining(ByRef $sStartError)
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Exact saved-recipe training cancelled before attachment", "cancelled")
	If Not RunExecutionApplyPrepared($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	Local $oIntent = RunExecutionPreparedIntent()
	If Not IsObj($oIntent) Or Not ExactRecipeTrainingRouteAccountMatches($oIntent, $g_sProfileCurrentName) Then _
		Return _BotOpenCollectorsReject("The active profile no longer matches the account bound at Start")
	Local $sAttachmentError = ""
	If Not _BotOpenHomeEnsureExactBlueStacks($sAttachmentError) Then Return _BotOpenCollectorsReject($sAttachmentError)
	If Not $g_bAndroidAdbScreencap Or Not AndroidControlAvailable() Or _
			Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then _
		Return _BotOpenCollectorsReject("The exact BlueStacks 5 framebuffer/control surface is not available")
	If Not OpenHomeCollectorsProveHome() Then Return _BotOpenCollectorsReject("The current screen is not the proven Home Village")
	If RunControlStopRequested() Then Return _BotOpenCollectorsReject("Exact saved-recipe training cancelled before execution", "cancelled")

	Local $sRecipeId = ExactRecipeTrainingRouteRecipeId($oIntent)
	Local $sRecipeDigest = ExactRecipeTrainingRouteRecipeDigest($oIntent)
	Local $iMaxQueueUnits = ExactRecipeTrainingRouteMaxQueueUnits($oIntent)
	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not RunExecutionBegin($sStartError) Then Return _BotOpenCollectorsReject($sStartError)
	RunControlReportStartOutcome(True, "Exact saved-recipe training pass started")
	RunEventLogExactTrainingStarted($sRecipeId, $iMaxQueueUnits)
	If Not OpenClanRequestOpenArmyOverview($NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY) Then
		$sStartError = $g_bNoPremiumPolicyTripped ? RunExecutionMessage() : _
				"Army Overview did not open for exact saved-recipe training; no queue input was issued"
		If $sStartError = "" Then $sStartError = "Exact saved-recipe training failed before Army Overview opened"
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	Local $oOutcome = ExactRecipeTrainingRouteRunAdapter($sRecipeId, $sRecipeDigest, $iMaxQueueUnits, _
		"_ExactTrainingLiveDetect", "_ExactTrainingLiveIssueQueue", "_ExactTrainingLiveStopRequested", _
		"OpenHomeNoGemInputReady", "OpenClanRequestCloseAndProveHome")
	If Not IsObj($oOutcome) Then
		$sStartError = "Exact saved-recipe training adapter returned no bounded outcome"
	Else
		Local $sOutcome = String($oOutcome.Item("state"))
		If $g_bNoPremiumPolicyTripped Then
			$sStartError = RunExecutionMessage()
			If $sStartError = "" Then $sStartError = "Exact saved-recipe training was blocked by the no-gem input guard"
			RunEventLogExactTrainingUnconfirmed($oOutcome.Item("queue_issued"), $sStartError)
			RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
			RunExecutionCancelPrepared($sStartError)
			RunControlReportOneShotOutcome("failed", $sStartError)
			Return False
		EndIf
		If $sOutcome = $EXACT_TRAINING_OUTCOME_CANCELLED Or RunControlStopRequested() Or Not $g_bRunState Then
			RunExecutionComplete("stopped")
			RunControlReportOneShotOutcome("stopped", "Exact saved-recipe training stopped")
			Return False
		EndIf
		If Not $oOutcome.Item("home_proven") Then
			RunEventLogExactTrainingUnconfirmed($oOutcome.Item("queue_issued"), _
					$oOutcome.Item("detail") & "; Home Village was not re-proven")
			$sStartError = "Home Village could not be re-proven after exact saved-recipe training; queue input will not be retried"
		Else
			RunEventLogExactTrainingHomeVerified($sOutcome)
			Switch $sOutcome
				Case $EXACT_TRAINING_OUTCOME_QUEUED
					RunEventLogExactTrainingQueued($oOutcome.Item("recipe_id"), $oOutcome.Item("missing_units"))
				Case $EXACT_TRAINING_OUTCOME_UNAVAILABLE
					RunEventLogExactTrainingUnavailable($oOutcome.Item("detail"))
				Case $EXACT_TRAINING_OUTCOME_UNCONFIRMED
					RunEventLogExactTrainingUnconfirmed($oOutcome.Item("queue_issued"), $oOutcome.Item("detail"))
					$sStartError = $oOutcome.Item("detail") & "; queue input will not be retried"
				Case Else
					$sStartError = "Exact saved-recipe training adapter returned an unknown terminal state"
			EndSwitch
		EndIf
	EndIf

	If $sStartError <> "" Then
		RunEventLogRunFailed("regular", $RUN_VERIFICATION_DIAGNOSTIC, $sStartError)
		RunExecutionCancelPrepared($sStartError)
		RunControlReportOneShotOutcome("failed", $sStartError)
		Return False
	EndIf

	Local $sReason = $sOutcome = $EXACT_TRAINING_OUTCOME_QUEUED ? "army-exact-recipe-queued" : "army-exact-recipe-unavailable"
	RunExecutionComplete($sReason)
	Local $sMessage = $sOutcome = $EXACT_TRAINING_OUTCOME_QUEUED ? _
			"Exact saved recipe queued and Home Village re-proven" : _
			"Exact saved-recipe training unavailable; no queue input was issued"
	RunControlReportOneShotOutcome("completed", $sMessage)
	SetLog("Run Planner: " & $sMessage, $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_BotStartExactRecipeTraining

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
	If RunControlCheckpoint() Or RunControlStopRequested() Then Return _BotEngineCheckFinish(False, "Managed engine check cancelled before initialization")
	Local $bEngineInitialized = MBRFuncInitialize(False)
	If RunControlCheckpoint() Or RunControlStopRequested() Then Return _BotEngineCheckFinish(False, "Managed engine check cancelled after initialization")
	If Not $bEngineInitialized Then
		$sError = MBRFuncEngineError()
		If $sError = "" Then $sError = "Managed engine initialization failed"
		Return _BotEngineCheckFinish(False, $sError)
	EndIf
	Return _BotEngineCheckFinish(True, "Managed engine initialized in the real backend; no emulator or game action was attempted")
EndFunc   ;==>_BotCheckManagedEngine

Func _BotGameLaunchFinish($bPassed, $sMessage)
	If $sMessage = "" Then $sMessage = $bPassed ? "BlueStacks and Clash of Clans launch passed" : "BlueStacks and Clash of Clans launch failed"
	; As with check-engine, native terminalization is the linearization point. A Stop accepted before
	; this call wins; a later Stop sees an idle backend and is a truthful no-op.
	Local $sOutcome = RunControlReportGameLaunchOutcome($bPassed, $sMessage)
	ReleaseExactAndroidInstanceLock()
	Switch $sOutcome
		Case "passed"
			RunEventLogGameLaunchPassed($sMessage)
		Case "cancelled"
			RunEventLogGameLaunchCancelled($sMessage)
		Case Else
			RunEventLogGameLaunchFailed($sMessage)
	EndSwitch
	Return $sOutcome = "passed"
EndFunc   ;==>_BotGameLaunchFinish

; Start only the exact BlueStacks 5 instance and CoC activity, passively prove Home or a verified
; startup overlay, then return idle. This command intentionally runs before plan preparation and
; managed-engine initialization and never dismisses the recognized overlay.
Func _BotLaunchGameOnly()
	Local $sReason = ""
	RunEventLogGameLaunchStarted()
	If RunControlStopRequested() Then Return _BotGameLaunchFinish(False, "BlueStacks and Clash of Clans launch cancelled before initialization")
	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	If Not AcquireExactAndroidInstanceLock($g_sAndroidEmulator, $g_sAndroidInstance, $sReason) Then _
		Return _BotGameLaunchFinish(False, $sReason)
	If Not LaunchBlueStacks5CoCOnly($sReason) Then
		If $sReason = "" Then $sReason = "BlueStacks and Clash of Clans launch failed"
		Return _BotGameLaunchFinish(False, $sReason)
	EndIf
	If RunControlStopRequested() Then Return _BotGameLaunchFinish(False, "BlueStacks and Clash of Clans launch cancelled after passive game-ready proof")
	Return _BotGameLaunchFinish(True, $sReason)
EndFunc   ;==>_BotLaunchGameOnly

Func BotStart($bAutostartDelay = 0)
	FuncEnter(BotStart)
	RunControlBeginStart()
	If RunControlEngineCheckRequested() Then Return FuncReturn(_BotCheckManagedEngine())
	If RunControlGameLaunchRequested() Then Return FuncReturn(_BotLaunchGameOnly())

	Local $sStartError = ""
	If Not RunExecutionPrepareStart($sStartError) Then
		SetLog("Run Planner cannot start: " & $sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	Local $oPreparedIntent = RunExecutionPreparedIntent()
	Local $iOpenCollectorsMode = OpenHomeCollectorsPreparedMode($oPreparedIntent, $sStartError)
	; OpenHomeCollectorsPreparedMode contract: 1=collectors, 2=Loot Cart, 3=Daily Reward, 4=Treasury, -1=invalid Home selection.
	If $iOpenCollectorsMode >= 1 And $iOpenCollectorsMode <= 4 Then _
		Return FuncReturn(_BotStartRunOneShot($iOpenCollectorsMode, $sStartError))
	If $iOpenCollectorsMode = -1 Then Return FuncReturn(_BotOpenCollectorsReject($sStartError))
	Local $iOpenBuilderMode = OpenBuilderBaseCollectorsPreparedMode($oPreparedIntent, $sStartError)
	If $iOpenBuilderMode = 1 Then Return FuncReturn(_BotStartRunOneShot(7, $sStartError))
	If $iOpenBuilderMode = -1 Then Return FuncReturn(_BotOpenCollectorsReject($sStartError))
	If RegularBattleEntryRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(8, $sStartError))
	If RegularBattleScoutRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(10, $sStartError))
	If BuilderBattleEntryRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(9, $sStartError))
	If ClanRequestRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(5, $sStartError))
	If ExactRecipeTrainingRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(6, $sStartError))
	; Readiness belongs to this Start attempt. A previous run may have left the
	; main-screen flag true even though the current emulator view has changed.
	$g_bMainWindowOk = False
	If RunControlStopRequested() Then Return FuncReturn(_BotStartReject("Start cancelled before waiting for the bot slot"))
	$g_bRunState = True
	$g_bTogglePauseAllowed = False
	LockBotSlot(True)
	If Not $g_bRunState Or (Not $g_bBotLaunchOption_NoBotSlot And Not LockBotSlot(Default)) Then _
		Return FuncReturn(_BotStartReject("Start cancelled while waiting for the bot slot"))
	If Not RunExecutionApplyPreparedTransport($sStartError) Then
		SetLog("Run Planner cannot bind the configured emulator: " & $sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	If Not AcquireExactAndroidInstanceLock($g_sAndroidEmulator, $g_sAndroidInstance, $sStartError) Then
		SetLog("Cannot reserve the configured emulator instance: " & $sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf

	If Not MBRFuncProbeEngine($sStartError) Then
		SetLog("Engine unavailable: " & $sStartError, $COLOR_ERROR)
		GUICtrlSetState($g_hBtnStart, $GUI_DISABLE)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf

	; The managed engine binds to the configured Android process during initialization. Bootstrap the
	; immutable plan-selected emulator and one exact game activity first so native attachment never
	; receives PID 0. No gameplay input is issued by this helper.
	If Not _BotEnsureConfiguredAndroidAndGame($sStartError) Then
		If $sStartError = "" Then $sStartError = "Unable to launch the configured emulator and Clash of Clans."
		SetLog($sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	Local $sStartupRewardOutcome = ""
	If Not OpenHomeStartupResolveDailyRewardBlocker($sStartupRewardOutcome, $sStartError) Then
		If $sStartError = "" Then $sStartError = "Startup Daily Reward recovery failed"
		SetLog($sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
	If $sStartupRewardOutcome <> "" And $sStartupRewardOutcome <> "not-seen" Then _
		SetLog("Run Planner: startup Daily Reward state before route=" & $sStartupRewardOutcome, $COLOR_INFO)

	If RunControlCheckpoint() Or RunControlStopRequested() Then _
		Return FuncReturn(_BotStartReject("Start cancelled before managed engine initialization"))
	Local $bEngineInitialized = MBRFuncInitialize()
	If RunControlCheckpoint() Or RunControlStopRequested() Then _
		Return FuncReturn(_BotStartReject("Start cancelled after managed engine initialization"))
	If Not $bEngineInitialized Then
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
	If Not RunExecutionReassertPreparedTransport($sStartError) Then
		SetLog("Run Planner cannot reassert the configured emulator after profile reload: " & $sStartError, $COLOR_ERROR)
		Return FuncReturn(_BotStartReject($sStartError))
	EndIf
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
	ReleaseExactAndroidInstanceLock()

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
