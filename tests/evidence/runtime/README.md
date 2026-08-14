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

No capability is promoted automatically. `tools/evaluate_support_readiness.py` reports two distinct
views: `ready` / `ready_for_support_review` accepts trusted ancestor-binary records as historical
lineage, while `exact_current_binary_records` / `current_binary_ready` additionally require each
trusted record's binary hash and byte size to match the binary and provenance committed at `HEAD`.
Exact-current reporting rejects the match if either worktree path differs from `HEAD`.
A reviewed source change is still required to change a capability status to `supported`.

The 2026-08-14 bea12973 LocalRuntime checkpoint is the current reviewed binary ancestor. Its ZIP is
32,207,931 bytes with SHA-256
`86163ae69b008216398980d7fe215af426f660a7b52538af762851309c4fd330`; six reviewed x86 targets and
the 2,578-file manifest validated, the installed chain launched through its Windows shortcut, and a
fresh-boot no-input check initialized the managed engine in the exact backend before returning idle.
That run is tracked as `orchestration.engine-initialization.pie64.20260814` and is exact-current for
the committed `MyBot.run.exe`. It does not promote an emulator, fixture, or gameplay capability.

Current HEAD is post-checkpoint and unbuilt because it adds evidence-validation and documentation
changes after bea12973. The evidence remains exact-current for the unchanged committed backend bytes,
but the ZIP does not contain the later repository-only changes; a final reviewed package is still
required before shipping HEAD.

Every capability that declares `fixture_status: required` must map to an explicit capture target in `tests/fixtures/current-client/manifest.json`. Defining a target improves traceability only: a missing image remains `missing` and cannot promote readiness.

Run the deterministic trust-contract regression suite:

```powershell
python -m unittest discover -s tests/python -p "test_*.py" -v
```
