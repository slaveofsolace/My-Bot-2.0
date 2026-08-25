; #FUNCTION# ====================================================================================================================
; Name ..........: Synchronization functions
; Description ...: Synchronize access to functions or code
; Syntax ........:
; Parameters ....:
; Return values .:
; Author ........: Cosote (2016-08)
; Modified ......:
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

Global $g_hExactAndroidInstanceMutex = 0
Global $g_sExactAndroidInstanceMutexIdentity = ""
Global $g_hConfiguredAndroidInstanceMutex = 0
Global $g_sConfiguredAndroidInstanceMutexIdentity = ""

Func _CanonicalExactAndroidInstanceIdentity($sEmulator, $sInstance)
	Local $sNormalizedEmulator = StringLower(StringStripWS(String($sEmulator), $STR_STRIPLEADING + $STR_STRIPTRAILING))
	Local $sNormalizedInstance = StringLower(StringStripWS(String($sInstance), $STR_STRIPLEADING + $STR_STRIPTRAILING))
	If Not StringRegExp($sNormalizedEmulator, "^[a-z0-9._ -]{1,64}$") Then Return ""
	If Not StringRegExp($sNormalizedInstance, "^[a-z0-9._ -]{0,64}$") Then Return ""

	Switch $sNormalizedEmulator
		Case "ldplayer9"
			Local $sLdIndex = StringReplace($sNormalizedInstance, "leidian", "")
			If Not StringIsInt($sLdIndex) Then $sLdIndex = "0"
			$sNormalizedInstance = "index-" & Int($sLdIndex)
		Case "mumu"
			Local $sMumuIndex = StringReplace($sNormalizedInstance, "mumuplayerglobal-12.0-", "")
			If Not StringIsInt($sMumuIndex) Then $sMumuIndex = "0"
			$sNormalizedInstance = "index-" & Int($sMumuIndex)
		Case "nox"
			If $sNormalizedInstance = "" Or $sNormalizedInstance = "nox" Or $sNormalizedInstance = "nox_0" Then _
				$sNormalizedInstance = "nox_0"
		Case "memu"
			If $sNormalizedInstance = "" Then $sNormalizedInstance = "memu"
		Case Else
			If $sNormalizedInstance = "" Then $sNormalizedInstance = "__default__"
	EndSwitch
	Return $sNormalizedEmulator & "|" & $sNormalizedInstance
EndFunc   ;==>_CanonicalExactAndroidInstanceIdentity

Func _ExactAndroidInstanceMutexName($sEmulator, $sInstance)
	Local $sCanonical = _CanonicalExactAndroidInstanceIdentity($sEmulator, $sInstance)
	Local $iSeparator = StringInStr($sCanonical, "|")
	If $iSeparator <= 1 Then Return ""
	Local $sNormalizedEmulator = StringLeft($sCanonical, $iSeparator - 1)
	Local $sNormalizedInstance = StringTrimLeft($sCanonical, $iSeparator)
	; Length-prefix each validated component. This is collision-free without importing Crypt into the
	; Watchdog and Mini entry points that also include the shared synchronization helpers.
	Return "Global\MyBot.run.AndroidInstance.v1." & StringLen($sNormalizedEmulator) & "." & _
			$sNormalizedEmulator & "." & StringLen($sNormalizedInstance) & "." & $sNormalizedInstance
EndFunc   ;==>_ExactAndroidInstanceMutexName

Func _ConfiguredAndroidInstanceMutexName($sEmulator, $sInstance)
	Local $sCanonical = _CanonicalExactAndroidInstanceIdentity($sEmulator, $sInstance)
	Local $iSeparator = StringInStr($sCanonical, "|")
	If $iSeparator <= 1 Then Return ""
	Local $sNormalizedEmulator = StringLeft($sCanonical, $iSeparator - 1)
	Local $sNormalizedInstance = StringTrimLeft($sCanonical, $iSeparator)
	; A running native controller holds this process-lifetime reservation from startup until exit.
	; Keep it in a separate namespace from action-scoped input locks: installed Start can be
	; dispatched by a different native event path than startup, and must not wait on its own
	; controller reservation before it can launch or attach the emulator.
	Return "Global\MyBot.run.ConfiguredAndroidReservation.v1." & StringLen($sNormalizedEmulator) & "." & _
			$sNormalizedEmulator & "." & StringLen($sNormalizedInstance) & "." & $sNormalizedInstance
