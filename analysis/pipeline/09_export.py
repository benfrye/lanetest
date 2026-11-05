"""Step 09: assemble model_params (§6.4 schema) and races.json.

The params are written to work/model_params.candidate.json. 10_validate.py promotes the file to
output/model_params.json only if no blocking validation item FAILs without a logged override
(METHODOLOGY §7); otherwise it is written as output/model_params.BLOCKED.json (same schema).

Overrides are read from the '## Overrides' section of analysis/methodology_decisions.md: any line
naming an item id (e.g. 'V12', 'D2', 'V7') counts as a logged override for that item.
"""
import hashlib
import math
import re

import numpy as np

from common import (ANALYSIS, ARCHETYPES, NON_REF, OUT, PIPE, RESEARCH, SEED, WORK, Log, load_json, now_iso,
                    save_json, summ)
from gibbs import PRESETS

log = Log("09_export")
rng = np.random.default_rng(SEED + 90)
rows = load_json(WORK / "dataset_labeled.json")
meta = load_json(WORK / "fit_meta.json")
diag = load_json(WORK / "diagnostics.json")
rob = load_json(WORK / "robustness.json")
labels = load_json(WORK / "labels_report.json")
U = load_json(WORK / "units.json")
errs = load_json(WORK / "errors.json")
sim5 = load_json(WORK / "sim5.json")
cands = load_json(WORK / "candidates.json")
primary = load_json(WORK / "primary.json")
STORY = OUT / "story_data"
oax = load_json(STORY / "oaxaca_decomposition.json")["by_archetype"]
quiz = load_json(STORY / "quiz_pairs.json")["pairs"]
nyt9 = load_json(STORY / "nyt_nine_state.json")
rawst = load_json(STORY / "raw_overperformance_by_archetype.json")
main = [r for r in rows if r["in_main"]]
asof = load_json(RESEARCH / "senate.json")["as_of"]


# ------------------------------------------------------------------ overrides
def read_overrides():
    txt = (ANALYSIS / "methodology_decisions.md").read_text()
    sec = txt.split("## Overrides", 1)[1] if "## Overrides" in txt else ""
    # Only explicit 'blanket-override: V7' style lines unblock a FAIL; decision rows (O-1a ...) do not.
    return sorted(set(re.findall(r"blanket-override:\s*(V\d{1,2}|D\d)", sec)))


overrides = read_overrides()
log("logged overrides:", overrides or "none")
pb_raw = diag["D2_ols_fe"]["publish_blocked"]
# O-1c: a D2 disagreement no longer blocks publication; the disagreeing cell is bracketed instead.
models_disagree = {a: bool(v) for a, v in diag["D2_ols_fe"].get("models_disagree", {}).items()}
publish_blocked = False
placebo_all = all(diag["D5_placebo"]["placebo_flag"].get(a) and (diag["D5_placebo"]["by_archetype"][a].get("placebo") is not None and
                  abs(diag["D5_placebo"]["by_archetype"][a]["placebo"]) >= abs(diag["gibbs_delta_agnostic"][a]["med"])) for a in NON_REF)
levels = list(meta["levels_triggered"])
if publish_blocked or placebo_all:
    levels.append({"level": 5, "trigger": ("publish_blocked (D2/V12) unresolved" if publish_blocked else "") + (" placebo >= |effect| for every archetype" if placebo_all else ""),
                   "action": "2026-is-uninformative mode: style draws from the Agnostic prior only; dial disabled; the Sim 4 heatmap is the centerpiece"})
fit_level = max(l["level"] for l in levels)
log(f"fit_level = {fit_level}; publish_blocked = {publish_blocked} (raw D2 flag {pb_raw})")

# ------------------------------------------------------------------ style draws
cents = meta["centroids"]
u_active = meta["u_active"]


def load_fit(preset):
    z = np.load(WORK / f"fit_{preset}.npz", allow_pickle=True)
    names = list(z["names"])
    th = z["theta"]
    get = lambda nm: th[:, names.index(nm)]
    out = {"beta_L": get("beta_L"), "beta_P": get("beta_P"), "omega_maga": get("omega_maga"), "omega_mod": get("omega_mod"),
           "u": {a: (get(f"u[{a}]") if f"u[{a}]" in names else np.zeros(len(th))) for a in ARCHETYPES}}
    return out


