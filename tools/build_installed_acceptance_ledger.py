#!/usr/bin/env python3
"""Build a conservative installed-product acceptance ledger.

The ledger joins support-readiness output with exact installed-runtime proof
files.  It deliberately separates installed mechanism evidence from live
account-mutating proof: a capability can be runtime-recognized or covered by
deterministic tests without being claimed as live accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATUSES = {
    "LIVE_PASS",
    "RUNTIME_PASS",
    "DETERMINISTIC_PASS",
    "STATE_BLOCKED",
    "RIGHTS_BLOCKED",
    "UNSAFE_BLOCKED",
}

RUNTIME_PROVEN_IDS = {
    "emulator.bluestacks5",
    "events.daily-reward",
    "model.current-game",
    "model.screen-state-registry",
    "orchestration.engine-initialization",
}

DETERMINISTIC_PROVEN_IDS = {
    "orchestration.run-event",
    "orchestration.run-plan",
    "orchestration.run-session",
    "safety.no-gem-guard",
    "village.clan-request",
    "village.collectors",
    "village.loot-cart",
}

UNSAFE_KEYWORDS = (
    "account",
    "battle",
    "boost",
    "builder-base.battle",
    "builder-base.hero",
    "clan-capital",
    "donation",
    "hero-upgrade",
    "shop",
    "training",
    "upgrade",
)

RIGHTS_BLOCKED_IDS = {
    "battle.fast-forward",
    "battle.regular-ranked-split",
    "battle.revenge",
    "battle.smart-zap",
    "battle.trophy-drop",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _proof_document(proof: dict[str, Any]) -> dict[str, Any]:
    final = proof.get("final_status")
    if isinstance(final, dict):
        document = final.get("document")
        if isinstance(document, dict):
            return document
    return {}


def installed_launch_proved(ui_proof: dict[str, Any] | None) -> bool:
    if not isinstance(ui_proof, dict):
        return False
    document = _proof_document(ui_proof)
    return (
        document.get("last_command") == "launch-game"
        and document.get("last_outcome") == "passed"
        and "Daily Reward" in str(document.get("last_command_message", ""))
    )


def classify_capability(
    row: dict[str, Any],
    *,
    installed_runtime_proved: bool,
) -> tuple[str, str]:
    capability_id = str(row.get("id", ""))
    blockers = row.get("blockers") if isinstance(row.get("blockers"), list) else []
    current_blockers = (
        row.get("current_binary_blockers")
        if isinstance(row.get("current_binary_blockers"), list)
        else []
    )
    passing = row.get("passing_evidence") if isinstance(row.get("passing_evidence"), list) else []
    fixtures = row.get("verified_fixtures") if isinstance(row.get("verified_fixtures"), list) else []
    declared_status = row.get("declared_status")

    if installed_runtime_proved and capability_id in RUNTIME_PROVEN_IDS:
        if capability_id == "events.daily-reward":
            return (
                "RUNTIME_PASS",
                "Exact installed UI launch proof passively recognized the Daily Reward overlay and one Claim candidate; the claim click remains live-action gated.",
            )
        return (
            "RUNTIME_PASS",
            "Exact installed UI launch proof covered the mechanism/recognition path; no live account mutation is claimed.",
        )

    if capability_id in RIGHTS_BLOCKED_IDS:
        return (
            "RIGHTS_BLOCKED",
            "The inherited route remains blocked by current-client recognition/provenance rights and lacks exact-current safe replacement proof.",
        )

    if capability_id in DETERMINISTIC_PROVEN_IDS:
        return (
            "DETERMINISTIC_PASS",
            "Source contracts, fixtures, tests, or historical trusted runtime evidence exist; exact-current live acceptance is not claimed.",
        )

    if any(keyword in capability_id for keyword in UNSAFE_KEYWORDS):
        return (
            "UNSAFE_BLOCKED",
            "This route can mutate the live account or social/game state and needs fresh action-specific confirmation with exact pre/post no-premium proof.",
        )

    if blockers:
        return (
            "STATE_BLOCKED",
            "Required fixtures, trusted runtime evidence, emulator/account state, or current-client proof are missing.",
        )

    if current_blockers:
        return (
            "DETERMINISTIC_PASS",
            "Historical or deterministic evidence exists, but exact-current installed-binary evidence is missing.",
        )

    if passing or fixtures or declared_status in {"adapter-added", "engine-added", "legacy-implemented"}:
        return (
            "DETERMINISTIC_PASS",
            "Inventoried source/mechanism evidence exists; live acceptance is not claimed.",
        )

    return (
        "STATE_BLOCKED",
        "No exact-current installed evidence is available for this capability.",
    )


def build_ledger(
    *,
    readiness: dict[str, Any],
    ui_proof: dict[str, Any] | None,
    passive_proof: dict[str, Any] | None,
    source_master: str,
    local_binary_commit: str,
    package_sha256: str,
    installed_manifest_sha256: str,
    installed_entrypoint_sha256: str,
    proof_paths: dict[str, Path],
    now: datetime | None = None,
) -> dict[str, Any]:
    installed_runtime_proved = installed_launch_proved(ui_proof)
    capabilities: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in readiness.get("results", []):
        status, note = classify_capability(row, installed_runtime_proved=installed_runtime_proved)
        counts[status] = counts.get(status, 0) + 1
        capabilities.append(
            {
                "capability_id": row.get("id"),
                "status": status,
                "declared_status": row.get("declared_status"),
                "ready_for_support_review": bool(row.get("ready_for_support_review")),
                "strict_exact_current_binary_ready": bool(row.get("current_binary_ready")),
                "verified_fixtures": row.get("verified_fixtures", []),
                "passing_historical_evidence": row.get("passing_evidence", []),
                "blockers": row.get("blockers", []),
                "current_binary_blockers": row.get("current_binary_blockers", []),
                "note": note,
            }
        )

    proof_records: dict[str, dict[str, Any]] = {}
    for key, path in proof_paths.items():
        proof_records[key] = {"path": str(path), "sha256": sha256_file(path)}

    ui_doc = _proof_document(ui_proof or {})
    passive_doc = _proof_document(passive_proof or {})
    proof_records["actual_web_ui_launch_game"].update(
        {
            "last_command": ui_doc.get("last_command"),
            "last_outcome": ui_doc.get("last_outcome"),
            "message": ui_doc.get("last_command_message"),
        }
    )
    proof_records["passive_installed_launch_game"].update(
        {
            "last_command": passive_doc.get("last_command"),
            "last_outcome": passive_doc.get("last_outcome"),
            "game_version": (passive_proof or {}).get("adb_package", {}).get("version_name"),
        }
    )

    return {
        "schema": "mybot-installed-acceptance-ledger-v1",
        "created_at": (now or datetime.now(timezone.utc)).isoformat(),
        "source_master": source_master,
        "local_binary_commit": local_binary_commit,
        "package_sha256": package_sha256,
        "installed_manifest_sha256": installed_manifest_sha256,
        "installed_entrypoint_sha256": installed_entrypoint_sha256,
        "proofs": proof_records,
        "counts": counts,
        "strict_support_readiness": {
            "capabilities": readiness.get("capabilities"),
            "historical_ready": readiness.get("ready"),
            "historical_not_ready": readiness.get("not_ready"),
            "exact_current_binary_ready": readiness.get("current_binary_ready"),
            "exact_current_binary_not_ready": readiness.get("current_binary_not_ready"),
        },
        "binding_nonclaims": [
            "No live gameplay or account mutation is claimed by this ledger.",
            "RUNTIME_PASS means installed mechanism/recognition proof, not account-mutating live completion.",
            "DETERMINISTIC_PASS means source/fixture/test/historical mechanism proof, not exact-current live completion.",
            "Public binary release remains blocked until inherited recognition/component rights are resolved.",
        ],
        "capabilities": capabilities,
    }


def validate_ledger(ledger: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    capabilities = ledger.get("capabilities", [])
    if not isinstance(capabilities, list):
        return ["ledger capabilities must be a list"]
    ids = [entry.get("capability_id") for entry in capabilities if isinstance(entry, dict)]
    readiness_ids = [
        entry.get("id")
        for entry in readiness.get("results", [])
        if isinstance(entry, dict)
    ]
    if len(ids) != len(set(ids)):
        errors.append("ledger contains duplicate capability IDs")
    if set(ids) != set(readiness_ids):
        errors.append("ledger capability IDs do not exactly match readiness results")
    if len(ids) != readiness.get("capabilities"):
        errors.append("ledger capability count does not match readiness capability count")
    invalid_statuses = sorted(
        {
            entry.get("status")
            for entry in capabilities
            if isinstance(entry, dict) and entry.get("status") not in VALID_STATUSES
        }
    )
    if invalid_statuses:
        errors.append("invalid status values: " + ", ".join(str(value) for value in invalid_statuses))
    live_claims = [
        str(entry.get("capability_id"))
        for entry in capabilities
        if isinstance(entry, dict) and entry.get("status") == "LIVE_PASS"
    ]
    if live_claims:
        errors.append("unexpected LIVE_PASS claims: " + ", ".join(live_claims))
    if sum(ledger.get("counts", {}).values()) != len(ids):
        errors.append("ledger status counts do not sum to capability count")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--actual-web-ui-proof", type=Path, required=True)
    parser.add_argument("--passive-launch-proof", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-master", required=True)
    parser.add_argument("--local-binary-commit", required=True)
    parser.add_argument("--package-sha256", required=True)
    parser.add_argument("--installed-manifest-sha256", required=True)
    parser.add_argument("--installed-entrypoint-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readiness = load_json(args.readiness)
    ui_proof = load_json(args.actual_web_ui_proof)
    passive_proof = load_json(args.passive_launch_proof)
    ledger = build_ledger(
        readiness=readiness,
        ui_proof=ui_proof,
        passive_proof=passive_proof,
        source_master=args.source_master,
        local_binary_commit=args.local_binary_commit,
        package_sha256=args.package_sha256,
        installed_manifest_sha256=args.installed_manifest_sha256,
        installed_entrypoint_sha256=args.installed_entrypoint_sha256,
        proof_paths={
            "actual_web_ui_launch_game": args.actual_web_ui_proof,
            "passive_installed_launch_game": args.passive_launch_proof,
            "support_readiness": args.readiness,
            "receipt": args.receipt,
        },
    )
    errors = validate_ledger(ledger, readiness)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "counts": ledger["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
