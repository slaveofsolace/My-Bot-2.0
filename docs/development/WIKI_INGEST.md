# Pulling game data from the community wiki

The Clash of Clans wiki on Fandom has per-level tables for buildings, troops, spells, heroes,
equipment, traps and pets. `tools/wiki_ingest.py` downloads that data and turns it into JSON the
project can use.

**You have to run this yourself.** The build environment this repository is developed in blocks
`fandom.com` at the network layer, so the tool was written and tested offline against a sample. The
fetch step has never been run against the live API — see [If something goes wrong](#if-something-goes-wrong).

---

## What you need

- **Python 3.11 or newer.** Check with `python --version`. No packages to install; the tool uses
  only the standard library.
- **A normal internet connection.** No API key, no wiki account.
- **About 15 minutes** for a full run, most of it waiting on the rate limit.

---

## Step 1 — Verify the parser works

Do this first. It takes a second, needs no network, and confirms the tool runs on your machine
before you point it at the wiki.

```bash
cd My-Bot-2.0
python tools/wiki_ingest.py selftest
```

Expected output ends with:

```
selftest passed
```

If you see `FAIL` lines, stop and report them — the parser is broken and fetching would just give
you unusable data.

---

## Step 2 — Do a small trial fetch

Never start with the full run. Pull a handful of pages from one category and look at what comes
back.

```bash
python tools/wiki_ingest.py fetch --only heroes --limit 3
```

This downloads three Hero pages. Expected output:

```
[heroes] listing Category:Heroes
  3 pages
    fetched 3/3
  wrote data/wiki-staging/heroes.json (3 pages)

fetch summary:
  heroes               {'pages': 3}
```

Now parse it:

```bash
python tools/wiki_ingest.py parse
```

Then open `data/wiki-parsed/heroes.json` and look at it. You should see, for each page, a
`level_tables` array with real numbers in it. If the tables are empty or the numbers look wrong,
stop here — that means the wiki's templates differ from what the parser expects, and the fix is a
parser change, not more fetching.

---

## Step 3 — Full fetch

Once the trial looks right:

```bash
python tools/wiki_ingest.py fetch
python tools/wiki_ingest.py parse
```

This pulls all ten categories. It will take a while — there is a one-second pause between API calls
on purpose.

### Groups it fetches

| Group | Wiki category |
|---|---|
| `home-buildings` | Home Village Buildings |
| `builder-buildings` | Builder Base Buildings |
| `heroes` | Heroes |
| `troops` | Home Village Troops |
| `dark-troops` | Dark Elixir Troops |
| `spells` | Spells |
| `equipment` | Hero Equipment |
| `traps` | Traps |
| `siege` | Siege Machines |
| `pets` | Pets |

Fetch a subset with `--only`:

```bash
python tools/wiki_ingest.py fetch --only home-buildings,troops,spells
```

---

## Step 4 — Commit the results

```bash
git add data/wiki-staging data/wiki-parsed
git commit -m "Add community wiki data pull"
git push
```

Both directories are committed on purpose. `data/wiki-staging/` holds the raw download so the parser
can be improved and re-run without hitting the wiki again; `data/wiki-parsed/` holds the normalised
output.

---

## Options

| Flag | Does |
|---|---|
| `--only a,b,c` | Fetch only these groups |
| `--limit N` | At most N pages per category. Use for trial runs. |
| `--delay S` | Seconds between API calls. Default 1.0. **Do not go below 0.5.** |

The delay exists so the tool does not hammer a free community wiki. The API also gets `maxlag=5`,
which tells MediaWiki to refuse the request rather than add load when the server is already
struggling; the tool backs off and retries when that happens.

---

## What it does and does not extract

**Extracted:** infobox fields and per-level stat tables — levels, hitpoints, damage, costs, build
times, capacities, unlock requirements. Numbers and short enumerable values.

**Not extracted:** article prose, strategy advice, trivia, images.

That split is deliberate. The wiki is CC-BY-SA. Factual data like "Cannon level 3 has 520 hitpoints"
is not copyrightable and is free to use. Article text is copyrightable and is not taken.

Every parsed page records its `title`, `revid`, `timestamp` and `source_url`, so attribution can be
generated for any value that ends up in the catalogs.

---

## How this relates to the official catalogs

`config/game/*.json` is sourced from official Supercell release notes and carries
`source_confidence` values of `official-explicit` or `official-historical-context`.

Wiki data is **not** as reliable. Fan wikis lag behind updates and contain errors. Everything this
tool produces is tagged `source_confidence: community-wiki`, which is a lower tier, and it lands in
`data/wiki-parsed/` rather than directly in `config/game/`.

Promoting a value into the official catalogs is a separate, deliberate step. The order of preference
when they disagree is always: official release note, then in-game observation, then wiki.

---

## If something goes wrong

The fetch step has not been run against the live API from this project's build environment, so
treat the first real run as a test.

| Symptom | Cause | What to do |
|---|---|---|
| `HTTP 403` | Fandom is blocking the user agent | Report it — the user agent string may need updating |
| `API error: {'code': 'maxlag'...}` repeatedly | Wiki server under load | Wait and retry; raise `--delay` |
| `unknown group(s)` | Typo in `--only` | The error lists the valid names |
| Parse finds 0 level tables everywhere | Wiki changed its table markup | Report it with one staged page attached; `parse_level_tables` needs updating |
| Some pages listed as yielding no data | Normal for disambiguation and overview pages | Ignore unless a page you care about is listed |
| `gave up after 3 attempts` | Network or DNS | Check the connection and re-run; staged groups already written are kept |

Re-running `fetch` overwrites a group's staged file, so an interrupted run is safe to repeat. `parse`
never touches the network and can be run as often as you like.
