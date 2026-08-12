#NoTrayIcon
#include "..\..\COCBot\functions\Attack\Attack Algorithms\SmartAttackPolicy.au3"

Opt("MustDeclareVars", 1)

Global $g_iSmartPolicyAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iSmartPolicyAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 20
	EndIf
EndFunc   ;==>AssertTrue

Func AssertEqual($vActual, $vExpected, $sMessage)
	AssertTrue($vActual = $vExpected, $sMessage & " (actual=" & $vActual & ", expected=" & $vExpected & ")")
EndFunc   ;==>AssertEqual

; Active base: TR path median is closest to the unique TH.
Local $aBR[3][2] = [[700, 600], [750, 650], [800, 700]]
Local $aBL[4][2] = [[60, 650], [90, 620], [120, 590], [150, 560]]
Local $aTR[3][2] = [[700, 150], [750, 200], [800, 250]]
Local $aTL[3][2] = [[60, 250], [110, 200], [160, 150]]
Local $aSide = SmartAttackPolicyChooseSide($aBR, $aBL, $aTR, $aTL, $SMART_ATTACK_BASE_ACTIVE, True, 760, 210)
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_TR, "active base chooses nearest path median")
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_NAME], "TR", "side exposes stable string")
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_SCORE], 200, "side exposes squared TH distance")
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_POINT_COUNT], 3, "side exposes valid point count")
AssertTrue($aSide[$SMART_ATTACK_SIDE_RESULT_USES_TOWN_HALL], "active unique TH decision records TH use")

; Production red-line globals use a one-dimensional array of [x,y] arrays.
Local $aNestedBRPoint0[2] = [700, 600]
Local $aNestedBRPoint1[2] = [750, 650]
Local $aNestedBRPoint2[2] = [800, 700]
Local $aNestedBR[3] = [$aNestedBRPoint0, $aNestedBRPoint1, $aNestedBRPoint2]
Local $aNestedBLPoint0[2] = [60, 650]
Local $aNestedBLPoint1[2] = [90, 620]
Local $aNestedBLPoint2[2] = [120, 590]
Local $aNestedBLPoint3[2] = [150, 560]
Local $aNestedBL[4] = [$aNestedBLPoint0, $aNestedBLPoint1, $aNestedBLPoint2, $aNestedBLPoint3]
Local $aNestedTRPoint0[2] = [700, 150]
Local $aNestedTRPoint1[2] = [750, 200]
Local $aNestedTRPoint2[2] = [800, 250]
Local $aNestedTR[3] = [$aNestedTRPoint0, $aNestedTRPoint1, $aNestedTRPoint2]
Local $aNestedTLPoint0[2] = [60, 250]
Local $aNestedTLPoint1[2] = [110, 200]
Local $aNestedTLPoint2[2] = [160, 150]
Local $aNestedTL[3] = [$aNestedTLPoint0, $aNestedTLPoint1, $aNestedTLPoint2]
Local $aNestedSide = SmartAttackPolicyChooseSide($aNestedBR, $aNestedBL, $aNestedTR, $aNestedTL, _
		$SMART_ATTACK_BASE_ACTIVE, True, 760, 210)
AssertEqual($aNestedSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_TR, "production point-array shape chooses nearest median")
AssertEqual($aNestedSide[$SMART_ATTACK_SIDE_RESULT_POINT_COUNT], 3, "production point-array shape counts valid points")

; Equal active scores retain BR, BL, TR, TL order.
Local $aTieBR[1][2] = [[20, 10]]
Local $aTieBL[1][2] = [[0, 10]]
Local $aTieTR[1][2] = [[10, 0]]
Local $aTieTL[1][2] = [[10, 20]]
$aSide = SmartAttackPolicyChooseSide($aTieBR, $aTieBL, $aTieTR, $aTieTL, $SMART_ATTACK_BASE_ACTIVE, True, 10, 10)
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_BR, "active tie chooses BR")

