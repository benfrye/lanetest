"""Step 03: main Gibbs fits for the four trust-dial presets (METHODOLOGY §3.1–3.4, §3.8, §3.9).

Writes work/fit_<preset>.npz (1,000 thinned joint draws + full-chain style draws) and
work/fit_meta.json (design, gates, convergence, fit-level evaluation so far).
"""
import time

import numpy as np

from common import ARCHETYPES, SEED, WORK, Log, ess, load_json, rhat, save_json, summ
import gibbs
from gibbs import PRESETS, Design, centroids, deltas, min_n_status, ppc_coverage, run_gibbs

log = Log("03_fit")
rows = load_json(WORK / "dataset_labeled.json")
labels = load_json(WORK / "labels_report.json")
main = [r for r in rows if r["in_main"]]
log(f"main sample n={len(main)}")

cents = centroids(main, "M")
log("empirical centroids (L, P, n):", cents)
mn = min_n_status(main, "M")
u_active = [a for a, s in mn.items() if s["ok"] and a != "mainstream_liberal"]
log("min-N status:", mn)
log("u_a active:", u_active)
n_statewide = sum(1 for r in main if r["statewide"])
statewide_dev = n_statewide >= 25
log(f"statewide contested races in main sample: {n_statewide} -> d active: {statewide_dev}")

# ------------------------------------------------------------------ fallback ladder (§3.9)
levels = []
if any(not s["ok"] for a, s in mn.items() if a != "mainstream_liberal"):
    levels.append({"level": 1, "trigger": "archetypes below minimum N: " + ", ".join(a for a, s in mn.items() if not s["ok"] and a != "mainstream_liberal"),
                   "action": "u_a = 0 for those archetypes (structural prediction only); cells greyed"})
interaction_gate = {
    "beta_PW": {"gate_passed": False, "badge": "prior",
                "reason": "district CVAP composition (research/districts_acs.json) is not on disk; the gate requires district-level W~ spanning >= 20 pts within >= 8 states. State-level proxies would make it a between-state term. Fixed at 0 (not prior draws) in all translations."},
    "beta_LY": {"gate_passed": False, "badge": "prior",
                "reason": "same as beta_PW (no district 18-29 shares on current lines)."},
}
levels.append({"level": 2, "trigger": "interactions below minimum N (no district composition)", "action": "gamma = 0; tilt disabled"})
levels.append({"level": 3, "trigger": "district demographics missing for 100% of rows (> 25%)",
               "action": "ES_re and ES_age dropped; rely on the m24 spline and the state effects/Mundlak terms. Banner: the wave's demographic shape is only partly controlled. (State-level ES would be collinear with alpha_s.)"})
kappa_arch = labels["kappa_agent_vs_second_coder_proxy"]["archetype"]["kappa"]
kappa_rules_main = labels["kappa_agent_vs_rules_main"]["archetype"]["kappa"]
level4 = len(main) < 80 or (kappa_arch is not None and kappa_arch < 0.4)
log(f"Level-4 check: n_main={len(main)} (need >= 80), archetype kappa proxy={kappa_arch:.3f}, agent-vs-rules={kappa_rules_main:.3f} -> triggered={level4}")
if level4:
    levels.append({"level": 4, "trigger": "few races or archetype kappa < 0.4", "action": "single leftness factor"})
fit_level = max(l["level"] for l in levels)

# ------------------------------------------------------------------ likelihood choice (override O-3, lead reviewer 2026-11-04)
# Try Normal, then t with nu = 10; use the first whose in-sample 80% PPC coverage is in [0.75, 0.85].
# If none qualifies, keep the METHODOLOGY t5 and V7 becomes non-blocking ("intervals conservative").
lik_trials = {}
chosen_nu = None
for nu in (np.inf, 10.0, 5.0):
    Dq = Design(main, "M", statewide_dev=statewide_dev, u_active=u_active, preset="agnostic", cents=cents)
    fq = run_gibbs(Dq, 2, 500, 1000, seed=SEED + 900 + (0 if np.isinf(nu) else int(nu)), nu=nu)
    cov, *_ = ppc_coverage(Dq, fq["theta"].reshape(-1, len(Dq.names)), fq["sig2"].reshape(-1, 3), np.random.default_rng(SEED + 950), nu=nu)
    lik_trials["normal" if np.isinf(nu) else f"t{int(nu)}"] = cov
    log(f"likelihood trial nu={nu}: in-sample 80% coverage {cov:.3f}")
    if chosen_nu is None and 0.75 <= cov <= 0.85:
        chosen_nu = nu
if chosen_nu is None:
    chosen_nu = 5.0
    lik_choice_note = "no likelihood reached 0.75-0.85 coverage; t5 kept and V7 is non-blocking (intervals conservative)"