def derive(d):
    d["delta"] = {a: d["beta_L"] * ((cents[a]["L"] if cents[a]["L"] is not None else 1.0) - 1)
                  + d["beta_P"] * (cents[a]["P"] if cents[a]["P"] is not None else 0.0) + d["u"][a] for a in ARCHETYPES}
    return d


def prior_draws(preset):
    pr = PRESETS["literature" if preset == "literature" else "agnostic"]
    n = 1000
    tau = np.abs(rng.standard_normal(n))
    d = {"beta_L": rng.normal(pr["beta_L"][0], pr["beta_L"][1], n), "beta_P": rng.normal(pr["beta_P"][0], pr["beta_P"][1], n),
         "omega_maga": rng.normal(pr["omega_maga"][0], pr["omega_maga"][1], n), "omega_mod": rng.normal(pr["omega_mod"][0], pr["omega_mod"][1], n),
         "u": {a: (tau * rng.standard_normal(n) if a in u_active else np.zeros(n)) for a in ARCHETYPES}}
    return derive(d)


fitted = {p: derive(load_fit(p)) for p in ("agnostic", "literature", "discount", "data_only")}
presets_out = {}
for p in ("agnostic", "literature", "discount", "data_only"):
    d = prior_draws(p) if fit_level == 5 else fitted[p]
    pr = PRESETS[p]
    if fit_level == 5:
        sdr = {"beta_L": 1.0, "beta_P": 1.0}
    else:
        sdr = {b: (float(d[b].std() / pr[b][1]) if pr[b][1] else None) for b in ("beta_L", "beta_P")}
    presets_out[p] = {"beta_L": d["beta_L"], "beta_P": d["beta_P"], "beta_PW": np.zeros(1000), "beta_LY": np.zeros(1000),
                      "u": {a: d["u"][a] for a in ARCHETYPES}, "delta": {a: d["delta"][a] for a in ARCHETYPES},
                      "omega_maga": d["omega_maga"], "omega_mod": d["omega_mod"], "sd_ratio": sdr}
    if fit_level == 5:
        presets_out[p]["source"] = "prior_only (Level 5)" + ("; data_only has no proper prior, agnostic prior used" if p == "data_only" else "")

# ------------------------------------------------------------------ O-8: history-based style preset
# The 2028 translation defaults to lane gaps estimated across 2018, 2022 and 2026 and read off
# at an even national environment (analysis/history), because 2026's wave compressed the gaps.
# Draws: normal around each even-year gap, SD from its 80% interval widened 1.5x (the history
# intervals count sampling noise only). beta_L and beta_P are solved per draw so the progressive
# and left-populist gaps are hit exactly; moderates keep the rest as u; center populists (too
# few races in any cycle) get the structural value with their spread doubled. omega comes from
# the 2026 fit (opponent type is not coded before 2026).
HIST = ANALYSIS / "history" / "history_comparison.json"
# §5.4 rule: re-center pi on the presidential/midterm ratio of the ideology coefficient only if its
# 80% interval excludes 1. Recorded either way.
hist_pi = None
if HIST.exists():
    _p = load_json(HIST)["headline"]["pi"]["beta_L"]
    hist_pi = {"ratio": _p["point"], "lo80": _p["lo80"], "hi80": _p["hi80"], "recentred": bool(_p["hi80"] < 1 or _p["lo80"] > 1),
               "source": "analysis/history: leftness slope in 2020/2024 vs 2018/2022 House races"}
