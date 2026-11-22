#!/usr/bin/env python3
"""Build the member's site from the SFO, the member's history and its journal.

    python3 build.py              REVOTT defaults to ~/revott

Writes, under docs/:

    data/sfo.json         REVOTT's 550 keys read in layers, and its 945 edges
    data/relevance.json   one entry per day of the URL era: the day's rows, the rows
                          any entry matched, the day's leading matched event, and the
                          events each entry matched -- NULL where GDELT published no
                          archive; docs/relevance.js reads it as member.py does
    data/items/YEAR.json  for each day, the entries that drove its reading (the largest terms of its sum)
                          and up to three passing items carrying them: the feed archive's headlines on
                          the days it covers, else GDELT's most-carried passing events
    data/filter.json      the geopolitical filter's classes, sources and codes (filter/classes.json)
    data/orders.json      the member's standing orders, relevance terms included
    data/journal.json     the list of journal entries
    journal/DAY.md        the entries themselves, written there by member.py

The page does the rest in the browser: it locates any instant on any Y's SFO and
walks the micronodes along every open edge, from these files alone. The corpus
is read by the member through `unzip -p` and never extracted; nothing here
touches it except through the member's cache.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVOTT = Path(os.environ.get("REVOTT", Path.home() / "revott"))
sys.path.insert(0, str(REVOTT))
sys.path.insert(0, str(HERE))
from revott.sfo import SFO  # noqa: E402
import member  # noqa: E402

DOCS = HERE / "docs"
DATA = DOCS / "data"
URL_ERA = date(2013, 4, 1)


def dump(name, obj):
    p = DATA / name
    p.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
    print(f"  {name:<16} {p.stat().st_size / 1024:8.1f} KB")


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    sfo = SFO()
    nodes = [{"x": x, "r": k.reading, "m": k.marks, "a": k.apoc, "d": k.derived,
              "c": k.primary_from if not k.has_primary else None}
             for x, k in ((x, sfo.keys[x]) for x in sfo.order)]
    edges = [[e.source, e.target, 1 if e.default else 0] for e in sfo.edges]
    dump("sfo.json", {"nodes": nodes, "edges": edges})

    # The member's history over the whole URL era, so any Y's edges can be walked.
    field_end = max(l.split(",", 1)[0] for l in open(member.FIELD) if l[:1].isdigit())
    end = date.fromisoformat(field_end)
    days = [(URL_ERA + timedelta(days=i)).isoformat() for i in range((end - URL_ERA).days + 1)]
    cache = member.ensure(days, member.load_cache())
    dump("relevance.json", {
        "start": days[0], "end": days[-1], "def": member.DEFHASH,
        "rows": [int(cache[d]["rows"]) if d in cache else None for d in days],
        "hits": [int(cache[d]["hits"]) if d in cache else None for d in days],
        "lead": [cache[d].get("lead", "") if d in cache else "" for d in days],
        "entries": member.ENTRIES,
        "counts": [[cache[d]["n"][k] if d in cache else None for d in days]
                   for k in range(len(member.ENTRIES))],
    })
    # Each day's drivers and their passing items, one file per year, read by the page on demand.
    ref = member.reference(cache, 1)
    items = member.load_items()
    by_year = {}
    for d in days:
        if d not in cache:
            continue
        w = member.window(cache, date.fromisoformat(d), 1)
        if w["shares"] is None:
            continue
        keys = member.drove(w, ref)
        if not keys:
            continue
        rows = [[cls, h, title, url, src] for cls, h, title, url, src in member.day_items(d, keys, items)]
        by_year.setdefault(d[:4], {})[d] = {"d": keys, "i": rows}
    (DATA / "items").mkdir(exist_ok=True)
    for y, v in sorted(by_year.items()):
        dump(f"items/{y}.json", v)
    dump("filter.json", {"def": member.GF.definition(), "settings": member.ORDERS["filter"],
                         "classes": [{k: c[k] for k in ("id", "name", "cow", "source", "codes")}
                                     for c in member.GF.CLASSES["classes"]]})
    dump("orders.json", member.ORDERS)

    dst = DOCS / "journal"
    dst.mkdir(exist_ok=True)
    entries = sorted(p.name for p in dst.glob("*.md"))
    dump("journal.json", [n[:-3] for n in reversed(entries)])
    print(f"  field through {field_end}; {len(entries)} journal entries")


if __name__ == "__main__":
    main()
