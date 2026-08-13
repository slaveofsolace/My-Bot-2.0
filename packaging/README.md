# Local release packaging

`tools/build_release.py` is the fail-closed release boundary for the Windows x86 LocalRuntime
package. It does not depend on PowerShell or the .NET CLR. The older
`tools/Build-Release.ps1` remains as a compatibility implementation, but new reviewed releases use
the Python boundary and its mandatory two-phase flow. The Python tool never rewrites the pinned
Mini GUI. It temporarily isolates each checked-in pragma output, restores it byte-for-byte, and
compiles the five locally owned entry points with explicit `/x86`, `/gui` or `/console`, `/nopack`,
and `/comp 2` arguments.

The launcher, main host, Engine Probe, and Watchdog retain the Windows GUI subsystem. WMI is the
only console helper. Watchdog may allocate a console for its explicit `/console` diagnostic mode,
but its packaged executable remains GUI like the reviewed artifact.

The release must start from an isolated, clean worktree at the reviewed source commit. Compile the
five candidates without packaging them:

```console
python tools/build_release.py --action compile-for-review ^
  --autoit-root "C:\Program Files (x86)\AutoIt3" ^
  --version 2.0.0 ^
  --output-directory "C:\path\to\isolated-release-output"
```

AutoIt output may differ between builds, so the exact bytes inspected must be the exact bytes
packaged:

1. Commit the reviewed source-only tree, then run `--action compile-for-review` from that clean
   commit using the Python command above.
2. Review the five candidate executables and `candidate-hashes.json` outside the live runtime.
3. Replace only the five checked-in executables with those reviewed bytes and update
   `config/binary-provenance.json`. The tool deliberately never writes provenance for the operator.
4. Commit only those five executables and provenance. From that clean descendant, package the exact
   reviewed candidate directory:

   ```console
   python tools/build_release.py --action package-reviewed ^
     --reviewed-binary-directory "C:\path\to\MyBot-2.0.0-win-x86-candidate" ^
     --version 2.0.0 ^
     --output-directory "C:\path\to\isolated-release-output"
   ```

The packager verifies the repository audit, clean source and immutable commit identity, candidate
manifest and bytes, ancestry, the exact intervening-change allowlist, promoted Git blobs, compiler
identity, complete binary provenance, pinned Mini GUI, zero-byte marker, and tracked payload
allowlist. It builds the payload exclusively from recorded Git blobs, never mutable working-tree
files. ZIP paths are sorted below one package root, timestamps are fixed to 1980-01-01, and final
publication is atomic and refuses to overwrite another release.

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
ImgLoc component. The Python boundary has no PublicDistribution mode and fails on every other mode.
Public release remains blocked until actual written ImgLoc permission exists or a clearly licensed
replacement has been validated. The legacy PowerShell acknowledgement switch records an operator
assertion; it does not create rights.

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
