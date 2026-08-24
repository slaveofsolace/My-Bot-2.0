# Local inherited runtime boundary

The current product backend remains the only backend reachable from Start Run. Inherited full-profile execution stays fail-closed because the reviewed runtime does not yet provide a contained, authenticated command boundary with complete no-premium enforcement. That execution-safety decision is independent of redistribution permission.

For local static investigation, the source repository contains developer-only utilities for one exact upstream Git object. They are intentionally excluded from LocalRuntime packages and installed products. The provisioner:

- reads commit `8ad6e5a552347acc2fcb8048d30262e2735a0c33` from an already-present owner-local repository;
- exports to the fixed `%LOCALAPPDATA%\My Bot 2.0\LocalInheritedRuntime\pinned-...` island;
- validates all 2,506 exported files and the complete manifest digest;
- separately validates the executable tuple, zero-byte upstream marker, and local attestation; and
- never downloads, builds, patches, signs, packages, publishes, or executes inherited binaries.

Run the utilities only from a reviewed source checkout. `tools\provision_local_inherited_runtime.py check-source` is read-only. `provision` writes only the fixed local island. `tools\prepare_local_inherited_proof_profile.py` and `config\local-inherited-runtime-safety.json` are likewise developer-only source assets, not product controls.

## Public distribution rights

Public distribution is a separate gate. `config\redistribution-rights.json` remains authoritative and blocks public redistribution of the inherited recognition binary. Resolving that rights record would not make inherited execution safe or reachable. Conversely, a future safe execution design would not authorize public binary distribution without independently accepted rights evidence.

## Why even a passive GUI launch is blocked

The pinned full GUI is not passive before the user presses Start. Its exact startup sequence:

- calls `getAllEmulators()` and `InitializeAndroid()`, which detect running/installed emulators and load distributor state;
- calls `CleanSecureFiles()` and creates or migrates profile, private-profile, log, loot, temporary, and donation-capture paths;
- calls `CheckPrerequisites()`, initializes the inherited DLL, and sets Android and GUI process identities;
- starts TCP support and can perform forum authentication, version, emulator-version, and notification checks; and
- contains internal restart paths that can start a watchdog despite a top-level `/nwd` launch.

These behaviors can inspect or mutate host/emulator/account-related state and can use the network before any Debug Run Function is selected. Configuration cannot suppress the complete sequence. Therefore `LocalInheritedRuntimeExecutableLaunchAvailable()` is always false. The adapter contains no `Run`, process termination, window message, web command, or inherited API path. BotStart, RunControl, and the loopback web service cannot launch or signal the pinned executable.

The inherited automation API is separately blocked because API 1.1 is unauthenticated and reviewed boost paths contain premium-currency confirmation clicks without a complete hard runtime interlock.

## Zero-copy static profile proof

`tools\prepare_local_inherited_proof_profile.py` hashes one owner source profile before and after preparation but copies none of its files or values. It creates only:

- `Profiles\profile.ini`; and
- `Profiles\Proof\config.ini`.

The generated config contains only reviewed inert values. It explicitly disables autostart/restart, version checks, auto-resume, window arrangement, notifications and remote control; blanks notification tokens/origin and emulator/instance identity; disables shared-prefs updates and SCID account selection; and retains the no-reward/no-super-troop boundaries. The proof receipt records `source_files_copied=0`, `source_data_policy=hash-source-copy-zero-files`, and `proof_mode=unlaunched-static-only`. Its destination name binds the canonical source root and profile name as well as the source-content and safety-contract digests. Reuse verifies the canonical root, profile name, exact file count, and complete source digest before accepting an existing proof directory.

All source files—including credentials, notification tokens, shared preferences, donation captures, logs, caches, account-switch files, and unknown content—remain outside the proof. Redirected source or proof content fails closed. Validation requires exactly the two generated files, the complete source no-drift hash, the tracked safety-contract hash, and the fixed owner-local proof path.

`LocalInheritedRuntimeValidateUnlaunchedReference()` may validate the island and zero-copy proof and write a truthful local receipt. Receipt persistence is part of success: an open, write, flush, or temporary-file replacement failure makes validation fail closed. It never executes inherited code. This proves only local source identity and boundary enforcement; it does not prove recognition, GUI startup, gameplay automation, account safety, current-client compatibility, or redistribution rights.

## Future recognition work

A fixture-only recognition receipt requires a new reference host that can load the approved recognition component without running OG application initialization. That host must have a bounded, authenticated fixed-function protocol and no emulator, ADB, network, account, process-restart, arbitrary `Execute`, or game-input capability. The full OG Debug Run Function surface is not an acceptable substitute because reaching it already crosses the startup boundary above.

Any unexpected HTML file in the island is treated as an unauthorized-use incident signal. Validation stops and records the path. The software never bypasses or modifies inherited anti-copycat or authentication behavior.
