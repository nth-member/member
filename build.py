#!/usr/bin/env python3
"""Build the member's site from the SFO, the member's history and its journal.

    python3 build.py              REVOTT defaults to ~/revott

Writes, under docs/:

    data/sfo.json         REVOTT's 400 keys read in layers, and its 704 edges
    data/relevance.json   one entry per day of the URL era: the day's rows, the rows
                          relevant to the member's terms, and the day's leading
                          relevant event -- NULL where GDELT published no archive
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
    })
    dump("orders.json", member.ORDERS)

    dst = DOCS / "journal"
    dst.mkdir(exist_ok=True)
    entries = sorted(p.name for p in dst.glob("*.md"))
    dump("journal.json", [n[:-3] for n in reversed(entries)])
    print(f"  field through {field_end}; {len(entries)} journal entries")


if __name__ == "__main__":
    main()
