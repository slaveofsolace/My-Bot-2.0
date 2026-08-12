; Pure deterministic Smart Attack decisions.
;
; This file intentionally has no includes and performs no capture, timing, logging,
; sleeping, input, or account actions. Callers own observations and actuation.

#include-once
;
; Point-array input accepted by side selection:
;   * a two-dimensional [point][2+] array where columns 0/1 are X/Y, or
;   * a one-dimensional array whose items are [X, Y] arrays.
; Invalid point items are ignored. The path median is the central valid point in
; source order; an even path uses the mean of its two central valid points.
;
; Existing MyBot hero index order used here:
;   0 King, 1 Queen, 2 Minion Prince, 3 Grand Warden, 4 Royal Champion.
; Hero damage is total enemy-base destruction/progress (0..100), not the
; individual Hero's lost health. Each Hero has a deterministic milestone.
;
; Spell schedule callers must pass the number of that spell already cast as the
; zero-based ordinal and evaluate only the next ordinal once per actuator tick.

Global Const $SMART_ATTACK_BASE_UNKNOWN = -1
Global Const $SMART_ATTACK_BASE_DEAD = 0
Global Const $SMART_ATTACK_BASE_ACTIVE = 1

; Stable side IDs and tie order: BR, BL, TR, TL.
Global Const $SMART_ATTACK_SIDE_NONE = -1
Global Const $SMART_ATTACK_SIDE_BR = 0
Global Const $SMART_ATTACK_SIDE_BL = 1
Global Const $SMART_ATTACK_SIDE_TR = 2
Global Const $SMART_ATTACK_SIDE_TL = 3

; SmartAttackPolicyChooseSide result indexes.
Global Const $SMART_ATTACK_SIDE_RESULT_ID = 0
Global Const $SMART_ATTACK_SIDE_RESULT_NAME = 1
Global Const $SMART_ATTACK_SIDE_RESULT_SCORE = 2
Global Const $SMART_ATTACK_SIDE_RESULT_POINT_COUNT = 3
Global Const $SMART_ATTACK_SIDE_RESULT_MEDIAN_X = 4
Global Const $SMART_ATTACK_SIDE_RESULT_MEDIAN_Y = 5
Global Const $SMART_ATTACK_SIDE_RESULT_USES_TOWN_HALL = 6
Global Const $SMART_ATTACK_SIDE_RESULT_REASON = 7
Global Const $SMART_ATTACK_SIDE_RESULT_SIZE = 8

; Internal candidate metric indexes.
Global Const $SMART_ATTACK_CANDIDATE_VALID = 0
Global Const $SMART_ATTACK_CANDIDATE_POINT_COUNT = 1
Global Const $SMART_ATTACK_CANDIDATE_MEDIAN_X = 2
Global Const $SMART_ATTACK_CANDIDATE_MEDIAN_Y = 3
Global Const $SMART_ATTACK_CANDIDATE_SIZE = 4

; SmartAttackPolicyTargetSafetyDecision result indexes.
Global Const $SMART_ATTACK_TARGET_SAFE = 0
Global Const $SMART_ATTACK_TARGET_REASON = 1
Global Const $SMART_ATTACK_TARGET_X = 2
Global Const $SMART_ATTACK_TARGET_Y = 3
Global Const $SMART_ATTACK_TARGET_RESULT_SIZE = 4

; Existing MyBot Hero ordinal indexes.
Global Const $SMART_ATTACK_HERO_KING = 0
Global Const $SMART_ATTACK_HERO_QUEEN = 1
Global Const $SMART_ATTACK_HERO_PRINCE = 2
Global Const $SMART_ATTACK_HERO_WARDEN = 3
Global Const $SMART_ATTACK_HERO_CHAMPION = 4

; SmartAttackPolicyHeroAbilityDecision result indexes.
Global Const $SMART_ATTACK_HERO_ACTIVATE = 0
Global Const $SMART_ATTACK_HERO_REASON = 1
Global Const $SMART_ATTACK_HERO_ELAPSED_THRESHOLD_MS = 2
Global Const $SMART_ATTACK_HERO_DAMAGE_THRESHOLD_PERCENT = 3
Global Const $SMART_ATTACK_HERO_ELAPSED_DUE = 4
Global Const $SMART_ATTACK_HERO_DAMAGE_DUE = 5
Global Const $SMART_ATTACK_HERO_RESULT_SIZE = 6

