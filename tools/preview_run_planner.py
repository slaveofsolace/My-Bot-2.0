#!/usr/bin/env python3
"""Validate and optionally render the compact native Run Planner bridge."""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "COCBot/GUI/MBR GUI Design Run Planner.au3"
CONTROL = ROOT / "COCBot/GUI/MBR GUI Control Run Planner.au3"
CHILD_W = 472 - 20
CHILD_H = 692 - 255


@dataclass(frozen=True)
class Box:
    kind: str
    x: int
    y: int
    width: int
    height: int
    text: str

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def overlaps(self, other: "Box") -> bool:
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )


def layout() -> list[Box]:
    left, width, y = 10, CHILD_W - 24, 8
    boxes = [Box("title", left, y, width, 22, "Run Planner")]
    y += 26
    boxes.append(Box("copy", left, y, width, 42, "Build and review the complete run in the local control center."))
    y += 48
    boxes.append(Box("banner", left, y, width, 24, "LOCAL BRIDGE · loopback only · no credentials stored"))
    y += 34
    boxes.append(Box("group", left, y, width, 132, "Bridge status"))
    for offset, label, value in (
        (24, "SERVICE", "Checking local planner…"),
        (62, "SAVED PLAN", "Not checked"),
        (100, "ENGINE", "No plan loaded"),
    ):
        boxes.append(Box("label", left + 12, y + offset + 3, 92, 18, label))
        boxes.append(Box("value", left + 110, y + offset + 3, width - 122, 34, value))
    y += 142
    boxes.append(Box("detail", left, y, width, 72, "The control center writes config\\run-plan.local.json atomically."))
    y += 82
    boxes.extend(
        [
            Box("button", left, y, 138, 28, "Open control center"),
            Box("button", left + 146, y, 118, 28, "Load saved plan"),
            Box("button", left + 272, y, 76, 28, "Refresh"),
            Box("status", left, y + 34, width, 18, ""),
        ]
    )
    return boxes


def validate_source(errors: list[str]) -> None:
    design = DESIGN.read_text(encoding="utf-8-sig")
    control = CONTROL.read_text(encoding="utf-8-sig")
    required_design = (
        r"Local \$iLeft = 10",
        r"Local \$iWidth = \$g_iSizeWGrpTab1 - 24",
        r'GUICtrlCreateButton\("Open control center"',
        r'GUICtrlCreateButton\("Load saved plan"',
        r'GUICtrlCreateButton\("Refresh"',
    )
    for pattern in required_design:
        if not re.search(pattern, design):
            errors.append(f"native bridge design drift: {pattern}")
    required_control = (
        "RunPlanFileLoadIntent",
        "RunIntentCanStart",
        "http://127.0.0.1:8765/api/health",
        "ShellExecute($RUN_PLANNER_URL)",
    )
    for token in required_control:
        if token not in control:
            errors.append(f"native bridge control is missing: {token}")


def render_html(boxes: list[Box]) -> str:
    parts = []
    for box in boxes:
        classes = html.escape(box.kind)
        parts.append(
            f'<div class="box {classes}" style="left:{box.x}px;top:{box.y}px;width:{box.width}px;height:{box.height}px">'
            f"{html.escape(box.text)}</div>"
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Run Planner native bridge preview</title>
<style>
body{{background:#353a3f;color:#111;font:12px Arial;margin:20px}}
.window{{position:relative;width:{CHILD_W}px;height:{CHILD_H}px;background:#f3f3f3;border:1px solid #111}}
.box{{position:absolute;box-sizing:border-box;padding:3px 5px;overflow:hidden}}
.title{{font-size:16px;font-weight:bold}} .banner{{background:#e9eef2;color:#28404f;font-weight:bold;text-align:center}}
.group,.detail{{border:1px solid #9a9a9a;background:#fff}} .label{{font-weight:bold}} .value{{color:#35505f}}
.button{{border:1px solid #777;background:#ececec;text-align:center;padding-top:6px}}
</style>
<div class="window">{''.join(parts)}</div>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    validate_source(errors)
    boxes = layout()
    for box in boxes:
        if box.x < 0 or box.y < 0 or box.right > CHILD_W or box.bottom > CHILD_H:
            errors.append(f"{box.kind} {box.text!r} leaves the {CHILD_W}x{CHILD_H} child window")
    for index, box in enumerate(boxes):
        for other in boxes[index + 1 :]:
            if "group" in (box.kind, other.kind):
                continue
            if box.overlaps(other):
                errors.append(f"{box.kind} {box.text!r} overlaps {other.kind} {other.text!r}")
    if args.html:
        args.html.write_text(render_html(boxes), encoding="utf-8")
    report = {
        "schema_version": 2,
        "surface": "native-browser-bridge",
        "window": {"width": CHILD_W, "height": CHILD_H},
        "controls": len(boxes),
        "errors": sorted(set(errors)),
        "warnings": warnings,
    }
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
