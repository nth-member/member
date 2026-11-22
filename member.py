#!/usr/bin/env python3
"""The nth member: REVOTT's numerator, keeping its own journal.

    python3 member.py [DAY]        default: the last day in the field

Run after every refresh (REVOTT's refresh.sh does, then build.py). Unprompted,
it writes one journal entry for the day, docs/journal/DAY.md, holding:

  1. where each standing instance's SFO is -- the open edges and how far along,
     the layered reading of their ends, what fires inside the day, the day's
     line through the 550 x 550 grid, and the eigen curiosity beside them
     (revott.introspect)
  2. the micronodes along every open edge: the trajectory walked in granules
     from the edge's source to today, each granule judged against the member's
     own history, and those deemed relevant refined to finer granules down to
     the day -- the adjustable granule of algorithmic introspection
  3. what the field carried that day, read against the relevance the member
     has been given in member.json -- never against all of GDELT, most of which
     has no bearing on the Revelation of the Trial
  4. what is coming: every firing within the horizon, and those close enough
     to announce now, before the field has seen them
  5. the granule it should be read at next, and whether the data can resolve it

It reports percentiles against the member's own history, never p-values. NULL
days read as NULL. The corpus is streamed through `unzip -p`, never extracted.
The relevance terms are the author's, in member.json; the entry names the
definition it read the field with.
"""
from __future__ import annotations

import csv
from bisect import bisect_left, bisect_right
import hashlib
import json
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import os

HERE = Path(__file__).resolve().parent
REVOTT = Path(os.environ.get("REVOTT", Path.home() / "revott"))
sys.path.insert(0, str(REVOTT))
from revott.core import NSUKKA  # noqa: E402
from revott.introspect import introspect, render  # noqa: E402
from revott.sfo import SFO  # noqa: E402
sys.path.insert(0, str(HERE / "filter"))
import geofilter as GF  # noqa: E402

CORPUS = Path(os.environ.get("CORPUS", Path.home() / "gdelt_raw_1979_2026")) / "files"
FIELD = REVOTT / "gdelt" / "gdelt_daily_1979_2026.csv"
CACHE = HERE / "cache" / "relevance_daily.csv"
ITEMS = HERE / "cache" / "items_daily.jsonl"     # each day's most-carried passing events, for the journal and the page
STAMPS_DAYS = Path(os.environ.get("REVOTT_STAMPS", Path.home() / "revott-stamps")) / "docs" / "data" / "days"
FEED_ERA = date(2026, 9, 28)                      # the feed archive's first day (05:32 Nsukka)
JOURNAL = HERE / "docs" / "journal"
ORDERS = json.loads((HERE / "member.json").read_text())
REL = ORDERS["relevance"]
# Each entry is one of the author's Fulfilment IDs with its words, and each word stands in one
# entry. Words are matched literally, as whole words, ignoring case. Where words overlap, the
# longest wins, so "Guinea-Bissau" counts for Guinea-Bissau and not for Guinea.
ENTRIES = list(REL["terms"])
WORD = {w.lower(): k for k, e in enumerate(ENTRIES) for w in REL["terms"][e].split("|")}
PATTERN = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(WORD, key=len, reverse=True))
                     + r")\b", re.I)
# Each entry's weight in a granule's reading: 1 unless member.json's relevance.weights sets it.
# Weights act on the counts, so changing them needs no rebuild of the cache.
WEIGHTS = [float(REL.get("weights", {}).get(e, 1)) for e in ENTRIES]
# The geopolitical filter (filter/): an event counts only if it passes. Its definition is part of the
# cache's, so a change to the classes or to member.json's "filter" rebuilds the cache.
FILTER = GF.load()
DEFHASH = hashlib.sha1((json.dumps(REL["terms"], sort_keys=True) + "v4" + GF.definition()).encode()).hexdigest()[:10]
KEEP = 60                                         # passing events kept per day, by articles


