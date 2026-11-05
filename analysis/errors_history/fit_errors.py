"""Re-estimate the §5.6 correlated state-error model on 12 presidential transitions (1976->80 ... 2020->24).

Same structure as analysis/pipeline/05_errors.py:
  eps_s = sum_k F_sk f_k + sigma_idio_s * v_s,  f ~ N(0,1), v ~ t5 (unit variance)
  F_sk = L0_sk * scale_k   (L0 = region indicators + z-scored 2024 state covariates, exactly as 05 builds them)
  sigma_idio_s = a + b * smallness_s   (05 fixes a = 1.5, b = 2.0; here a, b are estimated)
Fit = MAP with the pipeline's HalfNormal(1.5) prior on scale_k (Gaussian likelihood on the relative-margin changes).
Variants: all 12 / last 6 / first 6 transitions, per-cycle volatility multipliers, per-state idio multipliers, fixed idio.
Recommended candidate (errors_candidate.json): shape = last-6 fit with the 05 idio form (best held-out log score on
2000-16), level = one multiplier giving 80% pooled coverage on 2000-24. Alternative: current shape rescaled
(errors_candidate_current_shape_rescaled.json). Runtime ~6 min.

Inputs (read only): research/errors_history/state_two_party.json, research/states.json, analysis/work/errors.json,
analysis/output/model_params.json. Outputs: analysis/errors_history/{fit_results.json, errors_candidate.json}.
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.stats import multivariate_normal, norm

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/errors_history"
rng = np.random.default_rng(20261104)

# ------------------------------------------------------------- structure copied from pipeline (common.py / 05_errors.py)
REGIONS = {
    "NE": ["ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "DE", "MD", "DC"],
    "RUST": ["PA", "OH", "MI", "WI", "IN", "IL", "MN", "IA"],
    "SOUTH": ["VA", "NC", "SC", "GA", "FL", "AL", "MS", "LA", "AR", "TN", "KY", "WV", "TX", "OK"],
    "PLAINS_MTN": ["ND", "SD", "NE", "KS", "MO", "MT", "WY", "ID", "UT"],
    "SW": ["AZ", "NM", "NV", "CO"],
    "PACIFIC": ["CA", "OR", "WA", "AK", "HI"],
}
STATE_REGION = {s: r for r, ss in REGIONS.items() for s in ss}
FACT = ["NE", "RUST", "SOUTH", "PLAINS_MTN", "SW", "PACIFIC", "WNC", "BLACK", "HISP", "COLLEGE", "EVANG", "A65"]
DEM_KEYS = {"WNC": "white_noncollege_pct_adults25", "BLACK": "black_nh_pct_cvap", "HISP": "hispanic_pct_cvap",
            "COLLEGE": "bachelors_plus_pct_cvap", "EVANG": "white_evangelical_pct_adults_prri2025", "A65": "age_65plus_pct_cvap"}
K = len(FACT)

st = json.load(open(ROOT / "research/states.json"))["rows"]
srows = {r["id"]: r for r in st}
uid = [r["id"] for r in st]
base_ids = [r["id"] for r in st if r["type"] != "congressional_district"]
Z = {}
for k, key in DEM_KEYS.items():
    vals = np.array([np.nan if srows[i].get(key) is None else float(srows[i][key]) for i in base_ids])
    mu, sd = np.nanmean(vals), np.nanstd(vals)
    Z[k] = {i: (0.0 if np.isnan(v) else (v - mu) / sd) for i, v in zip(base_ids, vals)}


def raw_loadings(i):
    p = i.split("-")[0]
    return np.array([1.0 if STATE_REGION[p] == f else 0.0 for f in FACT[:6]] + [Z[k][p] for k in FACT[6:]])


L0_all = np.array([raw_loadings(i) for i in uid])
lv = np.log(np.array([srows[i]["pres2024"]["total_votes"] for i in uid], float))
small_all = (lv.max() - lv) / (lv.max() - lv.min())
bidx = [uid.index(i) for i in base_ids]
L0 = L0_all[bidx]
small = small_all[bidx]
NB = len(base_ids)

# ------------------------------------------------------------- data: relative-margin changes
H = json.load(open(ROOT / "research/errors_history/state_two_party.json"))
rel = {(r["year"], r["state"]): r["rel"] for r in H["rows"]}
YEARS = list(range(1976, 2025, 4))
TRANS = [(YEARS[i], YEARS[i + 1]) for i in range(len(YEARS) - 1)]
TK = [f"{a}-{b}" for a, b in TRANS]
X = np.array([[rel[(b, s)] - rel[(a, s)] for s in base_ids] for a, b in TRANS])  # 12 x 51

# Presidential-nominee home states (home effects are modelled separately in the sim), plus UT Romney/McMullin.
HOME = {1976: {"GA", "MI"}, 1980: {"GA", "CA"}, 1984: {"MN", "CA"}, 1988: {"MA", "TX"}, 1992: {"AR", "TX"},
        1996: {"AR", "KS"}, 2000: {"TN", "TX"}, 2004: {"MA", "TX"}, 2008: {"IL", "AZ"}, 2012: {"IL", "MA", "UT"},
        2016: {"NY", "UT"}, 2020: {"DE"}, 2024: {"CA"}}


def make_mask(home=True):
    M = np.ones_like(X, bool)
    for t, (a, b) in enumerate(TRANS):
        for j, s in enumerate(base_ids):
            if s == "DC":
                M[t, j] = False  # ceiling-compressed (rel ~ +80); never pivotal
            elif home and ((s in HOME[a]) != (s in HOME[b])):
                M[t, j] = False
    return M


MASK = make_mask(True)
MASK_NOHOME = make_mask(False)


# ------------------------------------------------------------- model
def cov(scales, a, b, idx=None, eta=None):
    Lm = L0 if idx is None else L0[idx]
    sm = small if idx is None else small[idx]
    e = np.zeros(len(sm)) if eta is None else (eta if idx is None else eta[idx])
    F = Lm * scales[None, :]
    return F @ F.T + np.diag(((a + b * sm) * np.exp(e)) ** 2)


NSI = NB  # per-state idio deviations (DC fixed at 0)
DCJ = base_ids.index("DC")


def unpack(p, cyc, per):
    """p = [log scale_k (K), log a, log b, (per-state eta (NB) if per), (log c_t free (11) if cyc)]."""
    s = np.exp(p[:K]); a, b = np.exp(p[K]), np.exp(p[K + 1]); o = K + 2
    eta = np.zeros(NB)
    if per:
        eta = p[o:o + NB].copy(); eta[DCJ] = 0.0; o += NB
    lc = np.zeros(12)
    if cyc:
        lc[:11] = p[o:o + 11]; lc[11] = -np.sum(p[o:o + 11])
    return s, a, b, eta, lc


def mvn_logpdf(x, C):
    Lc = np.linalg.cholesky(C)
    z = np.linalg.solve(Lc, x)
    return -0.5 * z @ z - np.log(np.diag(Lc)).sum() - 0.5 * len(x) * np.log(2 * np.pi)


def fit(tsel, mask=MASK, fix_idio=None, cyc=False, per=False, eta_sd=0.35, lc_sd=0.6):
    tsel = list(tsel)
    def negpost(p):
        s, a, b, eta, lc = unpack(p, cyc, per)
        if fix_idio:
            a, b = fix_idio
        lp = -0.5 * np.sum((s / 1.5) ** 2) + np.sum(p[:K])  # HalfNormal(1.5) as in 05, log-Jacobian
        lp += -0.5 * (a / 3) ** 2 - 0.5 * (b / 3) ** 2 + p[K] + p[K + 1]  # weak HalfNormal(3) on idio a, b
        if per:
            lp += -0.5 * np.sum((eta / eta_sd) ** 2)
        if cyc:
            lp += -0.5 * np.sum((lc / lc_sd) ** 2)
        F = L0 * s[None, :]
        G = F @ F.T
        si2 = ((a + b * small) * np.exp(eta)) ** 2
        for t in tsel:
            idx = np.where(mask[t])[0]
            C = np.exp(2 * lc[t]) * (G[np.ix_(idx, idx)] + np.diag(si2[idx]))
            lp += mvn_logpdf(X[t, idx], C)
        return -lp
    n = K + 2 + (NB if per else 0) + (11 if cyc else 0)
    p0 = np.zeros(n); p0[K:K + 2] = np.log([1.5, 1.0])
    bnds = [(-7, 2.5)] * K + [(-4, 2.5), (-6, 2.5)] + ([(-2, 2)] * NB if per else []) + ([(-2, 2)] * 11 if cyc else [])
    r = minimize(negpost, p0, method="L-BFGS-B", bounds=bnds, options={"maxiter": 3000, "maxfun": 400000})
    s, a, b, eta, lc = unpack(r.x, cyc, per)
    if fix_idio:
        a, b = fix_idio
    return {"scales": s, "a": a, "b": b, "eta": eta, "cycle_log_scale": lc if cyc else None, "ok": bool(r.success), "nlp": float(r.fun)}


def sig_of(m, sm=None, eta=None):
    sm = small if sm is None else sm
    e = m.get("eta", np.zeros(NB)) if eta is None else eta
    return (m["a"] + m["b"] * sm) * np.exp(e)


def rescale_to(m, target):
    """05_errors.rescale: multiply factor scales so the median total SD over base states hits target."""
    Fm2 = (L0 * m["scales"][None, :]) ** 2
    si = sig_of(m)
    lo, hi = 0.0, 10.0
    for _ in range(80):
        c = (lo + hi) / 2
        if np.median(np.sqrt(c * c * Fm2.sum(1) + si ** 2)) < target:
            lo = c
        else:
            hi = c
    return {**m, "scales": m["scales"] * c, "a": m["a"] * c, "b": m["b"] * c}


def describe(m):
    C = cov(m["scales"], m["a"], m["b"], eta=m.get("eta"))
    sd = np.sqrt(np.diag(C))
    R = C / np.outer(sd, sd)
    F = L0 * m["scales"][None, :]
    fac_share = (F ** 2).sum(1) / np.diag(C)
    return C, sd, R, fac_share


# ------------------------------------------------------------- current model (as in the pipeline output)
cur_err = json.load(open(ROOT / "analysis/work/errors.json"))
current = {"scales": np.array(cur_err["scales"]), "a": 1.5, "b": 2.0}
mp = json.load(open(ROOT / "analysis/output/model_params.json"))
wi = next(u for u in mp["units"] if u["id"] == "WI")
assert np.allclose(wi["F"], L0[base_ids.index("WI")] * current["scales"], atol=1e-3), "current F parity failed"
assert abs(wi["sigma_idio"] - (1.5 + 2.0 * small[base_ids.index("WI")])) < 1e-3

ALL = list(range(12))
LAST6 = list(range(6, 12))
FIRST6 = list(range(6))
models = {"current": current}
models["all12"] = fit(ALL)
models["last6"] = fit(LAST6)
models["first6"] = fit(FIRST6)
models["all12_nohome_mask"] = fit(ALL, mask=MASK_NOHOME)
models["all12_fixed_idio"] = fit(ALL, fix_idio=(1.5, 2.0))
loto = {t: fit([u for u in ALL if u != t]) for t in ALL}
# heteroskedastic-cycle variants: cov_t = c_t^2 (FF' + diag sigma^2), sum log c_t = 0, so cycle-wide volatility
# (1976-84 realignment, 2012-16) is not forced into the idiosyncratic term
models["all12_cyc"] = fit(ALL, cyc=True)
models["all12_cyc_perstate"] = fit(ALL, cyc=True, per=True)
models["last6_perstate"] = fit(LAST6, per=True)
loto_cp = {t: fit([u for u in ALL if u != t], cyc=True, per=True) for t in ALL}


def scaled(m, c):
    return {**m, "scales": m["scales"] * c, "a": m["a"] * c, "b": m["b"] * c}


def pooled_cov(m, tsel):
    q = intervals80_(m)
    h = [np.abs(X[t, MASK[t]]) <= q[MASK[t]] for t in tsel]
    return float(np.concatenate(h).mean())


def calib_level(m, tsel, target=0.80):
    lo_, hi_ = 0.3, 3.0
    for _ in range(30):
        c = (lo_ + hi_) / 2
        if pooled_cov(scaled(m, c), tsel) < target:
            lo_ = c
        else:
            hi_ = c
    return scaled(m, (lo_ + hi_) / 2)

# ------------------------------------------------------------- empirical second moments (pairwise, mask-aware, mean 0)
def emp_corr(tsel, s1, s2):
    i, j = base_ids.index(s1), base_ids.index(s2)
    ok = [t for t in tsel if MASK[t, i] and MASK[t, j]]
    x, y = X[ok, i], X[ok, j]
    return float(np.sum(x * y) / np.sqrt(np.sum(x * x) * np.sum(y * y))), len(ok)


RUST6 = ["WI", "MI", "PA", "MN", "OH", "IA"]
SUN = ["AZ", "NV", "GA", "NC", "TX", "FL"]
PAIRS = [("WI", "MI"), ("WI", "PA"), ("MI", "PA"), ("WI", "MN"), ("OH", "IA"), ("PA", "OH"), ("WI", "IA"),
         ("AZ", "NV"), ("GA", "NC"), ("AZ", "GA"), ("NV", "NC"), ("TX", "FL"), ("TX", "CA"), ("NC", "VA"), ("WI", "AZ"), ("PA", "GA")]


def block_mean(R, blk):
    ii = [base_ids.index(s) for s in blk]
    v = [R[a, b] for x, a in enumerate(ii) for b in ii[x + 1:]]
    return float(np.mean(v))


def emp_block(tsel, blk):
    v = [emp_corr(tsel, a, b)[0] for x, a in enumerate(blk) for b in blk[x + 1:]]
    return float(np.mean(v))


summary = {}
for name, m in models.items():
    C, sd, R, fs = describe(m)
    summary[name] = {
        "scales": dict(zip(FACT, np.round(m["scales"], 3).tolist())), "idio_a": round(m["a"], 3), "idio_b": round(m["b"], 3),
        "median_total_sd": float(np.median(sd[[base_ids.index(s) for s in base_ids if s != "DC"]])),
        "median_factor_var_share": float(np.median(fs)),
        "sd": {s: round(float(sd[base_ids.index(s)]), 2) for s in RUST6 + SUN + ["CA", "NH", "VT", "WY"]},
        "corr": {f"{a}-{b}": round(float(R[base_ids.index(a), base_ids.index(b)]), 3) for a, b in PAIRS},
        "block_mean_corr": {"rust6": round(block_mean(R, RUST6), 3), "sun6": round(block_mean(R, SUN), 3)},
    }
emp = {lab: {"corr": {f"{a}-{b}": round(emp_corr(ts, a, b)[0], 3) for a, b in PAIRS},
             "block_mean_corr": {"rust6": round(emp_block(ts, RUST6), 3), "sun6": round(emp_block(ts, SUN), 3)},
             "rms_rel_change_median_state": float(np.median(np.sqrt(np.nanmean(np.where(MASK[ts], X[ts] ** 2, np.nan), 0))))}
       for lab, ts in (("all12", ALL), ("last6", LAST6), ("first6", FIRST6))}
realized_sd = {TK[t]: round(float(np.sqrt(np.mean(X[t, MASK[t]] ** 2))), 2) for t in ALL}

# ------------------------------------------------------------- back-test
NMC = 400_000
z0 = rng.standard_normal(NMC)
t5 = rng.standard_t(5, NMC) * np.sqrt(3 / 5)


def intervals80_(m):
    return intervals80(m)


def intervals80(m):
    """Exact (MC) 10/90% quantiles of the engine's marginal: normal factor part + sigma * unit-variance t5."""
    F = L0 * m["scales"][None, :]
    sf = np.sqrt((F ** 2).sum(1))
    si = sig_of(m)
    q = np.empty(NB)
    for j in range(NB):
        q[j] = np.quantile(np.abs(sf[j] * z0 + si[j] * t5), 0.8)  # symmetric
    return q


