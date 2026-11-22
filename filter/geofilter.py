#!/usr/bin/env python3
"""The member's geopolitical filter: does an item carry geopolitical weight, and of which class?

    python3 filter/geofilter.py entries          map the relevance entries to COW states (filter/cow/entries.json)
    python3 filter/geofilter.py model MARKS OUT  rebuild the learned counts from a marks file (JSON lines)
    python3 filter/geofilter.py test "headline"  read one headline

An item is a headline, or a GDELT event read through the words of its article's address. For each item i:

    s(i)  the seed: 1 if i names one of the author's relevance entries and carries a word of any class
          (filter/classes.json), or carries a word of a class that needs no entry (needs_entry false: AI and
          computing), else 0. A GDELT event already carries an entry, through its own fields.
    O(i)  its odds: seed_odds ** (2 s(i) - 1) times, for every distinct word w of i that the marks have
          counted, ((p_w + 1) / (P + 2)) / ((d_w + 1) / (D + 2)): p_w and d_w count the author's pass and
          drop marks on items carrying w, P and D all the pass and drop marks (naive Bayes on the words
          present, add-one smoothed). Without marks O(i) is 4 or 1/4.
    G(i)  = O(i) / (1 + O(i)), the item's weight. Every factor is a ratio of integers, so G is computed
          exactly (fractions here, BigInt in geofilter.js) and both give the same answer to the last digit.
    k(i)  its class: the class with the most evidence, class_seed_count for each of its terms the item
          carries plus the author's class tags on marked items carrying the same words; ties go by the
          order in classes.json's precedence. A GDELT event takes its class from its CAMEO code instead.
    h(i)  for war and disputes, the highest MID hostility level among the class's terms it carries (a
          GDELT event: its CAMEO code's level).

i passes when G(i) >= theta, k(i) is among the chosen classes, h(i) >= min_hostility for war and
disputes, and, if pair_gate is set, the item is politically relevant: it names a COW major power, or two
states contiguous by land or up to 150 miles of sea. The settings are member.json's "filter".

A mark only adds counts, so the learned part is rebuilt from the marks alone (`model`). Whether the
published runs use it is member.json's filter.marks: "seed" (the classes' words only) or "learned".
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEMBER = HERE.parent
CLASSES = json.loads((HERE / "classes.json").read_text())


def tokens(text: str) -> list[str]:
    """Lower case, accents removed (every mark, Unicode category M, after NFKD), split on anything but
    letters, digits and apostrophes, and a possessive 's dropped; geofilter.js does the same."""
    t = unicodedata.normalize("NFKD", text.replace("’", "'").replace("‘", "'").lower())
    t = "".join(ch for ch in t if unicodedata.category(ch)[0] != "M")
    out = []
    for w in re.split(r"[^a-z0-9']+", t):
        w = w.strip("'")
        if w.endswith("'s"):          # the possessive: "Russia's" reads as "russia"
            w = w[:-2]
        if w:
            out.append(w)
    return out


GENERIC = {"www", "com", "org", "net", "html", "htm", "php", "aspx", "asp", "index", "amp"}


def url_tokens(url: str) -> list[str]:
    """The words of an article's address: its path, without the host, the query or the file endings."""
    path = re.sub(r"^[a-z]+://[^/]*", "", url.lower())
    path = re.sub(r"[?#].*$", "", path)
    return [w for w in tokens(path.replace("'", " ")) if not w.isdigit() and w not in GENERIC and len(w) > 1]


def _phrase(form: str) -> tuple[str, ...]:
    return tuple(tokens(form))


