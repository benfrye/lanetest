"""Caucus / group markers for each cycle's Democratic House nominees, read from Wikipedia revisions
dated BEFORE that election (saved under research/history/raw/caucus/). Matches by name to the
nominees in research/history/house_<year>.json.

Output: research/history/raw/markers_caucus_<year>.json  {race_id: [{"marker":..., "source":...}]}
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_races import same_person  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CAU = ROOT / "research" / "history" / "raw" / "caucus"
TS = {2018: "2018-11-05", 2020: "2020-11-02", 2022: "2022-11-07", 2024: "2024-11-04"}


def page(title, year):
    p = CAU / f"{title}_{TS[year]}.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text())
    pg = d["query"]["pages"][0]
    if "revisions" not in pg:
        return None, None
    rev = pg["revisions"][0]
    url = f"https://en.wikipedia.org/w/index.php?title={title}&oldid={rev['revid']}"
    return rev["slots"]["main"]["content"], url


def section(t, start_pat, end_pats):
    m = re.search(start_pat, t, re.M)
    if not m:
        return ""
    rest = t[m.end():]
    end = len(rest)
    for ep in end_pats:
        e = re.search(ep, rest, re.M)
        if e:
            end = min(end, e.start())
    return rest[:end]


def names(txt):
    out = []
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", txt):
        nm = m.group(2) or m.group(1)
        nm = re.sub(r"\s*\(.*?\)", "", nm)
        out.append(nm.strip())
    for m in re.finditer(r"\{\{\s*[Ss]ortname\|([^|}]*)\|([^|}]*)", txt):
        out.append(f"{m.group(1)} {m.group(2)}")
    return out


def extract(year):
    sets = {}
    srcs = {}
    # Congressional Progressive Caucus: House members section
    t, u = page("Congressional_Progressive_Caucus", year)
    if t:
        s = section(t, r"^==+\s*House members\s*==+", [r"^==+\s*(Senate members|Former members|See also)"])
        sets["CPC_member"] = names(s)
        srcs["CPC_member"] = u
    # Blue Dog: dedicated list page (members section only, before "Former")
    t, u = page("List_of_members_of_the_Blue_Dog_Coalition", year)
    if t:
        s = section(t, r"^==\s*Members for the 11\dth Congress.*$", [r"^==\s*\S"])
        sets["Blue_Dog_member"] = names(s)
        srcs["Blue_Dog_member"] = u
    t, u = page("Blue_Dog_Coalition", year)
    if t:
        s = section(t, r"^==+\s*Members of the Blue Dog Coalition\s*==+", [r"^==\s*(See also|References)"])
        if s:
            sets["Blue_Dog_member"] = sets.get("Blue_Dog_member", []) + names(s)
    # New Democrat Coalition
    t, u = page("New_Democrat_Coalition", year)
    if t:
        s = section(t, r"^==+\s*(New Democrat Coalition members \(House\)|Membership|Members)\s*==+", [r"^===+\s*Former", r"^==\s*(See also|References|Former Senate)"])
        sets["New_Dem_member"] = names(s)
        srcs["New_Dem_member"] = u
    # Problem Solvers
    t, u = page("Problem_Solvers_Caucus", year)
    if t:
        s = section(t, r"^==+\s*(Membership|Members|Current members)\s*==+", [r"^==+\s*(Former|See also|References|Media)"])
        sets["Problem_Solvers_member"] = names(s)
        srcs["Problem_Solvers_member"] = u
    # Justice Democrats: House candidate tables / congressional members (endorsement, any primary result)
    t, u = page("Justice_Democrats", year)
    if t:
        if year == 2018:
            tab = section(t, r"^===\s*Candidates for U\.S\. House\s*===", [r"^===\s*Summer"])
            # candidate column only: first cell of each table row
            s = "\n".join(re.sub(r"^\|\s*(rowspan=\d+\s*\|)?", "", blk.strip().split("\n")[1]) for blk in tab.split("|- ")[1:] if len(blk.strip().split("\n")) > 1) + section(t, r"^===\s*Congressional members[^=]*===", [r"^===\s*Notes", r"^==\s*See"])
        else:
            s = section(t, rf"^===\s*{year}\s*===", [r"^===\s*(\d{{4}}|Summer)"]) + section(t, r"^===\s*Congressional members[^=]*===", [r"^===\s*Notes", r"^==\s*See"])
        sets["Justice_Democrats_endorsed"] = names(s)
        srcs["Justice_Democrats_endorsed"] = u
    return sets, srcs


def main(year):
    races = json.loads((ROOT / "research" / "history" / f"house_{year}.json").read_text())["races"]
    sets, srcs = extract(year)
    out = {}
    for r in races:
        d = r.get("dem")
        if not d:
            continue
        hits = []
        for k, ns in sets.items():
            # incumbent-only caucuses must match a sitting member: require nominee is the incumbent,
            # except JD (endorses challengers)
            if k != "Justice_Democrats_endorsed" and not d["incumbent"]:
                continue
            if any(same_person(d["name"], n) for n in ns):
                hits.append({"marker": k, "source": srcs.get(k)})
        if hits:
            out[r["id"]] = {"name": d["name"], "markers": hits}
    p = ROOT / "research" / "history" / "raw" / f"markers_caucus_{year}.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    from collections import Counter
    print(year, {k: len(v) for k, v in sets.items()}, Counter(h["marker"] for v in out.values() for h in v["markers"]))


if __name__ == "__main__":
    for y in sys.argv[1:]:
        main(int(y))
