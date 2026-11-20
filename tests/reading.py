#!/usr/bin/env python3
"""member.py's reading of every micronode the journal walks, as JSON, for tests/fidelity.mjs.

    python3 tests/reading.py [Y ...]        default: the standing instances, 82.80 and 85.32

For each Y, every open edge on the field's last day is walked as the journal walks it, from
its source (or 2013-04-01) to that day at the edge's granule, with every refinement. Each
granule gives its first day, width, percentile, reading and the entries that rose. The day
itself is read as the journal's section 3 reads it.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import member  # noqa: E402
from revott.introspect import introspect  # noqa: E402
from revott.sfo import SFO  # noqa: E402


def flat(nodes, depth=0):
    for w in nodes:
        yield {"start": w["start"].isoformat(), "w": w["width"], "g": w["granule"], "depth": depth,
               "present": w["present"], "pct": w["pct"], "index": w["index"], "rose": w["rose"][:8]}
        yield from flat(w["finer"], depth + 1)


def main():
    ys = [float(a) for a in sys.argv[1:]] or list(member.ORDERS["instances"]) + [82.80, 85.32]
    cache = member.load_cache()
    D = date.fromisoformat(max(cache))
    day_dt = datetime(D.year, D.month, D.day, tzinfo=member.NSUKKA)
    cut = member.ORDERS["relevant_percentile"]
    refs, sfo, walks = {}, SFO(), []
    for y in ys:
        for e in introspect(y, day_dt, "day", 0, sfo)["edges"]:
            start = max(e.start.date(), date(2013, 4, 1))
            g = member.edge_granule((e.end - e.start).total_seconds() / 86400)
            nodes = member.micronodes(cache, start, D, g, cut, refs)
            walks.append({"y": y, "edge": [e.source, e.target], "start": start.isoformat(),
                          "stop": D.isoformat(), "g": g, "nodes": list(flat(nodes))})
    day = member.judge(member.window(cache, D, 1), refs.setdefault(1, member.reference(cache, 1)), cut)
    json.dump({"def": member.DEFHASH, "cut": cut, "walks": walks,
               "day": {"start": D.isoformat(), "pct": day["pct"], "index": day["index"], "rose": day["rose"]}},
              sys.stdout)


if __name__ == "__main__":
    main()