EndFunc   ;==>_ConfiguredAndroidInstanceMutexName

Func _AcquireExactAndroidInstanceMutexHandle($sIdentity, $iTimeoutMs, $bStopAware)
	Local $hTimer = __TimerInit()
	While (Not $bStopAware Or $g_bRunState) And ($iTimeoutMs < 1 Or __TimerDiff($hTimer) < $iTimeoutMs)
		Local $hMutex = CreateMutex($sIdentity)
		If $hMutex Then Return $hMutex
		Sleep(100)
	WEnd
	Return 0
EndFunc   ;==>_AcquireExactAndroidInstanceMutexHandle

; Reserve the configured physical emulator for the lifetime of the native backend. This covers
; independently callable idle/manual GUI actuators as well as Start. Action-scoped locks below are
; still used for a plan that temporarily targets a different exact instance.
Func ReserveConfiguredAndroidInstanceLock($sEmulator, $sInstance, ByRef $sReason, $iTimeoutMs = 5000)
	$sReason = ""
	Local $sIdentity = _ConfiguredAndroidInstanceMutexName($sEmulator, $sInstance)
	If $sIdentity = "" Then
		$sReason = "The configured emulator instance cannot be canonicalized for exclusive ownership"
		Return False
	EndIf
	If $g_hConfiguredAndroidInstanceMutex Then
		If $g_sConfiguredAndroidInstanceMutexIdentity = $sIdentity Then Return True
		$sReason = "The native controller is already reserved for a different emulator instance"
		Return False
	EndIf
	Local $hMutex = _AcquireExactAndroidInstanceMutexHandle($sIdentity, $iTimeoutMs, False)
	If Not $hMutex Then
		$sReason = "Another native controller is using the configured physical emulator instance"
		Return False
	EndIf
	$g_hConfiguredAndroidInstanceMutex = $hMutex
	$g_sConfiguredAndroidInstanceMutexIdentity = $sIdentity
	SetDebugLog("Reserved configured Android instance for this native controller")
	Return True
EndFunc   ;==>ReserveConfiguredAndroidInstanceLock

Func RebindConfiguredAndroidInstanceLock($sEmulator, $sInstance, ByRef $sReason)
	$sReason = ""
	If Not $g_hConfiguredAndroidInstanceMutex Then Return True
	Local $sIdentity = _ConfiguredAndroidInstanceMutexName($sEmulator, $sInstance)
	If $sIdentity = "" Then
		$sReason = "The selected emulator instance cannot be canonicalized for exclusive ownership"
		Return False
	EndIf
	If $g_sConfiguredAndroidInstanceMutexIdentity = $sIdentity Then Return True
	; Never wait while retaining another physical-instance reservation: two controllers swapping
	; instances could otherwise deadlock. Make exactly one acquisition attempt, then retain the old
	; reservation on failure. The action-scoped handle (when present) independently keeps the old
	; instance exclusive until that action reaches its terminal boundary.
	Local $hNewMutex = CreateMutex($sIdentity)
	If Not $hNewMutex Then
		$sReason = "Another native controller is using the selected physical emulator instance"
		Return False
	EndIf
	Local $hPrevious = $g_hConfiguredAndroidInstanceMutex
	$g_hConfiguredAndroidInstanceMutex = $hNewMutex
	$g_sConfiguredAndroidInstanceMutexIdentity = $sIdentity
	ReleaseMutex($hPrevious)
	SetDebugLog("Rebound configured Android instance reservation")
	Return True
EndFunc   ;==>RebindConfiguredAndroidInstanceLock

Func ReleaseConfiguredAndroidInstanceLock()
	If Not $g_hConfiguredAndroidInstanceMutex Then Return
	Local $hMutex = $g_hConfiguredAndroidInstanceMutex
	$g_hConfiguredAndroidInstanceMutex = 0
	$g_sConfiguredAndroidInstanceMutexIdentity = ""
	ReleaseMutex($hMutex)
	SetDebugLog("Released configured Android instance reservation")
EndFunc   ;==>ReleaseConfiguredAndroidInstanceLock

