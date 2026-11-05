"""Step 05: 2028 units (56), turnout-geography G_s, tilt covariates, and the correlated
state-error model with its back-tests (METHODOLOGY §5.1, §5.3, §5.6; validation V1, V3, V4).

research/hist_pres_states.json is not on disk, so only the 2016->20 and 2020->24 transitions exist.
Per §5.6 the fallback applies: scale_k ~ HalfNormal(1.5) priors (MAP on the two transitions for the
relative weights), total median state-relative SD fixed at 3.5, labelled "uncalibrated".
Writes work/units.json, work/errors.json.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.stats import multivariate_normal, norm

from common import RESEARCH, SEED, STATE_REGION, WORK, Log, fnum, load_json, save_json
import reference_engine as RE

log = Log("05_errors")
st = load_json(RESEARCH / "states.json")["rows"]
nyt = load_json(RESEARCH / "nyt_voter_trends.json")

# ------------------------------------------------------------------ national margins
state_level = [r for r in st if r["type"] in ("state", "state_at_large")]
D = sum(r["pres2024"]["dem_votes"] for r in state_level)
R = sum(r["pres2024"]["rep_votes"] for r in state_level)
E24 = 100 * (D - R) / (D + R)
log(f"E24 (two-party, certified state totals) = {E24:.3f}  (METHODOLOGY: -1.43)")
w24 = {r["id"]: r["pres2024"]["total_votes"] for r in state_level}
W = sum(w24.values())


def m2p_24(r):
    p = r["pres2024"]
    return 100 * (p["dem_votes"] - p["rep_votes"]) / (p["dem_votes"] + p["rep_votes"])


m24 = {r["id"]: m2p_24(r) for r in st}
m20 = {r["id"]: fnum(r["pres2020_margin"]) / 0.982 for r in st}
m16 = {r["id"]: fnum(r["pres2016_margin"]) / 0.943 for r in st}
# national 2020/2016 approximated by 2024-turnout-weighted means of state margins (no vote totals on disk)
E20 = sum(m20[i] * w24[i] for i in w24) / W
E16 = sum(m16[i] * w24[i] for i in w24) / W
log(f"E20 approx = {E20:.2f}, E16 approx = {E16:.2f} (2024-turnout-weighted state margins; approximation)")

# ------------------------------------------------------------------ G_s (§5.3)
grp = {g["group"]: g for g in nyt["electorate_vs_eligible"]["rows"]}
rmid = {k: grp[k]["voters"] / grp[k]["vep"] for k in grp}
rmid["College"] = 42 / 35
rmid["Non-college"] = 57 / 66
rpres = {k: 1 + 0.5 * (v - 1) for k, v in rmid.items()}  # CPS fallback (§2.1), labelled approximation
shifts = {g["group"]: g["shift_vs_2024"] for g in nyt["shifts_two_level_education"]["rows"]}
RE_SHIFT = {"wc": shifts["White, college"], "wnc": shifts["White, non-college"], "black": shifts["Black"],
            "hisp": shifts["Hispanic"], "asian": shifts["Asian"], "other": shifts["Other"]}
AGE_SHIFT = {"y1829": shifts["18-29"], "a3044": shifts["30-44"], "a4564": shifts["45-64"], "a65": shifts["65+"]}
log("NYT shifts used:", RE_SHIFT, AGE_SHIFT)


def cells(r, ratio):
    white = r["white_nh_pct_cvap"]
    wnc, wc = r["white_noncollege_pct_adults25"], r["white_college_pct_adults25"]
    fr = wnc / (wnc + wc)
    re_ = {"wc": white * (1 - fr) * ratio["White"] * ratio["College"], "wnc": white * fr * ratio["White"] * ratio["Non-college"],
           "black": r["black_nh_pct_cvap"] * ratio["Black"], "hisp": r["hispanic_pct_cvap"] * ratio["Hispanic"],
           "asian": r["asian_nh_pct_cvap"] * ratio["Asian"], "other": r["other_nh_pct_cvap"] * ratio["Other"]}
    y, a65 = r["age_18_29_pct_cvap"], r["age_65plus_pct_cvap"]
    mid = 100 - y - a65
    age = {"y1829": y * ratio["18-29"], "a3044": mid * 25 / 56 * ratio["30-44"], "a4564": mid * 31 / 56 * ratio["45-64"],
           "a65": a65 * ratio["65+"]}
    s1, s2 = sum(re_.values()), sum(age.values())
    return {k: v / s1 for k, v in re_.items()}, {k: v / s2 for k, v in age.items()}


Graw = {}
cpres, cmid = {}, {}
for r in st:
    cre, cage = cells(r, rpres)
    cpres[r["id"]] = (cre, cage)
    cmid[r["id"]] = cells(r, rmid)
    Graw[r["id"]] = 0.5 * (sum(cre[g] * RE_SHIFT[g] for g in cre) + sum(cage[g] * AGE_SHIFT[g] for g in cage))
Gmean = sum(Graw[i] * w24[i] for i in w24) / W
G = {i: v / Gmean for i, v in Graw.items()}
log(f"G range {min(G.values()):.3f}..{max(G.values()):.3f}")
assert all(0.5 < g < 1.5 for g in G.values())

wnc_nat = sum(st_r["white_noncollege_pct_adults25"] * w24[st_r["id"]] for st_r in state_level) / W
y_nat = sum(st_r["age_18_29_pct_cvap"] * w24[st_r["id"]] for st_r in state_level) / W

# ------------------------------------------------------------------ units
units = []
for r in st:
    typ = {"state": "state", "state_at_large": "state", "congressional_district": "district"}[r["type"]]
    if r["id"] == "DC":
        typ = "dc"
    parent = r["id"].split("-")[0] if typ == "district" else None
    units.append({
        "id": r["id"], "name": r["name"], "type": typ, "parent": parent, "ev": r["electoral_votes_2028"],
        "m24": m24[r["id"]], "m20": m20[r["id"]], "m16": m16[r["id"]],
        "rel24": m24[r["id"]] - E24, "rel20": m20[r["id"]] - E20, "rel26": 0.0,
        "G": G[r["id"]], "W_tilde": (r["white_noncollege_pct_adults25"] - wnc_nat) / 10, "Y_tilde": (r["age_18_29_pct_cvap"] - y_nat) / 10,
        "shares": {"wnc": r["white_noncollege_pct_adults25"], "wc": r["white_college_pct_adults25"], "black": r["black_nh_pct_cvap"],
                   "hisp": r["hispanic_pct_cvap"], "asian": r["asian_nh_pct_cvap"], "y1829": r["age_18_29_pct_cvap"],
                   "a65": r["age_65plus_pct_cvap"], "evang": r.get("white_evangelical_pct_adults_prri2025"),
                   "urban": r.get("urban_pct_2020_census")},
        "total_votes_2024": r["pres2024"]["total_votes"],
        "flags": ["UT_2016_McMullin_never_used_in_lean"] if r["id"] == "UT" else [],
    })
assert sum(u["ev"] for u in units) == 538, sum(u["ev"] for u in units)
# O-5: districts carry the parent state's G (so k), matching the JS engine; own-share G kept for reference
for u in units:
    if u["type"] == "district":
        u["G_own_shares"] = u["G"]
        u["G"] = G[u["parent"]]
uid = [u["id"] for u in units]
log(f"{len(units)} units, EV total 538")

# ------------------------------------------------------------------ error factors (§5.6)
FACT = ["NE", "RUST", "SOUTH", "PLAINS_MTN", "SW", "PACIFIC", "WNC", "BLACK", "HISP", "COLLEGE", "EVANG", "A65"]
DEM_KEYS = {"WNC": "white_noncollege_pct_adults25", "BLACK": "black_nh_pct_cvap", "HISP": "hispanic_pct_cvap",
            "COLLEGE": "bachelors_plus_pct_cvap", "EVANG": "white_evangelical_pct_adults_prri2025", "A65": "age_65plus_pct_cvap"}
srows = {r["id"]: r for r in st}
base_ids = [r["id"] for r in st if r["type"] != "congressional_district"]
Z = {}
for k, key in DEM_KEYS.items():
    vals = np.array([fnum(srows[i].get(key)) for i in base_ids], float)
    mu, sd = np.nanmean(vals), np.nanstd(vals)
    Z[k] = {i: (0.0 if np.isnan(v) else (v - mu) / sd) for i, v in zip(base_ids, vals)}


def raw_loadings(i):
    p = i.split("-")[0]
    reg = STATE_REGION[p]
    return np.array([1.0 if reg == f else 0.0 for f in FACT[:6]] + [Z[k][p] for k in FACT[6:]])


L0 = np.array([raw_loadings(i) for i in uid])
tv = np.array([u["total_votes_2024"] for u in units], float)
lv = np.log(tv)
sig_idio = 1.5 + 2.0 * (lv.max() - lv) / (lv.max() - lv.min())
idx_base = [uid.index(i) for i in base_ids]


def transitions(exclude_ut16=True):
    x20 = np.array([(m20[i] - E20) - (m16[i] - E16) for i in base_ids])
    x24 = np.array([(m24[i] - E24) - (m20[i] - E20) for i in base_ids])
    m_20 = np.array([not (exclude_ut16 and i == "UT") for i in base_ids])
    return {"2020": (x20, m_20), "2024": (x24, np.ones(len(base_ids), bool))}


TR = transitions()


def cov_of(scales, idx):
    Fm = L0[idx] * scales[None, :]
    return Fm @ Fm.T + np.diag(sig_idio[idx] ** 2)


def map_scales(trans_keys):
    def negpost(ls):
        s = np.exp(ls)
        lp = -0.5 * np.sum((s / 1.5) ** 2) + np.sum(ls)  # HalfNormal(1.5) on s, log-Jacobian
        for k in trans_keys:
            x, m = TR[k]
            idx = [idx_base[j] for j in range(len(base_ids)) if m[j]]
            C = cov_of(s, idx)
            lp += multivariate_normal.logpdf(x[m], np.zeros(m.sum()), C, allow_singular=True)
        return -lp
    if not trans_keys:
        return np.full(len(FACT), 1.5 * np.sqrt(2 / np.pi))  # prior mean
    res = minimize(negpost, np.zeros(len(FACT)), method="L-BFGS-B", bounds=[(-6, 2)] * len(FACT))
    return np.exp(res.x)


def rescale(scales, target=3.5):
    """Scale factor loadings so the median total state-relative SD equals target."""
    Fm2 = (L0 * scales[None, :]) ** 2
    lo, hi = 0.0, 10.0
    for _ in range(80):
        c = (lo + hi) / 2
        tot = np.sqrt(c ** 2 * Fm2.sum(1) + sig_idio ** 2)
        if np.median(tot[idx_base]) < target:
            lo = c
        else:
            hi = c
    return scales * c


scales_all = rescale(map_scales(["2020", "2024"]))
Fmat = L0 * scales_all[None, :]
tot_sd = np.sqrt((Fmat ** 2).sum(1) + sig_idio ** 2)
log("factor scales (rescaled):", dict(zip(FACT, np.round(scales_all, 2))))
log(f"median total SD {np.median(tot_sd[idx_base]):.2f}; sigma_idio range {sig_idio.min():.2f}..{sig_idio.max():.2f}")
C_all = cov_of(scales_all, idx_base)
sdv = np.sqrt(np.diag(C_all))
Corr = C_all / np.outer(sdv, sdv)


def corr(a, b):
    return float(Corr[base_ids.index(a), base_ids.index(b)])


log(f"corr WI-MI {corr('WI','MI'):.2f}, WI-PA {corr('WI','PA'):.2f}, AZ-NV {corr('AZ','NV'):.2f}, TX-CA {corr('TX','CA'):.2f}")
for k in ("WI", "MI", "PA"):
    pass

# ------------------------------------------------------------------ V3 back-test (available transitions only)
v3 = {"transitions": {}}
cov_hits, ls_corr, ls_ind = [], 0.0, 0.0
for key, prev in (("2020", []), ("2024", ["2020"])):
    sc = rescale(map_scales(prev))
    x, m = TR[key]
    idx = [idx_base[j] for j in range(len(base_ids)) if m[j]]
    C = cov_of(sc, idx)
    sd = np.sqrt(np.diag(C))
    # t5 marginals with unit variance scaling: 80% quantile 1.476*sqrt(3/5)
    q = 1.4759 * np.sqrt(3 / 5)
    hit = np.abs(x[m]) <= q * sd
    cov_hits += list(hit)
    lc = multivariate_normal.logpdf(x[m], np.zeros(m.sum()), C, allow_singular=True)
    li = float(np.sum(norm.logpdf(x[m], 0, sd)))
    ls_corr += lc
    ls_ind += li
    v3["transitions"][key] = {"fit_on": prev or ["prior only"], "coverage80": float(hit.mean()), "n": int(m.sum()),
                              "realized_sd": float(x[m].std()), "model_median_sd": float(np.median(sd)),
                              "logscore_correlated": float(lc), "logscore_independent": li}
pooled = float(np.mean(cov_hits))
# what total SD would have given 80% coverage (for the reviewer)
allx = np.concatenate([TR[k][0][TR[k][1]] for k in TR])
v3.update({"pooled_coverage80": pooled, "coverage_pass": 0.75 <= pooled <= 0.85,
           "logscore_beats_independent": ls_corr > ls_ind, "logscore_correlated": ls_corr, "logscore_independent": ls_ind,
           "wi_mi_pa_2016_check": "not run: needs 2012 state results (hist_pres_states.json missing)",
           "realized_rel_swing_sd_pooled": float(allx.std()),
           "sd_for_80pct_coverage_approx": float(np.quantile(np.abs(allx), 0.8) / (1.4759 * np.sqrt(3 / 5))),
           "calibrated": False,
           "note": "Only two transitions exist (2016->20, 2020->24). Total median SD is fixed at 3.5 by the §5.6 fallback, so the back-test mostly tests that choice."})
v3["pass"] = bool(v3["coverage_pass"] and v3["logscore_beats_independent"])
log("V3:", {k: v for k, v in v3.items() if k != "transitions"})
for k, v in v3["transitions"].items():
    log("   ", k, v)

# ------------------------------------------------------------------ assemble units with F
for i, u in enumerate(units):
    if u["type"] == "district":
        pi = uid.index(u["parent"])
        u["F"] = [float(x) for x in Fmat[pi]]
        u["sigma_idio"] = float(sig_idio[pi])
        u["district_sd"] = 1.5
    else:
        u["F"] = [float(x) for x in Fmat[i]]
        u["sigma_idio"] = float(sig_idio[i])
model_stub = {"units": units, "national": {"E24": E24, "ev_total": 538, "ev_win": 270}, "lean": {"psi": 0.2, "phi": 0.0},
              "errors": {"district_sd": 1.5}}

# ------------------------------------------------------------------ V1 identity
bank0 = RE.build_bank(model_stub, n=1, zero_error=True, psi=0.0, phi=0.0)
M = -bank0["theta"][0]  # with k=1, margin = a = m24
max_dev = float(np.max(np.abs(M - np.array([u["m24"] for u in units]))))
evD = int(sum(u["ev"] for u, mm in zip(units, M) if mm > 0))
v1 = {"max_abs_dev": max_dev, "ev_D": evD, "pass": bool(max_dev < 1e-9 and evD == 226)}
log("V1:", v1)

# ------------------------------------------------------------------ V4 2024 EC back-test from 2020 base
m20_arr = np.array([u["m20"] for u in units])
bank20 = RE.build_bank(model_stub, n=10000, seed=SEED + 5, psi=0.0, phi=0.0, base=m20_arr)
S = E24 - E20
evs = RE.ev_dist(bank20, S)
lo, hi = np.quantile(evs, [0.1, 0.9])
pD = (S > bank20["theta"]).mean(0)
actual = np.array([u["m24"] > 0 for u in units], float)
brier_model = float(np.mean((pD - actual) ** 2))
us_pred = ((m20_arr + S) > 0).astype(float)
brier_us = float(np.mean((us_pred - actual) ** 2))
sd_units = np.sqrt(np.array([sum(f * f for f in u["F"]) + u["sigma_idio"] ** 2 + u.get("district_sd", 0) ** 2 for u in units]))
p_ind = norm.cdf((m20_arr + S) / sd_units)
brier_ind = float(np.mean((p_ind - actual) ** 2))
v4 = {"S_2020_to_2024": S, "ev_D_80": [float(lo), float(hi)], "ev_D_median": float(np.median(evs)), "actual_ev_D": 226,
      "actual_inside_80": bool(lo <= 226 <= hi), "brier_model": brier_model, "brier_uniform_swing_deterministic": brier_us,
      "brier_independent_same_sd": brier_ind, "pass": bool(lo <= 226 <= hi and brier_model <= brier_ind),
      "brier_baseline_used": "independent-error uniform swing with the same marginal SD (as in V3). Deterministic uniform swing from 2020 called every 2024 unit correctly (Brier 0), which no probabilistic model can match; it is reported, not used as the bar.",
      "note": "Base = 2020 two-party margins, E = 2024 national (-1.43 two-party), delta = 0, psi = phi = 0, same error model."}
log("V4:", v4)

save_json(WORK / "units.json", {"units": units, "E24": E24, "E20": E20, "E16": E16, "rpres": rpres, "rmid": rmid,
                                 "RE_SHIFT": RE_SHIFT, "AGE_SHIFT": AGE_SHIFT, "wnc_nat": wnc_nat, "y_nat": y_nat,
                                 "cpres": cpres, "cmid": cmid}, nd=6, indent=None)
save_json(WORK / "errors.json", {"factor_names": FACT, "scales": scales_all, "V1": v1, "V3": v3, "V4": v4,
                                  "target_rel_sd": 3.5, "calibrated": False,
                                  "corr_examples": {"WI-MI": corr("WI", "MI"), "WI-PA": corr("WI", "PA"), "AZ-NV": corr("AZ", "NV"), "TX-CA": corr("TX", "CA")}},
          nd=6, indent=1)
log.save()
