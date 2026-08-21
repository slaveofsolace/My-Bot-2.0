# Capturing current-client fixtures

The current manifest defines 56 current-client fixture surfaces. Until real captures, recognition assertions, and controlled runtime checks exist, the related capabilities remain unverified. The manifest is authoritative; its count grows whenever the actuator inventory exposes another recognition boundary.

`tools/capture_fixture.py` validates dimensions, privacy-preserving pixel changes, paths, hashes, and metadata. It never edits an image and never copies the raw account capture into the repository.

This workflow needs Windows, an authorized test account, an emulator at 860 × 732, and the current game client. It cannot be completed by CI alone.

## The ladder

| Rung | Meaning | Command |
|---|---|---|
| `missing` | No reviewable fixture exists | — |
| `redacted` | Only a verified redacted derivative is tracked | `add` |
| `verified` | A reviewer approved the recognition assertions | `verify` |

## Import one fixture

List the missing evidence:

```powershell
python tools/capture_fixture.py list
```

Capture the 860 × 732 emulator surface to a private path outside the repository. Create a second 860 × 732 PNG using only opaque, solid-color rectangles over private content. Do not blur, crop, resize, sharpen, or otherwise alter it.

For every rectangle, pass `--mask x,y,width,height`:

```powershell
python tools/capture_fixture.py add home.maintenance.ready `
  C:\private\home-raw.png `
  C:\private\home-redacted.png `
  --mask 18,12,180,26 `
  --mask 690,8,160,74 `
  --game-version 18.400.9 `
  --source-type authorized-test-account `
  --privacy-notes "Player label and resource/account values replaced with opaque masks."
```

The command fails unless:

- both PNGs decode cleanly and are exactly 860 × 732;
- they use the same non-interlaced 8-bit pixel format;
- every changed pixel is inside a declared rectangle;
- each rectangle is a single, fully opaque color;
- at least one pixel changes when masks are declared;
- the derivative is neither flat-color nor predominantly black;
- both inputs remain outside the repository.

The importer and verifier also refuse to alter a verified fixture. Replacing an unverified `redacted`
fixture requires the explicit `--replace-redacted` flag. The observed game version is required;
`unknown` is not accepted. Image, metadata, and manifest JSON writes are individually atomic.

For a genuinely anonymous capture, `--no-redaction-needed` is allowed only when the decoded pixels are identical. A privacy note is still required.

The Loot Cart uses its own `home.loot-cart` fixture. Its assertions must identify exactly one cart and one unambiguous Collect button; they must not rely on chat, a fallback coordinate, or a confirmation dialog.

The startup Daily Reward uses `home.daily-reward` for the one unambiguous Claim state and `home.daily-reward.claimed` for the exact reversible post-claim close state. Neither fixture may treat an Okay/Confirm conversion dialog as a target.

Treasury uses its own `home.treasury.full` fixture. Its assertions must identify the selected Clan Castle, Treasury entry, full-state indicator, Collect button, and the contextual Treasury confirmation. It must also prove the Home storage-full indicators are absent; a generic Okay button or an inherited fallback coordinate is insufficient.

Only the redacted derivative and schema-2 metadata are copied. The metadata records the raw SHA-256 but never its path.

## Recognition review

Replace the metadata `TODO` assertion with exact, observable statements. For the shared maintenance fixture, useful statements identify the collector-ready indicators, the donation-request entry, and the upgrade entry without claiming that any action was executed.

Then verify interactively:

```powershell
python tools/capture_fixture.py verify home.maintenance.ready --reviewer "reviewer name"
```

The tool refuses verification while any assertion starts with `TODO`.
Immediately before approval it decodes the committed image again, rejects a blank/black frame,
and requires its SHA-256 to match the metadata.

## Validate

```powershell
python tools/capture_fixture.py selftest
python tools/validate_current_client_fixtures.py
```

`--require-complete` is a final evidence gate and intentionally fails until every required fixture is verified. A fixture proves recognition state only; it does not prove that collection, donation, upgrading, or another account-affecting action completed safely.
