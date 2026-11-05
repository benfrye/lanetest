"""Blocked Gibbs sampler for the correlated-random-effects style model (METHODOLOGY §3.1–3.4).

y*_i = mu_o + alpha_s + f(m24) + X'b_X + lambda_L*Lbar_s + lambda_P*Pbar_s
       + beta_L*(L-1) + beta_P*P + 1[statewide]*(d_L*(L-1) + d_P*P) + u_a + eps
eps ~ t5(0, sigma_o)  (scale mixture), alpha_s ~ N(0, sigma_alpha^2), u_a ~ N(0, tau_u^2)
y_obs = y* - g_s (1-p)/0.2 + e_count  for 0.80 <= p < 0.95 (latent y*)

ES terms are not in the model: district demographics are absent (fallback Level 3, >25% missing,
so ES is dropped; state-level ES would be collinear with alpha_s anyway).
The interactions beta_PW / beta_LY are gated off (Level 2) and fixed at 0.
Power prior alpha (Discount preset) tempers every likelihood term, including the augmented ones.
"""
from __future__ import annotations

import numpy as np

from common import ARCHETYPES, rcs_basis

MIN_N_RACES, MIN_N_STATES = 12, 8
# Likelihood degrees of freedom for eps: 5.0 = t5 (METHODOLOGY default); inf = Normal. Set from fit_meta by callers.
LIKELIHOOD_NU = 5.0
KNOTS = np.array([-60.0, -10.0, 0.0, 10.0, 60.0]) / 10.0  # interior -10/0/10 (§2.6); boundaries widened for the all-contested sample (O-6)
CONTROLS = ["inc_D", "inc_R", "R_inc_pv", "D_inc_pv", "rep_quality", "rep_scandal", "swing2024"]  # swing2024: O-9

PRESETS = {
    "agnostic":   {"beta_L": (0.0, 2.0), "beta_P": (0.0, 2.0), "omega_maga": (0.0, 2.0), "omega_mod": (0.0, 2.0), "alpha": 1.0},
    "literature": {"beta_L": (-1.5, 1.5), "beta_P": (0.0, 1.5), "omega_maga": (1.0, 2.0), "omega_mod": (-1.0, 2.0), "alpha": 1.0},
    "discount":   {"beta_L": (0.0, 2.0), "beta_P": (0.0, 2.0), "omega_maga": (0.0, 2.0), "omega_mod": (0.0, 2.0), "alpha": 0.5},
    "data_only":  {"beta_L": (0.0, None), "beta_P": (0.0, None), "omega_maga": (0.0, 2.0), "omega_mod": (0.0, 2.0), "alpha": 1.0},
}


def coords(row, labelset="M"):
    """Return (L, P, archetype or soft vector) under a label set."""
    if labelset == "C":
        probs = row.get("C_probs")
        return None, None, probs
    if labelset == "M":
        return row["L_M"], row["P_M"], row["M_archetype"]
    if labelset == "A":
        return row["L_A"], row["P_A"], row["archetype"]
    if labelset == "B":
        return row["L_B"], row["P_B"], row["B_archetype"]
    if labelset == "S":
        return row["L_S"], row["P_S"], row["S_archetype"]
    raise ValueError(labelset)


def centroids(rows, labelset="M"):
    out = {}
    for a in ARCHETYPES:
        Ls, Ps = [], []
        for r in rows:
            L, P, arch = coords(r, labelset)
            if arch == a and L is not None and P is not None:
                Ls.append(L)
                Ps.append(P)
        out[a] = (float(np.mean(Ls)) if Ls else None, float(np.mean(Ps)) if Ps else None, len(Ls))
    return out


def soft_coords(rows, labelset, cents):
    """Per-row (L, P, archetype-weight vector) arrays."""
    n = len(rows)
    L = np.zeros(n)
    P = np.zeros(n)
    W = np.zeros((n, len(ARCHETYPES)))
    for i, r in enumerate(rows):
        if labelset == "C":
            probs = r["C_probs"]
            for j, a in enumerate(ARCHETYPES):
                W[i, j] = probs[a]
            Lc = np.array([cents[a][0] if cents[a][0] is not None else 1.0 for a in ARCHETYPES])
            Pc = np.array([cents[a][1] if cents[a][1] is not None else 0.0 for a in ARCHETYPES])
            L[i] = W[i] @ Lc
            P[i] = W[i] @ Pc
        else:
            l, p, a = coords(r, labelset)
            L[i], P[i] = l, p
            W[i, ARCHETYPES.index(a)] = 1.0
    return L, P, W