Global Const $SMART_ATTACK_HERO_KING_ELAPSED_MS = 34000
Global Const $SMART_ATTACK_HERO_KING_DAMAGE_PERCENT = 50
Global Const $SMART_ATTACK_HERO_QUEEN_ELAPSED_MS = 24000
Global Const $SMART_ATTACK_HERO_QUEEN_DAMAGE_PERCENT = 35
Global Const $SMART_ATTACK_HERO_PRINCE_ELAPSED_MS = 18000
Global Const $SMART_ATTACK_HERO_PRINCE_DAMAGE_PERCENT = 25
Global Const $SMART_ATTACK_HERO_WARDEN_ELAPSED_MS = 10000
Global Const $SMART_ATTACK_HERO_WARDEN_DAMAGE_PERCENT = 12
Global Const $SMART_ATTACK_HERO_CHAMPION_ELAPSED_MS = 30000
Global Const $SMART_ATTACK_HERO_CHAMPION_DAMAGE_PERCENT = 45

; SmartAttackPolicySelectAttackBarSlot result indexes. Input is the seven-column
; final GetAttackBar shape: troop index, slot, amount, X, Y, OCR X, OCR Y.
Global Const $SMART_ATTACK_SLOT_FOUND = 0
Global Const $SMART_ATTACK_SLOT_ROW = 1
Global Const $SMART_ATTACK_SLOT_TROOP_INDEX = 2
Global Const $SMART_ATTACK_SLOT_NUMBER = 3
Global Const $SMART_ATTACK_SLOT_AMOUNT = 4
Global Const $SMART_ATTACK_SLOT_X = 5
Global Const $SMART_ATTACK_SLOT_Y = 6
Global Const $SMART_ATTACK_SLOT_REASON = 7
Global Const $SMART_ATTACK_SLOT_RESULT_SIZE = 8

; Rage/Freeze decision result indexes.
Global Const $SMART_ATTACK_SPELL_CAST = 0
Global Const $SMART_ATTACK_SPELL_REASON = 1
Global Const $SMART_ATTACK_SPELL_DUE_MS = 2
Global Const $SMART_ATTACK_SPELL_TARGET_PROGRESS = 3
Global Const $SMART_ATTACK_SPELL_ORDINAL = 4
Global Const $SMART_ATTACK_SPELL_RESULT_SIZE = 5

Global Const $SMART_ATTACK_RAGE_FIRST_DUE_MS = 0
Global Const $SMART_ATTACK_RAGE_SECOND_DUE_MS = 7000
Global Const $SMART_ATTACK_RAGE_THIRD_DUE_MS = 14000
Global Const $SMART_ATTACK_RAGE_FIRST_PROGRESS = 0.35
Global Const $SMART_ATTACK_RAGE_SECOND_PROGRESS = 0.60
Global Const $SMART_ATTACK_RAGE_THIRD_PROGRESS = 0.82
Global Const $SMART_ATTACK_FREEZE_FIRST_DUE_MS = 8000
Global Const $SMART_ATTACK_FREEZE_INTERVAL_MS = 4000