default_style_preset = "agnostic"
history_summary = None
if HIST.exists():
    # O-9 (model review): the history line uses competitive seats only (|pres| <= 20, every label
    # individually researched), not all seats, whose progressive slope came from safe-seat incumbents.
    he = load_json(HIST)["competitive"]["env_model"]["logit"]
    rng_h = np.random.default_rng(SEED + 808)
    def _hist_draws(a):
        g = he[a]["three_cycle"]["fe"]
        sd = (g["even_hi80"] - g["even_lo80"]) / (2 * 1.2816) * 1.5
        return g["even_gap"] + sd * rng_h.standard_normal(1000)
    d_pr, d_lp, d_mo = _hist_draws("progressive"), _hist_draws("left_populist"), _hist_draws("moderate")
    cp, cl = cents["progressive"], cents["left_populist"]
    # d = bL (L-1) + bP P at the progressive and left-populist centroids
    det = (cp["L"] - 1) * cl["P"] - cp["P"] * (cl["L"] - 1)
    bL = (d_pr * cl["P"] - cp["P"] * d_lp) / det
    bP = ((cp["L"] - 1) * d_lp - (cl["L"] - 1) * d_pr) / det
    struct = lambda a: bL * (cents[a]["L"] - 1) + bP * cents[a]["P"]
    d_cp = struct("center_populist")
    hist_delta = {"progressive": d_pr, "left_populist": d_lp, "moderate": d_mo, "center_populist": d_cp,
                  "mainstream_liberal": np.zeros(1000)}
    hist_u = {a: (hist_delta[a] - struct(a)) if a in ("moderate",) else np.zeros(1000) for a in ARCHETYPES}
    ag = presets_out["agnostic"]
    presets_out["history"] = {"beta_L": bL, "beta_P": bP, "beta_PW": np.zeros(1000), "beta_LY": np.zeros(1000),
                              "u": hist_u, "delta": hist_delta, "omega_maga": ag["omega_maga"], "omega_mod": ag["omega_mod"],
                              "sd_ratio": {"beta_L": None, "beta_P": None},
                              "source": "history: competitive-seat 2018/2022/2026 House lane gaps at an even environment (analysis/history), O-8/O-9"}
    # O-9: the 2028 default blends the two sources draw by draw (even draws: 2026 fit; odd: history),
    # so every 2028 range spans both instead of picking one.
    def _mix(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        out = x.copy()
        out[1::2] = y[1::2]
        return out
    hs = presets_out["history"]
    presets_out["blend"] = {"beta_L": _mix(ag["beta_L"], hs["beta_L"]), "beta_P": _mix(ag["beta_P"], hs["beta_P"]),
                            "beta_PW": np.zeros(1000), "beta_LY": np.zeros(1000),
                            "u": {a: _mix(ag["u"][a], hs["u"][a]) for a in ARCHETYPES},
                            "delta": {a: _mix(ag["delta"][a], hs["delta"][a]) for a in ARCHETYPES},
                            "omega_maga": ag["omega_maga"], "omega_mod": ag["omega_mod"], "sd_ratio": {"beta_L": None, "beta_P": None},
                            "source": "blend: alternate draws from the 2026 fit and the competitive-seat history line (O-9)"}
    default_style_preset = "blend"
    history_summary = {a: {"even_gap": he[a]["three_cycle"]["fe"]["even_gap"], "lo80": he[a]["three_cycle"]["fe"]["even_lo80"],
                           "hi80": he[a]["three_cycle"]["fe"]["even_hi80"]} for a in ("progressive", "left_populist", "moderate")}
    history_summary["sample"] = "competitive seats (|pres| <= 20)"
    _cc = load_json(HIST)["competitive"]["cycles"]
    history_summary["competitive_cycles"] = {y: {"env": _cc[y]["env"], "presidential": _cc[y]["presidential_year"],
        "gaps": {a: {k: _cc[y]["logit"]["adjusted"][a][k] for k in ("est", "lo80", "hi80", "n")} for a in ("progressive", "left_populist", "moderate") if a in _cc[y]["logit"]["adjusted"]}} for y in _cc}
    _ae = load_json(HIST)["headline"]["even_environment"]
    history_summary["all_seats"] = {a: _ae[a]["gls_3cycle"]["even_gap"] for a in ("progressive", "left_populist", "moderate")}
    _pc = load_json(HIST)["headline"]["per_cycle"]
    history_summary["per_cycle"] = {y: {a: _pc[y][a]["est"] for a in ("progressive", "left_populist", "moderate") if a in _pc[y]} for y in _pc}
    log("history preset means:", {a: round(float(hist_delta[a].mean()), 2) for a in ARCHETYPES}, "blend means:", {a: round(float(presets_out["blend"]["delta"][a].mean()), 2) for a in ARCHETYPES})

# ------------------------------------------------------------------ Gaussian dial (§3.3) and V15
do = fitted["data_only"]
bhat2 = np.array([do["beta_L"].mean(), do["beta_P"].mean()])
V2 = np.cov(np.vstack([do["beta_L"], do["beta_P"]]))
BIG = 1e4
Vhat = np.zeros((4, 4))
Vhat[:2, :2] = V2
Vhat[2, 2] = Vhat[3, 3] = BIG
bhat = np.array([bhat2[0], bhat2[1], 0.0, 0.0])
mu0 = {"agnostic": [0.0, 0.0, 0.0, 0.0], "literature": [-1.5, 0.0, 0.0, 0.0]}
S0 = {"agnostic": np.diag([4.0, 4.0, 0.25, 0.25]), "literature": np.diag([2.25, 2.25, 0.25, 0.25])}


def dial(prior, k, alpha):
    S0i = np.linalg.inv(S0[prior]) / k ** 2
    Vi = np.linalg.inv(Vhat)
    Sp = np.linalg.inv(S0i + alpha * Vi)
    mp = Sp @ (S0i @ np.array(mu0[prior]) + alpha * Vi @ bhat)
    return mp[:2], np.sqrt(np.diag(Sp)[:2])


v15 = {}
ok = True
for p, (prior, k, alpha) in {"agnostic": ("agnostic", 1, 1), "literature": ("literature", 1, 1), "discount": ("agnostic", 1, 0.5),
                             "data_only": ("agnostic", 1e6, 1)}.items():
    m, s = dial(prior, k, alpha)
    ex = fitted[p]
    em = np.array([ex["beta_L"].mean(), ex["beta_P"].mean()])
    es = np.array([ex["beta_L"].std(), ex["beta_P"].std()])
    mean_ok = np.all(np.abs(m - em) <= 0.1 * es)
    sd_ok = np.all(np.abs(s / es - 1) <= 0.10)
    v15[p] = {"dial_mean": m.tolist(), "exact_mean": em.tolist(), "dial_sd": s.tolist(), "exact_sd": es.tolist(),
              "mean_ok": bool(mean_ok), "sd_ok": bool(sd_ok)}
    ok &= bool(mean_ok and sd_ok)
dial_enabled = bool(ok and fit_level < 5)
log("V15 dial:", {p: (v["mean_ok"], v["sd_ok"]) for p, v in v15.items()}, "-> dial_enabled", dial_enabled)
# R5 k-sweep via the dial (robustness rows)
ksweep = {str(k): dict(zip(("beta_L", "beta_P"), dial("agnostic", k, 1)[0].tolist())) for k in (0.5, 1, 2, 4)}

# ------------------------------------------------------------------ hull of nominee (L, P) with >= 5 races nearby
from collections import Counter

cnt = Counter((r["L_M"], r["P_M"]) for r in main)
# Support region: grid points with >= 2 nominees, plus every archetype centroid. A centroid
# is an average of real nominees, so a reader choosing it is never extrapolating (lead
# reviewer, 2026-11-04: the >= 5 rule excluded 4 of 5 centroids).
pts = {pt for pt, c in cnt.items() if c >= 2}
for a in sorted({r["M_archetype"] for r in main}):
    rs = [r for r in main if r["M_archetype"] == a]
    pts.add((round(sum(r["L_M"] for r in rs) / len(rs), 5), round(sum(r["P_M"] for r in rs) / len(rs), 5)))
pts = sorted(pts)


def hull(points):
    if len(points) <= 2:
        return [list(p) for p in points]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]


