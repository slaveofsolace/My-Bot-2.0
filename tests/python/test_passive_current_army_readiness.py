from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
TRAIN_SYSTEM = ROOT / "COCBot/functions/CreateArmy/TrainSystem.au3"
OPEN_OVERVIEW = ROOT / "COCBot/functions/CreateArmy/openArmyOverview.au3"
READINESS = ROOT / "COCBot/functions/CreateArmy/PassiveCurrentArmyReadiness.au3"


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ims)^Func\s+{re.escape(name)}\b.*?^EndFunc\b.*?$", source
    )
    assert match, f"missing AutoIt function {name}"
    return match.group(0)


def test_passive_branch_uses_dedicated_observer_before_training_paths():
    source = TRAIN_SYSTEM.read_text(encoding="utf-8")
    train_system = _function_body(source, "TrainSystem")
    passive_call = train_system.index("CheckPassiveCurrentArmyReady()")
    first_training_call = train_system.index("BoostSuperTroop()")

    assert passive_call < first_training_call
    assert "CheckIfArmyIsReady(True, False)" not in train_system


def test_passive_observer_has_no_legacy_locator_mutator_or_profile_fallback():
    source = TRAIN_SYSTEM.read_text(encoding="utf-8")
    observer = _function_body(source, "CheckPassiveCurrentArmyReady")
    forbidden = (
        "CheckArmyCamp(",
        "CheckIfArmyIsReady(",
        "getArmyTroopCapacity(",
        "CheckHeroOrder(",
        "HeroHallValuesCheck(",
        "ImgLocate",
        "ZoomOut(",
        "SearchZoomOut(",
        "GetVillageSize(",
        "RemoveExtraTroops(",
        "QuickTrain(",
        "TrainCustomArmy(",
        "TrainSiege(",
        "IniWrite(",
        "$g_iTotalCampSpace",
        "$g_iTotalCampForcedValue",
    )

    for token in forbidden:
        assert token not in observer, f"passive observer contains forbidden path: {token}"

    assert 'OpenArmyOverview(False, "CheckPassiveCurrentArmyReady()", False)' in observer
    assert "getArmyCampCap($aArmyCampSize[0], $aArmyCampSize[1], True)" in observer
    assert "PassiveCurrentArmyCapacityProof(" in observer
    assert observer.index("$g_bIsFullArmywithHeroesAndSpells = False") < observer.index(
        "$g_bIsFullArmywithHeroesAndSpells = True"
    )


def test_army_overview_can_skip_only_hero_order_inspection():
    source = OPEN_OVERVIEW.read_text(encoding="utf-8")
    overview = _function_body(source, "OpenArmyOverview")

    assert "$bCheckHeroOrder = True" in overview
    assert "ElseIf $bCheckHeroOrder Then" in overview
    assert "CheckHeroOrder()" in overview
    assert "If Not WaitforPixel(23, 505 + $g_iBottomOffsetY, 53, 507 + $g_iBottomOffsetY" in overview
    missing_button = overview.index("Army button was not detected")
    click = overview.index("ClickP($aArmyTrainButton, 1, 120")
    wait_for_window = overview.index("_Sleep($DELAYRUNBOT6)")
    assert missing_button < click < wait_for_window


def test_capacity_contract_requires_two_matching_fresh_full_reads():
    source = READINESS.read_text(encoding="utf-8")
    proof = _function_body(source, "PassiveCurrentArmyCapacityProof")
    ready = _function_body(source, "PassiveCurrentArmyCapacityReady")

    assert proof.count("PassiveCurrentArmyCapacityParse(") == 2
    assert "$iFirstCurrent <> $iCurrent Or $iFirstTotal <> $iTotal" in proof
    assert "$iCurrent <= 0 Or $iCurrent < $iTotal" in ready
    assert "Mod($iTotal, 5) <> 0" in ready