def entry_of(text: str) -> int:
    """The entry a matched word belongs to."""
    k = WORD.get(text.lower())
    if k is None:   # a letter whose lower case differs from the pattern's case folding
        k = next(WORD[w] for w in WORD if re.fullmatch(re.escape(w), text, re.I))
    return k


def label(k: int) -> str:
    """An entry as the journal names it: its first word and its ID's number."""
    e = ENTRIES[k]
    return f"{REL['terms'][e].split('|')[0]} [{e.removeprefix('Fulfilment')}]"


def read_day(day: str):
    """Stream one daily archive: rows, rows any entry matched, those that also pass the geopolitical
    filter, those of them in material conflict, the day's most-carried passing events, and the passing
    events each entry matched. None if there is no archive. An event counts once for every entry whose
    words it carries, and only if it passes: its article's address reaches theta, its CAMEO code's class
    is among the chosen ones, and so on (filter/geofilter.py)."""
    f = CORPUS / f"{day.replace('-', '')}.export.CSV.zip"
    if not f.exists():
        return None
    rows = matched = hits = hits4 = 0
    counts = [0] * len(ENTRIES)
    best = {}       # article address -> its most-carried passing event
    memo = {}       # a field's entries, read once per distinct value; no word spans a tab, so the
                    # union over the five fields is what the joined fields would give
    umemo, cmemo, pmemo = {}, {}, {}

    def entries_in(field):
        r = memo.get(field)
        if r is None:
            r = memo[field] = frozenset(entry_of(m.group(1)) for m in PATTERN.finditer(field))
        return r
    p = subprocess.Popen(["unzip", "-p", str(f)], stdout=subprocess.PIPE,
                         text=True, errors="replace")
    for line in p.stdout:
        c = line.rstrip("\n").split("\t")
        if len(c) < 57:
            continue
        rows += 1
        found = (entries_in(c[6]) | entries_in(c[16]) | entries_in(c[36]) | entries_in(c[43])
                 | entries_in(c[50]))
        if not found:
            continue
        matched += 1
        url = c[57] if len(c) > 57 else ""
        ok = umemo.get(url)
        if ok is None:
            ok = umemo[url] = FILTER.url_ok(url)
        if not ok:
            continue
        ch = cmemo.get(c[26])
        if ch is None:
            ch = cmemo[c[26]] = FILTER.cameo_class(c[26])
        if not FILTER.class_ok(*ch):
            continue
        if FILTER.pair_gate:
            pr = pmemo.get(found)
            if pr is None:
                pr = pmemo[found] = FILTER.relevant_pair([ENTRIES[k] for k in found])
            if not pr:
                continue
        hits += 1
        for k in found:
            counts[k] += 1
        if c[29] == "4":
            hits4 += 1
        n = int(c[33] or 0)
        b = best.get(url)
        if b is None or n > b[0]:
            best[url] = (n, c[28], c[26], ch[0], ch[1], c[6], c[16], c[50], url, sorted(found))
    p.wait()
    top = sorted(best.values(), key=lambda t: (-t[0], t[8]))[:KEEP]
    return day, rows, matched, hits, hits4, top, counts


def load_cache():
    out = {}
    if CACHE.exists():
        for r in csv.DictReader(open(CACHE)):
            if r["def"] == DEFHASH:
                r["n"] = [int(v) for v in r["counts"].split()]
                out[r["date"]] = r
    return out


def load_items() -> dict:
    """Each day's most-carried passing events: [articles, root, code, class, hostility, actor 1, actor 2,
    place, address, entries]."""
    out = {}
    if ITEMS.exists():
        for line in open(ITEMS):
            r = json.loads(line)
            if r["def"] == DEFHASH:
                out[r["date"]] = r["items"]
    return out


def lead_of(t) -> str:
    n, root, code, cls, h, a1, a2, place, url, _ = t
    return f"{n} art · {cls}{'' if h is None else ' ' + str(h)} · root {root} · {a1 or '—'} / {a2 or '—'} · {place or '—'}"