def min_n_status(rows, labelset="M"):
    """§3.8 minimum-N for archetype deviations u_a."""
    st = {}
    for a in ARCHETYPES:
        sel = [r for r in rows if coords(r, labelset)[2] == a] if labelset != "C" else \
              [r for r in rows if max(r["C_probs"], key=r["C_probs"].get) == a]
        n = len(sel)
        ns = len({r["state"] for r in sel})
        n10 = sum(1 for r in sel if abs(r["m24"]) <= 10)
        # Override O-1a (lead reviewer, 2026-11-04): >= 12 races from >= 8 states (was >= 15 from >= 6), >= 5 with |m24| <= 10
        st[a] = {"n": n, "n_states": ns, "n_close": n10, "ok": n >= MIN_N_RACES and ns >= MIN_N_STATES and n10 >= 5}
    return st


class Design:
    def __init__(self, rows, labelset="M", mundlak=True, statewide_dev=True, u_active=None,
                 outcome="y", preset="agnostic", cents=None, drop_style=False, extra_cols=None):
        self.rows = rows
        self.labelset = labelset
        n = len(rows)
        self.n = n
        self.cents = cents or centroids(rows, labelset)
        L, P, W = soft_coords(rows, labelset, self.cents)
        self.L, self.P, self.W = L, P, W
        states = sorted({r["state"] for r in rows})
        self.states = states
        sidx = np.array([states.index(r["state"]) for r in rows])
        self.sidx = sidx
        groups = []
        for r in rows:
            if r["office"] == "Special":
                groups.append(r["period"])
            else:
                groups.append(r["office"])
        self.groups = sorted(set(groups), key=lambda g: (g != "House", g))
        gidx = np.array([self.groups.index(g) for g in groups])
        self.var_group = np.array([0 if r["office"] in ("House", "Special") else (1 if r["office"] == "Senate" else 2) for r in rows])
        cols, names, m0, sd0, kinds = [], [], [], [], []

        def add(col, name, mean, sd, kind):
            cols.append(np.asarray(col, float))
            names.append(name)
            m0.append(mean)
            sd0.append(sd)
            kinds.append(kind)

        for g, gn in enumerate(self.groups):
            add((gidx == g).astype(float), f"mu[{gn}]", 0.0, 10.0, "mu")
        for s, sn in enumerate(states):
            add((sidx == s).astype(float), f"alpha[{sn}]", 0.0, None, "alpha")
        m24 = np.array([r["m24"] for r in rows]) / 10.0
        B = rcs_basis(m24, KNOTS)
        for j in range(B.shape[1]):
            add(B[:, j], f"spline[{j}]", 0.0, 5.0, "spline")
        self.ctrl_means = {}
        for c in CONTROLS:
            v = np.array([float(r[c]) for r in rows])
            self.ctrl_means[c] = v.mean()
            add(v - v.mean(), c, 0.0, 5.0, "X")
        pr = PRESETS[preset]
        add([r["rep_maga"] for r in rows], "omega_maga", pr["omega_maga"][0], pr["omega_maga"][1], "X")
        add([r["rep_moderate"] for r in rows], "omega_mod", pr["omega_mod"][0], pr["omega_mod"][1], "X")
        if extra_cols:
            for nm, vals in extra_cols.items():
                add(vals, nm, 0.0, 5.0, "X")
        # Mundlak state means of style coordinates over included races
        self.mundlak = mundlak
        Lbar = np.array([np.mean(L[sidx == s] - 1) for s in range(len(states))])
        Pbar = np.array([np.mean(P[sidx == s]) for s in range(len(states))])
        self.Lbar_s, self.Pbar_s = Lbar, Pbar
        Wbar = np.array([W[sidx == s].mean(0) for s in range(len(states))])
        self.Wbar_s = Wbar
        self.mundlak_arch = []
        if mundlak and not drop_style:
            add(Lbar[sidx], "lambda_L", 0.0, 5.0, "X")
            add(Pbar[sidx], "lambda_P", 0.0, 5.0, "X")
            # Override O-1b: state means of archetype indicators, so u_a is identified within state like OLS-FE dummies
            for a in ARCHETYPES:
                if a == "mainstream_liberal":
                    continue
                j = ARCHETYPES.index(a)
                col = Wbar[sidx, j]
                if np.abs(col).sum() > 0:
                    add(col, f"lambda_A[{a}]", 0.0, 5.0, "X")
                    self.mundlak_arch.append(a)
        self.drop_style = drop_style
        stw = np.array([1.0 if r["statewide"] else 0.0 for r in rows])
        self.stw = stw
        if not drop_style:
            add(L - 1, "beta_L", pr["beta_L"][0], pr["beta_L"][1], "style")
            add(P, "beta_P", pr["beta_P"][0], pr["beta_P"][1], "style")
            self.statewide_dev = statewide_dev
            if statewide_dev:
                add(stw * (L - 1), "d_L", 0.0, 1.0, "X")
                add(stw * P, "d_P", 0.0, 1.0, "X")
            self.u_active = [a for a in (u_active or []) if a != "mainstream_liberal"]
            for a in self.u_active:
                add(W[:, ARCHETYPES.index(a)], f"u[{a}]", 0.0, None, "u")
        else:
            self.statewide_dev = False
            self.u_active = []
        self.X = np.column_stack(cols)
        self.names = names
        self.idx = {nm: i for i, nm in enumerate(names)}
        self.kinds = np.array(kinds)
        self.m0 = np.array(m0)
        sd = np.array([np.nan if s is None else s for s in sd0], float)
        self.prec0 = np.where(np.isnan(sd), 0.0, 1.0 / np.where(np.isnan(sd), 1.0, sd) ** 2)
        # flat priors (data_only) have sd None for style but kind 'style'
        self.flat = np.array([(k == "style" and s is None) for k, s in zip(kinds, sd0)])
        self.prec0[self.flat] = 0.0
        self.alpha_cols = np.where(self.kinds == "alpha")[0]
        self.u_cols = np.where(self.kinds == "u")[0]
        # outcome and partial-count info
        scale_rows = np.ones(n)
        if outcome == "y":  # main model scale (O-6: 50 x delta-logit)
            yobs = np.array([r["y_model"] for r in rows], float)
            scale_rows = np.array([r["J"] for r in rows], float)
        elif outcome == "margin":
            yobs = np.array([r["y"] for r in rows], float)
        elif outcome == "logit":
            yobs = np.array([r["y_logit"] for r in rows], float)
        elif outcome == "house24":
            yobs = np.array([r["y_house24"] for r in rows], float)
        elif outcome == "prev_seat":
            yobs = np.array([r["y_prev"] for r in rows], float)
        elif outcome == "custom":
            yobs = np.array([r["_y"] for r in rows], float)
        else:
            raise ValueError(outcome)
        self.yobs = yobs
        p = np.array([r["p"] for r in rows], float)
        self.p = p
        self.latent = (p < 0.95)
        scale = (1.0 if outcome in ("y", "margin", "house24", "prev_seat", "custom") else 0.25) * scale_rows
        self.sd_count = np.where(self.latent, 25.0 * (1 - p) * scale, 0.0)
        self.shift_mult = np.where(self.latent, (1 - p) / 0.2 * scale, 0.0)
        self.m_s = np.array([1.0 if s in ("CA", "WA", "OR") else 0.0 for s in states])
        self.alpha_power = pr["alpha"]

    def row_vector(self, row):
        """Design vector for a new (held-out) row using this design's columns."""
        v = np.zeros(len(self.names))
        if row["office"] == "Special":
            g = row["period"]
        else:
            g = row["office"]
        if f"mu[{g}]" in self.idx:
            v[self.idx[f"mu[{g}]"]] = 1.0
        if f"alpha[{row['state']}]" in self.idx:
            v[self.idx[f"alpha[{row['state']}]"]] = 1.0
        B = rcs_basis(np.array([row["m24"] / 10.0]), KNOTS)[0]
        for j in range(len(B)):
            v[self.idx[f"spline[{j}]"]] = B[j]
        for c in CONTROLS:
            v[self.idx[c]] = float(row[c]) - self.ctrl_means[c]
        v[self.idx["omega_maga"]] = row["rep_maga"]
        v[self.idx["omega_mod"]] = row["rep_moderate"]
        L, P, W = soft_coords([row], self.labelset, self.cents)
        if not self.drop_style:
            if self.mundlak:
                if row["state"] in self.states:
                    s = self.states.index(row["state"])
                    self.set_state_means(v, self.Lbar_s[s], self.Pbar_s[s], self.Wbar_s[s])
                else:
                    self.set_state_means(v, L[0] - 1, P[0], W[0])
            v[self.idx["beta_L"]] = L[0] - 1
            v[self.idx["beta_P"]] = P[0]
            if self.statewide_dev:
                sw = 1.0 if row["statewide"] else 0.0
                v[self.idx["d_L"]] = sw * (L[0] - 1)
                v[self.idx["d_P"]] = sw * P[0]
            for a in self.u_active:
                v[self.idx[f"u[{a}]"]] = W[0, ARCHETYPES.index(a)]
        return v


