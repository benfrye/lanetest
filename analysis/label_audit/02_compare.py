"""Blind relabel audit, steps 3-4: agreement, kappa, outcome correlation of disagreements, lane gaps.

Run with analysis/.venv/bin/python analysis/label_audit/02_compare.py
Inputs: research/label_audit/coded/coded_batch_*.json (blind labels), analysis/label_audit/sample_key.json,
        analysis/output/races.json (original labels and outcomes; joined only here, after blind coding).
Outputs: analysis/label_audit/audit_results.json, analysis/label_audit/audit_rows.csv
"""
import csv, glob, json, pathlib
from collections import Counter

import numpy as np
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/label_audit"
ARCH = ["progressive", "left_populist", "center_populist", "mainstream_liberal", "moderate"]
IDEO = ["left", "liberal", "moderate", "conservative"]
POST = ["populist", "mixed", "establishment"]
LCOORD = {"conservative": -1, "moderate": 0, "liberal": 1, "left": 2}
PCOORD = {"establishment": 0, "mixed": 0.5, "populist": 1}

blind = {}
for f in sorted(glob.glob(str(ROOT / "research/label_audit/coded/coded_batch_*.json"))):
    blind.update(json.load(open(f))["labels"])
key = {k["id"]: k for k in json.load(open(OUT / "sample_key.json"))["sample"]}
races = {r["id"]: r for r in json.load(open(ROOT / "analysis/output/races.json"))["races"]}
assert set(blind) == set(key), (set(key) - set(blind), set(blind) - set(key))


def derive(ideo, post):
    if ideo in ("left", "liberal") and post == "populist":
        return "left_populist"
    if ideo == "left":
        return "progressive"
    if ideo in ("moderate", "conservative"):
        return "center_populist" if post == "populist" else "moderate"
    return "mainstream_liberal"


rows = []
for rid in sorted(key):
    b, r = blind[rid], races[rid]
    arch_b = derive(b["ideology"], b["posture"])
    rows.append({
        "id": rid, "name": r["dem_name"], "office": r["office"], "state": r["state"], "stratum": key[rid]["stratum"],
        "weight": key[rid]["weight"],
        "orig_arch": r["fit_archetype"], "orig_ideo": r["ideology"], "orig_post": r["posture"],
        "orig_label_audit": r.get("label_audit"),
        "blind_arch": arch_b, "blind_arch_as_coded": b["archetype"], "blind_ideo": b["ideology"], "blind_post": b["posture"],
        "blind_conf": b["confidence"], "pre_election_verified": bool(b.get("pre_election_verified")),
        "verified_fetch": bool(b.get("verified_fetch")), "source_date": b.get("source_date"), "source_url": b.get("source_url"),
        "y": r["overperformance_model_scale"], "lean": r["pres2024_margin_2p"],
        "inc_D": float(bool(r["dem_incumbent"])), "inc_R": float(bool(r["rep_incumbent"])),
    })


def kappa(a, b, cats):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in cats) / n ** 2
    return {"n": n, "agreement": round(po, 3), "kappa": round((po - pe) / (1 - pe), 3) if pe < 1 else None}


def confusion(a, b, cats):
    return {ca: {cb: sum(1 for x, y in zip(a, b) if x == ca and y == cb) for cb in cats} for ca in cats}


def agree_block(rs):
    return {
        "archetype": kappa([r["orig_arch"] for r in rs], [r["blind_arch"] for r in rs], ARCH),
        "ideology": kappa([r["orig_ideo"] for r in rs], [r["blind_ideo"] for r in rs], IDEO),
        "posture": kappa([r["orig_post"] for r in rs], [r["blind_post"] for r in rs], POST),
    }


res = {"n": len(rows), "per_stratum": dict(Counter(r["stratum"] for r in rows)),
       "blind_lane_counts": dict(Counter(r["blind_arch"] for r in rows)),
       "coded_vs_derived_archetype_mismatch": [r["id"] for r in rows if r["blind_arch"] != r["blind_arch_as_coded"]]}
