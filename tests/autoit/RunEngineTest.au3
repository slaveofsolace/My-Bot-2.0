#NoTrayIcon
; Contract tests for Hero loadouts, attack quotas, run intents, and the verification latch.
; These run on the generated catalog, so a catalog change that breaks the engine fails here rather than in the field.
#include <StringConstants.au3>
#include <FileConstants.au3>
#include <Array.au3>
#include "..\..\COCBot\functions\Other\Json.au3"
#include "..\..\COCBot\functions\Run\RunIntent.au3"
#include "..\..\COCBot\functions\Run\RunPlanFile.au3"
#include "..\..\COCBot\functions\Run\RunExecutionContract.au3"
#include "..\..\COCBot\functions\Run\RunEventLog.au3"
#include "..\..\COCBot\functions\Run\RunProfileWriteGuard.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Func AttemptGuardedProfileWrite($sPath, $sValue)
	If Not RunProfileRegularConfigSerializationAllowed() Then Return False
	Return IniWrite($sPath, "attack", "ScriptDB", $sValue) <> 0
EndFunc   ;==>AttemptGuardedProfileWrite

Local $sError = "", $sReason = ""

; Selecting Heroes for a current-trained-army one-shot must deploy them without entering the Hero
; Hall readiness path that this mode intentionally cannot prove or mutate.
AssertTrue(RunExecutionHeroWaitMask(31, True, False) = 0, "current-army mode does not wait on selected Heroes")
AssertTrue(RunExecutionHeroWaitMask(31, False, True) = 0, "managed training does not wait when Wait for full army is off")
AssertTrue(RunExecutionHeroWaitMask(31, True, True) = 31, "managed training retains the selected Hero readiness mask")

; The Activity feed and native control status must identify one planned run with the same id.
AssertTrue(RunEventLogBindSession("run-session-a"), "event logger accepts the canonical run session id")
AssertTrue(RunEventLogSessionId() = "run-session-a", "event logger exposes the bound run session id")
Sleep(25)
Local $iFirstSessionElapsed = _RunEventLogNowMs()
AssertTrue($iFirstSessionElapsed >= 10, "event logger advances the active session clock")
AssertTrue(RunEventLogBindSession("run-session-b"), "event logger can bind a later canonical session")
AssertTrue(_RunEventLogNowMs() < $iFirstSessionElapsed, "a later session resets its timestamp origin")
AssertTrue(RunEventLogBindSession("run-session-a"), "event logger restores the first fixture session")
$g_iRunEventSequence = 7
AssertTrue(Not RunEventLogReleaseSession("run-session-b"), "a stale run cannot release the active event session")
AssertTrue(RunEventLogSessionId() = "run-session-a" And $g_iRunEventSequence = 7, "rejected release preserves event correlation")
AssertTrue(RunEventLogReleaseSession("run-session-a"), "the matching run releases its event session")
AssertTrue($g_sRunEventSessionId = "" And $g_iRunEventSequence = 0, "event session release clears id and sequence")
$g_iRunEventSequence = 5
AssertTrue(RunEventLogBattleCompleted(3, 100, 900, 800, 7, 21, 4), "battle telemetry is a successful no-op outside a planned session")
AssertTrue($g_iRunEventSequence = 5 And $g_iRunEventBattleIndex = 0, "an unbound battle cannot advance event correlation")
$g_iRunEventSequence = 0

; A planner run mutates live globals, but inherited runtime paths call SaveConfig while the bot is
; active. The shared guard must leave the on-disk profile byte-for-byte unchanged until restore.
Local $sGuardProfile = @TempDir & "\my-bot-run-profile-guard-" & @AutoItPID & ".ini"
FileDelete($sGuardProfile)
AssertTrue(IniWrite($sGuardProfile, "attack", "ScriptDB", "profile-script") <> 0, "profile guard fixture is written")
AssertTrue(IniWrite($sGuardProfile, "attack", "DBAtkAlgorithm", "0") <> 0, "profile guard algorithm fixture is written")
Local $sGuardBefore = FileRead($sGuardProfile)
Local $sLiveScript = "profile-script", $iLiveAlgorithm = 0
Local $sSnapshotScript = $sLiveScript, $iSnapshotAlgorithm = $iLiveAlgorithm
AssertTrue(RunProfileOverrideBegin(True, True, True), "profile override guard begins with captured serializer values")
$sLiveScript = "one-run-script"
$iLiveAlgorithm = 1
Local $aGuardGuiModes[2] = [1, 2]
For $iGuardGuiMode In $aGuardGuiModes
	AssertTrue(Not RunProfileRegularConfigSerializationAllowed(), "regular config is blocked with GUI mode " & $iGuardGuiMode)
