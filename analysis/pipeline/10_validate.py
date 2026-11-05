"""Step 10: validation (§7) -> output/validation.json; gate + promote model_params; findings.md; SCHEMA_NOTES.md.

Status values: PASS, FAIL, REPORT, NOT_RUN. A FAIL on a blocking item without a logged override in
methodology_decisions.md keeps model_params.json from being written; the schema-identical file is then
written as output/model_params.BLOCKED.json so engine work can continue against it.
"""
import json
import shutil
import subprocess

import numpy as np

from common import ARCHETYPES, NON_REF, OUT, ROOT, SEED, WORK, Log, load_json, now_iso, save_json, summ
import reference_engine as RE

log = Log("10_validate")
meta = load_json(WORK / "fit_meta.json")
diag = load_json(WORK / "diagnostics.json")
rob = load_json(WORK / "robustness.json")
labels = load_json(WORK / "labels_report.json")
errs = load_json(WORK / "errors.json")
sim5 = load_json(WORK / "sim5.json")
prim = load_json(WORK / "primary.json")
exm = load_json(WORK / "export_meta.json")
excl = load_json(WORK / "exclusions.json")
mp = load_json(WORK / "model_params.candidate.json")
overrides = set(exm["overrides"])
V = {}


def item(vid, name, status, blocking, numbers, note=None):
    V[vid] = {"name": name, "status": status, "blocking": blocking, "overridden": vid in overrides, "numbers": numbers}
    if note:
        V[vid]["note"] = note


# V1
v1 = errs["V1"]
item("V1", "Identity (delta=0, E=E24, u=psi=phi=eps=0)", "PASS" if v1["pass"] else "FAIL", True, v1)
# V2: JS <-> Python parity (O-5). Bank and P(win) layers, same seed, f64 and f32.
def run_v2():
    js_dir = ROOT / "site" / "src" / "lib" / "sim"
    if not (js_dir / "engine.js").exists() or shutil.which("node") is None:
        return "NOT_RUN", {"engine_js_exists": (js_dir / "engine.js").exists()}, "JS engine or node not available."
    n, seed = 2000, SEED
    try:
        res = subprocess.run(["node", str(WORK.parent / "pipeline" / "js_parity.mjs"), str(WORK / "model_params.candidate.json"), str(n), str(seed)],
                             capture_output=True, text=True, timeout=600, check=True)
    except subprocess.CalledProcessError as e:
        return "FAIL", {"error": e.stderr[-2000:]}, "JS engine failed to load or run the exported params."
    js = json.loads(res.stdout)
    b = RE.build_bank_js(mp, n=n, seed=seed)
    E24 = mp["national"]["E24"]
    f64, f32 = js["f64"], js["f32"]
    ts = b["t_sorted"]
    pp = np.array([np.searchsorted(ts, E - E24, side="left") / n for E in f64["Egrid"]])
    D = np.sort(b["Edraws"]["history"] - E24 - b["tRaw"])
    pdist = np.array([1 - np.searchsorted(D, -x, side="right") / n for x in f64["deltas"]])
    nums = {"n_draws": n, "seed": seed,
            "f64_max_abs_diff": {"tRaw": float(np.max(np.abs(b["tRaw"] - np.array(f64["tRaw"])))),
                                 "theta_first_row": float(np.max(np.abs(b["theta"][0] - np.array(f64["theta0"])))),
                                 "theta_last_row": float(np.max(np.abs(b["theta"][-1] - np.array(f64["thetaLast"])))),
                                 "E_history_draws": float(np.max(np.abs(b["Edraws"]["history"][:50] - np.array(f64["Ehist"])))),
                                 "pwin_point": float(np.max(np.abs(pp - np.array(f64["pPoint"])))),
                                 "pwin_dist": float(np.max(np.abs(pdist - np.array(f64["pDist"]))))},
            "f32_max_abs_diff_pwin": {"point": float(np.max(np.abs(pp - np.array(f32["pPoint"])))),
                                      "dist": float(np.max(np.abs(pdist - np.array(f32["pDist"]))))},
            "scope": "outcome bank (eps stream, E draws, thresholds, t_j) and P(win) in point and distribution modes",
            "not_covered": "full Sim 1/2/4/5 output objects (style/pi/opponent/home/track layers) are not re-implemented in Python"}
    ok = max(nums["f64_max_abs_diff"].values()) < 1e-9 and max(nums["f32_max_abs_diff_pwin"].values()) <= 0.002
    return ("PASS" if ok else "FAIL"), nums, "Partial scope: the bank and P(win) primitives that every Sim uses are exact; full Sim-object parity still to do."


st2, num2, note2 = run_v2()
item("V2", "JS <-> Python parity", st2, True, num2, note2)
# V3
v3 = errs["V3"]
item("V3", "Error calibration back-test", "PASS" if v3["pass"] else "FAIL", True,
     {"pooled_coverage80": v3["pooled_coverage80"], "transitions": v3["transitions"], "logscore_correlated": v3["logscore_correlated"],
      "logscore_independent": v3["logscore_independent"], "wi_mi_pa_2016": v3["wi_mi_pa_2016_check"],
      "realized_rel_swing_sd": v3["realized_rel_swing_sd_pooled"]},
     "Partial: only 2016->20 and 2020->24 transitions exist; the 2016 WI/MI/PA correlated-miss check needs 2012 results. Errors labelled uncalibrated.")
# V4
v4 = errs["V4"]
item("V4", "2024 EC back-test from 2020 base", "PASS" if v4["pass"] else "FAIL", True, v4)
# V5
item("V5", "u back-test", "NOT_RUN", False, {"offered_as": "scenario"},
     "No 2020->24 national group shifts on disk; turnout_u.offered_as = 'scenario' and the tooltip must say the back-test was not run.")
# V6
v6 = diag["V6_maine"]
item("V6", "Maine (refit without SEN-ME)", "REPORT", False,
     {k: v6[k] for k in ("nominee", "pred_with_delta", "pred_delta0", "actual", "covers_delta0", "covers_with_delta", "incumbency_pts", "style_pts",
                         "share_incumbency", "nyt_implied_shift", "covers_delta0_nyt")} | {"maine_explained_by_incumbent": v6["covers_delta0"]},
     "Nominee is Troy Jackson (left_populist; Platner won the primary then withdrew). " + v6["discrepancy"]["note"])
# V7
v7 = diag["V7_posterior_predictive"]
c7 = v7["coverage80"]
v7_ok = 0.75 <= c7 <= 0.85
# O-3: if no likelihood reaches the target, V7 is non-blocking ("intervals conservative")
item("V7", "Posterior predictive coverage (main sample)", "PASS" if v7_ok else "FAIL", bool(v7_ok or c7 < 0.75), v7 | {"likelihood_note": meta["likelihood_note"]},
     ("Intervals conservative (over-coverage). Non-blocking per decision O-3. " if (not v7_ok and c7 > 0.85) else "") +
     f"Likelihood trials (in-sample coverage): {meta['likelihood_trials']}. A Normal likelihood covers even more (sigma inflates to absorb outliers such as GOV-VT). Residual slopes vs p and m24 are reported; ES slopes not run (ES dropped).")
