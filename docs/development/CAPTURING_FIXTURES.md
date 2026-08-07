# Capturing current-client fixtures

Recognition is blocked on 20 screenshots of the current game. Until they exist, no battle surface
can move from unverified to verified, which is why nearly everything in the status table says "not
demonstrated".

`tools/capture_fixture.py` handles everything around a screenshot: dimension checking, filing,
hashing, and writing metadata that matches the schema. You take the picture; it does the paperwork.

**This needs Windows**, an emulator at 860 × 732, and the current game client. It cannot be done
from CI.

---

## The ladder

A fixture climbs four rungs, and nothing skips a step:

| Rung | Means | Command |
|---|---|---|
| `missing` | No capture exists | — |
| `captured` | Image filed, metadata stubbed | `add` |
| `redacted` | You confirmed nothing identifying is visible | `redact` |
| `verified` | You confirmed the image shows what recognition needs | `verify` |

The release gate needs all 20 at `verified`.

---

## Doing one

**See what is outstanding:**

```bash
python tools/capture_fixture.py list
```

**Take the screenshot.** The emulator must be at 860 × 732 and the shot must be of the emulator
surface only, not the whole desktop. Do not crop or rescale afterwards — resizing resamples pixels
and corrupts the template matching this exists to support.

**File it:**

```bash
python tools/capture_fixture.py add home.th18.default C:\path\to\shot.png --game-version 18.4.1
```

It refuses anything that is not exactly 860 × 732, so a wrong-sized capture fails here rather than
silently poisoning recognition later.

**Write the assertions.** Open the metadata file it just created and replace the `TODO` line with
what the image actually has to show, for example:

```json
"assertions": [
  "The Town Hall is level 18 and shows the Guardian platform",
  "The four resource counters are readable in the top-left",
  "No player or clan name appears anywhere in the frame"
]
```

These are what a reviewer checks against, so be specific. "Shows the village" is useless; "the
Attack button is present at the bottom-left and not covered by an event banner" is not.

**Confirm privacy:**

```bash
python tools/capture_fixture.py redact home.th18.default
```

It prints the redaction contract and asks you to confirm. If you edited the image to blur anything,
it recomputes the hash — the validator would otherwise reject the mismatch.

**Sign it off:**

```bash
python tools/capture_fixture.py verify home.th18.default --reviewer "your name"
```

It refuses while a `TODO` assertion remains, then shows the assertions and asks whether they all
hold.

**Check and commit:**

```bash
python tools/validate_current_client_fixtures.py
git add tests/fixtures/current-client && git commit -m "Add TH18 baseline fixture"
```

---

## What gets committed

Both the PNG and its metadata. The metadata records when it was captured, against which game
version, its SHA-256, whether privacy review passed, the assertions, and who signed off.

The hash matters: it is what proves the reviewed image is the one still in the tree. Edit the PNG
and the validator fails until the fixture goes back through `redact`.

---

## Privacy

The capture contract is in `manifest.json` and the tool prints it before asking you to confirm.
Remove player names, clan names, chat text, account identifiers, purchase information, notification
contents, and machine-specific paths.

These images go into a public repository. A blurred name cannot be recovered; a committed one
cannot be taken back.

---

## Verifying the tool itself

```bash
python tools/capture_fixture.py selftest
```

Runs offline against a synthetic PNG. CI runs it on every push, so a change that breaks the
dimension check or the hashing fails there rather than after you have captured twenty screenshots.