Next
AssertTrue(Not AttemptGuardedProfileWrite($sGuardProfile, "one-run-script"), "profile serialization is refused while overrides are active")
AssertTrue($sLiveScript = "one-run-script" And $iLiveAlgorithm = 1, "routine save leaves active one-run values intact")
AssertTrue(FileRead($sGuardProfile) = $sGuardBefore, "refused save leaves the profile byte-for-byte unchanged")
AssertTrue(IniRead($sGuardProfile, "attack", "ScriptDB", "") = "profile-script", "refused save retains the original script key")
AssertTrue(RunProfileClanGamesEnabledForSerialization(False), "Clan Games serialization uses the captured profile value")
AssertTrue(RunProfileAutoLabUpgradeEnabledForSerialization(False), "building serialization uses the captured laboratory value")
AssertTrue(RunProfileDonateLikeCrazyForSerialization(False), "switch-account serialization uses the captured donation value")
$sLiveScript = $sSnapshotScript
$iLiveAlgorithm = $iSnapshotAlgorithm
AssertTrue(RunProfileOverrideEnd(), "profile override guard ends")
AssertTrue($sLiveScript = "profile-script" And $iLiveAlgorithm = 0, "completion restores the exact pre-run values")
AssertTrue(RunProfileRegularConfigSerializationAllowed(), "regular config serialization resumes after restore")
AssertTrue(Not RunProfileClanGamesEnabledForSerialization(False), "Clan Games serialization resumes using the current value")
AssertTrue(Not RunProfileAutoLabUpgradeEnabledForSerialization(False), "building serialization resumes using the current laboratory value")
AssertTrue(Not RunProfileDonateLikeCrazyForSerialization(False), "switch-account serialization resumes using the current donation value")
AssertTrue(FileRead($sGuardProfile) = $sGuardBefore, "restoring write permission does not mutate the profile")
FileDelete($sGuardProfile)

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
Local $oDetectedLoadout = HeroLoadoutCreate(0)
AssertTrue(HeroLoadoutAdd($oDetectedLoadout, "archer-queen", $sError), "auto-TH plan may defer Queen validation: " & $sError)
AssertTrue(Not HeroLoadoutValidateForDetectedTownHall($oDetectedLoadout, 7, $sError), "fresh TH7 rejects a locked Queen")
AssertTrue(HeroLoadoutValidateForDetectedTownHall($oDetectedLoadout, 8, $sError), "fresh TH8 accepts an unlocked Queen: " & $sError)
Local $oUnsupportedLoadout = HeroLoadoutCreate(0)
AssertTrue(HeroLoadoutAdd($oUnsupportedLoadout, "dragon-duke", $sError), "auto-TH plan may carry a catalog Hero pending detection")
AssertTrue(Not HeroLoadoutValidateForDetectedTownHall($oUnsupportedLoadout, 18, $sError), "fresh TH18 still rejects a Hero without an actuator")

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
AssertTrue(RunPlanSetPlannedTownHall($oPlan, 18, $sError), "intent fixture pins TH18: " & $sError)
AssertTrue(Not $oPlan.Item("army_manage_training"), "default plan preserves the trained army")
AssertTrue($oPlan.Item("max_battles") = 1, "default current-army plan is bounded to one battle")
Local $oIntentLoadout = HeroLoadoutCreate(18)
AssertTrue(HeroLoadoutAdd($oIntentLoadout, "barbarian-king", $sError), "intent loadout is populated: " & $sError)

Local $oIntent = RunIntentCreate($oPlan, "legend-ii", $oIntentLoadout, $sError)
AssertTrue(IsObj($oIntent), "run intent is created: " & $sError)
AssertTrue($oIntent.Item("surface_id") = "legend-ii", "intent keeps the exact surface")

Local $oMismatch = RunIntentCreate($oPlan, "builder", $oIntentLoadout, $sError)
AssertTrue(Not IsObj($oMismatch), "surface that contradicts the plan mode is rejected")