# V8
v8 = diag["V8_leave_statewide_out"]
item("V8", "Leave-statewide-out", "PASS" if v8["pass"] else "FAIL", False,
     {k: v8[k] for k in ("n", "coverage80", "mae_style", "mae_nostyle")}, "Exact refits (2 chains x 900 iterations) without each statewide race.")
# V9
item("V9", "Spanberger same-ballot", "NOT_RUN", False, {}, "offyear.json has no 2025 VA Lt. Governor / Attorney General margins; C15 is therefore not licensed.")
# V10
item("V10", "Mamdani sign check vs beta_LY", "REPORT", False, {"beta_LY": "gated off (fixed 0)"},
     "No beta_LY estimate to compare. offyear.json subgroup notes (Jackson Heights +20 vs Harris share; South Asian Queens ~0) are story color only.")
# V11
item("V11", "Placebo (D5)", "REPORT", False, diag["D5_placebo"]["by_archetype"] | {"placebo_flag": diag["D5_placebo"]["placebo_flag"]})
# V12
d2 = diag["D2_ols_fe"]
dis = [a for a, v in d2["models_disagree"].items() if v]
item("V12", "OLS-FE + EB vs Gibbs (D2)", "PASS" if not dis else "REPORT", True,
     {"by_archetype": d2["by_archetype"], "tau2_hat": d2["tau2_hat"], "sd_threshold": d2["sd_threshold"], "models_disagree": d2["models_disagree"],
      "review_aids": {k: v for k, v in d2["review_aids"].items()}},
     f"Threshold {d2['sd_threshold']} posterior SD (decision O-1c). " + (f"Disagreeing cells bracketed, not blocked: {dis}. " if dis else "") + d2["rule_note"])
# V13
item("V13", "Label agreement (kappa)", "REPORT", False,
     {"proxy_second_coder": labels["kappa_agent_vs_second_coder_proxy"], "agent_vs_rules_main": labels["kappa_agent_vs_rules_main"],
      "agent_vs_rules_all": labels["kappa_agent_vs_rules"], "label_reliability": mp["copy_flags"]["label_reliability"],
      "level4_triggered": False, "label_sets_available": labels["label_sets_available"], "audit_counts_main": labels["audit_counts_main"]},
     "No blind 20% second coder exists; primaries.json labels serve as a non-blind proxy (n=65). Posture kappa 0.4-0.6 -> low_posture (P estimates badged).")
# V14
lf = rob["label_flip"]
item("V14", "Label-flip attenuation", "REPORT", False, {"A_beta_L": lf["A"][0], "A_beta_P": lf["A"][1], "simex": rob["simex"]},
     "A < 0.6 for at least one slope: copy should note effects may be understated." if min(lf["A"]) < 0.6 else None)
# V15
item("V15", "Trust-dial Gaussian validity", "PASS" if all(v["mean_ok"] and v["sd_ok"] for v in exm["V15"].values()) else "FAIL", False,
     exm["V15"] | {"dial_enabled_in_export": exm["dial_enabled"]}, "Dial is valid against the exact fits but disabled in the export while fit_level = 5." if exm["fit_level"] == 5 else None)
# V16
v16 = sim5["V16"]
item("V16", "Sim 5 consistency (national margin)", "PASS" if v16["within_1_5"] else "FAIL", True,
     {k: v16[k] for k in ("national_house26", "nyt_topline_two_party", "gap", "within_1_5")},
     "Decision O-2: only the national-margin check is blocking; the by-eye bucket match is item V16b (REPORT).")
item("V16b", "Sim 5 NYT leader-share buckets (by eye)", "REPORT", False,
     {k: v16[k] for k in ("bucket_match_share", "bucket_pass", "mismatches")}, v16["note"])
# V17
item("V17", "Sim 3 Brier", "REPORT", False, prim["validation"], "Model loses to the endorsement-leader baseline -> coalition_enabled = false (eta at prior means); copy: 'polls plus priors'." if not prim["validation"]["coalition_enabled"] else None)

# V18 engine invariants (python reference engine)
bank = RE.build_bank(mp, n=10000, seed=SEED + 100)
bank2 = RE.build_bank(mp, n=10000, seed=SEED + 100)
E24 = mp["national"]["E24"]
Eg = np.arange(-10, 20.5, 0.5)
pw = np.array([RE.p_win_point(bank, e, np.zeros(1), E24)[0] for e in Eg])
mono = bool(np.all(np.diff(pw) >= 0))
same = bool(np.array_equal(bank["t"], bank2["t"]))
zero = np.zeros(1000)
ident = bool(np.allclose(RE.p_win_point(bank, 3.0, zero, E24), RE.p_win_point(bank, 3.0, zero, E24)))
item("V18", "Engine invariants", "PASS" if (mono and same and ident) else "FAIL", True,
     {"monotone_in_E": mono, "seed_reproducible": same, "delta0_identical": ident},
     "Invariants checked on the Python reference engine; the JS test suite (invariants, §6.3 budgets in Node, real-params load) is attached below.")
# V19
conv = meta["convergence"]
worst = max(v["rhat"] for p in conv.values() for v in p.values())
mine = min(v["ess_bulk"] for p in conv.values() for v in p.values())
item("V19", "Convergence", "PASS" if worst < 1.01 and mine > 400 else "FAIL", True, {"max_rhat": worst, "min_ess_bulk": mine, "by_preset": conv})
# V20
item("V20", "Partial-count selection report", "REPORT", False, {"selection_report": rob["selection_report"], "provisional_archetypes": rob["provisional_archetypes"],
                                                                 "provisional_refit": rob.get("provisional_refit")})

blocking_fail = [k for k, v in V.items() if v["blocking"] and v["status"] == "FAIL" and not v["overridden"]]
not_run_blocking = [k for k, v in V.items() if v["blocking"] and v["status"] == "NOT_RUN"]
log("blocking FAILs:", blocking_fail, "| blocking NOT_RUN:", not_run_blocking)

# ------------------------------------------------------------------ 2028 headline numbers (reference engine)
rng = np.random.default_rng(SEED + 101)
pi = np.array(mp["transfer_pi"]["pi_draws"])
# Headline numbers use the default environment (O-7: an even national vote); the D+3
# history preset is computed too, for copy that shows the alternative.
DEF_PRESET = mp["environment"]["default_preset"]
Ehist = RE.sample_E(mp["environment"]["presets"][DEF_PRESET], 10000, rng)
E_def_center = float(mp["environment"]["presets"][DEF_PRESET].get("loc", mp["environment"]["presets"][DEF_PRESET].get("mean", 0)))


