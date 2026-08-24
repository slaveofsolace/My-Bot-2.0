"""Fail-closed, game-input-free clean-room recognition primitives.

This module never opens the inherited recognition DLL and never talks to an
emulator.  The only filesystem path supplied by a caller is a relative PNG
inside a marked, task-owned capture root.  Recognition assets and operations
are selected by enums from the repository-owned manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import time
from typing import Any, Mapping, Sequence

try:
    from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError
except ImportError:  # pragma: no cover - exercised by the installed dependency gate
    Image = ImageChops = ImageStat = None  # type: ignore[assignment]
    UnidentifiedImageError = OSError  # type: ignore[assignment,misc]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "config" / "cleanroom-recognition.json"
FIXTURE_MANIFEST_PATH = PROJECT_ROOT / "tests" / "fixtures" / "current-client" / "manifest.json"
ROOT_MARKER_NAME = "capture-root.json"
CAPTURE_OWNER = "mybot-cleanroom-recognition"
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RecognitionExport(str, Enum):
    DO_OCR = "DoOCR"
    FIND_TILE = "FindTile"
    GET_DEPLOYABLE_NEXT_TO = "GetDeployableNextTo"
    GET_OFFSET_REDLINE = "GetOffSetRedline"
    GET_PROPERTY = "GetProperty"
    SEARCH_MULTIPLE_TILES_BETWEEN_LEVELS = "SearchMultipleTilesBetweenLevels"
    SEARCH_RED_LINES = "SearchRedLines"
    GET_LOCATION_DARK_ELIXIR_STORAGE = "getLocationDarkElixirStorage"
    GET_LOCATION_DARK_ELIXIR_STORAGE_WITH_LEVEL = "getLocationDarkElixirStorageWithLevel"
    GET_LOCATION_ELIXIR_EXTRACTOR_WITH_LEVEL = "getLocationElixirExtractorWithLevel"
    GET_LOCATION_MINE_EXTRACTOR_WITH_LEVEL = "getLocationMineExtractorWithLevel"
    GET_LOCATION_SNOW_ELIXIR_EXTRACTOR_WITH_LEVEL = "getLocationSnowElixirExtractorWithLevel"
    GET_LOCATION_SNOW_MINE_EXTRACTOR_WITH_LEVEL = "getLocationSnowMineExtractorWithLevel"
    GET_LOCATION_TOWN_HALL = "getLocationTownHall"
    GET_RED_AREA = "getRedArea"
    GET_RED_AREA_SIDE_BUILDING = "getRedAreaSideBuilding"
    OCR = "ocr"


class RecognitionStatus(str, Enum):
    PASS = "PASS"
    NO_MATCH = "NO_MATCH"
    UNAVAILABLE = "UNAVAILABLE"
    REJECTED = "REJECTED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"


@dataclass(frozen=True)
class RecognitionRequest:
    export: str
    screenshot_relative_path: str
    asset_id: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    previous_screenshot_sha256: str | None = None
    deadline_ms: int = 500
    max_results: int = 8


@dataclass(frozen=True)
class RecognitionResult:
    export: str
    status: RecognitionStatus
    available: bool
    reason_code: str
    detail: str
    screenshot_sha256: str | None
    asset_id: str | None
    elapsed_ms: int
    result_count: int
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "export": self.export,
            "status": self.status.value,
            "available": self.available,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "screenshot_sha256": self.screenshot_sha256,
            "asset_id": self.asset_id,
            "elapsed_ms": self.elapsed_ms,
            "result_count": self.result_count,
            "payload": dict(self.payload),
        }


class RecognitionPolicyError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class RecognitionDeadlineExceeded(RecognitionPolicyError):
    def __init__(self) -> None:
        super().__init__("DEADLINE_EXCEEDED", "Recognition deadline expired before a result was produced")


@dataclass(frozen=True)
class _Capture:
    path: Path
    sha256: str
    width: int
    height: int
    image: Any


def _sha256_file(path: Path, maximum_bytes: int) -> str:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(chunk)
            if total > maximum_bytes:
                raise RecognitionPolicyError("FILE_TOO_LARGE", f"File exceeds the {maximum_bytes}-byte bound")
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_normalized_text_file(path: Path, maximum_bytes: int) -> str:
    """Hash tracked text independently of Git checkout newline conversion."""
    raw = path.read_bytes()
    if len(raw) > maximum_bytes:
        raise RecognitionPolicyError("FILE_TOO_LARGE", f"File exceeds the {maximum_bytes}-byte bound")
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _load_bounded_json(path: Path, maximum_bytes: int = 262_144) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RecognitionPolicyError("MISSING_METADATA", f"Required metadata is missing: {path.name}")
    raw = path.read_bytes()
    if len(raw) > maximum_bytes:
        raise RecognitionPolicyError("METADATA_TOO_LARGE", f"Metadata exceeds the {maximum_bytes}-byte bound")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecognitionPolicyError("INVALID_METADATA", f"Invalid JSON metadata: {path.name}") from exc
    if not isinstance(value, dict):
        raise RecognitionPolicyError("INVALID_METADATA", f"Metadata root must be an object: {path.name}")
    return value


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RecognitionPolicyError("INVALID_CAPTURE_TIME", "captured_at_utc must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RecognitionPolicyError("INVALID_CAPTURE_TIME", "captured_at_utc is invalid") from exc
    return parsed.astimezone(timezone.utc)


def _strict_relative_png(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot path must be a relative POSIX PNG path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot path traversal is forbidden")
    if relative.suffix.lower() != ".png" or any(not _SAFE_ID.fullmatch(part) for part in relative.parts):
        raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot path contains an unsupported component")
    return relative


def _strict_repo_path(value: Any) -> Path:
    relative = _strict_relative_path(value)
    resolved = (PROJECT_ROOT / Path(*relative.parts)).resolve(strict=False)
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise RecognitionPolicyError("INVALID_ASSET_PATH", "Manifest asset escapes the repository root") from exc
    return resolved


def _strict_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise RecognitionPolicyError("INVALID_ASSET_PATH", "Manifest paths must be relative POSIX paths")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise RecognitionPolicyError("INVALID_ASSET_PATH", "Manifest path traversal is forbidden")
    return relative


class CleanRoomRecognitionAdapter:
    """Typed adapter with a fixed repository manifest and no game-input surface."""

    def __init__(self, capture_root: Path, expected_session_id: str):
        if not _SAFE_ID.fullmatch(expected_session_id):
            raise RecognitionPolicyError("INVALID_SESSION", "Expected session id is invalid")
        lexical_root = Path(capture_root)
        if lexical_root.is_symlink():
            raise RecognitionPolicyError("INVALID_CAPTURE_ROOT", "Capture root cannot be a symbolic link")
        self._capture_root = lexical_root.resolve(strict=True)
        if not self._capture_root.is_dir() or self._capture_root.is_symlink():
            raise RecognitionPolicyError("INVALID_CAPTURE_ROOT", "Capture root must be a real directory")
        marker = _load_bounded_json(self._capture_root / ROOT_MARKER_NAME, 16_384)
        expected_marker_keys = {"schema_version", "owner", "session_id", "created_at_utc"}
        if set(marker) != expected_marker_keys:
            raise RecognitionPolicyError("INVALID_CAPTURE_ROOT", "Capture-root marker has unexpected fields")
        if marker.get("schema_version") != 1 or marker.get("owner") != CAPTURE_OWNER:
            raise RecognitionPolicyError("INVALID_CAPTURE_ROOT", "Capture-root marker owner or schema is invalid")
        if marker.get("session_id") != expected_session_id:
            raise RecognitionPolicyError("INVALID_CAPTURE_ROOT", "Capture-root session does not match the expected owner")
        _parse_utc(marker.get("created_at_utc"))
        self._session_id = expected_session_id
        self._manifest = _load_bounded_json(MANIFEST_PATH)
        self._validate_manifest()
        self._limits = self._manifest["limits"]
        self._exports = {item["name"]: item for item in self._manifest["legacy_exports"]}
        self._assets = self._manifest["assets"]

    def _validate_manifest(self) -> None:
        if self._manifest.get("schema_version") != 1:
            raise RecognitionPolicyError("INVALID_MANIFEST", "Unsupported clean-room recognition manifest schema")
        exports = self._manifest.get("legacy_exports")
        assets = self._manifest.get("assets")
        limits = self._manifest.get("limits")
        if not isinstance(exports, list) or not isinstance(assets, dict) or not isinstance(limits, dict):
            raise RecognitionPolicyError("INVALID_MANIFEST", "Manifest exports, assets, or limits are malformed")
        names = [item.get("name") for item in exports if isinstance(item, dict)]
        expected = {item.value for item in RecognitionExport}
        if len(names) != len(expected) or set(names) != expected:
            raise RecognitionPolicyError("INVALID_MANIFEST", "Manifest must inventory exactly the 17 recognized exports")
        if len(names) != len(set(names)):
            raise RecognitionPolicyError("INVALID_MANIFEST", "Manifest export names must be unique")
        for key in (
            "max_file_bytes", "max_width", "max_height", "max_pixels", "max_results", "max_points",
            "max_deadline_ms", "max_capture_age_seconds", "minimum_distinct_colors",
        ):
            if not isinstance(limits.get(key), int) or limits[key] <= 0:
                raise RecognitionPolicyError("INVALID_MANIFEST", f"Manifest limit {key} is invalid")
        ratio = limits.get("minimum_non_black_ratio")
        if not isinstance(ratio, (int, float)) or not 0 < float(ratio) < 1:
            raise RecognitionPolicyError("INVALID_MANIFEST", "Manifest black-frame ratio is invalid")
        for asset_id, asset in assets.items():
            if not _SAFE_ID.fullmatch(asset_id) or not isinstance(asset, dict):
                raise RecognitionPolicyError("INVALID_MANIFEST", "Manifest contains an invalid asset id or body")
            if asset.get("export") not in expected:
                raise RecognitionPolicyError("INVALID_MANIFEST", f"Asset {asset_id} references an unknown export")

    def recognize(self, request: RecognitionRequest) -> RecognitionResult:
        started = time.monotonic()
        try:
            try:
                export = RecognitionExport(request.export)
            except ValueError as exc:
                raise RecognitionPolicyError("UNKNOWN_EXPORT", "Operation must be one of the 17 exact enum values") from exc
            self._validate_request_envelope(request)
            metadata = self._exports[export.value]
            if metadata.get("clean_room_status") != "implemented":
                return self._result(
                    request, started, RecognitionStatus.UNAVAILABLE, False, "EXPORT_UNAVAILABLE",
                    str(metadata.get("unavailable_reason", "The export is not implemented")), None, (),
                )
            deadline = started + request.deadline_ms / 1000.0
            capture = self._validate_capture(request, deadline)
            if export is RecognitionExport.FIND_TILE:
                return self._find_tile(request, capture, deadline, started)
            if export is RecognitionExport.GET_OFFSET_REDLINE:
                return self._offset_redline(request, capture, deadline, started)
            if export is RecognitionExport.GET_DEPLOYABLE_NEXT_TO:
                return self._deployable_next_to(request, capture, deadline, started)
            raise RecognitionPolicyError("EXPORT_UNAVAILABLE", "The export has no clean-room handler")
        except RecognitionDeadlineExceeded as exc:
            return self._result(request, started, RecognitionStatus.DEADLINE_EXCEEDED, False, exc.code, exc.detail, None, ())
        except RecognitionPolicyError as exc:
            return self._result(request, started, RecognitionStatus.REJECTED, False, exc.code, exc.detail, None, ())
        except (OSError, UnidentifiedImageError) as exc:
            return self._result(request, started, RecognitionStatus.REJECTED, False, "IMAGE_DECODE_FAILED", str(exc), None, ())
        except Exception as exc:  # fail closed; do not leak a traceback across a future process boundary
            return self._result(request, started, RecognitionStatus.REJECTED, False, "INTERNAL_REJECTION", type(exc).__name__, None, ())

    def _validate_request_envelope(self, request: RecognitionRequest) -> None:
        if not isinstance(request.deadline_ms, int) or not 1 <= request.deadline_ms <= self._limits["max_deadline_ms"]:
            raise RecognitionPolicyError("INVALID_DEADLINE", "Deadline is outside the manifest bound")
        if not isinstance(request.max_results, int) or not 1 <= request.max_results <= self._limits["max_results"]:
            raise RecognitionPolicyError("INVALID_RESULT_LIMIT", "Result limit is outside the manifest bound")
        if not isinstance(request.params, Mapping) or len(request.params) > 8:
            raise RecognitionPolicyError("INVALID_PARAMETERS", "Parameters must be a small object")
        if request.asset_id is not None and not _SAFE_ID.fullmatch(request.asset_id):
            raise RecognitionPolicyError("UNKNOWN_ASSET", "Asset id is invalid")
        if request.previous_screenshot_sha256 is not None and not _HEX_SHA256.fullmatch(request.previous_screenshot_sha256):
            raise RecognitionPolicyError("INVALID_PREVIOUS_HASH", "Previous screenshot hash is invalid")

    def _check_deadline(self, deadline: float) -> None:
        if time.monotonic() > deadline:
            raise RecognitionDeadlineExceeded()

    def _validate_capture(self, request: RecognitionRequest, deadline: float) -> _Capture:
        relative = _strict_relative_png(request.screenshot_relative_path)
        lexical_path = self._capture_root / Path(*relative.parts)
        cursor = lexical_path
        while cursor != self._capture_root:
            if cursor.is_symlink():
                raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot path cannot contain symbolic links")
            cursor = cursor.parent
        try:
            path = lexical_path.resolve(strict=True)
        except OSError as exc:
            raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot does not exist inside the task-owned root") from exc
        try:
            path.relative_to(self._capture_root)
        except ValueError as exc:
            raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot escapes the task-owned capture root") from exc
        if not path.is_file() or path.is_symlink():
            raise RecognitionPolicyError("INVALID_SCREENSHOT_PATH", "Screenshot must be a regular task-owned file")
        receipt_path = path.with_name(path.name + ".capture.json")
        receipt = _load_bounded_json(receipt_path, 32_768)
        expected_receipt_keys = {
            "schema_version", "owner", "session_id", "relative_path", "sha256", "width", "height",
            "captured_at_utc", "source_kind", "source_fixture_id",
        }
        if set(receipt) != expected_receipt_keys:
            raise RecognitionPolicyError("INVALID_CAPTURE_RECEIPT", "Capture receipt has unexpected fields")
        if receipt.get("schema_version") != 1 or receipt.get("owner") != CAPTURE_OWNER:
            raise RecognitionPolicyError("INVALID_CAPTURE_RECEIPT", "Capture receipt owner or schema is invalid")
        if receipt.get("session_id") != self._session_id or receipt.get("relative_path") != relative.as_posix():
            raise RecognitionPolicyError("INVALID_CAPTURE_RECEIPT", "Capture receipt is not bound to this session and path")
        receipt_sha = receipt.get("sha256")
        if not isinstance(receipt_sha, str) or not _HEX_SHA256.fullmatch(receipt_sha):
            raise RecognitionPolicyError("INVALID_CAPTURE_RECEIPT", "Capture receipt hash is invalid")
        actual_sha = _sha256_file(path, self._limits["max_file_bytes"])
        if actual_sha != receipt_sha:
            raise RecognitionPolicyError("CAPTURE_HASH_MISMATCH", "Screenshot bytes do not match the task-owned receipt")
        if request.previous_screenshot_sha256 == actual_sha:
            raise RecognitionPolicyError("STALE_SCREENSHOT", "Screenshot hash is unchanged from the previous capture")
        captured_at = _parse_utc(receipt.get("captured_at_utc"))
        source_kind = receipt.get("source_kind")
        if source_kind == "owned-runtime-capture":
            age = (datetime.now(timezone.utc) - captured_at).total_seconds()
            if age < -10 or age > self._limits["max_capture_age_seconds"]:
                raise RecognitionPolicyError("STALE_SCREENSHOT", "Owned runtime screenshot is outside the freshness window")
            if receipt.get("source_fixture_id") is not None:
                raise RecognitionPolicyError("INVALID_CAPTURE_RECEIPT", "Runtime capture cannot claim a fixture id")
        elif source_kind == "fixture-replay":
            fixture_id = receipt.get("source_fixture_id")
            approved = {
                (asset.get("fixture_id"), asset.get("image_sha256"))
                for asset in self._assets.values() if isinstance(asset, dict)
            }
            if (fixture_id, actual_sha) not in approved:
                raise RecognitionPolicyError("UNAPPROVED_FIXTURE", "Fixture replay is not owned by the clean-room manifest")
        else:
            raise RecognitionPolicyError("INVALID_CAPTURE_RECEIPT", "Capture source_kind is unsupported")
        if Image is None:
            raise RecognitionPolicyError("PILLOW_UNAVAILABLE", "Pillow is required for bounded PNG decoding")
        with Image.open(path) as probe:
            if probe.format != "PNG":
                raise RecognitionPolicyError("UNSUPPORTED_IMAGE", "Only PNG screenshots are accepted")
            width, height = probe.size
            if width <= 0 or height <= 0 or width > self._limits["max_width"] or height > self._limits["max_height"]:
                raise RecognitionPolicyError("INVALID_DIMENSIONS", "Screenshot dimensions exceed the manifest bounds")
            if width * height > self._limits["max_pixels"]:
                raise RecognitionPolicyError("INVALID_DIMENSIONS", "Screenshot pixel count exceeds the manifest bound")
            if receipt.get("width") != width or receipt.get("height") != height:
                raise RecognitionPolicyError("CAPTURE_DIMENSION_MISMATCH", "Screenshot dimensions do not match its receipt")
            image = probe.convert("RGB")
            image.load()
        if _sha256_file(path, self._limits["max_file_bytes"]) != actual_sha:
            raise RecognitionPolicyError("CAPTURE_CHANGED_DURING_READ", "Screenshot changed while it was being decoded")
        grayscale = image.convert("L")
        histogram = grayscale.histogram()
        non_black = sum(histogram[9:])
        if non_black / (width * height) < self._limits["minimum_non_black_ratio"]:
            raise RecognitionPolicyError("BLACK_FRAME", "Screenshot is black or nearly black")
        colors = image.getcolors(maxcolors=self._limits["minimum_distinct_colors"])
        if colors is not None and len(colors) < self._limits["minimum_distinct_colors"]:
            raise RecognitionPolicyError("BLACK_FRAME", "Screenshot lacks enough visible color variation")
        self._check_deadline(deadline)
        return _Capture(path, actual_sha, width, height, image)

    def _load_asset_template(self, asset_id: str, export: RecognitionExport) -> tuple[dict[str, Any], Any]:
        asset = self._assets.get(asset_id)
        if not isinstance(asset, dict) or asset.get("export") != export.value:
            raise RecognitionPolicyError("UNKNOWN_ASSET", "Asset id is not manifest-owned for this operation")
        image_path = _strict_repo_path(asset.get("image_path"))
        metadata_path = _strict_repo_path(asset.get("metadata_path"))
        fixture_root = (PROJECT_ROOT / "tests" / "fixtures" / "current-client").resolve()
        try:
            image_path.relative_to(fixture_root / "images")
            metadata_path.relative_to(fixture_root / "metadata")
        except ValueError as exc:
            raise RecognitionPolicyError("INVALID_ASSET", "Manifest asset is outside the reviewed fixture directories") from exc
        if image_path.is_symlink() or metadata_path.is_symlink():
            raise RecognitionPolicyError("INVALID_ASSET", "Manifest assets cannot be symbolic links")
        image_sha = asset.get("image_sha256")
        metadata_sha = asset.get("metadata_sha256")
        if not isinstance(image_sha, str) or not _HEX_SHA256.fullmatch(image_sha):
            raise RecognitionPolicyError("INVALID_ASSET", "Manifest asset image hash is invalid")
        if not isinstance(metadata_sha, str) or not _HEX_SHA256.fullmatch(metadata_sha):
            raise RecognitionPolicyError("INVALID_ASSET", "Manifest asset metadata hash is invalid")
        if _sha256_file(image_path, self._limits["max_file_bytes"]) != image_sha:
            raise RecognitionPolicyError("ASSET_HASH_MISMATCH", "Manifest-owned image asset changed")
        if _sha256_normalized_text_file(metadata_path, 262_144) != metadata_sha:
            raise RecognitionPolicyError("ASSET_HASH_MISMATCH", "Manifest-owned fixture metadata changed")
        fixture_manifest = _load_bounded_json(FIXTURE_MANIFEST_PATH)
        fixture = next(
            (item for item in fixture_manifest.get("required_fixtures", []) if item.get("id") == asset.get("fixture_id")),
            None,
        )
        if not isinstance(fixture, dict) or fixture.get("status") != "verified":
            raise RecognitionPolicyError("UNAPPROVED_FIXTURE", "Manifest asset is not backed by a verified fixture")
        if fixture.get("image_path") != asset.get("image_path") or fixture.get("metadata_path") != asset.get("metadata_path"):
            raise RecognitionPolicyError("UNAPPROVED_FIXTURE", "Fixture paths disagree with the clean-room manifest")
        metadata = _load_bounded_json(metadata_path)
        if metadata.get("fixture_id") != asset.get("fixture_id") or metadata.get("sha256") != image_sha or metadata.get("redacted") is not True:
            raise RecognitionPolicyError("UNAPPROVED_FIXTURE", "Fixture privacy/hash metadata is not approved")
        with Image.open(image_path) as source:
            source_rgb = source.convert("RGB")
            source_rgb.load()
        if _sha256_file(image_path, self._limits["max_file_bytes"]) != image_sha:
            raise RecognitionPolicyError("ASSET_CHANGED_DURING_READ", "Manifest-owned image changed while it was decoded")
        box = self._validate_box(asset.get("template_box"), source_rgb.width, source_rgb.height)
        return asset, source_rgb.crop(box)

    @staticmethod
    def _validate_box(value: Any, width: int, height: int) -> tuple[int, int, int, int]:
        if not isinstance(value, list) or len(value) != 4 or any(not isinstance(item, int) for item in value):
            raise RecognitionPolicyError("INVALID_ASSET", "Asset box is malformed")
        left, top, right, bottom = value
        if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
            raise RecognitionPolicyError("INVALID_ASSET", "Asset box is outside the image")
        return left, top, right, bottom

    def _find_tile(self, request: RecognitionRequest, capture: _Capture, deadline: float, started: float) -> RecognitionResult:
        if set(request.params) != set():
            raise RecognitionPolicyError("INVALID_PARAMETERS", "FindTile accepts only its manifest-owned asset id")
        if request.asset_id is None:
            raise RecognitionPolicyError("UNKNOWN_ASSET", "FindTile requires a manifest-owned asset id")
        asset, template = self._load_asset_template(request.asset_id, RecognitionExport.FIND_TILE)
        if list((capture.width, capture.height)) != asset.get("required_screenshot_size"):
            raise RecognitionPolicyError("INVALID_DIMENSIONS", "Screenshot does not match the asset's current-client surface")
        candidates = asset.get("candidate_boxes")
        if not isinstance(candidates, list) or len(candidates) > self._limits["max_results"]:
            raise RecognitionPolicyError("INVALID_ASSET", "Asset candidate list is invalid")
        threshold = asset.get("minimum_score")
        if not isinstance(threshold, (int, float)) or not 0 <= float(threshold) <= 1:
            raise RecognitionPolicyError("INVALID_ASSET", "Asset score threshold is invalid")
        matches: list[dict[str, Any]] = []
        for raw_box in candidates:
            self._check_deadline(deadline)
            box = self._validate_box(raw_box, capture.width, capture.height)
            candidate = capture.image.crop(box)
            if candidate.size != template.size:
                raise RecognitionPolicyError("INVALID_ASSET", "Candidate and template dimensions differ")
            means = ImageStat.Stat(ImageChops.difference(template, candidate)).mean
            score = 1.0 - sum(float(item) for item in means) / (255.0 * len(means))
            if score >= float(threshold):
                left, top, right, bottom = box
                matches.append({
                    "x": (left + right) // 2,
                    "y": (top + bottom) // 2,
                    "box": [left, top, right, bottom],
                    "score": round(score, 6),
                })
        matches.sort(key=lambda item: (-item["score"], item["y"], item["x"]))
        maximum_matches = int(asset.get("maximum_matches", 1))
        if len(matches) > maximum_matches:
            return self._result(
                request, started, RecognitionStatus.REJECTED, False, "AMBIGUOUS_MATCHES",
                "More candidates matched than the manifest permits", capture.sha256, (),
            )
        limit = min(request.max_results, maximum_matches)
        bounded = matches[:limit]
        status = RecognitionStatus.PASS if bounded else RecognitionStatus.NO_MATCH
        reason = "MATCHES_FOUND" if bounded else "NO_MATCH"
        return self._result(request, started, status, True, reason, "Manifest-owned candidate search completed", capture.sha256, bounded)

    def _validated_points(self, raw: Any, capture: _Capture, name: str) -> list[tuple[int, int]]:
        if not isinstance(raw, list) or not 1 <= len(raw) <= self._limits["max_points"]:
            raise RecognitionPolicyError("INVALID_PARAMETERS", f"{name} must contain a bounded non-empty point list")
        points: list[tuple[int, int]] = []
        for item in raw:
            if not isinstance(item, list) or len(item) != 2 or any(type(value) is not int for value in item):
                raise RecognitionPolicyError("INVALID_PARAMETERS", f"{name} contains an invalid point")
            x, y = item
            if not 0 <= x < capture.width or not 0 <= y < capture.height:
                raise RecognitionPolicyError("INVALID_PARAMETERS", f"{name} contains an out-of-bounds point")
            points.append((x, y))
        return points

    @staticmethod
    def _offset_point(point: tuple[int, int], origin: tuple[int, int], distance: int, width: int, height: int) -> tuple[int, int]:
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        length = math.hypot(dx, dy)
        if length == 0:
            raise RecognitionPolicyError("INVALID_PARAMETERS", "Cannot offset a point located at its origin")
        x = round(point[0] + dx / length * distance)
        y = round(point[1] + dy / length * distance)
        return min(max(x, 0), width - 1), min(max(y, 0), height - 1)

    def _offset_redline(self, request: RecognitionRequest, capture: _Capture, deadline: float, started: float) -> RecognitionResult:
        if request.asset_id is not None or set(request.params) != {"points", "area", "distance"}:
            raise RecognitionPolicyError("INVALID_PARAMETERS", "GetOffSetRedline requires only points, area, and distance")
        points = self._validated_points(request.params["points"], capture, "points")
        area = request.params["area"]
        distance = request.params["distance"]
        if area not in {"TL", "BL", "BR", "TR"} or type(distance) is not int or not 1 <= distance <= 64:
            raise RecognitionPolicyError("INVALID_PARAMETERS", "Area or distance is outside the clean-room contract")
        center = (capture.width // 2, capture.height // 2)
        def selected(point: tuple[int, int]) -> bool:
            left, top = point[0] <= center[0], point[1] <= center[1]
            return area == ("T" if top else "B") + ("L" if left else "R")
        output: list[dict[str, int]] = []
        seen: set[tuple[int, int]] = set()
        for point in points:
            self._check_deadline(deadline)
            if not selected(point):
                continue
            transformed = self._offset_point(point, center, distance, capture.width, capture.height)
            if transformed not in seen:
                seen.add(transformed)
                output.append({"x": transformed[0], "y": transformed[1]})
        bounded = output[: request.max_results]
        status = RecognitionStatus.PASS if bounded else RecognitionStatus.NO_MATCH
        return self._result(
            request, started, status, True, "COORDINATES_READY" if bounded else "NO_MATCH",
            "Pure coordinate transform completed; legacy wire compatibility is not claimed", capture.sha256, bounded,
        )

    def _deployable_next_to(self, request: RecognitionRequest, capture: _Capture, deadline: float, started: float) -> RecognitionResult:
        if request.asset_id is not None or set(request.params) != {"targets", "redline_points", "distance"}:
            raise RecognitionPolicyError("INVALID_PARAMETERS", "GetDeployableNextTo requires targets, redline_points, and distance")
        targets = self._validated_points(request.params["targets"], capture, "targets")
        redline = self._validated_points(request.params["redline_points"], capture, "redline_points")
        distance = request.params["distance"]
        if type(distance) is not int or not 1 <= distance <= 64:
            raise RecognitionPolicyError("INVALID_PARAMETERS", "Distance is outside the clean-room contract")
        output: list[dict[str, int]] = []
        seen: set[tuple[int, int]] = set()
        for target in targets:
            self._check_deadline(deadline)
            nearest = min(redline, key=lambda point: ((point[0] - target[0]) ** 2 + (point[1] - target[1]) ** 2, point[1], point[0]))
            transformed = self._offset_point(nearest, target, distance, capture.width, capture.height)
            if transformed not in seen:
                seen.add(transformed)
                output.append({"x": transformed[0], "y": transformed[1]})
        bounded = output[: request.max_results]
        return self._result(
            request, started, RecognitionStatus.PASS, True, "COORDINATES_READY",
            "Pure nearest-redline transform completed; legacy wire compatibility is not claimed", capture.sha256, bounded,
        )

    @staticmethod
    def _result(
        request: RecognitionRequest,
        started: float,
        status: RecognitionStatus,
        available: bool,
        reason_code: str,
        detail: str,
        screenshot_sha256: str | None,
        payload_items: Sequence[Mapping[str, Any]],
    ) -> RecognitionResult:
        payload = {"items": list(payload_items), "legacy_wire_compatible": False}
        return RecognitionResult(
            export=request.export.value if isinstance(request.export, RecognitionExport) else str(request.export),
            status=status,
            available=available,
            reason_code=reason_code,
            detail=detail,
            screenshot_sha256=screenshot_sha256,
            asset_id=request.asset_id,
            elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
            result_count=len(payload_items),
            payload=payload,
        )


__all__ = [
    "CAPTURE_OWNER",
    "CleanRoomRecognitionAdapter",
    "RecognitionExport",
    "RecognitionPolicyError",
    "RecognitionRequest",
    "RecognitionResult",
    "RecognitionStatus",
    "ROOT_MARKER_NAME",
]