; The browser planner writes one flat document. The bridge must revalidate every field before producing an intent.
Local $oSavedPlan = Json_ObjCreate()
Local $aSavedHeroes = ["barbarian-king", "archer-queen"]
Json_ObjPut($oSavedPlan, "run.surface", "regular")
Json_ObjPut($oSavedPlan, "run.strategy", "legacy.csv")
Json_ObjPut($oSavedPlan, "run.attack_script", "Barch four fingers")
Json_ObjPut($oSavedPlan, "run.town_hall", 18)
Json_ObjPut($oSavedPlan, "run.heroes", $aSavedHeroes)
Json_ObjPut($oSavedPlan, "runtime.emulator", "auto")
Json_ObjPut($oSavedPlan, "runtime.instance", "")
Json_ObjPut($oSavedPlan, "run.duration_minutes", 45)
Json_ObjPut($oSavedPlan, "run.max_battles", 12)
Json_ObjPut($oSavedPlan, "run.stop_on_star_bonus", True)
Json_ObjPut($oSavedPlan, "run.max_failures", 3)
Json_ObjPut($oSavedPlan, "target.gold", 1000000)
Json_ObjPut($oSavedPlan, "target.elixir", 750000)
Json_ObjPut($oSavedPlan, "target.dark_elixir", 5000)
Json_ObjPut($oSavedPlan, "upgrade.policy", "disabled")
Json_ObjPut($oSavedPlan, "account.queue", "")
Json_ObjPut($oSavedPlan, "army.source", "recipe")
Json_ObjPut($oSavedPlan, "army.recipe_name", "farm")
Json_ObjPut($oSavedPlan, "army.manage_training", True)
Json_ObjPut($oSavedPlan, "army.wait_for_full", True)
Json_ObjPut($oSavedPlan, "army.train_spells", True)
Json_ObjPut($oSavedPlan, "army.train_sieges", False)
Json_ObjPut($oSavedPlan, "search.min_gold", 400000)
Json_ObjPut($oSavedPlan, "search.min_elixir", 400000)
Json_ObjPut($oSavedPlan, "search.min_dark", 0)
Json_ObjPut($oSavedPlan, "search.max_seconds", 120)
Json_ObjPut($oSavedPlan, "search.town_hall_filter", "same-or-lower")
Json_ObjPut($oSavedPlan, "donate.mode", "off")
Json_ObjPut($oSavedPlan, "donate.keep_army", True)
Json_ObjPut($oSavedPlan, "donate.max_per_run", 0)
Json_ObjPut($oSavedPlan, "donate.request_when_short", False)
Json_ObjPut($oSavedPlan, "events.clan_games", False)
Json_ObjPut($oSavedPlan, "events.clan_games_point_cap", 0)
Json_ObjPut($oSavedPlan, "events.laboratory", "off")
Json_ObjPut($oSavedPlan, "events.collect_resources", False)
Json_ObjPut($oSavedPlan, "notify.on_stop", False)
Json_ObjPut($oSavedPlan, "notify.on_error", True)
Json_ObjPut($oSavedPlan, "notify.channel", "log-only")
Json_ObjPut($oSavedPlan, "run.diagnostic_mode", True)
Json_ObjPut($oSavedPlan, "run.diagnostic_note", "supervised contract test")
Json_ObjPut($oSavedPlan, "pacing.action_delay_ms", 120)
Json_ObjPut($oSavedPlan, "pacing.settle_ms", 400)
Json_ObjPut($oSavedPlan, "pacing.retry_attempts", 0)
Json_ObjPut($oSavedPlan, "pacing.break_every_minutes", 0)
Json_ObjPut($oSavedPlan, "pacing.break_minutes", 5)
Local $sSavedPlanPath = @TempDir & "\mybot-run-plan-test.json"
FileDelete($sSavedPlanPath)
AssertTrue(FileWrite($sSavedPlanPath, Json_Encode($oSavedPlan)) > 0, "saved planner fixture is written")
Local $oSavedIntent = RunPlanFileLoadIntent($sSavedPlanPath, $sError)
AssertTrue(IsObj($oSavedIntent), "saved planner document becomes a run intent: " & $sError)
Local $oSavedEnginePlan = $oSavedIntent.Item("plan")
AssertTrue($oSavedEnginePlan.Item("search_max_seconds") = 120, "saved search limit reaches RunPlan")
AssertTrue($oSavedEnginePlan.Item("army_recipe_name") = "farm", "saved army recipe reaches RunPlan")
AssertTrue($oSavedEnginePlan.Item("attack_script") = "Barch four fingers", "saved attack script reaches RunPlan")
AssertTrue(RunIntentManagesTraining($oSavedIntent), "saved training-management choice reaches the intent")
Local $oSavedLoadout = $oSavedIntent.Item("loadout")
AssertTrue(HeroLoadoutCount($oSavedLoadout) = 2, "saved Hero list reaches the loadout")
AssertTrue($oSavedLoadout.Item("town_hall") = 18, "saved Town Hall constrains the Hero loadout")
AssertTrue($oSavedIntent.Item("planned_town_hall") = 18, "saved Town Hall reaches the intent")
Local $oSavedPacing = $oSavedIntent.Item("pacing")
AssertTrue(RunPacingSettleMilliseconds($oSavedPacing) = 400, "saved pacing reaches the intent")
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "unsupported planner values are blocked rather than ignored")
AssertTrue(StringInStr($sError, "recipe") > 0, "the first unsupported adapter is named")
$oSavedEnginePlan.Item("army_recipe_name") = ""
$oSavedEnginePlan.Item("search_max_seconds") = 0
$oSavedEnginePlan.Item("search_town_hall_filter") = "any"
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "a fully supported regular-battle plan crosses the execution boundary: " & $sError)
$oSavedPacing.Item("retry_attempts") = 1
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "generic retries are blocked without a visual-change observer")
$oSavedPacing.Item("retry_attempts") = 0
$oSavedEnginePlan.Item("notify_channel") = "windows-toast"
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "unwired notification channels are rejected")
$oSavedEnginePlan.Item("notify_channel") = "log-only"
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "restoring supported values clears the adapter gate: " & $sError)
Local $oSavedRoute = $oSavedIntent.Item("route")
$oSavedRoute.Item("diagnostic_enabled") = False
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "Scripted deployment cannot silently claim current-client confirmation")
AssertTrue(StringInStr($sError, "supervised diagnostic") > 0, "Scripted rejection names the evidence gate")
$oSavedRoute.Item("diagnostic_enabled") = True
$oSavedEnginePlan.Item("emulator") = "bluestacks5"
$oSavedEnginePlan.Item("emulator_instance") = ""
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "explicit BlueStacks refuses an ambiguous default instance")
AssertTrue(StringInStr($sError, "exact emulator instance") > 0, "the emulator instance rejection explains the account boundary")
$oSavedEnginePlan.Item("emulator_instance") = "Pie64"
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "an exact BlueStacks instance clears the account binding gate: " & $sError)
$oSavedEnginePlan.Item("emulator_instance") = "Pie64&other"
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "unsafe emulator instance characters are rejected before command construction")
$oSavedEnginePlan.Item("emulator") = "auto"
$oSavedEnginePlan.Item("emulator_instance") = ""
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "automatic single-instance detection remains supported: " & $sError)
$oSavedEnginePlan.Item("strategy") = "legacy.standard"
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "a named CSV script cannot be paired with Standard deployment")
$oSavedEnginePlan.Item("attack_script") = "profile-current"
$oSavedRoute.Item("diagnostic_enabled") = False
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "training management requires a supervised diagnostic until its current screens are proven")
AssertTrue(StringInStr($sError, "Training management") > 0, "the training evidence gate names the active behavior")
$oSavedRoute.Item("diagnostic_enabled") = True
$oSavedEnginePlan.Item("strategy") = "legacy.csv"
$oSavedEnginePlan.Item("attack_script") = "Barch four fingers"
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "restoring Scripted accepts the named bundled-script contract: " & $sError)
$oSavedEnginePlan.Item("strategy") = "smart.local"
$oSavedEnginePlan.Item("attack_script") = "profile-current"
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "Smart Attack maps to the exact local standard-deployment adapter: " & $sError)
AssertTrue(RunExecutionSmartDropSides(5, True) = 0, "Smart Attack concentrates early villages on one scored side")
AssertTrue(RunExecutionSmartDropSides(8, True) = 0, "Smart Attack concentrates TH6-8 on one scored side")
AssertTrue(RunExecutionSmartDropSides(15, True) = 0, "Smart Attack scores a current-frame side instead of trusting legacy TH-side selector 5")
AssertTrue(RunExecutionSmartDropSides(15, False) = 0, "Smart Attack uses one concentrated side for dead bases")
$oSavedEnginePlan.Item("strategy") = "legacy.csv"
$oSavedEnginePlan.Item("attack_script") = "Barch four fingers"
$oSavedEnginePlan.Item("army_manage_training") = False
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses an unbounded multi-battle run")
AssertTrue(StringInStr($sError, "exactly one battle") > 0, "current-army rejection names its one-battle boundary")
$oSavedEnginePlan.Item("max_battles") = 1
AssertTrue(Not RunIntentManagesTraining($oSavedIntent), "current-army intent explicitly disables training management")
$oSavedEnginePlan.Item("events_collect_resources") = True
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses pre-battle resource collection")
$oSavedEnginePlan.Item("events_collect_resources") = False
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "one current trained army is accepted for exactly one battle: " & $sError)
$oSavedEnginePlan.Item("army_wait_for_full") = False
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode requires a fresh full-army readiness result")
AssertTrue(StringInStr($sError, "Wait for full army") > 0, "current-army readiness rejection names the required setting")
$oSavedEnginePlan.Item("army_wait_for_full") = True
$oSavedEnginePlan.Item("donate_mode") = "matching"
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses donations that could consume the one-shot army")
$oSavedEnginePlan.Item("donate_mode") = "off"
$oSavedEnginePlan.Item("donate_request_when_short") = True
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses a pre-battle troop request")
$oSavedEnginePlan.Item("donate_request_when_short") = False
$oSavedEnginePlan.Item("events_clan_games") = True
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses pre-battle Clan Games work")
$oSavedEnginePlan.Item("events_clan_games") = False
$oSavedEnginePlan.Item("events_collect_resources") = True
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode keeps resource collection outside the terminal path")
$oSavedEnginePlan.Item("events_collect_resources") = False
$oSavedEnginePlan.Item("events_laboratory") = "cheapest"
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses pre-battle Laboratory work")
$oSavedEnginePlan.Item("events_laboratory") = "off"
$oSavedEnginePlan.Item("upgrade_policy") = "walls"
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "current-army mode refuses pre-battle wall or building work")
$oSavedEnginePlan.Item("upgrade_policy") = "disabled"
AssertTrue(RunExecutionContractValidate($oSavedIntent, $sError), "restoring terminal current-army settings clears every side-effect gate: " & $sError)
$oSavedEnginePlan.Item("strategy") = "legacy.standard"
$oSavedEnginePlan.Item("attack_script") = "profile-current"
$oSavedRoute.Item("diagnostic_enabled") = False
AssertTrue(Not RunExecutionContractValidate($oSavedIntent, $sError), "selected Heroes cannot silently bypass their supervised evidence gate")
AssertTrue(StringInStr($sError, "Hero deployment") > 0, "the Hero rejection names deployment and ability use")
$oSavedRoute.Item("diagnostic_enabled") = True
$oSavedEnginePlan.Item("strategy") = "legacy.csv"
$oSavedEnginePlan.Item("attack_script") = "Barch four fingers"
$oSavedEnginePlan.Item("army_manage_training") = True
$oSavedEnginePlan.Item("max_battles") = 12
FileDelete($sSavedPlanPath)

