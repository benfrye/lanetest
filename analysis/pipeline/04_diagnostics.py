"""Step 04: confounding diagnostics D1–D7 (§3.6) and the model checks V6, V7, V8, plus tau_c (§5.5).

Writes work/diagnostics.json.
"""
import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm, t as tdist

from common import (ARCHETYPES, L_MAP, NON_REF, RESEARCH, SEED, STATE_REGION, WORK, Log, load_json, logit50,
                    ols, save_json, summ)
import gibbs
from gibbs import Design, centroids, deltas, draw_omega_prior, min_n_status, ppc_coverage, run_gibbs, t_var_factor
import olsfe

log = Log("04_diagnostics")
rng = np.random.default_rng(SEED + 40)
rows = load_json(WORK / "dataset_labeled.json")
meta = load_json(WORK / "fit_meta.json")
main = [r for r in rows if r["in_main"]]
gibbs.LIKELIHOOD_NU = float("inf") if meta["likelihood_nu"] is None else meta["likelihood_nu"]
cents_raw = meta["centroids"]
cents = {a: (v["L"], v["P"], v["n"]) for a, v in cents_raw.items()}
u_active = meta["u_active"]
SWD = meta["statewide_dev_active"]
states_tbl = {r["id"]: r for r in load_json(RESEARCH / "states.json")["rows"]}
agn = np.load(WORK / "fit_agnostic.npz", allow_pickle=True)
names = list(agn["names"])
TH = agn["theta"]  # 1000 x p
D0 = Design(main, "M", statewide_dev=SWD, u_active=u_active, cents=cents)
assert list(D0.names) == names
fit0 = {"theta": TH[None]}
delta0 = {a: v.ravel() for a, v in deltas(fit0, D0, cents).items()}
delta0_sum = {a: {"med": float(np.median(v)), "sd": float(v.std()), "lo": float(np.quantile(v, .1)), "hi": float(np.quantile(v, .9))}
              for a, v in delta0.items()}
diag = {"gibbs_delta_agnostic": delta0_sum}


def quick_fit(rs, seed, chains=2, warm=400, draws=800, **kw):
    kw.setdefault("cents", cents)
    kw.setdefault("u_active", [a for a, s in min_n_status(rs, kw.get("labelset", "M")).items() if s["ok"] and a != "mainstream_liberal"]
                  if kw.get("labelset", "M") in ("M",) and False else u_active)
    kw.setdefault("statewide_dev", SWD and sum(r["statewide"] for r in rs) >= 25)
    D = Design(rs, **kw)
    f = run_gibbs(D, chains, warm, draws, seed=seed)
    return D, f


# ============================================================== D1 overlap refit
def state_val(st, key):
    v = states_tbl.get(st, {}).get(key)
    return float(v) if v is not None else np.nan


def prop_features(rs):
    regs = sorted(set(STATE_REGION.values()))
    F = []
    for r in rs:
        f = [r["m24"] / 10, state_val(r["state"], "white_noncollege_pct_adults25") / 10,
             state_val(r["state"], "urban_pct_2020_census") / 10, r["inc_D"], r["inc_R"], float(r["statewide"])]
        f += [1.0 if STATE_REGION.get(r["state"]) == g else 0.0 for g in regs[1:]]
        F.append(f)
    F = np.array(F)
    F = (F - F.mean(0)) / np.where(F.std(0) > 0, F.std(0), 1)
    return np.column_stack([np.ones(len(rs)), F])


def mnlogit(F, yk, K, l2=1.0):
    n, d = F.shape

    def nll(w):
        W = w.reshape(K - 1, d)
        eta = np.column_stack([np.zeros(n), F @ W.T])
        lse = np.log(np.exp(eta - eta.max(1, keepdims=True)).sum(1)) + eta.max(1)
        ll = eta[np.arange(n), yk] - lse
        return -ll.sum() + 0.5 * l2 * np.sum(W[:, 1:] ** 2)

    res = minimize(nll, np.zeros((K - 1) * d), method="L-BFGS-B")
    W = res.x.reshape(K - 1, d)
    eta = np.column_stack([np.zeros(n), F @ W.T])
    P = np.exp(eta - eta.max(1, keepdims=True))
    return P / P.sum(1, keepdims=True)