else:
    lik_choice_note = f"{'Normal' if np.isinf(chosen_nu) else 't%d' % chosen_nu} chosen: first with coverage in [0.75, 0.85]; t5 kept as a robustness run"
gibbs.LIKELIHOOD_NU = chosen_nu
log("likelihood:", lik_choice_note)

# ------------------------------------------------------------------ fits
N_CHAINS, WARM, DRAWS = 4, 1000, 2500
summary = {}
conv = {}
for k, preset in enumerate(["agnostic", "literature", "discount", "data_only"]):
    t0 = time.time()
    D = Design(main, "M", mundlak=True, statewide_dev=statewide_dev, u_active=u_active, preset=preset, cents=cents)
    fit = run_gibbs(D, N_CHAINS, WARM, DRAWS, seed=SEED + k)
    dl = deltas(fit, D, cents)
    th = fit["theta"]
    chk = {"beta_L": th[..., D.idx["beta_L"]], "beta_P": th[..., D.idx["beta_P"]],
           "omega_maga": th[..., D.idx["omega_maga"]], "omega_mod": th[..., D.idx["omega_mod"]]}
    for a in ARCHETYPES:
        if a != "mainstream_liberal":
            chk[f"delta[{a}]"] = dl[a]
    cv = {nm: {"rhat": rhat(v), "ess_bulk": ess(v)} for nm, v in chk.items()}
    conv[preset] = cv
    # thin to 1000 joint draws (chain-major concatenation, every 10th)
    flat = th.reshape(-1, th.shape[-1])
    step = flat.shape[0] // 1000
    sel = np.arange(0, step * 1000, step)
    np.savez_compressed(WORK / f"fit_{preset}.npz", theta=flat[sel], theta_full_style=np.stack([chk[k2].ravel() for k2 in chk]),
                        style_names=np.array(list(chk)), sig2=fit["sig2"].reshape(-1, 3)[sel], sa2=fit["sa2"].ravel()[sel],
                        tau=fit["tau"].ravel()[sel], names=np.array(D.names))
    s = {nm: summ(v.ravel()) for nm, v in chk.items()}
    s["sd"] = {nm: float(v.std()) for nm, v in chk.items()}
    pr = PRESETS[preset]
    s["sd_ratio"] = {b: (float(chk[b].std() / pr[b][1]) if pr[b][1] else None) for b in ("beta_L", "beta_P")}
    for nm in ("d_L", "d_P", "lambda_L", "lambda_P", "R_inc_pv", "inc_R", "inc_D"):
        if nm in D.idx:
            s[nm] = summ(th[..., D.idx[nm]].ravel())
    s["sigma"] = {o: summ(np.sqrt(fit["sig2"][..., j]).ravel()) for j, o in enumerate(["House+Special", "Senate", "Governor"])}
    s["sigma_alpha"] = summ(np.sqrt(fit["sa2"]).ravel())
    s["tau_u"] = summ(fit["tau"].ravel())
    summary[preset] = s
    worst = max(v["rhat"] for v in cv.values())
    miness = min(v["ess_bulk"] for v in cv.values())
    log(f"{preset}: {time.time()-t0:.1f}s  beta_L={s['beta_L']} beta_P={s['beta_P']}  max Rhat={worst:.4f} min ESS={miness:.0f}")
    for a in ARCHETYPES:
        if a != "mainstream_liberal":
            log(f"    delta[{a}] = {s[f'delta[{a}]']}")

meta = {
    "n_main": len(main), "centroids": {a: {"L": c[0], "P": c[1], "n": c[2]} for a, c in cents.items()},
    "min_n": mn, "u_active": u_active, "statewide_dev_active": statewide_dev, "n_statewide": n_statewide,
    "interaction_gate": interaction_gate, "levels_triggered": levels, "fit_level_pre_diagnostics": fit_level,
    "label_kappa_archetype_proxy": kappa_arch, "label_kappa_rules_main": kappa_rules_main,
    "names": Design(main, "M", statewide_dev=statewide_dev, u_active=u_active, cents=cents).names,
    "summary": summary, "convergence": conv,
    "likelihood_nu": (None if np.isinf(chosen_nu) else chosen_nu), "likelihood": ("normal" if np.isinf(chosen_nu) else f"t{int(chosen_nu)}"),
    "likelihood_trials": lik_trials, "likelihood_note": lik_choice_note,
    "mundlak_archetype_terms": Design(main, "M", statewide_dev=statewide_dev, u_active=u_active, cents=cents).mundlak_arch,
    "min_n_rule": {"races": gibbs.MIN_N_RACES, "states": gibbs.MIN_N_STATES, "close": 5, "source": "override O-1a"}, "settings": {"chains": N_CHAINS, "warmup": WARM, "draws": DRAWS, "thinned": 1000},
}
save_json(WORK / "fit_meta.json", meta, nd=5, indent=1)
log.save()
