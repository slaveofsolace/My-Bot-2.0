# Project documentation

Working notes for the My Bot 2.0 rebuild. The README covers installing and using the bot; this
folder covers why things are built the way they are.

The inherited AutoIt application stays in its original layout. Roughly 400 include paths and a
large number of OCR, template, and language assets resolve by relative path, so moving files
before those relationships are covered by automated checks would be a large, unreviewable change
with nothing to catch a mistake. New code is organised properly from the start; the legacy tree
gets moved once there is enough test coverage to prove a move was behaviour-neutral.

## Start here

- [Continuation handoff — August 7, 2026](development/CONTINUATION_HANDOFF_2026-08-07.md) — current commit, completed merge work, architecture, validation evidence, known issues, and prioritized next steps for the next implementation session.
- [Baseline audit](audit/BASELINE_AUDIT_2026-08-06.md) — repository state, source evaluation, risks, and the implementation order that followed from them.
- [Game compatibility matrix](compatibility/GAME_UPDATE_MATRIX.md) — the Clash of Clans changes that affect navigation, OCR, templates, data tables, and state handling.
- [Repository plan](architecture/REPOSITORY_PLAN.md) — target structure and the phased sequence for getting there.
- [Merge playbook](development/MERGE_PLAYBOOK.md) — how upstream fixes and clean-room features enter this repository.
- [UI handoff](ui/UI_HANDOFF.md) — requirements for the separate design-system work.
- [Run Planner web UI](development/PLANNER_UI.md) — a local browser front-end for building run plans, and how it connects to the engine.
- [Capturing fixtures](development/CAPTURING_FIXTURES.md) — how to turn a screenshot into a validated current-client fixture.
- [Wiki data ingest](development/WIKI_INGEST.md) — how to pull per-level game data from the community wiki, and what it is and is not good for.
- [Engineering notes](development/ENGINEERING_NOTES.md) — why particular decisions were made, and which ports were deliberately not taken.
- [Install guide](INSTALL.md) — setup detail beyond the README's quick path.
- [Upstream changelog](CHANGELOG.md) — release notes inherited from MyBot.run.

## Branches

`master` is the current source of truth and is where completed work lands. The stale
`claude/coc-bot-merge-ui-kobgds` branch is intentionally left alone; cleaning it up is not a
prerequisite for current-client data, fixtures, UI integration, or runtime work.

## Checks

Everything under `tools/` is standard-library Python and runs on any platform. `.github/workflows/ci.yml`
runs the whole set on every push and pull request; `.github/workflows/windows-autoit.yml` runs
`Au3Check` and the AutoIt contract tests against AutoIt 3.3.16.1 and 3.3.18.0.

The AutoIt linter (`tools/lint_autoit.py`) exists because `Au3Check` is Windows-only. It catches
unbalanced blocks, `ByRef` parameters with defaults, required parameters following optional ones,
duplicate function definitions, undeclared globals, includes that do not resolve, `ByRef`
parameters bound to expressions, and functions a build calls but does not include. It resolves each
entry point's include graph the way AutoIt does, which is how it catches a module that compiles
fine in one build and not another.

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
8. Update `config/binary-provenance.json` whenever a shipped executable, DLL, or archive is rebuilt
   or replaced; `tools/repo_audit.py` treats hash or coverage drift as a release error.
