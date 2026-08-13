# Local release packaging

`tools/Build-Release.ps1` is the release boundary for the Windows x86 package. It never rewrites the
checked-in executables or the pinned Mini GUI. All five locally owned entry points are compiled into
an isolated work directory with explicit `/x86`, `/gui` or `/console`, `/nopack`, and `/comp 2`
arguments.

The launcher, main host, Engine Probe, and Watchdog retain the Windows GUI subsystem. WMI is the
only console helper. Watchdog may allocate a console for its explicit `/console` diagnostic mode,
but its packaged executable remains GUI like the reviewed artifact.

The default one-shot path is suitable when compiler output already matches the reviewed records in
`config/binary-provenance.json`:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tools/Build-Release.ps1 `
  -Action BuildAndPackage `
  -AutoItRoot "C:\Program Files (x86)\AutoIt3" `
  -Version 2.0.0 `
  -Mode LocalRuntime
```

AutoIt output may differ between builds. When it does, use the review path so the exact bytes that
were inspected are the bytes that are packaged:

1. Commit the reviewed source-only tree, then run `-Action CompileForReview` from that clean commit
   with `-AutoItRoot` and `-Version`.
2. Review the five candidate executables and `candidate-hashes.json` outside the live runtime.
3. Update `config/binary-provenance.json` in a separate, reviewed change. This script deliberately
   does not update provenance.
4. Commit only the five reviewed executables and updated provenance. Run `-Action PackageReviewed
   -ReviewedBinaryDirectory <candidate-directory> -Version <version>` from that clean commit. The
   packager verifies the candidate manifest, every candidate byte, ancestry, and that the intervening
   commit changed only those binaries and provenance.

The package uses an explicit allowlist. It excludes profiles, plans and control state, logs,
artifacts, caches, temporary helpers, `CLAUDE_HANDOFF_PROMPT.md`, and the working-tree
`Languages/English.ini`. The package exports the canonical `Languages/English.ini` blob from the
recorded source commit, so a live translation-cache rewrite cannot enter the archive and English is
never omitted. `MyBot.run.txt` must exist and remain exactly zero bytes. Every packaged
`.exe`, `.dll`, and `.sys` must have matching bytes and SHA-256 in binary provenance. ZIP entries
are sorted and assigned a fixed timestamp; the PE bytes themselves are preserved exactly.

Mutable profiles are intentionally outside that allowlist and outside the replaceable application
directory. Installed releases use `%LOCALAPPDATA%\My Bot 2.0\Profiles`; upgrades and uninstall retain
that directory.

`LocalRuntime` creates a local-use package only. It is not permission to redistribute the inherited
ImgLoc component. `PublicDistribution` fails unless the release operator has actual written
permission or has validated a clearly licensed replacement and supplies the exact acknowledgement
token printed in the script. That switch records an operator assertion; it does not create rights.

The workflow performs no code signing and makes no signing claim.

## Install the reviewed LocalRuntime package

Extract the ZIP, then double-click `Install My Bot 2.0.cmd`. The installer verifies the clean
LocalRuntime manifest, zero-byte engine marker, and launcher provenance before copying the package
to `%LOCALAPPDATA%\Programs\My Bot 2.0`. It creates a per-user Start-menu shortcut and Windows
Apps uninstall entry; it does not require administrator permission. After installation, open Start
and type `My Bot 2.0`.

On the first install, the installer creates and selects a `MyVillage` profile under
`%LOCALAPPDATA%\My Bot 2.0\Profiles`. To copy a compatible profile set from this source baseline,
run the extracted command with an explicit source:

```powershell
& ".\Install My Bot 2.0.cmd" -ProfileSourceDirectory "C:\path\to\My-Bot-2.0\Profiles"
```

The migration validates `profile.ini` and its selected profile directory, copies through an isolated
stage, and refuses any existing target content. It never overwrites or removes the source.

The installer refuses to update while an executable from the installed directory is running. Use
the Start-menu uninstall shortcut, Windows Installed apps, or `Uninstall My Bot 2.0.cmd` from the
extracted package to remove the per-user installation. Profile data remains under
`%LOCALAPPDATA%\My Bot 2.0\Profiles` after uninstall.
