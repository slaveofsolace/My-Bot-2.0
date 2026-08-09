; #FUNCTION# ====================================================================================================================
; Name ..........: ForumAuthentication
; Description ...: Preserve the upstream MyBot.run v8.2.0 authorization compatibility contract.
; Author ........: cosote (2019)
; Modified ......:
; Remarks .......: This file is part of MyBot Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
;                  Official MyBot.run has bypassed its retired forum-login exchange since v7.8.1.
; Related .......: Returns True
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......:
; ===============================================================================================================================

; Keep the status field for Control Center protocol compatibility. It is always
; ready because the upstream v8.2.0 engine does not require network forum login.
Global $g_bForumAuthorizationReady = True

Func ForumAuthorizationReady()
	Return True
EndFunc   ;==>ForumAuthorizationReady

Func ForumAuthentication()
	$g_bForumAuthorizationReady = True
	Return True
EndFunc   ;==>ForumAuthentication