class Filter:
    def __init__(self, settings: dict | None = None, model: dict | None = None, entries: dict | None = None):
        orders = json.loads((MEMBER / "member.json").read_text())
        self.settings = dict(settings if settings is not None else orders["filter"])
        self.theta = Fraction(str(self.settings["theta"]))
        self.chosen = set(self.settings["classes"])
        self.min_h = int(self.settings["min_hostility"])
        self.pair_gate = bool(self.settings["pair_gate"])
        self.order = CLASSES["precedence"]
        self.odds = Fraction(CLASSES["seed_odds"])
        self.pi = int(CLASSES["class_seed_count"])
        # every phrase (class terms, the terms they need, the entries' words) gets an id; an index by
        # first word finds them in one pass over an item's words
        self.phrases, self._ids, self.first = [], {}, {}
        def pid(form):
            ph = _phrase(form)
            if ph not in self._ids:
                self._ids[ph] = len(self.phrases)
                self.phrases.append(ph)
                if ph:
                    self.first.setdefault(ph[0], []).append(self._ids[ph])
            return self._ids[ph]
        self.terms = []
        for c in CLASSES["classes"]:
            for t in c["terms"]:
                self.terms.append((c["id"], [pid(f) for f in t["forms"]], t.get("h"), [pid(f) for f in t.get("needs", [])]))
        self.cameo = [(p, cls, h) for p, cls, h in CLASSES["cameo"]]
        self.free = {c["id"] for c in CLASSES["classes"] if c.get("needs_entry") is False}   # pass without an entry
        # the author's relevance entries, longest phrase first
        terms = orders["relevance"]["terms"]
        self.entry_phrases = sorted(((pid(w), e) for e, v in terms.items() for w in v.split("|")),
                                    key=lambda t: (-len(self.phrases[t[0]]), self.phrases[t[0]]))
        self.entries = entries if entries is not None else json.loads((HERE / "cow" / "entries.json").read_text())
        gates = json.loads((HERE / "cow" / "gates.json").read_text())
        self.majors = set(gates["majors"])
        self.contig = {tuple(p) for p in gates["contiguous"]}
        self.model = model or {"p": {}, "d": {}, "tags": {}}

    # ---- the parts ----
    def occurrences(self, toks: list[str]) -> dict[int, list[int]]:
        """Every phrase the item carries: phrase id -> its start positions, in order."""
        occ = {}
        for i, w in enumerate(toks):
            for k in self.first.get(w, ()):
                ph = self.phrases[k]
                if tuple(toks[i:i + len(ph)]) == ph:
                    occ.setdefault(k, []).append(i)
        return occ

    def named_entries(self, toks: list[str], occ: dict[int, list[int]] | None = None) -> list[str]:
        """The relevance entries an item names, longest phrase first, each where no longer one covers it."""
        occ = self.occurrences(toks) if occ is None else occ
        used, found = [False] * len(toks), []
        for k, e in self.entry_phrases:
            n = len(self.phrases[k])
            for i in occ.get(k, ()):
                if not any(used[i:i + n]):
                    for j in range(i, i + n):
                        used[j] = True
                    if e not in found:
                        found.append(e)
        return found

    def matched_terms(self, toks: list[str], occ: dict[int, list[int]] | None = None) -> list[tuple[str, int | None]]:
        """Every class term the item carries: (class, hostility level)."""
        occ = self.occurrences(toks) if occ is None else occ
        return [(cls, h) for cls, forms, h, needs in self.terms
                if any(f in occ for f in forms) and (not needs or any(f in occ for f in needs))]

    def relevant_pair(self, entries: list[str]) -> bool:
        states = sorted({c for e in entries for c in self.entries.get(e, [])})
        if any(c in self.majors for c in states):
            return True
        return any((a, b) in self.contig for i, a in enumerate(states) for b in states[i + 1:])

    def url_ok(self, url: str) -> bool:
        """For a GDELT event, whose own fields already carry an entry: does its article's address reach
        theta? The seed is whether the address carries a word of any class."""
        toks = url_tokens(url)
        seed = 1 if self.matched_terms(toks) else 0
        return self.weight(toks, seed) >= self.theta

    def class_ok(self, cls: str | None, h: int | None) -> bool:
        return cls in self.chosen and (cls not in ("war", "dispute") or (h is not None and h >= self.min_h))

    def cameo_class(self, code: str) -> tuple[str | None, int | None]:
        for p, cls, h in self.cameo:
            if code.startswith(p):
                return cls, h
        return None, None

    def weight(self, toks: list[str], seed: int) -> Fraction:
        o = self.odds if seed else 1 / self.odds
        p, d = self.model["p"], self.model["d"]
        P, D = self.model.get("passes", 0), self.model.get("drops", 0)
        for w in sorted(set(toks)):
            if w in p or w in d:
                o *= Fraction((p.get(w, 0) + 1) * (D + 2), (d.get(w, 0) + 1) * (P + 2))
        return o / (1 + o)

    def classify(self, toks: list[str], terms: list[tuple[str, int | None]]) -> str | None:
        score = {}
        for cls, _h in terms:
            score[cls] = score.get(cls, 0) + self.pi
        tags = self.model["tags"]
        for w in set(toks):
            for cls, n in tags.get(w, {}).items():
                score[cls] = score.get(cls, 0) + n
        if not score:
            return None
        best = max(score.values())
        return next(c for c in self.order if score.get(c) == best)

    # ---- an item ----
    def read(self, text: str = "", url: str = "", cameo: str | None = None, entries: list[str] | None = None) -> dict:
        """Read one item. A headline gives text (and its link, unused); a GDELT event gives the article's
        address, its CAMEO code and the entries its fields carry."""
        gdelt = cameo is not None
        toks = url_tokens(url) if gdelt else tokens(text)
        occ = self.occurrences(toks)
        names = list(entries) if gdelt else self.named_entries(toks, occ)
        terms = self.matched_terms(toks, occ)
        if not names:                     # with no entry named, only a class that needs none may hold the item
            terms = [t for t in terms if t[0] in self.free]
        seed = 1 if terms else 0
        g = self.weight(toks, seed)
        if gdelt:
            cls, h = self.cameo_class(cameo)
        else:
            cls = self.classify(toks, terms)
            hs = [t[1] for t in terms if t[0] == cls and t[1] is not None]
            h = max(hs) if hs else None
        pair = self.relevant_pair(names)
        ok = (g >= self.theta and cls in self.chosen
              and (cls not in ("war", "dispute") or (h is not None and h >= self.min_h))
              and (pair or not self.pair_gate))
        return {"pass": ok, "g": g, "class": cls, "h": h, "seed": seed, "entries": names, "pair": pair,
                "terms": sorted({t[0] for t in terms})}