def joint_prob(m, states, xs, n=200_000):
    """P(eps_s <= x_s for all s) (or >= if x>0) under full joint sim, vs product of marginals."""
    ii = [base_ids.index(s) for s in states]
    F = L0[ii] * m["scales"][None, :]
    si = sig_of(m)[ii]
    f = rng.standard_normal((n, K))
    v = rng.standard_t(5, (n, len(ii))) * np.sqrt(3 / 5)
    e = f @ F.T + v * si
    sgn = np.sign(xs)
    hit = (e * sgn) >= (np.array(xs) * sgn)
    return float(hit.all(1).mean()), float(np.prod(hit.mean(0)))


def backtest(get_model, label):
    res = {}
    for t in ALL:
        m = get_model(t)
        q = intervals80(m)
        ok = MASK[t]
        hit = np.abs(X[t]) <= q
        C = cov(m["scales"], m["a"], m["b"], eta=m.get("eta"))
        idx = np.where(ok)[0]
        lc = multivariate_normal.logpdf(X[t, idx], np.zeros(len(idx)), C[np.ix_(idx, idx)])
        li = float(norm.logpdf(X[t, idx], 0, np.sqrt(np.diag(C)[idx])).sum())
        reg = {}
        for bn, blk in (("rust6", RUST6), ("sun6", SUN)):
            jj = [base_ids.index(s) for s in blk if ok[base_ids.index(s)]]
            miss = [base_ids[j] for j in jj if not hit[j]]
            signs = [int(np.sign(X[t, base_ids.index(s)])) for s in miss]
            reg[bn] = {"misses": miss, "miss_signs": signs, "cov80": float(hit[jj].mean())}
        res[TK[t]] = {"cov80": float(hit[ok].mean()), "n": int(ok.sum()), "logscore_corr": float(lc), "logscore_indep": li, **reg}
    tot = np.mean([res[k]["cov80"] for k in TK])
    pooled = float(np.sum([res[k]["cov80"] * res[k]["n"] for k in TK]) / np.sum([res[k]["n"] for k in TK]))
    rust_miss = sum(len(res[k]["rust6"]["misses"]) for k in TK)
    same_sign_clusters = sum(1 for k in TK if len(res[k]["rust6"]["misses"]) >= 2 and len(set(res[k]["rust6"]["miss_signs"])) == 1)
    return {"label": label, "pooled_cov80": pooled, "mean_cov80": float(tot), "by_transition": res,
            "logscore_corr_total": float(sum(res[k]["logscore_corr"] for k in TK)),
            "logscore_indep_total": float(sum(res[k]["logscore_indep"] for k in TK)),
            "rust6_total_misses": rust_miss, "rust6_same_sign_multi_miss_cycles": same_sign_clusters}


