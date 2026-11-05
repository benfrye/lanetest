"""Step 08: small JSON files for the story (analysis/output/story_data/).

raw overperformance by archetype x office, seeded quiz pairs (§3.5, decision 23), Oaxaca decomposition,
NYT nine-state table (tidy, §4.2) with the psi_P direction check, primaries linkage, ballot-measure gaps,
candidate profiles with shrunk effects, exclusion / selection summaries.
"""
import numpy as np

from common import ARCHETYPES, NON_REF, RESEARCH, SEED, STORY, WORK, Log, load_json, save_json, summ
from gibbs import Design, deltas

log = Log("08_story_data")
rows = load_json(WORK / "dataset_labeled.json")
meta = load_json(WORK / "fit_meta.json")
diag = load_json(WORK / "diagnostics.json")
rob = load_json(WORK / "robustness.json")
cands = load_json(WORK / "candidates.json")
main = [r for r in rows if r["in_main"]]
states_tbl = {r["id"]: r for r in load_json(RESEARCH / "states.json")["rows"]}
cents = {a: (v["L"], v["P"], v["n"]) for a, v in meta["centroids"].items()}
asof = load_json(RESEARCH / "senate.json")["as_of"]


def sval(st, k):
    return states_tbl.get(st, {}).get(k)


# ------------------------------------------------------------------ raw by archetype x office
raw = {"data_as_of": asof, "preliminary": True,
       "definition": "y = 2026 two-party D-R margin minus 2024 presidential two-party margin on current lines (points; + = toward D)",
       "main_sample": {}, "all_contested": {}, "common_support": {},
       "note": "Demographic distributions use STATE-level shares for every race (district ACS on current lines is not on disk)."}
for label, rs in (("main_sample", main), ("all_contested", [r for r in rows if r["in_full"] and r["office"] != "Validation2025"])):
    for a in ARCHETYPES:
        sel = [r for r in rs if r["M_archetype"] == a]
        cell = {"all": {"mean": float(np.mean([r["y"] for r in sel])) if sel else None, "n": len(sel), "n_states": len({r["state"] for r in sel})}}
        for o in ("House", "Senate", "Governor", "Special"):
            s2 = [r for r in sel if r["office"] == o]
            cell[o] = {"mean": float(np.mean([r["y"] for r in s2])) if s2 else None, "n": len(s2)}
        raw[label][a] = cell
_pv = [r["y"] for r in main if r["M_archetype"] == "progressive" and r["id"] != "GOV-VT"]
raw["main_sample"]["progressive_excluding_GOV_VT"] = {"mean": float(np.mean(_pv)), "n": len(_pv),
                                                      "note": "O-4: without Phil Scott's Vermont race (personal vote ~ -83 pts vs 2020 pres)"}
for a in ARCHETYPES:
    sel = [r for r in main if r["M_archetype"] == a]
    raw["common_support"][a] = {"m24": [round(r["m24"], 2) for r in sel],
                                "wnc_state": [sval(r["state"], "white_noncollege_pct_adults25") for r in sel],
                                "y1829_state": [sval(r["state"], "age_18_29_pct_cvap") for r in sel],
                                "hisp_state": [sval(r["state"], "hispanic_pct_cvap") for r in sel],
                                "urban_state": [sval(r["state"], "urban_pct_2020_census") for r in sel],
                                "ids": [r["id"] for r in sel]}
save_json(STORY / "raw_overperformance_by_archetype.json", raw, nd=3, indent=1)
log("raw main:", {a: (round(v["all"]["mean"], 2) if v["all"]["mean"] is not None else None, v["all"]["n"]) for a, v in raw["main_sample"].items() if "all" in v})

# ------------------------------------------------------------------ quiz pairs (seeded)
rng = np.random.default_rng(SEED + 80)


def inc_status(r):
    return "D_inc" if r["inc_D"] else ("R_inc" if r["inc_R"] else "open")


cand_pairs = []
for i in range(len(main)):
    for j in range(i + 1, len(main)):
        a, b = main[i], main[j]
        if a["M_archetype"] == b["M_archetype"] or abs(a["m24"] - b["m24"]) > 3:
            continue
        if inc_status(a) != inc_status(b) or a["rep_style"] != b["rep_style"]:
            continue
        cand_pairs.append((i, j))
order = rng.permutation(len(cand_pairs))
used, pairs = set(), []
for k in order:
    i, j = cand_pairs[k]
    if i in used or j in used:
        continue
    used |= {i, j}
    pairs.append((i, j))
    if len(pairs) == 10:
        break