def build_entries() -> dict:
    """Map each relevance entry to the current COW states its words name (COW's state names; four
    aliases where the author's spelling differs from COW's)."""
    alias = {"st. vincent and the grenadines": "saint vincent and the grenadines", "antigua & barbuda": "antigua and barbuda",
             "st. kitts and nevis": "saint kitts and nevis", "federated states of micronesia": "micronesia"}
    orders = json.loads((MEMBER / "member.json").read_text())
    words = {e: {" ".join(tokens(w)) for w in v.split("|")} for e, v in orders["relevance"]["terms"].items()}
    out = {}
    for r in csv.DictReader(open(HERE / "cow" / "statelist2024.csv")):
        if r["endyear"] != "2024":
            continue
        n = " ".join(tokens(alias.get(r["statenme"].lower(), r["statenme"])))
        for e, ws in words.items():
            if n in ws:
                out.setdefault(e, []).append(int(r["ccode"]))
    return {e: sorted(v) for e, v in sorted(out.items())}


def build_model(marks: list[dict]) -> dict:
    """The learned counts from the author's marks: for each word, the passes and drops of marked items
    carrying it, and the class tags of passed items carrying it. Rebuilt from the marks alone."""
    p, d, tags = {}, {}, {}
    passes = sum(1 for m in marks if m["mark"] == "pass")
    drops = sum(1 for m in marks if m["mark"] == "drop")
    for m in marks:
        toks = url_tokens(m["url"]) if m.get("gdelt") else tokens(m["text"])
        for w in set(toks):
            if m["mark"] == "pass":
                p[w] = p.get(w, 0) + 1
                if m.get("class"):
                    tags.setdefault(w, {})[m["class"]] = tags.setdefault(w, {}).get(m["class"], 0) + 1
            elif m["mark"] == "drop":
                d[w] = d.get(w, 0) + 1
    return {"marks": len(marks), "passes": passes, "drops": drops, "p": dict(sorted(p.items())), "d": dict(sorted(d.items())),
            "tags": {w: dict(sorted(v.items())) for w, v in sorted(tags.items())}}


def definition() -> str:
    """What a reading of the field depends on: the classes and the settings (and the learned counts
    when the settings say to use them)."""
    import hashlib
    orders = json.loads((MEMBER / "member.json").read_text())
    s = orders["filter"]
    blob = json.dumps({"classes": CLASSES, "settings": {k: v for k, v in s.items() if not k.startswith("_")},
                       "entries": json.loads((HERE / "cow" / "entries.json").read_text())}, sort_keys=True)
    if s.get("marks") == "learned":
        blob += model_path(s).read_text()
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


def load(settings: dict | None = None) -> Filter:
    """The filter as member.json's settings define it: the learned counts only when filter.marks is "learned"."""
    orders = json.loads((MEMBER / "member.json").read_text())
    s = settings if settings is not None else orders["filter"]
    model = json.loads(model_path(s).read_text()) if s.get("marks") == "learned" else None
    return Filter(s, model)


def model_path(s: dict) -> Path:
    """The learned counts' file: as given if absolute or under ~, else relative to the member's repository
    (filter/model.json, which SOLID STAMP's run checks out with filter/)."""
    p = Path(s["model"]).expanduser()
    return p if p.is_absolute() else MEMBER / p


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "entries":
        m = build_entries()
        (HERE / "cow" / "entries.json").write_text(json.dumps(m, indent=0) + "\n")
        majors = sorted({int(r["ccode"]) for r in csv.DictReader(open(HERE / "cow" / "majors2024.csv"))
                         if int(r["endyear"]) >= 2024})
        contig = sorted({(int(r["state1no"]), int(r["state2no"])) for r in csv.DictReader(open(HERE / "cow" / "contiguity2016.csv"))
                         if int(r["conttype"]) <= 4})
        (HERE / "cow" / "gates.json").write_text(json.dumps({
            "_note": "From COW's majors2024.csv (in tenure at the end of 2024) and contiguity2016.csv (types 1-4: land, or up to 150 miles of sea).",
            "majors": majors, "contiguous": [list(p) for p in contig]}) + "\n")
        print(f"{len(m)} entries name {sum(len(v) for v in m.values())} COW states; {len(majors)} major powers; {len(contig)} contiguous pairs")
    elif cmd == "model":
        marks = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
        Path(sys.argv[3]).write_text(json.dumps(build_model(marks), ensure_ascii=False) + "\n")
        print(f"{len(marks)} marks -> {sys.argv[3]}")
    elif cmd == "test":
        r = load().read(" ".join(sys.argv[2:]))
        print(json.dumps({**r, "g": f"{float(r['g']):.4f}"}, ensure_ascii=False))
    else:
        print(__doc__)
