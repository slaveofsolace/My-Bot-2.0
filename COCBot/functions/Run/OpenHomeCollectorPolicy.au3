; Pure color/geometry policy for the template-free Home collector adapter.
#include-once

Global Const $OPEN_HOME_COLLECTOR_NONE = 0
Global Const $OPEN_HOME_COLLECTOR_GOLD = 1
Global Const $OPEN_HOME_COLLECTOR_ELIXIR = 2
Global Const $OPEN_HOME_COLLECTOR_DARK = 3

Func _OpenHomeCollectorRed($iColor)
	Return BitAND(BitShift($iColor, 16), 0xFF)
EndFunc   ;==>_OpenHomeCollectorRed

Func _OpenHomeCollectorGreen($iColor)
	Return BitAND(BitShift($iColor, 8), 0xFF)
EndFunc   ;==>_OpenHomeCollectorGreen

Func _OpenHomeCollectorBlue($iColor)
	Return BitAND($iColor, 0xFF)
EndFunc   ;==>_OpenHomeCollectorBlue

Func _OpenHomeCollectorDistance($iColor, $iRed, $iGreen, $iBlue)
	Return Abs(_OpenHomeCollectorRed($iColor) - $iRed) + Abs(_OpenHomeCollectorGreen($iColor) - $iGreen) + _
			Abs(_OpenHomeCollectorBlue($iColor) - $iBlue)
EndFunc   ;==>_OpenHomeCollectorDistance

; The upper-left sample distinguishes the dark-elixir glyph from similarly colored scenery.
Func OpenHomeCollectorClassify($iCenterColor, $iUpperLeftColor)
	Local $iRed = _OpenHomeCollectorRed($iCenterColor)
	Local $iGreen = _OpenHomeCollectorGreen($iCenterColor)
	Local $iBlue = _OpenHomeCollectorBlue($iCenterColor)
	If $iRed >= 220 And $iGreen >= 145 And $iBlue <= 120 Then Return $OPEN_HOME_COLLECTOR_GOLD
	If $iRed >= 180 And $iBlue >= 160 And $iGreen <= 145 And ($iRed + $iBlue - 2 * $iGreen) >= 100 Then _
		Return $OPEN_HOME_COLLECTOR_ELIXIR
	If $iRed >= 130 And $iBlue >= 130 And $iGreen <= $iRed - 5 And _
			_OpenHomeCollectorRed($iUpperLeftColor) <= 170 And _OpenHomeCollectorBlue($iUpperLeftColor) <= 180 Then _
		Return $OPEN_HOME_COLLECTOR_DARK
	Return $OPEN_HOME_COLLECTOR_NONE
EndFunc   ;==>OpenHomeCollectorClassify

; The four pale edge samples describe the current-client resource speech bubble. A center color alone
; is never actionable because village scenery can share gold, magenta, or purple pixels.
Func OpenHomeCollectorGeometryScore($iTopLeft, $iTopRight, $iRight, $iBottomRight)
	Local $iTopLeftDistance = _OpenHomeCollectorDistance($iTopLeft, 215, 220, 185)
	Local $iTopRightDistance = _OpenHomeCollectorDistance($iTopRight, 215, 220, 185)
	Local $iRightDistance = _OpenHomeCollectorDistance($iRight, 200, 206, 160)
	Local $iBottomRightDistance = _OpenHomeCollectorDistance($iBottomRight, 180, 188, 123)
	If $iTopLeftDistance > 55 Or $iTopRightDistance > 55 Or $iRightDistance > 100 Or $iBottomRightDistance > 100 Then Return -1
	Return $iTopLeftDistance + $iTopRightDistance + $iRightDistance + $iBottomRightDistance
EndFunc   ;==>OpenHomeCollectorGeometryScore
