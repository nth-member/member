/* The member's relevance reading, computed as member.py computes it (tests/fidelity.mjs checks
   the two against each other).

   Each entry's share of a granule's events is placed as a percentile rank (ties counting half)
   in that entry's own history of granules the same size. The granule's reading is the sum of the entries' shares above
   their own medians: each entry's excess over its own median share, weighted (every weight 1
   unless member.json's relevance.weights sets it) and summed; an entry below its median adds
   nothing, so concentration on a few entries reads high. The reading
   is itself placed as a percentile in the member's history. The entries that rose are those
   at or above the cut in their own history. Sums run in entry order, as in member.py, so both
   give the same numbers to the last bit. */
(function (root) {
  "use strict";

  function make(R, weights) {
    const N = R.entries.length;
    const W = R.entries.map(e => (weights && weights[e] != null ? +weights[e] : 1));
    const refs = {};

    // percentile rank of v in a sorted history: the share of it below v, ties counting half
    function at(ref, v) {
      let lo = 0, hi = ref.length;
      while (lo < hi) { const m = (lo + hi) >> 1; if (ref[m] < v) lo = m + 1; else hi = m; }
      let up = lo, top = ref.length;
      while (up < top) { const m = (up + top) >> 1; if (ref[m] <= v) up = m + 1; else top = m; }
      return 100 * (lo + up) / (2 * ref.length);
    }

    // one granule: its days, NULL days, the share any entry matched, and each entry's share
    function win(i0, w) {
      let rows = 0, hits = 0, present = 0, nul = 0;
      const n = new Array(N).fill(0);
      for (let i = i0; i < i0 + w; i++) {
        if (i < 0 || i >= R.rows.length || R.rows[i] == null) { nul++; continue; }
        present++; rows += R.rows[i]; hits += R.hits[i];
        for (let k = 0; k < N; k++) n[k] += R.counts[k][i];
      }
      return { i0, w, present, nul, n, share: rows ? hits / rows : null,
               shares: rows ? n.map(v => v / rows) : null };
    }

    function read(ref, x) {
      const p = x.shares.map((s, k) => at(ref.E[k], s));
      let t = 0;
      for (let k = 0; k < N; k++) {
        const e = ref.E[k], n = e.length;
        const m = n ? (e[(n - 1) >> 1] + e[n >> 1]) / 2 : 0;
        t += W[k] * Math.max(0, x.shares[k] - m);
      }
      return { p, index: t };
    }

    // the member's history at this granule, from every non-overlapping window
    function reference(w) {
      if (refs[w]) return refs[w];
      const wins = [];
      for (let i = 0; i + w <= R.rows.length; i += w) {
        const x = win(i, w);
        if (x.share != null && x.present >= Math.max(1, w >> 1)) wins.push(x);
      }
      const ref = { E: [], I: null };
      for (let k = 0; k < N; k++) ref.E.push(wins.map(x => x.shares[k]).sort((a, b) => a - b));
      ref.I = wins.map(x => read(ref, x).index).sort((a, b) => a - b);
      return (refs[w] = ref);
    }

    function judge(x, ref, cut) {
      if (x.shares == null) { x.pct = null; x.rose = []; x.p = null; x.index = null; return x; }
      const r = read(ref, x);
      x.p = r.p; x.index = r.index; x.pct = at(ref.I, r.index);
      x.rose = [];
      for (let k = 0; k < N; k++) if (r.p[k] >= cut) x.rose.push(k);
      x.rose.sort((a, b) => (r.p[b] - r.p[a]) || (x.n[b] - x.n[a]));
      return x;
    }

    // walk days i0..i1 in granules of g; refine those deemed relevant
    function walk(i0, i1, g, cut, GD, FINER) {
      const w = GD[g], ref = reference(w), out = [];
      for (let i = i0; i <= i1; i += w) {
        const x = judge(win(i, Math.min(w, i1 - i + 1)), ref, cut);
        x.g = g;
        x.rel = x.pct != null && x.pct >= cut;
        x.finer = x.rel && FINER[g] ? walk(i, i + x.w - 1, FINER[g], cut, GD, FINER) : [];
        out.push(x);
      }
      return out;
    }

    return { N, at, win, read, reference, judge, walk };
  }

  const api = { make };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Relevance = api;
})(typeof window !== "undefined" ? window : globalThis);