def qrow(r):
    return {"id": r["id"], "name": r["dem_name"], "district": r["id"], "office": r["office"], "archetype": r["M_archetype"],
            "y": r["y"], "m24": r["m24"], "incumbency": inc_status(r), "rep_style": r["rep_style"], "rep_name": r["rep_name"],
            "pct_counted": r["pct_counted"]}


quiz = [{"a": qrow(main[i]), "b": qrow(main[j])} for i, j in pairs]
save_json(STORY / "quiz_pairs.json", {"seed": SEED + 80, "n_candidate_pairs": len(cand_pairs), "rule": "different archetypes, |dm24| <= 3, same incumbency status, same Rep style; seeded random draw without reuse",
                                      "pairs": quiz}, nd=2, indent=1)
log(f"quiz: {len(quiz)} pairs drawn from {len(cand_pairs)} eligible")

# ------------------------------------------------------------------ Oaxaca decomposition at posterior means
agn = np.load(WORK / "fit_agnostic.npz", allow_pickle=True)
D = Design(main, "M", statewide_dev=meta["statewide_dev_active"], u_active=meta["u_active"], cents=cents)
bh = agn["theta"].mean(0)
names = D.names
grp = {}
for k, nm in enumerate(names):
    if nm.startswith("spline"):
        g = "lean"
    elif nm in ("inc_D", "inc_R", "R_inc_pv", "D_inc_pv"):
        g = "incumbency"
    elif nm in ("omega_maga", "omega_mod", "rep_quality", "rep_scandal"):
        g = "opponent"
    elif nm.startswith("alpha[") or nm.startswith("lambda"):
        g = "state_wave"
    elif nm.startswith("mu["):
        g = "office"
    else:
        g = "style"
    grp.setdefault(g, []).append(k)
yadj = D.yobs + D.m_s[D.sidx] * D.shift_mult
resid = yadj - D.X @ bh
A = np.array([r["M_archetype"] for r in main])
dl = {a: v.ravel() for a, v in deltas({"theta": agn["theta"][None]}, D, cents).items()}
oax = {}
ml = A == "mainstream_liberal"
for a in NON_REF:
    sel = A == a
    if sel.sum() == 0:
        continue
    out = {"raw_gap": float(yadj[sel].mean() - yadj[ml].mean()), "n": int(sel.sum())}
    for g, ks in grp.items():
        out[g] = float(bh[ks] @ (D.X[sel][:, ks].mean(0) - D.X[ml][:, ks].mean(0)))
    out["demographic"] = 0.0
    out["residual"] = float(resid[sel].mean() - resid[ml].mean())
    out["delta_hat"] = float(dl[a].mean())
    out["check_sum"] = sum(out[g] for g in grp) + out["residual"]
    oax[a] = out
# O-4: progressive gap without GOV-VT (Phil Scott's personal vote), same posterior means
keep = np.array([r["id"] != "GOV-VT" for r in main])
selp = (A == "progressive") & keep
mlk = ml & keep
o = {"raw_gap": float(yadj[selp].mean() - yadj[mlk].mean()), "n": int(selp.sum()), "excluded": ["GOV-VT"]}
for g, ks in grp.items():
    o[g] = float(bh[ks] @ (D.X[selp][:, ks].mean(0) - D.X[mlk][:, ks].mean(0)))
