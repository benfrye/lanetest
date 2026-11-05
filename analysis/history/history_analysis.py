"""Lane gaps (vs mainstream liberal) in earlier House cycles, and how they vary with the national
environment. Reads research/history/house_<year>.json (2018, 2022, optional 2020/2024) and the 2026
House rows of analysis/output/races.json (read-only). Writes analysis/history/history_comparison.json.

Model per cycle (OLS, CR2 cluster-robust SEs by state; METHODOLOGY §2.6 / §3.6-D2 spec as far as the
historical data allow):
    y_i = state FE + rcs(m_pres_i; knots -60,-10,0,10,60) + inc_D + inc_R + D_inc_pv + R_inc_pv
          [+ rep_maga + rep_moderate, 2026 only] + sum_a delta_a * 1[lane_i = a] + e_i
y on two scales: margin (m_house_2p - m_pres_2p) and main (50 x delta-logit of the two-party D share, O-6).

Environment model: for each lane, gap_c = a + b * env_c over cycles c in {2018, 2022, 2026}, using
the joint covariance of the cycle gaps from a stacked race-level model (state x cycle FE, cycle-specific
controls, CR2 by state, so the same state/candidate appearing in several cycles is accounted for).
Reported: GLS fixed-effect fit, a random-effects version (DerSimonian-Laird tau^2 on 1 residual df),
the 2018/2022 two-point interpolation to an even environment, and the plain 2018/2022 average.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HIST = ROOT / "research" / "history"
RACES26 = ROOT / "analysis" / "output" / "races.json"

LANES = ["progressive", "left_populist", "center_populist", "mainstream_liberal", "moderate"]
NONREF = [a for a in LANES if a != "mainstream_liberal"]
L_MAP = {"conservative": -1.0, "moderate": 0.0, "liberal": 1.0, "left": 2.0}
P_MAP = {"establishment": 0.0, "mixed": 0.5, "populist": 1.0}
KNOTS = np.array([-60.0, -10.0, 0.0, 10.0, 60.0]) / 10.0
ENV = {2018: 8.6, 2020: 3.1, 2022: -2.7, 2024: -2.6, 2026: 13.0}   # national House vote margin D-R (README)
PRES_YEAR = {2018: False, 2020: True, 2022: False, 2024: True, 2026: False}
Z80 = stats.norm.ppf(0.9)


def logit50(m):
    m = max(min(m, 99.0), -99.0)
    s = (1 + m / 100) / 2
    return 50.0 * math.log(s / (1 - s))


def rcs_basis(x, knots):
    x = np.asarray(x, float)
    k = np.asarray(knots, float)
    K = len(k)
    cols = [x]
    norm = (k[-1] - k[0]) ** 2
    pp = lambda v: np.maximum(v, 0.0) ** 3  # noqa: E731
    for j in range(K - 2):
        cols.append((pp(x - k[j]) - pp(x - k[K - 2]) * (k[K - 1] - k[j]) / (k[K - 1] - k[K - 2])
                     + pp(x - k[K - 1]) * (k[K - 2] - k[j]) / (k[K - 1] - k[K - 2])) / norm)
    return np.column_stack(cols)


def ols(X, y):
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    return b, y - X @ b, XtX_inv


ROBUST = {"on": False}


def solve(X, y, cl):
    """OLS, or (ROBUST on) Huber M-estimation by IRLS (k = 1.345 x MAD scale); CR2 SEs on the weighted fit."""
    b, res, XtXi = ols(X, y)
    if ROBUST["on"]:
        w = np.ones(len(y))
        for _ in range(50):
            s = 1.4826 * np.median(np.abs(res - np.median(res)))
            u = np.abs(res) / (1.345 * s)
            w_new = np.where(u <= 1, 1.0, 1.0 / np.maximum(u, 1e-9))
            sw = np.sqrt(w_new)
            b_new, _, XtXi = ols(X * sw[:, None], y * sw)
            res = y - X @ b_new
            if np.max(np.abs(b_new - b)) < 1e-6:
                b = b_new
                break
            b, w = b_new, w_new
        sw = np.sqrt(w)
        Xw = X * sw[:, None]
        XtXi = np.linalg.pinv(Xw.T @ Xw)
        return b, cr2(Xw, res * sw, cl, XtXi), res
    return b, cr2(X, res, cl, XtXi), res


def cr2(X, resid, cl, XtX_inv):
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(cl):
        idx = np.where(cl == g)[0]
        Xg = X[idx]
        M = np.eye(len(idx)) - Xg @ XtX_inv @ Xg.T
        vals, vecs = np.linalg.eigh((M + M.T) / 2)
        vals = np.where(vals > 1e-8, vals ** -0.5, 0.0)
        u = Xg.T @ (vecs @ np.diag(vals) @ vecs.T @ resid[idx])
        meat += np.outer(u, u)
    return XtX_inv @ meat @ XtX_inv


# ----------------------------------------------------------------------------- data
def load_hist(year, label_filter=None, labelset="main"):
    p = HIST / f"house_{year}.json"
    if not p.exists():
        return None
    rows = []
    for r in json.loads(p.read_text())["races"]:
        if not r["included"]:
            continue
        d = r["dem"]
        if label_filter and not label_filter(r):
            continue
        m, mp = r["result"]["margin_2p"], r["baseline"]["pres_margin_2p"]
        rows.append({
            "cycle": year, "id": r["id"], "state": r["state"],
            "lane": d["archetype"] if labelset == "main" else (d.get("rule_archetype") or d["archetype"]),
            "L": L_MAP.get(d.get("ideology"), 1.0), "P": P_MAP.get(d.get("posture"), 0.0),
            "conf": d.get("style_confidence"), "tier": d.get("label_tier"),
            "m_pres": mp, "y_margin": m - mp, "y_logit": logit50(m) - logit50(mp),
            "inc_D": 1.0 if d["incumbent"] else 0.0,
            "inc_R": 1.0 if (r["rep"]["incumbent"] and not d["incumbent"]) else 0.0,
            "D_inc_pv": r.get("D_inc_pv", 0.0) or 0.0, "R_inc_pv": r.get("R_inc_pv", 0.0) or 0.0,
            "rep_maga": 0.0, "rep_moderate": 0.0,
        })
    return rows


def load_2026(label_filter=None, labelset="main"):
    d = json.loads(RACES26.read_text())
    rows = []
    for r in d["races"]:
        if r["office"] != "House" or not r["included_in_fit"]:
            continue
        if label_filter and not label_filter(r):
            continue
        rows.append({
            "cycle": 2026, "id": r["id"], "state": r["state"],
            "lane": r["fit_archetype"],  # 2026 always uses the pipeline's main-fit labels
            "L": L_MAP.get(r.get("ideology"), 1.0), "P": P_MAP.get(r.get("posture"), 0.0),
            "conf": r.get("style_confidence"), "tier": "2026_pipeline",
            "m_pres": r["pres2024_margin_2p"], "y_margin": r["overperformance"],
            "y_logit": r["overperformance_model_scale"],
            "inc_D": 1.0 if r["dem_incumbent"] else 0.0,
            "inc_R": 1.0 if (r["rep_incumbent"] and not r["dem_incumbent"]) else 0.0,
            "D_inc_pv": r.get("D_inc_pv") or 0.0, "R_inc_pv": r.get("R_inc_pv") or 0.0,
            "rep_maga": 1.0 if r.get("rep_style") == "maga" else 0.0,
            "rep_moderate": 1.0 if r.get("rep_style") == "moderate" else 0.0,
        })
    return rows


# ----------------------------------------------------------------------------- per-cycle model
def cycle_design(rows, opp=False, style="dummies", prefix=""):
    cols, names = [], []
    states = sorted({r["state"] for r in rows})
    for s in states:
        cols.append(np.array([1.0 if r["state"] == s else 0.0 for r in rows]))
        names.append(f"{prefix}fe[{s}]")
    B = rcs_basis(np.array([r["m_pres"] for r in rows]) / 10.0, KNOTS)
    for j in range(B.shape[1]):
        cols.append(B[:, j])
        names.append(f"{prefix}spline[{j}]")
    ctrl = ["inc_D", "inc_R", "D_inc_pv", "R_inc_pv"] + (["rep_maga", "rep_moderate"] if opp else [])
    for c in ctrl:
        cols.append(np.array([r[c] for r in rows]))
        names.append(f"{prefix}{c}")
    if style == "dummies":
        for a in NONREF:
            v = np.array([1.0 if r["lane"] == a else 0.0 for r in rows])
            cols.append(v)
            names.append(f"{prefix}lane[{a}]")
    elif style == "structural":
        cols.append(np.array([r["L"] - 1 for r in rows]))
        names.append(f"{prefix}beta_L")
        cols.append(np.array([r["P"] for r in rows]))
        names.append(f"{prefix}beta_P")
    X = np.column_stack(cols)
    keep = np.abs(X).sum(axis=0) > 0
    return X[:, keep], [n for n, k in zip(names, keep) if k]


def fit_cycle(rows, scale="logit", opp=False, style="dummies"):
    X, names = cycle_design(rows, opp=opp, style=style)
    y = np.array([r["y_logit" if scale == "logit" else "y_margin"] for r in rows])
    cl = np.array([r["state"] for r in rows])
    b, V, res = solve(X, y, cl)
    G = len(np.unique(cl))
    tq = stats.t.ppf(0.9, G - 1)
    out = {}
    keys = [f"lane[{a}]" for a in NONREF] if style == "dummies" else ["beta_L", "beta_P"]
    for k in keys:
        nm = k[5:-1] if k.startswith("lane[") else k
        n_lane = sum(1 for r in rows if r["lane"] == nm) if style == "dummies" else None
        if k not in names:
            out[nm] = {"est": None, "se": None, "lo80": None, "hi80": None, "n": n_lane}
            continue
        i = names.index(k)
        se = float(math.sqrt(max(V[i, i], 0)))
        out[nm] = {"est": float(b[i]), "se": se, "lo80": float(b[i] - tq * se), "hi80": float(b[i] + tq * se), "n": n_lane}
        if n_lane is not None and n_lane < 3:
            out[nm]["note"] = "fewer than 3 races: estimate is essentially those races' residuals"
    return out, {"n": len(rows), "n_states": G, "resid_sd": float(np.std(res, ddof=X.shape[1])) if len(rows) > X.shape[1] else None}


def raw_gaps(rows, scale="logit"):
    key = "y_logit" if scale == "logit" else "y_margin"
    ref = [r[key] for r in rows if r["lane"] == "mainstream_liberal"]
    out = {}
    for a in NONREF:
        v = [r[key] for r in rows if r["lane"] == a]
        out[a] = None if not v else float(np.mean(v) - np.mean(ref))
    return out


# ----------------------------------------------------------------------------- stacked model (joint covariance)
def fit_stacked(by_cycle, scale="logit", style="dummies", interact_env=False):
    """Stack cycles: cycle-specific state FE, spline and controls; lane x cycle dummies (or lane + lane x env).
    CR2 clustered by state across cycles."""
    blocks, names_all, ys, cls = [], [], [], []
    cycles = sorted(by_cycle)
    for c in cycles:
        rows = by_cycle[c]
        X, names = cycle_design(rows, opp=(c == 2026), style="none", prefix=f"{c}:")
        blocks.append((c, rows, X, names))
    allnames = [n for _, _, _, names in blocks for n in names]
    N = sum(len(rows) for _, rows, _, _ in blocks)
    style_cols = []
    if style == "dummies" and not interact_env:
        style_cols = [f"{c}:lane[{a}]" for c in cycles for a in NONREF]
    elif style == "dummies" and interact_env:
        style_cols = [f"lane[{a}]" for a in NONREF] + [f"lane[{a}]xenv" for a in NONREF]
    elif style == "structural" and not interact_env:
        style_cols = [f"{c}:{k}" for c in cycles for k in ("beta_L", "beta_P")]
    else:
        style_cols = ["beta_L", "beta_P", "beta_Lxenv", "beta_Pxenv"]
    names = allnames + style_cols
    X = np.zeros((N, len(names)))
    row0 = 0
    for c, rows, Xc, nc in blocks:
        for j, n in enumerate(nc):
            X[row0:row0 + len(rows), names.index(n)] = Xc[:, j]
        env = ENV[c]
        for i, r in enumerate(rows):
            if style == "dummies" and r["lane"] in NONREF:
                if not interact_env:
                    X[row0 + i, names.index(f"{c}:lane[{r['lane']}]")] = 1.0
                else:
                    X[row0 + i, names.index(f"lane[{r['lane']}]")] = 1.0
                    X[row0 + i, names.index(f"lane[{r['lane']}]xenv")] = env / 10.0
            elif style == "structural":
                if not interact_env:
                    X[row0 + i, names.index(f"{c}:beta_L")] = r["L"] - 1
                    X[row0 + i, names.index(f"{c}:beta_P")] = r["P"]
                else:
                    X[row0 + i, names.index("beta_L")] = r["L"] - 1
                    X[row0 + i, names.index("beta_P")] = r["P"]
                    X[row0 + i, names.index("beta_Lxenv")] = (r["L"] - 1) * env / 10.0
                    X[row0 + i, names.index("beta_Pxenv")] = r["P"] * env / 10.0
            ys.append(r["y_logit" if scale == "logit" else "y_margin"])
            cls.append(r["state"])
        row0 += len(rows)
    keep = np.abs(X).sum(axis=0) > 0
    X = X[:, keep]
    names = [n for n, k in zip(names, keep) if k]
    y = np.array(ys)
    cl = np.array(cls)
    b, V, _ = solve(X, y, cl)
    return b, V, names, len(np.unique(cl))


def env_models(b, V, names, cycles_use, key_fmt):
    """GLS fixed-effect and DL random-effects meta-regression gap = a + b*env over cycles, with the
    joint covariance of the cycle estimates."""
    idx = [names.index(key_fmt.format(c=c)) for c in cycles_use if key_fmt.format(c=c) in names]
    cyc = [c for c in cycles_use if key_fmt.format(c=c) in names]
    if len(cyc) < 2:
        return None
    g = b[idx]
    S = V[np.ix_(idx, idx)]
    E = np.array([ENV[c] for c in cyc])
    Xm = np.column_stack([np.ones(len(cyc)), E])
    out = {"cycles": cyc, "env": E.tolist(), "gaps": g.tolist(), "se": np.sqrt(np.diag(S)).tolist(),
           "corr": (S / np.sqrt(np.outer(np.diag(S), np.diag(S)))).tolist()}
    W = np.linalg.inv(S)
    C = np.linalg.inv(Xm.T @ W @ Xm)
    coef = C @ Xm.T @ W @ g
    out["fe"] = {"even_gap": float(coef[0]), "even_se": float(math.sqrt(C[0, 0])), "slope_per_pt": float(coef[1]),
                 "slope_se": float(math.sqrt(C[1, 1]))}
    if len(cyc) > 2:
        resid = g - Xm @ coef
        Q = float(resid @ W @ resid)
        df = len(cyc) - 2
        # DL tau^2 (diagonal approximation of the weights for the trace term)
        w = 1 / np.diag(S)
        P = np.diag(w) - np.outer(w, w) * 0  # placeholder for clarity
        A = Xm.T @ np.diag(w) @ Xm
        tr = w.sum() - np.trace(np.linalg.inv(A) @ (Xm.T @ np.diag(w ** 2) @ Xm))
        tau2 = max(0.0, (Q - df) / tr) if tr > 0 else 0.0
        S2 = S + tau2 * np.eye(len(cyc))
        W2 = np.linalg.inv(S2)
        C2 = np.linalg.inv(Xm.T @ W2 @ Xm)
        coef2 = C2 @ Xm.T @ W2 @ g
        out["fe"]["Q"] = Q
        out["fe"]["Q_df"] = df
        out["fe"]["Q_p"] = float(1 - stats.chi2.cdf(Q, df))
        out["re"] = {"tau2": tau2, "even_gap": float(coef2[0]), "even_se": float(math.sqrt(C2[0, 0])),
                     "slope_per_pt": float(coef2[1]), "slope_se": float(math.sqrt(C2[1, 1])),
                     "note": "tau^2 estimated from 1 residual degree of freedom; treat as illustrative"}
        del P
    for k in ("fe", "re"):
        if k in out:
            m, s = out[k]["even_gap"], out[k]["even_se"]
            out[k]["even_lo80"], out[k]["even_hi80"] = m - Z80 * s, m + Z80 * s
            out[k]["slope_lo80"] = out[k]["slope_per_pt"] - Z80 * out[k]["slope_se"]
            out[k]["slope_hi80"] = out[k]["slope_per_pt"] + Z80 * out[k]["slope_se"]
    return out


def midterm_two_point(b, V, names, key_fmt):
    k18, k22 = key_fmt.format(c=2018), key_fmt.format(c=2022)
    if k18 not in names or k22 not in names:
        return None
    i, j = names.index(k18), names.index(k22)
    e18, e22 = ENV[2018], ENV[2022]
    w18 = (0 - e22) / (e18 - e22)
    w22 = 1 - w18
    est = w18 * b[i] + w22 * b[j]
    var = w18 ** 2 * V[i, i] + w22 ** 2 * V[j, j] + 2 * w18 * w22 * V[i, j]
    avg = 0.5 * (b[i] + b[j])
    var_avg = 0.25 * (V[i, i] + V[j, j] + 2 * V[i, j])
    return {"interp_even": {"est": float(est), "se": float(math.sqrt(var)), "lo80": float(est - Z80 * math.sqrt(var)),
                            "hi80": float(est + Z80 * math.sqrt(var)), "weights": {"2018": w18, "2022": w22}},
            "avg_2018_2022": {"est": float(avg), "se": float(math.sqrt(var_avg)), "lo80": float(avg - Z80 * math.sqrt(var_avg)),
                              "hi80": float(avg + Z80 * math.sqrt(var_avg)), "env_of_average": (e18 + e22) / 2}}


def transfer_factor(b, V, names, key_fmt, n_boot=20000, seed=7):
    """pi = mean(pres-year gap) / mean(midterm gap), midterms 2018+2022 (no 2026: env far outside), pres 2020+2024.
    Interval by parametric simulation from the joint normal of the four estimates."""
    ks = [key_fmt.format(c=c) for c in (2018, 2022, 2020, 2024)]
    if not all(k in names for k in ks):
        return None
    idx = [names.index(k) for k in ks]
    mu = b[idx]
    S = V[np.ix_(idx, idx)]
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(mu, S, size=n_boot)
    mid = draws[:, :2].mean(axis=1)
    pres = draws[:, 2:].mean(axis=1)
    ratio = pres / mid
    point = float(mu[2:].mean() / mu[:2].mean())
    return {"point": point, "median_sim": float(np.median(ratio)), "lo80": float(np.quantile(ratio, 0.1)),
            "hi80": float(np.quantile(ratio, 0.9)), "share_mid_same_sign": float(np.mean(np.sign(mid) == np.sign(mu[:2].mean()))),
            "midterm_mean": float(mu[:2].mean()), "pres_mean": float(mu[2:].mean()),
            "env_mean_midterm": (ENV[2018] + ENV[2022]) / 2, "env_mean_pres": (ENV[2020] + ENV[2024]) / 2}


# ----------------------------------------------------------------------------- main
def run(sample_name, filt_hist=None, filt_26=None, cycles=(2018, 2022, 2026), pres_cycles=(2020, 2024), labelset="main"):
    by = {}
    for c in list(cycles) + list(pres_cycles):
        rows = load_2026(filt_26, labelset) if c == 2026 else load_hist(c, filt_hist, labelset)
        if rows:
            by[c] = rows
    res = {"sample": sample_name, "cycles": {}, "env_model": {}, "pi": {}}
    for c, rows in sorted(by.items()):
        cres = {"n_races": len(rows), "n_by_lane": {a: sum(r["lane"] == a for r in rows) for a in LANES},
                "env": ENV[c], "presidential_year": PRES_YEAR[c]}
        for scale in ("logit", "margin"):
            d, meta = fit_cycle(rows, scale=scale, opp=(c == 2026))
            s, _ = fit_cycle(rows, scale=scale, opp=(c == 2026), style="structural")
            cres[scale] = {"adjusted": d, "structural": s, "raw": raw_gaps(rows, scale), "fit": meta}
            if c == 2026:
                d2, _ = fit_cycle(rows, scale=scale, opp=False)
                cres[scale]["adjusted_no_opponent_type"] = d2
        res["cycles"][str(c)] = cres
    mids = [c for c in (2018, 2022, 2026) if c in by]
    for scale in ("logit", "margin"):
        sub = {c: by[c] for c in mids}
        b, V, names, G = fit_stacked(sub, scale=scale)
        em = {}
        for a in NONREF:
            em[a] = {"three_cycle": env_models(b, V, names, mids, "{c}:lane[" + a + "]"),
                     "midterm_2018_2022": midterm_two_point(b, V, names, "{c}:lane[" + a + "]")}
        bs, Vs, ns, _ = fit_stacked(sub, scale=scale, style="structural")
        for k in ("beta_L", "beta_P"):
            em[k] = {"three_cycle": env_models(bs, Vs, ns, mids, "{c}:" + k),
                     "midterm_2018_2022": midterm_two_point(bs, Vs, ns, "{c}:" + k)}
        res["env_model"][scale] = em
        if all(c in by for c in (2018, 2020, 2022, 2024)):
            sub2 = {c: by[c] for c in (2018, 2020, 2022, 2024)}
            b2, V2, n2, _ = fit_stacked(sub2, scale=scale)
            bs2, Vs2, ns2, _ = fit_stacked(sub2, scale=scale, style="structural")
            pi = {a: transfer_factor(b2, V2, n2, "{c}:lane[" + a + "]") for a in NONREF}
            pi["beta_L"] = transfer_factor(bs2, Vs2, ns2, "{c}:beta_L")
            pi["beta_P"] = transfer_factor(bs2, Vs2, ns2, "{c}:beta_P")
            # pooled across lanes: precision-weighted average leftness slope is the most stable single number
            res["pi"][scale] = pi
            # all four cycles: gap = a + b*env + log-pi shift is not identified separately with so few points;
            # we also report the four-cycle env fit with a presidential-year dummy for the structural slope
    return res


def main():
    out = {"generated": "2026-11-04", "env_D_minus_R": ENV,
           "env_sources": {
               "2018": "Wikipedia 2018 House elections infobox (Clerk of the House): D 53.4%, R 44.8%",
               "2020": "Wikipedia 2020 House elections infobox (Clerk): D 50.3%, R 47.2%",
               "2022": "Wikipedia 2022 House elections infobox (Clerk): R 50.0%, D 47.3%",
               "2024": "Wikipedia 2024 House elections infobox (Clerk): R 49.8%, D 47.2%",
               "2026": "Project headline (House vote about D+13; research/national.json)"},
           "spec": __doc__.strip()}
    out["main"] = run("all contested races (main, O-6)")
    out["competitive"] = run("competitive only |pres| <= 20 (all labels individually researched)",
                             filt_hist=lambda r: abs(r["baseline"]["pres_margin_2p"]) <= 20,
                             filt_26=lambda r: abs(r["pres2024_margin_2p"]) <= 20)
    out["researched_labels_only"] = run("excluding default (unresearched) labels",
                                        filt_hist=lambda r: r["dem"].get("coder") not in ("rule", "default"))
    out["medium_high_confidence"] = run("labels with medium/high confidence only",
                                        filt_hist=lambda r: r["dem"].get("style_confidence") in ("medium", "high"),
                                        filt_26=lambda r: r.get("style_confidence") in ("medium", "high"))
    out["rule_labels"] = run("marker-only rule labels for 2018/2022 (Set B analogue; 2026 keeps its main-fit labels)", labelset="rule")
    out["headline"] = headline(out["main"])
    ROBUST["on"] = True
    out["robust_huber"] = run("Huber M-estimation (outlier-resistant; main sample and labels)")
    ROBUST["on"] = False
    (HERE / "history_comparison.json").write_text(json.dumps(out, indent=1))
    summarize(out)


def headline(R, scale="logit"):
    """Compact summary: main sample, 50 x delta-logit scale, gaps vs mainstream liberal in points."""
    h = {"scale": "50 x delta-logit (points of margin in an even seat)", "per_cycle": {}, "even_environment": {}}
    for c, cr in R["cycles"].items():
        h["per_cycle"][c] = {a: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in cr[scale]["adjusted"][a].items()}
                             for a in NONREF}
        h["per_cycle"][c]["env"] = cr["env"]
    for a, em in R["env_model"][scale].items():
        tc, mt = em["three_cycle"], em["midterm_2018_2022"]
        h["even_environment"][a] = {
            "gls_3cycle": {k: round(tc["fe"][k], 3) for k in ("even_gap", "even_lo80", "even_hi80", "slope_per_pt", "slope_lo80", "slope_hi80")} if tc else None,
            "random_effects_3cycle": {k: round(tc["re"][k], 3) for k in ("even_gap", "even_lo80", "even_hi80", "tau2")} if tc and "re" in tc else None,
            "interp_2018_2022": {k: round(mt["interp_even"][k], 3) for k in ("est", "lo80", "hi80")} if mt else None,
            "avg_2018_2022": {k: round(mt["avg_2018_2022"][k], 3) for k in ("est", "lo80", "hi80")} if mt else None}
    if R["pi"].get(scale):
        h["pi"] = {k: ({kk: round(vv, 3) for kk, vv in v.items() if isinstance(vv, float)} if v else None) for k, v in R["pi"][scale].items()}
    return h


def fmt(d):
    if not d or d.get("est") is None:
        return "   n/a"
    return f"{d['est']:+5.1f} [{d['lo80']:+5.1f},{d['hi80']:+5.1f}] n={d.get('n')}"


def summarize(out):
    for samp in ("main", "competitive", "researched_labels_only", "medium_high_confidence", "rule_labels", "robust_huber"):
        R = out[samp]
        print(f"\n===== {R['sample']}")
        for scale in ("logit", "margin"):
            print(f"-- scale {scale}")
            for c, cr in R["cycles"].items():
                adj = cr[scale]["adjusted"]
                print(f"  {c} (env {cr['env']:+.1f}, N={cr['n_races']}): " + " | ".join(f"{a[:6]} {fmt(adj[a])}" for a in NONREF))
                st = cr[scale]["structural"]
                print(f"        structural: beta_L {fmt(st['beta_L'])}  beta_P {fmt(st['beta_P'])}")
            for a, em in R["env_model"][scale].items():
                tc = em["three_cycle"]
                mt = em["midterm_2018_2022"]
                if tc:
                    fe = tc["fe"]
                    s = f"  env[{a}]: slope/pt {fe['slope_per_pt']:+.3f} [{fe['slope_lo80']:+.3f},{fe['slope_hi80']:+.3f}] even {fe['even_gap']:+.2f} [{fe['even_lo80']:+.2f},{fe['even_hi80']:+.2f}]"
                    if "re" in tc:
                        re_ = tc["re"]
                        s += f" | RE even {re_['even_gap']:+.2f} [{re_['even_lo80']:+.2f},{re_['even_hi80']:+.2f}] tau2 {re_['tau2']:.2f}"
                    print(s)
                if mt:
                    print(f"        2-pt interp even {mt['interp_even']['est']:+.2f} [{mt['interp_even']['lo80']:+.2f},{mt['interp_even']['hi80']:+.2f}]  avg18/22 {mt['avg_2018_2022']['est']:+.2f} [{mt['avg_2018_2022']['lo80']:+.2f},{mt['avg_2018_2022']['hi80']:+.2f}]")
            if R["pi"].get(scale):
                for k, v in R["pi"][scale].items():
                    if v:
                        print(f"  pi[{k}]: {v['point']:.2f} (sim median {v['median_sim']:.2f}, 80% {v['lo80']:.2f}..{v['hi80']:.2f}); mid {v['midterm_mean']:+.2f} pres {v['pres_mean']:+.2f}")


if __name__ == "__main__":
    main()
