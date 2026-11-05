"""Multiverse over the post-hoc decisions O-6..O-9 (and the R3 label choice).

Reads pipeline inputs read-only (work/, output/, history/); writes only to analysis/multiverse/.

2026 grid (24 universes, full Gibbs fit, same sampler and settings as 03_fit.py's agnostic preset):
  sample   : all contested (in_main) | competitive only (|pres2024| <= 20)
  scale    : 50 x delta-logit (y_model) | margin points (y) with the m24 spline
  labels   : agent/fit labels (Set M = fit_archetype) | rule labels (Set B, u_a off as in 06 R3)
             | high-confidence agent labels only (subset, u_a off as in 06 R3)
  controls : with swing2024 | without
2028 grid (8 universes on the representative 2026 spec = current main fit, work/fit_agnostic.npz):
  source   : 2026 fit | competitive-seat history | all-seat history | blend (fit + competitive history)
  pi       : LogNormal(0, 0.35) clip [0.5, 2] (old, median 1) | LogNormal(log 0.6, 0.45) clip [0.2, 1.5] (current)
plus a secondary cross: sources {fit, blend} x pi x all 24 2026 universes.
"""
import json
import math
import sys
import time
from itertools import product
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent
sys.path.insert(0, str(ANALYSIS / "pipeline"))

import gibbs  # noqa: E402
from gibbs import Design, centroids, deltas, run_gibbs  # noqa: E402
import reference_engine as RE  # noqa: E402
from common import ARCHETYPES, SEED  # noqa: E402

WORK = ANALYSIS / "work"
GAPS = ["progressive", "left_populist", "moderate"]
LANES28 = ["mainstream_liberal", "progressive", "left_populist", "moderate"]
CHAINS, WARM, DRAWS = 4, 1000, 2500


def load(p):
    return json.loads(Path(p).read_text())


def q(x):
    x = np.asarray(x, float).ravel()
    return [round(float(np.median(x)), 3), round(float(np.quantile(x, .1)), 3), round(float(np.quantile(x, .9)), 3)]


rows = load(WORK / "dataset_labeled.json")
meta = load(WORK / "fit_meta.json")
mp = load(WORK / "model_params.candidate.json")
hist = load(ANALYSIS / "history" / "history_comparison.json")
main = [r for r in rows if r["in_main"]]
gibbs.LIKELIHOOD_NU = float("inf") if meta["likelihood_nu"] is None else meta["likelihood_nu"]
CENTS_M = {a: (v["L"], v["P"], v["n"]) for a, v in meta["centroids"].items()}
U_ACTIVE_M = meta["u_active"]
SWD = meta["statewide_dev_active"]
CONTROLS_FULL = list(gibbs.CONTROLS)
CONTROLS_NOSWING = [c for c in CONTROLS_FULL if c != "swing2024"]

