"""Step 06: robustness grid (§3.7), label-flip attenuation + SIMEX (R3), prior sensitivity,
partial-count selection report (§2.4 / V20).

Each Gibbs robustness run uses 2 chains x (400 warm-up + 800 draws); the headline fit uses 4 x (1000 + 2500).
Writes work/robustness.json.
"""
import math
import time

import numpy as np

from common import ARCHETYPES, L_MAP, NON_REF, P_MAP, SEED, WORK, Log, load_json, ols, save_json, summ
import gibbs
from gibbs import Design, centroids, deltas, run_gibbs
import olsfe

log = Log("06_robustness")
rng = np.random.default_rng(SEED + 60)
rows = load_json(WORK / "dataset_labeled.json")
meta = load_json(WORK / "fit_meta.json")
labels = load_json(WORK / "labels_report.json")
main = [r for r in rows if r["in_main"]]
gibbs.LIKELIHOOD_NU = float("inf") if meta["likelihood_nu"] is None else meta["likelihood_nu"]
cents = {a: (v["L"], v["P"], v["n"]) for a, v in meta["centroids"].items()}
u_active = meta["u_active"]
SWD = meta["statewide_dev_active"]
runs = []
t_start = time.time()


def gibbs_run(label, rs, seed, labelset="M", outcome="y", note=None, **kw):
    if len(rs) < 25:
        runs.append({"label": label, "n": len(rs), "skipped": "fewer than 25 rows"})
        return None
    kw.setdefault("u_active", u_active)
    kw.setdefault("statewide_dev", SWD and sum(r["statewide"] for r in rs) >= 25)
    kw.setdefault("mundlak", True)
    c = cents if labelset in ("M",) else centroids(rs, labelset) if labelset != "C" else cents
    for a in ARCHETYPES:
        if c[a][0] is None:
            c[a] = cents[a]
    D = Design(rs, labelset=labelset, outcome=outcome, cents=c, **kw)
    f = run_gibbs(D, 2, 400, 800, seed=seed)
    dl = deltas(f, D, c)
    out = {"label": label, "n": len(rs), "note": note,
           "beta_L": summ(f["theta"][..., D.idx["beta_L"]].ravel()), "beta_P": summ(f["theta"][..., D.idx["beta_P"]].ravel()),
           "delta": {a: summ(dl[a].ravel()) for a in NON_REF}}
    runs.append(out)
    log(f"{label:45s} n={len(rs):3d} " + " ".join(f"{a[:6]}={out['delta'][a][0]:+.2f}" for a in NON_REF))
    return out


def with_y(rs, fn):
    out = []
    for r in rs:
        v = fn(r)
        if v is None:
            continue
        r2 = dict(r)
        r2["_y"] = v
        out.append(r2)
    return out


def logit_share(m):
    s = (1 + m / 100) / 2
    return math.log(s / (1 - s))


k = 0
# ------------------------------------------------------------------ R1 outcomes
gibbs_run("R1: margin scale (D-R points) with m24 spline", main, SEED + 600, outcome="margin")
gibbs_run("R1: margin - house24 (House, unchanged lines)", with_y([r for r in main if r["office"] == "House" and r["house24"] is not None and abs(r["house24_total"] or 100) < 95],
                                                                    lambda r: r["m26"] - r["house24"]), SEED + 601, outcome="custom")
gibbs_run("R1: raw 2026 margin with m24 spline", with_y(main, lambda r: r["m26"]), SEED + 602, outcome="custom")
# ------------------------------------------------------------------ R2 leave-out
gibbs_run("R2: leave out Maine", [r for r in main if r["state"] != "ME"], SEED + 610)
gibbs_run("R2: leave out California", [r for r in main if r["state"] != "CA"], SEED + 611)
redistricted = sorted({r["state"] for r in rows if r.get("lines") == "2026_new"})
gibbs_run("R2: leave out redistricted states", [r for r in main if r["state"] not in redistricted], SEED + 612, note="states: " + ",".join(redistricted))
# 3 highest-leverage races per archetype (OLS-FE hat values)
Xs, ns, _ = olsfe.design(main, style="structural")
Hd = np.einsum("ij,jk,ik->i", Xs, np.linalg.pinv(Xs.T @ Xs), Xs)
drop = set()
for a in NON_REF:
    ii = [i for i, r in enumerate(main) if r["M_archetype"] == a and Hd[i] < 0.999]
    for i in sorted(ii, key=lambda i: -Hd[i])[:3]:
        drop.add(main[i]["id"])
gibbs_run("R2: drop each archetype's 3 highest-leverage races", [r for r in main if r["id"] not in drop], SEED + 613, note=",".join(sorted(drop)))
# leave-one-state-out (summarised as a range)
loso = {}
for j, s in enumerate(sorted({r["state"] for r in main})):
    rs = [r for r in main if r["state"] != s]
    D = Design(rs, "M", statewide_dev=SWD, u_active=u_active, cents=cents)
    f = run_gibbs(D, 1, 300, 500, seed=SEED + 700 + j)
    dl = deltas(f, D, cents)
    loso[s] = {a: float(np.median(dl[a])) for a in NON_REF}
