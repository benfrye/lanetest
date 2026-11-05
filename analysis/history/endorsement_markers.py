"""Extract, for each Democratic nominee, the Democratic-primary description line and endorsement list
from the PRE-ELECTION revision of the Wikipedia "<year> United States House of Representatives
elections in <State>" page (research/history/raw/statepages/), and scan it for group markers.

Output: research/history/raw/markers_endorse_<year>.json
  {race_id: {"name", "desc", "endorsers": [...], "markers": [...], "main_article": ..., "source": permalink}}
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_races import norm, same_person  # noqa: E402
from parse_wiki import STATES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SP = ROOT / "research" / "history" / "raw" / "statepages"
CODE2NAME = {v: k for k, v in STATES.items()}

MARKERS = {
    "Justice Democrats": r"Justice Democrats",
    "Our Revolution": r"Our Revolution",
    "DSA": r"Democratic Socialists of America|\bDSA\b",
    "Working Families": r"Working Families",
    "Sunrise": r"Sunrise Movement|\bSunrise\b",
    "Bernie Sanders": r"Bernie Sanders",
    "Elizabeth Warren": r"Elizabeth Warren",
    "PCCC": r"Progressive Change Campaign Committee|PCCC",
    "CPC PAC": r"Progressive Caucus|CPC PAC",
    "PDA": r"Progressive Democrats of America",
    "Brand New Congress": r"Brand New Congress",
    "Democracy for America": r"Democracy for America",
    "Squad member": r"Ocasio-Cortez|Ilhan Omar|Rashida Tlaib|Ayanna Pressley",
    "Blue Dog": r"Blue Dog",
    "New Democrat": r"New Democrat|NewDem",
    "Problem Solvers / No Labels": r"Problem Solvers|No Labels",
    "DCCC Red to Blue": r"Red to Blue",
    "DCCC": r"Democratic Congressional Campaign Committee|\bDCCC\b",
    "EMILY's List": r"EMILY'?s List",
    "VoteVets": r"VoteVets",
    "With Honor": r"With Honor",
    "DMFI": r"Democratic Majority for Israel|DMFI",
    "AIPAC/UDP": r"AIPAC|United Democracy Project",
    "Medicare for All (desc)": r"Medicare for All|single-payer|single payer",
    "Collective PAC": r"Collective PAC",
    "Indivisible": r"Indivisible",
    "Swing Left / Run for Something": r"Swing Left|Run for Something",
}


def strip(t):
    t = re.sub(r"<ref[^>/]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    return t


def link_text(s):
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\{\{\s*[Ss]ortname\|([^|}]*)\|([^|}]*)(?:\|[^}]*)?\}\}", r"\1 \2", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def load(year, st):
    p = SP / f"{year}_{CODE2NAME[st].replace(' ', '_')}.json"
    if not p.exists():
        return None, None
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None, None
    pg = d["query"]["pages"][0]
    if "revisions" not in pg:
        return None, None
    rev = pg["revisions"][0]
    return strip(rev["slots"]["main"]["content"]), f"https://en.wikipedia.org/w/index.php?title={pg['title'].replace(' ', '_')}&oldid={rev['revid']}"


def district_sections(t, at_large):
    """yield (district_number, text)"""
    hs = list(re.finditer(r"^(==+)\s*(District\s+(\d+)|At[- ]large[^=]*)\s*\1\s*$", t, re.M | re.I))
    out = {}
    for i, m in enumerate(hs):
        lvl = len(m.group(1))
        end = len(t)
        for m2 in re.finditer(r"^(==+)[^=].*?\1\s*$", t[m.end():], re.M):
            if len(m2.group(1)) <= lvl:
                end = m.end() + m2.start()
                break
        dn = int(m.group(3)) if m.group(3) else 0
        out.setdefault(dn, t[m.start():end])
    if not out and at_large:
        out[0] = t
    return out


def dem_primary(sec):
    m = re.search(r"^(=+)\s*Democratic(?:[- –]+[A-Za-z\- ]+)?\s+(primary|convention|nomination|candidates?)\b.*?\1\s*$", sec, re.M | re.I)
    if not m:
        m = re.search(r"^(=+)\s*(Democratic[^=]*)\1\s*$", sec, re.M)
    if not m:
        return ""
    lvl = len(m.group(1))
    rest = sec[m.end():]
    for m2 in re.finditer(r"^(=+)[^=].*?\1\s*$", rest, re.M):
        if len(m2.group(1)) <= lvl:
            return rest[:m2.start()]
    return rest


HEAD = re.compile(r"(\{\{\s*Endorsements box\s*\|\s*title\s*=\s*(?P<a>[^\n|]*)|\{\{\s*[Cc]ollapse top\s*\|\s*(?:title\s*=\s*)?(?P<b>[^\n|}]*)|^;\s*(?P<c>[^\n]+)$|^'''(?P<d>[^']+)'''\s*$|^=+\s*(?P<e>[^=\n]+?)\s*=+\s*$)", re.M)


BOX = re.compile(r"\{\{\s*(?:Endorsements box|[Cc]ollapse top)\s*\n?\s*\|\s*(?:title\s*=\s*)?(?P<t>[^\n|}]*)", re.I)
HEAD2 = re.compile(r"^;\s*(?P<c>[^\n]+)$", re.M)


def _owns(name, title):
    core = re.sub(r"(?i)endorsements?( for| of)?|candidates?|nominee|results", "", link_text(title or "")).strip(" :")
    return bool(core) and (same_person(name, core) or (bool(norm(name)) and norm(name)[-1] in norm(core)))


def nominee_blocks(dp, name):
    """Text owned by the nominee: endorsement boxes titled with the nominee (preferred), else ';Name' heads."""
    boxes = list(BOX.finditer(dp))
    own = []
    if boxes:
        for i, h in enumerate(boxes):
            end = boxes[i + 1].start() if i + 1 < len(boxes) else len(dp)
            if _owns(name, h.group("t")):
                own.append(dp[h.end():end])
        return "\n".join(own)
    heads = list(HEAD2.finditer(dp))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(dp)
        if _owns(name, h.group("c")):
            own.append(dp[h.end():end])
    return "\n".join(own)


def desc_line(dp, name):
    last = norm(name)[-1] if norm(name) else None
    for ln in dp.split("\n"):
        if ln.startswith("*") and last and last in " ".join(norm(link_text(ln))):
            return link_text(ln)[:400]
    return ""


def main(year):
    races = json.loads((ROOT / "research" / "history" / f"house_{year}.json").read_text())["races"]
    out = {}
    cache = {}
    stats = {"no_page": 0, "no_section": 0, "no_dem_primary": 0, "with_endorsements": 0, "n": 0}
    for r in races:
        d = r.get("dem")
        if not d:
            continue
        stats["n"] += 1
        st = r["state"]
        if st not in cache:
            cache[st] = load(year, st)
        t, url = cache[st]
        rec = {"name": d["name"], "source": url, "desc": "", "endorsers": [], "markers": [], "main_article": None}
        if t is None:
            stats["no_page"] += 1
            out[r["id"]] = rec
            continue
        dn = 0 if r["district"] == "AL" else r["district"]
        secs = district_sections(t, r["district"] == "AL")
        sec = secs.get(dn)
        if sec is None:
            stats["no_section"] += 1
            out[r["id"]] = rec
            continue
        mm = re.search(r"\{\{\s*[Mm]ain(?: article)?\s*\|\s*([^}|]+)", sec)
        if mm:
            rec["main_article"] = "https://en.wikipedia.org/wiki/" + mm.group(1).strip().replace(" ", "_")
        dp = dem_primary(sec)
        if not dp:
            stats["no_dem_primary"] += 1
        rec["desc"] = desc_line(dp or sec, d["name"])
        own = nominee_blocks(dp, d["name"]) if dp else ""
        if own:
            stats["with_endorsements"] += 1
            ends = []
            for ln in own.split("\n"):
                if ln.strip().startswith("*"):
                    ends.append(link_text(ln.strip(" *"))[:120])
            rec["endorsers"] = [e for e in ends if e][:80]
        scan = own + "\n" + rec["desc"]
        for k, pat in MARKERS.items():
            if re.search(pat, scan, re.I):
                rec["markers"].append(k)
        out[r["id"]] = rec
    p = ROOT / "research" / "history" / "raw" / f"markers_endorse_{year}.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    from collections import Counter
    print(year, stats, Counter(m for v in out.values() for m in v["markers"]).most_common(30))


if __name__ == "__main__":
    for y in sys.argv[1:]:
        main(int(y))