# ------------------------------------------------------------------ 2026 multiverse
DIM26 = {
    "sample": ["all", "competitive"],
    "scale": ["logit50", "margin"],
    "labels": ["agent", "rule", "high_conf"],
    "controls": ["with_swing2024", "no_swing2024"],
}
t0 = time.time()
univ26 = []
fit_deltas = {}  # key -> dict of thinned delta draws + omega_maga, for the 2028 cross
for k, (sample, scale, labels, ctrl) in enumerate(product(*DIM26.values())):
    rs = main if sample == "all" else [r for r in main if r["competitive"]]
    if labels == "high_conf":
        rs = [r for r in rs if r["style_confidence"] == "high" and r["label_source"] == "A"]
    labelset = "B" if labels == "rule" else "M"
    u_act = U_ACTIVE_M if labels == "agent" else []
    if labelset == "M":
        c = dict(CENTS_M)  # 06 convention: main-sample centroids for Set M runs
    else:
        c = centroids(rs, labelset)
        for a in ARCHETYPES:
            if c[a][0] is None:
                c[a] = CENTS_M[a]
    gibbs.CONTROLS = CONTROLS_FULL if ctrl == "with_swing2024" else CONTROLS_NOSWING
    D = Design(rs, labelset=labelset, mundlak=True, statewide_dev=SWD and sum(r["statewide"] for r in rs) >= 25,
               u_active=u_act, outcome="y" if scale == "logit50" else "margin", preset="agnostic", cents=c)
    f = run_gibbs(D, CHAINS, WARM, DRAWS, seed=SEED + 5000 + k)
    dl = deltas(f, D, c)
    gibbs.CONTROLS = CONTROLS_FULL
    key = f"{sample}|{scale}|{labels}|{ctrl}"
    arch_n = {a: int(sum(1 for r in rs if gibbs.coords(r, labelset)[2] == a)) for a in ARCHETYPES}
    row = {"id": key, "sample": sample, "scale": scale, "labels": labels, "controls": ctrl, "n": len(rs),
           "n_by_archetype": arch_n, "u_active": u_act,
           "gap_2026": {a: q(dl[a]) for a in GAPS},
           "p_gap_negative": {a: round(float(np.mean(dl[a] < 0)), 3) for a in GAPS}}
    univ26.append(row)
    flat = {a: dl[a].ravel() for a in ARCHETYPES}
    om = f["theta"][..., D.idx["omega_maga"]].ravel()
    sel = np.linspace(0, len(om) - 1, 1000).astype(int)
    fit_deltas[key] = {"delta": {a: flat[a][sel] for a in ARCHETYPES}, "omega_maga": om[sel]}
    print(f"{key:48s} n={len(rs):3d} " + " ".join(f"{a[:5]}={row['gap_2026'][a][0]:+.2f}" for a in GAPS), flush=True)
print(f"2026 grid: {time.time() - t0:.0f}s")

# ------------------------------------------------------------------ 2028 engine (as in 10_validate.py)
bank = RE.build_bank(mp, n=10000, seed=SEED + 100)
E24 = mp["national"]["E24"]
Ehist = RE.sample_E(mp["environment"]["presets"]["even"], 10000, np.random.default_rng(SEED + 101))

pi_rng = np.random.default_rng(SEED + 90)
PI = {
    "median1_old": np.clip(np.exp(pi_rng.normal(0.0, 0.35, 1000)), 0.5, 2.0),
    "median0.6_current": np.array(mp["transfer_pi"]["pi_draws"]),  # exact draws the pipeline uses
}


def headline28(delta, om, pi):
    res = {}
    for a in LANES28:
        dlt = np.asarray(delta[a], float)
        res[a] = 0.5 * (RE.v_dist(bank, Ehist, pi * dlt, E24) + RE.v_dist(bank, Ehist, pi * (dlt + om), E24))
    out = {"P_win": {a: round(float(res[a].mean()), 4) for a in LANES28},
           "dV_vs_ml_pts": {a: q(100 * (res[a] - res["mainstream_liberal"])) for a in LANES28 if a != "mainstream_liberal"}}
    return out


# style sources
z = np.load(WORK / "fit_agnostic.npz", allow_pickle=True)
nm = list(z["names"])
th = z["theta"]
cm = meta["centroids"]
fit_main = {"omega_maga": th[:, nm.index("omega_maga")], "delta": {}}
for a in ARCHETYPES:
    d = th[:, nm.index("beta_L")] * (cm[a]["L"] - 1) + th[:, nm.index("beta_P")] * cm[a]["P"]
    if f"u[{a}]" in nm:
        d = d + th[:, nm.index(f"u[{a}]")]
    fit_main["delta"][a] = d


def hist_draws(src):
    """Normal draws around the even-environment gap, SD from the 80% interval widened 1.5x (09_export)."""
    rng_h = np.random.default_rng(SEED + 808)
    out = {"mainstream_liberal": np.zeros(1000)}
    for a in GAPS:
        if src == "competitive":
            g = hist["competitive"]["env_model"]["logit"][a]["three_cycle"]["fe"]
        else:
            g = hist["headline"]["even_environment"][a]["gls_3cycle"]
        sd = (g["even_hi80"] - g["even_lo80"]) / (2 * 1.2816) * 1.5
        out[a] = g["even_gap"] + sd * rng_h.standard_normal(1000)
    return out


HIST_D = {"history_competitive": hist_draws("competitive"), "history_all_seats": hist_draws("all")}


def mix(x, y):
    o = np.asarray(x, float).copy()
    o[1::2] = np.asarray(y, float)[1::2]
    return o