def _set_state_means(self, v, Lb, Pb, Wb):
    """Write state-mean (Mundlak) values into a design vector."""
    if "lambda_L" in self.idx:
        v[self.idx["lambda_L"]] = Lb
        v[self.idx["lambda_P"]] = Pb
    for a in self.mundlak_arch:
        v[self.idx[f"lambda_A[{a}]"]] = Wb[ARCHETYPES.index(a)]


def _state_means_of(self, rows_same_state):
    L, P, W = soft_coords(rows_same_state, self.labelset, self.cents)
    return float(np.mean(L - 1)), float(np.mean(P)), W.mean(0)


Design.set_state_means = _set_state_means
Design.state_means_of = _state_means_of


def draw_omega_prior(rng, size, nu=None):
    """Scale-mixture weights for predictive draws: Gamma(nu/2, nu/2) for t_nu, 1 for Normal."""
    nu = LIKELIHOOD_NU if nu is None else nu
    if not np.isfinite(nu):
        return np.ones(size)
    return rng.gamma(nu / 2, 2 / nu, size=size)


def t_var_factor(nu=None):
    nu = LIKELIHOOD_NU if nu is None else nu
    return 1.0 if not np.isfinite(nu) else nu / (nu - 2)


def run_gibbs(D: Design, n_chains=4, warmup=1000, draws=2500, seed=0, tau_fixed=None,
              nu=None, sig_prior=(4.0, 6.0), alpha_prior=(3.0, 3.0), store_eta=False):
    rng = np.random.default_rng(seed)
    nu = LIKELIHOOD_NU if nu is None else nu
    normal_lik = not np.isfinite(nu)
    X, n = D.X, D.n
    p = X.shape[1]
    a_pow = D.alpha_power
    tau_grid = np.linspace(0.02, 4.0, 200)
    log_hn = -0.5 * tau_grid ** 2
    ngrp = 3
    out_theta = np.zeros((n_chains, draws, p))
    out_sig = np.zeros((n_chains, draws, ngrp))
    out_sa = np.zeros((n_chains, draws))
    out_tau = np.zeros((n_chains, draws))
    out_ystar = np.zeros((n_chains, draws, n)) if store_eta else None
    latent = D.latent
    yobs = D.yobs
    vg = D.var_group
    for c in range(n_chains):
        theta = np.zeros(p)
        sig2 = np.full(ngrp, 36.0) * rng.uniform(0.5, 2.0, ngrp)
        sa2 = 9.0 * rng.uniform(0.5, 2.0)
        tau = 1.0 if tau_fixed is None else tau_fixed
        omega = np.ones(n)
        ystar = yobs.copy()
        for it in range(warmup + draws):
            # 6. g_s from prior (not updated)
            g = D.m_s + 2.0 * rng.standard_normal(len(D.states))
            target = yobs + g[D.sidx] * D.shift_mult
            # 1. latent y*
            if latent.any():
                eta = X @ theta
                pm = omega / sig2[vg]
                pc = np.where(latent, 1.0 / np.maximum(D.sd_count, 1e-9) ** 2, 0.0)
                prec = pm + pc
                mean = (eta * pm + target * pc) / prec
                draw = mean + rng.standard_normal(n) / np.sqrt(a_pow * prec)
                ystar = np.where(latent, draw, yobs)
            # 2. coefficients
            prec0 = D.prec0.copy()
            prec0[D.alpha_cols] = 1.0 / sa2
            if len(D.u_cols):
                prec0[D.u_cols] = 1.0 / tau ** 2
            w = a_pow * omega / sig2[vg]
            Q = (X.T * w) @ X + np.diag(prec0)
            b = X.T @ (w * ystar) + prec0 * D.m0
            Lc = np.linalg.cholesky(Q)
            mu = np.linalg.solve(Lc.T, np.linalg.solve(Lc, b))
            theta = mu + np.linalg.solve(Lc.T, rng.standard_normal(p))
            r = ystar - X @ theta
            # 3. omega (t5 scale mixture)
            if not normal_lik:
                omega = rng.gamma((nu + a_pow) / 2.0, 1.0 / ((nu + a_pow * r ** 2 / sig2[vg]) / 2.0))
            # 4. sigma_o^2 and sigma_alpha^2
            for k in range(ngrp):
                sel = vg == k
                nk = sel.sum()
                nu0, s0 = sig_prior
                ss = nu0 * s0 ** 2 + a_pow * np.sum(omega[sel] * r[sel] ** 2)
                sig2[k] = ss / rng.chisquare(nu0 + a_pow * nk)
            al = theta[D.alpha_cols]
            sa2 = (alpha_prior[0] * alpha_prior[1] ** 2 + np.sum(al ** 2)) / rng.chisquare(alpha_prior[0] + len(al))
            # 5. tau_u griddy Gibbs
            if len(D.u_cols) and tau_fixed is None:
                u = theta[D.u_cols]
                lp = log_hn - len(u) * np.log(tau_grid) - 0.5 * np.sum(u ** 2) / tau_grid ** 2
                pr = np.exp(lp - lp.max())
                tau = rng.choice(tau_grid, p=pr / pr.sum())
            elif len(D.u_cols) == 0 and tau_fixed is None:
                tau = abs(rng.standard_normal())  # prior draw (no active deviations)
            if it >= warmup:
                k = it - warmup
                out_theta[c, k] = theta
                out_sig[c, k] = sig2
                out_sa[c, k] = sa2
                out_tau[c, k] = tau
                if store_eta:
                    out_ystar[c, k] = ystar
    return {"theta": out_theta, "sig2": out_sig, "sa2": out_sa, "tau": out_tau, "ystar": out_ystar,
            "names": D.names, "nu": nu}