; Inputs:
;   aBR/aBL/aTR/aTL - four candidate point arrays in fixed tie order.
;   iBaseState - SMART_ATTACK_BASE_* constant.
;   bUniqueTownHall - True only when recognition proved exactly one Town Hall.
;   iTownHallX/Y - Town Hall center; ignored unless active + unique + numeric.
;   iMinValidPoints - minimum valid points required for a candidate (default 1).
; Output (fixed array):
;   [ID, NAME, SCORE, POINT_COUNT, MEDIAN_X, MEDIAN_Y, USES_TH, REASON].
; Active + unique TH minimizes squared median-to-TH distance. All other states
; maximize valid point count. Equal scores retain BR, BL, TR, TL order.
Func SmartAttackPolicyChooseSide(ByRef $aBR, ByRef $aBL, ByRef $aTR, ByRef $aTL, _
		$iBaseState, $bUniqueTownHall, $iTownHallX, $iTownHallY, $iMinValidPoints = 1)
	Local $aDecision[$SMART_ATTACK_SIDE_RESULT_SIZE] = [$SMART_ATTACK_SIDE_NONE, "", -1, 0, -1, -1, False, "no-valid-side"]

	If Not IsNumber($iMinValidPoints) Or $iMinValidPoints < 1 Or Int($iMinValidPoints) <> $iMinValidPoints Then
		$aDecision[$SMART_ATTACK_SIDE_RESULT_REASON] = "invalid-minimum-point-count"
		Return $aDecision
	EndIf

	Local $aBRMetrics = _SmartAttackPolicyCandidateMetrics($aBR, $iMinValidPoints)
	Local $aBLMetrics = _SmartAttackPolicyCandidateMetrics($aBL, $iMinValidPoints)
	Local $aTRMetrics = _SmartAttackPolicyCandidateMetrics($aTR, $iMinValidPoints)
	Local $aTLMetrics = _SmartAttackPolicyCandidateMetrics($aTL, $iMinValidPoints)

	Local $bUseTownHall = $iBaseState = $SMART_ATTACK_BASE_ACTIVE And $bUniqueTownHall And _
			IsNumber($iTownHallX) And IsNumber($iTownHallY)
	Local $iBestSide = $SMART_ATTACK_SIDE_NONE
	Local $fBestScore = -1
	Local $iBestPointCount = 0
	Local $fBestMedianX = -1, $fBestMedianY = -1

	; These calls encode the public tie order. Equal scores never replace a winner.
	_SmartAttackPolicyConsiderSide($aBRMetrics, $SMART_ATTACK_SIDE_BR, $bUseTownHall, $iTownHallX, $iTownHallY, _
			$iBestSide, $fBestScore, $iBestPointCount, $fBestMedianX, $fBestMedianY)
	_SmartAttackPolicyConsiderSide($aBLMetrics, $SMART_ATTACK_SIDE_BL, $bUseTownHall, $iTownHallX, $iTownHallY, _
			$iBestSide, $fBestScore, $iBestPointCount, $fBestMedianX, $fBestMedianY)
	_SmartAttackPolicyConsiderSide($aTRMetrics, $SMART_ATTACK_SIDE_TR, $bUseTownHall, $iTownHallX, $iTownHallY, _
			$iBestSide, $fBestScore, $iBestPointCount, $fBestMedianX, $fBestMedianY)
	_SmartAttackPolicyConsiderSide($aTLMetrics, $SMART_ATTACK_SIDE_TL, $bUseTownHall, $iTownHallX, $iTownHallY, _
			$iBestSide, $fBestScore, $iBestPointCount, $fBestMedianX, $fBestMedianY)

	If $iBestSide = $SMART_ATTACK_SIDE_NONE Then Return $aDecision

	$aDecision[$SMART_ATTACK_SIDE_RESULT_ID] = $iBestSide
	$aDecision[$SMART_ATTACK_SIDE_RESULT_NAME] = SmartAttackPolicySideName($iBestSide)
	$aDecision[$SMART_ATTACK_SIDE_RESULT_SCORE] = $fBestScore
	$aDecision[$SMART_ATTACK_SIDE_RESULT_POINT_COUNT] = $iBestPointCount
	$aDecision[$SMART_ATTACK_SIDE_RESULT_MEDIAN_X] = $fBestMedianX
	$aDecision[$SMART_ATTACK_SIDE_RESULT_MEDIAN_Y] = $fBestMedianY
	$aDecision[$SMART_ATTACK_SIDE_RESULT_USES_TOWN_HALL] = $bUseTownHall
	If $bUseTownHall Then
		$aDecision[$SMART_ATTACK_SIDE_RESULT_REASON] = "nearest-median-to-town-hall"
	ElseIf $iBaseState = $SMART_ATTACK_BASE_DEAD Then
		$aDecision[$SMART_ATTACK_SIDE_RESULT_REASON] = "longest-valid-side-dead-base"
	ElseIf $iBaseState = $SMART_ATTACK_BASE_ACTIVE Then
		$aDecision[$SMART_ATTACK_SIDE_RESULT_REASON] = "longest-valid-side-no-unique-town-hall"
	Else
		$aDecision[$SMART_ATTACK_SIDE_RESULT_REASON] = "longest-valid-side-base-unknown"
	EndIf

	Return $aDecision
EndFunc   ;==>SmartAttackPolicyChooseSide