; The capacity-based ActiveBot ticket limits total work, but it does not protect one account from
; two bot processes. Hold this exact emulator+instance mutex across every emulator/game/input path.
; The kernel abandons the mutex on process death, so a crashed owner cannot deadlock future runs.
Func AcquireExactAndroidInstanceLock($sEmulator, $sInstance, ByRef $sReason, $iTimeoutMs = 30000, $bStopAware = True)
	$sReason = ""
	Local $sIdentity = _ExactAndroidInstanceMutexName($sEmulator, $sInstance)
	If $sIdentity = "" Then
		$sReason = "The configured emulator instance cannot be bound to an exclusive input lock"
		Return False
	EndIf
	If $g_hExactAndroidInstanceMutex Then
		If $g_sExactAndroidInstanceMutexIdentity = $sIdentity Then Return True
		$sReason = "The active run is already bound to a different emulator instance"
		Return False
	EndIf
	; Acquire an independent recursive kernel ownership even when the process-lifetime reservation
	; already owns this name. A later configuration rebind may release the base handle; this action
	; handle must continue excluding another process from the original instance until completion.
	Local $hMutex = _AcquireExactAndroidInstanceMutexHandle($sIdentity, $iTimeoutMs, $bStopAware)
	If $hMutex Then
		$g_hExactAndroidInstanceMutex = $hMutex
		$g_sExactAndroidInstanceMutexIdentity = $sIdentity
		SetDebugLog("Acquired exact Android instance mutex: " & $sEmulator & " (" & ($sInstance = "" ? "default" : $sInstance) & ")")
		Return True
	EndIf
	$sReason = ($bStopAware And Not $g_bRunState) ? "Start cancelled while waiting for the configured emulator instance" : "Another bot process is using the configured emulator instance"
	Return False
EndFunc   ;==>AcquireExactAndroidInstanceLock

Func ReleaseExactAndroidInstanceLock()
	If Not $g_hExactAndroidInstanceMutex Then
		$g_sExactAndroidInstanceMutexIdentity = ""
		Return
	EndIf
	Local $hMutex = $g_hExactAndroidInstanceMutex
	$g_hExactAndroidInstanceMutex = 0
	$g_sExactAndroidInstanceMutexIdentity = ""
	ReleaseMutex($hMutex)
	SetDebugLog("Released exact Android instance mutex")
EndFunc   ;==>ReleaseExactAndroidInstanceLock

Func CreateMutex($sMutex)

	Local $hMutex = _WinAPI_CreateMutex($sMutex, False)
	;If _WinAPI_GetLastError() <> $ERROR_ALREADY_EXISTS Then
	If $hMutex Then
		Switch _WinAPI_WaitForSingleObject($hMutex, 0)
			; WAIT_ABANDONED = 0x80, WAIT_OBJECT_0 = 0, $WAIT_TIMEOUT = 0x102
			Case 0x80, 0
				Return $hMutex
		EndSwitch
		_WinAPI_CloseHandle($hMutex)
	EndIf
	Return 0

EndFunc   ;==>CreateMutex

Func AcquireMutex($mutexName, $scope = Default, $timeout = Default, $sWaitMessage = "", $bUse_Sleep = False)
	Local $timer = __TimerInit()
	If $sWaitMessage = Default Then $sWaitMessage = "Waiting for mutex " & $mutexName & " to become available..."
	Local $iDelay = $DELAYSLEEP
	If $sWaitMessage Then $iDelay = 1000
	Local $g_hMutex_MyBot = 0
	If $scope = Default Then
		$scope = @AutoItPID & "/"
	ElseIf $scope <> "" Then
		$scope &= "/"
	EndIf
	If $timeout = Default Then $timeout = 30000
	Local $bLogged = False
	While $g_hMutex_MyBot = 0 And ($timeout < 1 Or __TimerDiff($timer) < $timeout)
		$g_hMutex_MyBot = CreateMutex("MyBot.run/" & $scope & $mutexName)
		If $g_hMutex_MyBot <> 0 Then ExitLoop
		If $timeout = 0 Then ExitLoop
		If $sWaitMessage Then
			If $bLogged = False Then
				$bLogged = True
				SetLog($sWaitMessage)
			EndIf
			_GUICtrlStatusBar_SetTextEx($g_hStatusBar, $sWaitMessage)
		EndIf
		If $bUse_Sleep Then
			If _Sleep($iDelay) Then Return
		Else
			Sleep($iDelay)
		EndIf
	WEnd
	If $g_hMutex_MyBot Then
		; protect the handle from getting closed by something else!
		;_WinAPI_SetHandleInformation($g_hMutex_MyBot, $HANDLE_FLAG_PROTECT_FROM_CLOSE, $HANDLE_FLAG_PROTECT_FROM_CLOSE)
	EndIf
	Return $g_hMutex_MyBot
