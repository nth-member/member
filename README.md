# The nth member

**REVOTT's numerator, working on its own.** Served at https://nth-member.github.io/member/.

Every fixed Y in REVOTT generates a 550-node, 945-edge SFO over X:

    TNLDY = 14160 + 100·(Y + X)        date = the instant at which the Nsukka/Yg clock reads TNLDY

Time is read from Nsukka (WAT, UTC+01:00) on the engine's own year, Yg = 17640/48.3 days, laid on
Nsukka's calendar from 1 December 00:00 and recalibrated every Yg year (REVOTT's `revott/clock.py`;
the page's copy is `docs/nsukka-yg-clock.js`). The instant box, the address and every time shown are
Nsukka time, and each journal day runs from Nsukka's midnight. Entries written before 2026-11-01 used
the earlier uniform UTC reckoning and are kept as written.

The member always knows where that SFO is. At any instant it reports:

- which keys fire;
- which edges are open and how far along each one is;
- the layered reading of both ends of each open edge;
- the (Y, X) sentences on the instant's line through the 550 × 550 grid, read as «X» is being «Y».

It walks the **micronodes** along every open edge. A micronode is a granule of the trajectory, from a
second to a year, judged for its relevance to that trajectory. A granule deemed relevant is refined
to finer granules, down to what the data can resolve. After each refresh the member writes a journal
entry without being asked, and announces firings before the field has seen them.

## The site

`docs/index.html` is static: no build step, no server. From the files in `docs/data/` it computes,
in the browser, for any Y, instant and granule:

- **position:** TNLDY, the X the instant falls on, and the next key;
- **firing:** keys of the SFO inside the granule;
- **open edges:** progress along each, the readings of both ends, and the micronode strip. The strip
  has one bar per granule, and its height is that granule's reading as a percentile in the member's
  own history (see *The reading*, below). Red bars are deemed relevant, each names the entries that
  rose, and each one's refinement to days links to that day's sources on
  [nth-member/gdelt](https://nth-member.github.io/gdelt/);
- **sentences:** every (Y, X) pair of SFO_BB values landing inside the granule;
- **ahead:** keys and eigen crossings within the horizon, with joint firings flagged;
- **eigen:** Z = 200·Yp + 14160, one value at a time. It is a curiosity, shown beside the primary
  readings;
- **the journal**, and the standing orders.

## How it runs

    python3 member.py          write docs/journal/DAY.md for the newest day in the field
    python3 build.py           rebuild docs/data/ for the site

REVOTT's `gdelt/refresh.sh` runs both as stage 4b whenever `~/member` exists, then commits `docs/`
here and pushes it with `--push`.

The member reads GDELT's daily archives through `unzip -p` and never extracts them. It keeps one
line per day in `cache/relevance_daily.csv` (gitignored), and rebuilds that cache when the relevance
terms change.

## Standing orders — `member.json`

| setting | what it sets |
|---|---|
| `instances` | the Ys the journal follows (default 24.50) |
| `horizon_days` | how far ahead to look |
| `announce_within_days` | how close a firing must be before the journal announces it |
| `relevant_percentile` | the cut for "deemed relevant" (default 90) |
| `granule_by_span_days` | the starting granule for an edge, by its length: day up to 400 days, week up to 1,900, month beyond |
| `relevance.terms` | what the field is read for |
| `relevance.weights` | each entry's weight in a granule's reading (1 where absent; empty until set) |
| `filter` | the geopolitical filter's settings: θ, the classes that pass, `min_hostility`, `pair_gate`, `marks` |

**The relevance terms are the author's.** The author set 25 on 2026-09-26: Sarajevo, Bosnia-Herzegovina,
Serbia and the Serbs, the Euphrates (with Iraq and Syria), Megiddo and Armageddon, Babylon, Gog and
Magog, Russia and Moscow, Washington and the United States, Jerusalem, Israel, the Temple Mount and
Al-Aqsa, Rome, Mecca, Sofia, Egypt, the European Union, NATO, the United Nations and its Security
Council, and China and Beijing.

On 2026-11-20 the author upgraded them:

- Iran, the West Bank and Palestine, Turkey, Jordan and the African Union join the first themes.
- Several of the first themes gain a capital or a country: Belgrade, Baghdad and Damascus, Italy, Bulgaria, Cairo.
- Every state of Europe and Asia is added with its capital.

The list was then completed at the author's instruction:

- Every other member state of the United Nations is added with its capital, together with Western Sahara and
  Somaliland. The author's own entries already held Kosovo, Palestine, Taiwan and Vatican City.
- Gaza joins Palestine's entry, and Hong Kong and Macau join China's.
- Listed countries gain the other names GDELT or the headlines use for them: Czech Republic, Slovak
  Republic, Macedonia, East Timor, Bosnia, Türkiye, Britain and UK, Vatican and Holy See, UAE.
- The Maldives' capital is written Malé, so that the ordinary word "male" does not match.

There are now 214 entries, Fulfilment0000000 to Fulfilment0000215, and each word stands in one entry. A city
with its own entry (Sarajevo, Moscow, Jerusalem) is not repeated in its country's entry.
Fulfilment0000028 and Fulfilment0000100 repeated earlier entries and were removed.

The terms are matched as whole words, case-insensitively, against GDELT's actor and place names. On
15–16 November 2026 they matched 97.2% of GDELT's events; the first 25 matched 45.0%. Nearly all the
rest carry no place at all. REVOTT, the Revelation Of The Trial, is tuned by default to geopolitical
events tending toward the fulfilment of the Apocalypse seen by John.

## The reading

Because nearly every event matches some entry, the member reads each entry on its own.

- An event counts once for every entry whose words it carries. Where words overlap, the longest
  wins, so "Guinea-Bissau" counts for Guinea-Bissau and not for Guinea.
- In a granule, each entry's share of the events is placed as a percentile rank in that entry's own
  history of granules the same size, with ties counting half. An entry at its usual zero reads 50,
  not 100; it rises only above its usual level.
- The granule's reading is the sum of the entries' shares above their own medians: each entry's
  excess over its own median share in that history, weighted by `relevance.weights` and summed. An
  entry below its median adds nothing, so a granule whose events concentrate on a few entries (a
  war, an invasion) reads high instead of being outvoted by the entries it crowds out. (Until
  2026-11-20 it was the mean of the entries' percentiles, which read such granules low.) The
  reading is placed in turn as a percentile in the member's history of granules that size. At or
  above `relevant_percentile` the granule is deemed relevant and refined.
- The entries that **rose** are those at or above that percentile in their own history.
- The cache keeps each entry's daily count, so a change of weights needs no rebuild. A change of
  terms rebuilds the cache.

`member.py` computes the reading for the journal, and `docs/relevance.js` computes it for the page.
`node tests/fidelity.mjs` checks that the two agree on every micronode the journal walks.

## The geopolitical filter

Since 2026-11-22 an event counts only if it also passes the member's geopolitical filter (`filter/`),
at the author's word: "classify feeds in terms of geopolitical weight ... by classify I mean filter".

- **Classes.** Six come from the Correlates of War project, each defined by its codebook codes: war
  (war types 1–9), militarized dispute (MID 5.0: hostility 1–5 and its 21 actions), alignment (formal
  alliances I/IIa/IIb/III, defense cooperation agreements, IGO membership), diplomatic representation
  (0/1/2/3/9), territorial change (procedures 1–6) and capability (NMC v7.0, arms technology). Five
  are marked "not from COW": agreement and negotiation, sanctions and other pressure, internal power
  (from CAMEO's event codes), holy places and religion (COW's World Religion Data and the author's
  holy-place entries), and economic statecraft. `filter/classes.json` keeps each class's source, its
  codes and the words it starts from, each word traced to its codebook.
- **The weight.** An item i passes when G(i) ≥ θ, its class is among the chosen ones, war and disputes
  reach `min_hostility` on the MID scale, and, with `pair_gate` set, it is politically relevant (it
  names a COW major power, or two states contiguous by land or up to 150 miles of sea: Lemke and Reed
  2001, from COW's Major Powers 2024 and Direct Contiguity v3.2). G = O/(1+O), with
  O(i) = 4^(2s−1) · Π_w ((p_w+1)/(P+2)) / ((d_w+1)/(D+2)): s is the seed (the item names an entry and
  carries a word of a class), p_w and d_w count the author's pass and drop marks on items carrying w,
  P and D all of them. Every factor is a ratio of integers, so Python and JavaScript compute G exactly.
- **GDELT events** are read through the words of their article's address (85–92% of rows carry at
  least three), and take their class and hostility from their CAMEO code (`classes.json` "cameo").
  The day's rows stay the denominator: an entry's share is its passing events per GDELT event.
- **Settings** are `member.json`'s `filter`: θ, the classes, `min_hostility`, `pair_gate`, and
  `marks`. With `marks` "seed" the classes' words alone are used; "learned" adds the counts built from
  the author's marks (`python3 filter/geofilter.py model MARKS OUT`), which are kept off the repos. A
  change to the filter rebuilds the cache (about 13 minutes).
- **Along each edge** the journal and the page show, for every relevant day, the entries that drove
  its reading (the largest terms of its sum) and up to three passing items carrying them: the feed
  archive's headlines on days it covers, else GDELT's most-carried passing events
  (`cache/items_daily.jsonl`, `docs/data/items/YEAR.json`).
- `node tests/geofilter_fidelity.mjs` checks `filter/geofilter.js` against `filter/geofilter.py` on
  every headline in the feed archive, four ways.

## Rules

- Percentiles are readings against the member's own history. There are no p-values.
- NULL is never zero.
- GDELT 1.0 floors the micronode at one day. Anything finer needs GDELT 2.0's 15-minute feed.
- Before 2013-04-01 the member has no daily history, so micronodes begin there.
- Readings lead with each key's marking, then the apocalypse sequence (seal, trumpet, vial, horns),
  then any derived sub-context. A key with no primary layer of its own carries the last preceding
  key's, and is marked as carried.

## Refreshing the sites

One command, on the computer that keeps the sites, refreshes every 3PP-NOAH site whose data changes: JOMO
SFO-WAM's feeds, REVOTT stamps, then GDELT into the GDELT day sources, REVOTT, the nth member,
H-Gematria/ASCII and IPPROTO.

```bash
cd ~ && ./refresh-all.sh --push     # refresh and publish every updatable site
cd ~ && ./refresh-all.sh            # refresh and commit, push nothing
cd ~ && ./refresh-all.sh --check    # what GDELT has that is new; changes nothing
```

JOMO SFO-WAM's feeds and REVOTT stamps also refresh themselves every 15 minutes, from cron.

## The nth-member sites

| site | repository | what it is |
|---|---|---|
| https://nth-member.github.io/revott/ | nth-member/revott | REVOTT atop GDELT: the field at every node of an instance |
| https://nth-member.github.io/gdelt/ | nth-member/gdelt | what GDELT was reading on a given day |
| https://nth-member.github.io/member/ | nth-member/member | the nth member: REVOTT's numerator, its introspection and its journal |
| https://nth-member.github.io/gematria/ | nth-member/gematria | H-Gematria/ASCII: the two name-value programs in the browser |
| https://nth-member.github.io/alien-corridor/ | nth-member/alien-corridor | the Alien Corridor Support System (MDQNM engine) in the browser |
| https://nth-member.github.io/gigaspeak/ | nth-member/gigaspeak | Gigaspeak: ASCII carried in colour, the speaker, the URL builder and the Communicator |
| https://nth-member.github.io/tsots_value_equation/ | nth-member/tsots_value_equation | the TSOTS value equation: a synthetic simulation of the Shula, run in the browser |
| https://nth-member.github.io/ipproto/ | nth-member/ipproto | IPPROTO: the 256 IP protocol numbers in 13 categories, a capture reader and a packet bridge |
| https://nth-member.github.io/revott-stamps/ | nth-member/revott-stamps | REVOTT stamps: feed items stamped onto a (Y, X) within a variable window |
| https://nth-member.github.io/solid-stamp/ | nth-member/solid-stamp | SOLID STAMP: a notification at every TNLDY that matches SFO-BBs, with its digest |
