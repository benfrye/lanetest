"""Step 07: 2026-as-presidential-map (Sim 5, rel26), named-candidate track records (§5.5),
and the primary share model (Sim 3, §6.6). Validation V16 and V17 are computed here.

Writes work/sim5.json, work/candidates.json, work/primary.json, and updates work/units.json (rel26).
"""
import math
import re

import numpy as np
from scipy.optimize import minimize

from common import (ANALYSIS, ARCHETYPES, L_MAP, P_MAP, RESEARCH, SEED, WORK, Log, fnum, load_json, save_json,
                    state_code, summ)

log = Log("07_translation")
rng = np.random.default_rng(SEED + 70)
rows = load_json(WORK / "dataset_labeled.json")
U = load_json(WORK / "units.json")
units = U["units"]
E24 = U["E24"]
uid = [u["id"] for u in units]
meta = load_json(WORK / "fit_meta.json")
diag = load_json(WORK / "diagnostics.json")
nyt = load_json(RESEARCH / "nyt_voter_trends.json")

# ============================================================== Sim 5: statewide House vote
house = [r for r in rows if r["office"] == "House"]
obs_ok = lambda r: (r["m26"] is not None and not r["uncontested"] and not r["same_party_general"] and not r["independent_backed"]
                    and (r["other_pct"] or 0) < 25 and r["rep_pct"] is not None)
by_state = {}
for r in house:
    by_state.setdefault(r["state"], []).append(r)
nat_obs_swing = np.mean([r["y"] for r in house if obs_ok(r)])
sim5_units = []
house26 = {}
for u in units:
    if u["type"] == "district":
        dist = int(u["id"].split("-")[1])
        rs = [r for r in by_state.get(u["parent"], []) if int(r["district"]) == dist]
    elif u["type"] == "dc":
        rs = []
    else:
        rs = by_state.get(u["id"], [])
    st_swing = [r["y"] for r in rs if obs_ok(r)]
    mean_sw = float(np.mean(st_swing)) if st_swing else float(nat_obs_swing)
    margins, vars_, ps, imp = [], [], [], 0
    for r in rs:
        if obs_ok(r):
            margins.append(r["m26"])
            p = r["p"] or 1.0
            vars_.append((25 * (1 - p)) ** 2 if p < 0.95 else 0.25)
            ps.append(p)
        else:
            margins.append(r["m24"] + mean_sw)
            vars_.append(25.0)
            ps.append(1.0)
            imp += 1
    if not rs:
        m = u["m24"] + mean_sw
        sd = 5.0
        pc, imp_share = None, 1.0
    else:
        m = float(np.mean(margins))
        sd = float(math.sqrt(sum(vars_)) / len(rs))
        pc, imp_share = float(np.mean(ps)), imp / len(rs)
    house26[u["id"]] = m
    sim5_units.append({"id": u["id"], "house26": m, "house26_sd": sd, "pct_counted": pc, "imputed_share": imp_share,
                       "hatched": bool(pc is not None and pc < 0.90), "n_districts": len(rs)})
state_level = [u for u in units if u["type"] != "district"]
W = sum(u["total_votes_2024"] for u in state_level)
nat_h26 = sum(house26[u["id"]] * u["total_votes_2024"] for u in state_level) / W
nat_swing = nat_h26 - E24
for u, s5 in zip(units, sim5_units):
    u["rel26"] = (house26[u["id"]] - u["m24"]) - nat_swing
    s5["rel26"] = u["rel26"]
log(f"national House two-party margin (equal-weight districts x 2024 state turnout) = D{nat_h26:+.2f}; swing {nat_swing:+.2f}")

# electorate adjustment (view 'electorate')
grp = {g["group"]: g for g in nyt["groups"]}
m_re = {"wc": grp["White college"]["margin"], "wnc": grp["White non-college"]["margin"], "black": grp["Black"]["margin"],
        "hisp": grp["Hispanic"]["margin"], "asian": grp["Asian"]["margin"], "other": grp["Other"]["margin"]}
m_age = {"y1829": grp["18-29"]["margin"], "a3044": grp["30-44"]["margin"], "a4564": grp["45-64"]["margin"], "a65": grp["65+"]["margin"]}
adj_raw = {}
for u in units:
    (pre_re, pre_age), (mid_re, mid_age) = U["cpres"][u["id"]], U["cmid"][u["id"]]
    a = 0.5 * (sum((pre_re[g] - mid_re[g]) * m_re[g] for g in m_re) + sum((pre_age[g] - mid_age[g]) * m_age[g] for g in m_age))
    adj_raw[u["id"]] = a
