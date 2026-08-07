#NoTrayIcon
; Contract tests for Hero loadouts, attack quotas, run intents, and the verification latch.
; These run on the generated catalog, so a catalog change that breaks the engine fails here rather than in the field.
#include <StringConstants.au3>
#include <Array.au3>
#include "..\..\COCBot\functions\Run\RunIntent.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Local $sError = "", $sReason = ""

; ---------------------------------------------------------------------------------------------------------------
; Hero loadout: six Heroes exist, four may be active, Town Hall gates membership.
; ---------------------------------------------------------------------------------------------------------------
Local $oLoadout = HeroLoadoutCreate(18)
AssertTrue(IsObj($oLoadout), "hero loadout is created")
AssertTrue(HeroLoadoutValidate($oLoadout, $sError), "empty loadout validates: " & $sError)
AssertTrue(Int($oLoadout.Item("max_slots")) = 4, "loadout exposes four active slots")

AssertTrue(HeroLoadoutAdd($oLoadout, "barbarian-king", $sError), "Barbarian King is added: " & $sError)
AssertTrue(HeroLoadoutAdd($oLoadout, "archer-queen", $sError), "Archer Queen is added: " & $sError)
AssertTrue(HeroLoadoutAdd($oLoadout, "dragon-duke", $sError), "Dragon Duke is added at TH18: " & $sError)
AssertTrue(Not HeroLoadoutAdd($oLoadout, "archer-queen", $sError), "duplicate Hero is rejected")
AssertTrue(Not HeroLoadoutAdd($oLoadout, "not-a-hero", $sError), "unknown Hero is rejected")
AssertTrue(HeroLoadoutCount($oLoadout) = 3, "three Heroes are selected")
AssertTrue(HeroLoadoutAdd($oLoadout, "grand-warden", $sError), "fourth Hero fills the last slot: " & $sError)
AssertTrue(Not HeroLoadoutAdd($oLoadout, "royal-champion", $sError), "fifth Hero exceeds four active slots")
AssertTrue(HeroLoadoutRemove($oLoadout, "grand-warden"), "Hero can be removed")
AssertTrue(HeroLoadoutCount($oLoadout) = 3, "count follows removal")

; Dropping the Town Hall releases Heroes the player could not actually field.
AssertTrue(HeroLoadoutSetTownHall($oLoadout, 5, $sError), "Town Hall can be lowered: " & $sError)
AssertTrue(Not HeroLoadoutContains($oLoadout, "dragon-duke"), "Dragon Duke is released below Town Hall 15")
AssertTrue(HeroLoadoutContains($oLoadout, "barbarian-king"), "Barbarian King survives at Town Hall 5")
AssertTrue(HeroLoadoutValidate($oLoadout, $sError), "loadout still validates after downgrade: " & $sError)

Local $aAvailable = HeroLoadoutAvailable(18)
AssertTrue(UBound($aAvailable) = 6, "all six Heroes are available at Town Hall 18")
Local $aEarly = HeroLoadoutAvailable(4)
AssertTrue(UBound($aEarly) = 1, "only the Barbarian King is available at Town Hall 4")

; ---------------------------------------------------------------------------------------------------------------
; Attack quota: a published maximum is not a remaining count.
; ---------------------------------------------------------------------------------------------------------------
Local $oRegular = BattleQuotaCreate("regular")
AssertTrue(IsObj($oRegular), "regular quota is created")
AssertTrue(BattleQuotaIsUnlimited($oRegular), "regular battles are unlimited")
AssertTrue(BattleQuotaCanConsume($oRegular, $sReason), "unlimited surface can always attack")

Local $oLegend = BattleQuotaCreate("legend-i")
AssertTrue(IsObj($oLegend), "legend quota is created")
AssertTrue(Int($oLegend.Item("published_maximum")) = 8, "Legend I publishes eight attacks per League Day")
AssertTrue(Not $oLegend.Item("verified"), "finite quota starts unobserved")
AssertTrue(Not BattleQuotaCanConsume($oLegend, $sReason), "finite quota blocks before observation")
AssertTrue(StringInStr($sReason, "not been read") > 0, "block reason names the missing observation")
AssertTrue(Not BattleQuotaObserve($oLegend, 9, 1000, $sError), "observation above the published maximum is rejected")
AssertTrue(BattleQuotaObserve($oLegend, 3, 1000, $sError), "observed remaining count is accepted: " & $sError)
AssertTrue(BattleQuotaRemaining($oLegend) = 3, "remaining count reflects the observation, not the maximum")
AssertTrue(BattleQuotaConsume($oLegend, $sError), "attack consumes one remaining: " & $sError)
AssertTrue(BattleQuotaRemaining($oLegend) = 2, "remaining decrements")
AssertTrue(BattleQuotaConsume($oLegend, $sError), "second attack consumes")
AssertTrue(BattleQuotaConsume($oLegend, $sError), "third attack consumes")
AssertTrue(Not BattleQuotaConsume($oLegend, $sError), "exhausted quota refuses a fourth attack")
AssertTrue(BattleQuotaIsExhausted($oLegend), "quota reports exhaustion")

; ---------------------------------------------------------------------------------------------------------------
; Run intent: exact surface binding and the diagnostic escape hatch.
; ---------------------------------------------------------------------------------------------------------------
Local $oPlan = RunPlanCreateDefault("legend", "fixture-strategy")
Local $oIntentLoadout = HeroLoadoutCreate(18)
AssertTrue(HeroLoadoutAdd($oIntentLoadout, "barbarian-king", $sError), "intent loadout is populated: " & $sError)