order = ["mainstream_liberal"] + NON_REF
yk = np.array([order.index(r["M_archetype"]) for r in main])
Pm = mnlogit(prop_features(main), yk, len(order))
keep = np.zeros(len(main), bool)
pair_info = {}
for k, a in enumerate(order[1:], start=1):
    e = Pm[:, k] / (Pm[:, k] + Pm[:, 0])
    inpair = (yk == k) | (yk == 0)
    ok = inpair & (e >= 0.05) & (e <= 0.95)
    pair_info[a] = {"n_a_kept": int(((yk == k) & ok).sum()), "n_a": int((yk == k).sum()),
                    "n_ml_kept": int(((yk == 0) & ok).sum())}
    keep |= ok
trim = [r for r, k in zip(main, keep) if k]
log(f"D1 overlap: kept {len(trim)}/{len(main)} rows; {pair_info}")
Dt, ft = quick_fit(trim, SEED + 41, chains=4, warm=500, draws=1500, labelset="M", mundlak=True)
dt = deltas(ft, Dt, cents)
d1 = {}
lead_with_overlap = False
for a in NON_REF:
    m_over = float(np.median(dt[a]))
    move = m_over - delta0_sum[a]["med"]
    big = abs(move) > 1.5 or abs(move) > delta0_sum[a]["sd"]
    d1[a] = {"overlap": summ(dt[a].ravel()), "full": [delta0_sum[a]["med"], delta0_sum[a]["lo"], delta0_sum[a]["hi"]],
             "move": move, "flag": bool(big), **pair_info[a]}
    if big and pair_info[a]["n_a_kept"] > 0:
        lead_with_overlap = True
diag["D1_overlap"] = {"by_archetype": d1, "n_trimmed": len(trim), "lead_with_overlap": lead_with_overlap,
                      "note": "Propensity covariates: m24, state WNC share, state urban share, incumbency, statewide, region (district demographics unavailable). An archetype with no rows inside [0.05, 0.95] keeps only its structural (beta_L, beta_P) prediction and does not set the flag."}
log("D1:", {a: (round(v["move"], 2), v["flag"]) for a, v in d1.items()}, "lead_with_overlap", lead_with_overlap)

# ============================================================== D2 OLS state-FE + EB
yadj = olsfe.adj_outcome(main)
o2 = olsfe.fit(main, yadj, labelset="M", style="dummies")
dh, se = {}, {}
for a in NON_REF:
    k = f"arch[{a}]"
    if k in o2["idx"]:
        dh[a], se[a] = float(o2["b"][o2["idx"][k]]), float(o2["se"][o2["idx"][k]])
n_by = {a: sum(1 for r in main if r["M_archetype"] == a) for a in ARCHETYPES}
comparable = [a for a in dh if n_by[a] >= 10]
tau2 = max(0.0, float(np.mean([dh[a] ** 2 - se[a] ** 2 for a in comparable]))) if comparable else 0.0
d2 = {}
D2_SD_THRESHOLD = 1.5
publish_blocked = False
for a in NON_REF:
    if a not in dh:
        d2[a] = {"ols": None, "note": "no rows"}
        continue
    shr = dh[a] * tau2 / (tau2 + se[a] ** 2) if tau2 > 0 else 0.0
    gap = shr - delta0_sum[a]["med"]
    gap_sd = abs(gap) / delta0_sum[a]["sd"]
    is_cmp = a in comparable
    # Override O-1c (lead reviewer, 2026-11-04): V12 passes if the EB-vs-Gibbs gap <= 1.5 posterior SD
    d2[a] = {"ols": dh[a], "se_cr2": se[a], "eb_shrunk": shr, "gibbs_med": delta0_sum[a]["med"], "gibbs_sd": delta0_sum[a]["sd"],
             "gap": gap, "gap_in_sd": gap_sd, "n": n_by[a], "comparable": is_cmp, "flag": bool(is_cmp and gap_sd > D2_SD_THRESHOLD)}
    if is_cmp and gap_sd > D2_SD_THRESHOLD:
        publish_blocked = True