hull_pts = hull(pts)
log("hull:", hull_pts, "grid counts:", dict(cnt))

# ------------------------------------------------------------------ transfer pi
# O-9 (model review): pi is centred on the presidential-year evidence (House lane gaps in 2020/2024
# ran about half their midterm size: leftness ratio 0.54, moderate 0.41) at 0.6, with a wider spread.
PI_MU, PI_SIGMA, PI_CLIP = math.log(0.6), 0.45, (0.2, 1.5)
pi_draws = np.clip(np.exp(rng.normal(PI_MU, PI_SIGMA, 1000)), *PI_CLIP)
ag = fitted["agnostic"]
z = np.load(WORK / "fit_agnostic.npz", allow_pickle=True)
nm = list(z["names"])
dL = z["theta"][:, nm.index("d_L")] if "d_L" in nm else np.zeros(1000)
ratio = (ag["beta_L"] + dL) / ag["beta_L"]
swh = summ(ratio)
d7 = diag["D7_wave_compression"]

# ------------------------------------------------------------------ copy flags
lab_k = labels["kappa_agent_vs_second_coder_proxy"]
if lab_k["archetype"]["kappa"] is not None and lab_k["archetype"]["kappa"] < 0.4:
    reliab = "low"
elif lab_k["posture"]["kappa"] is not None and lab_k["posture"]["kappa"] < 0.6:
    reliab = "low_posture"
