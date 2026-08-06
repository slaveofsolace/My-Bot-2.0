# Current-client fixtures

These fixtures are the evidence layer for screen recognition and route readiness. A feature must not move to `supported` because a coordinate or template appears plausible; its required fixture, recognition assertions, and controlled runtime test must all pass.

## Capture contract

Capture the game content at the engine's canonical **860 × 732** client size and save it as PNG in `images/` using the exact fixture ID from `manifest.json`:

```text
images/battle.ranked.entry.png
metadata/battle.ranked.entry.json
```

Do not resize, crop, sharpen, recolor, or recompress a fixture after capture. Those operations change pixel and OCR evidence.

## Privacy review

Before a fixture is committed, remove or replace:

- player and clan names;
- Supercell IDs or other account identifiers;
- chat messages and social notifications;
- purchase, payment, or offer-account information;
- email addresses, machine usernames, and local paths;
- any unrelated personal content visible outside the game window.

Redaction must not cover the control, text, icon, border, or background area being tested. Recapture the state when safe redaction would invalidate the evidence.

## Metadata

Every non-missing fixture requires a metadata JSON file:

```json
{
  "schema_version": 1,
  "fixture_id": "battle.ranked.entry",
  "captured_at": "2026-08-06T15:30:00Z",
  "game_version": "documented-client-version",
  "source_type": "authorized-test-account",
  "width": 860,
  "height": 732,
  "sha256": "64-lowercase-hex-characters",
  "redacted": true,
  "redaction_notes": "Player and clan labels replaced outside recognition regions.",
  "assertions": [
    "Ranked entry control is visible",
    "Remaining-attack area is present"
  ],
  "reviewed_by": "",
  "reviewed_at": "",
  "notes": ""
}
```

`reviewed_by` and `reviewed_at` are required only when the manifest status becomes `verified`.

## Status progression

1. `missing` — no image or metadata is committed.
2. `captured` — image and metadata exist; privacy review is incomplete.
3. `redacted` — privacy review is complete; recognition assertions still need approval.
4. `verified` — privacy review and recognition assertions are approved.

Run the validator after every fixture change:

```powershell
python tools/validate_current_client_fixtures.py --json fixture-validation.json
```

Use `--require-complete` only for a release gate. It fails while any required fixture is still missing.