# Unshrunk comparison as context (EB with a 4-archetype tau^2 can be degenerate)
models_disagree = {a: bool(v.get("flag")) for a, v in d2.items()}
diag["D2_ols_fe"] = {"by_archetype": d2, "tau2_hat": tau2, "publish_blocked": publish_blocked, "sd_threshold": D2_SD_THRESHOLD,
                     "models_disagree": models_disagree,
                     "rule_note": "Compared only for archetypes with n >= 10 in the main sample (§3.8 cell minimum); smaller archetypes have no estimable dummy and are reported but not gated.",
                     "beta_structural_ols": None}
o2s = olsfe.fit(main, yadj, labelset="M", style="structural")
diag["D2_ols_fe"]["beta_structural_ols"] = {nm: [float(o2s["b"][o2s["idx"][nm]]), float(o2s["se"][o2s["idx"][nm]])] for nm in ("beta_L", "beta_P")}
log("D2:", {a: (round(v.get("ols") or 0, 2), round(v.get("eb_shrunk", 0), 2), round(v.get("gap_in_sd", 0), 2)) for a, v in d2.items()}, "tau2", round(tau2, 3), "blocked", publish_blocked)

# ---- D2 review aids (do not change the gate; they help the human reviewer resolve it)
aids = {}
# (a) Gibbs with every archetype deviation u_a switched on (min-N ignored)
Da, fa = quick_fit(main, SEED + 42, chains=4, warm=500, draws=1500, labelset="M", u_active=NON_REF)
da = deltas(fa, Da, cents)
aids["gibbs_all_u_active"] = {a: summ(da[a].ravel()) for a in NON_REF}
# (b) OLS-FE dummy leave-one-out over that archetype's own rows (influence)
for a in NON_REF:
    if not d2.get(a, {}).get("flag"):
        continue
    loo = []
    for i, r in enumerate(main):
        if r["M_archetype"] != a:
            continue
        rs = [x for j, x in enumerate(main) if j != i]
        ob = olsfe.fit(rs, olsfe.adj_outcome(rs), labelset="M", style="dummies")
        k = f"arch[{a}]"
        loo.append({"drop": r["id"], "ols": float(ob["b"][ob["idx"][k]]) if k in ob["idx"] else None,
                    "y": r["y"], "same_state_rows": sum(1 for x in main if x["state"] == r["state"]) - 1})
    aids[f"ols_loo_{a}"] = loo
# (c) OLS-FE dummy with Huber-type downweighting (mimics the t5 errors of the Gibbs model)
w = np.ones(len(main))
Xd, nd_, _ = olsfe.design(main, style="dummies")
for _ in range(30):
    b_, r_, _ = ols(Xd, yadj, w)
    s_ = 1.4826 * np.median(np.abs(r_ - np.median(r_)))
    w = np.minimum(1.0, 1.345 * s_ / np.maximum(np.abs(r_), 1e-9))
aids["ols_huber"] = {a: float(b_[nd_.index(f"arch[{a}]")]) for a in NON_REF if f"arch[{a}]" in nd_}
diag["D2_ols_fe"]["review_aids"] = aids
log("D2 aids: gibbs all-u", {a: [round(x, 2) for x in v] for a, v in aids["gibbs_all_u_active"].items()}, "huber", {a: round(v, 2) for a, v in aids["ols_huber"].items()})

# ============================================================== D3 Freedman–Lane permutation
Xr, nr, _ = olsfe.design(main, style="none")
Xf, nf, _ = olsfe.design(main, style="structural")
br, rr, _ = ols(Xr, yadj)
fitted_r = Xr @ br
XtXi = np.linalg.pinv(Xf.T @ Xf)
A = XtXi @ Xf.T
H = Xf @ A
iL, iP = nf.index("beta_L"), nf.index("beta_P")
dfree = len(main) - np.linalg.matrix_rank(Xf)
Vsub = XtXi[np.ix_([iL, iP], [iL, iP])]
Vsub_inv = np.linalg.inv(Vsub)


def wald(Y):
    B = A @ Y
    R = Y - H @ Y
    s2 = (R ** 2).sum(0) / dfree
    bb = B[[iL, iP]]
    return np.einsum("ik,ij,jk->k", bb, Vsub_inv, bb) / s2