; The immediately preceding planner contract had 44 keys and inferred Town Hall from the profile.
$oSavedPlan.Remove("run.town_hall")
AssertTrue(FileWrite($sSavedPlanPath, Json_Encode($oSavedPlan)) > 0, "legacy 44-key planner fixture is written")
Local $oLegacyTrainingIntent = RunPlanFileLoadIntent($sSavedPlanPath, $sError)
AssertTrue(IsObj($oLegacyTrainingIntent), "legacy 44-key plan is upgraded losslessly: " & $sError)
AssertTrue(RunIntentPlannedTownHall($oLegacyTrainingIntent) = 0, "legacy plan migrates to detect Town Hall at Start")
FileDelete($sSavedPlanPath)

; The 43-key contract also always managed profile training.
$oSavedPlan.Remove("army.manage_training")
AssertTrue(FileWrite($sSavedPlanPath, Json_Encode($oSavedPlan)) > 0, "legacy 43-key planner fixture is written")
$oLegacyTrainingIntent = RunPlanFileLoadIntent($sSavedPlanPath, $sError)
AssertTrue(IsObj($oLegacyTrainingIntent), "legacy 43-key plan is upgraded losslessly: " & $sError)
AssertTrue(RunIntentManagesTraining($oLegacyTrainingIntent), "legacy plan preserves inherited training management")
FileDelete($sSavedPlanPath)