loso_range = {a: {"min": min(v[a] for v in loso.values()), "max": max(v[a] for v in loso.values()),
                  "argmin": min(loso, key=lambda s: loso[s][a]), "argmax": max(loso, key=lambda s: loso[s][a])} for a in NON_REF}
log("R2 LOSO range:", loso_range)
# DFBETA for statewide races (OLS-FE, beta_L and beta_P)
yadj = olsfe.adj_outcome(main)
base = olsfe.fit(main, yadj, style="structural")
dfb = []
for i, r in enumerate(main):
    if not r["statewide"]:
        continue
    rs = [x for j, x in enumerate(main) if j != i]
    o = olsfe.fit(rs, olsfe.adj_outcome(rs), style="structural")
    dfb.append({"id": r["id"], "dbeta_L": float(o["b"][o["idx"]["beta_L"]] - base["b"][base["idx"]["beta_L"]]),
                "dbeta_P": float(o["b"][o["idx"]["beta_P"]] - base["b"][base["idx"]["beta_P"]])})
dfb.sort(key=lambda d: -(abs(d["dbeta_L"]) + abs(d["dbeta_P"])))
log("R2 top statewide DFBETA:", dfb[:3])
# ------------------------------------------------------------------ R3 labels
gibbs_run("R3: Set B (rule-based) labels only", main, SEED + 620, labelset="B", u_active=[])
gibbs_run("R3: high-confidence labels only", [r for r in main if r["style_confidence"] == "high" and r["label_source"] == "A"], SEED + 621, u_active=[])
gibbs_run("R3: Set C soft labels", main, SEED + 622, labelset="C")
gibbs_run("R3: strict source-date audit (dated/primary-record only keep Set A)", main, SEED + 623, labelset="S", u_active=[])
gibbs_run("R3: all archetype deviations u_a on (min-N ignored)", main, SEED + 624, u_active=NON_REF)

# label-flip attenuation (OLS-FE structural, 500 sims, 15% of labels flipped uniformly)
Lm = np.array([r["L_M"] for r in main])
Pm = np.array([r["P_M"] for r in main])
Am = [r["M_archetype"] for r in main]
pool = {a: [(r["L_M"], r["P_M"]) for r in main if r["M_archetype"] == a] or [(cents[a][0] or 1.0, cents[a][1] or 0.0)] for a in ARCHETYPES}
Xb, nb, _ = olsfe.design(main, style="structural", labels_override=(Lm, Pm, Am))
bb, _, _ = ols(Xb, yadj)
b0 = np.array([bb[nb.index("beta_L")], bb[nb.index("beta_P")]])


def flip_fit(rate):
    L, P, A = Lm.copy(), Pm.copy(), list(Am)
    sel = rng.random(len(main)) < rate
    for i in np.where(sel)[0]:
        new = rng.choice([a for a in ARCHETYPES if a != A[i]])
        L[i], P[i] = pool[new][rng.integers(len(pool[new]))]
        A[i] = new
    X, nm, _ = olsfe.design(main, style="structural", labels_override=(L, P, A))
    b, _, _ = ols(X, yadj)
    return np.array([b[nm.index("beta_L")], b[nm.index("beta_P")]])


fl = np.array([flip_fit(0.15) for _ in range(500)])
A_att = (fl.mean(0) / b0).tolist()
log(f"R3 label-flip attenuation A (beta_L, beta_P) = {A_att}, OLS base {b0}")
# SIMEX using the proxy second-coder agreement
po = labels["kappa_agent_vs_second_coder_proxy"]["archetype"]["agree"]
q = 1 - math.sqrt(po)
lams = [0.0, 0.5, 1.0, 1.5, 2.0]
means = [b0] + [np.mean([flip_fit(min(0.9, l * q)) for _ in range(100)], axis=0) for l in lams[1:]]
means = np.array(means)
simex = []
for j in range(2):
    c = np.polyfit(lams, means[:, j], 2)
    simex.append(float(np.polyval(c, -1.0)))