else:
    reliab = "ok"
copy_flags = {
    "no_detectable_effect": bool(diag["D3_freedman_lane"]["no_detectable_effect"]),
    "no_predictive_gain": bool(diag["D4_grouped_cv"]["no_predictive_gain"]),
    "lead_with_overlap": bool(diag["D1_overlap"]["lead_with_overlap"]),
    "publish_blocked": publish_blocked,
    "placebo_flag": diag["D5_placebo"]["placebo_flag"],
    "direction_depends_on_prior": rob["direction_depends_on_prior"],
    "provisional_archetypes": rob["provisional_archetypes"],
    "maine_explained_by_incumbent": bool(diag["V6_maine"]["covers_delta0"]),
    "models_disagree": models_disagree,
    "label_reliability": reliab,
}
log("copy_flags:", copy_flags)

# ------------------------------------------------------------------ reveal
reveal = {"raw": {}, "adjusted": {}, "decomposition": {}, "quiz_pairs": [], "fragility": [], "maine": {}, "nyt9": {}}
for a in ARCHETYPES:
    sel = [r for r in main if r["M_archetype"] == a]
    cs = rawst["common_support"][a]
    reveal["raw"][a] = {"mean": float(np.mean([r["y"] for r in sel])) if sel else None, "n": len(sel),
                        "n_states": len({r["state"] for r in sel}), "dist_m24": cs["m24"], "dist_wnc": cs["wnc_state"],
                        "dist_y1829": cs["y1829_state"], "dist_urban": cs["urban_state"]}
    dd = fitted["agnostic"]["delta"][a]
    q = summ(dd)
    reveal["adjusted"][a] = {"med": q[0], "lo": q[1], "hi": q[2], "min_n_ok": meta["min_n"][a]["ok"],
                             "mostly_prior": bool(dd.std() / 2.0 > 0.7)}
    if models_disagree.get(a):
        eb = diag["D2_ols_fe"]["by_archetype"][a]["eb_shrunk"]
        reveal["adjusted"][a]["delta_range_models"] = sorted([q[0], eb])
        reveal["adjusted"][a]["delta_range_sources"] = {"gibbs_median": q[0], "ols_fe_eb": eb}
for a, o in oax.items():
    reveal["decomposition"][a] = {k: o.get(k, 0.0) for k in ("lean", "demographic", "incumbency", "opponent", "state_wave", "style", "residual", "office")}
for p in quiz:
    reveal["quiz_pairs"].append({k: {"name": p[k]["name"], "district": p[k]["district"], "archetype": p[k]["archetype"], "y": p[k]["y"]} for k in ("a", "b")})
for run in rob["runs"]:
    if "delta" not in run:
        continue
    for a in NON_REF:
        v = run["delta"][a]
        reveal["fragility"].append({"label": run["label"], "archetype": a, "med": v[0], "lo": v[1], "hi": v[2]})
v6 = diag["V6_maine"]
reveal["maine"] = {"pred_with_delta": v6["pred_with_delta"], "pred_delta0": v6["pred_delta0"], "actual": v6["actual"],
                   "share_incumbency": v6["share_incumbency"], "incumbency_pts": v6["incumbency_pts"], "style_pts": v6["style_pts"],
                   "nominee": v6["nominee"], "nyt_implied": v6["nyt_implied_shift"]}
reveal["nyt9"] = {"table": nyt9["table"], "sd_across_states": nyt9["sd_across_states"], "psi_P": nyt9["psi_P"]}

# ------------------------------------------------------------------ units
units_out = []
for u in U["units"]:
    v = {k: u[k] for k in ("id", "name", "type", "parent", "ev", "m24", "m20", "m16", "rel24", "rel20", "rel26", "G", "W_tilde",
                           "Y_tilde", "F", "sigma_idio", "shares")}
    if u["type"] == "district":
        v["district_sd"] = u["district_sd"]
    units_out.append(v)