def sources(fit):
    return {
        "fit_2026": fit,
        "history_competitive": {"omega_maga": fit_main["omega_maga"], "delta": HIST_D["history_competitive"]},
        "history_all_seats": {"omega_maga": fit_main["omega_maga"], "delta": HIST_D["history_all_seats"]},
        "blend": {"omega_maga": fit["omega_maga"],
                  "delta": {a: mix(fit["delta"][a], HIST_D["history_competitive"][a]) for a in LANES28}},
    }


REP = "all|logit50|agent|with_swing2024"
univ28 = []
for (sname, st), (pname, pi) in product(sources(fit_main).items(), PI.items()):
    h = headline28(st["delta"], np.asarray(st["omega_maga"]), pi)
    univ28.append({"id": f"{sname}|{pname}", "spec_2026": REP + " (work/fit_agnostic.npz, the published fit)",
                   "source": sname, "pi": pname, "pi_median": round(float(np.median(pi)), 3),
                   "gap_input": {a: q(st["delta"][a]) for a in GAPS}, **h})
    print(f"2028 {sname:22s} {pname:18s} " + " ".join(f"{a[:5]}={h['P_win'][a]:.3f}" for a in LANES28))

# secondary cross: fit and blend sources over every 2026 universe
cross = []
for key, fd in fit_deltas.items():
    srcs = sources(fd)
    for sname in ("fit_2026", "blend"):
        for pname, pi in PI.items():
            st = srcs[sname]
            h = headline28(st["delta"], np.asarray(st["omega_maga"]), pi)
            cross.append({"id": f"{key}|{sname}|{pname}", "spec_2026": key, "source": sname, "pi": pname, **h})

# check: published headline (blend, current pi) reproduced?
pub = load(ANALYSIS / "output" / "validation.json")["headline_2028"]["published"]
chk = next(u for u in univ28 if u["id"] == "blend|median0.6_current")
repro = {a: {"published_V": pub[a]["V"], "multiverse_V": chk["P_win"][a]} for a in LANES28}
print("repro check:", repro)
rep_refit = next(u for u in univ26 if u["id"] == REP)


# ------------------------------------------------------------------ summaries
def pct(vals):
    v = np.asarray(vals, float)
    return {"median": round(float(np.median(v)), 3), "p10": round(float(np.quantile(v, .1)), 3),
            "p90": round(float(np.quantile(v, .9)), 3), "min": round(float(v.min()), 3), "max": round(float(v.max()), 3)}


def dim_effect(universes, dims, getter):
    """Mean over 'all other dims fixed' cells of the range of the headline across that dimension's levels."""
    out = {}
    for d, levels in dims.items():
        others = [o for o in dims if o != d]
        cells = {}
        for u in universes:
            cells.setdefault(tuple(u[o] for o in others), {})[u[d]] = getter(u)
        rngs = [max(c.values()) - min(c.values()) for c in cells.values() if len(c) == len(levels)]
        out[d] = round(float(np.mean(rngs)), 3)
    return out


summary = {"2026": {}, "2028": {}}
ref_sign = {a: np.sign(rep_refit["gap_2026"][a][0]) for a in GAPS}
for a in GAPS:
    meds = [u["gap_2026"][a][0] for u in univ26]
    summary["2026"][a] = {
        "headline_spec_median": rep_refit["gap_2026"][a][0],
        "across_universes": pct(meds),
        "share_same_sign_as_headline": round(float(np.mean([np.sign(m) == ref_sign[a] for m in meds])), 3),
        "share_negative": round(float(np.mean([m < 0 for m in meds])), 3),
        "share_80pct_excludes_0": round(float(np.mean([(u["gap_2026"][a][1] > 0) or (u["gap_2026"][a][2] < 0) for u in univ26])), 3),
        "dimension_effect": dim_effect(univ26, DIM26, lambda u, a=a: u["gap_2026"][a][0]),
    }