W_obs = float(wald(yadj[:, None])[0])
NPERM = 2000
st_arr = np.array([r["state"] for r in main])
groups_idx = [np.where(st_arr == s)[0] for s in np.unique(st_arr)]
Yp = np.empty((len(main), NPERM))
for k in range(NPERM):
    rp = rr.copy()
    for gi in groups_idx:
        if len(gi) > 1:
            rp[gi] = rr[rng.permutation(gi)]
    Yp[:, k] = fitted_r + rp
Wp = wald(Yp)
p_fl = float((1 + np.sum(Wp >= W_obs)) / (NPERM + 1))
diag["D3_freedman_lane"] = {"wald_obs": W_obs, "p_value": p_fl, "n_perm": NPERM, "no_detectable_effect": p_fl > 0.10,
                            "note": "Residuals of the reduced OLS-FE model permuted within state; singleton states cannot permute."}
log(f"D3: Wald={W_obs:.2f} p={p_fl:.3f}")

# ============================================================== D4 grouped CV (10 folds by state)
uniq_states = sorted({r["state"] for r in main})
perm = rng.permutation(len(uniq_states))
fold_of = {uniq_states[j]: int(i % 10) for i, j in enumerate(perm)}
lpd_with = np.zeros(len(main))
lpd_without = np.zeros(len(main))
t0 = time.time()
for fold in range(10):
    tr = [r for r in main if fold_of[r["state"]] != fold]
    te_idx = [i for i, r in enumerate(main) if fold_of[r["state"]] == fold]
    te = [main[i] for i in te_idx]
    for drop, store in ((False, lpd_with), (True, lpd_without)):
        D, f = quick_fit(tr, SEED + 400 + fold * 2 + drop, labelset="M", drop_style=drop)
        th = f["theta"].reshape(-1, len(D.names))
        sig2 = f["sig2"].reshape(-1, 3)
        sa2 = f["sa2"].ravel()
        for i, r in zip(te_idx, te):
            v = D.row_vector(r)
            if not drop and D.mundlak:
                same = [x for x in te if x["state"] == r["state"]]
                D.set_state_means(v, *D.state_means_of(same))
            eta = th @ v
            vg = 0 if r["office"] in ("House", "Special") else (1 if r["office"] == "Senate" else 2)
            p = r["p"]
            Jr = r["J"]
            meas = 0.0 if p >= 0.95 else (25 * (1 - p) * Jr) ** 2 + (2 * (1 - p) / 0.2 * Jr) ** 2
            shift = 0.0 if p >= 0.95 else r["late_shift_prior_mean"] * (1 - p) / 0.2 * Jr
            var = sig2[:, vg] * t_var_factor() + sa2 + meas
            dens = norm.pdf(r["y_model"], eta - shift, np.sqrt(var))
            store[i] = np.log(np.mean(dens) + 1e-300)
diff = lpd_with - lpd_without
d_elpd = float(diff.sum())
se_elpd = float(np.sqrt(len(diff) * diff.var()))
diag["D4_grouped_cv"] = {"delta_elpd": d_elpd, "se": se_elpd, "no_predictive_gain": d_elpd < 2 * se_elpd,
                         "elpd_with": float(lpd_with.sum()), "elpd_without": float(lpd_without.sum())}
log(f"D4: dELPD={d_elpd:.2f} se={se_elpd:.2f} ({time.time()-t0:.0f}s)")

# ============================================================== D5 2024 placebo
plc = []
for r in rows:
    if r["office"] != "House" or r["lines"] != "2024_same" or r["house24"] is None or r["exclusion_reason"] in (
            "uncontested_or_no_major_party_opponent", "same_party_general", "no_democrat_on_ballot"):
        continue
    if r["M_archetype"] not in ARCHETYPES or abs(r["house24_total"] or 100) >= 95:
        continue
    txt = (r["dem_background"] + " " + r["style_evidence"] + " " + r["notes"]).lower()
    if r["dem_incumbent"] or "2024 nominee" in txt or "rematch" in txt:
        continue
    r2 = dict(r)
    r2["_y"] = logit50(r["house24"]) - logit50(r["m24"])  # model scale (O-6)
    plc.append(r2)