Func SmartAttackPolicySideName($iSideId)
	Switch $iSideId
		Case $SMART_ATTACK_SIDE_BR
			Return "BR"
		Case $SMART_ATTACK_SIDE_BL
			Return "BL"
		Case $SMART_ATTACK_SIDE_TR
			Return "TR"
		Case $SMART_ATTACK_SIDE_TL
			Return "TL"
	EndSwitch
	Return ""
EndFunc   ;==>SmartAttackPolicySideName

; Returns [x, y] rounded to screen pixels for E + progress * (T - E).
; progress must be numeric in [0,1]. Invalid input returns [-1,-1] with @error=1.
; This function does not claim the point is deployable; feed the result of the
; existing coordinate validator to SmartAttackPolicyTargetSafetyDecision.
Func SmartAttackPolicyTargetPoint($iEntryX, $iEntryY, $iTargetX, $iTargetY, $fProgress)
	Local $aPoint[2] = [-1, -1]
	If Not IsNumber($iEntryX) Or Not IsNumber($iEntryY) Or Not IsNumber($iTargetX) Or Not IsNumber($iTargetY) Or _
			Not IsNumber($fProgress) Or $fProgress < 0 Or $fProgress > 1 Then Return SetError(1, 0, $aPoint)

	$aPoint[0] = Round($iEntryX + $fProgress * ($iTargetX - $iEntryX), 0)
	$aPoint[1] = Round($iEntryY + $fProgress * ($iTargetY - $iEntryY), 0)
	Return SetError(0, 0, $aPoint)
EndFunc   ;==>SmartAttackPolicyTargetPoint

; Inputs: aPoint from SmartAttackPolicyTargetPoint and the Boolean result of the
; caller's safe-coordinate validator (for MyBot, isInsideDiamondRedArea(aPoint)).
; Output: [SAFE, REASON, X, Y]. Missing/non-Boolean validation fails closed.
Func SmartAttackPolicyTargetSafetyDecision(ByRef $aPoint, $bSafeCoordinate)
	Local $aDecision[$SMART_ATTACK_TARGET_RESULT_SIZE] = [False, "invalid-target", -1, -1]
	If Not IsArray($aPoint) Or UBound($aPoint, 0) <> 1 Or UBound($aPoint, 1) < 2 Then Return $aDecision
	If Not IsNumber($aPoint[0]) Or Not IsNumber($aPoint[1]) Or $aPoint[0] < 0 Or $aPoint[1] < 0 Then Return $aDecision

	$aDecision[$SMART_ATTACK_TARGET_X] = $aPoint[0]
	$aDecision[$SMART_ATTACK_TARGET_Y] = $aPoint[1]
	If Not IsBool($bSafeCoordinate) Then
		$aDecision[$SMART_ATTACK_TARGET_REASON] = "validator-result-required"
		Return $aDecision
	EndIf
	If Not $bSafeCoordinate Then
		$aDecision[$SMART_ATTACK_TARGET_REASON] = "unsafe-target"
		Return $aDecision
	EndIf

	$aDecision[$SMART_ATTACK_TARGET_SAFE] = True
	$aDecision[$SMART_ATTACK_TARGET_REASON] = "safe-target"
	Return $aDecision
EndFunc   ;==>SmartAttackPolicyTargetSafetyDecision

; Returns [elapsed threshold ms, enemy-base destruction threshold percent], or
; [-1,-1] for an unknown Hero ordinal.
Func SmartAttackPolicyHeroAbilityThresholds($iHeroIndex)
	Local $aThresholds[2] = [-1, -1]
	Switch $iHeroIndex
		Case $SMART_ATTACK_HERO_KING
			$aThresholds[0] = $SMART_ATTACK_HERO_KING_ELAPSED_MS
			$aThresholds[1] = $SMART_ATTACK_HERO_KING_DAMAGE_PERCENT
		Case $SMART_ATTACK_HERO_QUEEN
			$aThresholds[0] = $SMART_ATTACK_HERO_QUEEN_ELAPSED_MS
			$aThresholds[1] = $SMART_ATTACK_HERO_QUEEN_DAMAGE_PERCENT
		Case $SMART_ATTACK_HERO_PRINCE
			$aThresholds[0] = $SMART_ATTACK_HERO_PRINCE_ELAPSED_MS
			$aThresholds[1] = $SMART_ATTACK_HERO_PRINCE_DAMAGE_PERCENT
		Case $SMART_ATTACK_HERO_WARDEN
			$aThresholds[0] = $SMART_ATTACK_HERO_WARDEN_ELAPSED_MS
			$aThresholds[1] = $SMART_ATTACK_HERO_WARDEN_DAMAGE_PERCENT
		Case $SMART_ATTACK_HERO_CHAMPION
			$aThresholds[0] = $SMART_ATTACK_HERO_CHAMPION_ELAPSED_MS
			$aThresholds[1] = $SMART_ATTACK_HERO_CHAMPION_DAMAGE_PERCENT
	EndSwitch
	Return $aThresholds