; The older 42-key contract also lacked a script override. Preserve both legacy meanings.
$oSavedPlan.Remove("run.attack_script")
AssertTrue(FileWrite($sSavedPlanPath, Json_Encode($oSavedPlan)) > 0, "legacy 42-key planner fixture is written")
Local $oLegacyIntent = RunPlanFileLoadIntent($sSavedPlanPath, $sError)
AssertTrue(IsObj($oLegacyIntent), "legacy 42-key plan is upgraded losslessly: " & $sError)
Local $oLegacyPlan = $oLegacyIntent.Item("plan")
AssertTrue($oLegacyPlan.Item("attack_script") = "profile-current", "legacy plan preserves the active profile script")
AssertTrue(RunIntentManagesTraining($oLegacyIntent), "legacy 42-key plan preserves inherited training management")
FileDelete($sSavedPlanPath)

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
Local $oIntentQuota = $oIntent.Item("quota")
AssertTrue(BattleQuotaRemaining($oIntentQuota) = 4, "recording a battle consumes quota")

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
Local $oEvent = RunEventCreate("battle.completed", 1, 2000, "engine-test", "info", "Diagnostic battle", "profile-a", "legend", 1, 500, 250, 10, 0, $RUN_VERIFICATION_DIAGNOSTIC, "legend-ii", 2, 76, -5, 9)
AssertTrue(IsObj($oEvent), "diagnostic event is created")
Local $sJson = RunEventToJson($oEvent)
AssertTrue(StringInStr($sJson, Chr(34) & "verification_state" & Chr(34) & ":" & Chr(34) & $RUN_VERIFICATION_DIAGNOSTIC & Chr(34)) > 0, "event serializes the verification state")
AssertTrue(StringInStr($sJson, Chr(34) & "surface_id" & Chr(34) & ":" & Chr(34) & "legend-ii" & Chr(34)) > 0, "event serializes the exact surface")
AssertTrue(StringInStr($sJson, Chr(34) & "trophy_delta" & Chr(34) & ":-5") > 0, "event telemetry keeps trophy loss signed")