yp = np.array([r["_y"] for r in plc])
regs = sorted(set(STATE_REGION.values()))
extra = {f"reg[{g}]": [1.0 if STATE_REGION.get(r["state"]) == g else 0.0 for r in plc] for g in regs[1:]}
op = olsfe.fit(plc, yp, labelset="M", style="dummies", state_fe=False, extra=extra)
d5 = {}
placebo_flag = {}
for a in NON_REF:
    k = f"arch[{a}]"
    n_a = sum(1 for r in plc if r["M_archetype"] == a)
    if k not in op["idx"] or n_a < 5:
        d5[a] = {"n": n_a, "placebo": None, "note": "fewer than 5 eligible seats"}
        placebo_flag[a] = False
        continue
    pb, ps = float(op["b"][op["idx"][k]]), float(op["se"][op["idx"][k]])
    dm = delta0_sum[a]["med"]
    flag = (np.sign(pb) == np.sign(dm) and abs(pb) >= 0.5 * abs(dm)) or abs(pb) >= 1.5
    d5[a] = {"n": n_a, "placebo": pb, "se": ps, "lo80": pb - 1.2816 * ps, "hi80": pb + 1.2816 * ps,
             "delta_med": dm, "delta_minus_placebo": dm - pb, "flag": bool(flag)}
    placebo_flag[a] = bool(flag)
diag["D5_placebo"] = {"n_seats": len(plc), "by_archetype": d5, "placebo_flag": placebo_flag,
                      "note": "House seats on unchanged lines with a contested 2024 race where the 2026 D nominee was not the 2024 nominee/incumbent (text match on '2024 nominee'/'rematch'). Outcome house24 - pres24 (two-party). Controls: m24 spline, incumbency/opponent controls, region (no state FE: too few seats per state)."}
log("D5:", {a: (v.get("n"), v.get("placebo") and round(v["placebo"], 2), v.get("flag")) for a, v in d5.items()})

# ============================================================== D6 close-primary RD (sign check)
prim = load_json(RESEARCH / "primaries.json")
row_by_id = {r["id"]: r for r in rows}


def rid(g):
    if not g:
        return None
    if g.startswith("HOUSE-"):
        st, dist = g[6:].split("-")[:2]
        return f"{st}-{int(dist)}"
    return "SEN-FL-special" if g.startswith("SEN-FL") else g


rd = []
for c in prim["contests"]:
    cands = [x for x in c.get("candidates") or [] if x.get("pct") is not None and x.get("ideology") in L_MAP]
    if len(cands) < 2 or "convention" in (c.get("office") or "").lower():
        continue
    cands.sort(key=lambda x: -x["pct"])
    a, b = cands[0], cands[1]
    dL = L_MAP[a["ideology"]] - L_MAP[b["ideology"]]
    if abs(dL) < 1 or abs(a["pct"] - b["pct"]) > 10:
        continue
    r = row_by_id.get(rid(c.get("race_id_general")))
    if r is None or r.get("y") is None or r["exclusion_reason"] in ("same_party_general", "uncontested_or_no_major_party_opponent", "independent_backed (Dem-backed independent; descriptive only)"):
        continue
    left_won = 1.0 if dL > 0 else 0.0
    left_pct = a["pct"] if dL > 0 else b["pct"]
    right_pct = b["pct"] if dL > 0 else a["pct"]
    rd.append({"contest": c["id"], "race": r["id"], "left_won": left_won, "margin_left": left_pct - right_pct, "y": r["y_model"], "y_margin": r["y"], "m24": r["m24"]})
if len(rd) >= 4:
    Xrd = np.column_stack([np.ones(len(rd)), [x["left_won"] for x in rd], [x["margin_left"] for x in rd], [x["m24"] / 10 for x in rd]])
    yrd = np.array([x["y"] for x in rd])
    brd, rrd, XtXi_rd = ols(Xrd, yrd)
    dof = max(1, len(rd) - Xrd.shape[1])
    s2 = (rrd ** 2).sum() / dof
    se_rd = float(np.sqrt(s2 * XtXi_rd[1, 1]))
    tq = tdist.ppf(0.9, dof)
    est = float(brd[1])
    lo, hi = est - tq * se_rd, est + tq * se_rd
    bL_med = float(np.median(TH[:, names.index("beta_L")]))
    tension = (np.sign(est) != np.sign(bL_med)) and (lo > 0 or hi < 0)
    diag["D6_close_primary_rd"] = {"n": len(rd), "estimate": est, "lo80": lo, "hi80": hi, "tension": bool(tension), "races": rd,
                                   "note": "Sign check only, never estimated into delta. Linear in primary margin with an m24 control; n is tiny."}