EndFunc   ;==>SmartAttackPolicyHeroAbilityThresholds

; Stable integration API. iDamagePercent means total enemy-base destruction,
; matching the battle percentage display. Returns "" while not due or on
; invalid/unknown input; otherwise: "damage", "elapsed", "damage+elapsed".
Func SmartAttackPolicyHeroAbilityReason($iHeroIndex, $iElapsedMs, $iDamagePercent)
	Local $aDecision = SmartAttackPolicyHeroAbilityDecision($iHeroIndex, $iElapsedMs, $iDamagePercent)
	Return $aDecision[$SMART_ATTACK_HERO_REASON]
EndFunc   ;==>SmartAttackPolicyHeroAbilityReason

; Output: [ACTIVATE, REASON, ELAPSED_THRESHOLD_MS, DAMAGE_THRESHOLD_PERCENT,
;          ELAPSED_DUE, DAMAGE_DUE]. A sensor may pass -1 for an unknown elapsed
; or damage value; the other independently proven threshold can still trigger.
Func SmartAttackPolicyHeroAbilityDecision($iHeroIndex, $iElapsedMs, $iDamagePercent)
	Local $aDecision[$SMART_ATTACK_HERO_RESULT_SIZE] = [False, "", -1, -1, False, False]
	Local $aThresholds = SmartAttackPolicyHeroAbilityThresholds($iHeroIndex)
	If $aThresholds[0] < 0 Or $aThresholds[1] < 0 Then Return $aDecision

	$aDecision[$SMART_ATTACK_HERO_ELAPSED_THRESHOLD_MS] = $aThresholds[0]
	$aDecision[$SMART_ATTACK_HERO_DAMAGE_THRESHOLD_PERCENT] = $aThresholds[1]
	If IsNumber($iElapsedMs) And $iElapsedMs >= 0 Then _
			$aDecision[$SMART_ATTACK_HERO_ELAPSED_DUE] = $iElapsedMs >= $aThresholds[0]
	If IsNumber($iDamagePercent) And $iDamagePercent >= 0 And $iDamagePercent <= 100 Then _
			$aDecision[$SMART_ATTACK_HERO_DAMAGE_DUE] = $iDamagePercent >= $aThresholds[1]

	If $aDecision[$SMART_ATTACK_HERO_DAMAGE_DUE] And $aDecision[$SMART_ATTACK_HERO_ELAPSED_DUE] Then
		$aDecision[$SMART_ATTACK_HERO_ACTIVATE] = True
		$aDecision[$SMART_ATTACK_HERO_REASON] = "damage+elapsed"
	ElseIf $aDecision[$SMART_ATTACK_HERO_DAMAGE_DUE] Then
		$aDecision[$SMART_ATTACK_HERO_ACTIVATE] = True
		$aDecision[$SMART_ATTACK_HERO_REASON] = "damage"
	ElseIf $aDecision[$SMART_ATTACK_HERO_ELAPSED_DUE] Then
		$aDecision[$SMART_ATTACK_HERO_ACTIVATE] = True
		$aDecision[$SMART_ATTACK_HERO_REASON] = "elapsed"
	EndIf
	Return $aDecision
EndFunc   ;==>SmartAttackPolicyHeroAbilityDecision

