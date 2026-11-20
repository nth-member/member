// docs/relevance.js must read the member's history exactly as member.py does.
//
//   node tests/fidelity.mjs
//
// tests/reading.py walks every open edge the journal walks (from the cache); this walks the
// same spans from docs/data/relevance.json with docs/relevance.js. Every granule, at every depth
// of refinement, must agree on its days present, its percentile, its reading and the entries
// that rose, to the last bit. The day itself is checked as the journal's section 3 reads it.
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url)), root = join(here, "..");
const require = createRequire(import.meta.url);
const Relevance = require(join(root, "docs", "relevance.js"));
const R = JSON.parse(readFileSync(join(root, "docs", "data", "relevance.json"), "utf8"));
const O = JSON.parse(readFileSync(join(root, "docs", "data", "orders.json"), "utf8"));
const py = JSON.parse(execFileSync("python3", [join(here, "reading.py"), ...process.argv.slice(2)],
                                   { cwd: root, maxBuffer: 1 << 28 }).toString());

const GD = { day: 1, week: 7, month: 30 }, FINER = { month: "week", week: "day" };
const RL = Relevance.make(R, O.relevance.weights || {});
const DAY = 86400000, idx = d => Math.round((Date.parse(d + "T00:00:00Z") - Date.parse(R.start + "T00:00:00Z")) / DAY);
const iso = i => new Date(Date.parse(R.start + "T00:00:00Z") + i * DAY).toISOString().slice(0, 10);
function* flat(ns, depth = 0) {
  for (const n of ns) {
    yield { start: iso(n.i0), w: n.w, g: n.g, depth, present: n.present, pct: n.pct, index: n.index, rose: n.rose.slice(0, 8) };
    yield* flat(n.finer, depth + 1);
  }
}

let ok = 0, bad = 0;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
if (py.def !== R.def) { console.log(`definition differs: member.py ${py.def}, relevance.json ${R.def}`); process.exit(1); }
for (const wk of py.walks) {
  const js = [...flat(RL.walk(idx(wk.start), idx(wk.stop), wk.g, py.cut, GD, FINER))];
  if (js.length !== wk.nodes.length) { bad++; console.log(`Y ${wk.y} ${wk.edge.join(" → ")}: ${wk.nodes.length} granules in Python, ${js.length} here`); continue; }
  wk.nodes.forEach((p, k) => {
    if (same(p, js[k])) ok++;
    else { bad++; if (bad <= 10) console.log(`Y ${wk.y} ${wk.edge.join(" → ")} ${p.g} from ${p.start}:`, JSON.stringify(p), "≠", JSON.stringify(js[k])); }
  });
}
const d = RL.judge(RL.win(idx(py.day.start), 1), RL.reference(1), py.cut);
if (same({ pct: d.pct, index: d.index, rose: d.rose }, { pct: py.day.pct, index: py.day.index, rose: py.day.rose })) ok++;
else { bad++; console.log("the day differs:", JSON.stringify(py.day), "≠", JSON.stringify({ pct: d.pct, index: d.index, rose: d.rose })); }
console.log(`${ok}/${ok + bad} granules identical (${py.walks.length} walks, definition ${R.def})`);
process.exit(bad ? 1 : 0);