o["demographic"] = 0.0
o["residual"] = float(resid[selp].mean() - resid[mlk].mean())
o["raw_mean_progressive"] = float(np.array([r["y"] for r in main])[selp].mean())
o["raw_mean_progressive_with_vt"] = float(np.array([r["y"] for r in main])[A == "progressive"].mean())
oax_excl_vt = {"progressive": o}
log("oaxaca progressive excl GOV-VT:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in o.items()})
save_json(STORY / "oaxaca_decomposition.json", {"reference": "mainstream_liberal", "by_archetype": oax, "excluding_GOV_VT": oax_excl_vt,
                                                "note": "raw_a - raw_ml = sum_k beta_k (Xbar_a,k - Xbar_ml,k) + residual gap, at agnostic posterior means. 'style' = the style columns' contribution (beta_L, beta_P, statewide d, u); delta_hat is the archetype effect at its centroid. 'demographic' is 0 because ES terms were dropped (no district demographics). 'office' = office/period intercepts. Partial counts use the expected late shift."},
          nd=3, indent=1)
log("oaxaca:", {a: {k: round(v, 2) for k, v in o.items() if isinstance(v, float)} for a, o in oax.items()})

# ------------------------------------------------------------------ NYT nine-state table (§4.2)
nyt = load_json(RESEARCH / "nyt_voter_trends.json")
ss = nyt["senate_shift_vs_2024_by_group"]
nat = {g["group"]: g["shift_vs_2024"] for g in nyt["shifts_two_level_education"]["rows"]}
nat_ed = {g["group"]: g["shift_vs_2024"] for g in nyt["groups"] if g["dimension"] == "education"}
tidy = []
tab = []
sen = {r["state"]: r for r in rows if r["office"] == "Senate"}
for j, s in enumerate(ss["states"]):
    for g, vals in ss["rows"].items():
        tidy.append({"state": s, "group": g, "shift": vals[j]})
    R = {g: v[j] for g, v in ss["rows"].items()}
    sh = 0.47 * R["Male"] + 0.53 * R["Female"]
    r = sen.get(s, {})
    tab.append({"state": s, "overall_shift": sh, "wnc_minus_wc": R["White non-college"] - R["White college"],
                "y1829_minus_65": R["18-29"] - R["65+"], "edu_gradient_resid": (R["High school"] - R["Postgraduate"]) - (nat_ed["High school"] - nat_ed["Postgraduate"]),
                "r_65": (R["65+"] - sh) - (nat["65+"] - 15), "r_wnc": (R["White non-college"] - sh) - (nat["White, non-college"] - 15),
                "dem_nominee": r.get("dem_name"), "archetype": r.get("M_archetype"), "P": r.get("P_M"), "R_inc_pv": r.get("R_inc_pv"),
                "race_file_y": r.get("y")})
grad = np.array([t["edu_gradient_resid"] for t in tab], float)
Pv = np.array([t["P"] if t["P"] is not None else 0.0 for t in tab])
Rpv = np.array([t["R_inc_pv"] or 0.0 for t in tab])
X = np.column_stack([np.ones(9), Pv, Rpv / 10])
# conjugate normal with plug-in sigma: c ~ N(0,10^2), psi_P ~ N(0,3^2), zeta ~ N(0,5^2)
b_ols = np.linalg.lstsq(X, grad, rcond=None)[0]
s2 = float(np.sum((grad - X @ b_ols) ** 2) / max(1, 9 - 3))
P0 = np.diag([1 / 100, 1 / 9, 1 / 25])
Vp = np.linalg.inv(X.T @ X / s2 + P0)
mp = Vp @ (X.T @ grad / s2)
psi = {"mean": float(mp[1]), "sd": float(np.sqrt(Vp[1, 1])), "lo80": float(mp[1] - 1.2816 * np.sqrt(Vp[1, 1])),
       "hi80": float(mp[1] + 1.2816 * np.sqrt(Vp[1, 1])), "sd_ratio": float(np.sqrt(Vp[1, 1]) / 3.0),
       "note": "grad_s = c + psi_P*P_s + zeta*R_inc_pv_s; N = 9; beta_PW is gated off, so no 'tension' test is possible."}
sds = {k: float(np.std([t[k] for t in tab], ddof=1)) for k in ("wnc_minus_wc", "y1829_minus_65", "edu_gradient_resid")}
me = next(t for t in tab if t["state"] == "ME")
save_json(STORY / "nyt_nine_state.json", {"tidy": tidy, "table": tab, "sd_across_states": sds, "psi_P": psi,
                                          "maine_discrepancy": diag["V6_maine"]["discrepancy"],
                                          "caveat": "Nine races, one Democrat each: we can't tell style from state."}, nd=3, indent=1)
log("nyt9 SDs:", sds, "psi_P:", psi)
log(f"Maine: NYT overall shift {me['overall_shift']:.2f} vs race file y {me['race_file_y']:.2f}")

# ------------------------------------------------------------------ primaries linkage
prim = load_json(RESEARCH / "primaries.json")
rid = {r["id"]: r for r in rows}


def gid(g):
    if not g:
        return None
    if g.startswith("HOUSE-"):
        st, dd = g[6:].split("-")[:2]
        return f"{st}-{int(dd)}"
    return "SEN-FL-special" if g.startswith("SEN-FL") else g


link = []
for c in prim["contests"]:
    r = rid.get(gid(c.get("race_id_general")))
    w = next((x for x in c.get("candidates") or [] if x.get("won")), {})
    link.append({"contest": c["id"], "race": r["id"] if r else None, "winner": w.get("name"), "winner_archetype": c.get("winner_archetype"),
                 "incumbent_defeated": c.get("incumbent_defeated"), "direction": c.get("ideological_direction_of_upset"),
                 "general_y": r.get("y") if r else None, "general_m26": r.get("m26") if r else None, "in_main": r.get("in_main") if r else None,
                 "general_called": r.get("called") if r else None})
summ_by = {}
for a in ARCHETYPES:
    sel = [x for x in link if x["winner_archetype"] == a and x["general_y"] is not None]
    summ_by[a] = {"n": len(sel), "mean_general_y": float(np.mean([x["general_y"] for x in sel])) if sel else None}
save_json(STORY / "primaries_linkage.json", {"contests": link, "by_winner_archetype": summ_by, "aggregates": prim["aggregates"],
                                             "close_primary_rd": diag["D6_close_primary_rd"],
                                             "note": "general_y uses all contested races (not only the main sample); the RD is a sign check only."}, nd=3, indent=1)

# ------------------------------------------------------------------ ballot-measure gaps
bm = load_json(RESEARCH / "ballot_measures.json")
ms = []
for m in bm["measures_2026"] + bm["measures_2025"]:
    ms.append({k: m.get(k) for k in ("id", "state", "title", "topic", "valence", "populist", "yes_pct", "passed",
                                     "pct_expected_vote_counted", "dem_top_of_ticket_margin_2026", "gap_measure_vs_dem")})
    ms[-1]["year"] = 2026 if m in bm["measures_2026"] else 2025
    ms[-1]["partial_count"] = (m.get("pct_expected_vote_counted") or 0) < 95
by = {}
for m in ms:
    if m["gap_measure_vs_dem"] is None:
        continue
    for key in (f"valence:{m['valence']}", f"topic:{m['topic']}", f"populist:{m['populist']}"):
        by.setdefault(key, []).append(m["gap_measure_vs_dem"])
summary = {k: {"n": len(v), "mean_gap": float(np.mean(v)), "median_gap": float(np.median(v))} for k, v in sorted(by.items())}
save_json(STORY / "ballot_measure_gaps.json", {"measures": ms, "summary": summary, "convention": bm["conventions"]}, nd=2, indent=1)

# ------------------------------------------------------------------ candidate profiles
prof = []
for c in cands["dem"]:
    cd = np.array(c["track"]["c_draws"])
    prof.append({"id": c["id"], "name": c["name"], "party": "D", "archetype": c["archetype"], "L": c["L"], "P": c["P"], "home": c["home"],
                 "track_n": c["track"]["n"], "o_hat": c["track"]["o_hat"], "w": c["track"]["w"], "c_shrunk": summ(cd),
                 "track_used": c["track_detail"]["used"], "track_dropped": c["track_detail"]["dropped"],
                 "poll_nat_primary": c["poll_nat_primary"], "market_nom": c["market_nom"],
                 "shrinkage_note": "c = 0 below 2 general elections (§3.8)" if c["track"]["n"] < 2 else None})
for c in cands["gop"]:
    cd = np.array(c["track"]["c_draws"])
    prof.append({"id": c["id"], "name": c["name"], "party": "R", "opp_type": c["opp_type"], "home": c["home"], "track_n": c["track"]["n"],
                 "o_hat": c["track"]["o_hat"], "w": c["track"]["w"], "c_shrunk": summ(cd), "track_used": c["track_detail"]["used"],
                 "track_dropped": c["track_detail"]["dropped"], "market_nom": c["market_nom"],
                 "shrinkage_note": "c = 0 below 2 general elections (§3.8)" if c["track"]["n"] < 2 else None})
save_json(STORY / "candidate_profiles.json", {"tau_c": cands["tau_c"], "sigma_r": cands["sigma_r"], "env2026": cands["env2026"],
                                              "external_env_constants": cands["external_env_constants"], "candidates": prof,
                                              "note": "Personal effect c is wave-relative, net of the Democrat's archetype effect (agnostic posterior median), shrunk with w = tau_c^2/(tau_c^2 + sigma_r^2/n). GOP c is R-positive. Midterm environments before 2025 use EXTERNAL national constants listed here (not from research files)."},
          nd=3, indent=1)

# ------------------------------------------------------------------ exclusions / selection
ex = load_json(WORK / "exclusions.json")
save_json(STORY / "sample_and_exclusions.json", {"counts": ex["counts"], "main_n": len(main), "selection_report": rob["selection_report"],
                                                 "provisional_archetypes": rob["provisional_archetypes"],
                                                 "user_flagged_uncalled": ex["user_flagged_uncalled"], "data_flag_counts": ex["data_flag_counts"]},
          nd=3, indent=1)
log.save()