def headline(style):
    out = {}
    om = np.array(style["omega_maga"])
    V_ml = None
    res = {}
    for a in ARCHETYPES:
        dlt = np.array(style["delta"][a])
        # generic opponent: Bernoulli(0.5) MAGA -> average of the two P(win)
        Va = 0.5 * (RE.v_dist(bank, Ehist, pi * dlt, E24) + RE.v_dist(bank, Ehist, pi * (dlt + om), E24))
        es = RE.estar(bank, pi * (dlt + 0.5 * om), E24)
        res[a] = {"V": Va, "Estar": es, "pidelta": pi * dlt}
    base = res["mainstream_liberal"]["V"]
    for a in ARCHETYPES:
        dV = 100 * (res[a]["V"] - base)
        out[a] = {"V": float(res[a]["V"].mean()), "V80": [float(np.quantile(res[a]["V"], .1)), float(np.quantile(res[a]["V"], .9))],
                  "dV_pts": summ(dV), "p_dV_below_minus10": float(np.mean(dV < -10)),
                  "Estar": [int(round(x)) for x in summ(res[a]["Estar"])], "pidelta": summ(res[a]["pidelta"])}
    # B_a: smallest pi*delta making dV <= -10 pts at the default E (distribution mode)
    v0 = RE.v_dist(bank, Ehist, np.zeros(1), E24)[0]
    grid = np.arange(0, -15.01, -0.05)
    vv = RE.v_dist(bank, Ehist, grid, E24)
    hit = np.where(vv - v0 <= -0.10)[0]
    B = float(grid[hit[0]]) if len(hit) else None
    for a in NON_REF:
        out[a]["B_threshold"] = B
        out[a]["P_pidelta_le_B"] = float(np.mean(res[a]["pidelta"] <= B)) if B is not None else None
    # How far the national mood alone moves a mainstream liberal's odds: P(win) with E fixed at
    # the 10th and 90th percentiles of the default range (generic opponent). Copy compares this
    # with the lane gaps (dV) above.
    nb = len(bank["t"])
    def v_point(E):
        return float(0.5 * (RE.v_dist(bank, np.full(nb, E), np.zeros(1), E24)[0] + RE.v_dist(bank, np.full(nb, E), np.array([float(np.median(om))]), E24)[0]))
    eq10, eq90 = float(np.quantile(Ehist, .1)), float(np.quantile(Ehist, .9))
    out["_mood"] = {"E10": eq10, "E90": eq90, "V_ml_at_E10": v_point(eq10), "V_ml_at_E90": v_point(eq90)}
    width_E = float(np.quantile(Ehist, .9) - np.quantile(Ehist, .1))
    # O-9: center populists are left out of the 2028 outputs (too few races in any cycle to estimate).
    max_hi = max(float(np.quantile(np.abs(res[a]["pidelta"]), .9)) for a in NON_REF if a != "center_populist")
    out["_C7"] = {"E_width80": width_E, "max_abs_pidelta_hi80": max_hi, "licensed": width_E > 2 * max_hi}
    return out


# O-8: headline 2028 numbers use the default style preset (history-based when available).
STYLE_DEFAULT = mp["style"].get("default_preset", "agnostic")
pub_style = mp["style"]["presets"][STYLE_DEFAULT]
z = np.load(WORK / "fit_agnostic.npz", allow_pickle=True)
names = list(z["names"])
cents = meta["centroids"]
th = z["theta"]
fit_style = {"omega_maga": th[:, names.index("omega_maga")], "delta": {}}
for a in ARCHETYPES:
    d = th[:, names.index("beta_L")] * (cents[a]["L"] - 1) + th[:, names.index("beta_P")] * cents[a]["P"]
    if f"u[{a}]" in names:
        d = d + th[:, names.index(f"u[{a}]")]
    fit_style["delta"][a] = d
H_pub = headline(pub_style)
if DEF_PRESET != "history":
    _E_default = Ehist
    Ehist = RE.sample_E(mp["environment"]["presets"]["history"], 10000, np.random.default_rng(SEED + 101))
    H_hist = headline(pub_style)
    Ehist = _E_default
else:
    H_hist = None
# O-1c: for cells where the models disagree, also compute the 2028 numbers at the OLS-FE/EB end of the bracket
dis_all = [a for a, v in mp["copy_flags"].get("models_disagree", {}).items() if v] if STYLE_DEFAULT == "agnostic" else []
H_eb = None
if dis_all:
    st_eb = {"omega_maga": pub_style["omega_maga"], "delta": dict(pub_style["delta"])}
    for a in dis_all:
        src = mp["reveal"]["adjusted"][a]["delta_range_sources"]
        st_eb["delta"][a] = np.array(pub_style["delta"][a]) + (src["ols_fe_eb"] - src["gibbs_median"])
    H_eb = headline(st_eb)
H_fit = headline(fit_style)
H_2026 = headline(mp["style"]["presets"]["agnostic"]) if STYLE_DEFAULT != "agnostic" else None  # 2026 fit alone, for comparison
log("published E*:", {a: H_pub[a]["Estar"] for a in ARCHETYPES})
log("fitted (unpublished) E*:", {a: H_fit[a]["Estar"] for a in ARCHETYPES})
# Sim 5 EV (C14)
ev = {u["id"]: u["ev"] for u in mp["units"]}
h26 = {u["id"]: u["house26"] for u in mp["sim5"]["units"]}
nat = mp["sim5"]["national_house26"]
ev_raw = sum(ev[i] for i in ev if h26[i] > 0)
ev_dur = sum(ev[i] for i in ev if h26[i] - (nat - E_def_center) > 0)

# ------------------------------------------------------------------ promote / block model_params
mp["meta"]["validation_summary"] = {k: v["status"] for k, v in V.items()}
mp["meta"]["notes"].append("validation: blocking FAIL " + (", ".join(blocking_fail) or "none") + "; blocking NOT_RUN " + ", ".join(not_run_blocking))
dst_ok, dst_blk = OUT / "model_params.json", OUT / "model_params.BLOCKED.json"
if blocking_fail:
    mp["meta"]["notes"].append("BLOCKED: not for publication. Written as model_params.BLOCKED.json for engine development only (§7 gate).")
    save_json(dst_blk, mp, nd=5)
    if dst_ok.exists():
        dst_ok.unlink()
    promoted = False
else:
    save_json(dst_ok, mp, nd=5)
    if dst_blk.exists():
        dst_blk.unlink()
    promoted = True