nat_adj = sum(adj_raw[u["id"]] * u["total_votes_2024"] for u in state_level) / W
for s5 in sim5_units:
    s5["electorate_adj"] = adj_raw[s5["id"]] - nat_adj

# V16 consistency
nyt_top = nyt["topline"]
nyt_2p = 100 * (nyt_top["dem_pct"] - nyt_top["rep_pct"]) / (nyt_top["dem_pct"] + nyt_top["rep_pct"])
buckets = nyt["state_house_vote_leader_buckets"]
bucket_of = {}
for b in ("D_70plus", "D_55_70", "D_50_55", "R_50_55", "R_55_70"):
    for s in buckets[b]:
        bucket_of[s] = b


def my_bucket(m):
    share = 50 + abs(m) / 2
    side = "D" if m > 0 else "R"
    if share >= 70:
        return f"{side}_70plus"
    if share >= 55:
        return f"{side}_55_70"
    return f"{side}_50_55"


agree = []
for s, b in bucket_of.items():
    mb = my_bucket(house26[s])
    agree.append({"state": s, "nyt": b, "ours": mb, "house26": house26[s], "match": mb == b})
share_match = float(np.mean([a["match"] for a in agree]))
v16 = {"national_house26": nat_h26, "nyt_topline_two_party": nyt_2p, "gap": nat_h26 - nyt_2p,
       "within_1_5": abs(nat_h26 - nyt_2p) <= 1.5, "bucket_match_share": share_match, "bucket_pass": share_match >= 0.90,
       "mismatches": [a for a in agree if not a["match"]],
       "pass": bool(abs(nat_h26 - nyt_2p) <= 1.5 and share_match >= 0.90),
       "note": "District vote totals are not on disk: districts are equal-weighted within a state and states weighted by 2024 presidential turnout. NYT buckets were read by eye from a map (approximate)."}
log("V16:", {k: v for k, v in v16.items() if k != "mismatches"})
log("V16 mismatches:", [(a["state"], a["nyt"], a["ours"], round(a["house26"], 1)) for a in v16["mismatches"]])

senate26 = [{"id": r["state"], "race": r["id"], "margin": r["m26"]} for r in rows if r["office"] == "Senate" and r["m26"] is not None]
gov26 = [{"id": r["state"], "race": r["id"], "margin": r["m26"]} for r in rows if r["office"] == "Governor" and r["m26"] is not None]

# ============================================================== candidates (§5.5)
# National environments for track-record years. EXTERNAL CONSTANTS (not in research files; published
# national House popular-vote and presidential margins, total-vote points). Verify before publication.
EXT_HOUSE = {2006: 8.0, 2010: -6.8, 2014: -5.7, 2018: 8.6, 2022: -2.7}
EXT_PRES = {2004: -2.5, 2008: 7.3, 2012: 3.9, 2016: 2.1, 2020: 4.5, 2024: -1.5}
off = load_json(RESEARCH / "offyear.json")
env2025 = float(np.mean([e["overperformance_vs_pres2024"] for e in off["elections"] if e["id"] in ("va_gov_2025", "nj_gov_2025")]))
env2026 = {}
for o in ("Senate", "Governor", "House"):
    ys = [r["y"] for r in rows if r["office"] == o and r["in_full"] and r["y"] is not None]
    env2026[o] = float(np.mean(ys))
log("2026 same-office mean overperformance:", env2026, "2025 env:", env2025)


def env_for(year, base_year, office):
    if year == 2026:
        o = "Governor" if "overnor" in office else ("Senate" if "Senate" in office else "House")
        return env2026[o], "2026 same-office mean (data)"
    if base_year is not None and int(base_year) == int(year):
        return 0.0, "same-day presidential baseline"
    if year == 2025:
        return env2025, "2025 VA/NJ governor mean (data)"
    if year == 2021 and "runoff" in office.lower():
        return 0.0, "Jan-2021 runoff vs 2020 baseline (treated as same cycle)"
    if year in EXT_HOUSE and base_year is not None and int(base_year) in EXT_PRES:
        return EXT_HOUSE[year] - EXT_PRES[int(base_year)], "EXTERNAL: national House margin minus prior presidential"
    if year % 2 == 1:
        # O-9: odd-year races (e.g. KY, VA, NJ governors) take the mean environment of the midterms
        # on either side, each measured against its prior presidential race.
        envs = []
        for my in (year - 1, year + 1, year - 3, year + 3):
            if my in EXT_HOUSE and (my - 2) in EXT_PRES:
                envs.append(EXT_HOUSE[my] - EXT_PRES[my - 2])
            elif my == 2026:
                envs.append(env2026["House"])
        envs = envs[:2]
        if envs:
            return float(np.mean(envs)), "odd year: mean of the neighbouring midterm environments (O-9)"
    return None, "no environment available"