else:
    diag["D6_close_primary_rd"] = {"n": len(rd), "estimate": None, "note": "fewer than 4 close ideological primaries with a contested general"}
log("D6:", {k: v for k, v in diag["D6_close_primary_rd"].items() if k != "races"})

# ============================================================== D7 wave compression
alpha_hat = {nm[6:-1]: float(TH[:, i].mean()) for i, nm in enumerate(names) if nm.startswith("alpha[")}
ah = np.array([alpha_hat.get(r["state"], 0.0) for r in main])
Lm = np.array([r["L_M"] - 1 for r in main])
Pm_ = np.array([r["P_M"] for r in main])
o7 = olsfe.fit(main, yadj, labelset="M", style="structural", extra={"Lxalpha": Lm * ah, "Pxalpha": Pm_ * ah})
d7 = {}
for k in ("Lxalpha", "Pxalpha"):
    b, s = float(o7["b"][o7["idx"][k]]), float(o7["se"][o7["idx"][k]])
    d7[k] = [b, b - 1.2816 * s, b + 1.2816 * s]
d7_flag = any(v[1] > 0 or v[2] < 0 for v in d7.values())
diag["D7_wave_compression"] = {"L": d7["Lxalpha"], "P": d7["Pxalpha"], "excludes_zero": bool(d7_flag),
                               "note": "slopes per point of the state wave alpha_s (posterior mean), OLS-FE with CR2 SEs"}
log("D7:", diag["D7_wave_compression"])

# ============================================================== V7 posterior predictive
sig2 = agn["sig2"]
S = TH.shape[0]
c7, cover, lo, hi, eta = ppc_coverage(D0, TH, sig2, rng)
lat = D0.p < 0.95
p_arr = D0.p
resid_mean = D0.yobs + D0.m_s[D0.sidx] * D0.shift_mult - eta.mean(0)
slopes = {}
for nm, v in (("p", p_arr), ("m24", np.array([r["m24"] for r in main]))):
    Xs = np.column_stack([np.ones(len(main)), v])
    bs, rs_, XtXs = ols(Xs, resid_mean)
    s = float(np.sqrt((rs_ ** 2).sum() / (len(main) - 2) * XtXs[1, 1]))
    slopes[nm] = [float(bs[1]), float(bs[1] - 1.2816 * s), float(bs[1] + 1.2816 * s)]
diag["V7_posterior_predictive"] = {
    "coverage80": float(cover.mean()), "n": len(main), "likelihood": meta["likelihood"], "likelihood_trials": meta["likelihood_trials"],
    "coverage_by_office": {o: float(cover[[r["office"] == o for r in main]].mean()) for o in ("House", "Senate", "Governor", "Special")},
    "coverage_by_count_tier": {"p>=0.95": float(cover[~lat].mean()), "0.80<=p<0.95": float(cover[lat].mean()), "n_latent": int(lat.sum())},
    "residual_slopes": slopes,
    "residual_slopes_ok": {k: bool((v[1] <= 0 <= v[2]) or abs(v[0]) < 0.1) for k, v in slopes.items()},
    "ES_slopes": "not run: ES terms dropped (no district demographics)",
}
log("V7:", diag["V7_posterior_predictive"])
diag["residuals"] = {r["id"]: {"resid_mean": float(resid_mean[i]), "eta_mean": float(eta[:, i].mean()), "pred_lo": float(lo[i]),
                                "pred_hi": float(hi[i])} for i, r in enumerate(main)}
