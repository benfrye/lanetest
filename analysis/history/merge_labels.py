"""Merge coder labels (research/history/label_work/labels_<year>_<k>.json) with rule labels for safe-seat
incumbents and defaults for safe-seat challengers into research/history/labels_<year>.json.

Also builds a marker-only label set (robustness, like METHODOLOGY §2.5 Set B):
  ideology: left if Justice Democrats / Our Revolution / Working Families / DSA marker;
            moderate if Blue Dog (member or PAC-endorsed) / Problem Solvers / NewDem Action Fund / New Dem member;
            else liberal.  posture: the coder's posture where researched, else establishment.
"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
H = ROOT / "research" / "history"
LW = H / "label_work"
RAW = H / "raw"

ARCH = {("left", "populist"): "left_populist", ("liberal", "populist"): "left_populist",
        ("moderate", "populist"): "center_populist", ("conservative", "populist"): "center_populist",
        ("left", "mixed"): "progressive", ("left", "establishment"): "progressive",
        ("moderate", "mixed"): "moderate", ("moderate", "establishment"): "moderate",
        ("conservative", "mixed"): "moderate", ("conservative", "establishment"): "moderate",
        ("liberal", "mixed"): "mainstream_liberal", ("liberal", "establishment"): "mainstream_liberal"}
LEFT_M = {"Justice_Democrats_endorsed", "Our Revolution", "Working Families", "DSA"}
MOD_M = {"Blue_Dog_member", "Problem_Solvers_member", "Blue Dog PAC (endorsed)", "Blue Dog PAC (member)",
         "NewDem Action Fund", "New_Dem_member"}


def main(year):
    tiers = json.loads((LW / f"tiers_{year}.json").read_text())
    coded = {}
    for f in sorted(glob.glob(str(LW / f"labels_{year}_*.json"))):
        d = json.loads(Path(f).read_text())
        for k, v in d["labels"].items():
            v["coder"] = d.get("coder", Path(f).stem)
            coded[k] = v
    out = {}
    issues = []
    for rid, t in tiers.items():
        if t["tier"].startswith("research") or rid in coded:
            v = coded.get(rid)
            if v is None:
                issues.append(f"{rid}: research tier but no coder label")
                continue
            arch = ARCH.get((v["ideology"], v["posture"]))
            if arch != v["archetype"]:
                issues.append(f"{rid}: archetype {v['archetype']} != mapping {arch}; mapping used")
            out[rid] = {"name": v["name"], "ideology": v["ideology"], "posture": v["posture"], "archetype": arch,
                        "style_confidence": v["style_confidence"], "style_evidence": v["style_evidence"],
                        "label_source_url": v.get("label_source_url"), "verified_fetch": v.get("verified_fetch"),
                        "label_tier": t["tier"], "coder": v["coder"]}
        elif t["tier"] == "rule_incumbent_safe":
            mk = set(t["markers"])
            note = []
            if "CPC_member" in mk:
                note.append("CPC member (plain CPC membership = liberal, as in 2026 coding)")
            if "New_Dem_member" in mk:
                note.append("New Democrat Coalition member in a safe seat (= liberal by rubric)")
            out[rid] = {"name": t["name"], "ideology": "liberal", "posture": "establishment", "archetype": "mainstream_liberal",
                        "style_confidence": "medium" if note else "low",
                        "style_evidence": "Rule label, safe-seat incumbent with no left/moderate marker in the pre-election caucus and group lists checked"
                                          + (": " + "; ".join(note) if note else "."),
                        "label_source_url": (t["marker_sources"] or [None])[0], "verified_fetch": bool(note),
                        "label_tier": t["tier"], "coder": "rule"}
        else:
            out[rid] = {"name": t["name"], "ideology": "liberal", "posture": "establishment", "archetype": "mainstream_liberal",
                        "style_confidence": "low",
                        "style_evidence": "Default: safe-seat challenger not individually researched; no left/moderate marker in the pre-election group lists checked (JD, Our Revolution, PCCC, WFP, Blue Dog PAC, NewDem Action Fund).",
                        "label_source_url": None, "verified_fetch": False, "label_tier": t["tier"], "coder": "default"}
        # marker-only robustness label
        mk = set(t["markers"])
        ide = "left" if mk & LEFT_M else ("moderate" if mk & MOD_M else "liberal")
        post = out[rid]["posture"] if out[rid]["coder"] not in ("rule", "default") else "establishment"
        out[rid]["rule_archetype"] = ARCH[(ide, post)]
        out[rid]["markers"] = sorted(mk)
    (H / f"labels_{year}.json").write_text(json.dumps({"cycle": year, "rubric": "research/history/label_work/RUBRIC.md",
                                                       "labels": out, "merge_issues": issues}, indent=1, ensure_ascii=False))
    print(year, len(out), Counter(v["archetype"] for v in out.values()), Counter(v["label_tier"] for v in out.values()))
    print("  rule set:", Counter(v["rule_archetype"] for v in out.values()))
    print("  conf:", Counter(v["style_confidence"] for v in out.values()), "issues:", issues[:10])


if __name__ == "__main__" and (len(sys.argv) < 2 or sys.argv[1] != "pres"):
    for y in sys.argv[1:]:
        main(int(y))


def merge_pres(year):
    """2020/2024: carried labels (carry_<year>.json) + coder labels for new competitive/open nominees + default."""
    carry = json.loads((LW / f"carry_{year}.json").read_text())
    coded = {}
    for f in sorted(glob.glob(str(LW / f"labels_{year}_*.json"))):
        d = json.loads(Path(f).read_text())
        for k, v in d["labels"].items():
            v["coder"] = d.get("coder", Path(f).stem)
            coded[k] = v
    R = [r for r in json.loads((H / f"house_{year}.json").read_text())["races"] if r["included"]]
    out, issues = {}, []
    for r in R:
        rid = r["id"]
        if rid in coded:
            v = coded[rid]
            out[rid] = {"name": v["name"], "ideology": v["ideology"], "posture": v["posture"],
                        "archetype": ARCH.get((v["ideology"], v["posture"])), "style_confidence": v["style_confidence"],
                        "style_evidence": v["style_evidence"], "label_source_url": v.get("label_source_url"),
                        "verified_fetch": v.get("verified_fetch"), "label_tier": "research_new_nominee", "coder": v["coder"]}
        elif rid in carry:
            out[rid] = carry[rid]
        else:
            out[rid] = {"name": r["dem"]["name"], "ideology": "liberal", "posture": "establishment",
                        "archetype": "mainstream_liberal", "style_confidence": "low",
                        "style_evidence": "Default: safe-seat nominee not coded in the previous midterm and not individually researched.",
                        "label_source_url": None, "verified_fetch": False, "label_tier": "default_safe_challenger", "coder": "default"}
        out[rid].setdefault("rule_archetype", None)
    (H / f"labels_{year}.json").write_text(json.dumps({"cycle": year, "rubric": "research/history/label_work/RUBRIC.md",
                                                       "labels": out, "merge_issues": issues}, indent=1, ensure_ascii=False))
    print(year, len(out), Counter(v["archetype"] for v in out.values()), Counter(v["label_tier"] for v in out.values()))
    print("  conf:", Counter(v["style_confidence"] for v in out.values()))


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "pres":
    for y in sys.argv[2:]:
        merge_pres(int(y))
