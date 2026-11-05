"""Shared helpers for the election-swing analysis pipeline.

Everything here is deterministic. Paths are resolved relative to this file so the
scripts can be run from any working directory.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

PIPE = Path(__file__).resolve().parent
ANALYSIS = PIPE.parent
ROOT = ANALYSIS.parent
RESEARCH = ROOT / "research"
WORK = ANALYSIS / "work"
OUT = ANALYSIS / "output"
STORY = OUT / "story_data"
for _d in (WORK, OUT, STORY):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 20261104
ELECTION_DAY = "2026-11-03"
ARCHETYPES = ["progressive", "left_populist", "center_populist", "mainstream_liberal", "moderate"]
NON_REF = [a for a in ARCHETYPES if a != "mainstream_liberal"]
L_MAP = {"conservative": -1.0, "moderate": 0.0, "liberal": 1.0, "left": 2.0}
P_MAP = {"establishment": 0.0, "mixed": 0.5, "populist": 1.0}
EXPECTED_CENTROIDS = {
    "progressive": (2.0, 0.25), "left_populist": (2.0, 1.0), "center_populist": (0.5, 1.0),
    "mainstream_liberal": (1.0, 0.0), "moderate": (0.0, 0.0),
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
NAME_TO_CODE = {v.lower(): k for k, v in STATE_NAMES.items()}

# Regions for the error-factor model (METHODOLOGY §5.6)
REGIONS = {
    "NE": ["ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "DE", "MD", "DC"],
    "RUST": ["PA", "OH", "MI", "WI", "IN", "IL", "MN", "IA"],
    "SOUTH": ["VA", "NC", "SC", "GA", "FL", "AL", "MS", "LA", "AR", "TN", "KY", "WV", "TX", "OK"],
    "PLAINS_MTN": ["ND", "SD", "NE", "KS", "MO", "MT", "WY", "ID", "UT"],
    "SW": ["AZ", "NM", "NV", "CO"],
    "PACIFIC": ["CA", "OR", "WA", "AK", "HI"],
}
STATE_REGION = {s: r for r, ss in REGIONS.items() for s in ss}
WEST_COAST_LATE_D = {"CA", "WA", "OR"}  # m_s = +1 late-shift prior (§2.4)

# NYT national shifts (2026 House vs 2024 pres), from research/nyt_voter_trends.json; loaded
# dynamically in 07 but kept here as a documented fallback.
NYT_RE_SHIFT = {"wc": 9, "wnc": 14, "black": 9, "hisp": 28, "asian": 17, "other": 17}
NYT_AGE_SHIFT = {"y1829": 32, "a3044": 24, "a4564": 13, "a65": 6}


# ----------------------------------------------------------------------------- main outcome (decision O-6)
# Main sample = all contested races (user decision 2026-11-04). Main outcome = 50 x delta-logit of the
# two-party D share ("points of margin in an even seat"), which compresses correctly near the ceiling/floor
# of lopsided seats. Raw/descriptive numbers stay in plain margin points.
MAIN_OUTCOME = "logit50"
COMPETITIVE_WINDOW = 20.0  # old House lean window, now the R4 robustness row


def logit50(m):
    m = max(min(m, 99.0), -99.0)
    s = (1 + m / 100) / 2
    return 50.0 * math.log(s / (1 - s))


def jac50(m):
    """d logit50 / d margin at margin m (converts margin-point SDs and shifts to the model scale)."""
    m = max(min(m, 99.0), -99.0)
    return 1.0 / (1 - (m / 100) ** 2)


def ymodel(r):
    """Outcome on the main model scale for a row dict (needs m26 and m24)."""
    if r.get("m26") is None or r.get("m24") is None:
        return None
    if MAIN_OUTCOME == "logit50":
        return logit50(r["m26"]) - logit50(r["m24"])
    return r["m26"] - r["m24"]


def jmodel(r):
    return jac50(r["m26"]) if MAIN_OUTCOME == "logit50" else 1.0


# ----------------------------------------------------------------------------- logging
class Log:
    """Tiny logger that also records structured exclusions."""

    def __init__(self, step: str):
        self.step = step
        self.lines: list[str] = []

    def __call__(self, *msg):
        s = " ".join(str(m) for m in msg)
        print(f"[{self.step}] {s}", flush=True)
        self.lines.append(s)

    def save(self):
        (WORK / f"log_{self.step}.txt").write_text("\n".join(self.lines) + "\n")


# ----------------------------------------------------------------------------- IO
def load_json(path):
    with open(path) as f:
        return json.load(f)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        v = float(o)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _round(o, nd):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v, nd) for v in o]
    return o


def save_json(path, obj, nd: int | None = 4, indent=None):
    obj = _clean(obj)
    if nd is not None:
        obj = _round(obj, nd)
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent, separators=(",", ":") if indent is None else None)


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


# ----------------------------------------------------------------------------- numeric helpers
def fnum(x):
    """Defensive float conversion: returns None for missing / unparsable values."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v):
        return None
    return v


def two_party(dem, rep):
    d, r = fnum(dem), fnum(rep)
    if d is None or r is None or d + r <= 0:
        return None
    return 100.0 * (d - r) / (d + r)


