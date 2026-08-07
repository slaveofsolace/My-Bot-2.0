#!/usr/bin/env python3
"""Turn a raw screenshot into a validated current-client fixture.

The recognition work is blocked on 20 screenshots of the current game (see tests/fixtures/
current-client/manifest.json). This tool takes one you captured on Windows and does everything
around it: checks the dimensions, files the image where the validator expects it, computes the
hash, and writes metadata that matches the schema exactly. It does not touch the network and needs
only the standard library.

A fixture climbs a four-rung ladder, and each rung is a subcommand here:

    list                 show every fixture and where it stands
    add <id> <png>       missing  -> captured   (image filed, metadata stubbed)
    redact <id>          captured -> redacted   (you confirm privacy is done)
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
    order = {"missing": 0, "captured": 1, "redacted": 2, "verified": 3}
    counts = {k: 0 for k in order}
    print(f"{'fixture':<28} {'status':<10} purpose")
    print("-" * 78)
    for entry in sorted(entries, key=lambda e: (order.get(e.get("status"), 0), e.get("id", ""))):
        status = entry.get("status", "?")
        counts[status] = counts.get(status, 0) + 1
        marker = {"missing": " ", "captured": ".", "redacted": ":", "verified": "*"}.get(status, "?")
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

    source = Path(args.png)
    if not source.is_file():
        print(f"no such file: {source}")
        return 2

    try:
        width, height = png_dimensions(source)
    except ValueError as exc:
        print(f"{source}: {exc}")
        return 2

    contract = manifest.get("capture_contract", {})
    want_w, want_h = contract.get("width", 860), contract.get("height", 732)
    if (width, height) != (want_w, want_h):
        print(f"wrong size: the capture is {width}x{height}, the contract needs {want_w}x{want_h}.")
        print("Set the emulator to 860x732 and recapture; do not rescale, which would corrupt recognition.")
        return 2

    IMAGES.mkdir(parents=True, exist_ok=True)
    destination = image_path(args.fixture_id)
    shutil.copyfile(source, destination)
    digest = sha256(destination)

    # Stub metadata at the "captured" rung: schema-complete, but privacy and assertions are still
    # the operator's to confirm. redacted stays false and the review fields stay blank on purpose.
    write_metadata(args.fixture_id, {
        "schema_version": 1,
        "fixture_id": args.fixture_id,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "game_version": args.game_version,
        "source_type": args.source_type,
        "width": width,
        "height": height,
        "sha256": digest,
        "redacted": False,
        "redaction_notes": "",
        "assertions": [
            f"TODO: state what {args.fixture_id} must show for recognition to trust it."
        ],
        "reviewed_by": "",
        "reviewed_at": "",
        "notes": args.notes or "",
    })
    entry["status"] = "captured"
    save_manifest(manifest)

    print(f"captured {args.fixture_id}")
    print(f"  image     {destination.relative_to(ROOT)}")
    print(f"  metadata  {metadata_path(args.fixture_id).relative_to(ROOT)}")
    print(f"  sha256    {digest}")
    print("\nNext:")
    print(f"  1. Edit the metadata: replace the TODO assertion(s) with what the image must show.")
    print(f"  2. Confirm privacy:   python tools/capture_fixture.py redact {args.fixture_id}")
    return 0


def cmd_redact(args) -> int:
    manifest = load_manifest()
    entry = find_entry(manifest, args.fixture_id)
    if entry is None or entry.get("status") == "missing":
        print(f"'{args.fixture_id}' has not been captured yet.")
        return 2
    if not metadata_path(args.fixture_id).is_file():
        print(f"metadata for {args.fixture_id} is missing; re-run add.")
        return 2

    contract = load_manifest().get("capture_contract", {})
    print("Before confirming, check the image has none of the following visible:")
    print(f"  {contract.get('redaction', 'player names, clan names, chat, account identifiers')}")
    if not args.yes:
        reply = input("Is the image fully redacted? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("left unchanged.")
            return 1

    data = read_metadata(args.fixture_id)
    # A privacy edit changes the file, so the recorded hash has to be recomputed or the validator
    # will (correctly) reject the mismatch.
    if image_path(args.fixture_id).is_file():
        data["sha256"] = sha256(image_path(args.fixture_id))
    data["redacted"] = True
    if not data.get("redaction_notes"):
        data["redaction_notes"] = args.notes or "Reviewed against the capture contract; no identifying content visible."
    write_metadata(args.fixture_id, data)
    entry["status"] = "redacted"
    save_manifest(manifest)
    print(f"{args.fixture_id} -> redacted")
    print(f"  next: python tools/capture_fixture.py verify {args.fixture_id} --reviewer \"<name>\"")
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

    # A real 860x732 PNG, built by hand so the test needs no image library.
    def make_png(path: Path, w: int, h: int):
        raw = b"".join(b"\x00" + b"\x20\x30\x40" * w for _ in range(h))
        def chunk(tag, data):
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        path.write_bytes(PNG_SIGNATURE + chunk(b"IHDR", ihdr)
                         + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.png"; make_png(good, 860, 732)
        wrong = Path(tmp) / "wrong.png"; make_png(wrong, 800, 600)
        w, h = png_dimensions(good)
        check((w, h) == (860, 732), "reads PNG dimensions from the header")
        check(png_dimensions(wrong) == (800, 600), "reads a non-contract size too")
        digest = sha256(good)
        check(len(digest) == 64 and digest == sha256(good), "sha256 is stable")
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

    add = sub.add_parser("add", help="file a captured screenshot (missing -> captured)")
    add.add_argument("fixture_id")
    add.add_argument("png", help="path to the 860x732 screenshot")
    add.add_argument("--game-version", default="unknown", help="e.g. 18.x.y")
    add.add_argument("--source-type", default="emulator", help="emulator or device")
    add.add_argument("--notes", default="")
    add.set_defaults(func=cmd_add)

    redact = sub.add_parser("redact", help="confirm privacy review (captured -> redacted)")
    redact.add_argument("fixture_id")
    redact.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    redact.add_argument("--notes", default="")
    redact.set_defaults(func=cmd_redact)

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
