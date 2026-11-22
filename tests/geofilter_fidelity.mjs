// filter/geofilter.js against filter/geofilter.py: every headline in the feed archive, read four ways
// (tests/geofilter_ref.py), must give the same pass, weight (as an exact fraction), class, hostility,
// seed, entries, pair and terms.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const GF = require("../filter/geofilter.js");
const here = new URL("..", import.meta.url).pathname;
const J = p => JSON.parse(readFileSync(here + p, "utf8"));
const py = JSON.parse(execFileSync("python3", [here + "tests/geofilter_ref.py"], { maxBuffer: 1 << 30 }).toString());
const cfg = { classes: J("filter/classes.json"), orders: J("member.json"), entries: J("filter/cow/entries.json"), gates: J("filter/cow/gates.json") };
const model = GF.buildModel(py.marks);
let ok = 0, bad = 0;
for (const v of py.variants) {
  const f = GF.make({ ...cfg, settings: v.settings, model: v.model ? model : null });
  let vb = 0;
  for (const row of v.rows) {
    const r = f.read(py.items[row[0]]);
    const js = [row[0], r.pass, r.g, r.class, r.h, r.seed, r.entries, r.pair, r.terms];
    if (JSON.stringify(js) === JSON.stringify(row)) ok++;
    else { bad++; if (vb++ < 5) console.log(v.name, "differs:\n  py", JSON.stringify(row), "\n  js", JSON.stringify(js), "\n  ", py.items[row[0]]); }
  }
  console.log(`${v.name}: ${v.rows.length} readings, ${v.rows.filter(r => r[1]).length} pass`);
}
console.log(`${ok} of ${ok + bad} readings identical`);
process.exit(bad ? 1 : 0);