; Selects the lowest visual slot number containing the requested troop/spell
; index with a positive amount and numeric click coordinates. Output:
; [FOUND, ROW, TROOP_INDEX, SLOT, AMOUNT, X, Y, REASON].
Func SmartAttackPolicySelectAttackBarSlot(ByRef $aAttackBar, $iTroopIndex)
	Local $aDecision[$SMART_ATTACK_SLOT_RESULT_SIZE] = [False, -1, $iTroopIndex, -1, 0, -1, -1, "slot-not-found"]
	If Not IsArray($aAttackBar) Or UBound($aAttackBar, 0) <> 2 Or UBound($aAttackBar, 2) < 5 Then
		$aDecision[$SMART_ATTACK_SLOT_REASON] = "invalid-attack-bar"
		Return $aDecision
	EndIf

	For $i = 0 To UBound($aAttackBar, 1) - 1
		If $aAttackBar[$i][0] <> $iTroopIndex Then ContinueLoop
		If Not IsNumber($aAttackBar[$i][1]) Or Not IsNumber($aAttackBar[$i][2]) Or $aAttackBar[$i][2] <= 0 Then ContinueLoop
		If Not IsNumber($aAttackBar[$i][3]) Or Not IsNumber($aAttackBar[$i][4]) Then ContinueLoop
		If $aDecision[$SMART_ATTACK_SLOT_FOUND] And $aAttackBar[$i][1] >= $aDecision[$SMART_ATTACK_SLOT_NUMBER] Then ContinueLoop

		$aDecision[$SMART_ATTACK_SLOT_FOUND] = True
		$aDecision[$SMART_ATTACK_SLOT_ROW] = $i
		$aDecision[$SMART_ATTACK_SLOT_NUMBER] = $aAttackBar[$i][1]
		$aDecision[$SMART_ATTACK_SLOT_AMOUNT] = $aAttackBar[$i][2]
		$aDecision[$SMART_ATTACK_SLOT_X] = $aAttackBar[$i][3]
		$aDecision[$SMART_ATTACK_SLOT_Y] = $aAttackBar[$i][4]
		$aDecision[$SMART_ATTACK_SLOT_REASON] = "slot-selected"
	Next
	Return $aDecision
EndFunc   ;==>SmartAttackPolicySelectAttackBarSlot

; Accepts only an exact one-spell decrement. A missing post-cast portrait proves
; consumption only when the pre-cast stack contained exactly one spell.
Func SmartAttackPolicySpellQuantityProved($iBefore, $bAfterFound, $iAfter)
	If Not IsNumber($iBefore) Or $iBefore <= 0 Or Int($iBefore) <> $iBefore Then Return False
	If Not $bAfterFound Then Return $iBefore = 1
	If Not IsNumber($iAfter) Or $iAfter < 0 Or Int($iAfter) <> $iAfter Then Return False
	Return $iAfter = $iBefore - 1
EndFunc   ;==>SmartAttackPolicySpellQuantityProved

; Rage schedule: ordinal 0/1/2 at 0/7s/14s and progress .35/.60/.82.
; Inputs: zero-based next ordinal, initial available count, elapsed since main
; entry deployment, and a Boolean safe-target proof. Output:
; [CAST, REASON, DUE_MS, TARGET_PROGRESS, ORDINAL].
Func SmartAttackPolicyRageDecision($iOrdinal, $iAvailableCount, $iElapsedMs, $bTargetSafe)
	Local $aDecision[$SMART_ATTACK_SPELL_RESULT_SIZE] = [False, "invalid-input", -1, -1, $iOrdinal]
	If Not IsNumber($iOrdinal) Or $iOrdinal < 0 Or Int($iOrdinal) <> $iOrdinal Then Return $aDecision

	Switch $iOrdinal
		Case 0
			$aDecision[$SMART_ATTACK_SPELL_DUE_MS] = $SMART_ATTACK_RAGE_FIRST_DUE_MS
			$aDecision[$SMART_ATTACK_SPELL_TARGET_PROGRESS] = $SMART_ATTACK_RAGE_FIRST_PROGRESS
		Case 1
			$aDecision[$SMART_ATTACK_SPELL_DUE_MS] = $SMART_ATTACK_RAGE_SECOND_DUE_MS
			$aDecision[$SMART_ATTACK_SPELL_TARGET_PROGRESS] = $SMART_ATTACK_RAGE_SECOND_PROGRESS
		Case 2
			$aDecision[$SMART_ATTACK_SPELL_DUE_MS] = $SMART_ATTACK_RAGE_THIRD_DUE_MS
			$aDecision[$SMART_ATTACK_SPELL_TARGET_PROGRESS] = $SMART_ATTACK_RAGE_THIRD_PROGRESS
		Case Else
			$aDecision[$SMART_ATTACK_SPELL_REASON] = "schedule-exhausted"
			Return $aDecision
	EndSwitch

	Return _SmartAttackPolicyFinishSpellDecision($aDecision, $iAvailableCount, $iElapsedMs, $bTargetSafe)
