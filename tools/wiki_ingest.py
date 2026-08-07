#!/usr/bin/env python3
"""Pull game data from the Clash of Clans community wiki.

Three subcommands, meant to be run in order:

    fetch     Download raw page data from the MediaWiki API into data/wiki-staging/.
    parse     Turn staged pages into normalised JSON in data/wiki-parsed/.
    selftest  Run the parser against a bundled sample. No network needed.

Fetching and parsing are deliberately separate. Fetching is the part that touches the network and is
slow; parsing is the part most likely to need adjusting when the wiki changes its templates. Keeping
them apart means you download once and can re-parse as often as you like.

The wiki is CC-BY-SA. Numbers are facts and are not copyrightable, so level tables and costs are fine
to use. Article prose is not: this tool extracts numeric and enumerable fields only, and records the
source page and revision for every value so attribution can be produced.

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data/wiki-staging"
PARSED = ROOT / "data/wiki-parsed"

API = "https://clashofclans.fandom.com/api.php"

# Identifies this tool to the wiki. Courtesy, and it means the operators can contact the project
# rather than blanket-blocking an anonymous scraper.
USER_AGENT = (
    "MyBot2.0-WikiIngest/1.0 "
    "(+https://github.com/slaveofsolace/My-Bot-2.0; game data catalog for an open source project)"
)

# Categories worth pulling. Each becomes a group of pages under data/wiki-staging/<group>/.
DEFAULT_CATEGORIES = {
    "home-buildings": "Category:Home Village Buildings",
    "builder-buildings": "Category:Builder Base Buildings",
    "heroes": "Category:Heroes",
    "troops": "Category:Home Village Troops",
    "dark-troops": "Category:Dark Elixir Troops",
    "spells": "Category:Spells",
    "equipment": "Category:Hero Equipment",
    "traps": "Category:Traps",
    "siege": "Category:Siege Machines",
    "pets": "Category:Pets",
}


class WikiError(RuntimeError):
    pass


def api_get(params: dict, delay: float, retries: int = 3) -> dict:
    """One API call, with a polite delay and bounded retries on transient failures."""
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    # maxlag tells MediaWiki to refuse rather than pile onto a struggling server.
    params.setdefault("maxlag", "5")

    url = f"{API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if "error" in payload:
                code = payload["error"].get("code", "")
                if code == "maxlag":
                    time.sleep(5 * (attempt + 1))
                    continue
                raise WikiError(f"API error: {payload['error']}")
            time.sleep(delay)
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            raise WikiError(f"HTTP {exc.code} for {params.get('titles') or params.get('cmtitle')}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(3 * (attempt + 1))

    raise WikiError(f"gave up after {retries} attempts: {last_error}")


def category_members(category: str, delay: float, limit: int = 0) -> list[str]:
    """Every page in a category, following continuation."""
    titles: list[str] = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": "500",
        "cmnamespace": "0",
    }
    while True:
        payload = api_get(params, delay)
        for member in payload.get("query", {}).get("categorymembers", []):
            titles.append(member["title"])
            if limit and len(titles) >= limit:
                return titles
        if "continue" not in payload:
            return titles
        params.update(payload["continue"])


def fetch_pages(titles: list[str], delay: float) -> list[dict]:
    """Wikitext plus revision id for each page, in batches the API accepts."""
    pages: list[dict] = []
    for start in range(0, len(titles), 20):
        batch = titles[start:start + 20]
        payload = api_get({
            "action": "query",
            "prop": "revisions",
            "rvprop": "content|ids|timestamp",
            "rvslots": "main",
            "titles": "|".join(batch),
        }, delay)
        for page in payload.get("query", {}).get("pages", []):
            revisions = page.get("revisions") or []
            if not revisions:
                continue
            slot = revisions[0].get("slots", {}).get("main", {})
            pages.append({
                "title": page.get("title"),
                "pageid": page.get("pageid"),
                "revid": revisions[0].get("revid"),
                "timestamp": revisions[0].get("timestamp"),
                "wikitext": slot.get("content", ""),
            })
        print(f"    fetched {min(start + 20, len(titles))}/{len(titles)}", flush=True)
    return pages


# --------------------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------------------

NUMBER = re.compile(r"^-?[\d,]+(?:\.\d+)?$")
TEMPLATE_ARG = re.compile(r"^\s*\|?\s*([A-Za-z0-9 _\-]+?)\s*=\s*(.*?)\s*$")


def clean_value(raw: str) -> str:
    """Strip the wiki markup that wraps otherwise plain values."""
    text = raw
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)   # [[Link|Text]] -> Text
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)                        # drop simple templates
    text = re.sub(r"'''?", "", text)                                  # bold / italic
    text = re.sub(r"<[^>]+>", " ", text)                              # stray html
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split()).strip()


def to_number(text: str):
    """Return an int or float when the cell is numeric, otherwise None."""
    candidate = text.replace(",", "").strip()
    if not NUMBER.fullmatch(text.strip()) and not NUMBER.fullmatch(candidate):
        return None
    try:
        return int(candidate)
    except ValueError:
        try:
            return float(candidate)
        except ValueError:
            return None


def parse_infoboxes(wikitext: str) -> list[dict]:
    """Named arguments of each top-level template call, which is where infobox fields live."""
    results = []
    depth = 0
    buffer: list[str] = []
    index = 0
    while index < len(wikitext) - 1:
        pair = wikitext[index:index + 2]
        if pair == "{{":
            depth += 1
            if depth == 1:
                buffer = []
                index += 2
                continue
        elif pair == "}}":
            depth -= 1
            if depth == 0:
                fields = {}
                for line in "".join(buffer).split("\n|"):
                    match = TEMPLATE_ARG.match(line)
                    if not match:
                        continue
                    key = match.group(1).strip().lower().replace(" ", "_")
                    value = clean_value(match.group(2))
                    if key and value:
                        fields[key] = value
                if len(fields) >= 2:
                    results.append(fields)
                index += 2
                continue
        if depth >= 1:
            buffer.append(wikitext[index])
        index += 1
    return results


def parse_level_tables(wikitext: str) -> list[dict]:
    """Wiki tables that look like per-level stat tables: a header row plus numeric body rows."""
    tables = []
    for block in re.findall(r"\{\|(.*?)\n\|\}", wikitext, flags=re.DOTALL):
        rows: list[list[str]] = []
        current: list[str] = []
        for line in block.split("\n"):
            stripped = line.strip()
            if stripped.startswith("|-"):
                if current:
                    rows.append(current)
                current = []
            elif stripped.startswith("!") or stripped.startswith("|"):
                body = stripped.lstrip("!|")
                # A row may pack several cells onto one line with || or !!
                for cell in re.split(r"\|\||!!", body):
                    cleaned = clean_value(cell)
                    if "|" in cell and not cleaned:
                        cleaned = clean_value(cell.split("|")[-1])
                    current.append(cleaned)
        if current:
            rows.append(current)

        rows = [r for r in rows if any(c for c in r)]
        if len(rows) < 2:
            continue
        header = [h.lower().replace(" ", "_") for h in rows[0]]
        if not any("level" in h for h in header):
            continue

        records = []
        for row in rows[1:]:
            if len(row) < 2:
                continue
            record = {}
            for key, cell in zip(header, row):
                if not key:
                    continue
                number = to_number(cell)
                record[key] = number if number is not None else cell
            if record:
                records.append(record)
        if records:
            tables.append({"columns": header, "rows": records})
    return tables


def parse_page(page: dict) -> dict:
    wikitext = page.get("wikitext", "")
    return {
        "title": page.get("title"),
        "pageid": page.get("pageid"),
        "revid": page.get("revid"),
        "timestamp": page.get("timestamp"),
        "source_url": "https://clashofclans.fandom.com/wiki/"
                      + urllib.parse.quote((page.get("title") or "").replace(" ", "_")),
        "infoboxes": parse_infoboxes(wikitext),
        "level_tables": parse_level_tables(wikitext),
    }


# --------------------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------------------

def cmd_fetch(args) -> int:
    categories = DEFAULT_CATEGORIES
    if args.only:
        wanted = {name.strip() for name in args.only.split(",")}
        unknown = wanted - set(categories)
        if unknown:
            print(f"unknown group(s): {', '.join(sorted(unknown))}")
            print(f"available: {', '.join(sorted(categories))}")
            return 2
        categories = {k: v for k, v in categories.items() if k in wanted}

    STAGING.mkdir(parents=True, exist_ok=True)
    summary = {}
    for group, category in sorted(categories.items()):
        print(f"[{group}] listing {category}")
        try:
            titles = category_members(category, args.delay, args.limit)
        except WikiError as exc:
            print(f"  FAILED: {exc}")
            summary[group] = {"error": str(exc)}
            continue
        print(f"  {len(titles)} pages")
        if not titles:
            summary[group] = {"pages": 0}
            continue
        pages = fetch_pages(titles, args.delay)
        out = STAGING / f"{group}.json"
        out.write_text(json.dumps({
            "group": group,
            "category": category,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "license": "CC-BY-SA (Fandom). Numeric data only; prose is not extracted.",
            "pages": pages,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {out.relative_to(ROOT)} ({len(pages)} pages)")
        summary[group] = {"pages": len(pages)}

    print("\nfetch summary:")
    for group, info in sorted(summary.items()):
        print(f"  {group:<20} {info}")
    return 0


def cmd_parse(args) -> int:
    if not STAGING.exists():
        print(f"nothing staged. Run: python tools/wiki_ingest.py fetch")
        return 2

    PARSED.mkdir(parents=True, exist_ok=True)
    total_pages = total_tables = unparsed = 0
    report = []

    for staged in sorted(STAGING.glob("*.json")):
        data = json.loads(staged.read_text(encoding="utf-8"))
        parsed_pages = []
        for page in data.get("pages", []):
            result = parse_page(page)
            parsed_pages.append(result)
            total_pages += 1
            total_tables += len(result["level_tables"])
            if not result["level_tables"] and not result["infoboxes"]:
                unparsed += 1
                report.append(result["title"])

        out = PARSED / staged.name
        out.write_text(json.dumps({
            "group": data.get("group"),
            "source_category": data.get("category"),
            "fetched_at": data.get("fetched_at"),
            "source_confidence": "community-wiki",
            "license": data.get("license"),
            "pages": parsed_pages,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {staged.stem:<20} {len(parsed_pages)} pages -> {out.relative_to(ROOT)}")

    print(f"\nparsed {total_pages} pages, {total_tables} level tables")
    if unparsed:
        # Reported rather than swallowed: a page yielding nothing usually means a template changed.
        print(f"{unparsed} page(s) yielded no structured data:")
        for title in report[:25]:
            print(f"  - {title}")
        if len(report) > 25:
            print(f"  ... and {len(report) - 25} more")
    return 0


SAMPLE = """
{{Building
|name = Cannon
|description = The Cannon is a single-target defence.
|village = home
|unlock_th = 1
}}
Some prose that must not be extracted.