Local $oBadEvent = RunEventCreate("battle.completed", 2, 3000, "engine-test", "info", "Bad state", "", "legend", 1, 0, 0, 0, 0, "totally-fine")
AssertTrue(Not IsObj($oBadEvent), "unknown verification state is rejected")

; ---------------------------------------------------------------------------------------------------------------
; Pacing: gaps, settle waits, retries, and rests. The clock is an argument, so this is arithmetic and not a wait.
; ---------------------------------------------------------------------------------------------------------------
Local $oPacing = RunPacingCreateDefault()
AssertTrue(IsObj($oPacing), "pacing is created")
AssertTrue(RunPacingValidate($oPacing, $sError), "default pacing validates: " & $sError)
AssertTrue(RunPacingWaitBeforeAction($oPacing, 10000) = 0, "the first action of a run does not wait")

AssertTrue(RunPacingNoteAction($oPacing, 10000), "an action is timestamped")
AssertTrue(RunPacingWaitBeforeAction($oPacing, 10000) = 120, "an action immediately after another waits the whole gap")
AssertTrue(RunPacingWaitBeforeAction($oPacing, 10050) = 70, "part of the gap already spent is not waited again")
AssertTrue(RunPacingWaitBeforeAction($oPacing, 10120) = 0, "the gap elapsed means no wait")
AssertTrue(RunPacingWaitBeforeAction($oPacing, 99999) = 0, "a long gap never becomes a negative wait")
; A restarted timer reads as time travelling backwards; waiting the whole gap is the safe reading of that.
AssertTrue(RunPacingWaitBeforeAction($oPacing, 5000) = 120, "a clock that went backwards waits the whole gap")

AssertTrue(RunPacingSettleMilliseconds($oPacing) = 400, "settle wait is reported")
AssertTrue(RunPacingRetryAttempts($oPacing) = 0, "safe default does not retry an unobserved action")

AssertTrue(Not RunPacingSet($oPacing, 120, 400, 2, 0, 0, $sError), "a rest shorter than a minute is rejected")
; The settle value here differs from the current one, so "untouched" below is a real check and not a coincidence.
AssertTrue(Not RunPacingSet($oPacing, 999999, 777, 2, 0, 5, $sError), "an action gap past the maximum is rejected")
AssertTrue(RunPacingSettleMilliseconds($oPacing) = 400, "a rejected change leaves the pacing untouched")
AssertTrue(RunPacingSet($oPacing, 250, 600, 3, 45, 10, $sError), "pacing is set: " & $sError)
AssertTrue(RunPacingSettleMilliseconds($oPacing) = 600, "the accepted settle wait is kept")