# ------------------------------------------------------------------ pipeline "commit" (no git repo): content hash
h = hashlib.sha256()
for f in sorted(PIPE.glob("*.py")) + sorted(PIPE.glob("*.sh")):
    h.update(f.read_bytes())
commit = "nogit-" + h.hexdigest()[:12]

mp = {
    "meta": {"version": "2026-11-04-prelim-1", "generated_at": now_iso(), "data_as_of": asof, "preliminary": True,
             "fit_level": fit_level, "seed": SEED, "pipeline_commit": commit, "n_param_draws": 1000,
             "notes": [f"Level {l['level']}: {l['trigger']} -> {l['action']}" for l in levels]
             + [f"logged overrides: {overrides or 'none'}",
                "E24 computed from certified state totals in states.json = %.3f (METHODOLOGY text says -1.43; see SCHEMA_NOTES.md)" % U["E24"],
                "Fitted (unpublished) style posteriors are summarised in analysis/output/findings.md and validation.json" if fit_level == 5 else "",
                "Primary model: " + primary["_meta"]["notes"],
                "Units: UT 2016 margin carries the McMullin flag and is never used in a lean"]},
    "national": {"E24": U["E24"], "ev_total": 538, "ev_win": 270},
    "units": units_out,
    "errors": {"factor_names": errs["factor_names"], "idio_df": 5, "calibrated": False, "target_rel_sd": 3.5, "district_sd": 1.5,
               "backtest": {"cov80_2016": None, "cov80_2020": errs["V3"]["transitions"]["2020"]["coverage80"],
                            "cov80_2024": errs["V3"]["transitions"]["2024"]["coverage80"]}},
    # O-7: the default is an even national vote with history's width; the post-midterm
    # historical mean (D+3) stays available as the "history" preset.
    "environment": {"default_preset": "even",
                    "presets": {"rerun2024": {"type": "point", "value": round(U["E24"], 2)}, "neutral": {"type": "point", "value": 0},
                                "even": {"type": "t", "df": 5, "loc": 0, "scale": 5},
                                "history": {"type": "t", "df": 5, "loc": 3, "scale": 5}, "regress26": {"type": "normal", "mean": 5.3, "sd": 5.6},
                                "wave_holds": {"type": "point", "value": 13, "warning": "larger than any presidential margin since 1984"}},
                    "slider": {"min": -10, "max": 15, "step": 0.5}},
    "transfer_pi": {"default_mode": "sampled", "sampled": {"type": "lognormal", "mu": PI_MU, "sigma": PI_SIGMA, "clip": list(PI_CLIP)},
                    "slider": {"min": 0.2, "max": 1.5, "step": 0.05},
                    "evidence": {"statewide_house_ratio": swh, "wave_compression": {"L": d7["L"], "P": d7["P"]}, "historical_pres_mid_ratio": hist_pi},
                    "pi_draws": pi_draws},
    "turnout_u": {"default": 0, "min": -1, "max": 1, "offered_as": "scenario"},
    "lean": {"psi": 0.2, "psi_calibrated": False, "phi": 0, "phi_max": 0.5},
    "style": {
        "default_preset": default_style_preset,
        "history_summary": history_summary,
        "coords": {a: {"L": cents[a]["L"], "P": cents[a]["P"], "n": meta["min_n"][a]["n"], "n_states": meta["min_n"][a]["n_states"],
                       "min_n_ok": meta["min_n"][a]["ok"]} for a in ARCHETYPES},
        "hull": hull_pts,
        "presets": presets_out,
        "gaussian": {"names": ["beta_L", "beta_P", "beta_PW", "beta_LY"], "bhat": bhat, "Vhat": Vhat, "mu0": mu0,
                     "Sigma0": {k: v for k, v in S0.items()}, "dial_enabled": dial_enabled},
        "interactions": {k: {"gate_passed": v["gate_passed"], "badge": v["badge"]} for k, v in meta["interaction_gate"].items()},
        "tilt_default_on": False,
    },
    "reveal": reveal,
    "copy_flags": copy_flags,
    "candidates_dem": [{k: c[k] for k in ("id", "name", "archetype", "L", "P", "home", "track", "poll_nat_primary", "market_nom", "include_default")}
                       for c in cands["dem"]],
    "candidates_gop": [{k: c[k] for k in ("id", "name", "opp_type", "home", "track", "market_nom")} for c in cands["gop"]],
    "home_effect": {"mean": 2.0, "sd": 1.5, "vp": 0.5},
    "rho": {"default": 0.5, "min": 0, "max": 1},
    "primary": {k: v for k, v in primary.items() if k != "_meta"},
    "sim5": {"units": [{k: s[k] for k in ("id", "house26", "house26_sd", "pct_counted", "imputed_share", "electorate_adj", "hatched")}
                       for s in sim5["units"]],
             "national_house26": sim5["national_house26"], "durable_phi_default": 1,
             "senate": [{"id": s["id"], "margin": s["margin"]} for s in sim5["senate"]],
             "governor": [{"id": s["id"], "margin": s["margin"]} for s in sim5["governor"]]},
    "banners": {"not_forecast": "A translation under stated assumptions, not a forecast.",
                "preliminary": f"Preliminary: results as of {asof}; several races are uncalled and Western states are still counting.",
                "primary_weak_proxy": "40 House primaries are a weak proxy for a national primary.",
                "wave_shape": "The wave's demographic shape is only partly controlled (district demographics unavailable).",
                **({"uninformative": "2026 doesn't tell us; here's what you'd have to believe."} if fit_level == 5 else {})},
}
mp["meta"]["notes"] = [n for n in mp["meta"]["notes"] if n]
save_json(WORK / "model_params.candidate.json", mp, nd=5)
save_json(WORK / "export_meta.json", {"fit_level": fit_level, "levels": levels, "publish_blocked": publish_blocked, "publish_blocked_raw": pb_raw,
                                      "models_disagree": models_disagree,
                                      "overrides": overrides, "V15": v15, "dial_enabled": dial_enabled, "ksweep": ksweep,
                                      "statewide_house_ratio": swh, "copy_flags": copy_flags}, nd=5, indent=1)

