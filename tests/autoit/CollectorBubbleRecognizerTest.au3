#NoTrayIcon
Opt("MustDeclareVars", 1)

#include <GDIPlus.au3>
#include <Math.au3>
#include "..\..\COCBot\functions\Run\CollectorBubbleRecognizer.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWrite("FAIL: " & $sMessage & @CRLF)
		Exit 1
	EndIf
EndFunc   ;==>AssertTrue

Func AssertNear($iExpected, $iActual, $iTolerance, $sMessage)
	AssertTrue(Abs($iExpected - $iActual) <= $iTolerance, $sMessage & " expected=" & $iExpected & " actual=" & $iActual)
EndFunc   ;==>AssertNear

Func DrawBubble(ByRef $hGraphics, $iX, $iY, $iKind)
	Local $hPale = _GDIPlus_BrushCreateSolid(0xFFD7DCB9)
	_GDIPlus_GraphicsFillEllipse($hGraphics, $iX - 16, $iY - 16, 33, 33, $hPale)
	_GDIPlus_BrushDispose($hPale)

	Switch $iKind
		Case $eCollectorBubbleGold
			Local $hGold = _GDIPlus_BrushCreateSolid(0xFFF8BD03)
			_GDIPlus_GraphicsFillEllipse($hGraphics, $iX - 6, $iY - 4, 12, 9, $hGold)
			_GDIPlus_BrushDispose($hGold)
		Case $eCollectorBubbleElixir
			Local $hElixir = _GDIPlus_BrushCreateSolid(0xFFDB58D1)
			_GDIPlus_GraphicsFillEllipse($hGraphics, $iX - 7, $iY - 7, 14, 14, $hElixir)
			_GDIPlus_BrushDispose($hElixir)
		Case $eCollectorBubbleDark
			Local $hPurple = _GDIPlus_BrushCreateSolid(0xFF806088)
			Local $hDark = _GDIPlus_BrushCreateSolid(0xFF050505)
			_GDIPlus_GraphicsFillEllipse($hGraphics, $iX - 10, $iY - 10, 20, 20, $hPurple)
			_GDIPlus_GraphicsFillEllipse($hGraphics, $iX - 6, $iY - 6, 12, 12, $hDark)
			_GDIPlus_BrushDispose($hDark)
			_GDIPlus_BrushDispose($hPurple)
	EndSwitch
EndFunc   ;==>DrawBubble

_GDIPlus_Startup()
Local $hBitmap = _GDIPlus_BitmapCreateFromScan0(860, 732)
Local $hGraphics = _GDIPlus_ImageGetGraphicsContext($hBitmap)
_GDIPlus_GraphicsSetSmoothingMode($hGraphics, 3)
_GDIPlus_GraphicsClear($hGraphics, 0xFF31502C)
DrawBubble($hGraphics, 220, 220, $eCollectorBubbleGold)
DrawBubble($hGraphics, 420, 220, $eCollectorBubbleElixir)
DrawBubble($hGraphics, 620, 220, $eCollectorBubbleDark)

Local $hHBitmap = _GDIPlus_BitmapCreateDIBFromBitmap($hBitmap)
Local $aFound = CollectorBubbleRecognize($hHBitmap)
AssertTrue(IsArray($aFound), "recognizer returns an array")
AssertTrue(UBound($aFound) = 3, "recognizer returns the three resource rows")
AssertNear(220, $aFound[$eCollectorBubbleGold][1], 5, "Gold bubble x")
AssertNear(220, $aFound[$eCollectorBubbleGold][2], 5, "Gold bubble y")
AssertNear(420, $aFound[$eCollectorBubbleElixir][1], 5, "Elixir bubble x")
AssertNear(220, $aFound[$eCollectorBubbleElixir][2], 5, "Elixir bubble y")
AssertNear(620, $aFound[$eCollectorBubbleDark][1], 6, "Dark Elixir bubble x")
AssertNear(220, $aFound[$eCollectorBubbleDark][2], 6, "Dark Elixir bubble y")
_WinAPI_DeleteObject($hHBitmap)

_GDIPlus_GraphicsClear($hGraphics, 0xFF31502C)
$hHBitmap = _GDIPlus_BitmapCreateDIBFromBitmap($hBitmap)
$aFound = CollectorBubbleRecognize($hHBitmap)
For $i = 0 To 2
	AssertTrue($aFound[$i][1] = -1 And $aFound[$i][2] = -1, "blank frame rejects resource row " & $i)
Next

_WinAPI_DeleteObject($hHBitmap)
_GDIPlus_GraphicsDispose($hGraphics)
_GDIPlus_BitmapDispose($hBitmap)

; Optional developer/live-fixture audit. The tracked test stays synthetic; an explicitly supplied
; local frame may contain private game data and is never copied into the repository.
If $CmdLine[0] >= 2 Then
	Local $hExternalBitmap = _GDIPlus_BitmapCreateFromFile($CmdLine[1])
	AssertTrue($hExternalBitmap <> 0, "external audit frame loads")
	Local $hExternalHBitmap = _GDIPlus_BitmapCreateDIBFromBitmap($hExternalBitmap)
	Local $aExternal = CollectorBubbleRecognize($hExternalHBitmap)
	Local $iExternalFound = 0
	For $i = 0 To 2
		If $aExternal[$i][1] >= 0 And $aExternal[$i][2] >= 0 Then $iExternalFound += 1
		ConsoleWrite("external " & $aExternal[$i][0] & "=" & $aExternal[$i][1] & "," & $aExternal[$i][2] & @CRLF)
	Next
	If $CmdLine[2] = "expect-all" Then AssertTrue($iExternalFound = 3, "external frame contains all three collector bubbles")
	If $CmdLine[2] = "expect-none" Then AssertTrue($iExternalFound = 0, "external frame contains no collector bubbles")
	_WinAPI_DeleteObject($hExternalHBitmap)
	_GDIPlus_BitmapDispose($hExternalBitmap)
EndIf

_GDIPlus_Shutdown()

ConsoleWrite("Collector bubble recognizer tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
