# Project documentation

This folder is the working map for the My Bot 2.0 rebuild. The current AutoIt application remains in its original layout while compatibility work is isolated, reviewed, and tested. Large file moves will happen only after the include graph and release process are protected by automated checks.

## Start here

- [Baseline audit](audit/BASELINE_AUDIT_2026-08-06.md) — current repository state, source evaluation, material risks, and the first implementation order.
- [Game compatibility matrix](compatibility/GAME_UPDATE_MATRIX.md) — Clash of Clans changes that affect navigation, OCR, templates, data tables, and state handling.
- [Repository plan](architecture/REPOSITORY_PLAN.md) — target boundaries and the phased reorganization sequence.
- [Merge playbook](development/MERGE_PLAYBOOK.md) — how upstream fixes and clean-room features enter this repository.
- [UI handoff](ui/UI_HANDOFF.md) — requirements for the separate design-system and shell work.
- [Development install guide](INSTALL.md) — a source-first setup for contributors and authorized test environments.

## Current branch roles

| Branch | Purpose |
| --- | --- |
| `master` | Existing v8.2.0 release metadata. It is not the runnable source baseline. |
| `integration/unified-foundation` | Full v8.2.0 source, audit material, repository tooling, and reviewed integration work. |

## Working rules

1. Keep `integration/unified-foundation` reviewable. Do not mix compatibility changes, UI replacement, and broad file moves in one commit.
2. Pin every external source in `upstreams.lock.json` before using it.
3. Preserve GPL notices and record the origin of every ported change.
4. Treat repositories without source or a stated license as behavior references only.
5. Do not add stealth, detection-evasion, account-protection bypasses, or claims that usage is undetectable.
6. Run automation only in an environment where that testing is explicitly authorized.
