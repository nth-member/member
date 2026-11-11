# The nth member

**REVOTT's numerator, working on its own.** Served at https://nth-member.github.io/member/.

Every fixed Y in REVOTT generates a 401-node, 707-edge SFO over X:

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
- the (Y, X) sentences on the instant's line through the 401 × 401 grid, read as «X» is being «Y».

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
  has one bar per granule, and its height is that granule's percentile in the member's own history.
  Red bars are deemed relevant, and each one's refinement to days links to that day's sources on
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

**The relevance terms are the author's**, set on 2026-09-26: Sarajevo, Bosnia-Herzegovina, Serbia and
the Serbs, the Euphrates (with Iraq and Syria), Megiddo and Armageddon, Babylon, Gog and Magog, Russia
and Moscow, Washington and the United States, Jerusalem, Israel, the Temple Mount and Al-Aqsa, Rome,
Mecca, Sofia, Egypt, the European Union, NATO, the United Nations and its Security Council, and China
and Beijing. They are matched as whole words, case-insensitively, against GDELT's actor and place
names. REVOTT, the Revelation Of The Trial, is tuned by default to geopolitical events tending toward
the fulfilment of the Apocalypse seen by John. Most of GDELT has no bearing on it, and nothing here
reads GDELT whole.

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
