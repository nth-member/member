/* The member's geopolitical filter, read as filter/geofilter.py reads it (tests/geofilter_fidelity.mjs
   checks the two against each other on every headline in the feed archive).

   An item is seeded when it names one of the author's entries and carries a class word, or carries a word of a
   class that needs no entry (AI and computing). It passes when its weight G reaches theta, its class is among the chosen classes, war and
   disputes reach min_hostility on the MID scale, and, with pair_gate set, it is politically relevant.
   G = O / (1 + O), with O = seed_odds^(2s - 1) times ((p_w + 1) / (P + 2)) / ((d_w + 1) / (D + 2)) for each
   distinct word w the author's marks have counted: every factor a ratio of integers, kept exact here with
   BigInt. */
(function (root) {
  "use strict";

  const GENERIC = new Set(["www", "com", "org", "net", "html", "htm", "php", "aspx", "asp", "index", "amp"]);

  // lower case, every mark (Unicode category M) removed after NFKD, split on anything but a-z, 0-9 and ',
  // and a possessive 's dropped
  function tokens(text) {
    const t = String(text).replace(/[’‘]/g, "'").toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");
    const out = [];
    for (const w of t.split(/[^a-z0-9']+/)) {
      let s = w.replace(/^'+|'+$/g, "");
      if (s.endsWith("'s")) s = s.slice(0, -2);     // the possessive: "Russia's" reads as "russia"
      if (s) out.push(s);
    }
    return out;
  }

  // the words of an article's address: its path, without the host, the query or the file endings
  function urlTokens(url) {
    let p = String(url).toLowerCase().replace(/^[a-z]+:\/\/[^/]*/, "").replace(/[?#].*$/, "");
    return tokens(p.replace(/'/g, " ")).filter(w => !/^[0-9]+$/.test(w) && !GENERIC.has(w) && w.length > 1);
  }

  const gcd = (a, b) => { while (b) [a, b] = [b, a % b]; return a < 0n ? -a : a; };
  function frac(s) {                       // "1/2" or "0.5" -> [num, den]
    s = String(s);
    if (s.includes("/")) { const [a, b] = s.split("/"); return [BigInt(a.trim()), BigInt(b.trim())]; }
    const [i, f = ""] = s.split(".");
    return [BigInt(i + f), 10n ** BigInt(f.length)];
  }
  function cmpTuple(a, b) {
    for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
    return a.length - b.length;
  }

  function make(cfg) {
    const C = cfg.classes, O = cfg.orders, S = cfg.settings || O.filter;
    const theta = frac(S.theta), chosen = new Set(S.classes), minH = +S.min_hostility, pairGate = !!S.pair_gate;
    const order = C.precedence, odds = BigInt(C.seed_odds), pi = +C.class_seed_count;
    const model = cfg.model || { p: {}, d: {}, tags: {} };
    const terms = [];
    for (const c of C.classes) for (const t of c.terms)
      terms.push([c.id, t.forms.map(tokens), t.h == null ? null : t.h, (t.needs || []).map(tokens)]);
    const entryPhrases = [];
    for (const [e, v] of Object.entries(O.relevance.terms)) for (const w of v.split("|")) entryPhrases.push([tokens(w), e]);
    entryPhrases.sort((a, b) => (b[0].length - a[0].length) || cmpTuple(a[0], b[0]));
    const free = new Set(C.classes.filter(c => c.needs_entry === false).map(c => c.id));   // pass without an entry
    const entries = cfg.entries, majors = new Set(cfg.gates.majors);
    const contig = new Set(cfg.gates.contiguous.map(([a, b]) => a + "," + b));

    function has(toks, ph) {
      const n = ph.length;
      outer: for (let i = 0; i + n <= toks.length; i++) {
        for (let j = 0; j < n; j++) if (toks[i + j] !== ph[j]) continue outer;
        return true;
      }
      return false;
    }
    function namedEntries(toks) {
      const used = new Array(toks.length).fill(false), found = [];
      for (const [ph, e] of entryPhrases) {
        const n = ph.length;
        for (let i = 0; i + n <= toks.length; i++) {
          let eq = true;
          for (let j = 0; j < n; j++) if (toks[i + j] !== ph[j]) { eq = false; break; }
          if (!eq) continue;
          let free = true;
          for (let j = i; j < i + n; j++) if (used[j]) { free = false; break; }
          if (!free) continue;
          for (let j = i; j < i + n; j++) used[j] = true;
          if (!found.includes(e)) found.push(e);
        }
      }
      return found;
    }
    function matchedTerms(toks) {
      const out = [];
      for (const [cls, forms, h, needs] of terms)
        if (forms.some(f => has(toks, f)) && (!needs.length || needs.some(f => has(toks, f)))) out.push([cls, h]);
      return out;
    }
    function relevantPair(names) {
      const st = [...new Set(names.flatMap(e => entries[e] || []))].sort((a, b) => a - b);
      if (st.some(c => majors.has(c))) return true;
      for (let i = 0; i < st.length; i++) for (let j = i + 1; j < st.length; j++) if (contig.has(st[i] + "," + st[j])) return true;
      return false;
    }
    function weight(toks, seed) {         // [num, den] of G, reduced
      let n = seed ? odds : 1n, m = seed ? 1n : odds;
      const P = BigInt(model.passes || 0), D = BigInt(model.drops || 0);
      const ws = [...new Set(toks)].sort();
      for (const w of ws) {
        const p = model.p[w], d = model.d[w];
        if (p == null && d == null) continue;
        n *= BigInt((p || 0) + 1) * (D + 2n); m *= BigInt((d || 0) + 1) * (P + 2n);
      }
      const g = gcd(n, n + m);
      return [n / g, (n + m) / g];
    }
    function classify(toks, ts) {
      const score = {};
      for (const [cls] of ts) score[cls] = (score[cls] || 0) + pi;
      for (const w of new Set(toks)) {
        const t = model.tags[w];
        if (t) for (const [cls, n] of Object.entries(t)) score[cls] = (score[cls] || 0) + n;
      }
      const vals = Object.values(score);
      if (!vals.length) return null;
      const best = Math.max(...vals);
      return order.find(c => score[c] === best);
    }
    function read(text) {
      const toks = tokens(text), names = namedEntries(toks);
      let ts = matchedTerms(toks);
      if (!names.length) ts = ts.filter(t => free.has(t[0]));   // with no entry named, only a class that needs none may hold the item
      const seed = ts.length ? 1 : 0;
      const [gn, gd] = weight(toks, seed);
      const cls = classify(toks, ts);
      const hs = ts.filter(t => t[0] === cls && t[1] != null).map(t => t[1]);
      const h = hs.length ? Math.max(...hs) : null;
      const pair = relevantPair(names);
      const ok = gn * theta[1] >= theta[0] * gd && chosen.has(cls)
        && (cls !== "war" && cls !== "dispute" || (h != null && h >= minH)) && (pair || !pairGate);
      return { pass: ok, g: gn + "/" + gd, gf: Number(gn) / Number(gd), class: cls, h, seed, entries: names, pair,
               terms: [...new Set(ts.map(t => t[0]))].sort() };
    }
    return { read, tokens, urlTokens };
  }

  // the learned counts from the author's marks, as filter/geofilter.py's build_model makes them
  function buildModel(marks) {
    const p = {}, d = {}, tags = {};
    const passes = marks.filter(m => m.mark === "pass").length, drops = marks.filter(m => m.mark === "drop").length;
    for (const m of marks) {
      const ws = new Set(m.gdelt ? urlTokens(m.url) : tokens(m.text));
      for (const w of ws) {
        if (m.mark === "pass") {
          p[w] = (p[w] || 0) + 1;
          if (m.class) { tags[w] = tags[w] || {}; tags[w][m.class] = (tags[w][m.class] || 0) + 1; }
        } else if (m.mark === "drop") d[w] = (d[w] || 0) + 1;
      }
    }
    return { marks: marks.length, passes, drops, p, d, tags };
  }

  const api = { make, tokens, urlTokens, buildModel };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.GeoFilter = api;
})(typeof self !== "undefined" ? self : this);