; Rests are off by default, and off means never due no matter how long the run has been going.
Local $oRestless = RunPacingCreateDefault()
AssertTrue(Not RunPacingRestsEnabled($oRestless), "rests are off by default")
AssertTrue(Not RunPacingRestIsDue($oRestless, 0, 86400000), "a run with rests off never owes one")
AssertTrue(RunPacingRestMilliseconds($oRestless) = 0, "rests off means a zero-length rest")

AssertTrue(RunPacingRestsEnabled($oPacing), "rests are on once an interval is set")
AssertTrue(Not RunPacingRestIsDue($oPacing, 0, 44 * 60000), "no rest is due before the interval")
AssertTrue(RunPacingRestIsDue($oPacing, 0, 45 * 60000), "a rest is due once the interval passes")
AssertTrue(RunPacingRestMilliseconds($oPacing) = 10 * 60000, "rest length is reported in milliseconds")

; The interval restarts from the end of the rest, so the second interval is the same length as the first.
AssertTrue(RunPacingNoteRestTaken($oPacing, 55 * 60000), "a completed rest is recorded")
AssertTrue(Not RunPacingRestIsDue($oPacing, 0, 99 * 60000), "the interval restarts after a rest")
AssertTrue(RunPacingRestIsDue($oPacing, 0, 100 * 60000), "the next rest falls due an interval later")

; An intent always carries pacing, so nothing downstream has to check whether it is there.
Local $oPacingLoadout = HeroLoadoutCreate(18)
Local $oPacingPlan = RunPlanCreateDefault("regular", "fixture-strategy")
AssertTrue(RunPlanSetPlannedTownHall($oPacingPlan, 18, $sError), "pacing fixture pins TH18: " & $sError)
AssertTrue(RunPlanSetStopConditions($oPacingPlan, 1, 1, False, 1), "intent fixture receives bounded stop conditions")
Local $oPacingIntent = RunIntentCreate($oPacingPlan, "regular", $oPacingLoadout, $sError)
AssertTrue(IsObj($oPacingIntent), "intent is created for the pacing check: " & $sError)
AssertTrue($oPacingIntent.Exists("pacing"), "every intent carries pacing")
AssertTrue(RunIntentSetPacing($oPacingIntent, 200, 500, 1, 30, 5, $sError), "intent pacing is set: " & $sError)
Local $oAttached = $oPacingIntent.Item("pacing")
AssertTrue(RunPacingSettleMilliseconds($oAttached) = 500, "the intent holds the pacing that was set")
AssertTrue(Not RunIntentSetPacing($oPacingIntent, 200, 500, 1, 30, 0, $sError), "the intent refuses out-of-range pacing")
AssertTrue(RunPacingSettleMilliseconds($oAttached) = 500, "a refused change leaves the intent's pacing alone")
AssertTrue(StringInStr(RunIntentDescribe($oPacingIntent), "500ms settle") > 0, "the intent describes its pacing")
AssertTrue(StringInStr(RunIntentDescribe($oPacingIntent), "Plan: REGULAR / fixture-strategy / planned TH18 / 1 min / 1 battle / 1 failure max") > 0, "the intent describes its actual run limits")
AssertTrue(StringInStr(RunIntentDescribe($oPacingIntent), "Surface quota: Unlimited attacks") > 0, "the intent labels the separate surface quota")

; An intent with pacing stripped out must not validate, or the required-field list is decorative.
$oPacingIntent.Remove("pacing")
AssertTrue(Not RunIntentValidate($oPacingIntent, $sError), "an intent without pacing is rejected")