summary["2026_agent_labels_only"] = {}
ag26 = [u for u in univ26 if u["labels"] == "agent"]
for a in GAPS:
    meds = [u["gap_2026"][a][0] for u in ag26]
    summary["2026_agent_labels_only"][a] = {
        "n_universes": len(ag26), "across_universes": pct(meds),
        "share_same_sign_as_headline": round(float(np.mean([np.sign(m) == ref_sign[a] for m in meds])), 3),
        "share_80pct_excludes_0": round(float(np.mean([(u["gap_2026"][a][1] > 0) or (u["gap_2026"][a][2] < 0) for u in ag26])), 3),
        "dimension_effect": dim_effect(ag26, {k: v for k, v in DIM26.items() if k != "labels"}, lambda u, a=a: u["gap_2026"][a][0])}
DIM28 = {"source": ["fit_2026", "history_competitive", "history_all_seats", "blend"], "pi": list(PI)}
for a in LANES28:
    summary["2028"][f"P_win[{a}]"] = {"across_universes": pct([u["P_win"][a] for u in univ28]),
                                      "dimension_effect": dim_effect(univ28, DIM28, lambda u, a=a: u["P_win"][a])}
for a in GAPS:
    meds = [u["dV_vs_ml_pts"][a][0] for u in univ28]
    pub_sign = np.sign(chk["dV_vs_ml_pts"][a][0])
    summary["2028"][f"dV[{a}]"] = {"published_spec": chk["dV_vs_ml_pts"][a][0], "across_universes": pct(meds),
                                   "share_same_sign_as_published": round(float(np.mean([np.sign(m) == pub_sign for m in meds])), 3),
                                   "dimension_effect": dim_effect(univ28, DIM28, lambda u, a=a: u["dV_vs_ml_pts"][a][0])}
summary["2028_cross"] = {}
for a in GAPS:
    for s in ("fit_2026", "blend"):
        meds = [u["dV_vs_ml_pts"][a][0] for u in cross if u["source"] == s]
        summary["2028_cross"][f"dV[{a}]|{s}"] = {**pct(meds), "share_negative": round(float(np.mean([m < 0 for m in meds])), 3)}

outj = {
    "generated": time.strftime("%Y-%m-%d %H:%M"),
    "method": {
        "fit_2026": f"Full Gibbs (gibbs.run_gibbs), agnostic preset, likelihood nu={gibbs.LIKELIHOOD_NU}, {CHAINS} chains x ({WARM} warm-up + {DRAWS} draws), Mundlak on, statewide deviations if >= 25 statewide rows. Rule/high-confidence label universes switch u_a off (as in 06 R3). OLS-FE/EB not needed: each fit takes a few seconds.",
        "gap": "delta_a = beta_L (Lbar_a - 1) + beta_P Pbar_a + u_a vs mainstream_liberal; [median, 10th, 90th] of posterior draws; points on the outcome scale of that universe (logit50 = points in an even seat).",
        "engine_2028": "reference_engine.v_dist at the 'even' environment t5(0,5), bank seed SEED+100, E seed SEED+101, generic opponent = average of non-MAGA and MAGA (as in 10_validate.headline). P_win = mean over style x pi draws; dV = 100 x (P_win[lane] - P_win[mainstream_liberal]) per draw, [median, 10th, 90th].",
        "history_sources": "competitive: history_comparison.competitive.env_model.logit[a].three_cycle.fe; all seats: headline.even_environment[a].gls_3cycle; drawn normal with 80% interval widened 1.5x (09_export). blend = alternate draws of the 2026 fit and competitive history.",
        "pi": {"median1_old": "LogNormal(0, 0.35) clipped [0.5, 2] (METHODOLOGY 5.4 original)", "median0.6_current": "model_params transfer_pi.pi_draws: LogNormal(log 0.6, 0.45) clipped [0.2, 1.5]"},
        "representative_2026_spec": REP,
    },
    "dimensions_2026": DIM26, "dimensions_2028": DIM28,
    "universes_2026": univ26, "universes_2028": univ28, "universes_2028_cross": cross,
    "summary": summary,
    "checks": {"published_2028_reproduced": repro,
               "refit_vs_published_main_2026": {a: {"refit": rep_refit["gap_2026"][a],
                                                    "published": [round(v, 3) for v in meta["summary"]["agnostic"][f"delta[{a}]"]]} for a in GAPS}},
}
(HERE / "multiverse.json").write_text(json.dumps(outj, indent=1))
print(json.dumps(summary, indent=1))
