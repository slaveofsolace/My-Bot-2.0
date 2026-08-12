
; #FUNCTION# ====================================================================================================================
; Name ..........: GetPixelDropTroop
; Description ...:
; Syntax ........: GetPixelDropTroop($troop, $number, $slotsPerEdge)
; Parameters ....: $troop               - a dll struct value.
;                  $number              - a general number value.
;                  $slotsPerEdge        - a string value.
; Return values .: None
; Author ........:
; Modified ......: ProMac (07-2018)
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================
Func GetPixelDropTroop($troop, $number, $slotsPerEdge)
	Local $newPixelTopLeft
	Local $newPixelBottomLeft
	Local $newPixelTopRight
	Local $newPixelBottomRight

	If ($troop = $eArch Or $troop = $eSArch Or $troop = $eWiza Or $troop = $eSWiza Or $troop = $eMini Or $troop = $eSMini Or $troop = $eBarb Or $troop = $eSBarb) Then
		If UBound($g_aiPixelTopLeftFurther) > 0 Then
			$newPixelTopLeft = $g_aiPixelTopLeftFurther
		Else
			$newPixelTopLeft = $g_aiPixelTopLeft
		EndIf
		If UBound($g_aiPixelBottomLeftFurther) > 0 Then
			$newPixelBottomLeft = $g_aiPixelBottomLeftFurther
		Else
			$newPixelBottomLeft = $g_aiPixelBottomLeft
		EndIf
		If UBound($g_aiPixelTopRightFurther) > 0 Then
			$newPixelTopRight = $g_aiPixelTopRightFurther
		Else
			$newPixelTopRight = $g_aiPixelTopRight
		EndIf
		If UBound($g_aiPixelBottomRightFurther) Then
			$newPixelBottomRight = $g_aiPixelBottomRightFurther
		Else
			$newPixelBottomRight = $g_aiPixelBottomRight
		EndIf
	Else
		$newPixelTopLeft = $g_aiPixelTopLeft
		$newPixelBottomLeft = $g_aiPixelBottomLeft
		$newPixelTopRight = $g_aiPixelTopRight
		$newPixelBottomRight = $g_aiPixelBottomRight
	EndIf

	$newPixelTopLeft = GetVectorPixelOnEachSide2($newPixelTopLeft, 0, $slotsPerEdge)
	$newPixelBottomLeft = GetVectorPixelOnEachSide2($newPixelBottomLeft, 1, $slotsPerEdge)
	$newPixelTopRight = GetVectorPixelOnEachSide2($newPixelTopRight, 1, $slotsPerEdge)
	$newPixelBottomRight = GetVectorPixelOnEachSide2($newPixelBottomRight, 0, $slotsPerEdge)

	Local $g_aaiEdgeDropPointsPixelToDrop[4] = [$newPixelBottomRight, $newPixelTopLeft, $newPixelBottomLeft, $newPixelTopRight]
	; A planned Smart run scores the current four red-line sides once. Put that proven side first because
	; the inherited one-side actuator consumes index 0; retain the remaining order only for diagnostics.
	If RunExecutionSmartAttackEnabled() Then
		Switch SmartAttackCombatSelectedSide()
			Case $SMART_ATTACK_SIDE_BL
				$g_aaiEdgeDropPointsPixelToDrop[0] = $newPixelBottomLeft
				$g_aaiEdgeDropPointsPixelToDrop[1] = $newPixelBottomRight
				$g_aaiEdgeDropPointsPixelToDrop[2] = $newPixelTopLeft
				$g_aaiEdgeDropPointsPixelToDrop[3] = $newPixelTopRight
			Case $SMART_ATTACK_SIDE_TR
				$g_aaiEdgeDropPointsPixelToDrop[0] = $newPixelTopRight
				$g_aaiEdgeDropPointsPixelToDrop[1] = $newPixelBottomRight
				$g_aaiEdgeDropPointsPixelToDrop[2] = $newPixelBottomLeft
				$g_aaiEdgeDropPointsPixelToDrop[3] = $newPixelTopLeft
			Case $SMART_ATTACK_SIDE_TL
				$g_aaiEdgeDropPointsPixelToDrop[0] = $newPixelTopLeft
				$g_aaiEdgeDropPointsPixelToDrop[1] = $newPixelBottomRight
				$g_aaiEdgeDropPointsPixelToDrop[2] = $newPixelBottomLeft
				$g_aaiEdgeDropPointsPixelToDrop[3] = $newPixelTopRight
		EndSwitch
	EndIf
	Return $g_aaiEdgeDropPointsPixelToDrop
EndFunc   ;==>GetPixelDropTroop
