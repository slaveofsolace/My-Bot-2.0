# Current-client fixtures

These fixtures are the evidence layer for screen recognition and route readiness. A feature must not move to `supported` because a coordinate or template appears plausible; its required fixture, recognition assertions, and controlled runtime test must all pass.

## Capture contract

Capture only the game content at the engine's canonical **860 × 732** client size. Do not resize, crop, sharpen, recolor, or recompress the recognition image. Those operations change pixel and OCR evidence.

Raw account captures must remain outside the repository. Create a same-size derivative using only opaque, solid-color rectangles over private regions. The import tool compares decoded pixels and rejects any change outside those declared rectangles.

## Privacy review

Before import, replace:

- player and clan names;
- Supercell IDs or other account identifiers;
- chat messages and social notifications;
- purchase, payment, or offer-account information;
- email addresses, machine usernames, and local paths;
- unrelated personal content visible outside the game window.

Do not blur. Do not cover a control, text, icon, border, or background area being tested. Recapture the state when safe redaction would invalidate the evidence.

## Metadata

Every non-missing fixture uses schema version 2 and records both source and derivative hashes without recording the private source path:

```json
{
  "schema_version": 2,
  "fixture_id": "home.maintenance.ready",
  "captured_at": "2026-08-13T15:30:00Z",
  "game_version": "documented-client-version",
  "source_type": "authorized-test-account",
  "width": 860,
  "height": 732,
  "sha256": "redacted-file-sha256",
  "raw_sha256": "private-source-sha256",
  "redacted_sha256": "redacted-file-sha256",
  "redacted": true,
  "redaction_masks": [
    {"x": 20, "y": 14, "width": 160, "height": 24, "fill_hex": "#000000"}
  ],
  "redaction_pixel_changes": 3840,
  "privacy_review_method": "decoded-pixel-diff-v1",
  "redaction_notes": "Player label replaced with one opaque solid mask.",
  "assertions": [
    "Collector-ready indicators are visible without covering the tested regions"
  ],
  "reviewed_by": "",
  "reviewed_at": "",
  "notes": ""
}
```

`reviewed_by` and `reviewed_at` are required only when the manifest status becomes `verified`.

## Status progression

1. `missing` — no image or metadata is committed.
2. `redacted` — a pixel-diff-verified derivative exists; recognition assertions still need approval.
3. `verified` — privacy review and recognition assertions are approved.

Run the validator after every fixture change:

```powershell
python tools/validate_current_client_fixtures.py --json fixture-validation.json
```

Use `--require-complete` only for a release gate. It fails while any required fixture is still missing.
