# Project documentation

Working notes for the My Bot 2.0 rebuild. The README covers installing and using the bot; this
folder covers why things are built the way they are.

The inherited AutoIt application stays in its original layout. Roughly 400 include paths and a
large number of OCR, template, and language assets resolve by relative path, so moving files
before those relationships are covered by automated checks would be a large, unreviewable change
with nothing to catch a mistake. New code is organised properly from the start; the legacy tree
gets moved once there is enough test coverage to prove a move was behaviour-neutral.

## Start here

- [Baseline audit](audit/BASELINE_AUDIT_2026-08-06.md) — repository state, source evaluation, risks, and the implementation order that followed from them.
- [Game compatibility matrix](compatibility/GAME_UPDATE_MATRIX.md) — the Clash of Clans changes that affect navigation, OCR, templates, data tables, and state handling.
- [Repository plan](architecture/REPOSITORY_PLAN.md) — target structure and the phased sequence for getting there.
- [Merge playbook](development/MERGE_PLAYBOOK.md) — how upstream fixes and clean-room features enter this repository.
- [UI handoff](ui/UI_HANDOFF.md) — requirements for the separate design-system work.
- [Install guide](INSTALL.md) — setup detail beyond the README's quick path.

## Implementation notes

- [Emulator adapters and orchestration](implementation/current-client-compat-1.md)
- [Sourced game catalogs and the generated registry](implementation/current-game-model-1.md)

## Branches

Development happens on `claude/coc-bot-merge-ui-kobgds` and lands on `master`. The four
`integration/*` branches and the `foundation/v8.2.0-source` pin were stacked review branches; they
have been merged and removed. `master` now carries the complete runnable source.

## Checks

Everything under `tools/` is standard-library Python and runs on any platform. `.github/workflows/ci.yml`
runs the whole set on every push and pull request; `.github/workflows/windows-autoit.yml` runs
`Au3Check` and the AutoIt contract tests against AutoIt 3.3.16.1 and 3.3.18.0.

The AutoIt linter (`tools/lint_autoit.py`) exists because `Au3Check` is Windows-only. It catches
unbalanced blocks, `ByRef` parameters with defaults, required parameters following optional ones,
duplicate function definitions, and includes or project calls that do not resolve — the class of
mistake that would otherwise sit undetected until a Windows job ran.

## Working rules

1. Keep commits reviewable. Do not mix compatibility changes, UI work, and file moves in one commit.
2. Pin every external source in `upstreams.lock.json` before using it.
3. Preserve GPL notices and record the origin of every ported change.
4. Treat repositories without source or a usable licence as behaviour references only.
5. Never mark something verified that has not been demonstrated. Diagnostic runs are for finding
   out how something behaves; they do not become evidence that it works.
6. Do not add stealth, detection evasion, or account-protection bypasses, and do not claim that
   usage is undetectable.
7. Run automation only where that testing is authorised.
