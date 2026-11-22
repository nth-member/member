#!/usr/bin/env python3
"""Carry the author's marks from the Geofilter Marking Desk into the filter's learned counts.

    python3 filter/sync_marks.py DIR      DIR holds the desk's "marks" documents, one JSON file each
                                          (as Claude saves them from the page's private store)

Writes, outside every repository (the marks are the author's own, kept off the public sites):

    ~/geofilter-marks/marks.jsonl   every mark, oldest first: text, link, mark, class, when, where from
    ~/geofilter-marks/model.json    the counts built from them (geofilter.build_model)

The published runs use model.json only when member.json's filter.marks is "learned".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geofilter  # noqa: E402

OUT = Path.home() / "geofilter-marks"


def main():
    src = Path(sys.argv[1])
    marks = []
    for f in sorted(src.rglob("*.json")):
        d = json.loads(f.read_text())
        d = d.get("data", d) if isinstance(d, dict) else d
        if isinstance(d, dict) and d.get("mark") in ("pass", "drop") and d.get("text"):
            marks.append({k: d.get(k) for k in ("id", "text", "url", "source", "day", "origin", "kind", "mark", "class", "at", "seed")})
    marks.sort(key=lambda m: (m.get("at") or "", m.get("id") or ""))
    OUT.mkdir(exist_ok=True)
    (OUT / "marks.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in marks))
    model = geofilter.build_model(marks)
    (OUT / "model.json").write_text(json.dumps(model, ensure_ascii=False) + "\n")
    p = sum(1 for m in marks if m["mark"] == "pass")
    print(f"{len(marks)} marks ({p} pass, {len(marks) - p} drop) -> {OUT / 'marks.jsonl'}; counts for "
          f"{len(set(model['p']) | set(model['d']))} words -> {OUT / 'model.json'}")


if __name__ == "__main__":
    main()