# candidate: shape from the heteroskedastic per-state fit on all 12, level set so pooled 80% coverage on the last 6
# (2000-24) transitions is 0.80. Honest version: LOTO shape, level calibrated on the other modern transitions.
SHAPE = "last6"  # best held-out log score on 2000-16 (see modern_backtest); per-state idio overfits, fixed small idio is much worse
models["candidate"] = calib_level(models[SHAPE], LAST6)
models["candidate_current_shape"] = calib_level(current, LAST6)
models["candidate_all12level"] = calib_level(models["all12_cyc_perstate"], ALL)
cand_loto = {t: calib_level(fit([u for u in LAST6 if u != t]), [u for u in LAST6 if u != t]) for t in ALL}
for nm in ("all12_cyc", "all12_cyc_perstate", "last6_perstate", "candidate", "candidate_current_shape", "candidate_all12level"):
    m = models[nm]
    C, sd, R, fs = describe(m)
    summary[nm] = {
        "scales": dict(zip(FACT, np.round(m["scales"], 3).tolist())), "idio_a": round(m["a"], 3), "idio_b": round(m["b"], 3),
        "cycle_scale": None if m.get("cycle_log_scale") is None else dict(zip(TK, np.round(np.exp(m["cycle_log_scale"]), 2).tolist())),
        "median_total_sd": float(np.median(sd[[base_ids.index(s) for s in base_ids if s != "DC"]])),
        "median_factor_var_share": float(np.median(fs)),
        "sd": {s: round(float(sd[base_ids.index(s)]), 2) for s in RUST6 + SUN + ["CA", "NH", "VT", "WY"]},
        "sigma_idio": {s: round(float(sig_of(m)[base_ids.index(s)]), 2) for s in RUST6 + SUN + ["CA", "NH", "VT", "WY"]},
        "corr": {f"{a}-{b}": round(float(R[base_ids.index(a), base_ids.index(b)]), 3) for a, b in PAIRS},
        "block_mean_corr": {"rust6": round(block_mean(R, RUST6), 3), "sun6": round(block_mean(R, SUN), 3)},
    }

