"""Assign each included race a labeling tier and write research batches for the label coders.

Tiers
  research_competitive : |pres margin 2p| <= 20                       -> individually researched
  research_open        : open seat outside the window                  -> individually researched
  research_marker      : outside the window, any left/moderate marker  -> individually researched
  rule_incumbent_safe  : safe-seat incumbent, no left/moderate marker   -> rule label (CPC/NDC noted), low/medium conf
  default_safe_challenger : safe-seat challenger, no marker            -> default mainstream_liberal, low conf

Writes research/history/label_work/batch_<year>_<k>.json and tiers_<year>.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "history" / "raw"
LW = ROOT / "research" / "history" / "label_work"
LW.mkdir(exist_ok=True)

LEFT = {"Justice_Democrats_endorsed", "Our Revolution", "PCCC", "Working Families"}
MOD = {"Blue_Dog_member", "Problem_Solvers_member", "Blue Dog PAC (endorsed)", "Blue Dog PAC (member)", "NewDem Action Fund"}


def load(p):
    return json.loads(p.read_text()) if p.exists() else {}


def main(year, n_batches):
    R = json.loads((ROOT / "research" / "history" / f"house_{year}.json").read_text())["races"]
    cm = load(RAW / f"markers_caucus_{year}.json")
    gm = load(RAW / f"markers_groups_{year}.json")
    em = load(RAW / f"markers_endorse_{year}.json")
    tiers, items = {}, []
    for r in R:
        if not r["included"]:
            continue
        mk = [h for h in cm.get(r["id"], {}).get("markers", [])] + [h for h in gm.get(r["id"], {}).get("markers", [])]
        names = {h["marker"] for h in mk}
        comp = abs(r["baseline"]["pres_margin_2p"]) <= 20
        inc = r["dem"]["incumbent"]
        if comp:
            t = "research_competitive"
        elif r["open_seat"]:
            t = "research_open"
        elif names & (LEFT | MOD):
            t = "research_marker"
        elif inc:
            t = "rule_incumbent_safe"
        else:
            t = "default_safe_challenger"
        tiers[r["id"]] = {"tier": t, "name": r["dem"]["name"], "incumbent": inc, "markers": sorted(names),
                          "marker_sources": sorted({h["source"] for h in mk if h.get("source")})}
        if t.startswith("research"):
            e = em.get(r["id"], {})
            items.append({
                "id": r["id"], "dem_name": r["dem"]["name"], "dem_incumbent": inc, "open_seat": r["open_seat"],
                "rep_name": r["rep"]["name"], "rep_incumbent": r["rep"]["incumbent"],
                "pres_margin_2p": r["baseline"]["pres_margin_2p"], "pres_year": r["baseline"]["pres_year"],
                "markers_found": [{"marker": h["marker"], "source": h.get("source")} for h in mk],
                "wiki_primary_desc": e.get("desc") or None,
                "wiki_endorsement_markers": e.get("markers") or None,
                "wiki_endorsers_sample": (e.get("endorsers") or [])[:25] or None,
                "wiki_state_page_pre_election": e.get("source"),
                "wiki_district_article": e.get("main_article"),
            })
    (LW / f"tiers_{year}.json").write_text(json.dumps(tiers, indent=1, ensure_ascii=False))
    k = len(items)
    size = -(-k // n_batches)
    for b in range(n_batches):
        chunk = items[b * size:(b + 1) * size]
        (LW / f"batch_{year}_{b + 1}.json").write_text(json.dumps({"cycle": year, "election_day": {2018: "2018-11-06", 2020: "2020-11-03", 2022: "2022-11-08", 2024: "2024-11-05"}[year],
                                                                     "races": chunk}, indent=1, ensure_ascii=False))
        print(year, b + 1, len(chunk), chunk[0]["id"], "...", chunk[-1]["id"])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
