#!/usr/bin/env python3
"""Small, dependency-free PNG decoder and fixture-redaction verifier.

Only lossless, non-interlaced 8-bit PNGs are accepted.  The current-client
fixture contract uses 860x732 emulator captures, so supporting the four common
grayscale/RGB color types keeps the review path deterministic without adding a
large image dependency to the bot or CI.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS_BY_COLOR_TYPE = {0: 1, 2: 3, 4: 2, 6: 4}


@dataclass(frozen=True)
class DecodedPng:
    width: int
    height: int
    channels: int
    color_type: int
    pixels: bytes


def recognition_frame_metrics(image: DecodedPng) -> dict[str, int]:
    """Return deterministic visible-content metrics for a recognition fixture.

    Alpha is intentionally excluded: a fully opaque black capture and a transparent
    black capture are equally useless as recognizer evidence.  Distinct colors are
    capped at two because the gate only needs to distinguish a flat frame from real
    visible content without retaining a large per-image set.
    """
    visible_channels = 1 if image.color_type in {0, 4} else 3
    non_black_pixels = 0
    distinct: set[bytes] = set()
    for offset in range(0, len(image.pixels), image.channels):
        visible = image.pixels[offset:offset + visible_channels]
        if any(channel > 8 for channel in visible):
            non_black_pixels += 1
        if len(distinct) < 2:
            distinct.add(visible)
    return {
        "total_pixels": image.width * image.height,
        "non_black_pixels": non_black_pixels,
        "distinct_visible_colors": len(distinct),
    }


def verify_recognition_frame(image: DecodedPng) -> dict[str, int]:
    """Reject blank or predominantly black images before they can become evidence."""
    metrics = recognition_frame_metrics(image)
    minimum_visible = max(1, metrics["total_pixels"] // 1000)
    if metrics["non_black_pixels"] < minimum_visible:
        raise ValueError(
            "fixture is blank or predominantly black; capture the fully rendered game surface"
        )
    if metrics["distinct_visible_colors"] < 2:
        raise ValueError("fixture is a flat-color frame with no recognition content")
    return metrics


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_upper_left:
        return left
    if distance_above <= distance_upper_left:
        return above
    return upper_left


def decode_png(path: Path) -> DecodedPng:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")

    offset = len(PNG_SIGNATURE)
    ihdr: tuple[int, int, int, int, int, int, int] | None = None
    compressed = bytearray()
    saw_iend = False

    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise ValueError("truncated PNG chunk payload")
        payload = data[offset + 8:offset + 8 + length]
        declared_crc = struct.unpack(">I", data[offset + 8 + length:chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        if declared_crc != actual_crc:
            raise ValueError(f"PNG chunk {chunk_type!r} has an invalid CRC")

        if chunk_type == b"IHDR":
            if ihdr is not None or length != 13:
                raise ValueError("PNG must contain one valid IHDR chunk")
            ihdr = struct.unpack(">IIBBBBB", payload)
        elif chunk_type == b"IDAT":
            compressed.extend(payload)
        elif chunk_type == b"IEND":
            if length != 0:
                raise ValueError("invalid IEND chunk")
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end

    if ihdr is None or not compressed or not saw_iend:
        raise ValueError("PNG is missing IHDR, IDAT, or IEND")
    if offset != len(data):
        raise ValueError("data follows the PNG IEND chunk")

    width, height, bit_depth, color_type, compression, filter_method, interlace = ihdr
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    if bit_depth != 8 or color_type not in CHANNELS_BY_COLOR_TYPE:
        raise ValueError("fixture PNG must use 8-bit grayscale, RGB, grayscale-alpha, or RGBA pixels")
    if compression != 0 or filter_method != 0 or interlace != 0:
        raise ValueError("fixture PNG must use standard compression/filtering and no interlace")

    channels = CHANNELS_BY_COLOR_TYPE[color_type]
    row_bytes = width * channels
    expected_bytes = height * (row_bytes + 1)
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(bytes(compressed), expected_bytes + 1)
    if len(raw) > expected_bytes or decompressor.unconsumed_tail:
        raise ValueError("PNG pixel stream exceeds the expected decoded size")
    if not decompressor.eof or decompressor.unused_data or len(raw) != expected_bytes:
        raise ValueError("PNG pixel stream has an unexpected decompressed length")

    pixels = bytearray(width * height * channels)
    previous = bytearray(row_bytes)
    source_offset = 0
    destination_offset = 0
    for _ in range(height):
        filter_type = raw[source_offset]
        source_offset += 1
        scanline = bytearray(raw[source_offset:source_offset + row_bytes])
        source_offset += row_bytes
        if filter_type not in range(5):
            raise ValueError(f"unsupported PNG filter type {filter_type}")
        for index in range(row_bytes):
            left = scanline[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                scanline[index] = (scanline[index] + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (scanline[index] + above) & 0xFF
            elif filter_type == 3:
                scanline[index] = (scanline[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[index] = (scanline[index] + _paeth(left, above, upper_left)) & 0xFF
        pixels[destination_offset:destination_offset + row_bytes] = scanline
        destination_offset += row_bytes
        previous = scanline

    return DecodedPng(width, height, channels, color_type, bytes(pixels))


def parse_mask(value: str) -> dict[str, int]:
    try:
        x, y, width, height = (int(part.strip()) for part in value.split(","))
    except (TypeError, ValueError):
        raise ValueError(f"invalid mask {value!r}; expected x,y,width,height") from None
    return {"x": x, "y": y, "width": width, "height": height}


def normalize_masks(masks: Iterable[dict[str, int]], width: int, height: int) -> list[dict[str, int]]:
    normalized: list[dict[str, int]] = []
    for index, mask in enumerate(masks):
        if not isinstance(mask, dict) or set(mask) != {"x", "y", "width", "height"}:
            raise ValueError(f"mask {index} must contain only x, y, width, and height")
        if any(not isinstance(mask[key], int) or isinstance(mask[key], bool) for key in mask):
            raise ValueError(f"mask {index} coordinates must be integers")
        x, y, mask_width, mask_height = (mask["x"], mask["y"], mask["width"], mask["height"])
        if x < 0 or y < 0 or mask_width <= 0 or mask_height <= 0:
            raise ValueError(f"mask {index} must have non-negative origin and positive size")
        if x + mask_width > width or y + mask_height > height:
            raise ValueError(f"mask {index} exceeds the {width}x{height} image")
        for prior in normalized:
            overlaps = (
                x < prior["x"] + prior["width"]
                and x + mask_width > prior["x"]
                and y < prior["y"] + prior["height"]
                and y + mask_height > prior["y"]
            )
            if overlaps:
                raise ValueError(f"mask {index} overlaps another mask")
        normalized.append({"x": x, "y": y, "width": mask_width, "height": mask_height})
    return normalized


def verify_redaction(
    raw: DecodedPng,
    redacted: DecodedPng,
    masks: Iterable[dict[str, int]],
    *,
    no_redaction_needed: bool = False,
) -> dict[str, object]:
    if (raw.width, raw.height, raw.channels, raw.color_type) != (
        redacted.width,
        redacted.height,
        redacted.channels,
        redacted.color_type,
    ):
        raise ValueError("raw and redacted PNGs must have identical dimensions and pixel format")

    normalized = normalize_masks(masks, raw.width, raw.height)
    if no_redaction_needed and normalized:
        raise ValueError("--no-redaction-needed cannot be combined with masks")
    if not no_redaction_needed and not normalized:
        raise ValueError("declare at least one mask or pass --no-redaction-needed")
    if no_redaction_needed and raw.pixels != redacted.pixels:
        raise ValueError("--no-redaction-needed requires byte-identical decoded pixels")

    channel_count = raw.channels
    fills: list[bytes | None] = [None] * len(normalized)
    changed = 0
    for y in range(raw.height):
        for x in range(raw.width):
            start = (y * raw.width + x) * channel_count
            raw_pixel = raw.pixels[start:start + channel_count]
            redacted_pixel = redacted.pixels[start:start + channel_count]
            mask_index = None
            for index, mask in enumerate(normalized):
                if (mask["x"] <= x < mask["x"] + mask["width"]
                        and mask["y"] <= y < mask["y"] + mask["height"]):
                    mask_index = index
                    break
            if mask_index is None:
                if raw_pixel != redacted_pixel:
                    raise ValueError(f"pixel changed outside declared masks at {x},{y}")
                continue
            fill = fills[mask_index]
            if fill is None:
                fills[mask_index] = redacted_pixel
            elif fill != redacted_pixel:
                raise ValueError(f"mask {mask_index} is not a solid-color replacement")
            if channel_count in {2, 4} and redacted_pixel[-1] != 255:
                raise ValueError(f"mask {mask_index} is not fully opaque")
            if raw_pixel != redacted_pixel:
                changed += 1

    if no_redaction_needed:
        if changed:  # Defensive; the equality check above should make this unreachable.
            raise ValueError("--no-redaction-needed requires byte-identical decoded pixels")
    elif changed == 0:
        raise ValueError("declared masks did not change any pixels")

    rendered_masks: list[dict[str, object]] = []
    for mask, fill in zip(normalized, fills):
        rendered = dict(mask)
        rendered["fill_hex"] = "#" + (fill or b"").hex().upper()
        rendered_masks.append(rendered)
    return {"changed_pixels": changed, "masks": rendered_masks}