res["agreement_all"] = agree_block(rows)
pv = [r for r in rows if r["pre_election_verified"]]
res["agreement_pre_election_verified_only"] = agree_block(pv)
res["agreement_blind_high_conf_only"] = agree_block([r for r in rows if r["blind_conf"] == "high"])
res["confusion_archetype_rows_orig_cols_blind"] = confusion([r["orig_arch"] for r in rows], [r["blind_arch"] for r in rows], ARCH)
res["confusion_ideology_rows_orig_cols_blind"] = confusion([r["orig_ideo"] for r in rows], [r["blind_ideo"] for r in rows], IDEO)
res["confusion_posture_rows_orig_cols_blind"] = confusion([r["orig_post"] for r in rows], [r["blind_post"] for r in rows], POST)
res["per_stratum_archetype_agreement"] = {
    s: round(np.mean([r["orig_arch"] == r["blind_arch"] for r in rows if r["stratum"] == s]), 3) for s in ARCH}

# Evidence quality
res["evidence"] = {
    "pre_election_verified": sum(r["pre_election_verified"] for r in rows),
    "verified_fetch_any": sum(r["verified_fetch"] for r in rows),
    "memory_only": sum(not r["verified_fetch"] for r in rows),
    "wayback_snapshots_used": sum(1 for r in rows if r["source_url"] and "web.archive.org" in r["source_url"]),
    "blind_confidence": dict(Counter(r["blind_conf"] for r in rows)),
}

# Outcome-correlated mislabeling: does (orig - blind) populism / leftness / "non-mainstream" track overperformance?
y = np.array([r["y"] for r in rows])
dP = np.array([PCOORD[r["orig_post"]] - PCOORD[r["blind_post"]] for r in rows])
dL = np.array([LCOORD[r["orig_ideo"]] - LCOORD[r["blind_ideo"]] for r in rows])
pop_o = np.array([r["orig_arch"] in ("left_populist", "center_populist") for r in rows], float)
pop_b = np.array([r["blind_arch"] in ("left_populist", "center_populist") for r in rows], float)
dis = np.array([r["orig_arch"] != r["blind_arch"] for r in rows], float)


def corr(x, yv):
    if np.std(x) == 0:
        return None
    rp, pp = stats.pearsonr(x, yv)
    rs, ps = stats.spearmanr(x, yv)
    return {"pearson": round(rp, 3), "p": round(pp, 3), "spearman": round(rs, 3), "p_s": round(ps, 3)}


# residualize y on lean and incumbency so the correlation is not just seat type
Xc = np.column_stack([np.ones(len(rows)), [r["lean"] for r in rows], [r["inc_D"] for r in rows], [r["inc_R"] for r in rows]])
yres = y - Xc @ np.linalg.lstsq(Xc, y, rcond=None)[0]
res["outcome_correlation"] = {
    "posture_orig_minus_blind_vs_y": corr(dP, y), "posture_orig_minus_blind_vs_y_resid": corr(dP, yres),
    "ideology_orig_minus_blind_vs_y": corr(dL, y), "ideology_orig_minus_blind_vs_y_resid": corr(dL, yres),
    "populist_lane_orig_minus_blind_vs_y_resid": corr(pop_o - pop_b, yres),
    "any_disagreement_vs_y_resid": corr(dis, yres),
    "n_orig_more_populist": int((dP > 0).sum()), "n_blind_more_populist": int((dP < 0).sum()),
    "mean_y_resid_orig_more_populist": round(float(yres[dP > 0].mean()), 2) if (dP > 0).any() else None,
    "mean_y_resid_blind_more_populist": round(float(yres[dP < 0].mean()), 2) if (dP < 0).any() else None,
    "mean_y_resid_same_posture": round(float(yres[dP == 0].mean()), 2),
    "n_orig_populist_lane_blind_not": int(((pop_o == 1) & (pop_b == 0)).sum()),
    "n_blind_populist_lane_orig_not": int(((pop_o == 0) & (pop_b == 1)).sum()),
}
res["disagreements"] = [{k: r[k] for k in ("id", "name", "orig_arch", "blind_arch", "orig_ideo", "blind_ideo", "orig_post",
                                         "blind_post", "blind_conf", "pre_election_verified")} | {"y": round(r["y"], 1), "y_resid": round(float(e), 1)}
                        for r, e in zip(rows, yres) if r["orig_arch"] != r["blind_arch"]]