BT = {
    "candidate_in_sample": backtest(lambda t: models["candidate"], "candidate, in-sample"),
    "candidate_loto": backtest(lambda t: cand_loto[t], "candidate: shape fit on the modern transitions other than t, level from the same; 1976-2000 are fully out of sample"),
    "all12_cyc_perstate_loto_unscaled": backtest(lambda t: loto_cp[t], "heteroskedastic per-state fit, LOTO, average-cycle level"),
    "current": backtest(lambda t: current, "current errors.json (in-sample only for 2016-20, 2020-24)"),
    "all12_in_sample": backtest(lambda t: models["all12"], "all-12 fit, in-sample"),
    "all12_loto": backtest(lambda t: loto[t], "all-12 fit, leave-one-transition-out"),
    "last6_fit": backtest(lambda t: models["last6"], "last-6 fit (out of sample for 1976-2000)"),
    "first6_fit": backtest(lambda t: models["first6"], "first-6 fit (out of sample for 2000-2024)"),
}
bt_brief = {k: {"pooled_cov80": round(v["pooled_cov80"], 3), "logscore_corr": round(v["logscore_corr_total"], 1),
                "logscore_indep": round(v["logscore_indep_total"], 1), "rust6_misses": v["rust6_total_misses"],
                "rust6_same_sign_multi_miss_cycles": v["rust6_same_sign_multi_miss_cycles"],
                "cov80_by_transition": {kk: round(vv["cov80"], 2) for kk, vv in v["by_transition"].items()}} for k, v in BT.items()}

