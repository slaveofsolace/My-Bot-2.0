# Current-client compatibility: implementation slice 1

**Branch:** `integration/current-client-compat-1`  
**Audit date:** August 6, 2026  
**Base:** MyBot v8.2.0 source

## Included

### Emulator adapters

The first port adds native adapter modules for LDPlayer 9 and MuMu Player 12. Both modules use the existing v8.2.0 Android dispatch surface rather than replacing the Android core.

The LDPlayer adapter includes the corrected multi-instance endpoint formula:

```text
emulator-(5554 + 2 × instance index)
```

Both adapters implement installation discovery, instance addressing, launch, shutdown, ADB selection, shared-folder discovery, required resolution/DPI configuration, background mode selection, window lookup, reboot configuration, and zoom-out hooks.

Static integration is not a runtime support claim. Each advertised emulator still requires a clean Windows test matrix covering installation discovery, instance 0 and non-zero instances, ADB reconnect, window recreation, background screenshots, clicks, zoom, restart, and shutdown.

### Run orchestration

`RunPlan.au3` establishes a stable engine contract for:

- Home Village, Builder Base, regular, Ranked, and Legend routes
- strategy selection
- duration and battle limits
- Star Bonus completion
- failure limits
- resource targets
- upgrade policies
- account-queue selection

`AccountQueue.au3` provides ordered, optional cycling through local profile references. It intentionally contains no credential, token, session-cookie, or account-password fields.

### Capability and fixture catalogs

The capability catalog separates four states: catalogued, adapter added, engine added, and supported. Current game features remain catalogued until both screenshot fixtures and controlled runtime evidence pass.

The fixture manifest defines the required 860×732 redacted captures for Town Hall 18, Guardians, separate regular/Ranked/Legend routes, six-Hero layouts, Dragon Duke, Hero Journey, Global Chat, fast-forward, current Builder Base states, and the new emulator windows.

## Reviewed upstream changes not copied

Two July 2026 xbebenk changes were reviewed and intentionally not transplanted:

- `a477cbaf50ac8247da935a921f6de0dd5ca9a5e7`: its chest handling modifies an older `PlacedOnLeague` path. v8.2.0 already uses a newer Treasure Hunt interruption path and does not contain that control flow.
- `84c9115021f0b2c55d38a351086466ec61afa3dd`: its resource-icon guard modifies `FindUpgradeBB`. v8.2.0 uses the reorganized `GetIconPosition` pipeline instead.

Copying either patch literally would replace newer logic with older structure. Equivalent defects will be addressed only if current-client fixtures reproduce them.

## Automated integration

`tools/apply_current_client_compat.py` performs exact, idempotent edits to:

- include the compatibility entry point
- expose LDPlayer 9 and MuMu in emulator discovery and instance selection
- add both adapters to generic ADB resolution
- correct the run-plan validation signature

The write-enabled workflow runs only on the named compatibility branch and refuses to run for bot-authored commits. The read-only verification workflow applies the same patch in its temporary checkout, validates the result, and then runs the repository audit.

## Remaining acceptance gates

This slice is not release-ready until all of the following pass:

1. AutoIt syntax and compile validation on Windows.
2. Clean-profile startup with no inherited configuration.
3. LDPlayer 9 instance 0 and instance 1+ tests.
4. MuMu instance 0 and instance 1+ tests.
5. Current-client fixture capture and redaction.
6. Recognition tests for each catalogued game surface.
7. Route separation tests for regular, Ranked, Legend, and Builder Base battles.
8. Controlled end-to-end sessions with deterministic stop-condition evidence.
