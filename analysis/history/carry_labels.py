"""Presidential-year cycles (stretch): carry labels forward from the previous midterm for nominees who were
coded then (same person, same state; the earlier label uses only evidence from before the earlier
election, so it is also pre-election evidence for this one), and write research batches for new
nominees in competitive (|pres| <= 20) or open seats. Everyone else defaults to mainstream_liberal.

2020 carries from 2018; 2024 carries from 2022.
Writes research/history/label_work/carry_<year>.json and batch_<year>_<k>.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_races import same_person  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
H = ROOT / "research" / "history"
LW = H / "label_work"
PREV = {2020: 2018, 2024: 2022}


def main(year, n_batches):
    p = PREV[year]
    R = [r for r in json.loads((H / f"house_{year}.json").read_text())["races"] if r["included"]]
    L = json.loads((H / f"labels_{p}.json").read_text())["labels"]
    P = {r["id"]: r for r in json.loads((H / f"house_{p}.json").read_text())["races"] if r.get("dem")}
    prev = [(P[k]["state"], k, v) for k, v in L.items() if k in P]
    carry, items = {}, []
    for r in R:
        hit = [(k, v) for st, k, v in prev if st == r["state"] and same_person(v["name"], r["dem"]["name"])]
        if hit and hit[0][1]["coder"] != "default":
            k, v = hit[0]
            c = dict(v)
            c["label_tier"] = f"carried_from_{p}"
            c["carried_from"] = f"{p} {k}"
            c["name"] = r["dem"]["name"]
            carry[r["id"]] = c
        elif abs(r["baseline"]["pres_margin_2p"]) <= 20 or r["open_seat"]:
            items.append({"id": r["id"], "dem_name": r["dem"]["name"], "dem_incumbent": r["dem"]["incumbent"],
                          "open_seat": r["open_seat"], "rep_name": r["rep"]["name"], "rep_incumbent": r["rep"]["incumbent"],
                          "pres_margin_2p_same_day": r["baseline"]["pres_margin_2p"],
                          "wiki_state_page": f"https://en.wikipedia.org/wiki/{year}_United_States_House_of_Representatives_elections_in_" })
    (LW / f"carry_{year}.json").write_text(json.dumps(carry, indent=1, ensure_ascii=False))
    size = -(-len(items) // n_batches)
    for b in range(n_batches):
        chunk = items[b * size:(b + 1) * size]
        (LW / f"batch_{year}_{b + 1}.json").write_text(json.dumps({"cycle": year, "election_day": {2020: "2020-11-03", 2024: "2024-11-05"}[year],
                                                                     "races": chunk}, indent=1, ensure_ascii=False))
        print(year, b + 1, len(chunk), chunk[0]["id"], "...", chunk[-1]["id"])
    print(year, "carried", len(carry))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