# ------------------------------------------------------------- modern-era honest comparison (2000-04 ... 2020-24)
# For each held-out modern transition t: shape fit WITHOUT t; level calibrated (80% pooled) on the other modern transitions.
models["last6_cyc_perstate"] = fit(LAST6, cyc=True, per=True)
shape_fns = {
    "all12_cyc_perstate": lambda tr: fit(tr, cyc=True, per=True),
    "last6_perstate": lambda tr: fit([u for u in tr if u in LAST6], per=True),
    "last6_cyc_perstate": lambda tr: fit([u for u in tr if u in LAST6], cyc=True, per=True),
    "last6": lambda tr: fit([u for u in tr if u in LAST6]),
    "last6_fixed_idio_1.5_2": lambda tr: fit([u for u in tr if u in LAST6], fix_idio=(1.5, 2.0)),
    "all12_cyc": lambda tr: fit(tr, cyc=True),
    "all12_cyc_fixed_idio_1.5_2": lambda tr: fit(tr, cyc=True, fix_idio=(1.5, 2.0)),
}
modern = {}
modern_models = {}
for nm, fn in shape_fns.items():
    modern_models[nm] = {}
    for t in LAST6:
        tr = [u for u in ALL if u != t]
        shp = loto_cp[t] if nm == "all12_cyc_perstate" else fn(tr)
        modern_models[nm][t] = calib_level(shp, [u for u in LAST6 if u != t])
