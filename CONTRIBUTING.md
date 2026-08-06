# Contributing

My Bot 2.0 is being rebuilt in reviewable stages. The current priority is preserving the v8.2.0 source baseline while adding current-client compatibility, tests, and a stable engine/UI boundary.

## Before changing code

1. Read `docs/audit/BASELINE_AUDIT_2026-08-06.md`.
2. Check `docs/compatibility/GAME_UPDATE_MATRIX.md`.
3. Confirm the source and commit in `upstreams.lock.json`.
4. Decide whether the work is an original change, an attributed GPL port, or a clean-room implementation of public behavior.
5. Keep UI styling, compatibility logic, and physical file moves in separate changes.

## Branches

Use a focused branch from `integration/unified-foundation`.

Recommended prefixes:

- `compat/` — game, popup, OCR, template, or emulator compatibility
- `feature/` — original product feature
- `ui/` — design system or shell work
- `refactor/` — behavior-neutral structure changes
- `test/` — fixtures and validation
- `docs/` — documentation only
- `build/` — tooling, packaging, or CI

## Commit messages

Use a direct subsystem and outcome:

```text
compat(android): correct LDPlayer instance addressing
compat(hero-hall): recognize Hero Journey interruption
refactor(profiles): add schema version adapter
ui(run-plan): add detailed strategy selector
build(audit): validate local AutoIt includes
```

Avoid generic messages such as `update`, `changes`, `latest support`, or `fix stuff`.

## Source provenance

For an adapted upstream change, include:

- repository
- exact commit
- source paths
- license
- reason for the port
- differences from the upstream implementation
- validation evidence

Do not copy code or assets from a repository that does not provide source under a compatible license. Public screenshots or feature descriptions may be converted into original requirements, not copied implementation.

## Code expectations

- Keep `Opt("MustDeclareVars", 1)` compatibility.
- Prefer stable IDs over localized display strings or array positions.
- Do not add a new global when a feature-scoped structure or adapter can own the state.
- Bound retries and return a reason when an action fails.
- Route unexpected screens through the interruption inventory.
- Keep image regions, template family, and game version documented together.
- Avoid blind clicks on unrecognized screens.
- Never log credentials, login codes, payment data, or personal chat text.
- Do not add automatic premium-currency spending without a separate, explicit, off-by-default design and review.
- Do not add stealth, fingerprint spoofing, detection-evasion, or ban-avoidance behavior.

## User-facing settings

Every new setting requires:

- stable key/ID
- label
- short description
- default
- valid values or range
- dependency/conflict rules
- persistence behavior
- reset behavior
- migration behavior
- documentation for non-obvious consequences

A disabled dropdown option must explain why it is unavailable.

## Validation evidence

A compatibility pull request should include as many of these as apply:

- static audit output
- AutoIt syntax check
- source build result
- positive and negative screenshot fixtures
- expected state transition
- recovery-path result
- Windows version
- emulator product/version and instance
- game client version
- redacted log excerpt
- clean-profile smoke test

Do not state that a feature is supported when only source changes or templates have been added.

## Pull-request scope

A reviewable pull request has one primary outcome. Large updates should be divided into:

1. fixture or failing check
2. catalog/schema change
3. platform/recognition change
4. state transition and recovery
5. UI descriptor
6. documentation and evidence

Broad directory moves should be mechanical and behavior-neutral.

## Documentation style

- Write for operators and maintainers, not for the implementation alone.
- Use exact dates, versions, branches, and commits.
- Separate verified facts from assumptions and planned work.
- Keep installation steps copyable.
- Use direct, ordinary wording.
- Preserve original license and copyright notices.

## Reporting bugs

Include the template in `docs/INSTALL.md`. Remove private information before attaching logs or screenshots. For security-sensitive issues, follow `SECURITY.md` instead of opening a public issue with exploit details.