EndFunc   ;==>AcquireMutex

Func ReleaseMutex($hMutex, $ReturnValue = Default)
	If $hMutex Then
		;_WinAPI_SetHandleInformation($hMutex, $HANDLE_FLAG_PROTECT_FROM_CLOSE, 0)
		_WinAPI_ReleaseMutex($hMutex)
		_WinAPI_CloseHandle($hMutex)
	EndIf
	If $ReturnValue = Default Then Return
	Return $ReturnValue
EndFunc   ;==>ReleaseMutex

Func WaitForSemaphore($sSemaphore, $iInitial = 4096, $iMaximum = 4096, $sWaitMessage = Default, $tSecurity = 0)
	Local $hSemaphore = _WinAPI_CreateSemaphore($sSemaphore, $iInitial, $iMaximum, $tSecurity)
	If LockSemaphore($hSemaphore, $sWaitMessage) Then Return $hSemaphore
	; close semaphore when created and bot stopped
	_WinAPI_CloseHandle($hSemaphore)
	Return 0
EndFunc   ;==>WaitForSemaphore

Func LockSemaphore($Semaphore, $sWaitMessage = Default)
	Local $bAquired = False
	If $sWaitMessage = Default Then $sWaitMessage = "Waiting for slot to become available..."
	Local $iDelay = $DELAYSLEEP
	If $sWaitMessage Then $iDelay = 1000
	Local $hSemaphore = $Semaphore
	If IsString($Semaphore) = 1 Then $hSemaphore = _WinAPI_CreateSemaphore($Semaphore, 1, 1)
	Local $bLogged = False
	While $bAquired = False And $g_bRunState = True
		$bAquired = _WinAPI_WaitForSingleObject($hSemaphore, $DELAYSLEEP) <> $WAIT_TIMEOUT
		If $bAquired = True Then
			Return $hSemaphore
		EndIf
		If $sWaitMessage Then
			If $bLogged = False Then
				$bLogged = True
				SetLog($sWaitMessage)
			EndIf
			_GUICtrlStatusBar_SetTextEx($g_hStatusBar, $sWaitMessage)
		EndIf
		If _Sleep($iDelay, True, False) Then Return
		;Sleep($iDelay)
	WEnd
	; close semaphore when created and bot stopped
	If $Semaphore <> $hSemaphore Then _WinAPI_CloseHandle($hSemaphore)
	Return 0
EndFunc   ;==>LockSemaphore

Func UnlockSemaphore(ByRef $hSemaphore, $bCloseHandle = False)
	If $hSemaphore <> 0 And $hSemaphore <> -1 Then
		Local $iPreviousCount = _WinAPI_ReleaseSemaphore($hSemaphore)
		If $bCloseHandle = True Then
			_WinAPI_CloseHandle($hSemaphore)
			$hSemaphore = 0
		EndIf
		Return $iPreviousCount
	EndIf
	Return -1
EndFunc   ;==>UnlockSemaphore