modern_models["current_level_recalibrated"] = {t: calib_level(current, [u for u in LAST6 if u != t]) for t in LAST6}
modern_models["current_as_is"] = {t: current for t in LAST6}
for nm, mm in modern_models.items():
    b = backtest(lambda t: mm.get(t, current), nm)
    rows = {TK[t]: b["by_transition"][TK[t]] for t in LAST6}
    C, sd, R, fs = describe(mm[LAST6[-1]])
    modern[nm] = {"pooled_cov80": float(np.mean([rows[k]["cov80"] for k in rows])),
                  "logscore_corr": float(sum(rows[k]["logscore_corr"] for k in rows)),
                  "logscore_indep": float(sum(rows[k]["logscore_indep"] for k in rows)),
                  "rust6_misses": int(sum(len(rows[k]["rust6"]["misses"]) for k in rows)),
                  "cov80_by_transition": {k: round(rows[k]["cov80"], 2) for k in rows},
                  "logscore_by_transition": {k: round(rows[k]["logscore_corr"], 1) for k in rows},
                  "logscore_2000_2016_heldout_for_all_shapes": round(float(sum(rows[TK[t]]["logscore_corr"] for t in LAST6[:4])), 1),
                  "rust6_by_transition": {k: rows[k]["rust6"] for k in rows},
                  "example_median_sd_(fit_without_2020-24)": float(np.median(sd)),
                  "example_rust6_corr": block_mean(R, RUST6), "example_sun6_corr": block_mean(R, SUN)}