def q80(x, axis=0):
    x = np.asarray(x)
    return np.median(x, axis=axis), np.quantile(x, 0.1, axis=axis), np.quantile(x, 0.9, axis=axis)


def summ(x):
    m, lo, hi = q80(x)
    return [float(m), float(lo), float(hi)]


def rcs_basis(x, knots):
    """Restricted (natural) cubic spline basis (Harrell). Returns len(knots)-1 columns,
    the first being x itself. Linear beyond the boundary knots."""
    x = np.asarray(x, float)
    k = np.asarray(knots, float)
    K = len(k)
    cols = [x]
    norm = (k[-1] - k[0]) ** 2

    def pp(v):
        return np.maximum(v, 0.0) ** 3

    for j in range(K - 2):
        term = (pp(x - k[j]) - pp(x - k[K - 2]) * (k[K - 1] - k[j]) / (k[K - 1] - k[K - 2])
                + pp(x - k[K - 1]) * (k[K - 2] - k[j]) / (k[K - 1] - k[K - 2]))
        cols.append(term / norm)
    return np.column_stack(cols)


def cohen_kappa(a, b):
    a = list(a)
    b = list(b)
    n = len(a)
    if n == 0:
        return None
    cats = sorted(set(a) | set(b), key=str)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    if pe >= 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


# ----------------------------------------------------------------------------- MCMC diagnostics
def _autocorr(x):
    n = len(x)
    x = x - x.mean()
    f = np.fft.rfft(x, n=2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    return ac / ac[0] if ac[0] > 0 else np.zeros(n)


def ess(chains):
    """Bulk-ish ESS (Geyer initial monotone sequence) on rank-normalised split chains.
    chains: array (n_chains, n_draws)."""
    from scipy.stats import norm, rankdata

    c = np.asarray(chains, float)
    m, n = c.shape
    half = n // 2
    c = np.concatenate([c[:, :half], c[:, half:2 * half]], axis=0)
    m, n = c.shape
    if np.allclose(c.std(), 0):
        return float(m * n)
    r = rankdata(c.ravel()).reshape(c.shape)
    z = norm.ppf((r - 0.375) / (c.size + 0.25))
    acs = np.array([_autocorr(z[i]) for i in range(m)])
    var_w = z.var(axis=1, ddof=1).mean()
    var_plus = var_w * (n - 1) / n + z.mean(axis=1).var(ddof=1)
    rho = 1 - (var_w - (acs * z.var(axis=1, ddof=1)[:, None]).mean(axis=0)) / var_plus
    rho[0] = 1.0
    # Geyer initial positive & monotone sequence
    s = 0.0
    prev = np.inf
    t = 0
    while t + 1 < n:
        p = rho[t] + rho[t + 1]
        if p < 0:
            break
        p = min(p, prev)
        s += p
        prev = p
        t += 2
    tau = -1 + 2 * s
    tau = max(tau, 1.0 / math.log10(m * n))
    return float(m * n / tau)


def rhat(chains):
    """Rank-normalised split R-hat (max of bulk and folded)."""
    from scipy.stats import norm, rankdata

    c = np.asarray(chains, float)
    m, n = c.shape
    half = n // 2
    c = np.concatenate([c[:, :half], c[:, half:2 * half]], axis=0)

    def _rh(x):
        mm, nn = x.shape
        if np.allclose(x.std(), 0):
            return 1.0
        r = rankdata(x.ravel()).reshape(x.shape)
        z = norm.ppf((r - 0.375) / (x.size + 0.25))
        W = z.var(axis=1, ddof=1).mean()
        B = nn * z.mean(axis=1).var(ddof=1)
        vhat = (nn - 1) / nn * W + B / nn
        return float(math.sqrt(vhat / W))

    med = np.median(c)
    return max(_rh(c), _rh(np.abs(c - med)))


# ----------------------------------------------------------------------------- OLS helpers
def ols(X, y, w=None):
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    if w is not None:
        sw = np.sqrt(w)
        Xw, yw = X * sw[:, None], y * sw
    else:
        Xw, yw = X, y
    XtX = Xw.T @ Xw
    XtX_inv = np.linalg.pinv(XtX)
    b = XtX_inv @ Xw.T @ yw
    resid = y - X @ b
    return b, resid, XtX_inv


def cr2_vcov(X, resid, clusters, XtX_inv):
    """Bell-McCaffrey CR2 cluster-robust covariance."""
    X = np.asarray(X, float)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(clusters):
        idx = np.where(clusters == g)[0]
        Xg = X[idx]
        Hgg = Xg @ XtX_inv @ Xg.T
        M = np.eye(len(idx)) - Hgg
        vals, vecs = np.linalg.eigh((M + M.T) / 2)
        vals = np.where(vals > 1e-8, vals ** -0.5, 0.0)
        A = vecs @ np.diag(vals) @ vecs.T
        u = Xg.T @ (A @ resid[idx])
        meat += np.outer(u, u)
    return XtX_inv @ meat @ XtX_inv


def state_code(s):
    if s is None:
        return None
    s = str(s).strip()
    if s.upper() in STATE_NAMES:
        return s.upper()
    base = re.split(r"[(/]", s)[0].strip().lower()
    return NAME_TO_CODE.get(base)


def die(msg):
    print("FATAL:", msg, file=sys.stderr)
    sys.exit(1)