{| class="wikitable"
! Level !! Damage per Second !! Hitpoints !! Build Cost !! Build Time
|-
| 1 || 7.2 || 420 || 250 || 1m
|-
| 2 || 8.8 || 470 || 1,000 || 15m
|-
| 3 || 12 || 520 || 4,000 || 45m
|}
"""


def cmd_selftest(args) -> int:
    """Exercises the parser on a known sample so it can be verified without touching the network."""
    page = {"title": "Cannon", "pageid": 1, "revid": 2, "timestamp": "2026-01-01T00:00:00Z",
            "wikitext": SAMPLE}
    result = parse_page(page)

    failures = []

    def check(condition, message):
        print(f"  {'ok  ' if condition else 'FAIL'}  {message}")
        if not condition:
            failures.append(message)

    boxes = result["infoboxes"]
    check(len(boxes) == 1, f"one infobox found (got {len(boxes)})")
    if boxes:
        check(boxes[0].get("name") == "Cannon", "infobox name extracted")
        check(boxes[0].get("unlock_th") == "1", "infobox numeric field extracted")

    tables = result["level_tables"]
    check(len(tables) == 1, f"one level table found (got {len(tables)})")
    if tables:
        rows = tables[0]["rows"]
        check(len(rows) == 3, f"three level rows (got {len(rows)})")
        check("level" in tables[0]["columns"], "level column detected")
        if rows:
            check(rows[0].get("hitpoints") == 420, "hitpoints parsed as an integer")
            check(rows[1].get("build_cost") == 1000, "comma-separated cost parsed as 1000")
            check(rows[2].get("damage_per_second") == 12, "decimal-free float parsed as a number")
            check(rows[0].get("build_time") == "1m", "non-numeric cell kept as text")

    check(result["source_url"].endswith("/wiki/Cannon"), "source url recorded for attribution")
    check("prose" not in json.dumps(result).lower(), "article prose is not extracted")

    print(f"\n{'selftest passed' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="download raw pages into data/wiki-staging/")
    fetch.add_argument("--delay", type=float, default=1.0,
                       help="seconds between API calls (default 1.0; do not go below 0.5)")
    fetch.add_argument("--limit", type=int, default=0,
                       help="max pages per category, for a quick trial run (default 0 = all)")
    fetch.add_argument("--only", type=str, default="",
                       help="comma-separated group names, e.g. --only heroes,troops")
    fetch.set_defaults(func=cmd_fetch)

    parse_cmd = sub.add_parser("parse", help="turn staged pages into data/wiki-parsed/")
    parse_cmd.set_defaults(func=cmd_parse)

    selftest = sub.add_parser("selftest", help="verify the parser offline")
    selftest.set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