sig_r = float(np.mean([meta["summary"]["agnostic"]["sigma"]["Senate"][0], meta["summary"]["agnostic"]["sigma"]["Governor"][0]]))
delta_med = {a: (meta["summary"]["agnostic"][f"delta[{a}]"][0] if a != "mainstream_liberal" else 0.0) for a in ARCHETYPES}
SKIP_PAT = re.compile(r"primary|vice president|president, national|recall|ticket|mayor|top-two|lost to", re.I)


# O-9 (model review): residuals on the logit scale (50 x delta-logit, like the 2026 outcome), the
# home-state advantage taken out of each past result (the engine adds it back at home), shrinkage
# with tau_c = 2 for statewide candidates and sigma_r = the empirical within-candidate SD of these
# residuals, no hard cutoff at one race, and lane / MAGA effects netted with the same values the
# engine applies (the 2028 blend of the 2026 fit and the competitive-seat history line).
TAU_C = 2.0
H_MEAN = 2.0
_hist_file = ANALYSIS / "history" / "history_comparison.json"
_hist_gap = {}
if _hist_file.exists():
    _he = load_json(_hist_file)["competitive"]["env_model"]["logit"]
    _hist_gap = {a: _he[a]["three_cycle"]["fe"]["even_gap"] for a in ("progressive", "left_populist", "moderate") if a in _he}
delta_net = {a: (0.5 * (delta_med[a] + _hist_gap[a]) if a in _hist_gap else delta_med[a]) for a in ARCHETYPES}
omega_maga_med = float(meta["summary"]["agnostic"]["omega_maga"][0])


def _l50(m):
    sh = min(max((100.0 + m) / 200.0, 0.005), 0.995)
    return 50.0 * math.log(sh / (1 - sh))


def _resid(entries, sign):
    used, dropped = [], []
    for t in entries or []:
        office = t.get("office") or ""
        mg = fnum(t.get("margin"))
        base = fnum(t.get("pres_baseline_margin", t.get("baseline_margin")))
        by = t.get("pres_baseline_year")
        if by is None and t.get("baseline"):
            mm = re.search(r"(20\d\d)", t["baseline"])
            by = int(mm.group(1)) if mm else None
        yr = t.get("year")
        if mg is None or base is None or yr is None or SKIP_PAT.search(office):
            dropped.append({"year": yr, "office": office, "why": "no baseline / not a general election vs a party opponent"})
            continue
        if (fnum(t.get("other_pct")) or 0) >= 10:  # same rule as the 2026 sample: strong third candidate
            dropped.append({"year": yr, "office": office, "why": "third candidate >= 10%"})
            continue
        env, src = env_for(int(yr), by, office)
        if env is None:
            dropped.append({"year": yr, "office": office, "why": src})
            continue
        r = sign * (_l50(mg) - _l50(base) - env) - H_MEAN
        used.append({"year": yr, "office": office, "r": r, "env": env, "env_source": src})
    return used, dropped


def track(entries, sign, arche=None, net=0.0):
    used, dropped = _resid(entries, sign)
    n = len(used)
    if n == 0:
        return {"o_hat": 0.0, "n": 0, "w": 0.0, "c_draws": [0.0] * 1000, "c_med": 0.0, "used": used, "dropped": dropped}
    o = float(np.mean([u["r"] for u in used])) - net
    w = TAU_C ** 2 / (TAU_C ** 2 + SIG_WITHIN ** 2 / n)
    draws = rng.normal(w * o, math.sqrt(w * SIG_WITHIN ** 2 / n), 1000)
    return {"o_hat": o, "n": n, "w": w, "c_draws": draws.tolist(), "c_med": float(np.median(draws)), "used": used, "dropped": dropped}


def slug(n):
    return re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


