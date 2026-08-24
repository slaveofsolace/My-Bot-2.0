# Clan Request input permits

The Clan Request one-shot route owns five and only five input actions on the canonical
860x732 BlueStacks surface:

| Action | Point | Required current-frame predicate |
| --- | --- | --- |
| Open Army Overview | `39,585` | neutral Home Village |
| Open Request dialog | `761,498` | Army Overview with Request available |
| Send request | `545,478` | Request Reinforcements dialog |
| Cancel dialog | `316,478` | Request Reinforcements dialog |
| Close Army Overview | `792,187` | Army Overview |

Each action uses an exact action identifier and point. The source-owned permit gate
captures and recognizes the required surface when minting the permit, consumes the
permit before transport, captures and recognizes the surface again, and permits one
window-control or ADB click egress. Send is attempted at most once and is never retried.

The verified `clan.request.available` fixture supports the dialog predicate. The
`army.training.ready` frame contains the reviewed Army Overview anchors and its privacy
masks do not cover the Request control, so it is mapped to `village.clan-request` for
honest coverage accounting. Its manifest status is still `redacted`, not `verified`.
Therefore Clan Request remains fixture-blocked for exact-current Army Overview entry
recognition until that fixture's assertions receive independent review and the fixture
is promoted through the normal verification workflow. The verified dialog frame alone
does not prove Home-to-Army navigation or Request availability.