log(f"SIMEX (q={q:.3f}): beta_L {b0[0]:.2f} -> {simex[0]:.2f}; beta_P {b0[1]:.2f} -> {simex[1]:.2f}")
# ------------------------------------------------------------------ R4 samples
gibbs_run("R4: House only", [r for r in main if r["office"] in ("House", "Special")], SEED + 630)
gibbs_run("R4: statewide only", [r for r in main if r["statewide"]], SEED + 631)
gibbs_run("R4: Nov 2026 only (no specials)", [r for r in main if r["office"] != "Special"], SEED + 632)
ext = [r for r in rows if r["in_extended"]]
gibbs_run("R4: extended sample (|pres2024| <= 30)", [r for r in ext if r["p"] >= 0.80], SEED + 633)
full = [r for r in rows if r["in_full"] and r["p"] >= 0.80]
comp = [r for r in main if r["competitive"]]
gibbs_run("R4: competitive only (|pres2024| <= 20)", comp, SEED + 634, note="model scale (50 x delta-logit)")
gibbs_run("R4: competitive only, margin scale (previous headline spec)", comp, SEED + 636, outcome="margin")
prov = [r for r in rows if r["in_provisional"]]
prov_run = gibbs_run("R4: provisional (p >= 0.5)", prov, SEED + 635, note="latent treatment extended to all p < 0.95")
# ------------------------------------------------------------------ R5 priors / tau
for tf, sd in ((0.5, SEED + 641), (2.0, SEED + 642)):
    D = Design(main, "M", statewide_dev=SWD, u_active=u_active, cents=cents)
    f = run_gibbs(D, 2, 400, 800, seed=sd, tau_fixed=tf)
    dl = deltas(f, D, cents)
    runs.append({"label": f"R5: tau_u fixed {tf}", "n": len(main), "beta_L": summ(f["theta"][..., D.idx["beta_L"]].ravel()),
                 "beta_P": summ(f["theta"][..., D.idx["beta_P"]].ravel()), "delta": {a: summ(dl[a].ravel()) for a in NON_REF}})
for preset in ("agnostic", "literature", "discount", "data_only"):
    s = meta["summary"][preset]
    runs.append({"label": f"R5: preset {preset}", "n": len(main), "beta_L": s["beta_L"], "beta_P": s["beta_P"],
                 "delta": {a: s[f"delta[{a}]"] for a in NON_REF}, "exact_fit": True})
for nu, lab in ((float("inf"), "Normal"), (5.0, "t5")):
    if nu == gibbs.LIKELIHOOD_NU:
        continue
    D = Design(main, "M", statewide_dev=SWD, u_active=u_active, cents=cents)
    f = run_gibbs(D, 2, 400, 800, seed=SEED + 645, nu=nu)
    dl = deltas(f, D, cents)
    runs.append({"label": f"R5: {lab} likelihood", "n": len(main), "beta_L": summ(f["theta"][..., D.idx["beta_L"]].ravel()),
                 "beta_P": summ(f["theta"][..., D.idx["beta_P"]].ravel()), "delta": {a: summ(dl[a].ravel()) for a in NON_REF}})
runs.append({"label": "R5: sigma_gamma = 1.0", "skipped": "interactions gated off (fixed at 0); no effect"})
# ------------------------------------------------------------------ R6 between-state
gibbs_run("R6: random effects without Mundlak terms (between-state)", main, SEED + 650, mundlak=False)
runs.append({"label": "R7: with spending (post-treatment)", "skipped": "no spending data in the race files"})

# ------------------------------------------------------------------ prior sensitivity rule (§3.7)
dep = {}
for a in NON_REF:
    sa = np.sign(meta["summary"]["agnostic"][f"delta[{a}]"][0])
    sd_ = np.sign(meta["summary"]["data_only"][f"delta[{a}]"][0])
    sl = np.sign(meta["summary"]["literature"][f"delta[{a}]"][0])
    dep[a] = bool(sa != sd_ or sa != sl)
log("direction_depends_on_prior:", dep)

# ------------------------------------------------------------------ partial-count selection report (§2.4, V20)
sel_rep = {}
prov_arch = []
for a in ARCHETYPES:
    elig = [r for r in rows if r["M_archetype"] == a and (r["in_main"] or (r["exclusion_reason"] or "").startswith("partial_count_lt_80"))]
    ex = [r for r in elig if not r["in_main"]]
    share = len(ex) / len(elig) if elig else 0.0
    sel_rep[a] = {"eligible": len(elig), "excluded_p_lt_80": len(ex), "share": share, "ids": [r["id"] for r in ex]}
    if share > 0.20:
        prov_arch.append(a)
log("selection report:", {a: (v["eligible"], v["excluded_p_lt_80"], round(v["share"], 2)) for a, v in sel_rep.items()})
log("provisional_archetypes:", prov_arch)

save_json(WORK / "robustness.json", {"runs": runs, "loso": loso, "loso_range": loso_range, "dfbeta_statewide": dfb,
                                      "label_flip": {"A": A_att, "beta_ols": b0.tolist(), "rate": 0.15, "n_sims": 500,
                                                     "flip_mean": fl.mean(0).tolist()},
                                      "simex": {"q": q, "lambdas": lams, "means": means.tolist(), "corrected": simex,
                                                "note": "misclassification rate q = 1 - sqrt(proxy second-coder agreement); OLS-FE structural; robustness row only"},
                                      "direction_depends_on_prior": dep, "selection_report": sel_rep, "provisional_archetypes": prov_arch,
                                      "provisional_refit": prov_run},
          nd=5, indent=1)
log(f"done in {time.time()-t_start:.0f}s")
log.save()
