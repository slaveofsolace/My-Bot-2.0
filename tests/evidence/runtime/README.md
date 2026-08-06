# Runtime evidence

This directory stores reviewed JSON evidence for emulator, recognition, route, and end-to-end tests. It must not contain screenshots, logs, or identifiers that expose player, account, chat, payment, machine, or operator information.

Each file name must match its `evidence_id`:

```text
ldplayer9.instance-1.smoke.json
```

Use `config/runtime-evidence.schema.json` as the contract. A `passed` record requires all checks to pass, `redacted: true`, at least one artifact reference, and reviewer information. Artifact references may point to a retained GitHub Actions artifact, a redacted fixture ID, or a repository-relative report.

Validate all records:

```powershell
python tools/validate_runtime_evidence.py --json runtime-evidence-validation.json
```

Require evidence for one capability:

```powershell
python tools/validate_runtime_evidence.py --require-capability emulator.ldplayer9
```

No capability is promoted automatically. `tools/evaluate_support_readiness.py` reports whether the documented fixture and evidence gates are complete; a reviewed source change is still required to change a capability status to `supported`.