; Dead, unknown, and active-without-unique-TH all choose the longest valid path.
$aSide = SmartAttackPolicyChooseSide($aBR, $aBL, $aTR, $aTL, $SMART_ATTACK_BASE_DEAD, False, -1, -1)
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_BL, "dead base chooses longest side")
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_SCORE], 4, "longest-side score is valid point count")
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_REASON], "longest-valid-side-dead-base", "dead base reason is explicit")
$aSide = SmartAttackPolicyChooseSide($aBR, $aBL, $aTR, $aTL, $SMART_ATTACK_BASE_UNKNOWN, False, -1, -1)
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_BL, "unknown base chooses longest side")
$aSide = SmartAttackPolicyChooseSide($aBR, $aBL, $aTR, $aTL, $SMART_ATTACK_BASE_ACTIVE, False, 760, 210)
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_BL, "active non-unique TH falls back to longest side")
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_REASON], "longest-valid-side-no-unique-town-hall", "TH ambiguity is explicit")

Local $aEmpty[0][2]
$aSide = SmartAttackPolicyChooseSide($aTieBR, $aEmpty, $aEmpty, $aEmpty, $SMART_ATTACK_BASE_UNKNOWN, False, -1, -1, 2)
AssertEqual($aSide[$SMART_ATTACK_SIDE_RESULT_ID], $SMART_ATTACK_SIDE_NONE, "minimum point gate fails closed")

; Exact linear target points and external safety proof.
Local $aTarget = SmartAttackPolicyTargetPoint(430, 700, 430, 300, 0.50)
Local $iTargetError = @error
AssertEqual($iTargetError, 0, "valid target interpolation succeeds")
AssertEqual($aTarget[0], 430, "target X interpolates")
AssertEqual($aTarget[1], 500, "target Y interpolates")
Local $aTargetDecision = SmartAttackPolicyTargetSafetyDecision($aTarget, True)
AssertTrue($aTargetDecision[$SMART_ATTACK_TARGET_SAFE], "safe-coordinate proof is accepted")
$aTargetDecision = SmartAttackPolicyTargetSafetyDecision($aTarget, False)
AssertTrue(Not $aTargetDecision[$SMART_ATTACK_TARGET_SAFE], "unsafe coordinate fails closed")
AssertEqual($aTargetDecision[$SMART_ATTACK_TARGET_REASON], "unsafe-target", "unsafe reason is explicit")
Local $aInvalidTarget = SmartAttackPolicyTargetPoint(430, 700, 430, 300, 1.01)
$iTargetError = @error
AssertEqual($iTargetError, 1, "out-of-range progress fails")
AssertEqual($aInvalidTarget[0], -1, "invalid target carries sentinel")

; Third input is total enemy-base destruction; each Hero has its own milestone.
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_WARDEN, 9999, 11), "", "Warden is not due below 10s and 12 percent")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_WARDEN, 9999, 12), "damage", "Warden activates at 12 percent destruction")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_WARDEN, 10000, 11), "elapsed", "Warden activates at 10 seconds")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_PRINCE, 17999, 24), "", "Prince is not due below 18s and 25 percent")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_PRINCE, 17999, 25), "damage", "Prince activates at 25 percent destruction")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_PRINCE, 18000, 24), "elapsed", "Prince activates at 18 seconds")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_QUEEN, 23999, 34), "", "Queen is not due below 24s and 35 percent")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_QUEEN, 23999, 35), "damage", "Queen activates at 35 percent destruction")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_QUEEN, 24000, 34), "elapsed", "Queen activates at 24 seconds")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_CHAMPION, 29999, 44), "", "Champion is not due below 30s and 45 percent")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_CHAMPION, 29999, 45), "damage", "Champion activates at 45 percent destruction")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_CHAMPION, 30000, 44), "elapsed", "Champion activates at 30 seconds")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_KING, 33999, 49), "", "King is not due below 34s and 50 percent")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_KING, 33999, 50), "damage", "King activates at 50 percent destruction")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_KING, 34000, 49), "elapsed", "King activates at 34 seconds")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_KING, 34000, 50), "damage+elapsed", "both hero reasons are retained")
AssertEqual(SmartAttackPolicyHeroAbilityReason($SMART_ATTACK_HERO_WARDEN, 10000, -1), "elapsed", "elapsed proof works with unknown battle damage")
AssertEqual(SmartAttackPolicyHeroAbilityReason(99, 99999, 100), "", "unknown Hero fails closed")

