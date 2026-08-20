# Runtime evidence

This directory stores reviewed JSON evidence for emulator, recognition, route, and end-to-end tests. It must not contain screenshots, logs, or identifiers that expose player, account, chat, payment, machine, or operator information.

Each file name must match its `evidence_id`:

```text
ldplayer9.instance-1.smoke.json
```

Use `config/runtime-evidence.schema.json` as the record contract and
`runtime_evidence_policy` in `config/current-client-capabilities.json` as the
capability-specific acceptance contract. A `passed` record is trusted only when:

- its test type and passed check IDs satisfy that capability's policy;
- it is fresh, redacted, reviewed, and captured on Windows;
- `commit_sha` exists locally and is an ancestor of the revision being tested;
- `binary` matches both the Git blob and binary-provenance entry at that commit;
- the evidence record is committed and unchanged at `HEAD`;
- every artifact is committed and unchanged at `HEAD`, with matching SHA-256
  and byte size.

Free-form string artifact references remain readable for old failed or blocked
records, but cannot prove a pass. Use an integrity reference for new evidence:

```json
{
  "kind": "repository",
  "path": "tests/evidence/runtime/artifacts/run-plan-20260809.json",
  "sha256": "64-lowercase-hex-characters",
  "bytes": 1234
}
```

The required numeric `environment.instance_index` remains compatible with old
records. Add optional `environment.instance_name` (for example, `Pie64`) when a
named emulator instance is used.

Validate all records:

```powershell
python tools/validate_runtime_evidence.py --json runtime-evidence-validation.json
```

Require evidence for one capability:

```powershell
python tools/validate_runtime_evidence.py --require-capability emulator.ldplayer9
```

## Reproducible managed-engine capture

`tools/capture_check_engine_evidence.py` is dry-run-only unless `--execute` is
present. Its dry run validates the reviewed ZIP/installed manifest, exact
launcher/controller/backend/service ancestry, external Profiles root, fresh
idle/not-run state, and absence of BlueStacks and ADB. The live mode queues one
`check-engine` command, never retries it, retains the complete identity-bound
phase history, and emits a redacted schema-2 artifact plus evidence-record
draft outside the repository for human review:

```text
python tools/capture_check_engine_evidence.py ^
  --package-zip E:\MyBot2-Recovery\reviewed\MyBot-2.0.0-win-x86.zip ^
  --emulator-version 5.22.252.1008 ^
  --game-version 18.400.9

python tools/capture_check_engine_evidence.py ^
  --package-zip E:\MyBot2-Recovery\reviewed\MyBot-2.0.0-win-x86.zip ^
  --emulator-version 5.22.252.1008 ^
  --game-version 18.400.9 ^
  --output-directory E:\MyBot2-Recovery\evidence-candidate ^
  --execute
```

The output deliberately omits raw tokens, request/process identifiers, paths,
profile/account names, and player data. It also fails if warning HTML appears,
an owned browser child starts, the backend opens an observed outbound TCP
connection, immutable package bytes drift, or the saved plan/configuration or
emulator/ADB process sets change. Drafts do not earn readiness credit until
reviewed, committed, and accepted by the normal evidence validator.

## Closed no-gem proof

Any new passing `end-to-end` or `route-execution` record for a capability in the
catalog's `no_gem_contract` must reference exactly one committed semantic JSON
artifact containing a schema-2 `no_gem_proof`. The proof requires ordered
before/after gem observations and frame digests, a nondecreasing gem balance,
an armed gem-surface hard stop, zero gem-completion, purchase, and shop-offer
inputs, exact profile/emulator/account binding, separate issued-versus-confirmed
receipts, and a proved route return. Raw frames remain private: retain only
reviewed redacted derivatives or the hashes produced by a clean-room recognizer.

This artifact is an additional fail-closed gate. Capability-specific checks still
have to prove the exact route outcome, resource delta, and Home or Builder Home
state; a no-gem artifact alone cannot promote readiness.

No capability is promoted automatically. `tools/evaluate_support_readiness.py` reports two distinct
views: `ready` / `ready_for_support_review` accepts trusted ancestor-binary records as historical
lineage, while `exact_current_binary_records` / `current_binary_ready` additionally require each
trusted record's binary hash and byte size to match the binary and provenance committed at `HEAD`.
Exact-current reporting rejects the match if either worktree path differs from `HEAD`.
A reviewed source change is still required to change a capability status to `supported`.

The 2026-08-14 bea12973 LocalRuntime checkpoint is a reviewed historical binary ancestor. Its ZIP is
32,207,931 bytes with SHA-256
`86163ae69b008216398980d7fe215af426f660a7b52538af762851309c4fd330`; six reviewed x86 targets and
the 2,578-file manifest validated, the installed chain launched through its Windows shortcut, and a
fresh-boot no-input check initialized the managed engine in the exact backend before returning idle.
That run is tracked as `orchestration.engine-initialization.pie64.20260814`. It is historical evidence:
its backend hash and byte size do not match the `MyBot.run.exe` and provenance currently committed at
`HEAD`. It does not promote an emulator, fixture, or gameplay capability.

The local-only `aa8ee424` discriminator package is 32,288,698 bytes with SHA-256
`d5cc8d0557c8f39a81c120f4f878c52421c4fd1fd0aafbb24eb61229d824ec72`. It is source-matched to the
current committed revision but has not completed the post-repair install, managed-engine, warning-HTML,
BlueStacks, fixture, gameplay, or immutable-package proof. The evaluator therefore correctly reports
zero exact-current-binary records and zero of 61 exact-current-ready capabilities. The working tree also
contains later unbuilt evidence/fixture hardening, so this ZIP is not a final release candidate.

New engine-initialization captures use semantic artifact schema 2. Schema 2 never moves or deletes
an operator's saved plan for the check: it records whether the plan exists and requires unchanged
before/after plan digests when present. It also requires unchanged release-manifest, emulator-process,
and ADB-process identity receipts. Schema 1 remains accepted only for the committed historical
captures that proved an absent-plan baseline.

Every capability that declares `fixture_status: required` must map to an explicit capture target in `tests/fixtures/current-client/manifest.json`. Defining a target improves traceability only: a missing image remains `missing` and cannot promote readiness.

Run the deterministic trust-contract regression suite:

```powershell
python -m unittest discover -s tests/python -p "test_*.py" -v
```