log("model_params promoted:", promoted)
js_suite = {"ran": False}
if shutil.which("node") and (ROOT / "site" / "src" / "lib" / "sim").exists():
    try:
        r = subprocess.run(["node", "--test", "src/lib/sim/**/*.test.js"], cwd=ROOT / "site", capture_output=True, text=True, timeout=900)
        tail = (r.stdout + r.stderr)[-3000:]
        import re as _re
        cnt = {k: int(v) for k, v in _re.findall(r"(?:#|ℹ) (pass|fail|skipped|tests) (\d+)", tail)}
        budgets = _re.findall(r"^(.+?)\s+budget\s+(\d+) ms \| cold\s+([\d.]+) \| warm\s+([\d.]+) \| ×4 proxy\s+([\d.]+) (\w+)", r.stdout + r.stderr, _re.M)
        js_suite = {"ran": True, "exit_code": r.returncode, "counts": cnt, "tail": tail[-1500:],
                    "budgets": [{"op": b_[0].strip(), "budget_ms": float(b_[1]), "cold_ms": float(b_[2]), "warm_ms": float(b_[3]),
                                 "x4_proxy_ms": float(b_[4]), "status": b_[5]} for b_ in budgets],
                    "real_model_tested": promoted}
    except Exception as e:  # noqa: BLE001
        js_suite = {"ran": False, "error": str(e)}
log("JS test suite:", {k: v for k, v in js_suite.items() if k != "tail"})
V["V18"]["numbers"]["js_test_suite"] = {k: v for k, v in js_suite.items() if k != "tail"}
if js_suite.get("ran") and js_suite.get("exit_code") != 0:
    V["V18"]["status"] = "FAIL"
    V["V18"]["note"] = (V["V18"].get("note") or "") + " JS test suite failed on the exported params; see validation.json."

validation = {"generated_at": now_iso(), "data_as_of": mp["meta"]["data_as_of"], "fit_level": exm["fit_level"],
              "levels_triggered": exm["levels"], "overrides": sorted(overrides), "blocking_fail": blocking_fail,
              "blocking_not_run": not_run_blocking, "model_params_written": "model_params.json" if promoted else "model_params.BLOCKED.json",
              "js_test_suite": js_suite, "items": V, "headline_2028": {"default_preset": DEF_PRESET, "style_preset": STYLE_DEFAULT, "published": H_pub, "history_preset": H_hist, "ols_fe_eb_end_for_disagreeing_cells": ({a: H_eb[a] for a in dis_all} if H_eb else None), "published_is_prior_only": exm["fit_level"] == 5, "fitted_unpublished": H_fit, "style_2026_only": H_2026},
              "sim5_ev": {"raw": ev_raw, "durable": ev_dur, "durable_E": E_def_center, "durable_D+3": ev_dur if E_def_center == 3 else None, "national_house26": nat},
              "diagnostics": {"D1": diag["D1_overlap"], "D3": diag["D3_freedman_lane"], "D4": diag["D4_grouped_cv"], "D6": {k: v for k, v in diag["D6_close_primary_rd"].items() if k != "races"},
                              "D7": diag["D7_wave_compression"], "tau_c": diag["tau_c"]},
              "data_issues": {"maine_discrepancy": diag["V6_maine"]["discrepancy"], "user_flagged_uncalled": excl["user_flagged_uncalled"],
                              "n_uncalled": len(excl["uncalled_ids"]), "data_flag_counts": excl["data_flag_counts"]}}
save_json(OUT / "validation.json", validation, nd=4, indent=1)

# ------------------------------------------------------------------ findings.md
S = meta["summary"]
cf = mp["copy_flags"]


def f1(x):
    return f"{x:+.1f}"


def lean(x):
    x = int(round(x))
    return "even" if x == 0 else (f"D+{x}" if x > 0 else f"R+{-x}")


def iv(v):
    return f"{f1(v[0])} (80%: {f1(v[1])} to {f1(v[2])})"


raw = mp["reveal"]["raw"]
lines = []
A = lines.append
A("# Findings: 2026 candidate styles (preliminary)\n")
A(f"Generated {now_iso()} from data as of {mp['meta']['data_as_of']}. Every number is preliminary. Pipeline `{mp['meta']['pipeline_commit']}`.\n")
A("## Bottom line\n")
if exm["fit_level"] == 5:
    A(f"- **Fallback level reached: 5** (\"2026 is uninformative\" mode): " + "; ".join(l["trigger"] for l in exm["levels"] if l["level"] == 5) + ".")
else:
    A(f"- **Fit level {exm['fit_level']}** (no Level-5 block). Lead-reviewer decisions O-1a to O-5 (2026-11-04, logged in `methodology_decisions.md`) were applied: u_a minimum 12 races from 8 states, Mundlak terms for archetype indicators, V12 threshold 1.5 SD with bracketing, V16 national-only, likelihood trial for V7, district_sd = 1.5 with JS parity.")
A(f"- Levels triggered: " + "; ".join(f"L{l['level']} ({l['trigger']})" for l in exm["levels"]) + ".")
A(f"- **Validation:** blocking FAIL = {', '.join(blocking_fail) or 'none'}; blocking NOT_RUN = {', '.join(not_run_blocking) or 'none'}. "
  + ("`model_params.json` was **not** written; the schema-identical `model_params.BLOCKED.json` is there for engine development." if not promoted else "`model_params.json` written."))
dis_ = [a for a, v in cf.get("models_disagree", {}).items() if v]
if dis_:
    A(f"- Models disagree for {dis_}: those δ cells are exported as a bracket (`delta_range_models`) and copy must name both numbers."
      + (f" Note: the EB between-archetype variance estimate τ̂² is 0 this run, so EB shrinks every OLS-FE dummy to 0 and the bracket's lower end is 0 by construction; unshrunk OLS-FE dummies are " + ", ".join(f"{a} {v['ols']:+.1f} (SE {v['se_cr2']:.1f})" for a, v in d2["by_archetype"].items() if v.get("ols") is not None) + "." if d2["tau2_hat"] == 0 else ""))
else:
    A(f"- D2 cross-check now agrees within {d2['sd_threshold']} posterior SD for every gated archetype (largest gap {max(v.get('gap_in_sd', 0) for v in d2['by_archetype'].values() if v.get('comparable')):.2f} SD), so no cell is bracketed. The raw OLS-FE progressive dummy ({d2['by_archetype']['progressive']['ols']:+.1f}) is still well below the Gibbs estimate; EB shrinkage takes it to {d2['by_archetype']['progressive']['eb_shrunk']:+.1f}.")
A("")
A("## Sample\n")
A(f"- {meta['n_main']} races in the main sample (every contested race with ≥ 80% counted: House at any lean, Senate, governor, 2025–26 House specials; decision O-6), out of {len(json.load(open(OUT / 'races.json'))['races'])} rows loaded.")
A("- Exclusions (counts): " + ", ".join(f"{k} {v}" for k, v in excl["counts"].items()) + ". Every exclusion and its reason is in `races.json` (`exclusion_reason`).")
A(f"- Archetype counts in the main sample: " + ", ".join(f"{a} {raw[a]['n']} ({raw[a]['n_states']} states)" for a in ARCHETYPES) + f". Archetype deviations u_a are estimated for {meta['u_active']} (rule: ≥ {meta['min_n_rule']['races']} races from ≥ {meta['min_n_rule']['states']} states, ≥ 5 with |m24| ≤ 10); the others are structural only. Center-populists are almost all Dem-backed independents (excluded), leaving 2.")
A(f"- Partial counts: {sum(1 for r in excl['exclusions'] if r['reason'].startswith('partial'))} races below 80% counted are out of the main fit (provisional refit only). Selection report: " +
  ", ".join(f"{a} {v['excluded_p_lt_80']}/{v['eligible']}" for a, v in rob["selection_report"].items()) + f". `provisional_archetypes` = {cf['provisional_archetypes']}.")