; ---------------------------------------------------------------------------------------------------------------
; Run plan file: what the web planner writes is what the native tab reads.
; ---------------------------------------------------------------------------------------------------------------
Local $oValues = RunPlanFileParse('{"run.surface": "legend-ii", "run.max_battles": 12, "run.stop_on_star_bonus": true, "run.diagnostic_mode": false, "run.diagnostic_note": "", "run.heroes": ["barbarian-king", "archer-queen"]}', $sError)
AssertTrue(IsObj($oValues), "a plan file parses: " & $sError)
AssertTrue($oValues.Item("run.surface") = "legend-ii", "strings survive the parse")
AssertTrue($oValues.Item("run.max_battles") = 12, "numbers survive the parse")
AssertTrue($oValues.Item("run.stop_on_star_bonus") = True, "true parses as a boolean")
; The regression the web server has its own guard for: false must not arrive as a string that reads as true.
AssertTrue(IsBool($oValues.Item("run.diagnostic_mode")), "false parses as a boolean and not a string")
AssertTrue($oValues.Item("run.diagnostic_mode") = False, "false parses as false")
AssertTrue($oValues.Item("run.diagnostic_note") = "", "an empty string stays empty")
AssertTrue($oValues.Item("run.heroes") = "barbarian-king|archer-queen", "a list arrives pipe-delimited")

Local $oEscaped = RunPlanFileParse('{"a": "line\nbreak", "b": "quote\"inside", "c": "sla\\sh", "d": "\u00e9", "e": null, "f": [], "g": -1.5}', $sError)
AssertTrue(IsObj($oEscaped), "escapes parse: " & $sError)
AssertTrue($oEscaped.Item("a") = "line" & @LF & "break", "\n becomes a newline")
AssertTrue($oEscaped.Item("b") = 'quote"inside', "an escaped quote does not end the string")
AssertTrue($oEscaped.Item("c") = "sla\sh", "an escaped backslash is one backslash")
AssertTrue($oEscaped.Item("d") = ChrW(233), "a \u escape becomes its character")
AssertTrue($oEscaped.Item("e") = "", "null reads as empty")
AssertTrue($oEscaped.Item("f") = "", "an empty list reads as empty")
AssertTrue($oEscaped.Item("g") = -1.5, "a negative fraction parses")

AssertTrue(Not IsObj(RunPlanFileParse('["not", "an", "object"]', $sError)), "a top-level array is refused")
AssertTrue(Not IsObj(RunPlanFileParse('{"a": {"nested": 1}}', $sError)), "a nested object is refused")
AssertTrue(Not IsObj(RunPlanFileParse('{"a": 1, "a": 2}', $sError)), "a duplicated key is refused")
AssertTrue(Not IsObj(RunPlanFileParse('{"a": 1', $sError)), "an unclosed object is refused")
AssertTrue(Not IsObj(RunPlanFileParse('{"a": tru}', $sError)), "a malformed literal is refused")
AssertTrue(Not IsObj(RunPlanFileParse('{"a" 1}', $sError)), "a missing colon is refused")
AssertTrue(Not IsObj(RunPlanFileParse('{"a": "unclosed}', $sError)), "an unclosed string is refused")
AssertTrue(IsObj(RunPlanFileParse('{}', $sError)), "an empty plan is a valid plan")

Local $sMissing = @TempDir & "\mybot-run-plan-that-is-not-there.json"
Local $oMissingPlan = RunPlanFileLoad($sMissing, $sError)
Local $iMissingStatus = @error ; captured before the next call clears it
AssertTrue(Not IsObj($oMissingPlan), "a missing plan file does not load")
AssertTrue($iMissingStatus = 2, "a missing plan file is reported as absent rather than broken")
AssertTrue(RunPlanFileStamp($sMissing) = "", "a missing plan file has an empty change token")

; The round trip that matters: a file written the way the web planner writes them comes back with the same values.
Local $sRoundTrip = @TempDir & "\mybot-run-plan-round-trip.json"
Local $hRoundTrip = FileOpen($sRoundTrip, $FO_OVERWRITE + $FO_UTF8_NOBOM)
AssertTrue($hRoundTrip <> -1, "a temporary plan file can be written")
FileWrite($hRoundTrip, '{' & @CRLF & '  "run.max_battles": 7,' & @CRLF & '  "run.surface": "regular"' & @CRLF & '}' & @CRLF)
FileClose($hRoundTrip)
Local $oRoundTrip = RunPlanFileLoad($sRoundTrip, $sError)
AssertTrue(IsObj($oRoundTrip), "a written plan file loads back: " & $sError)
AssertTrue($oRoundTrip.Item("run.max_battles") = 7, "the value written is the value read")
AssertTrue(RunPlanFileStamp($sRoundTrip) <> "", "a present plan file has a change token")
FileDelete($sRoundTrip)

ConsoleWrite("Run engine tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