# 2016 Rust Belt joint test: P(WI, MI, PA all swing at least as far R as realized in 2012->16)
t16 = TK.index("2012-2016")
x16 = [float(X[t16, base_ids.index(s)]) for s in ("WI", "MI", "PA")]
x16b = [float(X[t16, base_ids.index(s)]) for s in RUST6]
joint16 = {"realized_WI_MI_PA": dict(zip(["WI", "MI", "PA"], np.round(x16, 2).tolist())),
           "realized_rust6": dict(zip(RUST6, np.round(x16b, 2).tolist()))}
for name, m in (("current", current), ("all12_loto", loto[t16]), ("all12", models["all12"]), ("last6", models["last6"]),
                ("candidate", models["candidate"]), ("candidate_loto", cand_loto[t16]),
                ("last6_perstate_modern_loto", modern_models["last6_perstate"][t16]),
                ("all12_cyc_perstate_modern_loto", modern_models["all12_cyc_perstate"][t16]),
                ("current_level_recalibrated_loto", modern_models["current_level_recalibrated"][t16])):
    pj, pi = joint_prob(m, ["WI", "MI", "PA"], x16)
    pj6, pi6 = joint_prob(m, RUST6, x16b)
    joint16[name] = {"P_joint_WI_MI_PA": pj, "P_if_independent": pi, "P_joint_rust6": pj6, "P_rust6_if_independent": pi6}

# ------------------------------------------------------------- candidate
def candidate_from(m, label):
    C, sd, R, fs = describe(m)
    Fm = L0_all * m["scales"][None, :]
    eta_all = np.array([m["eta"][base_ids.index(i.split("-")[0])] if m.get("eta") is not None else 0.0 for i in uid])
    si = (m["a"] + m["b"] * small_all) * np.exp(eta_all)
    units = {}
    for n, i in enumerate(uid):
        if srows[i]["type"] == "congressional_district":
            pi = uid.index(i.split("-")[0])
            units[i] = {"F": [round(float(x), 5) for x in Fm[pi]], "sigma_idio": round(float(si[pi]), 5), "district_sd": 1.5}
        else:
            units[i] = {"F": [round(float(x), 5) for x in Fm[n]], "sigma_idio": round(float(si[n]), 5)}
    return units, sd, R


SHAPE_NOTES = {
    "last6": "Shape: MAP fit on the 6 transitions 2000->04 ... 2020->24 (HalfNormal(1.5) on scale_k as in 05, HalfNormal(3) "
             "on idio a,b in sigma_idio = a + b*smallness, the 05 functional form; Gaussian likelihood).",
    "current": "Shape: the current 05_errors.py fit (2016->20, 2020->24, sigma_idio = 1.5 + 2*smallness), rescaled.",
    "last6_perstate": "Shape: MAP fit on the 6 transitions 2000->04 ... 2020->24 (HalfNormal(1.5) on scale_k as in 05, HalfNormal(3) "
                      "on idio a,b, N(0,0.35^2) per-state idio log-multipliers; Gaussian likelihood).",
    "all12_cyc_perstate": "Shape: MAP fit on all 12 transitions 1976->80 ... 2020->24 (HalfNormal(1.5) on scale_k as in 05, HalfNormal(3) "
                          "on idio a,b, N(0,0.35^2) per-state idio log-multipliers, N(0,0.6^2) per-cycle log volatility with sum zero; "
                          "Gaussian likelihood).",
}