EndFunc   ;==>SmartAttackPolicyRageDecision

; Freeze schedule: next available Freeze at 8s, then every 4s. Its target is a
; caller-supplied, independently proven core point, so TARGET_PROGRESS is 1.0. Output shape is
; identical to SmartAttackPolicyRageDecision.
Func SmartAttackPolicyFreezeDecision($iOrdinal, $iAvailableCount, $iElapsedMs, $bTargetSafe)
	Local $aDecision[$SMART_ATTACK_SPELL_RESULT_SIZE] = [False, "invalid-input", -1, 1.0, $iOrdinal]
	If Not IsNumber($iOrdinal) Or $iOrdinal < 0 Or Int($iOrdinal) <> $iOrdinal Then Return $aDecision
	$aDecision[$SMART_ATTACK_SPELL_DUE_MS] = $SMART_ATTACK_FREEZE_FIRST_DUE_MS + ($iOrdinal * $SMART_ATTACK_FREEZE_INTERVAL_MS)
	Return _SmartAttackPolicyFinishSpellDecision($aDecision, $iAvailableCount, $iElapsedMs, $bTargetSafe)
EndFunc   ;==>SmartAttackPolicyFreezeDecision

Func _SmartAttackPolicyFinishSpellDecision(ByRef $aDecision, $iAvailableCount, $iElapsedMs, $bTargetSafe)
	If Not IsNumber($iAvailableCount) Or $iAvailableCount < 0 Or Int($iAvailableCount) <> $iAvailableCount Or _
			Not IsNumber($iElapsedMs) Or $iElapsedMs < 0 Then Return $aDecision
	If $aDecision[$SMART_ATTACK_SPELL_ORDINAL] >= $iAvailableCount Then
		$aDecision[$SMART_ATTACK_SPELL_REASON] = "no-spell-available"
		Return $aDecision
	EndIf
	If $iElapsedMs < $aDecision[$SMART_ATTACK_SPELL_DUE_MS] Then
		$aDecision[$SMART_ATTACK_SPELL_REASON] = "not-due"
		Return $aDecision
	EndIf
	If Not IsBool($bTargetSafe) Then
		$aDecision[$SMART_ATTACK_SPELL_REASON] = "target-safety-required"
		Return $aDecision
	EndIf
	If Not $bTargetSafe Then
		$aDecision[$SMART_ATTACK_SPELL_REASON] = "unsafe-target"
		Return $aDecision
	EndIf

	$aDecision[$SMART_ATTACK_SPELL_CAST] = True
	$aDecision[$SMART_ATTACK_SPELL_REASON] = "cast"
	Return $aDecision
EndFunc   ;==>_SmartAttackPolicyFinishSpellDecision

Func _SmartAttackPolicyCandidateMetrics(ByRef $aPoints, $iMinValidPoints)
	Local $aMetrics[$SMART_ATTACK_CANDIDATE_SIZE] = [False, 0, -1, -1]
	Local $iPointCount = _SmartAttackPolicyValidPointCount($aPoints)
	$aMetrics[$SMART_ATTACK_CANDIDATE_POINT_COUNT] = $iPointCount
	If $iPointCount < $iMinValidPoints Then Return $aMetrics

	Local $iFirstMedianIndex = Int(($iPointCount - 1) / 2)
	Local $iSecondMedianIndex = Int($iPointCount / 2)
	Local $fFirstX = 0, $fFirstY = 0, $fSecondX = 0, $fSecondY = 0
	If Not _SmartAttackPolicyValidPointAt($aPoints, $iFirstMedianIndex, $fFirstX, $fFirstY) Then Return $aMetrics
	If Not _SmartAttackPolicyValidPointAt($aPoints, $iSecondMedianIndex, $fSecondX, $fSecondY) Then Return $aMetrics

	$aMetrics[$SMART_ATTACK_CANDIDATE_VALID] = True
	$aMetrics[$SMART_ATTACK_CANDIDATE_MEDIAN_X] = ($fFirstX + $fSecondX) / 2
	$aMetrics[$SMART_ATTACK_CANDIDATE_MEDIAN_Y] = ($fFirstY + $fSecondY) / 2
	Return $aMetrics