def ensure(days, cache):
    need = [d for d in days if d not in cache]
    if not need:
        return cache
    print(f"  reading {len(need)} days against the relevance terms and the geopolitical filter …", file=sys.stderr)
    items = load_items()
    with ProcessPoolExecutor(max_workers=14) as ex:
        for res in ex.map(read_day, need):
            if res is None:
                continue
            d, rows, matched, hits, hits4, top, counts = res
            cache[d] = dict(date=d, rows=rows, matched=matched, hits=hits, hits4=hits4,
                            lead=lead_of(top[0]) if top else "",
                            counts=" ".join(map(str, counts)), n=counts, **{"def": DEFHASH})
            items[d] = [list(t) for t in top]
    with open(CACHE, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["date", "rows", "matched", "hits", "hits4", "lead", "counts", "def"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(cache[d] for d in sorted(cache))
    with open(ITEMS, "w") as fh:
        for d in sorted(items):
            if d in cache:
                fh.write(json.dumps({"date": d, "def": DEFHASH, "items": items[d]}, ensure_ascii=False) + "\n")
    return cache


def pct(history, v):
    """Percentile of v within the member's own history: share of days at or below."""
    h = sorted(history)
    return 100.0 * sum(1 for x in h if x <= v) / len(h) if h else float("nan")


GRAN = {"day": 1, "week": 7, "month": 30}
FINER = {"month": "week", "week": "day"}


def edge_granule(span_days: float) -> str:
    """The starting granule for an edge, by its length; adjustable in member.json."""
    for g, limit in ORDERS["granule_by_span_days"]:
        if span_days <= limit:
            return g
    return ORDERS["granule_by_span_days"][-1][0]


def window(cache, d0: date, width: int):
    """One granule: its days, NULL days, the share any entry matched, and each entry's share."""
    days = [(d0 + timedelta(days=i)).isoformat() for i in range(width)]
    got = [cache[d] for d in days if d in cache]
    rows = sum(int(c["rows"]) for c in got)
    hits = sum(int(c["hits"]) for c in got)
    n = [0] * len(ENTRIES)
    for c in got:
        for k, v in enumerate(c["n"]):
            n[k] += v
    return dict(start=d0, width=width, present=len(got), null=width - len(got),
                share=(hits / rows if rows else None), hits=hits, n=n,
                shares=([v / rows for v in n] if rows else None))


def rank(ref, v):
    """Percentile rank of v in a sorted history: the share of it below v, ties counting half.
    An entry at its usual zero reads 50, not 100; it rises only above its usual level."""
    return 100.0 * (bisect_left(ref, v) + bisect_right(ref, v)) / (2 * len(ref)) if ref else float("nan")


def read(ref, w):
    """Each entry's percentile in its own history of granules this size, and the granule's
    reading: the share of its events above the entries' usual levels, i.e. each entry's excess
    over its own median share, weighted and summed in entry order. An entry below its usual level
    adds nothing, so a granule whose events concentrate on a few entries reads high instead of
    being outvoted by the entries it crowds out."""
    p = [rank(ref[0][k], s) for k, s in enumerate(w["shares"])]
    t = 0.0
    for k, s in enumerate(w["shares"]):
        e = ref[0][k]
        m = (e[(len(e) - 1) // 2] + e[len(e) // 2]) / 2 if e else 0.0
        t += WEIGHTS[k] * max(0.0, s - m)
    return p, t


def reference(cache, width: int):
    """The member's own history at this granule, from every non-overlapping window: each
    entry's shares, sorted, and the windows' own readings, sorted."""
    ds = sorted(cache)
    if not ds:
        return [[] for _ in ENTRIES], []
    d0, end = date.fromisoformat(ds[0]), date.fromisoformat(ds[-1])
    wins = []
    while d0 + timedelta(days=width - 1) <= end:
        w = window(cache, d0, width)
        if w["share"] is not None and w["present"] >= max(1, width // 2):
            wins.append(w)
        d0 += timedelta(days=width)
    E = [sorted(w["shares"][k] for w in wins) for k in range(len(ENTRIES))]
    return E, sorted(read((E, None), w)[1] for w in wins)


def judge(w, ref, cut):
    """Place a granule in the member's history: its reading's percentile, and the entries
    at or above the cut in their own history, highest first."""
    if w["shares"] is None:
        w.update(pct=None, rose=[], p=None, index=None)
        return w
    p, index = read(ref, w)
    w.update(p=p, index=index, pct=rank(ref[1], index),
             rose=sorted((k for k in range(len(p)) if p[k] >= cut), key=lambda k: (-p[k], -w["n"][k])))
    return w


def rose(w, n=5):
    return ", ".join(f"{label(k)} p{w['p'][k]:.0f}" for k in w["rose"][:n]) or "no entry at the cut"


def drove(w, ref, n=3) -> list[int]:
    """The entries that drove a granule's reading: the largest terms of its sum, each entry's weighted
    excess over its own median share."""
    terms = []
    for k, s in enumerate(w["shares"]):
        e = ref[0][k]
        m = (e[(len(e) - 1) // 2] + e[len(e) // 2]) / 2 if e else 0.0
        c = WEIGHTS[k] * max(0.0, s - m)
        if c > 0:
            terms.append((c, k))
    terms.sort(key=lambda t: (-t[0], t[1]))
    return [k for _, k in terms[:n]]


_FEEDS = {}


def feed_items(day: str) -> list[tuple]:
    """The feed archive's headlines for a Nsukka day that pass the filter: (ms, source, headline, link,
    class, hostility, entries named)."""
    if day not in _FEEDS:
        out, seen = [], set()
        f = STAMPS_DAYS / f"{day}.json"
        for it in (json.load(open(f)) if f.exists() else []):
            if it[1] != "f" or not it[3] or it[4] in seen:
                continue
            seen.add(it[4])
            r = FILTER.read(it[3])
            if r["pass"]:
                out.append((it[0], it[2], it[3], it[4], r["class"], r["h"], r["entries"]))
        _FEEDS[day] = out
    return _FEEDS[day]


def day_items(day: str, keys: list[int], items: dict, n: int = 3) -> list[tuple]:
    """The passing items of the entries that drove a day's reading: on days the feed archive covers, its
    headlines naming them, in the order of the entries; else GDELT's most-carried passing events
    carrying them, one per story. Each is (class, hostility, headline, link, what carried it)."""
    ids = [ENTRIES[k] for k in keys]
    if date.fromisoformat(day) >= FEED_ERA:
        fs = [x for x in feed_items(day) if set(x[6]) & set(ids)]
        fs.sort(key=lambda x: (min(ids.index(e) for e in x[6] if e in ids), x[0]))
        if fs:
            return [(cls, h, title, url, src) for _ms, src, title, url, cls, h, _e in fs[:n]]
    out, seen = [], set()
    for t in items.get(day, []):
        if set(t[9]) & set(keys):
            title = " ".join(GF.url_tokens(t[8])) or t[8]
            if title in seen:
                continue
            seen.add(title)
            out.append((t[3], t[4], title, t[8], f"{t[0]} art"))
            if len(out) == n:
                break
    return out


def item_lines(cache, dw, refs, items, pad: str) -> list[str]:
    keys = drove(dw, refs[1] if 1 in refs else refs.setdefault(1, reference(cache, 1)))
    if not keys:
        return []
    out = [f"{pad}- drove it: " + ", ".join(label(k) for k in keys)]
    for cls, h, title, url, src in day_items(dw["start"].isoformat(), keys, items):
        tag = cls + ("" if h is None else f" {h}")
        title = title.replace("[", "(").replace("]", ")")
        out.append(f"{pad}- **{tag}** · {title} — {src} · [link]({url})")
    return out


def micronodes(cache, start: date, stop: date, g: str, cut: float, refs, depth=0):
    """Walk [start, stop] in granules of g; judge each; refine those deemed relevant."""
    width = GRAN[g]
    ref = refs[width] if width in refs else refs.setdefault(width, reference(cache, width))
    out, d0 = [], start
    while d0 <= stop:
        w = judge(window(cache, d0, min(width, (stop - d0).days + 1)), ref, cut)
        w["granule"] = g
        w["relevant"] = w["pct"] is not None and w["pct"] >= cut
        w["finer"] = (micronodes(cache, d0, d0 + timedelta(days=w["width"] - 1),
                                 FINER[g], cut, refs, depth + 1)
                      if w["relevant"] and g in FINER else [])
        out.append(w)
        d0 += timedelta(days=width)
    return out


def relevant_days(nodes):
    """The day-level micronodes reached by refinement, deemed relevant."""
    out = []
    for w in nodes:
        if w["granule"] == "day" and w["relevant"]:
            out.append(w)
        out += relevant_days(w["finer"])
    return out


def edge_micronode_lines(cache, e, day: date, refs, items) -> list[str]:
    start = max(e.start.date(), date(2013, 4, 1))
    span = (e.end - e.start).total_seconds() / 86400
    g = edge_granule(span)
    cut = ORDERS["relevant_percentile"]
    nodes = micronodes(cache, start, day, g, cut, refs)
    judged = [w for w in nodes if w["pct"] is not None]
    nulls = sum(w["null"] for w in nodes)
    kind = "backbone" if e.backbone else "long-range"
    L = [f"**{kind} {e.source:g} → {e.target:g}** · {e.progress:.1%} along · granule **{g}** · "
         f"{len(nodes)} micronodes walked from {start}, {nulls} NULL days among them"]
    if e.start.date() < date(2013, 4, 1):
        L.append(f"  - the edge opened {e.start:%Y-%m-%d}; micronodes before 2013-04-01 are not "
                 "walked yet (the pre-2013 archives are yearly and monthly)")
    if judged:
        third = max(1, len(judged) // 3)
        med = lambda ws: sorted(w["pct"] for w in ws)[len(ws) // 2]
        L.append(f"  - relevance along the trajectory: median percentile {med(judged[:third]):.0f} "
                 f"in the first third, {med(judged[-third:]):.0f} in the last third")
        today = judged[-1]
        L.append(f"  - the current micronode ({today['granule']} from {today['start']}): "
                 f"percentile {today['pct']:.0f}")
    rel = [w for w in nodes if w["relevant"]]
    L.append(f"  - deemed relevant (percentile ≥ {cut:g}): {len(rel)} of {len(judged)} {g}s")
    for w in sorted(rel, key=lambda w: -w["pct"])[:6]:
        L.append(f"    - {g} from {w['start']}: percentile {w['pct']:.0f} — rose: {rose(w)}")
        for dd in sorted(relevant_days([w]) if g != "day" else [], key=lambda d: -d["pct"])[:3]:
            L.append(f"      - day {dd['start']}: percentile {dd['pct']:.0f} — rose: {rose(dd, 3)}")
            L.extend(item_lines(cache, dd, refs, items, "        "))
        if g == "day":
            L.extend(item_lines(cache, w, refs, items, "      "))
    return L


def granule_advice(ahead, day_dt):
    if not ahead:
        return "day — nothing of this SFO within the horizon"
    x, when = ahead[0]
    left = (when - day_dt).total_seconds() / 86400
    if left <= 7:
        return (f"hour — X = {x:g} fires in {left:.1f} days. GDELT 1.0 resolves only to the day; "
                "an hourly granule needs GDELT 2.0's 15-minute feed, which is not on disk.")
    if left <= 30:
        return f"day, tightening — X = {x:g} fires in {left:.0f} days"
    return f"day — the next key of this SFO, X = {x:g}, is {left:.0f} days off"


def main():
    field = {r["date"]: r for r in csv.DictReader(open(FIELD))}
    day = sys.argv[1] if len(sys.argv) > 1 else max(field)
    D = date.fromisoformat(day)
    day_dt = datetime(D.year, D.month, D.day, tzinfo=NSUKKA)   # the day, from Nsukka's midnight
    base_days = [(D - timedelta(days=i)).isoformat() for i in range(ORDERS["baseline_days"], -1, -1)]
    base_days = [d for d in base_days if d >= "2013-04-01"]

    sfo = SFO()
    # The micronodes walk every open edge from its source, so the member's
    # history must reach back to the earliest open edge (within the URL era).
    earliest = D
    for y in ORDERS["instances"]:
        for e in introspect(y, day_dt, "day", 0, sfo)["edges"]:
            earliest = min(earliest, max(e.start.date(), date(2013, 4, 1)))
    span_days = [(earliest + timedelta(days=i)).isoformat()
                 for i in range((D - earliest).days + 1)]
    cache = ensure(sorted(set(base_days) | set(span_days)), load_cache())
    items = load_items()
    fs = ORDERS["filter"]
    lines = [f"# {day} — the member's entry", ""]
    lines.append(f"*Written {datetime.now(NSUKKA):%Y-%m-%d %H:%M} Nsukka, unprompted, after the refresh. "
                 f"Relevance definition `{DEFHASH}` — {REL['_status']} Geopolitical filter `{GF.definition()}`: "
                 f"theta {fs['theta']}, {len(fs['classes'])} classes, hostility at least {fs['min_hostility']}, "
                 f"pair gate {'on' if fs['pair_gate'] else 'off'}, {'learned from the author' + chr(39) + 's marks' if fs['marks'] == 'learned' else 'the classes' + chr(39) + ' words only'}.*")
    lines.append("")

    # 1. where each instance is
    lines.append("## 1. Where REVOTT is")
    announcements = []
    for y in ORDERS["instances"]:
        r = introspect(y, day_dt, "day", ORDERS["horizon_days"], sfo)
        lines.append("")
        lines.append(render(r, markdown=True))
        for x, when in r["ahead"]:
            if (when - day_dt).days <= ORDERS["announce_within_days"]:
                announcements.append(f"- **Y = {y:g}: X = {x:g} fires {when:%Y-%m-%d %H:%M} Nsukka** — "
                                     f"{sfo.keys[x].reading}")
        for x, when in r["eigen_ahead"]:
            if (when - day_dt).days <= ORDERS["announce_within_days"]:
                announcements.append(f"- eigen crosses {x:g} on {when:%Y-%m-%d %H:%M} Nsukka — "
                                     f"{sfo.keys[x].reading} *(a curiosity)*")
        lines.append("")
        lines.append(f"**Granule for the next reading:** {granule_advice(r['ahead'], day_dt)}")

    # 2. the micronodes
    lines.append("")
    lines.append("## 2. Micronodes along the open edges")
    lines.append("")
    lines.append("*A micronode is a granule of the trajectory deemed relevant to it. Each open edge is "
                 "walked from its source to today at a granule set by its length; each granule is judged "
                 "against the member's own history of granules that size; those deemed relevant are "
                 "refined to finer granules, down to the day GDELT 1.0 can resolve.*")
    refs = {}
    for y in ORDERS["instances"]:
        r = introspect(y, day_dt, "day", 0, sfo)
        lines.append("")
        lines.append(f"### Y = {y:g}")
        walked = {}
        for e in r["edges"]:
            lines.append("")
            # Edges from one source over the same span walk the same micronodes;
            # say so rather than repeat them.
            key = (e.source, edge_granule((e.end - e.start).total_seconds() / 86400))
            if key in walked:
                kind = "backbone" if e.backbone else "long-range"
                lines.append(f"**{kind} {e.source:g} → {e.target:g}** · {e.progress:.1%} along · "
                             f"the same micronodes as {e.source:g} → {walked[key]:g} above; "
                             f"it differs only in its end: {sfo.keys[e.target].reading}")
                continue
            walked[key] = e.target
            lines.extend(edge_micronode_lines(cache, e, D, refs, items))

    # 3. the field
    lines.append("")
    lines.append("## 3. What the field carried")
    f = field.get(day)
    if f is None or f["present"] != "1":
        lines.append(f"- {day}: **NULL** — GDELT published no archive. Not a quiet day; not zero.")
    else:
        today = read_day(day)
        _, rows, matched, hits, hits4, top, _counts = today
        cut = ORDERS["relevant_percentile"]
        dw = judge(window(cache, D, 1), refs.setdefault(1, reference(cache, 1)), cut)
        hist4 = [int(c["hits4"]) / max(1, int(c["hits"])) for d, c in cache.items()
                 if d < day and int(c["hits"]) > 0]
        share = hits / rows if rows else 0
        share4 = hits4 / hits if hits else 0
        z = f["z"] or "—"
        lines.append(f"- All of GDELT: {int(f['n_events']):,} events, z = {z} "
                     "(z is provisional this close to the end of the series).")
        lines.append(f"- Matched by any entry: {matched:,} events = {matched / rows:.2%} of the day.")
        lines.append(f"- Passing the geopolitical filter as well: {hits:,} events = {share:.2%} of the day, "
                     f"{hits / matched if matched else 0:.1%} of those matched. Only these are counted below.")
        lines.append(f"- **The day's reading** — the sum of the {len(ENTRIES)} entries' shares above their own "
                     f"median day (an event matching several entries counts for each) — is {dw['index']:.2%}: "
                     f"percentile **{dw['pct']:.0f}** "
                     "among the member's days.")
        lines.append(f"- **Entries that rose** (at or above the {cut:g}th percentile of their own history): "
                     + (", ".join(f"{label(k)} {dw['n'][k]:,} events, p{dw['p'][k]:.0f}" for k in dw["rose"][:12])
                        or "none") + (f"; {len(dw['rose']) - 12} more" if len(dw["rose"]) > 12 else "") + ".")
        lines.append(f"- Of the passing events, material conflict (CAMEO roots 15–20): {hits4:,} = {share4:.1%} — "
                     f"percentile **{pct(hist4, share4):.0f}**.")
        lines.append("")
        lines.append("Most-carried passing events:")
        lines.append("")
        lines.append("| articles | class | root | code | actor 1 | actor 2 | place | source |")
        lines.append("|---:|---|---|---|---|---|---|---|")
        for n, root, code, cls, h, a1, a2, place, url, _found in top[:12]:
            src = f"[link]({url})" if url.startswith("http") else ""
            lines.append(f"| {n} | {cls}{'' if h is None else ' ' + str(h)} | {root} | {code} | {a1} | {a2} | {place} | {src} |")

    # 4. announcements
    lines.append("")
    lines.append("## 4. Announced before the field has seen them")
    lines.extend(announcements or ["- nothing within "
                                   f"{ORDERS['announce_within_days']} days"])

    # 5. what the member cannot yet do
    lines.append("")
    lines.append("## 5. Standing limits")
    lines.append("- The field is read only for the author's relevance terms in `member.json`; everything else in GDELT is left unread.")
    lines.append("- Only events passing the geopolitical filter are counted (`filter/classes.json`; settings in `member.json`'s filter). "
                 "A GDELT event is read through the words of its article's address and classed by its CAMEO code.")
    lines.append("- Percentiles are against the member's own history; they are readings, not significance.")
    lines.append("- GDELT 1.0 floors the granule at one day; micronodes below a day need GDELT 2.0's 15-minute feed.")
    lines.append("- Micronodes before 2013-04-01 are not yet walked.")

    JOURNAL.mkdir(exist_ok=True)
    out = JOURNAL / f"{day}.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"  journal: {out}")
    for a in announcements:
        print("  " + a.lstrip("- "))


if __name__ == "__main__":
    main()
