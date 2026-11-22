#!/usr/bin/env python3
"""filter/geofilter.py's reading of every headline in the feed archive, as JSON, for tests/geofilter_fidelity.mjs.

    python3 tests/geofilter_ref.py            reads ~/revott-stamps/docs/data/days/*.json

Four readings: the seed with member.json's settings; then, on every fifth headline, a learned model
(from marks made here by a fixed rule, so the arithmetic of marks is exercised), the pair gate with
min_hostility 4, and a narrower set of classes with theta 3/5.
"""
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "filter"))
import geofilter as gf  # noqa: E402

DAYS = Path.home() / "revott-stamps" / "docs" / "data" / "days"


def main():
    seen, items = set(), []
    for f in sorted(glob.glob(str(DAYS / "*.json"))):
        for it in json.load(open(f)):
            if it[1] == "f" and it[3] and it[3] not in seen:
                seen.add(it[3])
                items.append(it[3])
    base = gf.load()
    # marks by a fixed rule: every 7th headline the seed passes is marked pass with its class, every
    # 11th it drops is marked drop
    marks = []
    for i, t in enumerate(items):
        r = base.read(t)
        if r["pass"] and i % 7 == 0:
            marks.append({"text": t, "mark": "pass", "class": r["class"]})
        elif not r["pass"] and i % 11 == 0:
            marks.append({"text": t, "mark": "drop"})
    model = gf.build_model(marks)
    s = dict(base.settings)
    variants = [("seed", s, None),
                ("learned", s, model),
                ("pair4", {**s, "pair_gate": True, "min_hostility": 4}, None),
                ("narrow", {**s, "classes": ["war", "dispute", "territory", "religion"], "theta": "3/5"}, model)]
    out = {"items": items, "marks": marks, "variants": []}
    for name, settings, m in variants:
        f = gf.Filter(settings, m)
        rows = []
        for i, t in enumerate(items):
            if name != "seed" and i % 5:
                continue
            r = f.read(t)
            g = r["g"]
            rows.append([i, r["pass"], f"{g.numerator}/{g.denominator}", r["class"], r["h"], r["seed"], r["entries"],
                         r["pair"], r["terms"]])
        out["variants"].append({"name": name, "settings": settings, "model": m is not None, "rows": rows})
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