# Lane gaps: OLS, y = 50*dlogit, state FE + office FE + lean + inc_D + inc_R + archetype dummies (ref mainstream_liberal)
def ols_gaps(lab, state_fe=True, weights=None):
    states = sorted({r["state"] for r in rows})
    offices = sorted({r["office"] for r in rows})
    cols, names = [], []
    if state_fe:
        for s in states:
            cols.append([float(r["state"] == s) for r in rows]); names.append(f"fe[{s}]")
    else:
        cols.append([1.0] * len(rows)); names.append("const")
    for o in offices[1:]:
        cols.append([float(r["office"] == o) for r in rows]); names.append(f"office[{o}]")
    for c in ("lean", "inc_D", "inc_R"):
        cols.append([r[c] for r in rows]); names.append(c)
    for a in ARCH:
        if a == "mainstream_liberal":
            continue
        v = [float(r[lab] == a) for r in rows]
        if sum(v):
            cols.append(v); names.append(a)
    X = np.array(cols).T
    keep = np.abs(X).sum(0) > 0
    X, names = X[:, keep], [n for n, k in zip(names, keep) if k]
    w = np.ones(len(rows)) if weights is None else np.asarray(weights, float)
    sw = np.sqrt(w)
    Xw, yw = X * sw[:, None], y * sw
    XtXi = np.linalg.pinv(Xw.T @ Xw)
    b = XtXi @ Xw.T @ yw
    e = yw - Xw @ b
    n, k = X.shape
    rank = np.linalg.matrix_rank(Xw)
    meat = (Xw * e[:, None]).T @ (Xw * e[:, None])
    V = XtXi @ meat @ XtXi * n / max(n - rank, 1)  # HC1
    out = {"n": n, "df_resid": int(n - rank)}
    for a in ARCH:
        if a in names:
            i = names.index(a)
            nlane = int(sum(r[lab] == a for r in rows))
            out[a] = {"gap_vs_mainstream_liberal": round(b[i], 2), "se_hc1": round(float(np.sqrt(max(V[i, i], 0))), 2), "n_lane": nlane}
    return out


res["lane_gaps_50dlogit"] = {
    "spec": "OLS on overperformance_model_scale; state FE + office FE + pres2024_margin_2p + inc_D + inc_R + archetype dummies; ref = mainstream_liberal; HC1 SEs; unweighted (strata oversampled)",
    "original_labels_state_fe": ols_gaps("orig_arch"),
    "blind_labels_state_fe": ols_gaps("blind_arch"),
    "original_labels_no_fe": ols_gaps("orig_arch", state_fe=False),
    "blind_labels_no_fe": ols_gaps("blind_arch", state_fe=False),
    "original_labels_state_fe_weighted": ols_gaps("orig_arch", weights=[r["weight"] for r in rows]),
    "blind_labels_state_fe_weighted": ols_gaps("blind_arch", weights=[r["weight"] for r in rows]),
}
# raw lane means of y for context
res["raw_mean_y_by_lane"] = {
    lab: {a: (round(float(np.mean([r["y"] for r in rows if r[lab] == a])), 2), sum(r[lab] == a for r in rows)) for a in ARCH if any(r[lab] == a for r in rows)}
    for lab in ("orig_arch", "blind_arch")}

json.dump(res, open(OUT / "audit_results.json", "w"), indent=1, default=float)
with open(OUT / "audit_rows.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print(json.dumps(res, indent=1, default=float))
