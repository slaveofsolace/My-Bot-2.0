#NoTrayIcon
; Focused contract tests for the own-village fail-closed gate used by planned runs.
#include "..\..\COCBot\functions\Run\RunVillageReadiness.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Local $sError = ""
RunVillageReadinessResetIdentity()
AssertTrue(Not RunVillageReadinessIdentityVerified(17), "identity starts unverified")
AssertTrue(RunVillageReadinessMarkIdentityVerified(17), "fresh TH17 identity can be latched")
AssertTrue(RunVillageReadinessIdentityVerified(17), "latched identity is bound to TH17")
AssertTrue(RunVillageReadinessIdentitySource() = "template", "fresh visual identity records its template source")
AssertTrue(Not RunVillageReadinessIdentityVerified(16), "latched identity cannot authorize another level")
AssertTrue(RunVillageReadinessValidate(17, True, 17, $sError, RunVillageReadinessIdentityVerified(17)), _
	"supported TH with fresh identity and valid coordinates is ready: " & $sError)
AssertTrue(RunVillageReadinessValidate(17, True, 17, $sError, RunVillageReadinessIdentityVerified(17), False), _
	"identity-only current-army readiness does not require legacy coordinates: " & $sError)
AssertTrue(RunVillageReadinessValidate(17, True, 17, $sError, True, False, 17, "template"), _
	"freshly detected TH17 matches a plan pinned to TH17: " & $sError)
AssertTrue(Not RunVillageReadinessValidate(17, True, 17, $sError, True, False, 16, "template"), _
	"planned Town Hall mismatch fails closed")
AssertTrue(StringInStr($sError, "planned TH16") > 0 And StringInStr($sError, "TH17") > 0, _
	"Town Hall mismatch names both plan and account")
AssertTrue(Not RunVillageReadinessValidate(17, True, 17, $sError, True, False, 17, "main-screen-profile"), _
	"a pinned Town Hall cannot be authorized by profile attestation")
AssertTrue(StringInStr($sError, "fresh own-village template") > 0, "pinned-plan evidence error is actionable")
AssertTrue(Not RunVillageReadinessValidate(0, True, 17, $sError, True), "unknown Town Hall level is rejected")
AssertTrue(StringInStr($sError, "not detected") > 0, "unknown-level error is actionable")
AssertTrue(Not RunVillageReadinessValidate(18, True, 17, $sError, True), "Town Hall above the engine maximum is rejected")
AssertTrue(StringInStr($sError, "supported maximum TH17") > 0, "unsupported-level error names the boundary")
AssertTrue(Not RunVillageReadinessValidate(17, True, 17, $sError, False), "saved level without fresh identity is rejected")
AssertTrue(StringInStr($sError, "identity") > 0 And StringInStr($sError, "verified") > 0, "identity error is actionable")
AssertTrue(Not RunVillageReadinessValidate(17, False, 17, $sError, True), "invalid required coordinates are rejected")
AssertTrue(StringInStr($sError, "coordinates are invalid") > 0, "coordinate error is actionable")
AssertTrue(Not RunVillageReadinessValidate(17, True, 1, $sError, True), "invalid engine support range fails closed")
RunVillageReadinessResetIdentity()
AssertTrue(Not RunVillageReadinessIdentityVerified(17), "identity reset prevents reuse across planned starts")
AssertTrue(RunVillageReadinessIdentitySource() = "", "identity reset clears its evidence source")
AssertTrue(RunVillageReadinessMarkMainScreenProfileAttested(17, 17), "proven main-screen current-army mode can attest a supported profile TH")
AssertTrue(RunVillageReadinessIdentityVerified(17), "main-screen/profile attestation authorizes only its supported TH")
AssertTrue(RunVillageReadinessIdentitySource() = "main-screen-profile", "profile attestation is explicitly distinguishable from a template match")
AssertTrue(Not RunVillageReadinessMarkMainScreenProfileAttested(18, 17), "profile attestation rejects a TH above engine support")
AssertTrue(Not RunVillageReadinessIdentityVerified(17), "a rejected attestation leaves no stale identity")

ConsoleWrite("RunVillageReadinessTest passed " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
