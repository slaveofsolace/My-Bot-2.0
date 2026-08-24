#!/usr/bin/env python3
"""Replay approved current-client captures through pure recognizer adapters.

The harness itself has no emulator, AutoIt, Win32-input, network, or subprocess
integration.  A caller must explicitly register a recognizer adapter.  Every
adapter receives decoded pixels and a fail-closed action sink; attempting to
click, tap, type, swipe, or emit an action fails the replay.

Only manifest entries already marked ``verified`` are eligible.  Missing and
redacted entries remain non-evidence and are reported as skipped.  A verified
entry also needs an explicit ``replay_contract`` in its metadata, for example::

    {
      "replay_contract": {
        "schema_version": 1,
        "adapter": "production.screen-state-v1",
        "expected_state": "army.recipes.home",
        "safe_regions": [
          {"id": "close", "x": 810, "y": 12, "width": 36, "height": 36}
        ]
      }
    }

The registered adapters below load their anchors from the production AutoIt
sources, so fixture replay cannot silently drift into an easier second
recognizer.  Each adapter must also reject an all-black frame before any replay
report is accepted.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

try:  # Supports both ``python tools/...`` and ``from tools import ...``.
    from fixture_png import DecodedPng, decode_png
except ModuleNotFoundError:  # pragma: no cover - exercised by package imports.
    from tools.fixture_png import DecodedPng, decode_png


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/fixtures/current-client/manifest.json"
SCREEN_COORDINATES_SOURCE = ROOT / "COCBot/functions/Config/ScreenCoordinates.au3"
OPEN_CLAN_REQUEST_SOURCE = ROOT / "COCBot/functions/Run/OpenClanRequest.au3"
OPEN_HOME_COLLECTORS_SOURCE = ROOT / "COCBot/functions/Run/OpenHomeCollectors.au3"


class FixtureReplayError(RuntimeError):
    """A fixture or recognizer violated the offline replay contract."""


class UnsafeActionAttempt(FixtureReplayError):
    """A recognizer attempted input while running in passive replay."""


@dataclass(frozen=True, order=True)
class SafeRegion:
    id: str
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_mapping(cls, value: Any, *, fixture_id: str) -> "SafeRegion":
        if not isinstance(value, dict):
            raise FixtureReplayError(f"{fixture_id}: each safe region must be an object")
        region_id = value.get("id")
        if not isinstance(region_id, str) or not region_id.strip():
            raise FixtureReplayError(f"{fixture_id}: safe region id must be a non-empty string")
        coordinates: dict[str, int] = {}
        for field in ("x", "y", "width", "height"):
            number = value.get(field)
            if not isinstance(number, int) or isinstance(number, bool):
                raise FixtureReplayError(f"{fixture_id}: safe region {region_id!r} {field} must be an integer")
            coordinates[field] = number
        return cls(id=region_id.strip(), **coordinates)

    def assert_within(self, image: DecodedPng, *, fixture_id: str) -> None:
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise FixtureReplayError(
                f"{fixture_id}: safe region {self.id!r} must have non-negative origin and positive size"
            )
        if self.x + self.width > image.width or self.y + self.height > image.height:
            raise FixtureReplayError(
                f"{fixture_id}: safe region {self.id!r} exceeds {image.width}x{image.height} capture bounds"
            )


@dataclass(frozen=True)
class RecognitionResult:
    state: str
    safe_regions: tuple[SafeRegion, ...]


HOME_MAIN_ADAPTER = "production.home-main-pixel-v1"
CLAN_REQUEST_DIALOG_ADAPTER = "production.open-clan-request-dialog-v1"
HOME_LOOT_CART_ADAPTER = "production.open-home-loot-cart-cue-v1"
HOME_DAILY_REWARD_ADAPTER = "production.open-home-daily-reward-v1"
HOME_DAILY_REWARD_CLAIMED_ADAPTER = "production.open-home-daily-reward-claimed-v1"
HOME_INACTIVITY_RELOAD_ADAPTER = "production.open-home-inactivity-reload-v1"
HOME_WELCOME_BACK_ADAPTER = "production.open-home-welcome-back-v1"
HOME_MAIN_REGION = SafeRegion(id="home-proof", x=378, y=10, width=1, height=1)
CLAN_REQUEST_SEND_REGION = SafeRegion(id="send", x=455, y=438, width=181, height=83)


def _pixel_near(image: DecodedPng, x: int, y: int, expected: int, variation: int) -> bool:
    if x < 0 or y < 0 or x >= image.width or y >= image.height or image.channels < 3:
        return False
    offset = (y * image.width + x) * image.channels
    actual = image.pixels[offset:offset + 3]
    wanted = ((expected >> 16) & 0xFF, (expected >> 8) & 0xFF, expected & 0xFF)
    return all(abs(actual[index] - wanted[index]) <= variation for index in range(3))


@functools.lru_cache(maxsize=1)
def _load_home_main_anchor() -> tuple[int, int, int, int]:
    source = SCREEN_COORDINATES_SOURCE.read_text(encoding="utf-8-sig")
    match = re.search(
        r"Global\s+\$aIsMain\[4\]\s*=\s*\[(\d+),\s*(\d+),\s*0x([0-9A-Fa-f]{6}),\s*(\d+)\]",
        source,
    )
    if match is None:
        raise FixtureReplayError("cannot load the production $aIsMain pixel contract")
    x, y, color, variation = match.groups()
    anchor = (int(x), int(y), int(color, 16), int(variation))
    if anchor[:2] != (HOME_MAIN_REGION.x, HOME_MAIN_REGION.y):
        raise FixtureReplayError("production $aIsMain moved outside the reviewed Home proof region")
    return anchor


@functools.lru_cache(maxsize=1)
def _load_clan_request_dialog_anchors() -> tuple[tuple[int, int, int, int], ...]:
    source = OPEN_CLAN_REQUEST_SOURCE.read_text(encoding="utf-8-sig")
    function = re.search(
        r"Func\s+_OpenClanRequestDialogFrameReady\(\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if function is None:
        raise FixtureReplayError("cannot load the production Clan request dialog predicate")
    anchors = tuple(
        (int(x), int(y), int(color, 16), int(variation))
        for x, y, color, variation in re.findall(
            r"_OpenHomePixelNear\(\s*(\d+)\s*,\s*(\d+)\s*,\s*0x([0-9A-Fa-f]{6})\s*,\s*(\d+)\s*\)",
            function.group(1),
        )
    )
    if len(anchors) != 11:
        raise FixtureReplayError(
            f"production Clan request dialog predicate has {len(anchors)} anchors; expected exactly 11"
        )
    return anchors


@functools.lru_cache(maxsize=1)
def _load_home_loot_cart_contract() -> tuple[
    tuple[tuple[int, int, int, int], ...],
    tuple[tuple[int, int, int, int], ...],
]:
    source = OPEN_HOME_COLLECTORS_SOURCE.read_text(encoding="utf-8-sig")
    cue_function = re.search(
        r"Func\s+_OpenHomeLootCartCueAt\(\$iX,\s*\$iY\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if cue_function is None:
        raise FixtureReplayError("cannot load the production Loot Cart cue predicate")
    anchors = tuple(
        (int(dx or 0), int(dy or 0), int(color, 16), 32)
        for dx, dy, color in re.findall(
            r"_OpenHomePixelNear\(\s*\$iX(?:\s*\+\s*(\d+))?\s*,\s*"
            r"\$iY(?:\s*\+\s*(\d+))?\s*,\s*0x([0-9A-Fa-f]{6})\s*\)",
            cue_function.group(1),
        )
    )
    if len(anchors) != 8:
        raise FixtureReplayError(
            f"production Loot Cart cue predicate has {len(anchors)} anchors; expected exactly 8"
        )

    detect_function = re.search(
        r"Func\s+OpenHomeLootCartDetectCue\(\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if detect_function is None:
        raise FixtureReplayError("cannot load the production Loot Cart scan regions")
    scan_regions = tuple(
        tuple(int(value) for value in match)
        for match in re.findall(
            r"_OpenHomeLootCartScanRegion\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
            detect_function.group(1),
        )
    )
    if scan_regions != ((0, 80, 150, 515), (680, 80, 830, 515), (150, 515, 680, 600)):
        raise FixtureReplayError("production Loot Cart scan regions changed outside the reviewed contract")
    return anchors, scan_regions


@functools.lru_cache(maxsize=1)
def _load_home_daily_reward_contract() -> tuple[
    tuple[tuple[int, int, int, int], ...],
    tuple[tuple[int, int, int, int], ...],
    tuple[tuple[int, int], ...],
]:
    source = OPEN_HOME_COLLECTORS_SOURCE.read_text(encoding="utf-8-sig")
    overlay_function = re.search(
        r"Func\s+OpenHomeDailyRewardOverlayReady\(\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if overlay_function is None:
        raise FixtureReplayError("cannot load the production Daily Reward overlay predicate")
    overlay_anchors = tuple(
        (int(x), int(y), int(color, 16), int(variation))
        for x, y, color, variation in re.findall(
            r"_OpenHomePixelNear\(\s*(\d+)\s*,\s*(\d+)\s*,\s*0x([0-9A-Fa-f]{6})\s*,\s*(\d+)\s*\)",
            overlay_function.group(1),
        )
    )
    if len(overlay_anchors) != 7:
        raise FixtureReplayError(
            f"production Daily Reward overlay predicate has {len(overlay_anchors)} anchors; expected exactly 7"
        )

    claim_function = re.search(
        r"Func\s+_OpenHomeDailyRewardClaimCandidateReady\(\$iX,\s*\$iY\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if claim_function is None:
        raise FixtureReplayError("cannot load the production Daily Reward Claim predicate")
    claim_anchors: list[tuple[int, int, int, int]] = []
    for x_sign, x_value, y_sign, y_value, color, variation in re.findall(
        r"_OpenHomePixelNear\(\s*\$iX(?:\s*([+-])\s*(\d+))?\s*,\s*"
        r"\$iY(?:\s*([+-])\s*(\d+))?\s*,\s*0x([0-9A-Fa-f]{6})\s*,\s*(\d+)\s*\)",
        claim_function.group(1),
    ):
        dx = int(x_value or 0) * (-1 if x_sign == "-" else 1)
        dy = int(y_value or 0) * (-1 if y_sign == "-" else 1)
        claim_anchors.append((dx, dy, int(color, 16), int(variation)))
    if len(claim_anchors) != 4:
        raise FixtureReplayError(
            f"production Daily Reward Claim predicate has {len(claim_anchors)} anchors; expected exactly 4"
        )

    find_function = re.search(
        r"Func\s+OpenHomeDailyRewardFindClaim\(ByRef\s+\$aClaim\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if find_function is None:
        raise FixtureReplayError("cannot load the production Daily Reward candidate centers")
    candidate_match = re.search(
        r"Local\s+\$aCandidates\[7\]\[2\]\s*=\s*(\[\[.*?\]\])",
        find_function.group(1),
        re.DOTALL,
    )
    if candidate_match is None:
        raise FixtureReplayError("production Daily Reward candidate centers are missing")
    centers = tuple(
        (int(x), int(y))
        for x, y in re.findall(r"\[(\d+)\s*,\s*(\d+)\]", candidate_match.group(1))
    )
    if centers != ((149, 326), (297, 326), (445, 326), (149, 485), (297, 485), (445, 485), (592, 485)):
        raise FixtureReplayError("production Daily Reward candidate centers changed outside the reviewed contract")
    return overlay_anchors, tuple(claim_anchors), centers


@functools.lru_cache(maxsize=1)
def _load_home_daily_reward_claimed_contract() -> tuple[tuple[int, int, int, int], ...]:
    source = OPEN_HOME_COLLECTORS_SOURCE.read_text(encoding="utf-8-sig")
    function = re.search(
        r"Func\s+OpenHomeDailyRewardClaimedOverlayReady\(\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if function is None:
        raise FixtureReplayError("cannot load the production claimed Daily Reward overlay predicate")
    anchors = tuple(
        (int(x), int(y), int(color, 16), int(variation))
        for x, y, color, variation in re.findall(
            r"_OpenHomePixelNear\(\s*(\d+)\s*,\s*(\d+)\s*,\s*0x([0-9A-Fa-f]{6})\s*,\s*(\d+)\s*\)",
            function.group(1),
        )
    )
    if len(anchors) != 7:
        raise FixtureReplayError(
            f"production claimed Daily Reward predicate has {len(anchors)} anchors; expected exactly 7"
        )
    return anchors


@functools.lru_cache(maxsize=1)
def _load_home_inactivity_reload_contract() -> tuple[tuple[int, int, int, int], ...]:
    source = OPEN_HOME_COLLECTORS_SOURCE.read_text(encoding="utf-8-sig")
    function = re.search(
        r"Func\s+OpenHomeInactivityReloadDialogReady\(\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if function is None:
        raise FixtureReplayError("cannot load the production inactivity reload predicate")
    anchors = tuple(
        (int(x), int(y), int(color, 16), int(variation))
        for x, y, color, variation in re.findall(
            r"_OpenHomePixelNear\(\s*(\d+)\s*,\s*(\d+)\s*,\s*0x([0-9A-Fa-f]{6})\s*,\s*(\d+)\s*\)",
            function.group(1),
        )
    )
    if len(anchors) != 6:
        raise FixtureReplayError(
            f"production inactivity reload predicate has {len(anchors)} anchors; expected exactly 6"
        )
    return anchors


@functools.lru_cache(maxsize=1)
def _load_home_welcome_back_contract() -> tuple[tuple[int, int, int, int], ...]:
    source = OPEN_HOME_COLLECTORS_SOURCE.read_text(encoding="utf-8-sig")
    function = re.search(
        r"Func\s+OpenHomeWelcomeBackOverlayReady\(\)(.*?)EndFunc",
        source,
        re.DOTALL,
    )
    if function is None:
        raise FixtureReplayError("cannot load the production Welcome Back overlay predicate")
    anchors = tuple(
        (int(x), int(y), int(color, 16), int(variation))
        for x, y, color, variation in re.findall(
            r"_OpenHomePixelNear\(\s*(\d+)\s*,\s*(\d+)\s*,\s*0x([0-9A-Fa-f]{6})\s*,\s*(\d+)\s*\)",
            function.group(1),
        )
    )
    if len(anchors) != 12:
        raise FixtureReplayError(
            f"production Welcome Back predicate has {len(anchors)} anchors; expected exactly 12"
        )
    return anchors


def recognize_home_main(image: DecodedPng, _sink: "NoOpActionSink") -> RecognitionResult | None:
    if not _pixel_near(image, *_load_home_main_anchor()):
        return None
    return RecognitionResult("home.maintenance.ready", (HOME_MAIN_REGION,))


def recognize_clan_request_dialog(
    image: DecodedPng,
    _sink: "NoOpActionSink",
) -> RecognitionResult | None:
    if not all(_pixel_near(image, *anchor) for anchor in _load_clan_request_dialog_anchors()):
        return None
    return RecognitionResult("clan.request.send-ready", (CLAN_REQUEST_SEND_REGION,))


def recognize_home_loot_cart(
    image: DecodedPng,
    _sink: "NoOpActionSink",
) -> RecognitionResult | None:
    anchors, scan_regions = _load_home_loot_cart_contract()
    cue_width = max(anchor[0] for anchor in anchors) + 1
    cue_height = max(anchor[1] for anchor in anchors) + 1
    for left, top, right, bottom in scan_regions:
        for x in range(left, right + 1):
            for y in range(top, bottom + 1):
                if all(_pixel_near(image, x + dx, y + dy, color, variation)
                       for dx, dy, color, variation in anchors):
                    return RecognitionResult(
                        "home.loot-cart",
                        (SafeRegion(id="loot-cart-cue", x=x, y=y, width=cue_width, height=cue_height),),
                    )
    return None


def recognize_home_daily_reward(
    image: DecodedPng,
    _sink: "NoOpActionSink",
) -> RecognitionResult | None:
    overlay_anchors, claim_anchors, centers = _load_home_daily_reward_contract()
    if not all(_pixel_near(image, *anchor) for anchor in overlay_anchors):
        return None
    matches = [
        (x, y)
        for x, y in centers
        if all(_pixel_near(image, x + dx, y + dy, color, variation)
               for dx, dy, color, variation in claim_anchors)
    ]
    if len(matches) != 1:
        return None
    x, y = matches[0]
    return RecognitionResult(
        "home.daily-reward.claim-ready",
        (SafeRegion(id="claim", x=x - 58, y=y - 21, width=117, height=40),),
    )


def recognize_home_daily_reward_claimed(
    image: DecodedPng,
    _sink: "NoOpActionSink",
) -> RecognitionResult | None:
    if not all(_pixel_near(image, *anchor) for anchor in _load_home_daily_reward_claimed_contract()):
        return None
    return RecognitionResult(
        "home.daily-reward.claimed-close-ready",
        (SafeRegion(id="close", x=741, y=154, width=36, height=38),),
    )


def recognize_home_inactivity_reload(
    image: DecodedPng,
    _sink: "NoOpActionSink",
) -> RecognitionResult | None:
    if not all(_pixel_near(image, *anchor) for anchor in _load_home_inactivity_reload_contract()):
        return None
    return RecognitionResult(
        "home.inactivity-reload.operator-reload-ready",
        (SafeRegion(id="reload-game", x=232, y=404, width=112, height=31),),
    )


def recognize_home_welcome_back(
    image: DecodedPng,
    _sink: "NoOpActionSink",
) -> RecognitionResult | None:
    if not all(_pixel_near(image, *anchor) for anchor in _load_home_welcome_back_contract()):
        return None
    return RecognitionResult(
        "home.welcome-back.operator-blocked",
        (SafeRegion(id="operator-ok", x=386, y=516, width=109, height=51),),
    )


class PassiveRecognizer(Protocol):
    def __call__(
        self,
        image: DecodedPng,
        action_sink: "NoOpActionSink",
    ) -> RecognitionResult | None: ...


class NoOpActionSink:
    """Reject every input request and never execute an operating-system action."""

    def __init__(self) -> None:
        self._attempts: list[str] = []

    @property
    def attempts(self) -> tuple[str, ...]:
        return tuple(self._attempts)

    @property
    def executed_count(self) -> int:
        return 0

    def _reject(self, action: str) -> None:
        self._attempts.append(action)
        raise UnsafeActionAttempt(f"passive fixture replay rejected action attempt: {action}")

    def emit(self, action: str, *_args: Any, **_kwargs: Any) -> None:
        self._reject(f"emit:{action}")

    def click(self, *_args: Any, **_kwargs: Any) -> None:
        self._reject("click")

    def tap(self, *_args: Any, **_kwargs: Any) -> None:
        self._reject("tap")

    def type_text(self, *_args: Any, **_kwargs: Any) -> None:
        self._reject("type_text")

    def key(self, *_args: Any, **_kwargs: Any) -> None:
        self._reject("key")

    def swipe(self, *_args: Any, **_kwargs: Any) -> None:
        self._reject("swipe")


@dataclass(frozen=True)
class ReplayContract:
    adapter: str
    expected_state: str
    safe_regions: tuple[SafeRegion, ...]


@dataclass(frozen=True)
class ReplayReport:
    manifest_entries: int
    verified_entries: int
    replayed_entries: int
    skipped_entries: int
    unknown_checks: int
    replayed_fixture_ids: tuple[str, ...]
    skipped_fixture_ids: tuple[str, ...]
    checked_adapters: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for field in ("replayed_fixture_ids", "skipped_fixture_ids", "checked_adapters"):
            value[field] = list(value[field])
        return value


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureReplayError(f"cannot read {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise FixtureReplayError(f"{label} {path} must contain a JSON object")
    return value


def _resolve_repo_path(root: Path, value: Any, *, fixture_id: str, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FixtureReplayError(f"{fixture_id}: manifest {field} must be a non-empty path")
    root = root.resolve()
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise FixtureReplayError(f"{fixture_id}: manifest {field} escapes the replay root") from error
    return candidate


def _load_contract(metadata: Mapping[str, Any], *, fixture_id: str) -> ReplayContract:
    raw = metadata.get("replay_contract")
    if not isinstance(raw, dict):
        raise FixtureReplayError(f"{fixture_id}: verified metadata is missing replay_contract")
    if raw.get("schema_version") != 1:
        raise FixtureReplayError(f"{fixture_id}: replay_contract schema_version must be 1")
    adapter = raw.get("adapter")
    expected_state = raw.get("expected_state")
    if not isinstance(adapter, str) or not adapter.strip():
        raise FixtureReplayError(f"{fixture_id}: replay_contract adapter must be a non-empty string")
    if not isinstance(expected_state, str) or not expected_state.strip():
        raise FixtureReplayError(f"{fixture_id}: replay_contract expected_state must be a non-empty string")
    raw_regions = raw.get("safe_regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise FixtureReplayError(f"{fixture_id}: replay_contract must declare at least one safe region")
    regions = tuple(SafeRegion.from_mapping(item, fixture_id=fixture_id) for item in raw_regions)
    region_ids = [region.id for region in regions]
    if len(region_ids) != len(set(region_ids)):
        raise FixtureReplayError(f"{fixture_id}: replay_contract safe region ids must be unique")
    return ReplayContract(adapter=adapter.strip(), expected_state=expected_state.strip(), safe_regions=regions)


def _validate_verified_fixture(
    *,
    fixture_id: str,
    image_path: Path,
    metadata_path: Path,
    expected_width: int,
    expected_height: int,
) -> tuple[DecodedPng, ReplayContract]:
    metadata = _read_json(metadata_path, label=f"metadata for {fixture_id}")
    if metadata.get("fixture_id") != fixture_id:
        raise FixtureReplayError(f"{fixture_id}: metadata fixture_id does not match the manifest")
    if not str(metadata.get("reviewed_by", "")).strip() or not str(metadata.get("reviewed_at", "")).strip():
        raise FixtureReplayError(f"{fixture_id}: verified metadata lacks reviewer attestation")
    try:
        image = decode_png(image_path)
    except (OSError, ValueError) as error:
        raise FixtureReplayError(f"{fixture_id}: cannot decode fixture image: {error}") from error
    if (image.width, image.height) != (expected_width, expected_height):
        raise FixtureReplayError(
            f"{fixture_id}: decoded size is {image.width}x{image.height}, expected {expected_width}x{expected_height}"
        )
    if (metadata.get("width"), metadata.get("height")) != (image.width, image.height):
        raise FixtureReplayError(f"{fixture_id}: metadata dimensions do not match decoded pixels")
    expected_hash = metadata.get("sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise FixtureReplayError(f"{fixture_id}: metadata sha256 is missing or malformed")
    actual_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    if actual_hash.lower() != expected_hash.lower():
        raise FixtureReplayError(f"{fixture_id}: fixture image sha256 does not match metadata")
    contract = _load_contract(metadata, fixture_id=fixture_id)
    for region in contract.safe_regions:
        region.assert_within(image, fixture_id=fixture_id)
    return image, contract


def _recognize(
    recognizer: PassiveRecognizer,
    image: DecodedPng,
    *,
    fixture_id: str,
    adapter: str,
) -> RecognitionResult | None:
    sink = NoOpActionSink()
    try:
        result = recognizer(image, sink)
    except UnsafeActionAttempt:
        raise
    except Exception as error:
        raise FixtureReplayError(f"{fixture_id}: adapter {adapter!r} raised {type(error).__name__}: {error}") from error
    if sink.attempts or sink.executed_count:
        raise FixtureReplayError(f"{fixture_id}: adapter {adapter!r} attempted an action during passive replay")
    if result is not None and not isinstance(result, RecognitionResult):
        raise FixtureReplayError(f"{fixture_id}: adapter {adapter!r} returned an invalid recognition result")
    return result


def replay_verified_fixtures(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    root: Path = ROOT,
    recognizers: Mapping[str, PassiveRecognizer] | None = None,
    require_verified: bool = False,
) -> ReplayReport:
    """Replay verified fixtures and require every used adapter to reject a black unknown frame."""

    recognizers = recognizers or {}
    manifest = _read_json(Path(manifest_path), label="fixture manifest")
    entries = manifest.get("required_fixtures")
    if not isinstance(entries, list):
        raise FixtureReplayError("fixture manifest required_fixtures must be a list")
    capture_contract = manifest.get("capture_contract")
    if not isinstance(capture_contract, dict):
        raise FixtureReplayError("fixture manifest capture_contract must be an object")
    width = capture_contract.get("width")
    height = capture_contract.get("height")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise FixtureReplayError("fixture manifest capture width must be a positive integer")
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        raise FixtureReplayError("fixture manifest capture height must be a positive integer")

    replayed: list[str] = []
    skipped: list[str] = []
    used_adapters: dict[str, PassiveRecognizer] = {}
    verified_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise FixtureReplayError("each required fixture entry must be an object")
        fixture_id = entry.get("id")
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise FixtureReplayError("each required fixture entry must have a non-empty id")
        fixture_id = fixture_id.strip()
        if entry.get("status") != "verified":
            skipped.append(fixture_id)
            continue
        verified_count += 1
        image_path = _resolve_repo_path(root, entry.get("image_path"), fixture_id=fixture_id, field="image_path")
        metadata_path = _resolve_repo_path(
            root,
            entry.get("metadata_path"),
            fixture_id=fixture_id,
            field="metadata_path",
        )
        image, contract = _validate_verified_fixture(
            fixture_id=fixture_id,
            image_path=image_path,
            metadata_path=metadata_path,
            expected_width=width,
            expected_height=height,
        )
        recognizer = recognizers.get(contract.adapter)
        if recognizer is None:
            raise FixtureReplayError(
                f"{fixture_id}: no passive production recognizer is registered for adapter {contract.adapter!r}"
            )
        result = _recognize(recognizer, image, fixture_id=fixture_id, adapter=contract.adapter)
        if result is None:
            raise FixtureReplayError(f"{fixture_id}: adapter {contract.adapter!r} returned unknown")
        if result.state != contract.expected_state:
            raise FixtureReplayError(
                f"{fixture_id}: adapter {contract.adapter!r} returned state {result.state!r}; "
                f"expected {contract.expected_state!r}"
            )
        actual_regions = tuple(result.safe_regions)
        for region in actual_regions:
            if not isinstance(region, SafeRegion):
                raise FixtureReplayError(f"{fixture_id}: adapter returned a malformed safe region")
            region.assert_within(image, fixture_id=fixture_id)
        if actual_regions != contract.safe_regions:
            raise FixtureReplayError(f"{fixture_id}: adapter safe regions do not exactly match the reviewed contract")
        replayed.append(fixture_id)
        used_adapters[contract.adapter] = recognizer

    if require_verified and verified_count == 0:
        raise FixtureReplayError("fixture manifest contains no verified fixtures; replay would prove nothing")

    if used_adapters:
        unknown = DecodedPng(
            width=width,
            height=height,
            channels=3,
            color_type=2,
            pixels=bytes(width * height * 3),
        )
        for adapter, recognizer in sorted(used_adapters.items()):
            result = _recognize(recognizer, unknown, fixture_id="<unknown-black-frame>", adapter=adapter)
            if result is not None:
                raise FixtureReplayError(
                    f"<unknown-black-frame>: adapter {adapter!r} returned {result.state!r} instead of failing closed"
                )

    return ReplayReport(
        manifest_entries=len(entries),
        verified_entries=verified_count,
        replayed_entries=len(replayed),
        skipped_entries=len(skipped),
        unknown_checks=len(used_adapters),
        replayed_fixture_ids=tuple(replayed),
        skipped_fixture_ids=tuple(skipped),
        checked_adapters=tuple(sorted(used_adapters)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--require-verified",
        action="store_true",
        help="fail when the manifest has no verified captures",
    )
    parser.add_argument("--json", action="store_true", help="print the replay report as JSON")
    args = parser.parse_args(argv)
    try:
        report = replay_verified_fixtures(
            args.manifest,
            root=args.root,
            recognizers={
                HOME_MAIN_ADAPTER: recognize_home_main,
                CLAN_REQUEST_DIALOG_ADAPTER: recognize_clan_request_dialog,
                HOME_LOOT_CART_ADAPTER: recognize_home_loot_cart,
                HOME_DAILY_REWARD_ADAPTER: recognize_home_daily_reward,
                HOME_DAILY_REWARD_CLAIMED_ADAPTER: recognize_home_daily_reward_claimed,
                HOME_INACTIVITY_RELOAD_ADAPTER: recognize_home_inactivity_reload,
                HOME_WELCOME_BACK_ADAPTER: recognize_home_welcome_back,
            },
            require_verified=args.require_verified,
        )
    except FixtureReplayError as error:
        print(f"fixture replay failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(
            f"fixture replay: {report.replayed_entries}/{report.verified_entries} verified replayed; "
            f"{report.skipped_entries} non-verified skipped; {report.unknown_checks} adapter unknown checks"
        )
        if report.verified_entries == 0:
            print("NO CURRENT-CLIENT RECOGNITION EVIDENCE: the manifest has no verified fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
