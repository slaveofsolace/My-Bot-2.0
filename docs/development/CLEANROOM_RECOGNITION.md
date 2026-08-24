# Clean-room recognition tranche

`tools/cleanroom_recognition.py` is an unwired, fail-closed recognition adapter. It does not load
`MyBot.run.dll`, decrypt inherited assets, open an emulator, capture a window, or issue game input.

The repository-owned `config/cleanroom-recognition.json` inventories all 17 case-sensitive
`DllCallMyBot` recognition export families and records the argument and return shapes their current
AutoIt callers expect. The adapter accepts only those exact enum values. Its output is typed JSON;
legacy wire compatibility is deliberately false until an AutoIt serializer and runtime acceptance
are separately reviewed.

The first tranche implements:

- `FindTile` for one manifest-owned, verified current-client Daily Reward fixture asset. The source
  fixture and privacy metadata are SHA-256 pinned; only seven manifest-owned candidate rectangles
  are compared with Pillow, with a one-result cap. This is a fixed-coordinate fixture-replay
  primitive only: live capture tolerance, performance, and current-screen acceptance are unproven.
- `GetOffSetRedline` as a bounded pure coordinate transform over caller-supplied integer points.
- `GetDeployableNextTo` as a bounded pure nearest-redline coordinate transform.

The remaining 14 export families return `UNAVAILABLE` with a concrete reason. They are not silently
forwarded to the inherited DLL.

Every implemented operation requires a PNG inside a marked task-owned capture root and a matching
receipt. Runtime captures expire after 30 seconds; fixture replays must match a manifest-approved
verified fixture. Hash drift, repeated/stale hashes, black frames, traversal, unowned assets,
oversized images/results, malformed coordinates, and expired deadlines fail closed.

The Python adapter remains outside the LocalRuntime packaging allowlist. LocalRuntime therefore keeps
its standard-library-only Python contract and does not acquire Pillow, a helper process, or a new
loopback API.

The native backend includes `CleanRoomRecognitionBridge.au3`, generated from the manifest through
`CleanRoomRecognitionContract.generated.au3`. That bridge is inert and read-only:

- the two pure coordinate transforms are callable only through their new, typed
  `CleanRoomRecognition...` names;
- `FindTile` can only attest that an already-hashed receipt names the exact reviewed fixture bytes;
  it returns no match box or coordinate and is never advertised runtime-ready;
- the other 14 exports remain explicitly unavailable; and
- `DllCallMyBot`, Bot Start, capture, emulator/ADB, and every input path remain untouched.

This native bridge is a deterministic contract prerequisite, not live recognition evidence. A future
live-image adapter still requires separate review of capture ownership, dependency provenance,
transport, cancellation, current-client tolerance, package identity, and exact installed-runtime
behavior before any observation may authorize an input.