; Lowest live visual slot wins for the requested spell index.
Local $aAttackBar[4][7] = [[99, 4, 1, 400, 600, 0, 0], [6, 5, 2, 450, 600, 0, 0], [6, 2, 1, 300, 600, 0, 0], [7, 1, 3, 250, 600, 0, 0]]
Local $aSlot = SmartAttackPolicySelectAttackBarSlot($aAttackBar, 6)
AssertTrue($aSlot[$SMART_ATTACK_SLOT_FOUND], "requested spell slot is found")
AssertEqual($aSlot[$SMART_ATTACK_SLOT_ROW], 2, "lowest slot row is selected")
AssertEqual($aSlot[$SMART_ATTACK_SLOT_NUMBER], 2, "lowest slot number is selected")
AssertEqual($aSlot[$SMART_ATTACK_SLOT_AMOUNT], 1, "slot amount is returned")
AssertEqual($aSlot[$SMART_ATTACK_SLOT_X], 300, "slot click X is returned")
$aSlot = SmartAttackPolicySelectAttackBarSlot($aAttackBar, 8)
AssertTrue(Not $aSlot[$SMART_ATTACK_SLOT_FOUND], "missing spell fails closed")

; Rage: fixed three-cast schedule and target progress.
Local $aSpell = SmartAttackPolicyRageDecision(0, 3, 0, True)
AssertTrue($aSpell[$SMART_ATTACK_SPELL_CAST], "first Rage is due immediately")
AssertEqual($aSpell[$SMART_ATTACK_SPELL_TARGET_PROGRESS], 0.35, "first Rage target progress is fixed")
$aSpell = SmartAttackPolicyRageDecision(1, 3, 6999, True)
AssertTrue(Not $aSpell[$SMART_ATTACK_SPELL_CAST], "second Rage waits seven seconds")
AssertEqual($aSpell[$SMART_ATTACK_SPELL_REASON], "not-due", "early Rage reason is explicit")
$aSpell = SmartAttackPolicyRageDecision(1, 3, 7000, True)
AssertTrue($aSpell[$SMART_ATTACK_SPELL_CAST], "second Rage threshold is inclusive")
AssertEqual($aSpell[$SMART_ATTACK_SPELL_TARGET_PROGRESS], 0.60, "second Rage target progress is fixed")
$aSpell = SmartAttackPolicyRageDecision(2, 3, 14000, False)
AssertTrue(Not $aSpell[$SMART_ATTACK_SPELL_CAST], "unsafe Rage target fails closed")
AssertEqual($aSpell[$SMART_ATTACK_SPELL_REASON], "unsafe-target", "unsafe Rage reason is explicit")
$aSpell = SmartAttackPolicyRageDecision(1, 1, 7000, True)
AssertEqual($aSpell[$SMART_ATTACK_SPELL_REASON], "no-spell-available", "spell count bounds ordinal")
$aSpell = SmartAttackPolicyRageDecision(3, 4, 30000, True)
AssertEqual($aSpell[$SMART_ATTACK_SPELL_REASON], "schedule-exhausted", "Rage schedule is bounded to three")

; Freeze: first at 8s and then every 4s.
$aSpell = SmartAttackPolicyFreezeDecision(0, 3, 7999, True)
AssertEqual($aSpell[$SMART_ATTACK_SPELL_REASON], "not-due", "first Freeze waits eight seconds")
$aSpell = SmartAttackPolicyFreezeDecision(0, 3, 8000, True)
AssertTrue($aSpell[$SMART_ATTACK_SPELL_CAST], "first Freeze threshold is inclusive")
$aSpell = SmartAttackPolicyFreezeDecision(2, 3, 15999, True)
AssertTrue(Not $aSpell[$SMART_ATTACK_SPELL_CAST], "third Freeze waits sixteen seconds")
$aSpell = SmartAttackPolicyFreezeDecision(2, 3, 16000, True)
AssertTrue($aSpell[$SMART_ATTACK_SPELL_CAST], "third Freeze threshold is inclusive")
AssertEqual($aSpell[$SMART_ATTACK_SPELL_DUE_MS], 16000, "Freeze interval is deterministic")

ConsoleWrite("SmartAttackPolicyTest passed " & $g_iSmartPolicyAssertions & " assertions" & @CRLF)
Exit 0
