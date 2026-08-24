# Gameplay scope and proof matrix

My Bot 2.0 is intended to automate the full repeatable Clash of Clans loop, not only resource farming. That product goal does not make every inherited routine current-client safe. This matrix is the release boundary: a source path means **implemented**, while support requires current recognition fixtures plus controlled runtime evidence.

The exhaustive direct-owner audit currently covers 1,179 actuator call sites in 465 non-test AutoIt owners. Of those owners, 30 are held by closed-world capability routes, 253 remain explicitly blocked, 181 are shared infrastructure, 1 is a compile-time test/reference owner, and 0 are unclassified. The inventory includes intended untracked AutoIt source, treats every dynamic `Call(...)` dispatch as an actuator boundary, and includes the reviewed one-shot point-click wrapper plus the public click, drag, region, training, image-button, text-input, ADB-shell, process, and window-control APIs rather than only their lowest-level transports. These are source-ownership counts, not support percentages: a capability-owned route still needs its required fixture and exact-current runtime evidence before the UI may advertise it as available.

The generated full-system inventory also derives parity directly from the pinned OG commit in
`config/upstreams.lock.json`. It classifies 339 OG automation sources (65 GUI/control sources,
273 function sources and the native entry point; overlapping paths are counted once) and records
the current path/blob state plus linked actuator policies for every row. No OG source is silently
unclassified. Parity inventory is a reachability and ownership audit, not live support evidence:
every exact-current runtime verdict remains deferred until its required fixture and supervised proof
exist.

