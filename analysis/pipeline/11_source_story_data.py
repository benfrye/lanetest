"""Story data that triangulates sources beyond the NYT Voter Trends estimates.

Writes three files to analysis/output/story_data/:
  group_sources.json  voter-group margins and 2024->2026 shifts, NYT vs the SSRS network
                      voter poll (NBC presentation), with AP Voter Poll approximations
  geo_shifts.json     county/district swings relative to the same race's statewide swing
  sources.json        every cited source domain, by dataset, with citation counts

Only verified figures from research/*.json are used; rows marked UNVERIFIED or null are
skipped. Pure standard library so it runs with any python3.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "research"
OUT = ROOT / "analysis" / "output" / "story_data"


def load(name):
    return json.loads((RES / name).read_text())


# ---------------------------------------------------------------- voter groups
nyt = load("nyt_voter_trends.json")
national = load("national.json")
ssrs = next(e for e in national["exit_polls"] if e["source"].startswith("SSRS Voter Poll (consortium) - NBC"))
ap = next(e for e in national["exit_polls"] if e["source"].startswith("AP Voter Poll"))

nyt_rows = {g["group"]: g for g in nyt["groups"]}
nyt_two = {r["group"]: r["shift_vs_2024"] for r in nyt["shifts_two_level_education"]["rows"]}
ssrs_rows = {g["group"]: g for g in ssrs["groups"]}

# (label, NYT group, SSRS group). College splits differ: NYT's two-level chart gives shifts
# only, so those rows carry shift without a 2026 margin on the NYT side.
PAIRS = [
    ("Men", "Male", "Men"),
    ("Women", "Female", "Women"),
    ("18-29", "18-29", "18-29"),
    ("30-44", "30-44", "30-44"),
    ("45-64", "45-64", "45-64"),
    ("65+", "65+", "65+"),
    ("White", "White", "White"),
    ("Black", "Black", "Black"),
    ("Hispanic", "Hispanic", "Latino"),
    ("Asian", "Asian", "Asian"),
    ("College degree", None, "College graduate"),
    ("No college degree", None, "No college degree"),
    ("White, college", "White college", "White college grad"),
    ("White, no college", "White non-college", "White non-college"),
]
NYT_TWO_LEVEL = {"College degree": "College", "No college degree": "Non-college"}


def ssrs_entry(name):
    g = ssrs_rows.get(name)
    if not g or g.get("margin_2026") is None:
        return None
    m26, m24 = g["margin_2026"], g.get("margin_2024")
    return {"margin_2026": m26, "margin_2024": m24, "shift": None if m24 is None else m26 - m24, "share": g.get("share_of_electorate")}


def nyt_entry(label, name):
    if name:
        g = nyt_rows[name]
        return {"margin_2026": g["margin"], "margin_2024": g["margin"] - g["shift_vs_2024"], "shift": g["shift_vs_2024"], "share": g["share"]}
    return {"margin_2026": None, "margin_2024": None, "shift": nyt_two[NYT_TWO_LEVEL[label]], "share": None}


# AP Voter Poll was only available as text ("about 7 in 10"); keep its approximate 2026 margin.
AP_APPROX = {
    "18-29": {"margin_2026": 40, "text": "about 7 in 10 Democratic, 3 in 10 Republican"},
    "Hispanic": {"margin_2026": 27, "text": "about 6 in 10 Democratic, one-third Republican"},
    "Black": {"margin_2026": 80, "text": "about 9 in 10 Democratic"},
}

groups = []
for label, n_name, s_name in PAIRS:
    row = {"group": label, "nyt": nyt_entry(label, n_name), "ssrs": ssrs_entry(s_name), "ap": AP_APPROX.get(label)}
    n, s = row["nyt"], row["ssrs"]
    row["shift_gap"] = None if not s or s["shift"] is None else n["shift"] - s["shift"]
    groups.append(row)

group_sources = {
    "definition": "Margins are Democratic minus Republican, in points. Shift = 2026 House margin minus the same source's 2024 presidential margin.",
    "sources": {
        "nyt": {"name": "New York Times Voter Trends", "method": "Times/Siena polling (26,706 interviews) modeled onto precinct results and voter files", "url": nyt["url"]},
        "ssrs": {"name": "Network voter poll (SSRS for NBC, CNN, ABC, CBS, Fox)", "method": "Exit and pre-election survey of voters; 2024 comparison is the 2024 network exit poll", "url": ssrs["url"]},
        "ap": {"name": "AP Voter Poll", "method": "Survey of voters; only rounded shares were published in text", "url": ap["url"]},
    },
    "groups": groups,
    "note": "The two main sources use different methods and different 2024 baselines, so their shifts can differ by several points. Where they agree, the pattern is more trustworthy.",
}

# ---------------------------------------------------------------- geography
geo = load("geography.json")
patterns = {p["group"]: p for p in geo["shift_patterns"]}


def src(group):
    return patterns[group]["source"]


# Each place: (kind, name, race, shift, reference shift, reference label, source group key).
# Reference = the same race's statewide shift; House districts use the national House swing.
NAT_HOUSE = nyt["topline"]["shift_vs_2024"]
PLACES = [
    ("Big-city counties", "Allegheny Co., Pa. (Pittsburgh)", "Governor", 23.35, 23.81, "Pennsylvania", "Urban core: Allegheny County, PA (Pittsburgh) - Governor"),
    ("Big-city counties", "Broward Co., Fla.", "Governor", 15.11, 11.8, "Florida", "Urban/suburban: Broward County, FL - Governor"),
    ("Suburbs", "Berks Co., Pa.", "Governor", 24.58, 23.81, "Pennsylvania", "Suburban: Berks County, PA - Governor"),
    ("Suburbs", "Oakland Co., Mich. (preliminary)", "Senate", 3, 8.42, "Michigan", "Affluent suburb: Oakland County, MI - Senate"),
    ("Suburbs", "Kent Co., Mich. (Grand Rapids)", "Senate", 8, 8.42, "Michigan", "Mixed metro/suburb: Kent County, MI (Grand Rapids) - Senate"),
    ("College towns", "Athens Co., Ohio (Ohio University)", "Governor", 23.28, 19.14, "Ohio", "Athens County, OH (Ohio University) - Governor"),
    ("College towns", "Alachua Co., Fla. (Univ. of Florida)", "Governor", 12.26, 11.8, "Florida", "Alachua County, FL (Univ. of Florida) - Governor"),
    ("Small-town and rural", "Beaver Co., Pa.", "Governor", 26.83, 23.81, "Pennsylvania", "Working-class exurb: Beaver County, PA - Governor"),
    ("Small-town and rural", "Adams Co., Pa.", "Governor", 24.83, 23.81, "Pennsylvania", "Rural/small-town: Adams County, PA - Governor"),
    ("Small-town and rural", "Armstrong Co., Pa.", "Governor", 22.81, 23.81, "Pennsylvania", "Rural/small-town: Adams County, PA - Governor"),
    ("Small-town and rural", "Bedford Co., Pa.", "Governor", 18.32, 23.81, "Pennsylvania", "Rural/small-town: Adams County, PA - Governor"),
]
# Rural county lists parsed from "Name +x.xx" pairs in the verified paraphrases.
RURAL_LISTS = [
    ("Rural: Iowa sample counties (Adair, Adams, Allamakee, Appanoose, Audubon, Benton) - Senate", "Iowa", "Senate", 17.32, "Iowa"),
    ("Rural: same Iowa counties - Governor (Sand)", "Iowa", "Governor", 24.19, "Iowa"),
    ("Rural: Kansas sample counties - Senate", "Kansas", "Senate", 20.99, "Kansas"),
    ("Rural: Texas sample counties (Anderson, Andrews, Angelina, Aransas, Archer, Armstrong) - Senate", "Texas", "Senate", 25.77, "Texas"),
    ("Rural: Georgia sample counties - Senate", "Georgia", "Senate", 20.2, "Georgia"),
    ("Rural Appalachian NC (Alleghany, Ashe, Avery, Alexander) - Senate", "North Carolina", "Senate", 22.84, "North Carolina"),
]
ABBR = {"Iowa": "Iowa", "Kansas": "Kan.", "Texas": "Texas", "Georgia": "Ga.", "North Carolina": "N.C."}
for key, state, race, ref, ref_label in RURAL_LISTS:
    text = patterns[key]["quote_or_paraphrase"]
    for name, val in re.findall(r"([A-Z][a-z]+) \+(\d+\.\d+)", text):
        suffix = " (Sand)" if race == "Governor" else ""
        PLACES.append(("Small-town and rural", f"{name} Co., {ABBR[state]}{suffix}", race, float(val), ref, ref_label, key))

BLACK = [
    ("Black-majority MS counties (Bolivar, Adams) vs non-Black-majority rural MS (Benton, Attala, Amite, Alcorn) - Senate", "Mississippi", 22.89, "Miss.",
     {"Bolivar": "Black-majority", "Adams": "Black-majority", "Benton": "rural", "Attala": "rural", "Amite": "rural", "Alcorn": "rural"}),
    ("Black-majority SC counties (Allendale, Bamberg) vs white Upstate (Anderson, Abbeville) - Senate", "South Carolina", 22.34, "S.C.",
     {"Allendale": "Black-majority", "Bamberg": "Black-majority", "Anderson": "rural", "Abbeville": "rural", "Aiken": "rural"}),
]
for key, state, ref, ab, kinds in BLACK:
    note = patterns[key]["metric_note"]
    for name, val in re.findall(r"([A-Z][a-z]+) D\+(\d+\.\d+)", note):
        if name not in kinds:
            continue
        kind = "Black-majority counties" if kinds[name] == "Black-majority" else "Small-town and rural"
        PLACES.append((kind, f"{name} Co., {ab}", "Senate", float(val), ref, state, key))
PLACES.append(("Black-majority counties", "Anson Co., N.C.", "Senate", 13.79, 22.84, "North Carolina", "Anson County, NC (Black-plurality rural) vs Alamance - Senate"))

HISP = [
    ("South Texas: TX-15 (Rio Grande Valley) - House", "TX-15 (Rio Grande Valley)", 42.65),
    ("South Texas: TX-35 (redrawn) - House", "TX-35 (San Antonio-Austin)", 21.41),
    ("FL-27 (Miami, ~70% Hispanic) - House", "FL-27 (Miami)", 14.25),
    ("CO-8 (~39% Hispanic) - House", "CO-8 (Denver suburbs, 78% counted)", 16.53),
]
for key, name, val in HISP:
    PLACES.append(("Heavily Hispanic districts", name, "House", val, NAT_HOUSE, "national House vote", key))

places = []
for kind, name, race, shift, ref, ref_label, key in PLACES:
    places.append({
        "kind": kind, "place": name, "race": race, "shift": round(shift, 2), "reference_shift": ref,
        "reference": ref_label, "relative": round(shift - ref, 2), "source": src(key),
    })

KIND_ORDER = ["Heavily Hispanic districts", "Small-town and rural", "College towns", "Big-city counties", "Suburbs", "Black-majority counties"]
summary = []
for k in KIND_ORDER:
    rel = sorted(p["relative"] for p in places if p["kind"] == k)
    summary.append({"kind": k, "n": len(rel), "median_relative": rel[len(rel) // 2] if rel else None})

geo_shifts = {
    "definition": "Swing = 2026 margin minus Harris's 2024 margin in the same place. Relative swing = that minus the statewide swing in the same race (House districts: minus the national House swing).",
    "kinds": KIND_ORDER,
    "summary": summary,
    "places": places,
    "caveats": [
        "A sample, not every county: results pages listed counties alphabetically and some were cut off, and western counts are incomplete.",
        "Statewide races mix candidates; Shapiro (Pennsylvania) and Sand (Iowa) are strong statewide candidates.",
        "Oakland and CO-8 were still counting.",
    ],
}

# ---------------------------------------------------------------- source inventory
DATASETS = {
    "Race results (House, Senate, governor)": sorted(str(p.relative_to(RES)) for p in (RES / "house").glob("*.json")) + ["senate.json", "governors.json"],
    "Primaries and 2025 races": ["primaries.json", "offyear.json"],
    "Ballot measures": ["ballot_measures.json"],
    "Exit polls and national results": ["national.json"],
    "County and regional shifts": ["geography.json"],
    "Analysis and commentary": ["analyst_takes.json"],
    "2028 contenders": ["candidates_dem.json", "candidates_gop.json"],
    "State demographics": ["states.json"],
}
NAMES = {
    "en.wikipedia.org": "Wikipedia", "nbcnews.com": "NBC News", "docs.google.com": "The Downballot (data sheets)",
    "the-downballot.com": "The Downballot", "apnews.com": "Associated Press", "cbsnews.com": "CBS News",
    "abcnews.com": "ABC News", "nytimes.com": "New York Times", "api.census.gov": "U.S. Census Bureau",
    "census.gov": "U.S. Census Bureau", "www2.census.gov": "U.S. Census Bureau", "polymarket.com": "Polymarket",
    "echeloninsights.com": "Echelon Insights", "defirate.com": "DeFi Rate (Kalshi odds)", "split-ticket.org": "Split Ticket",
    "gelliottmorris.com": "Strength in Numbers (G. Elliott Morris)", "bridgemi.com": "Bridge Michigan", "calmatters.org": "CalMatters",
    "api.sos.ca.gov": "California Secretary of State", "flelectionfiles.floridados.gov": "Florida Division of Elections",
    "election.lab.ufl.edu": "University of Florida Election Lab", "ava.prri.org": "PRRI", "circle.tufts.edu": "Tufts CIRCLE",
}


def urls(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from urls(v)
    elif isinstance(o, list):
        for v in o:
            yield from urls(v)
    elif isinstance(o, str) and o.startswith("http"):
        yield o


def domain(u):
    d = urlparse(u).netloc.lower()
    return d[4:] if d.startswith("www.") else d


inventory, total = [], Counter()
for label, files in DATASETS.items():
    c = Counter()
    for f in files:
        c.update(domain(u) for u in urls(json.loads((RES / f).read_text())))
    total.update(c)
    inventory.append({
        "dataset": label, "citations": sum(c.values()), "domains": len(c),
        "top": [{"domain": d, "name": NAMES.get(d, d), "citations": n} for d, n in c.most_common(8)],
    })
nyt_share = sum(n for d, n in total.items() if "nytimes" in d)
sources = {
    "total_citations": sum(total.values()), "total_domains": len(total), "nyt_citations": nyt_share,
    "datasets": inventory,
    "user_supplied": ["New York Times Voter Trends page, supplied as a PDF (nytimes.com cannot be fetched automatically)"],
}

OUT.mkdir(parents=True, exist_ok=True)
for name, obj in [("group_sources.json", group_sources), ("geo_shifts.json", geo_shifts), ("sources.json", sources)]:
    (OUT / name).write_text(json.dumps(obj, indent=1))
print(f"groups {len(groups)}; places {len(places)}; sources {sources['total_domains']} domains / {sources['total_citations']} citations (NYT {nyt_share})")
for s in summary:
    print(f"  {s['kind']:28} n={s['n']:2} median relative {s['median_relative']}")
for g in groups:
    print(f"  {g['group']:18} NYT shift {g['nyt']['shift']:>4}  SSRS shift {g['ssrs'] and g['ssrs']['shift']}")