# empirical within-candidate SD of past-race residuals, pooled over both parties' candidates with 2+ races
_devs = []
for _f, _sg in (("candidates_dem.json", 1.0), ("candidates_gop.json", -1.0)):
    for _c in load_json(RESEARCH / _f)["candidates"]:
        _u, _ = _resid(_c.get("track_record"), _sg)
        if len(_u) >= 2:
            _rs = np.array([x["r"] for x in _u])
            _devs.extend((_rs - _rs.mean()) * math.sqrt(len(_rs) / (len(_rs) - 1)))
SIG_WITHIN = float(np.sqrt(np.mean(np.square(_devs)))) if _devs else 7.0
log("track records: tau_c", TAU_C, "sigma_within", round(SIG_WITHIN, 2), "from", len(_devs), "residuals")
cd = load_json(RESEARCH / "candidates_dem.json")
cands_dem = []
for c in cd["candidates"]:
    polls = [p["pct"] for p in c.get("primary_polling") or [] if fnum(p.get("pct")) is not None]
    mk = fnum((c.get("market_prob") or {}).get("value"))
    arch = c.get("archetype")
    tr = track(c.get("track_record"), +1.0, arch, net=delta_net.get(arch, 0.0))
    cands_dem.append({"id": slug(c["name"]), "name": c["name"], "archetype": arch, "L": L_MAP.get(c.get("ideology")),
                      "P": P_MAP.get(c.get("posture")), "home": state_code(c.get("home_state")),
                      "track": {k: tr[k] for k in ("o_hat", "n", "w", "c_draws")}, "track_detail": {"used": tr["used"], "dropped": tr["dropped"]},
                      "poll_nat_primary": float(np.mean(polls)) if polls else None, "market_nom": (mk / 100) if mk is not None else None,
                      "include_default": bool((mk or 0) >= 2 or (np.mean(polls) if polls else 0) >= 5),
                      "style_confidence": c.get("style_confidence")})
cg = load_json(RESEARCH / "candidates_gop.json")
cands_gop = []
for c in cg["candidates"]:
    sty = c.get("style") or ""
    # 2026 races sit in result_2026 in the GOP file; Democrats' 2026 races are in their
    # track_record lists, so add them here to treat both parties the same.
    recs = list(c.get("track_record") or [])
    r26 = c.get("result_2026")
    if r26 and fnum(r26.get("margin")) is not None and r26.get("office") and fnum(c.get("home_state_pres2024_margin")) is not None:
        recs.append({"year": 2026, "office": r26["office"], "margin": r26["margin"], "pres_baseline_margin": c["home_state_pres2024_margin"],
                     "pres_baseline_year": 2024})
    # MAGA nominees carried the MAGA-opponent penalty in their own races; the engine applies it again, so add it back.
    tr = track(recs, -1.0, net=(-omega_maga_med if sty.startswith("maga") else 0.0))  # R-positive personal strength
    mk = (c.get("market_prob") or {}).get("avg")
    cands_gop.append({"id": slug(c["name"]), "name": c["name"], "opp_type": "maga" if sty.startswith("maga") else "traditional",
                      "style_raw": sty, "home": state_code(c.get("home_state")),
                      "track": {k: tr[k] for k in ("o_hat", "n", "w", "c_draws")}, "track_detail": {"used": tr["used"], "dropped": tr["dropped"]},
                      "market_nom": (fnum(mk) / 100) if fnum(mk) is not None else None})
log("Dem track records:", [(c["name"], c["track"]["n"], round(c["track"]["o_hat"], 1), round(c["track"]["w"], 2)) for c in cands_dem])
log("GOP track records:", [(c["name"], c["track"]["n"], round(c["track"]["o_hat"], 1), round(c["track"]["w"], 2)) for c in cands_gop])

# ============================================================== primary share model (Sim 3)
prim = load_json(RESEARCH / "primaries.json")
srows = {r["id"]: r for r in load_json(RESEARCH / "states.json")["rows"]}
COV = [("black", "black_nh_pct_cvap"), ("white_college", "white_college_pct_adults25"), ("y1829", "age_18_29_pct_cvap"),
       ("urban", "urban_pct_2020_census")]