def build_candidate(mname, shape, cov_by_tr, pooled_all, fname):
    cm = models[mname]
    cunits, csd, cR = candidate_from(cm, mname)
    cand = {
        "errors": {
            "factor_names": FACT, "idio_df": 5, "calibrated": True,
            "target_rel_sd": round(float(np.median(csd[[base_ids.index(s) for s in base_ids if s != "DC"]])), 3),
            "district_sd": 1.5,
            "backtest": {"cov80_2016": round(cov_by_tr["2012-2016"], 5), "cov80_2020": round(cov_by_tr["2016-2020"], 5),
                         "cov80_2024": round(cov_by_tr["2020-2024"], 5),
                         "method": "held-out transition: shape and level fit without it; exact 80% interval of the normal-factor + "
                                   "t5-idio marginal; nominee home states and DC excluded",
                         "pooled_cov80_2004_2024_heldout": round(float(np.mean([cov_by_tr[k] for k in TK[6:]])), 4),
                         "pooled_cov80_1980_2024": None if pooled_all is None else round(pooled_all, 4)},
            # extra fields 05_errors.py writes to work/errors.json
            "scales": [round(float(x), 6) for x in cm["scales"]],
            "sigma_idio_formula": {"a": round(cm["a"], 4), "b": round(cm["b"], 4),
                                   "smallness": "(max log 2024 votes - log votes)/(range) over the 56 units, as in 05_errors.py",
                                   "per_state_multiplier": "none (eta = 0) unless eta is given; per-unit values are in units[*].sigma_idio",
                                   "eta": None if cm.get("eta") is None or not np.any(cm["eta"]) else {i: round(float(cm["eta"][j]), 3) for j, i in enumerate(base_ids)}},
            "cycle_volatility_1976_2024": summary["all12_cyc_perstate"]["cycle_scale"],
            "corr_examples": {k: summary[mname]["corr"][k] for k in ("WI-MI", "WI-PA", "AZ-NV", "TX-CA")},
            "block_mean_corr": summary[mname]["block_mean_corr"],
            "calibration_note": SHAPE_NOTES[shape] + " Data: state relative two-party margin changes (MIT EDSL doi:10.7910/DVN/42MVDX). "
                                "Nominee home-state transitions and DC excluded. Loadings use 2024-era covariates for all years. Level: "
                                "one common multiplier so pooled exact 80% intervals cover 80% of state changes over 2000->04 ... "
                                "2020->24. target_rel_sd is the resulting median total SD (informational; do not rescale again).",
        },
        "units": cunits,
        "_how_to_apply": "Replace model_params.errors with candidate.errors and, for every unit id, overwrite units[i].F and "
                         "units[i].sigma_idio (and district_sd for districts) with candidate.units[id]. In 05_errors.py terms: "
                         "scales_all = errors.scales, sig_idio = per-unit sigma_idio (formula plus eta), and skip rescale().",
    }
    json.dump(cand, open(OUT / fname, "w"), indent=1)
    return cand


CHOICE = "candidate"
lo = {k: v["cov80"] for k, v in BT["candidate_loto"]["by_transition"].items()}
candidate = build_candidate("candidate", SHAPE, lo, BT["candidate_loto"]["pooled_cov80"], "errors_candidate.json")
alt_cov = {**{k: v["cov80"] for k, v in BT["current"]["by_transition"].items()},
           **modern["current_level_recalibrated"]["cov80_by_transition"]}
build_candidate("candidate_current_shape", "current", alt_cov, None, "errors_candidate_current_shape_rescaled.json")

res = {"modern_backtest": modern, "data": {"transitions": TK, "n_states_fit": int(MASK.sum()), "masked_home_state_cells": int((~MASK).sum() - 12),
                "realized_rms_rel_change_by_transition": realized_sd},
       "models": summary, "empirical": emp, "backtest": bt_brief, "backtest_full": BT, "rust_2016_joint": joint16,
       "loto_scales": {TK[t]: dict(zip(FACT, np.round(loto[t]["scales"], 2).tolist())) | {"a": round(loto[t]["a"], 2), "b": round(loto[t]["b"], 2)} for t in ALL},
       "fit_ok": {k: v.get("ok", True) for k, v in models.items()}}


def conv(o):
    if isinstance(o, dict):
        return {k: conv(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [conv(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    return o


json.dump(conv(res), open(OUT / "fit_results.json", "w"), indent=1)
print(json.dumps(conv({"modern": modern, "data": res["data"], "models": summary, "empirical": emp, "backtest": bt_brief, "joint16": joint16,
                       "fit_ok": res["fit_ok"]}), indent=1))
