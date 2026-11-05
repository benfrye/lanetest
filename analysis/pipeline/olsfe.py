"""OLS with state fixed effects, used by the diagnostics (D2, D3, D5, D7) and fast robustness runs."""
from __future__ import annotations

import numpy as np

from common import ARCHETYPES, cr2_vcov, ols, rcs_basis
from gibbs import CONTROLS, KNOTS, coords


def adj_outcome(rows, key="y"):
    """Observed outcome plus the expected late shift m_s*(1-p)/0.2 for partial counts (§2.4)."""
    out = []
    for r in rows:
        main_scale = key == "y"
        v = r["y_model"] if main_scale else r[key]
        p = r["p"]
        if p is not None and p < 0.95:
            v = v + r["late_shift_prior_mean"] * (1 - p) / 0.2 * (r["J"] if main_scale else 1.0)
        out.append(v)
    return np.array(out, float)


def design(rows, labelset="M", style="structural", state_fe=True, extra=None, labels_override=None):
    """Returns X, names, clusters. style in {'structural', 'dummies', 'none'}."""
    n = len(rows)
    cols, names = [], []
    states = sorted({r["state"] for r in rows})
    sidx = np.array([states.index(r["state"]) for r in rows])
    groups = sorted({(r["period"] if r["office"] == "Special" else r["office"]) for r in rows})
    gi = np.array([groups.index(r["period"] if r["office"] == "Special" else r["office"]) for r in rows])
    if state_fe:
        for s in range(len(states)):
            cols.append((sidx == s).astype(float))
            names.append(f"fe[{states[s]}]")
        for g in range(1, len(groups)):
            cols.append((gi == g).astype(float))
            names.append(f"office[{groups[g]}]")
    else:
        for g in range(len(groups)):
            cols.append((gi == g).astype(float))
            names.append(f"office[{groups[g]}]")
    B = rcs_basis(np.array([r["m24"] for r in rows]) / 10.0, KNOTS)
    for j in range(B.shape[1]):
        cols.append(B[:, j])
        names.append(f"spline[{j}]")
    for c in CONTROLS + ["rep_maga", "rep_moderate"]:
        cols.append(np.array([float(r[c]) for r in rows]))
        names.append(c)
    if extra:
        for nm, v in extra.items():
            cols.append(np.asarray(v, float))
            names.append(nm)
    if labels_override is not None:
        L, P, A = labels_override
    else:
        L = np.array([coords(r, labelset)[0] for r in rows], float)
        P = np.array([coords(r, labelset)[1] for r in rows], float)
        A = [coords(r, labelset)[2] for r in rows]
    if style == "structural":
        cols += [L - 1, P]
        names += ["beta_L", "beta_P"]
    elif style == "dummies":
        for a in ARCHETYPES:
            if a == "mainstream_liberal":
                continue
            v = np.array([1.0 if x == a else 0.0 for x in A])
            if v.sum() > 0:
                cols.append(v)
                names.append(f"arch[{a}]")
    X = np.column_stack(cols)
    # drop all-zero columns
    keep = np.abs(X).sum(axis=0) > 0
    X = X[:, keep]
    names = [nm for nm, k in zip(names, keep) if k]
    return X, names, np.array([r["state"] for r in rows])


def fit(rows, y, **kw):
    X, names, cl = design(rows, **kw)
    b, resid, XtX_inv = ols(X, y)
    V = cr2_vcov(X, resid, cl, XtX_inv)
    return {"b": b, "names": names, "se": np.sqrt(np.maximum(np.diag(V), 0)), "V": V, "resid": resid, "X": X,
            "XtX_inv": XtX_inv, "idx": {nm: i for i, nm in enumerate(names)}, "clusters": cl}