base_states = [s for s in srows if "-" not in s]
Zraw = np.array([[srows[s][k] for _, k in COV] for s in base_states], float)
Zmu, Zsd = Zraw.mean(0), Zraw.std(0)
Zs = {s: (np.array([srows[s][k] for _, k in COV]) - Zmu) / Zsd for s in base_states}
LANE = {"progressive": "left", "left_populist": "left", "mainstream_liberal": "mainstream", "moderate": "moderate", "center_populist": "moderate"}
LANES = ["left", "mainstream", "moderate"]
contests = []
for c in prim["contests"]:
    if "convention" in (c.get("office") or "").lower():
        continue
    cs = [x for x in c.get("candidates") or [] if fnum(x.get("pct")) is not None and x.get("archetype") in LANE]
    if len(cs) < 2 or c["state"] not in Zs:
        continue
    tot = sum(x["pct"] for x in cs)
    contests.append({"id": c["id"], "state": c["state"], "Z": Zs[c["state"]],
                     "lane": [LANES.index(LANE[x["archetype"]]) for x in cs], "P": [P_MAP.get(x.get("posture"), 0.0) for x in cs],
                     "s": [x["pct"] / tot for x in cs], "won": [bool(x.get("won")) for x in cs],
                     "nendorse": [len(x.get("key_endorsements") or []) for x in cs], "names": [x["name"] for x in cs]})
lane_cov = {l: {"n": sum(1 for c in contests if LANES.index(l) in c["lane"]),
                "states": len({c["state"] for c in contests if LANES.index(l) in c["lane"]})} for l in LANES}
slope_ok = {l: v["n"] >= 10 and v["states"] >= 5 for l, v in lane_cov.items()}
log("primary contests:", len(contests), "lane coverage:", lane_cov)
KAPPA = 20.0  # effective sample size per contest (overdispersion; documented simplification)
NP = 2 + 2 * 4 + 1  # zeta(left, moderate), eta(left, moderate) x 4, b_pop


def unpack(w):
    zeta = np.array([w[0], 0.0, w[1]])
    eta = np.zeros((3, 4))
    eta[0] = w[2:6] if slope_ok["left"] else 0.0
    eta[2] = w[6:10] if slope_ok["moderate"] else 0.0
    return zeta, eta, w[10]


def neglp(w):
    zeta, eta, bp = unpack(w)
    lp = -0.5 * (w[0] ** 2 + w[1] ** 2) - 0.5 * np.sum(w[2:10] ** 2) / 0.25 - 0.5 * w[10] ** 2
    for c in contests:
        u = np.array([zeta[l] + eta[l] @ c["Z"] + bp * p for l, p in zip(c["lane"], c["P"])])
        u -= u.max()
        logp = u - np.log(np.exp(u).sum())
        lp += KAPPA * np.dot(c["s"], logp)
    return -lp


res = minimize(neglp, np.zeros(NP), method="BFGS")
w_hat = res.x
Hinv = res.hess_inv
draws = rng.multivariate_normal(w_hat, (Hinv + Hinv.T) / 2, 1000)
zeta_d = {"left": draws[:, 0].tolist(), "moderate": draws[:, 1].tolist()}
eta_d = {"left": (draws[:, 2:6] if slope_ok["left"] else np.zeros((1000, 4))).tolist(),
         "moderate": (draws[:, 6:10] if slope_ok["moderate"] else np.zeros((1000, 4))).tolist()}
bpop = draws[:, 10].tolist()
log("primary MAP: zeta", w_hat[:2].round(2), "b_pop", round(w_hat[10], 2))


def pwin(c, w, nsim=2000):
    zeta, eta, bp = unpack(w)
    u = np.array([zeta[l] + eta[l] @ c["Z"] + bp * p for l, p in zip(c["lane"], c["P"])])
    sims = u[None, :] + rng.normal(0, 0.6, (nsim, len(u))) + rng.normal(0, 0.3, (nsim, len(u)))
    win = np.argmax(sims, 1)
    return np.bincount(win, minlength=len(u)) / nsim


bm, bb = [], []
for c in contests:
    pw = pwin(c, w_hat)
    y = np.array(c["won"], float)
    bm.append(float(np.sum((pw - y) ** 2)))
    ne = np.array(c["nendorse"])
    if ne.max() > 0 and (ne == ne.max()).sum() < len(ne):
        base = (ne == ne.max()).astype(float) / (ne == ne.max()).sum()
    else:
        base = np.full(len(ne), 1 / len(ne))
    bb.append(float(np.sum((base - y) ** 2)))
brier_m, brier_b = float(np.mean(bm)), float(np.mean(bb))
coalition_enabled = brier_m <= brier_b
log(f"V17: Brier model {brier_m:.3f} vs baseline {brier_b:.3f} -> coalition_enabled={coalition_enabled}")