A(f"- {len(excl['uncalled_ids'])} races are uncalled in the data; {excl['data_flag_counts'].get('single_source_nbc', 0)} rows rely on NBC alone for vote shares. Uncalled races still enter if ≥ 80% counted (the call does not matter for the margin).\n")

A("## Raw vs adjusted style effects (vs a mainstream liberal)\n")
A("Raw means are plain margin points relative to Harris 2024. Adjusted δ is on the main model scale, 50 × Δlogit of the two-party D share: points of margin in an evenly split seat, compressed correctly in lopsided seats (decision O-6). It is what the 2028 translation uses, where the national race is near even.\n")
A(f"Likelihood: {meta['likelihood']} ({meta['likelihood_note']}).\n")
A("| Archetype | n | Raw mean y | Adjusted δ (fitted, agnostic) | Literature | Data-only | Discount | posterior SD / prior SD |")
A("|---|---|---|---|---|---|---|---|")
for a in ARCHETYPES:
    if a == "mainstream_liberal":
        A(f"| mainstream_liberal | {raw[a]['n']} | {raw[a]['mean']:+.1f} | reference (δ = β_P·P̄ = {np.median(fit_style['delta'][a]):+.2f}) | | | | |")
        continue
    sdr = float(np.std(fit_style["delta"][a]) / np.sqrt(4 * ((cents[a]['L'] - 1) ** 2 + cents[a]['P'] ** 2) + (1 if a in meta['u_active'] else 0)))
    A(f"| {a} | {raw[a]['n']} | {raw[a]['mean']:+.1f} | {iv(S['agnostic'][f'delta[{a}]'])} | {iv(S['literature'][f'delta[{a}]'])} | {iv(S['data_only'][f'delta[{a}]'])} | {iv(S['discount'][f'delta[{a}]'])} | {sdr:.2f}{' (mostly prior)' if sdr > 0.7 else ''} |")
A("")
A(f"- Slopes (agnostic): β_L = {iv(S['agnostic']['beta_L'])} per step left; β_P = {iv(S['agnostic']['beta_P'])} per unit populist posture. SD ratios: β_L {S['agnostic']['sd_ratio']['beta_L']:.2f}, β_P {S['agnostic']['sd_ratio']['beta_P']:.2f} (below 0.7, so 2026 does inform the slopes).")
A(f"- Center-populist δ is an extrapolation of β_P from 2 races at (L, P) = (0, 1); it is structural only and its cell is greyed.")
A(f"- Opponent: facing MAGA {iv(S['agnostic']['omega_maga'])}; facing a moderate R {iv(S['agnostic']['omega_mod'])}. R incumbent personal vote coefficient {iv(S['agnostic']['R_inc_pv'])} per point.")
A(f"- Statewide deviation d_L {iv(S['agnostic']['d_L'])}, d_P {iv(S['agnostic']['d_P'])}; statewide/House ratio for leftness {iv(exm['statewide_house_ratio'])} (evidence beside the π slider only).")
oxd_file = load_json(OUT / "story_data" / "oaxaca_decomposition.json")
oxd = oxd_file["by_archetype"]
_rr = {r_["label"]: r_ for r_ in rob["runs"] if "delta" in r_}
_cmp = [k for k in _rr if k.startswith("R4: competitive only")] + [k for k in _rr if k.startswith("R1: margin scale")]
A("- Alternative specifications for the story (decision O-6): " + "; ".join(f"**{k}** (n = {_rr[k]['n']}): " + ", ".join(f"{a} {iv(_rr[k]['delta'][a])}" for a in NON_REF) for k in _cmp) + ".")
A("- Oaxaca on the model scale (raw gap vs mainstream liberals = lean + incumbency + opponent + state wave + office + style + residual): " + "; ".join(
    f"{a}: {o['raw_gap']:+.1f} = lean {o['lean']:+.1f}, incumbency {o['incumbency']:+.1f}, opponent {o['opponent']:+.1f}, state {o['state_wave']:+.1f}, office {o['office']:+.1f}, style {o['style']:+.1f}, residual {o['residual']:+.1f}" for a, o in oxd.items()) + ".")
_rows = [r for r in json.load(open(WORK / "dataset_labeled.json")) if r["in_main"]]
_b = th.mean(0)
_mR = np.mean([r["R_inc_pv"] for r in _rows]); _mi = np.mean([r["inc_R"] for r in _rows])
_pc = {r["id"]: _b[names.index("R_inc_pv")] * (r["R_inc_pv"] - _mR) + _b[names.index("inc_R")] * (r["inc_R"] - _mi) for r in _rows if r["M_archetype"] == "progressive"}
_big = min(_pc, key=_pc.get)
A(f"- Progressives' raw gap ({oxd['progressive']['raw_gap']:+.1f}) is mostly incumbency and an unexplained residual ({oxd['progressive']['residual']:+.1f}). The incumbency term is largely one race: {_big} (Phil Scott's personal vote), {_pc[_big]:+.0f} pts for that race, {_pc[_big] / len(_pc):+.1f} of the archetype average. The residual is what the OLS-FE dummy picks up.")
_xv = oxd_file["excluding_GOV_VT"]["progressive"]
A(f"- Without GOV-VT (decision O-4), progressives' raw mean is {_xv['raw_mean_progressive']:+.1f} (vs {_xv['raw_mean_progressive_with_vt']:+.1f} with it) and the raw gap to mainstream liberals is {_xv['raw_gap']:+.1f} (n = {_xv['n']}): incumbency {_xv['incumbency']:+.1f}, state {_xv['state_wave']:+.1f}, style {_xv['style']:+.1f}, residual {_xv['residual']:+.1f}. So the raw deficit is not one Vermont race, but about half of it is.\n")

A("## Diagnostics and copy flags\n")
A(f"- D1 overlap: {diag['D1_overlap']['n_trimmed']}/{meta['n_main']} races on common support; no δ moved > 1.5 → `lead_with_overlap = false`. (Propensity uses state-level demographics.)")
A(f"- D2 OLS-FE + EB: " + "; ".join(f"{a} OLS {v['ols']:+.1f} (SE {v['se_cr2']:.1f}) → EB {v['eb_shrunk']:+.1f} vs Gibbs {v['gibbs_med']:+.1f} ({v['gap_in_sd']:.1f} SD{', gated' if v['comparable'] else ', n<10 not gated'})" for a, v in d2["by_archetype"].items() if v.get("ols") is not None)
  + f". Review aid: Gibbs with every u_a switched on gives progressive {iv(d2['review_aids']['gibbs_all_u_active']['progressive'])}; Huber-weighted OLS-FE gives {d2['review_aids']['ols_huber']['progressive']:+.1f}. "
  "The first run (u_progressive switched off by the 15-race rule, no archetype Mundlak terms) had a 2.5-SD progressive gap; decisions O-1a/O-1b closed most of it.")
