#include "..\..\COCBot\functions\CreateArmy\PassiveCurrentArmyReadiness.au3"

Opt("MustDeclareVars", 1)

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 1
	EndIf
EndFunc   ;==>AssertTrue

Local $sError = ""
Local $iCurrent = 0, $iTotal = 0

AssertTrue(PassiveCurrentArmyRequirementsSupported(0, False, False, $sError), "troop-only passive proof is supported: " & $sError)
AssertTrue(Not PassiveCurrentArmyRequirementsSupported(1, False, False, $sError), "Hero wait fails closed")
AssertTrue(Not PassiveCurrentArmyRequirementsSupported(0, True, False, $sError), "spell wait fails closed")
AssertTrue(Not PassiveCurrentArmyRequirementsSupported(0, False, True, $sError), "siege wait fails closed")

AssertTrue(Not PassiveCurrentArmyCapacityParse("", $iCurrent, $iTotal, $sError), "empty OCR is rejected")
AssertTrue(Not PassiveCurrentArmyCapacityParse("340/340", $iCurrent, $iTotal, $sError), "wrong separator is rejected")
AssertTrue(Not PassiveCurrentArmyCapacityParse("9#9", $iCurrent, $iTotal, $sError), "capacity below ten is rejected")
AssertTrue(Not PassiveCurrentArmyCapacityParse("341#341", $iCurrent, $iTotal, $sError), "capacity not divisible by five is rejected")

AssertTrue(Not PassiveCurrentArmyCapacityProof("340#340", "335#340", $iCurrent, $iTotal, $sError), "mismatched observations are rejected")
AssertTrue(Not PassiveCurrentArmyCapacityProof("335#340", "335#340", $iCurrent, $iTotal, $sError), "matching partial army remains not ready")
AssertTrue(PassiveCurrentArmyCapacityProof("340#340", "340#340", $iCurrent, $iTotal, $sError), "two fresh full-capacity observations prove readiness: " & $sError)
AssertTrue($iCurrent = 340 And $iTotal = 340, "proof returns the fresh OCR values")
AssertTrue(PassiveCurrentArmyCapacityProof("345#340", "345#340", $iCurrent, $iTotal, $sError), "a matching over-capacity army is ready")

ConsoleWrite("PassiveCurrentArmyReadinessTest passed " & $g_iAssertions & " assertions" & @CRLF)