# style contribution per race
iL, iP = names.index("beta_L"), names.index("beta_P")
style_contrib = TH[:, iL][:, None] * (D0.L - 1)[None] + TH[:, iP][:, None] * D0.P[None]
if "d_L" in names:
    style_contrib += TH[:, names.index("d_L")][:, None] * (D0.stw * (D0.L - 1))[None] + TH[:, names.index("d_P")][:, None] * (D0.stw * D0.P)[None]
for a in u_active:
    style_contrib += TH[:, names.index(f"u[{a}]")][:, None] * D0.W[:, ARCHETYPES.index(a)][None]
for i, r in enumerate(main):
    diag["residuals"][r["id"]]["style_contrib"] = summ(style_contrib[:, i])

# ============================================================== V8 leave-statewide-out (exact refits)
t0 = time.time()
v8 = []
for i, r in enumerate(main):
    if not r["statewide"]:
        continue
    tr = [x for x in main if x is not r]
    res = {"id": r["id"], "y": r["y_model"]}
    for drop in (False, True):
        D, f = quick_fit(tr, SEED + 800 + i * 2 + drop, chains=2, warm=300, draws=600, labelset="M", drop_style=drop)
        th = f["theta"].reshape(-1, len(D.names))
        s2 = f["sig2"].reshape(-1, 3)
        v = D.row_vector(r)
        e = th @ v
        vgi = 1 if r["office"] == "Senate" else 2
        p = r["p"]
        shift = 0.0 if p >= 0.95 else r["late_shift_prior_mean"] * (1 - p) / 0.2 * r["J"]
        meas = 0.0 if p >= 0.95 else 25 * (1 - p) * r["J"]
        om_ = draw_omega_prior(rng, len(e))
        yr = e - shift + np.sqrt(s2[:, vgi] / om_) * rng.standard_normal(len(e)) + meas * rng.standard_normal(len(e))
        key = "nostyle" if drop else "style"
        res[key] = {"mean": float(e.mean() - shift), "lo": float(np.quantile(yr, 0.1)), "hi": float(np.quantile(yr, 0.9))}
    v8.append(res)
cov8 = float(np.mean([x["style"]["lo"] <= x["y"] <= x["style"]["hi"] for x in v8]))
mae_s = float(np.mean([abs(x["y"] - x["style"]["mean"]) for x in v8]))
mae_n = float(np.mean([abs(x["y"] - x["nostyle"]["mean"]) for x in v8]))
diag["V8_leave_statewide_out"] = {"n": len(v8), "coverage80": cov8, "mae_style": mae_s, "mae_nostyle": mae_n,
                                  "pass": bool(0.70 <= cov8 <= 0.90 and mae_s <= mae_n + 0.2), "races": v8}
log(f"V8: coverage={cov8:.2f} MAE style={mae_s:.2f} nostyle={mae_n:.2f} ({time.time()-t0:.0f}s)")