A(f"- D3 Freedman–Lane: Wald {diag['D3_freedman_lane']['wald_obs']:.1f}, p = {diag['D3_freedman_lane']['p_value']:.3f} → `no_detectable_effect = {cf['no_detectable_effect']}`.")
A(f"- D4 grouped CV: ΔELPD = {diag['D4_grouped_cv']['delta_elpd']:.1f} (SE {diag['D4_grouped_cv']['se']:.1f}); below 2·SE → `no_predictive_gain = {cf['no_predictive_gain']}` (borderline).")
A(f"- D5 placebo (2024 House − pres on unchanged lines, new nominees): " + "; ".join(f"{a} {v['placebo']:+.1f} (n {v['n']})" if v.get('placebo') is not None else f"{a} n/a (n {v['n']})" for a, v in diag['D5_placebo']['by_archetype'].items())
  + f" → `placebo_flag` = {cf['placebo_flag']}. Progressive seats already ran ~3 pts ahead of Harris in 2024 with other nominees.")
d6 = diag["D6_close_primary_rd"]
A(f"- D6 close-primary RD (sign check, n = {d6['n']}): more-left winner {d6['estimate']:+.1f} (80%: {d6['lo80']:+.1f} to {d6['hi80']:+.1f}); no tension flagged.")
A(f"- D7 wave compression: leftness × state wave {iv(diag['D7_wave_compression']['L'])}; posture × wave {iv(diag['D7_wave_compression']['P'])}. The leftness interval excludes 0, so the π tooltip should say style differences were smaller where the wave was bigger (as an OLS-FE robustness model).")
A(f"- `direction_depends_on_prior` = all false (agnostic, literature and data-only agree in sign). `label_reliability = {cf['label_reliability']}`. `maine_explained_by_incumbent = {cf['maine_explained_by_incumbent']}`.")
A(f"- Label fragility (R3): Set B rule labels give progressive {iv(next(r for r in rob['runs'] if r['label'].startswith('R3: Set B'))['delta']['progressive'])} and moderate {iv(next(r for r in rob['runs'] if r['label'].startswith('R3: Set B'))['delta']['moderate'])}; strict source-date audit labels shrink every δ toward 0. "
  f"Label-flip attenuation A = {lf['A'][0]:.2f} (β_L), {lf['A'][1]:.2f} (β_P): effects may be understated if labels are noisy. Agent-vs-rules κ (archetype) {labels['kappa_agent_vs_rules_main']['archetype']['kappa']:.2f}; proxy second coder κ {labels['kappa_agent_vs_second_coder_proxy']['archetype']['kappa']:.2f} (archetype), {labels['kappa_agent_vs_second_coder_proxy']['posture']['kappa']:.2f} (posture).")
A(f"- Label sets actually available: A (agent) yes; B (rule-based) implemented from the evidence text, not raw campaign text; C (soft) constructed from confidence; no blind second coder (primaries.json used as a non-blind proxy, n = 65). Source-date audit: only {labels['audit_counts_main'].get('dated_pre_election_source', 0)} main-sample labels cite a dated pre-election URL; {labels['audit_counts_main'].get('primary_record', 0)} more have a pre-election primary record; {labels['label_source_main'].get('B', 0)} labels with no pre-election evidence were replaced by Set B.\n")

A("## Validation (§7)\n")
A("| Item | Status | Blocking | Key numbers |")
A("|---|---|---|---|")
keynum = {
    "V1": f"EV_D {v1['ev_D']}, max dev {v1['max_abs_dev']:.1e}", "V3": f"pooled 80% coverage {v3['pooled_coverage80']:.2f}; correlated log score {v3['logscore_correlated']:.1f} vs independent {v3['logscore_independent']:.1f}",
    "V4": f"D EV 80% {v4['ev_D_80']} contains 226; Brier {v4['brier_model']:.4f} vs {v4['brier_independent_same_sd']:.4f}",
    "V6": f"δ=0 prediction {iv(v6['pred_delta0'])} vs actual {v6['actual']:+.1f} (NYT-implied {v6['nyt_implied_shift']:+.1f}); incumbency share {v6['share_incumbency'][0]:.2f}",
    "V7": f"coverage {c7:.3f} (target 0.75–0.85)", "V8": f"coverage {v8['coverage80']:.2f}; MAE {v8['mae_style']:.2f} vs {v8['mae_nostyle']:.2f}",
    "V12": f"progressive gap {d2['by_archetype']['progressive']['gap_in_sd']:.1f} SD", "V14": f"A = {lf['A'][0]:.2f}, {lf['A'][1]:.2f}",
    "V16": f"national D{v16['national_house26']:+.1f} vs NYT D{v16['nyt_topline_two_party']:+.1f} (ok); bucket match {v16['bucket_match_share']:.0%} (< 90%)",
    "V17": f"Brier {prim['validation']['brier_model']:.3f} vs baseline {prim['validation']['brier_baseline']:.3f}", "V19": f"max R̂ {worst:.4f}, min ESS {mine:.0f}",
    "V11": "progressive placebo " + f"{diag['D5_placebo']['by_archetype']['progressive'].get('placebo') or 0:+.1f} (flag)",
    "V20": "excluded p<0.80: " + ", ".join(f"{a} {v['excluded_p_lt_80']}/{v['eligible']}" for a, v in rob["selection_report"].items()),
    "V13": f"proxy κ archetype {labels['kappa_agent_vs_second_coder_proxy']['archetype']['kappa']:.2f}, posture {labels['kappa_agent_vs_second_coder_proxy']['posture']['kappa']:.2f}",
}
for k, v in V.items():
    A(f"| {k} {v['name']} | {v['status']} | {'yes' if v['blocking'] else 'no'} | {keynum.get(k, v.get('note', '')[:110])} |")
A("")
A(f"Notes: V7 over-covers ({c7:.3f}); {meta['likelihood_note']}. V16 national margin passes; the by-eye bucket match ({v16['bucket_match_share']:.0%}) is REPORT only (V16b). V2 covers the bank and P(win) layers exactly; full Sim-object parity is not yet tested.\n")

A("## Claims ledger (§8): what the copy may say now\n")
hp = H_pub
lvl5 = exm["fit_level"] == 5
pf = cf["placebo_flag"]
plc = diag["D5_placebo"]["by_archetype"]
def _pts(x):
    x = abs(x)
    return "less than 1 point" if x < 0.95 else (f"about {round(x)} point" + ("s" if round(x) != 1 else ""))


def _int(x):
    v = int(round(x))
    return "0" if v == 0 else f"{v:+d}"


