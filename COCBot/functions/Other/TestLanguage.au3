; #FUNCTION# ====================================================================================================================
; Name ..........: TestLanguage
; Description ...: This function tests if the game is in english language
; Syntax ........:
; Parameters ....: None
; Return values .: None
; Author ........: Sardo (2015-06) , MHK2012 (2018-02)
; Modified ......: Hervidero(2015)
;
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

Func TestLanguage()
	If Not $g_bRunState Then Return
	; test the word "Attack!" on the Attack Button in the lower left corner
	If getOcrLanguage($aDetectLang[0], $aDetectLang[1]) = "english" Then
		SetLog("Language setting is English: Correct.", $COLOR_INFO)
		Return True
	ElseIf Not ChangeLanguage() Then
		SetLog("Language setting is Wrong: Change CoC language to English!", $COLOR_ERROR)
		btnStop()
	EndIf
EndFunc

Func ChangeLanguage()
	SetLog("Change Language To English", $COLOR_INFO)

	If IsMainPage() Then Click($aButtonSetting[0], $aButtonSetting[1], 1, 120, "Click Setting")
	If _Sleep(500) Then Return False

	For $i = 0 To 20 ; Check the current-language label or the green Language button for up to 20 seconds.
		_CaptureRegion()
		If _IsSettingsLanguageEnglish(False) Then
			SetLog("Settings explicitly reports English: Correct.", $COLOR_INFO)
			Click(786, 79 + $g_iMidOffsetY, 1, 300, "Close Settings")
			If _Sleep(300) Then Return False
			Return IsMainPage()
		EndIf

		If _ColorCheck(_GetPixelColor($aButtonLanguageCheck[0], $aButtonLanguageCheck[1], False), Hex($aButtonLanguageCheck[2], 6), $aButtonLanguageCheck[3]) Then ; Green
			Click($aButtonLanguage[0], $aButtonLanguage[1], 1, 1000) ; Click Language Button
			SetLog("   1. Click Language Button")
			If _Sleep(200) Then Return False
			ExitLoop
		EndIf
		If $i = 20 Then Return False
		If _Sleep(900) Then Return False
	Next

	For $i = 0 To 20 ; Checking Language List continuously in 20sec
		If _ColorCheck(_GetPixelColor($aListLanguage[0], $aListLanguage[1], True), Hex($aListLanguage[2], 6), $aListLanguage[3]) Then ;	Green
			Click($aEnglishLanguage[0], $aEnglishLanguage[1], 1, 1000) ; English is the first fixed row in the current client.
			SetLog("   2. Click English Language")
			If _Sleep(300) Then Return False
			ExitLoop
		EndIf
		If $i = 20 Then Return False
		If _Sleep(900) Then Return False
	Next

	For $i = 0 To 10 ; Checking OKAY Button continuously in 10sec
		If _ColorCheck(_GetPixelColor($aLanguageOkay[0], $aLanguageOkay[1], True), Hex($aLanguageOkay[2], 6), $aLanguageOkay[3]) Then
			If _Sleep(250) Then Return False
			Click($aLanguageOkay[0], $aLanguageOkay[1], 1, 120, "Click OKAY")
			SetLog("   3. Click OKAY")
			SetLog("Please wait for loading CoC...!")
			waitMainScreen()
			Return True
		EndIf
		If $i = 10 Then Return False
		If _Sleep(900) Then Return False
	Next

	Return False
EndFunc   ;==>ChangeLanguage

; Prove the current 860x732 Settings label says "English".  The green-button
; checks establish the correct control; the light/dark samples establish the
; word itself.  This is a bounded compatibility fallback for the legacy Attack
; OCR and must stay fail-closed when the current-client signature is absent.
Func _IsSettingsLanguageEnglish($bNeedCapture = True)
	If $bNeedCapture Then _CaptureRegion()

	Local $bLanguageButton = _
			_ColorCheck(_GetPixelColor(360, 372 + $g_iMidOffsetY, False), Hex(0xA9D556, 6), 30) And _
			_ColorCheck(_GetPixelColor(360, 382 + $g_iMidOffsetY, False), Hex(0x70B52B, 6), 30)
	If Not $bLanguageButton Then Return False

	Local $bEnglishLight = _
			_ColorCheck(_GetPixelColor(400, 364 + $g_iMidOffsetY, False), Hex(0xEDEEE9, 6), 25) And _
			_ColorCheck(_GetPixelColor(419, 368 + $g_iMidOffsetY, False), Hex(0xE8EAE2, 6), 25) And _
			_ColorCheck(_GetPixelColor(443, 372 + $g_iMidOffsetY, False), Hex(0xEDEEEA, 6), 25) And _
			_ColorCheck(_GetPixelColor(423, 375 + $g_iMidOffsetY, False), Hex(0xEDEEEB, 6), 25)
	Local $bEnglishOutline = _
			_ColorCheck(_GetPixelColor(399, 363 + $g_iMidOffsetY, False), Hex(0x4C5041, 6), 25) And _
			_ColorCheck(_GetPixelColor(407, 375 + $g_iMidOffsetY, False), Hex(0x1A1D16, 6), 25) And _
			_ColorCheck(_GetPixelColor(455, 375 + $g_iMidOffsetY, False), Hex(0x33362A, 6), 25)

	Return $bEnglishLight And $bEnglishOutline
EndFunc   ;==>_IsSettingsLanguageEnglish
