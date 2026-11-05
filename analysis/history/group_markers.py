"""Match Democratic nominees against pre-election snapshots (Wayback Machine) of group endorsement pages
saved in research/history/raw/groups/. Output: research/history/raw/markers_groups_<year>.json
"""
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "research" / "history" / "raw" / "groups"

SNAPSHOTS = {
    2018: {
        "Our Revolution": ("or_2018.html", "http://web.archive.org/web/20181104071734/https://ourrevolution.com/candidates/"),
        "PCCC": ("pccc_2018.html", "http://web.archive.org/web/20181110105324/https://www.boldprogressives.org/candidates/"),
        "Blue Dog PAC": ("bluedog_2018.html", "http://web.archive.org/web/20181022062501/https://bluedogdems.com/"),
        "DCCC Red to Blue": ("r2b_2018.html", "http://web.archive.org/web/20181030021445/https://redtoblue.dccc.org/"),
    },
    2022: {
        "PCCC": ("pccc_2022.html", "http://web.archive.org/web/20221104205821/https://www.boldprogressives.org/candidates/"),
        "Working Families": ("wfp_2022.html", "http://web.archive.org/web/20221104214919/https://workingfamilies.org/candidates/"),
        "Blue Dog PAC": ("bluedog_2022.html", "http://web.archive.org/web/20221101203156/https://bluedogdems.com/"),
        "NewDem Action Fund": ("nd_2022.html", "http://web.archive.org/web/20221105094506/http://newdemactionfund.com/candidates"),
        "DCCC Red to Blue": ("r2b_2022.html", "http://web.archive.org/web/20221101124824/https://redtoblue.dccc.org/"),
    },
}


def ascii_(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def text(fn):
    t = (G / fn).read_text(errors="ignore")
    t = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = ascii_(t)
    return re.sub(r"\s+", " ", t)


def name_in(name, t):
    n = ascii_(re.sub(r"\(.*?\)|\"[^\"]*\"", " ", name))
    toks = [x for x in re.split(r"\s+", n) if x and not re.match(r"^(Jr|Sr|II|III|IV)\.?$", x)]
    if len(toks) < 2:
        return False
    first, last = toks[0], toks[-1]
    # allow at most a middle initial between first and last name (avoids e.g. "Susan Hatch Davis" -> Susan Davis)
    pat = re.escape(first) + r"\.?\s+(?:[A-Z]\.?\s+)?" + re.escape(last) + r"\b"
    return re.search(pat, t) is not None


def main(year):
    races = json.loads((ROOT / "research" / "history" / f"house_{year}.json").read_text())["races"]
    texts = {k: (text(fn), url) for k, (fn, url) in SNAPSHOTS.get(year, {}).items()}
    out = {}
    for r in races:
        d = r.get("dem")
        if not d:
            continue
        hits = []
        for k, (t, url) in texts.items():
            if name_in(d["name"], t):
                # Blue Dog pages list members AND endorsed candidates; keep the distinction
                if k == "Blue Dog PAC":
                    i = t.find("Endorsed Candidates")
                    seg = "member" if (i < 0 or not name_in(d["name"], t[i:])) else "endorsed"
                    hits.append({"marker": f"Blue Dog PAC ({seg})", "source": url})
                else:
                    hits.append({"marker": k, "source": url})
        if hits:
            out[r["id"]] = {"name": d["name"], "markers": hits}
    p = ROOT / "research" / "history" / "raw" / f"markers_groups_{year}.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    from collections import Counter
    print(year, Counter(h["marker"] for v in out.values() for h in v["markers"]))


if __name__ == "__main__":
    for y in sys.argv[1:]:
        main(int(y))
