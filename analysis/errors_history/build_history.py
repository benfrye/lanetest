"""Build state two-party presidential margins 1976-2024 from the MIT EDSL file.
Reads research/errors_history/raw/1976-2024-president.csv; writes research/errors_history/state_two_party.{csv,json}.
Nominee votes are summed over every ballot line carrying the nominee's surname (fusion lines in NY/CT/SC etc.)."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "research/errors_history/raw/1976-2024-president.csv"
OUT = ROOT / "research/errors_history"
NOM = {1976: ("CARTER", "FORD"), 1980: ("CARTER", "REAGAN"), 1984: ("MONDALE", "REAGAN"), 1988: ("DUKAKIS", "BUSH"),
       1992: ("CLINTON", "BUSH"), 1996: ("CLINTON", "DOLE"), 2000: ("GORE", "BUSH"), 2004: ("KERRY", "BUSH"),
       2008: ("OBAMA", "MCCAIN"), 2012: ("OBAMA", "ROMNEY"), 2016: ("CLINTON", "TRUMP"), 2020: ("BIDEN", "TRUMP"),
       2024: ("HARRIS", "TRUMP")}
votes = defaultdict(lambda: [0, 0, 0])  # (year, st) -> D, R, total
party_check = defaultdict(set)
with open(RAW, newline="") as f:
    for r in csv.DictReader(f):
        y, s = int(r["year"]), r["state_po"]
        name = (r["candidate"] or "").upper().replace(",", " ").split()
        v = int(float(r["candidatevotes"] or 0))
        votes[(y, s)][2] = int(float(r["totalvotes"]))
        dn, rn = NOM[y]
        if name and name[0] == dn:
            votes[(y, s)][0] += v; party_check[(y, "D")].add(r["party_simplified"])
        elif name and name[0] == rn:
            votes[(y, s)][1] += v; party_check[(y, "R")].add(r["party_simplified"])
years = sorted(NOM)
states = sorted({s for (_, s) in votes})
assert len(states) == 51, states
nat = {}
for y in years:
    D = sum(votes[(y, s)][0] for s in states); R = sum(votes[(y, s)][1] for s in states)
    nat[y] = 100 * (D - R) / (D + R)
rows = []
for y in years:
    for s in states:
        d, r, t = votes[(y, s)]
        assert d > 0 and r > 0, (y, s)
        m = 100 * (d - r) / (d + r)
        rows.append({"year": y, "state": s, "dem_votes": d, "rep_votes": r, "total_votes": t, "margin2p": round(m, 4),
                     "national2p": round(nat[y], 4), "rel": round(m - nat[y], 4), "two_party_share_of_total": round((d + r) / t, 4)})
with open(OUT / "state_two_party.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
json.dump({"source": "MIT EDSL U.S. President 1976-2024, doi:10.7910/DVN/42MVDX v10.1, retrieved 2026-11-04",
           "national2p": nat, "rows": rows}, open(OUT / "state_two_party.json", "w"), indent=0)
print({y: round(nat[y], 2) for y in years})
print("party labels on nominee lines:", {k: sorted(v) for k, v in party_check.items() if len(v) > 1})