def ppc_coverage(D: Design, theta, sig2, rng, nu=None):
    """In-sample 80% posterior-predictive coverage of the observed outcome (V7 procedure).
    theta: (S, p) draws, sig2: (S, 3)."""
    S = theta.shape[0]
    eta = theta @ D.X.T
    om = draw_omega_prior(rng, (S, D.n), nu)
    yrep = eta + np.sqrt(sig2[:, D.var_group] / om) * rng.standard_normal((S, D.n))
    g = D.m_s[D.sidx] + 2 * rng.standard_normal((S, D.n))
    yrep = np.where(D.latent, yrep - g * D.shift_mult + D.sd_count * rng.standard_normal((S, D.n)), yrep)
    lo, hi = np.quantile(yrep, 0.1, axis=0), np.quantile(yrep, 0.9, axis=0)
    cover = (D.yobs >= lo) & (D.yobs <= hi)
    return float(cover.mean()), cover, lo, hi, eta


def deltas(fit, D: Design, cents):
    """delta_a = beta_L*(Lbar_a - 1) + beta_P*Pbar_a + u_a  (per draw; chains x draws)."""
    th = fit["theta"]
    out = {}
    if D.drop_style:
        return {a: np.zeros(th.shape[:2]) for a in ARCHETYPES}
    bL = th[..., D.idx["beta_L"]]
    bP = th[..., D.idx["beta_P"]]
    for a in ARCHETYPES:
        La, Pa, _ = cents[a]
        if La is None:
            La, Pa = 1.0, 0.0
        d = bL * (La - 1) + bP * Pa
        if f"u[{a}]" in D.idx:
            d = d + th[..., D.idx[f"u[{a}]"]]
        out[a] = d
    return out


def param(fit, D, name):
    return fit["theta"][..., D.idx[name]]