Local $oIntent = RunIntentCreate($oPlan, "legend-ii", $oIntentLoadout, $sError)
AssertTrue(IsObj($oIntent), "run intent is created: " & $sError)
AssertTrue($oIntent.Item("surface_id") = "legend-ii", "intent keeps the exact surface")

Local $oMismatch = RunIntentCreate($oPlan, "builder", $oIntentLoadout, $sError)
AssertTrue(Not IsObj($oMismatch), "surface that contradicts the plan mode is rejected")

; Undemonstrated surfaces are blocked by default, which is what makes the diagnostic opt-in meaningful.
AssertTrue(Not RunIntentCanStart($oIntent, $sReason), "intent is blocked before evidence")
AssertTrue(RunIntentVerificationState($oIntent) = $RUN_VERIFICATION_DIAGNOSTIC, "unproven surface reports as unverified")
AssertTrue(Not RunIntentEnableDiagnostic($oIntent, "", $sError), "diagnostic mode requires an acknowledgement")
AssertTrue(RunIntentEnableDiagnostic($oIntent, "operator observing first run", $sError), "diagnostic mode is enabled: " & $sError)

; With the evidence gate relaxed the quota gate still holds, because it is a client fact and not a missing fixture.
AssertTrue(Not RunIntentCanStart($oIntent, $sReason), "diagnostic mode does not bypass an unobserved quota")
AssertTrue(RunIntentObserveQuota($oIntent, 5, 2000, $sError), "quota observation is recorded: " & $sError)
AssertTrue(RunIntentCanStart($oIntent, $sReason), "intent starts once the quota is known")
AssertTrue(RunIntentVerificationState($oIntent) = $RUN_VERIFICATION_DIAGNOSTIC, "diagnostic mode never reports verified")

; ---------------------------------------------------------------------------------------------------------------
; Verification latch: a session that ran unverified work stays unverified.
; ---------------------------------------------------------------------------------------------------------------
AssertTrue(RunIntentSetProfile($oIntent, "profile-a"), "profile reference is attached")
Local $oSession = RunIntentOpenSession($oIntent, "engine-test", $sError)
AssertTrue(IsObj($oSession), "session opens from the intent: " & $sError)
AssertTrue(Not RunSessionIsVerified($oSession), "session inherits the unverified state")
AssertTrue($oSession.Item("account_profile_id") = "profile-a", "session carries the profile reference")
AssertTrue(StringStripWS($oSession.Item("verification_reason"), $STR_STRIPALL) <> "", "session records why it is unverified")

AssertTrue(RunSessionStart($oSession), "session starts")
AssertTrue(RunIntentRecordBattle($oIntent, $oSession, True, $sError, 500, 250, 10), "battle is recorded through the intent: " & $sError)
AssertTrue($oSession.Item("battle_count") = 1, "session counts the battle")
AssertTrue(BattleQuotaRemaining($oIntent.Item("quota")) = 4, "recording a battle consumes quota")

Local $oSnapshot = RunSessionSnapshot($oSession)
AssertTrue($oSnapshot.Item("verification_state") = $RUN_VERIFICATION_DIAGNOSTIC, "snapshot carries the unverified state")

; A verified session must never be reachable from a diagnostic one.
Local $oCleanPlan = RunPlanCreateDefault("regular", "fixture-strategy")
Local $oCleanSession = RunSessionCreate($oCleanPlan, "clean")
AssertTrue(RunSessionIsVerified($oCleanSession), "a fresh session starts verified")
AssertTrue(RunSessionMarkDiagnostic($oCleanSession, "observed manually"), "session can be latched to unverified")
AssertTrue(Not RunSessionIsVerified($oCleanSession), "latched session is unverified")
AssertTrue(RunVerificationMerge($RUN_VERIFICATION_VERIFIED, $RUN_VERIFICATION_DIAGNOSTIC) = $RUN_VERIFICATION_DIAGNOSTIC, "merging with unverified stays unverified")

; ---------------------------------------------------------------------------------------------------------------
; Events carry the verification state so a log can never imply a demonstrated result.
; ---------------------------------------------------------------------------------------------------------------
Local $oEvent = RunEventCreate("battle.completed", 1, 2000, "engine-test", "info", "Diagnostic battle", "profile-a", "legend", 1, 500, 250, 10, 0, $RUN_VERIFICATION_DIAGNOSTIC, "legend-ii")
AssertTrue(IsObj($oEvent), "diagnostic event is created")
Local $sJson = RunEventToJson($oEvent)
AssertTrue(StringInStr($sJson, Chr(34) & "verification_state" & Chr(34) & ":" & Chr(34) & $RUN_VERIFICATION_DIAGNOSTIC & Chr(34)) > 0, "event serializes the verification state")
AssertTrue(StringInStr($sJson, Chr(34) & "surface_id" & Chr(34) & ":" & Chr(34) & "legend-ii" & Chr(34)) > 0, "event serializes the exact surface")

Local $oBadEvent = RunEventCreate("battle.completed", 2, 3000, "engine-test", "info", "Bad state", "", "legend", 1, 0, 0, 0, 0, "totally-fine")
AssertTrue(Not IsObj($oBadEvent), "unknown verification state is rejected")

ConsoleWrite("Run engine tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
