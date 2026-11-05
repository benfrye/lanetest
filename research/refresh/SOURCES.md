# Results refresh: sources

Refresh run: 2026-11-04, about 22:00 to 22:30 ET (2026-11-05 ~03:00 to 03:30 UTC).
Input: `to_refresh.json` (236 races, snapshot ~11:10 ET Nov 4).
Output: `results_refresh.json`

## Source used for all 236 races

**NBC News results (Decision Desk / NBC projections)**, fetched from NBC's results JSON feed, which is what the public results pages load:

- Feed pattern: `https://www.nbcnews.com/firecracker/api/v2/state-results/2026-elections/{state}-{house|senate|governor}-results`
- Public pages: `https://www.nbcnews.com/politics/2026-elections/{state}-{office}-results` (each record's `source_url` points to the race page)
- 63 state/office feeds fetched (every state/office in the input list). All returned HTTP 200.
- Feed `lastModified`: **2026-11-05T02:52:26Z (9:52 PM ET Nov 4)** on every feed. A second fetch about 30 minutes later returned the same timestamp.
- Fields used: candidate `percentVote` (share of total vote), `votes`, area `percentIn` (percent of expected vote), candidate `callStatus == "P"` / `isWinner` (NBC projected winner), statewide `callStatusText` ("Too close to call", "Too early to call").

## Sources tried and not used

| Source | Result |
|---|---|
| AP (apnews.com/projects/election-results-2026/...) | 404 on curl; apnews.com is blocked for the search/fetch tool |
| NYT results (nytimes.com/interactive/2026/11/03/us/elections/...) | 403 |
| NY State BOE (nyenr.elections.ny.gov) | 403 |
| Wikipedia, 2026 NY House elections page (rev 2026-11-05T01:41Z) | Prose and candidate lists only, no live result tables for NY-17. Not used. |
| Web search for an NY-17 general-election call | Nothing conclusive |

Every race has a single source (NBC). There is no second source to confirm the figures.

## Conventions in results_refresh.json

- `dem_pct` / `rep_pct` are the shares of the candidates named in the input. Names are matched with accents and Jr./III suffixes ignored. Independents the input treats as the "dem" slot (Osborn NE, Bodnar MT, Hill AK-AL) are matched by name.
- `other_pct` is the sum of all other candidates, including same-party opponents in CA top-two races.
- `called` comes from the NBC projection. For same-party general elections (CA-4, CA-7, CA-11, CA-14 D-vs-D; CA-40 R-vs-R) NBC has not projected a candidate. These keep the party in `called`, and `called_by` marks it as implied.
- `changed` is true if dem_pct, rep_pct, pct_counted or called differs from the input by 0.05 or more. Records with `unchanged: true` show NBC figures identical to the snapshot.
- Extra fields: `candidates` (full NBC list), `flags`, `source_data_url`, `source_last_modified`.