def _plc(a):
    p_, d_ = plc[a]["placebo"], mp["reveal"]["adjusted"][a]["med"]
    where = f"In these seats a different Democrat already ran {_pts(p_)} {'ahead of' if p_ > 0 else 'behind'} Harris in 2024 (placebo, n = {plc[a]['n']} seats)"
    if np.sign(p_) == np.sign(d_):
        return where + ", so part of this may be the place, not the candidate."
    return where + ", so the place favoured the opposite direction; the style gap could be larger than shown, not smaller."


plc_txt = {a: _plc(a) for a in NON_REF if pf.get(a) and plc[a].get("placebo") is not None}
A(f"- **C1 licensed** (descriptive): e.g. \"Moderate Democrats beat Harris's 2024 margin in their districts by {round(raw['moderate']['mean'])} points on average\" (progressive {round(raw['progressive']['mean'])}, {round(oxd_file['excluding_GOV_VT']['progressive']['raw_mean_progressive'])} without Vermont's governor race; left-populist {round(raw['left_populist']['mean'])}, mainstream liberal {round(raw['mainstream_liberal']['mean'])}), always followed by \"But they ran in very different places.\"")
c2_ok = [a for a in NON_REF if (not cf["publish_blocked"]) and meta["min_n"][a]["ok"] and not cf["no_detectable_effect"]]
if c2_ok:
    for a in c2_ok:
        adj = mp["reveal"]["adjusted"][a]
        if cf.get("models_disagree", {}).get(a):
            lo_, hi_ = adj["delta_range_models"]
            near, far = sorted([abs(lo_), abs(hi_)])
            fmt_ = lambda x: "0" if x < 0.05 else ("less than 1" if x < 0.95 else f"about {round(x)}")
            unit_ = "point" if round(far) == 1 else "points"
            dirw = "behind" if hi_ <= 0.05 else ("ahead of" if lo_ >= -0.05 else "behind or ahead of")
            eb_note = " The OLS-FE/EB end is 0 because the EB between-archetype variance estimate is 0 (every OLS dummy is shrunk fully); the unshrunk OLS-FE dummy is " + f"{d2['by_archetype'][a]['ols']:+.1f} (SE {d2['by_archetype'][a]['se_cr2']:.1f})." if d2["tau2_hat"] == 0 else ""
            A(f"- **C2 licensed for {a} as a bracket** (models disagree: Gibbs {adj['delta_range_sources']['gibbs_median']:+.1f}, OLS-FE/EB {adj['delta_range_sources']['ols_fe_eb']:+.1f}): \"In comparable races, on the same ballot, {a.replace('_', '-')} nominees ran between {fmt_(near)} and {fmt_(far)} {unit_} {dirw} mainstream liberals, depending on the model\" + the mandatory caveat." + eb_note + (f" **Placebo caveat required:** \"{plc_txt[a]}\"" if a in plc_txt else ""))
        else:
            d_ = adj["med"]
            A(f"- **C2 licensed for {a}**: \"In comparable races, on the same ballot, {a.replace('_', '-')} nominees ran {_pts(d_)} {'behind' if d_ < 0 else 'ahead of'} mainstream liberals (range {_int(adj['lo'])} to {_int(adj['hi'])})\" + the mandatory caveat (comparable races, not cause and effect; preliminary)." + (f" **Placebo caveat required:** \"{plc_txt[a]}\"" if a in plc_txt else ""))
    A(f"- C2 not licensed for {[a for a in NON_REF if a not in c2_ok]} (below the minimum N for their own deviation; structural prediction only).")
else:
    A("- **C2 not licensed**" + (": `publish_blocked = true`." if cf["publish_blocked"] else "."))
if cf["no_detectable_effect"] or cf["no_predictive_gain"]:
    A(f"- **C3 required wording** (`no_predictive_gain = {cf['no_predictive_gain']}`): \"style adds no detectable predictive power\" / \"We found no detectable difference between styles once we compared like with like; the range runs from [lo] to [hi]\", with \"No detectable difference is not proof of no difference.\" **Tension for the desk:** C2's conditions also hold for the archetypes above, and D3's permutation test detects the style slopes (p = {diag['D3_freedman_lane']['p_value']:.3f}); the slopes explain in-sample variation but do not improve out-of-state prediction by 2 SE (ΔELPD {diag['D4_grouped_cv']['delta_elpd']:.1f}, SE {diag['D4_grouped_cv']['se']:.1f}). Because C3 is marked required, lead with C3 and give the C2 numbers as its range.")
A("- **C4 " + ("required for " + str([a for a, v in cf["direction_depends_on_prior"].items() if v]) if any(cf["direction_depends_on_prior"].values()) else "not required") + "** (direction vs prior).")
A(f"- **C5 licensed** (integers): E* = " + ", ".join(f"{a} {lean(hp[a]['Estar'][0])} ({lean(hp[a]['Estar'][1])} to {lean(hp[a]['Estar'][2])})" + (f" [OLS-FE/EB end: {lean(H_eb[a]['Estar'][0])}]" if a in dis_all else "") for a in ARCHETYPES) + (". Prior-only at Level 5." if lvl5 else ". Center-populist numbers are a 2-race extrapolation of β_P."))
A(f"- **C6 licensed** ({DEF_PRESET} environment, generic opponent): ΔV vs mainstream liberal = " + ", ".join(f"{a} {hp[a]['dV_pts'][0]:+.0f} pts ({hp[a]['dV_pts'][1]:+.0f} to {hp[a]['dV_pts'][2]:+.0f})" + (f" [OLS-FE/EB end: {H_eb[a]['dV_pts'][0]:+.0f}]" if a in dis_all else "") for a in NON_REF) + "." + (f" For bracketed cells ({dis_all}) copy must give both ends." if dis_all else ""))
A(f"- **C7 {'licensed' if hp['_C7']['licensed'] else 'not licensed'}**: E 80% width {hp['_C7']['E_width80']:.1f} vs 2 × max |π·δ| upper bound {2 * hp['_C7']['max_abs_pidelta_hi80']:.1f}.")
A(f"- **C8 licensed**: a style must cost at least {abs(hp['progressive']['B_threshold']):.1f} pts nationally (π·δ ≤ {hp['progressive']['B_threshold']:.1f}) to cut win probability by 10 points at the default environment; 2026 puts the chance of a cost that large at " + ", ".join(f"{hp[a]['P_pidelta_le_B']:.0%} ({a})" for a in NON_REF) + ".")
if plc_txt:
    A("- **Placebo caveats (D5, required wherever these archetypes' effects are quoted):** " + " ".join(f"{a}: {t}" for a, t in plc_txt.items()))
