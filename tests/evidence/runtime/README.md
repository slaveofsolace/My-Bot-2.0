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

No capability is promoted automatically. `tools/evaluate_support_readiness.py` reports whether the documented fixture and evidence gates are complete; a reviewed source change is still required to change a capability status to `supported`.

Run the deterministic trust-contract regression suite:

```powershell
python -m unittest discover -s tests/python -p "test_*.py" -v
```
