#!/usr/bin/env python3
"""Lay out the Run Planner exactly as the AutoIt code does, then check and draw it.

The GUI cannot be launched outside Windows, so this replays the same arithmetic from
COCBot/GUI/MBR GUI Design Run Planner.au3 against the generated metadata. It reports controls that
overflow the child window or overlap each other, and can emit an HTML preview at true pixel size.

Run with --html to write a preview, or plain to get the geometry report.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "config/ui/run-planner.settings.json"
DESIGN = ROOT / "COCBot/GUI/MBR GUI Design Run Planner.au3"

# From COCBot/MBR GUI Design Mini.au3: the child window is the main window minus its chrome.
GUI_MAIN_WIDTH = 472
GUI_MAIN_HEIGHT = 692
CHILD_W = GUI_MAIN_WIDTH - 20      # $g_iSizeWGrpTab1
CHILD_H = GUI_MAIN_HEIGHT - 255    # $g_iSizeHGrpTab1

TAB_HEIGHT = 188
# These mirror the AutoIt source exactly. check_design_constants() asserts the source still uses
# them, and layout() draws with them, so the guard and the renderer cannot drift apart.
POST_TAB_ADVANCE = 194
DETAIL_HEIGHT = 76
POST_DETAIL_ADVANCE = 82
TAB_HEADER = 52   # two caption rows: the strip is multiline


class Box:
    def __init__(self, kind, x, y, w, h, text="", tab=None):
        self.kind, self.x, self.y, self.w, self.h = kind, x, y, w, h
        self.text, self.tab = text, tab

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    def overlaps(self, other):
        return not (self.right <= other.x or other.right <= self.x
                    or self.bottom <= other.y or other.bottom <= self.y)


def check_design_constants(errors):
    """The preview is only meaningful if it still matches the AutoIt source it models."""
    source = DESIGN.read_text(encoding="utf-8-sig")
    expected = [
        (r"Local \$iLeft = 8", "iLeft = 8"),
        (r"Local \$iWidth = \$g_iSizeWGrpTab1 - 22", "iWidth = child width - 22"),
        (r"GUICtrlCreateTab\(\$iLeft, \$y, \$iWidth, 188, \$TCS_MULTILINE\)", "tab height 188, multiline"),
        (r"Local \$iRowY = \$y \+ 52", "row origin = tab top + 52"),
        (r"Local \$iCtrlX = \$iLeft \+ 150", "control column at iLeft + 150"),
        (r"Local \$iCtrlW = \$iWidth - 166", "control width = iWidth - 166"),
        (rf"\$y \+= {POST_TAB_ADVANCE}", f"post-tab advance {POST_TAB_ADVANCE}"),
        (rf"\$iWidth, {DETAIL_HEIGHT}, BitOR\(\$ES_READONLY", f"detail height {DETAIL_HEIGHT}"),
        (rf"\$y \+= {POST_DETAIL_ADVANCE}", f"post-detail advance {POST_DETAIL_ADVANCE}"),
    ]
    for pattern, label in expected:
        if not re.search(pattern, source):
            errors.append(f"design drift: AutoIt source no longer matches '{label}' - preview is stale")


def decorated_default(setting):
    """Mirror _RunPlannerDecoratedLabel: the combo shows a label with its availability appended."""
    for option in setting.get("options", []):
        if option["value"] != setting.get("default"):
            continue
        label, availability = option["label"], option["availability"]
        if availability == "available":
            return label + ("  (recommended)" if option.get("recommended") else "")
        return label + {"planned": "  (not implemented)",
                        "unsupported": "  (unsupported)"}.get(availability, "  (unverified)")
    return str(setting.get("default", ""))


def layout():
    doc = json.loads(METADATA.read_text(encoding="utf-8-sig"))
    sections = sorted(doc["sections"], key=lambda s: s["order"])

    boxes: list[Box] = []
    left, width, y = 8, CHILD_W - 22, 6

    boxes.append(Box("title", left, y, width, 18, doc["title"]))
    y += 20
    boxes.append(Box("desc", left, y, width, 32, doc["description"]))
    y += 36
    boxes.append(Box("banner", left, y, width, 28, "(verification banner)"))
    y += 32

    tab_top = y
    boxes.append(Box("tab", left, y, width, TAB_HEIGHT, ""))

    label_x, ctrl_x, ctrl_w = left + 8, left + 150, width - 166

    for section in sections:
        row = tab_top + TAB_HEADER
        tab_name = section["tab_label"]
        for setting in section["settings"]:
            kind = setting["type"]
            label = setting["label"] + (" *" if setting.get("required") else "")
            boxes.append(Box("label", label_x, row + 3, 138, 18, label, tab_name))

            if kind == "select":
                boxes.append(Box("combo", ctrl_x, row, ctrl_w, 20, decorated_default(setting), tab_name))
                row += 26
            elif kind == "multi-select":
                boxes.append(Box("combo", ctrl_x, row, ctrl_w - 90, 20, decorated_default(setting), tab_name))
                boxes.append(Box("button", ctrl_x + ctrl_w - 86, row, 40, 21, "Add", tab_name))
                boxes.append(Box("button", ctrl_x + ctrl_w - 43, row, 43, 21, "Drop", tab_name))
                row += 26
                boxes.append(Box("label", label_x, row + 3, 138, 18, "Active slots", tab_name))
                boxes.append(Box("input", ctrl_x, row, ctrl_w, 20, "No Heroes selected", tab_name))
                row += 26
            elif kind == "integer":
                boxes.append(Box("input", ctrl_x, row, 90, 20, str(setting["default"]), tab_name))
                unit = setting.get("unit", "")
                if unit:
                    boxes.append(Box("unit", ctrl_x + 96, row + 3, ctrl_w - 96, 18, unit, tab_name))
                row += 26
            elif kind == "boolean":
                boxes.append(Box("check", ctrl_x, row, 20, 20, "", tab_name))
                boxes.append(Box("unit", ctrl_x + 24, row + 3, ctrl_w - 24, 18, setting["summary"], tab_name))
                row += 26
            else:
                boxes.append(Box("input", ctrl_x, row, ctrl_w, 20, str(setting["default"]), tab_name))
                empty = setting.get("empty_state", "")
                if empty:
                    row += 20
                    boxes.append(Box("hint", ctrl_x, row, ctrl_w, 16, empty, tab_name))
                    row += 8
                row += 26

    y += POST_TAB_ADVANCE
    boxes.append(Box("label", left, y, width, 16, "About the selected option"))
    y += 18
    boxes.append(Box("edit", left, y, width, DETAIL_HEIGHT,
                     "Select a control to see what it does and what it still needs."))
    y += POST_DETAIL_ADVANCE
    boxes.append(Box("button", left, y, 90, 24, "Apply plan"))
    boxes.append(Box("button", left + 96, y, 70, 24, "Reset"))
    boxes.append(Box("status", left + 174, y + 5, width - 174, 18, "(status)"))

    return boxes, tab_top, [s["tab_label"] for s in sections]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, help="write an HTML preview at true pixel size")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    check_design_constants(errors)
    boxes, tab_top, page_order = layout()

    tab_bottom = tab_top + TAB_HEIGHT

    for box in boxes:
        if box.right > CHILD_W:
            errors.append(f"{box.kind} '{box.text[:28]}' overflows the window right edge "
                          f"({box.right} > {CHILD_W})")
        if box.bottom > CHILD_H:
            errors.append(f"{box.kind} '{box.text[:28]}' overflows the window bottom "
                          f"({box.bottom} > {CHILD_H})")
        # Controls belonging to a tab page must stay inside the tab body.
        if box.tab and box.bottom > tab_bottom:
            errors.append(f"tab '{box.tab}': {box.kind} '{box.text[:28]}' spills past the tab body "
                          f"({box.bottom} > {tab_bottom})")

    # Overlaps only matter between controls drawn on the same surface.
    def surface(b):
        return b.tab or ("__tabframe__" if b.kind == "tab" else "__root__")

    groups: dict[str, list[Box]] = {}
    for box in boxes:
        if box.kind == "tab":
            continue
        groups.setdefault(surface(box), []).append(box)

    for name, items in groups.items():
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if a.overlaps(b):
                    errors.append(f"{name}: {a.kind} '{a.text[:20]}' overlaps {b.kind} '{b.text[:20]}'")

    # Approximate Arial advance widths at the sizes the design uses.
    char_px = {"label": 5.8, "combo": 5.8, "input": 5.8, "unit": 5.2, "hint": 5.2,
               "button": 5.8, "status": 5.8, "title": 7.0}
    for box in boxes:
        if box.kind not in char_px or not box.text:
            continue
        # Multi-line controls wrap instead of clipping.
        if box.kind in ("desc", "banner", "edit"):
            continue
        needed = len(box.text) * char_px[box.kind] + 8
        if needed > box.w:
            warnings.append(f"{box.tab or 'root'}: {box.kind} text likely clipped "
                            f"(~{int(needed)}px in {box.w}px): {box.text[:52]!r}")

    tab_pages = page_order
    used = max((b.bottom for b in boxes if b.tab), default=tab_top)
    if tab_bottom - used > 60:
        warnings.append(f"tallest tab page leaves {tab_bottom - used}px unused inside the tab body")

    report = {
        "schema_version": 1,
        "window": {"width": CHILD_W, "height": CHILD_H},
        "controls": len(boxes),
        "tab_pages": tab_pages,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }

    if args.html:
        args.html.write_text(render_html(boxes, tab_top, page_order), encoding="utf-8")
        report["preview"] = str(args.html)

    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


def render_html(boxes, tab_top, pages) -> str:
    css_kind = {
        "title": "font:bold 13px Arial;",
        "desc": "font:11px Arial;color:#333;",
        "banner": "font:bold 11px Arial;color:#8b1a1a;background:#fff6f6;border:1px solid #f0d0d0;",
        "label": "font:11px Arial;",
        "unit": "font:10px Arial;color:#777;",
        "hint": "font:10px Arial;color:#777;",
        "combo": "font:11px Arial;background:#fff;border:1px solid #7a7a7a;",
        "input": "font:11px Arial;background:#fff;border:1px solid #7a7a7a;",
        "check": "background:#fff;border:1px solid #7a7a7a;",
        "button": "font:11px Arial;background:linear-gradient(#fdfdfd,#e6e6e6);border:1px solid #8a8a8a;border-radius:3px;text-align:center;",
        "edit": "font:10px Arial;background:#fff;border:1px solid #7a7a7a;color:#333;",
        "status": "font:11px Arial;color:#444;",
        "tab": "border:1px solid #9a9a9a;background:#f2f1f0;",
    }

    def draw(page):
        out = []
        for b in boxes:
            if b.tab and b.tab != page:
                continue
            style = css_kind.get(b.kind, "")
            pad = "padding:2px 4px;box-sizing:border-box;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;"
            if b.kind in ("desc", "banner", "edit"):
                pad = "padding:3px 5px;box-sizing:border-box;overflow:hidden;white-space:normal;line-height:1.25;"
            out.append(
                f'<div style="position:absolute;left:{b.x}px;top:{b.y}px;width:{b.w}px;height:{b.h}px;'
                f'{style}{pad}">{html.escape(b.text)}</div>')
        # Tab strip. TCS_MULTILINE wraps captions onto a second row rather than clipping them, so the
        # preview wraps too: a strip drawn on one row would hide exactly the overflow worth seeing.
        x, row = 9, 0
        strip_right = 9 + CHILD_W - 22
        for name in pages:
            w = 8 + len(name) * 6
            if x + w > strip_right:
                x, row = 9, row + 1
            sel = "background:#fff;font-weight:bold;" if name == page else "background:#e2e0de;"
            top = tab_top + 1 + row * 25
            out.append(f'<div style="position:absolute;left:{x}px;top:{top}px;width:{w}px;height:22px;'
                       f'font:10px Arial;text-align:center;padding-top:5px;box-sizing:border-box;'
                       f'border:1px solid #9a9a9a;{sel}">{html.escape(name)}</div>')
            x += w + 1
        return "".join(out)

    panels = "".join(
        f'<figure><figcaption>{html.escape(p)}</figcaption>'
        f'<div class="win">{draw(p)}</div></figure>' for p in pages)

    return f"""<!doctype html><meta charset="utf-8"><title>Run Planner preview</title>
<style>
 body{{background:#5a5a5a;font:12px system-ui;margin:16px;color:#eee}}
 .wrap{{display:flex;flex-wrap:wrap;gap:18px}}
 figure{{margin:0}}
 figcaption{{margin:0 0 6px;font:bold 12px system-ui;color:#fff}}
 .win{{color:#111;position:relative;width:{CHILD_W}px;height:{CHILD_H}px;background:#f0efee;
      border:1px solid #222;box-shadow:0 3px 10px rgba(0,0,0,.5)}}
</style>
<h2 style="font:bold 14px system-ui">Run Planner &mdash; {CHILD_W}&times;{CHILD_H} child window, one panel per tab</h2>
<div class="wrap">{panels}</div>
"""


if __name__ == "__main__":
    raise SystemExit(main())
