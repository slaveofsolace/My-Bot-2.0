# Gameplay scope and proof matrix

My Bot 2.0 is intended to automate the full repeatable Clash of Clans loop, not only resource farming. That product goal does not make every inherited routine current-client safe. This matrix is the release boundary: a source path means **implemented**, while support requires current recognition fixtures plus controlled runtime evidence.

| Scope | Native implementation | Current release status | Evidence required before support |
| --- | --- | --- | --- |
| Regular farming battles | `COCBot/functions/Attack` | Standard deployment and one Smart path have supervised battle observations; other routes and layouts remain diagnostic | Current-client entry/search/battle/end fixtures; structured deployment, spell, Hero, loot and stop events |
| Army training | `COCBot/functions/CreateArmy/TrainSystem.au3` | Inherited implementation; current Army Recipe/Cookbook screens are not verified | Army-screen fixture, exact composition proof, safe return home |
| Collectors and mines | `COCBot/functions/Run/OpenHomeCollectors.au3` | Template-free BlueStacks 5 route implemented; one supervised direct current-client pass collected Gold, Elixir, and Dark Elixir with Home re-proved before each input. The integrated packaged-binary route is not yet runtime-evidenced. | Redacted collector fixture, exact packaged-binary click receipts, Home restored, unchanged gems/profile/account state |
| Loot Cart | `COCBot/functions/Run/LootCartRoute.au3` | Explicit Home-maintenance route allows at most one cart-open input and one exact Collect input; it never opens chat, uses fallback coordinates, confirms a dialog, or accepts gem conversion; current-client recognition and completion are not verified | Redacted Loot Cart fixture, exact issued-input receipts, unchanged gem balance, passive Home proof |
| Startup Daily Reward | `COCBot/functions/Main Screen/checkObstacles.au3` | Explicit Home-maintenance route issues at most one Claim input and never accepts a gem-conversion dialog; current-client recognition and completion are not verified | Redacted Daily Reward fixture, one issued Claim receipt, unchanged gem balance, Home restored |
| Treasury | `COCBot/functions/Run/TreasuryRoute.au3` | Explicit Home-maintenance route uses only a cached exact Clan Castle coordinate, requires a full Treasury and non-full Home storages, then permits one Castle, entry, Collect, contextual Okay, and close input each; no fallback, retry, generic confirmation, or gem path; current-client recognition and transfer completion are not verified | Redacted full-Treasury fixture, exact issued-input receipts, unchanged gem balance, Home restored |
| Achievements, challenge rewards, and free items | Legacy Home/Village maintenance functions | Not owned by a reviewed planner route; all are forced off during managed runs | One explicit closed-world route per reward surface, current-client fixtures, exact receipt, no-gems proof, Home restored |
| Donate and request | `COCBot/functions/Village/DonateCC.au3`, `RequestCC.au3` | Inherited implementation; Global Chat and current request layout are not verified | Redacted chat/request fixtures, exact request match, army preservation, safe return home |
| Home Village upgrades | `COCBot/functions/Village/Auto Upgrade.au3` | Inherited implementation; current costs, Hero layout, buildings and TH18 are incomplete | Cost/name fixtures, no-premium-currency guard, one reviewed upgrade, safe return home |
| Laboratory | `COCBot/functions/Village/Laboratory.au3` | Inherited implementation; planner-driven selection is blocked | Lab fixture, research-state proof, one reviewed start, safe return home |
| Builder Base upgrades | `COCBot/functions/Village/BuilderBase/SuggestedUpgrades.au3` | Inherited implementation; current Builder count/layout is not verified | Builder Base fixtures, builder/resource proof, one reviewed upgrade |
| Builder Base battles | `COCBot/functions/Attack/BuilderBase/AttackBB.au3` | Inherited implementation; current route is blocked in the Run Planner | Entry/troop/end fixtures, one bounded battle, stop and return proof |
| Clan Games | `COCBot/functions/Village/Clan Games/ClanGames.au3` | Inherited implementation; challenge list and points are not verified | Challenge fixtures, selected challenge identity, completion and points proof |
| Multi-account | `COCBot/functions/Village/SwitchAccount.au3` | Inherited implementation; planner queue adapter remains blocked | Redacted account-switcher fixture, exact target identity, queue progression without credentials |
| Clan Capital upgrades | `COCBot/functions/Village/ClanCapital.au3` | Inherited implementation; current layout is not verified | Capital fixture, upgrade/resource proof, safe return |
| Error/restart recovery | `COCBot/functions/Main Screen/checkObstacles.au3` and launcher `/recover` | Bounded owned-process recovery exists; broader game-dialog matrix is incomplete | Exact failure identity, no unrelated process closure, restored idle/home state, no orphan |

The machine-readable source of truth is [`config/current-client-capabilities.json`](../../config/current-client-capabilities.json). Its readiness evaluator fails closed when a required fixture mapping or trusted runtime record is absent.

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
