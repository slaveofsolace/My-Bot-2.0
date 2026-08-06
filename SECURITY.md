# Security policy

## Scope

Security reports may cover the source code, build and update process, profile storage, local logs, account-switch verification, emulator/ADB integration, native libraries, release artifacts, or documentation that could cause unsafe installation behavior.

Gameplay compatibility bugs and ordinary feature failures should use the normal issue process. Do not post credentials, login codes, personal chat content, payment information, or unredacted profile data in either location.

## Reporting a security issue

Use GitHub's private vulnerability reporting feature for this repository when available. Include:

- affected commit or release
- affected path or component
- clear impact
- reproduction steps
- required environment
- proof-of-concept limited to the minimum needed to demonstrate the issue
- suggested mitigation, when known

Do not open a public issue containing a working credential-theft path, arbitrary code execution chain, unsafe update path, or private account data.

## Sensitive data rules

The project must not collect or log:

- Supercell ID login codes
- passwords or recovery data
- payment details
- emulator account credentials
- private keys or access tokens
- full personal chat history

Account switching should verify a non-secret display identity or approved test identifier. Logs should use profile/account aliases and redact personal content by default.

## Native and binary dependencies

The inherited tree contains executables and native libraries. Until the release pipeline is rebuilt:

- prefer reviewed source execution for development
- do not assume inherited binaries match the current source
- record hashes and provenance before using a native dependency
- do not disable antivirus or endpoint protection as an installation step
- quarantine or remove an unexplained binary instead of adding an exclusion
- never publish a new release made from unverified inherited executables

Future releases should include a dependency manifest, source commit, checksums, build environment, and signature status.

## Profiles and local storage

- New profile formats require a schema version.
- Credentials do not belong in profile INI files.
- Diagnostic exports must be reviewable before sharing.
- Screenshots should support masking account identifiers, chat text, and notifications.
- Logs and screenshot evidence must have bounded retention.
- Temporary files should be written to project-controlled paths and removed on clean shutdown where practical.

## Emulator and ADB boundary

- Connect only to the selected local test instance.
- Verify the device identity and expected port before sending input.
- Do not expose ADB to external interfaces as part of setup.
- Do not install unrelated certificates, proxies, packet interception, or device-management profiles.
- Treat a device mismatch as a hard stop, not a warning.
- Never use emulator integration to collect credentials or unrelated app data.

## Update and release safety

A future updater must:

- use HTTPS
- verify a signed or pinned manifest
- verify file hashes before replacement
- reject downgrades unless explicitly requested
- stage updates safely and support rollback
- preserve user profiles separately from program files
- never execute an unsigned payload solely because a server returned it

No update service is considered trusted merely because it uses the project name.

## Automation boundary

Supercell's public policy prohibits unapproved gameplay bots on live accounts. This repository is intended only for environments and accounts where testing is explicitly authorized. Security work must not add stealth, anti-detection, fingerprint spoofing, ban avoidance, or mechanisms intended to defeat enforcement.

## Disclosure handling

Maintainers should acknowledge a private report, reproduce it where possible, document affected versions, prepare a narrow fix, add a regression check, and publish a concise advisory after affected users have a reasonable update path.
