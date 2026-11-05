"""Blind relabel audit, step 1: stratified random sample of main-sample races.

Strata = existing fit_archetype (used only to stratify; never written to the blind coder file).
Writes:
  analysis/label_audit/sample_key.json       (id, stratum, sampling weight)  -- NOT given to coders
  research/label_audit/blind_input.json      (id, name, state, district, office, opponent only), shuffled
"""
import json, random, collections, pathlib

SEED = 20261104
TARGET = {"center_populist": "all", "left_populist": 10, "progressive": 10, "moderate": 15, "mainstream_liberal": 41}
ROOT = pathlib.Path(__file__).resolve().parents[2]

races = json.load(open(ROOT / "analysis/output/races.json"))["races"]
main = sorted([r for r in races if r["included_in_fit"]], key=lambda r: r["id"])
by = collections.defaultdict(list)
for r in main:
    by[r["fit_archetype"]].append(r)

rng = random.Random(SEED)
sample, key = [], []
for lane in sorted(by):
    pool = by[lane]
    k = len(pool) if TARGET[lane] == "all" else min(TARGET[lane], len(pool))
    pick = rng.sample(pool, k)
    for r in pick:
        sample.append(r)
        key.append({"id": r["id"], "stratum": lane, "stratum_N": len(pool), "stratum_n": k, "weight": len(pool) / k})

rng.shuffle(sample)
blind = [{"id": r["id"], "name": r["dem_name"], "state": r["state"], "district": r["district"],
          "office": r["office"], "opponent": r["rep_name"]} for r in sample]
json.dump({"seed": SEED, "n_main": len(main), "targets": TARGET, "sample": key},
          open(ROOT / "analysis/label_audit/sample_key.json", "w"), indent=1)
json.dump({"note": "Blind coder input: name/state/district/office/opponent only.", "races": blind},
          open(ROOT / "research/label_audit/blind_input.json", "w"), indent=1)
print(len(blind), collections.Counter(k["stratum"] for k in key))
