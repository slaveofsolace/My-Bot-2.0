#!/usr/bin/env python3
"""Import a privacy-safe current-client screenshot fixture.

The recognition work is blocked on current-game screenshots (see tests/fixtures/
current-client/manifest.json). Raw account captures must remain outside the repository. This tool
compares a raw capture with an operator-created solid-mask derivative, proves that every changed
pixel is inside a declared mask, and copies only the redacted derivative into the fixture tree. It
does not touch the network and needs only the standard library.

A fixture climbs a three-rung ladder:

    list                 show every fixture and where it stands
    add <id> <raw> <redacted>     missing -> redacted (pixel changes verified)
    verify <id>          redacted -> verified   (you confirm the recognition assertions)

Run tools/validate_current_client_fixtures.py after any change; the release gate needs every
fixture at verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import time
from pathlib import Path

try:
    from tools.fixture_png import decode_png, parse_mask, verify_redaction
except ModuleNotFoundError:  # Direct execution from the tools directory.
    from fixture_png import decode_png, parse_mask, verify_redaction

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tests/fixtures/current-client"
MANIFEST = BASE / "manifest.json"
IMAGES = BASE / "images"
METADATA = BASE / "metadata"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8-sig"))


def save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find_entry(manifest: dict, fixture_id: str) -> dict | None:
    for entry in manifest.get("required_fixtures", []):
        if entry.get("id") == fixture_id:
            return entry
    return None


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("not a valid PNG with an IHDR header")
    return struct.unpack(">II", header[16:24])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metadata_path(fixture_id: str) -> Path:
    return METADATA / f"{fixture_id}.json"


def image_path(fixture_id: str) -> Path:
    return IMAGES / f"{fixture_id}.png"


def write_metadata(fixture_id: str, data: dict) -> None:
    METADATA.mkdir(parents=True, exist_ok=True)
    metadata_path(fixture_id).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_metadata(fixture_id: str) -> dict:
    return json.loads(metadata_path(fixture_id).read_text(encoding="utf-8-sig"))


# --------------------------------------------------------------------------------------------------

def cmd_list(args) -> int:
    manifest = load_manifest()
    entries = manifest.get("required_fixtures", [])
    order = {"missing": 0, "redacted": 1, "verified": 2}
    counts = {k: 0 for k in order}
    print(f"{'fixture':<28} {'status':<10} purpose")
    print("-" * 78)
    for entry in sorted(entries, key=lambda e: (order.get(e.get("status"), 0), e.get("id", ""))):
        status = entry.get("status", "?")
        counts[status] = counts.get(status, 0) + 1
        marker = {"missing": " ", "redacted": ":", "verified": "*"}.get(status, "?")
        print(f"{marker} {entry.get('id',''):<26} {status:<10} {entry.get('purpose','')}")
    print("-" * 78)
    print("  ".join(f"{k}: {counts.get(k,0)}" for k in order))
    remaining = len(entries) - counts.get("verified", 0)
    print(f"\n{remaining} of {len(entries)} still short of verified")
    return 0


def cmd_add(args) -> int:
    manifest = load_manifest()
    entry = find_entry(manifest, args.fixture_id)
    if entry is None:
        print(f"'{args.fixture_id}' is not a required fixture. Run: python tools/capture_fixture.py list")
        return 2
    if not args.privacy_notes.strip():
        print("--privacy-notes must describe the masks or explain why no redaction was needed")
        return 2

    raw_source = Path(args.raw_png).resolve()
    redacted_source = Path(args.redacted_png).resolve()
    for label, source in (("raw", raw_source), ("redacted", redacted_source)):
        if not source.is_file():
            print(f"no such {label} file: {source}")
            return 2
        if source == ROOT or ROOT in source.parents:
            print(f"{label} input must remain outside the repository: {source}")
            return 2

    try:
        raw_image = decode_png(raw_source)
        redacted_image = decode_png(redacted_source)
        masks = [parse_mask(value) for value in args.mask]
        redaction = verify_redaction(
            raw_image,
            redacted_image,
            masks,
            no_redaction_needed=args.no_redaction_needed,
        )
    except (OSError, ValueError) as exc:
        print(f"redaction verification failed: {exc}")
        return 2

    width, height = redacted_image.width, redacted_image.height

    contract = manifest.get("capture_contract", {})
    want_w, want_h = contract.get("width", 860), contract.get("height", 732)
    if (width, height) != (want_w, want_h):
        print(f"wrong size: the capture is {width}x{height}, the contract needs {want_w}x{want_h}.")
        print("Set the emulator to 860x732 and recapture; do not rescale, which would corrupt recognition.")
        return 2

    IMAGES.mkdir(parents=True, exist_ok=True)
    destination = image_path(args.fixture_id)
    temporary = destination.with_suffix(".png.tmp")
    shutil.copyfile(redacted_source, temporary)
    temporary.replace(destination)
    digest = sha256(destination)

    raw_digest = sha256(raw_source)
    write_metadata(args.fixture_id, {
        "schema_version": 2,
        "fixture_id": args.fixture_id,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "game_version": args.game_version,
        "source_type": args.source_type,
        "width": width,
        "height": height,
        "sha256": digest,
        "raw_sha256": raw_digest,
        "redacted_sha256": digest,
        "redacted": True,
        "redaction_masks": redaction["masks"],
        "redaction_pixel_changes": redaction["changed_pixels"],
        "privacy_review_method": "decoded-pixel-diff-v1",
        "redaction_notes": args.privacy_notes,
        "assertions": [
            f"TODO: state what {args.fixture_id} must show for recognition to trust it."
        ],
        "reviewed_by": "",
        "reviewed_at": "",
        "notes": args.notes or "",
    })
    entry["status"] = "redacted"
    save_manifest(manifest)

    print(f"imported redacted fixture {args.fixture_id}")
    print(f"  image     {destination.relative_to(ROOT)}")
    print(f"  metadata  {metadata_path(args.fixture_id).relative_to(ROOT)}")
    print(f"  sha256    {digest}")
    print(f"  masks     {len(redaction['masks'])}")
    print(f"  changes   {redaction['changed_pixels']} pixels")
    print("\nNext:")
    print(f"  1. Edit the metadata: replace the TODO assertion(s) with what the image must show.")
    print(f"  2. Review/verify: python tools/capture_fixture.py verify {args.fixture_id} --reviewer \"<name>\"")
    return 0


def cmd_verify(args) -> int:
    manifest = load_manifest()
    entry = find_entry(manifest, args.fixture_id)
    if entry is None or entry.get("status") not in ("redacted", "verified"):
        print(f"'{args.fixture_id}' must be redacted before it can be verified.")
        return 2

    data = read_metadata(args.fixture_id)
    todo = [a for a in data.get("assertions", []) if a.strip().lower().startswith("todo")]
    if todo:
        print(f"the assertions still contain a TODO; fill them in before verifying:")
        for item in todo:
            print(f"  - {item}")
        return 2

    if not args.yes:
        print("Assertions to confirm the image actually demonstrates:")
        for item in data.get("assertions", []):
            print(f"  - {item}")
        reply = input("Do all of these hold in the image? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("left unchanged.")
            return 1

    data["reviewed_by"] = args.reviewer
    data["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_metadata(args.fixture_id, data)
    entry["status"] = "verified"
    save_manifest(manifest)
    print(f"{args.fixture_id} -> verified (reviewer: {args.reviewer})")
    return 0


def cmd_selftest(args) -> int:
    """Exercise the ladder on a throwaway fixture id, in a scratch tree, touching nothing tracked."""
    import tempfile
    import zlib

    failures = []

    def check(condition, message):
        print(f"  {'ok  ' if condition else 'FAIL'}  {message}")
        if not condition:
            failures.append(message)

    # Real PNGs, built by hand so the test needs no image library.
    def make_png(path: Path, w: int, h: int, changed=False):
        rows = []
        for y in range(h):
            row = bytearray(b"\x20\x30\x40" * w)
            if changed and y == 1:
                row[3:6] = b"\x00\x00\x00"
            rows.append(b"\x00" + bytes(row))
        raw = b"".join(rows)
        def chunk(tag, data):
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        path.write_bytes(PNG_SIGNATURE + chunk(b"IHDR", ihdr)
                         + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.png"; make_png(good, 860, 732)
        redacted = Path(tmp) / "redacted.png"; make_png(redacted, 860, 732, changed=True)
        wrong = Path(tmp) / "wrong.png"; make_png(wrong, 800, 600)
        w, h = png_dimensions(good)
        check((w, h) == (860, 732), "reads PNG dimensions from the header")
        check(png_dimensions(wrong) == (800, 600), "reads a non-contract size too")
        digest = sha256(good)
        check(len(digest) == 64 and digest == sha256(good), "sha256 is stable")
        result = verify_redaction(decode_png(good), decode_png(redacted), [{"x": 1, "y": 1, "width": 1, "height": 1}])
        check(result["changed_pixels"] == 1, "proves a solid masked pixel replacement")
        try:
            png_dimensions(Path(tmp) / "nope.png") if (Path(tmp) / "nope.png").exists() else make_png(Path(tmp)/"txt.png",1,1)
            (Path(tmp) / "bad.bin").write_bytes(b"not a png at all")
            png_dimensions(Path(tmp) / "bad.bin")
            check(False, "rejects a non-PNG")
        except (ValueError, FileNotFoundError):
            check(True, "rejects a non-PNG")

    manifest = load_manifest()
    ids = [e["id"] for e in manifest.get("required_fixtures", [])]
    check(len(ids) == len(set(ids)), "manifest fixture ids are unique")
    check(all(image_path(i) == IMAGES / f"{i}.png" for i in ids), "image paths derive from the id")

    print(f"\n{'selftest passed' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show every fixture and its status").set_defaults(func=cmd_list)

    add = sub.add_parser("add", help="verify and import a redacted screenshot (missing -> redacted)")
    add.add_argument("fixture_id")
    add.add_argument("raw_png", help="private raw 860x732 PNG outside the repository")
    add.add_argument("redacted_png", help="solid-mask derivative outside the repository")
    add.add_argument("--mask", action="append", default=[], metavar="X,Y,W,H", help="solid redaction rectangle; repeat as needed")
    add.add_argument("--no-redaction-needed", action="store_true", help="attest that decoded pixels are identical and contain no private data")
    add.add_argument("--game-version", default="unknown", help="e.g. 18.x.y")
    add.add_argument("--source-type", default="authorized-test-account", help="authorized-test-account, emulator, or device")
    add.add_argument("--privacy-notes", required=True, help="what was masked or why no redaction was needed")
    add.add_argument("--notes", default="")
    add.set_defaults(func=cmd_add)

    verify = sub.add_parser("verify", help="confirm the recognition assertions (redacted -> verified)")
    verify.add_argument("fixture_id")
    verify.add_argument("--reviewer", required=True, help="who is signing off")
    verify.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    verify.set_defaults(func=cmd_verify)

    sub.add_parser("selftest", help="verify the harness offline").set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