Func AcquireMutexTicket($sMutexName, $iMinTicketNo, $sWaitMessage = Default, $bCheckRunState = True)
	; get ticket
	Local $hTicketMutex = 0
	Local $sTicketMutex = 0
	Local $iTicket = 256
	For $i = 1 To 255
		If $bCheckRunState = True And $g_bRunState = False Then Return 0
		$sTicketMutex = $sMutexName & "." & $i
		$hTicketMutex = AcquireMutex($sTicketMutex, "Global", 0)
		If $hTicketMutex Then
			$iTicket = $i
			ExitLoop
		EndIf
	Next

	If $hTicketMutex = 0 Then
		SetLog("Could not aquire mutex ticker for: " & $sMutexName, $COLOR_RED)
		Return 0
	EndIf

	If $iTicket <= $iMinTicketNo Then
		SetDebugLog("Aquired mutex ticket: " & $sTicketMutex & ", " & $hTicketMutex)
		Return $hTicketMutex
	EndIf

	SetDebugLog("Wait mutex ticket: " & $sTicketMutex)

	; wait for ticket to get to counter
	If $sWaitMessage = Default Then $sWaitMessage = "Waiting for slot to become available..."
	Local $iDelay = $DELAYSLEEP
	If $sWaitMessage Then $iDelay = 1000

	Local $bLogged = False
	While $bCheckRunState = False Or $g_bRunState = True
		If $iTicket = $iMinTicketNo + 1 Then
			; next in line
			For $i = 1 To $iMinTicketNo
				$sTicketMutex = $sMutexName & "." & $i
				Local $hFinalTicketMutex = AcquireMutex($sTicketMutex, "Global", 0)
				If $hFinalTicketMutex Then
					; found slot
					SetDebugLog("Aquired mutex ticket: " & $sTicketMutex & ", " & $hFinalTicketMutex)
					Return ReleaseMutex($hTicketMutex, $hFinalTicketMutex)
				EndIf
			Next
		Else
			; wait to become next in line
			$sTicketMutex = $sMutexName & "." & ($iTicket - 1)
			Local $hNextTicketMutex = AcquireMutex($sTicketMutex, "Global", 0)
			If $hNextTicketMutex Then
				; move one slot closer
				SetDebugLog("New mutex ticket: " & $sTicketMutex)
				$iTicket -= 1
				$hTicketMutex = ReleaseMutex($hTicketMutex, $hNextTicketMutex)
			EndIf
		EndIf

		If $sWaitMessage Then
			If $bLogged = False Then
				$bLogged = True
				SetLog($sWaitMessage)
			EndIf
			_GUICtrlStatusBar_SetTextEx($g_hStatusBar, $sWaitMessage)
		EndIf
		;SetDebugLog("Waiting for mutex ticket (" & $iTicket & "): " & $sTicketMutex)
		If _Sleep($iDelay, True, False) Then Return
		;Sleep($iDelay)
	WEnd

	; bot stopped
	Return ReleaseMutex($hTicketMutex, 0)
EndFunc   ;==>AcquireMutexTicket

Func LockBotSlot($bLock = True)
	If $g_bBotLaunchOption_NoBotSlot = True Then Return False
	Static $bBotIsLocked = False
	If $bLock = Default Then Return $bBotIsLocked
	If $bLock = $bBotIsLocked Then Return $bBotIsLocked
	Local $bWasLocked = $bBotIsLocked
	If $bLock = True And $g_bRunState = True Then
		;Semaphores here don't support FIFO, use AcquireMutexTicket
		;If LockSemaphore($g_hMutextOrSemaphoreGlobalActiveBots, GetTranslatedFileIni("MBR GUI Design - Loading", "SplashStep_09", "Waiting for bot slot...")) Then $bBotIsLocked = $bLock
		If $g_hMutextOrSemaphoreGlobalActiveBots Then
			; should not happen
			SetDebugLog("LockBotSlot not released: " & $g_hMutextOrSemaphoreGlobalActiveBots)
			ReleaseMutex($g_hMutextOrSemaphoreGlobalActiveBots)
			$g_hMutextOrSemaphoreGlobalActiveBots = 0
		EndIf
		$g_hMutextOrSemaphoreGlobalActiveBots = AcquireMutexTicket("ActiveBot", $g_iGlobalActiveBotsAllowed, GetTranslatedFileIni("MBR GUI Design - Loading", "SplashStep_09", "Waiting for bot slot..."))
		If $g_hMutextOrSemaphoreGlobalActiveBots Then $bBotIsLocked = $bLock
	ElseIf $bLock = False Then
		;Semaphores here don't support FIFO, use AcquireMutexTicket
		;UnlockSemaphore($g_hMutextOrSemaphoreGlobalActiveBots)
		ReleaseMutex($g_hMutextOrSemaphoreGlobalActiveBots)
		SetDebugLog("Released Bot slot mutex: " & $g_hMutextOrSemaphoreGlobalActiveBots)
		$g_hMutextOrSemaphoreGlobalActiveBots = 0
		$bBotIsLocked = $bLock
	EndIf
	Return $bWasLocked
EndFunc   ;==>LockBotSlot