# ------------------------------------------------------------------ races.json
res = diag["residuals"]
races = []
for r in rows:
    rr = res.get(r["id"], {})
    races.append({
        "id": r["id"], "office": r["office"], "state": r["state"], "district": r["district"],
        "dem_name": r["dem_name"], "dem_party_label": r["dem_party_label"], "archetype": r["archetype"], "ideology": r["ideology"],
        "posture": r["posture"], "style_confidence": r["style_confidence"],
        "fit_archetype": r["M_archetype"], "label_source": r["label_source"], "label_audit": r["label_audit"], "rule_archetype": r["B_archetype"],
        "rep_name": r["rep_name"], "rep_style": r["rep_style_raw"],
        "dem_pct": r["dem_pct"], "rep_pct": r["rep_pct"], "margin": r["margin_total"], "margin_2p": r["m26"],
        "pres2024_margin": r["pres24_total"], "pres2024_margin_2p": r["m24"], "overperformance": r["y"],
        "overperformance_model_scale": r.get("y_model"), "competitive": r.get("competitive"),
        "overperformance_reported": r["overperf_reported"], "pct_counted": r["pct_counted"], "count_tier": r["count_tier"],
        "called": r["called"], "flipped": r["flipped"], "dem_incumbent": r["dem_incumbent"], "rep_incumbent": r["rep_incumbent"],
        "open_seat": r["open_seat"], "lines": r["lines"], "R_inc_pv": r["R_inc_pv"], "D_inc_pv": r["D_inc_pv"],
        "included_in_fit": r["in_main"], "exclusion_reason": r["exclusion_reason"],
        "in_extended": r["in_extended"], "in_provisional": r["in_provisional"],
        "adjusted_residual": rr.get("resid_mean"), "style_contribution": rr.get("style_contrib"), "predicted_80": [rr.get("pred_lo"), rr.get("pred_hi")] if rr else None,
        "data_flags": r["data_flags"],
    })
save_json(OUT / "races.json", {"data_as_of": asof, "preliminary": True, "n": len(races),
                               "fields": "margins are D-R points; *_2p are two-party; overperformance = margin_2p - pres2024_margin_2p; overperformance_model_scale = 50 x delta-logit of the two-party D share (the main fit's outcome; equals margin points in an even seat); adjusted_residual and style_contribution are on the model scale; style_contribution = [median, lo80, hi80] of the fitted (agnostic) style terms",
                               "races": races}, nd=3)
log(f"races.json: {len(races)} rows; candidate model_params written (fit_level {fit_level})")
log.save()