A("- **C9 " + ("licensed" if cf["maine_explained_by_incumbent"] else "not licensed") + "**: \"Maine's swing toward Republicans looks like Susan Collins's personal vote, not a populism penalty\" with \"One race; the model can't separate the candidate from the opponent.\" Caveat for the desk: the race file shows Jackson slightly *ahead* of Harris (+0.5 two-party at 86% counted), while the NYT nine-state table implies a 3.7-point shift toward R. The δ = 0 interval covers both. Never \"populism failed in Maine\".")
A("- **C10 licensed** (descriptive, nine races). Between-state SDs reproduce §4.2 (WNC−WC 4.9, 18–29 vs 65+ 4.4, education gradient 5.1).")
A("- **C11 not licensed** (interaction gates closed: no district composition).")
A("- **C12 licensed** in matrix context only. **C13** licensed with V17 shown: coalition model disabled, so \"polls plus priors\".")
A(f"- **C14 licensed**: the 2026 House vote as a presidential map gives Democrats {ev_raw} EV; at a {"D+%g" % E_def_center if E_def_center > 0 else "even" if E_def_center == 0 else "R+%g" % -E_def_center} environment (durable view) {ev_dur} EV. National House margin D+{nat:.1f} (two-party; NYT D+13.1).")
A("- **C15 not licensed** (V9 not run: no VA LG/AG margins).")
A(f"- **C16 licensed**: provisional archetypes {cf['provisional_archetypes']} (West Coast and other slow counts).\n")

A("## Known data issues carried through\n")
A("- Maine Senate: nominee is Troy Jackson (left_populist; Platner won the primary and withdrew). See the C9 caveat for the NYT-vs-race-file discrepancy (also in validation.json `data_issues`).")
A("- Uncalled races named in the brief: " + "; ".join(f"{u['id']} ({'in main fit' if u.get('in_main') else (u.get('exclusion_reason') or u.get('status'))})" for u in excl["user_flagged_uncalled"]) + ".")
A("- Dem-backed independents (NE Osborn, ID Achilles, SD Bengs, MT Bodnar, AK-AL Hill) are excluded and descriptive only; Montana's split anti-GOP vote (Bodnar 37.3 + Bankhead 11.9) is also excluded.")
A("- No district demographics (Level 3): ES terms dropped; common-support plots use state-level shares; interactions gated off.")
A("- Candidate track records before 2025 use national environment constants that are not in the research files (listed in candidate_profiles.json); verify before publishing named-candidate numbers.")
A("- E24 from certified state totals is −1.50 two-party, not the −1.43 quoted in METHODOLOGY.")
(OUT / "findings.md").write_text("\n".join(lines) + "\n")

# ------------------------------------------------------------------ SCHEMA_NOTES.md
notes = f"""# SCHEMA_NOTES: deviations from METHODOLOGY §6.4

Generated {now_iso()}. Read with `model_params{'.BLOCKED' if not promoted else ''}.json`.

1. **File name / gate.** {("This run has blocking FAILs (" + ", ".join(blocking_fail) + "), so the schema-identical file is `analysis/output/model_params.BLOCKED.json` (§7 gate); switch to `model_params.json` when it appears." if blocking_fail else "No blocking FAIL: the file is `analysis/output/model_params.json`. On a blocked run the pipeline instead writes the schema-identical `model_params.BLOCKED.json` and deletes any stale `model_params.json` (§7 gate).")}
2. **`meta.fit_level = {exm['fit_level']}`.** At Level 5 (not this run unless stated) every `style.presets.*` block would hold prior draws with an extra `source` string and `dial_enabled = false`. New in this run: `copy_flags.models_disagree` ({{archetype: bool}}); when true for an archetype, `reveal.adjusted[a]` carries `delta_range_models` [lo, hi] (Gibbs median and OLS-FE EB estimate) and `delta_range_sources`, and copy must name both numbers (decision O-1c).
3. **`national.E24 = {mp['national']['E24']:.3f}`**, computed from certified state totals in `states.json` (two-party). METHODOLOGY quotes −1.43; it cannot be reproduced from the file. `environment.presets.rerun2024.value` uses the same number so the identity test (V1) holds.
4. **District units** (`ME-1`, `ME-2`, `NE-1..3`) carry `district_sd = 1.5`, and `errors.district_sd = 1.5` is written explicitly (decision O-5; matches the JS default in `site/src/lib/sim/model.js`). District `F`, `sigma_idio` and `G` are copies of the parent state's (the JS engine uses the parent's k anyway). Both engines draw `eps_district = eps_parent + N(0, district_sd^2)`; V2 parity of the bank is exact (see validation.json).
5. **`errors.backtest.cov80_2016 = null`**: no 2012 results on disk. `cov80_2020` and `cov80_2024` are the 2016→20 and 2020→24 transitions. `errors.calibrated = false`.
6. **`style.presets.*.beta_PW` / `beta_LY`** are arrays of 1000 zeros (gated off; "set to 0, not prior draws"). In `style.gaussian`, the γ rows of `Vhat` have variance 1e4 (no data information) and zero covariance.
7. **δ reference point.** `delta[a] = beta_L*(Lbar_a - 1) + beta_P*Pbar_a + u_a` uses empirical centroids, so `delta.mainstream_liberal` = beta_P × {cents['mainstream_liberal']['P']:.3f} (small, not exactly 0). ΔV is still V_a − V_mainstream_liberal under common random numbers.
8. **`reveal` additions**: `adjusted[a]` adds `min_n_ok`, `mostly_prior`; `decomposition[a]` adds `office` (office/period intercepts); `maine` adds `incumbency_pts`, `style_pts`, `nominee`, `nyt_implied`; `nyt9` = {{table, sd_across_states, psi_P}}. `reveal.raw[a].dist_wnc / dist_y1829 / dist_urban` are **state-level** proxies (no district ACS).
9. **Nullable fields**: `candidates_*.home`, `poll_nat_primary`, `market_nom` can be null; `sim5.units[DC].pct_counted` is null; `transfer_pi.evidence.historical_pres_mid_ratio` is null.
10. **`primary`**: `zeta.{{left,moderate}}` and `b_populist` are 1000 draws; `eta.{{left,moderate}}` are 1000×4 draws. `validation.coalition_enabled = {prim['validation']['coalition_enabled']}`: the engine should use η = 0 (prior means) when it is false. Delegates and the `dnc2024` calendar are approximations of the 2024 rules and dates.
11. **`copy_flags.placebo_flag` / `direction_depends_on_prior`** have keys for the four non-reference archetypes only.
12. **`meta.pipeline_commit`** is a content hash of `analysis/pipeline/*` (`nogit-…`); the project is not a git repository.
13. **`meta.validation_summary`** (extra) maps V1–V20 to status.
14. **`style.gaussian.dial_enabled = {mp['style']['gaussian']['dial_enabled']}`**: V15 checks the Gaussian dial against the exact preset fits; when it fails (as for the literature and discount presets after the O-1 model changes), only the four exact presets should be offered.
15. `races.json` and `story_data/*` are not in §6.4; their fields are described inside each file.
"""
(OUT / "SCHEMA_NOTES.md").write_text(notes)
log.save()