# delegates (approximation of the DNC allocation: half 2024 Dem-vote share, half EV share, x 3,936 pledged)
dem24 = {s: srows[s]["pres2024"]["dem_votes"] for s in base_states}
ev = {s: srows[s]["electoral_votes_2028"] + (2 if s in ("ME", "NE") else 0) for s in base_states}
for s in ("ME", "NE"):
    ev[s] = sum(srows[x]["electoral_votes_2028"] for x in srows if x == s or x.startswith(s + "-"))
D_tot, EV_tot = sum(dem24.values()), sum(ev.values())
DATES = {  # 2024 Democratic calendar, approximate (labelled assumption)
    "SC": "2028-02-03", "NH": "2028-01-23", "NV": "2028-02-06", "MI": "2028-02-27",
    **{s: "2028-03-05" for s in ["AL", "AR", "CA", "CO", "IA", "ME", "MA", "MN", "NC", "OK", "TN", "TX", "UT", "VT", "VA"]},
    **{s: "2028-03-12" for s in ["GA", "MS", "WA"]}, **{s: "2028-03-19" for s in ["AZ", "IL", "KS", "OH", "FL"]},
    **{s: "2028-03-23" for s in ["LA", "MO"]}, **{s: "2028-04-02" for s in ["CT", "DE", "NY", "RI", "WI"]},
    **{s: "2028-04-06" for s in ["AK", "HI", "ND", "WY"]}, "PA": "2028-04-23", "IN": "2028-05-07",
    **{s: "2028-05-14" for s in ["MD", "NE", "WV"]}, **{s: "2028-05-21" for s in ["KY", "OR", "ID"]},
    **{s: "2028-06-04" for s in ["MT", "NJ", "NM", "SD", "DC"]},
}
pstates = []
for s in base_states:
    dele = round(3936 * (0.5 * dem24[s] / D_tot + 0.5 * ev[s] / EV_tot))
    pstates.append({"id": s, "delegates": int(dele), "X": Zs[s].tolist(), "date_dnc2024": DATES.get(s, "2028-06-04")})
order = sorted({d for d in DATES.values()})
cal_dnc = [[s for s in base_states if DATES.get(s, "2028-06-04") == d] for d in order]
trad_first = [["IA"], ["NH"], ["NV"], ["SC"]]
rest = [[s for s in g if s not in ("IA", "NH", "NV", "SC")] for g in cal_dnc]
cal_trad = trad_first + [g for g in rest if g]
primary = {"lanes": LANES, "populist_term": True, "covariates": [c for c, _ in COV], "zeta": zeta_d, "eta": eta_d,
           "b_populist": bpop, "states": pstates, "calendars": {"dnc2024": cal_dnc, "traditional": cal_trad},
           "settings": {"poll_weight": 0.3, "kappa_sd": 0.7, "noise_sd": 0.3, "home_logit": 0.8, "momentum": 0.5, "threshold": 0.15,
                        "dropout_after": ["4th", "super_tuesday"], "dropout_share": 0.10, "lane_affinity_same": 0.6,
                        "majority": int(sum(p["delegates"] for p in pstates) // 2 + 1)},
           "validation": {"brier_model": brier_m, "brier_baseline": brier_b, "coalition_enabled": bool(coalition_enabled)},
           "_meta": {"n_contests": len(contests), "lane_coverage": lane_cov, "slope_min_n_ok": slope_ok, "kappa_effective_n": KAPPA,
                     "covariates_are_state_level": True,
                     "notes": "Z uses state-level composition (district primary electorates not on disk); priors eta ~ N(0,0.5^2) (no 2016/2020 exit-poll file); Laplace approximation for draws; delegates and calendar are approximations of the 2024 DNC rules/calendar."}}

save_json(WORK / "units.json", U, nd=6)
save_json(WORK / "sim5.json", {"units": sim5_units, "national_house26": nat_h26, "durable_phi_default": 1, "senate": senate26, "governor": gov26,
                                "V16": v16}, nd=4, indent=1)
save_json(WORK / "candidates.json", {"dem": cands_dem, "gop": cands_gop, "sigma_r": sig_r, "tau_c": TAU_C, "sigma_within": SIG_WITHIN, "env2026": env2026, "env2025": env2025,
                                      "external_env_constants": {"house": EXT_HOUSE, "pres": EXT_PRES}}, nd=4, indent=1)
save_json(WORK / "primary.json", primary, nd=4)
log.save()