# ============================================================== V6 Maine (refit without SEN-ME)
me = next(r for r in main if r["id"] == "SEN-ME")
tr = [x for x in main if x["id"] != "SEN-ME"]
D, f = quick_fit(tr, SEED + 60, chains=4, warm=500, draws=1500, labelset="M")
th = f["theta"].reshape(-1, len(D.names))
s2 = f["sig2"].reshape(-1, 3)[:, 1]
v = D.row_vector(me)
style_idx = [D.idx[k] for k in D.idx if k in ("beta_L", "beta_P", "d_L", "d_P") or k.startswith("u[")]
v0 = v.copy()
v0[style_idx] = 0.0
p = me["p"]
Jm = me["J"]
shift = me["late_shift_prior_mean"] * (1 - p) / 0.2 * Jm
om_ = draw_omega_prior(rng, th.shape[0])
noise = np.sqrt(s2 / om_) * rng.standard_normal(th.shape[0]) + Jm * (25 * (1 - p) * rng.standard_normal(th.shape[0]) - (2 * rng.standard_normal(th.shape[0])) * (1 - p) / 0.2)
pa = th @ v - shift + noise
pb = th @ v0 - shift + noise
inc_c = th[:, D.idx["R_inc_pv"]] * (me["R_inc_pv"] - D.ctrl_means["R_inc_pv"]) + th[:, D.idx["inc_R"]] * (me["inc_R"] - D.ctrl_means["inc_R"])
sty_c = th @ v - th @ v0
share = np.abs(inc_c) / (np.abs(inc_c) + np.abs(sty_c) + 1e-9)
nyt = load_json(RESEARCH / "nyt_voter_trends.json")["senate_shift_vs_2024_by_group"]
j = nyt["states"].index("ME")
nyt_me_margin = 0.47 * nyt["rows"]["Male"][j] + 0.53 * nyt["rows"]["Female"][j]
nyt_me = logit50(me["m24"] + nyt_me_margin) - logit50(me["m24"])  # model scale
actual = me["y_model"]
qa, qb = summ(pa), summ(pb)
diag["V6_maine"] = {
    "nominee": me["dem_name"], "archetype": me["M_archetype"], "R_inc_pv": me["R_inc_pv"],
    "pred_with_delta": qa, "pred_delta0": qb, "actual": actual, "actual_reported_overperf_total": me["overperf_reported"],
    "pct_counted": me["pct_counted"], "nyt_implied_shift": nyt_me, "nyt_implied_shift_margin": nyt_me_margin, "actual_margin": me["y"],
    "scale": "model scale = 50 x delta-logit (pts in an even seat); Maine is near even so it is ~ margin points",
    "covers_delta0": bool(qb[1] <= actual <= qb[2]), "covers_with_delta": bool(qa[1] <= actual <= qa[2]),
    "covers_delta0_nyt": bool(qb[1] <= nyt_me <= qb[2]),
    "incumbency_pts": summ(inc_c), "style_pts": summ(sty_c), "share_incumbency": summ(share),
    "discrepancy": {"senate_json_y_two_party": me["y"], "nyt_9state_implied": nyt_me_margin, "gap": me["y"] - nyt_me_margin,
                    "note": (f"senate.json (NBC, 86% counted) has Jackson running +0.66 (total-vote) / {me['y']:.2f} (two-party) ahead of Harris's 2024 Maine margin; "
                             f"the NYT nine-state table implies a {nyt_me_margin:.1f}-point shift (negative = toward R; 0.47*Male + 0.53*Female). Unresolved; both are preliminary. "
                             "The NYT figure is a model estimate from early returns and its 2024 baseline may differ.")},
}
log("V6:", {k: v for k, v in diag["V6_maine"].items() if k != "discrepancy"})
log("V6 discrepancy:", diag["V6_maine"]["discrepancy"]["note"])

# ============================================================== tau_c (§5.5) from incumbents' 2024 and 2026 residuals
pairs = []
iRpv, iDpv = names.index("R_inc_pv"), names.index("D_inc_pv")
for i, r in enumerate(main):
    if r["office"] != "House" or r["lines"] != "2024_same" or r["house24"] is None:
        continue
    if not (r["inc_D"] or r["inc_R"]) or abs(r["house24_total"] or 100) >= 95:
        continue
    pv_back = TH[:, iRpv].mean() * (r["R_inc_pv"] - D0.ctrl_means["R_inc_pv"]) + TH[:, iDpv].mean() * (r["D_inc_pv"] - D0.ctrl_means["D_inc_pv"])
    r26 = resid_mean[i] + pv_back
    sign = 1.0 if r["inc_D"] else -1.0  # incumbent-party orientation
    pairs.append((sign * (logit50(r["house24"]) - logit50(r["m24"])), sign * r26))
if len(pairs) >= 3:
    a24 = np.array([p[0] for p in pairs])
    a26 = np.array([p[1] for p in pairs])
    cov = float(np.cov(a24 - a24.mean(), a26 - a26.mean())[0, 1])
else:
    cov = None
use = cov is not None and len(pairs) >= 40 and cov > 0
diag["tau_c"] = {"n_incumbents": len(pairs), "cov": cov, "tau_c": float(np.sqrt(cov)) if use else 2.0,
                 "estimated": bool(use), "sensitivity": [1.0, 3.0],
                 "note": "r26 adds back the fitted personal-vote term (the model controls for it); oriented to the incumbent's party. Fallback tau_c=2 if < 40 incumbents or Cov <= 0."}
log("tau_c:", diag["tau_c"])

save_json(WORK / "diagnostics.json", diag, nd=5, indent=1)
log.save()