EndFunc   ;==>_SmartAttackPolicyCandidateMetrics

Func _SmartAttackPolicyConsiderSide(ByRef $aMetrics, $iSide, $bUseTownHall, $iTownHallX, $iTownHallY, _
		ByRef $iBestSide, ByRef $fBestScore, ByRef $iBestPointCount, ByRef $fBestMedianX, ByRef $fBestMedianY)
	If Not $aMetrics[$SMART_ATTACK_CANDIDATE_VALID] Then Return

	Local $fScore = $aMetrics[$SMART_ATTACK_CANDIDATE_POINT_COUNT]
	Local $bBetter = $iBestSide = $SMART_ATTACK_SIDE_NONE Or $fScore > $fBestScore
	If $bUseTownHall Then
		Local $fDeltaX = $aMetrics[$SMART_ATTACK_CANDIDATE_MEDIAN_X] - $iTownHallX
		Local $fDeltaY = $aMetrics[$SMART_ATTACK_CANDIDATE_MEDIAN_Y] - $iTownHallY
		$fScore = ($fDeltaX * $fDeltaX) + ($fDeltaY * $fDeltaY)
		$bBetter = $iBestSide = $SMART_ATTACK_SIDE_NONE Or $fScore < $fBestScore
	EndIf
	If Not $bBetter Then Return

	$iBestSide = $iSide
	$fBestScore = $fScore
	$iBestPointCount = $aMetrics[$SMART_ATTACK_CANDIDATE_POINT_COUNT]
	$fBestMedianX = $aMetrics[$SMART_ATTACK_CANDIDATE_MEDIAN_X]
	$fBestMedianY = $aMetrics[$SMART_ATTACK_CANDIDATE_MEDIAN_Y]
EndFunc   ;==>_SmartAttackPolicyConsiderSide

Func _SmartAttackPolicyValidPointCount(ByRef $aPoints)
	If Not IsArray($aPoints) Then Return 0
	Local $iDimensions = UBound($aPoints, 0)
	Local $iCount = 0

	If $iDimensions = 2 Then
		If UBound($aPoints, 2) < 2 Then Return 0
		For $i = 0 To UBound($aPoints, 1) - 1
			If IsNumber($aPoints[$i][0]) And IsNumber($aPoints[$i][1]) Then $iCount += 1
		Next
	ElseIf $iDimensions = 1 Then
		For $i = 0 To UBound($aPoints, 1) - 1
			Local $aPoint = $aPoints[$i]
			If IsArray($aPoint) And UBound($aPoint, 0) = 1 And UBound($aPoint, 1) >= 2 And _
					IsNumber($aPoint[0]) And IsNumber($aPoint[1]) Then $iCount += 1
		Next
	EndIf
	Return $iCount
EndFunc   ;==>_SmartAttackPolicyValidPointCount

Func _SmartAttackPolicyValidPointAt(ByRef $aPoints, $iValidIndex, ByRef $fX, ByRef $fY)
	If Not IsArray($aPoints) Or Not IsNumber($iValidIndex) Or $iValidIndex < 0 Then Return False
	Local $iDimensions = UBound($aPoints, 0)
	Local $iSeen = 0

	If $iDimensions = 2 Then
		If UBound($aPoints, 2) < 2 Then Return False
		For $i = 0 To UBound($aPoints, 1) - 1
			If Not IsNumber($aPoints[$i][0]) Or Not IsNumber($aPoints[$i][1]) Then ContinueLoop
			If $iSeen = $iValidIndex Then
				$fX = $aPoints[$i][0]
				$fY = $aPoints[$i][1]
				Return True
			EndIf
			$iSeen += 1
		Next
	ElseIf $iDimensions = 1 Then
		For $i = 0 To UBound($aPoints, 1) - 1
			Local $aPoint = $aPoints[$i]
			If Not IsArray($aPoint) Or UBound($aPoint, 0) <> 1 Or UBound($aPoint, 1) < 2 Or _
					Not IsNumber($aPoint[0]) Or Not IsNumber($aPoint[1]) Then ContinueLoop
			If $iSeen = $iValidIndex Then
				$fX = $aPoint[0]
				$fY = $aPoint[1]
				Return True
			EndIf
			$iSeen += 1
		Next
	EndIf
	Return False
EndFunc   ;==>_SmartAttackPolicyValidPointAt