| Scope | Native implementation | Current release status | Evidence required before support |
| --- | --- | --- | --- |
| Regular farming battles | `COCBot/functions/Attack` | Historical Standard/Smart observations exist, but exact-current supervised readiness was rejected by inherited ImgLoc before matchmaking. All generic battle strategies now fail closed before Start; diagnostic consent cannot bypass the licensing boundary. | Written licensed permission or a clean-room recognizer, then current-client entry/search/battle/end fixtures and structured deployment, spell, Hero, loot and stop events |
| Army training | `COCBot/functions/CreateArmy/TrainSystem.au3` | Inherited implementation; current Army Recipe/Cookbook screens are not verified | Army-screen fixture, exact composition proof, safe return home |
| Collectors and mines | `COCBot/functions/Run/OpenHomeCollectors.au3`, `COCBot/functions/Run/CollectorBubbleRecognizer.au3` | The prior packaged route proved three accepted clicks, resource increases, Home restoration, and unchanged gems. The protected recognizer has since been replaced by an independent pixel classifier that passes synthetic and authorized private before/after frames; the new source is not yet rebuilt or live-proven. | Rebuild all six binaries, install, prove no generated warning page, repeat the bounded collector receipt/resource/gem/Home checks, then refresh exact-current evidence |
| No-gem runtime guard | `COCBot/functions/Run/OpenHomeCollectors.au3` | Every reachable template-free Home click now passively rejects the inherited gem-window anchors, but only negative route fixtures exist. | Capture one privacy-safe positive gem-window fixture, prove black-frame and non-gem rejection, then prove a supervised route stops with zero input and unchanged gems |
| Loot Cart | `COCBot/functions/Run/LootCartRoute.au3` | Explicit Home-maintenance route allows at most one cart-open input and one exact Collect input; it never opens chat, uses fallback coordinates, confirms a dialog, or accepts gem conversion; current-client recognition and completion are not verified | Redacted Loot Cart fixture, exact issued-input receipts, unchanged gem balance, passive Home proof |
| Startup Daily Reward | `COCBot/functions/Run/OpenHomeCollectors.au3` | Claim and post-claim close recognition are fixture-verified. The route now also owns a clean-room inactivity Reload Game recovery point before Claim recognition. One supervised Claim committed with unchanged gems, but the rebuilt package still needs exact-current completion proof for inactivity recovery, Claim, red close, Home return, and gem balance. | Rebuilt route clears the inactivity popup if present, issues one Claim, recognizes the exact red close, returns Home automatically, and preserves plan/profile/language and gem balance |
| Treasury | `COCBot/functions/Run/TreasuryRoute.au3` | Explicit Home-maintenance route uses only a cached exact Clan Castle coordinate, requires a full Treasury and non-full Home storages, then permits one Castle, entry, Collect, contextual Okay, and close input each; no fallback, retry, generic confirmation, or gem path; current-client recognition and transfer completion are not verified | Redacted full-Treasury fixture, exact issued-input receipts, unchanged gem balance, Home restored |
| Achievements, challenge rewards, and free items | Legacy Home/Village maintenance functions | Not owned by a reviewed planner route; all are forced off during managed runs | One explicit closed-world route per reward surface, current-client fixtures, exact receipt, no-gems proof, Home restored |
| Pets | `COCBot/functions/Village/PetHouse.au3` | Inherited resource-spending path; not owned by a reviewed plan | Pet House fixture, exact Pet/cost/builder observation, one bounded upgrade, unchanged gems, Home restored |
| Hero equipment | `COCBot/functions/Village/Blacksmith.au3` | Inherited Blacksmith path; current equipment and ore states are not verified | Blacksmith fixture, exact equipment/ore observation, one bounded upgrade, unchanged gems, Home restored |
| Obstacles | `COCBot/functions/Image Search/CheckTombs.au3`, `COCBot/functions/Village/BuilderBase/CleanBBYard.au3` | Inherited Home and Builder removal paths; no cost or gem-surface proof | Exact obstacle/cost fixture, one bounded removal, black-frame rejection, unchanged gems, correct village restored |
| Helper Hut | `COCBot/functions/Village/HelperHut.au3` | Inherited Apprentice Builder and Laboratory Assistant actions; no plan contract | Helper identity/state fixture, exact duration/resource receipt, one bounded action, unchanged gems, Home restored |
| Boosts | `COCBot/functions/Village/BoostStructure.au3`, `BoostSuperTroop.au3` | Inherited potion/resource paths may reach gem surfaces and remain blocked | Exact boost/cost fixture, gem surface rejection, one bounded activation, unchanged gems, Home restored |
| Donate and request | `COCBot/functions/Village/DonateCC.au3`, `RequestCC.au3` | Inherited implementation; Global Chat and current request layout are not verified | Redacted chat/request fixtures, exact request match, army preservation, safe return home |
| Home Village upgrades | `COCBot/functions/Village/Auto Upgrade.au3` | Inherited implementation; current costs, Hero layout, buildings and TH18 are incomplete | Cost/name fixtures, no-premium-currency guard, one reviewed upgrade, safe return home |
| Laboratory | `COCBot/functions/Village/Laboratory.au3` | Inherited implementation; planner-driven selection is blocked | Lab fixture, research-state proof, one reviewed start, safe return home |
| Builder Base upgrades | `COCBot/functions/Village/BuilderBase/SuggestedUpgrades.au3` | Inherited implementation; current Builder count/layout is not verified | Builder Base fixtures, builder/resource proof, one reviewed upgrade |
| Builder resources, Star Laboratory, and Heroes | `COCBot/functions/Village/BuilderBase/Collect.au3`, `StarLaboratory.au3`, `UpgradeBattleMachine.au3`, `UpgradeBattleCopter.au3` | Inherited mixed paths; each is blocked until separated | Dedicated collection/research/Hero fixtures, exact cost or receipt, one action per route, unchanged gems, Builder Home restored |
| Builder Base battles | `COCBot/functions/Attack/BuilderBase/AttackBB.au3` | Inherited implementation; current route is blocked in the Run Planner | Entry/troop/end fixtures, one bounded battle, stop and return proof |
| Clan Games | `COCBot/functions/Village/Clan Games/ClanGames.au3` | Inherited implementation; challenge list and points are not verified | Challenge fixtures, selected challenge identity, completion and points proof |
| Multi-account | `COCBot/functions/Village/SwitchAccount.au3` | Inherited implementation; planner queue adapter remains blocked | Redacted account-switcher fixture, exact target identity, queue progression without credentials |
| Clan Capital upgrades | `COCBot/functions/Village/ClanCapital.au3` | Inherited implementation; current layout is not verified | Capital fixture, upgrade/resource proof, safe return |
| Forge and Capital Gold | `COCBot/functions/Village/ClanCapital.au3` | Mixed with Capital navigation and upgrade loops; not plan-owned | Forge slot/cost fixture, exact single-slot receipt, unchanged gems, main-village return |
| Trophy drop and Smart Zap | `COCBot/functions/Village/DropTrophy.au3`, `COCBot/functions/Attack/SmartZap/smartZap.au3` | Inherited battle actuators; all battle surfaces remain gated | Exact route/target/spell fixtures, one bounded execution, battle and Home receipts |
| Replay share and profile report | `COCBot/functions/Village/ReplayShare.au3`, `ProfileReport.au3` | Replay share types into chat; profile report can claim achievements; neither is a passive terminal route | Destination/identity fixtures, exact text or passive-only policy, no unintended claim, Home restored |
| Error/restart recovery | `COCBot/functions/Main Screen/checkObstacles.au3` and launcher `/recover` | Bounded owned-process recovery exists; broader game-dialog matrix is incomplete | Exact failure identity, no unrelated process closure, restored idle/home state, no orphan |

The machine-readable source of truth is [`config/current-client-capabilities.json`](../../config/current-client-capabilities.json). Direct actuator ownership is pinned separately in [`config/actuator-registry.json`](../../config/actuator-registry.json); CI fails on a new or ambiguous owner. The readiness evaluator fails closed when a required fixture mapping or trusted runtime record is absent.

## Hard safety boundaries

- No gems, purchases, offers, credentials, Supercell ID entry, chat posting, or account deletion may be inferred from a general run plan.
- A reward route may close a full-storage or conversion prompt, but it may never click its accept/Okay action when that action converts an item into gems.
- A visual click path is not supported merely because the inherited function exists or an AutoIt test passes.
- Account switching must bind an exact local profile and visually confirm the target account before gameplay resumes.
- Spending paths require a recognized resource type, exact cost, adequate non-premium balance and a reviewed no-gems guard.
- Unknown screens stop or return home; they never fall through to coordinate clicks.

## Promotion sequence

1. Capture and redact the named current-client fixture.
2. Add deterministic recognition and safe-region tests.
3. Run the smallest supervised action with exact source/binary provenance.
4. Record structured events and a human visual receipt.
5. Review the evidence and only then change the capability from `legacy-implemented` to `supported`.
