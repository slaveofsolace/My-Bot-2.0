#NoTrayIcon
#include "..\..\COCBot\functions\Game\GameCatalog.au3"
#include "..\..\COCBot\functions\Game\ScreenStateRegistry.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 20
	EndIf
EndFunc   ;==>AssertTrue

Local $sError = ""
AssertTrue(CurrentGameCatalogValidate($sError), "generated game catalog validates: " & $sError)
AssertTrue($CURRENT_GAME_AS_OF = "2026-08-06", "catalog audit date is fixed")
AssertTrue($CURRENT_GAME_VERIFIED_THROUGH = "2026-07-09", "official facts are bounded by the verified date")
AssertTrue($CURRENT_GAME_MAX_TOWN_HALL = 18, "Town Hall 18 is the maximum")
AssertTrue(UBound($g_aCurrentGameHeroes, 1) = 6, "six Home Village Heroes are generated")
AssertTrue($CURRENT_GAME_MAX_ACTIVE_HERO_SLOTS = 4, "four active Hero slots are retained")
AssertTrue(UBound($g_aCurrentGameGuardians, 1) = 3, "three Guardians are generated")
AssertTrue($CURRENT_GAME_MAX_ACTIVE_GUARDIANS = 1, "one active Guardian is retained")

AssertTrue(CurrentGameGetHeroUnlockTH("barbarian-king") = 4, "Barbarian King unlocks at Town Hall 4")
AssertTrue(CurrentGameGetHeroUnlockTH("dragon-duke") = 15, "Dragon Duke unlocks at Town Hall 15")
AssertTrue(CurrentGameHeroMovement("dragon-duke") = "air", "Dragon Duke movement is catalogued")
AssertTrue(CurrentGameHeroIsUnlocked("archer-queen", 8), "Archer Queen is available at Town Hall 8")
AssertTrue(Not CurrentGameHeroIsUnlocked("royal-champion", 12), "Royal Champion remains locked below Town Hall 13")
AssertTrue(StringInStr(CurrentGameSourceUrl("february-2026-02-23"), "supercell.com") > 0, "Hero source URL is official")
AssertTrue(CurrentGameFindGuardian("logger") >= 0, "Logger is catalogued as a Guardian")
AssertTrue(CurrentGameGuardianRequiresBuilder("smasher"), "Guardian upgrades require a Builder")
AssertTrue(CurrentGameGuardianUnavailableWhileUpgrading("longshot"), "upgrading Guardians are unavailable")

Local $sKind = "", $iValue = -1, $sUnit = ""
AssertTrue(CurrentGameGetBattleAttackBudget("regular", $sKind, $iValue, $sUnit), "regular battle budget is available")
AssertTrue($sKind = "unlimited" And $iValue = -1, "regular battles are unlimited")
AssertTrue(CurrentGameGetBattleMinimumTH("regular") = 2, "regular battles unlock at Town Hall 2")
AssertTrue(CurrentGameGetBattleMinimumTH("ranked") = 7, "ranked battles unlock at Town Hall 7")
Local $iBuilderSurface = CurrentGameFindBattleSurface("builder")
AssertTrue($iBuilderSurface >= 0, "Builder Base battle surface is catalogued")
AssertTrue($g_aCurrentGameBattleSurfaces[$iBuilderSurface][$eGameBattleFixtureIds] = "builder.battle.entry", "Builder Base battles use their dedicated entry fixture")

AssertTrue(CurrentGameGetBattleAttackBudget("legend-iii", $sKind, $iValue, $sUnit), "Legend III budget is available")
AssertTrue($sKind = "fixed" And $iValue = 24 And $sUnit = "per-week", "Legend III has 24 weekly attacks")
AssertTrue(CurrentGameGetBattleAttackBudget("legend-ii", $sKind, $iValue, $sUnit), "Legend II budget is available")
AssertTrue($iValue = 30 And $sUnit = "per-week", "Legend II has 30 weekly attacks")
AssertTrue(CurrentGameGetBattleAttackBudget("legend-i", $sKind, $iValue, $sUnit), "Legend I budget is available")
AssertTrue($iValue = 8 And $sUnit = "per-league-day", "Legend I has eight attacks per League Day")

Local $sReason = ""
AssertTrue(Not CurrentGameBattleSurfaceReady("ranked", $sReason), "Ranked remains closed before recognition evidence")
AssertTrue(StringInStr($sReason, "Recognition") > 0, "Ranked readiness explains its blocker")

AssertTrue(CurrentGameFindScreenState("battle.fast-forward") >= 0, "fast-forward state is catalogued")
AssertTrue(CurrentGameScreenAppearsAfterSeconds("battle.fast-forward") = 120, "fast-forward appears after 120 seconds")
AssertTrue(CurrentGameScreenSpeedMultiplier("battle.fast-forward") = 4, "fast-forward uses 4x speed")
AssertTrue(CurrentGameScreenDefaultAction("battle.fast-forward") = "ignore", "unverified optional fast-forward is ignored")
AssertTrue(CurrentGameScreenDefaultAction("heroes.journey") = "stop-route", "unverified Hero Journey stops the route")
AssertTrue(CurrentGameScreenIsBlocking("heroes.journey"), "Hero Journey is a blocking state")
AssertTrue(CurrentGameScreenRetryLimit("heroes.journey") = 1, "Hero Journey retry is bounded")
AssertTrue(CurrentGameScreenShouldStopRoute("chat.global.open"), "unverified open Global Chat stops the route")
AssertTrue(Not CurrentGameScreenCanHandle("chat.global.open", $sReason), "Global Chat handler remains closed")
AssertTrue(StringInStr($sReason, "Recognition") > 0, "Global Chat readiness explains its blocker")

ConsoleWrite("Game catalog tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
