"""Float64 reference implementation of the browser engine's core (METHODOLOGY §5–6.2).

Used for validation (V1, V4, V18) and for the headline 2028 numbers in findings.md.
It reproduces the *math* of the break-even swing bank, not the JS PRNG stream (xoshiro128**),
so it cannot by itself serve as the V2 parity test.
"""
from __future__ import annotations

import numpy as np


def t5_unit(rng, size):
    """t5 draws scaled to unit variance: z*sqrt(3/5)/sqrt(chi2_5/5)."""
    z = rng.standard_normal(size)
    c = rng.chisquare(5, size)
    return z * np.sqrt(3 / 5) / np.sqrt(c / 5)


def unit_arrays(model):
    U = model["units"]
    ids = [u["id"] for u in U]
    ev = np.array([u["ev"] for u in U], float)
    m24 = np.array([u["m24"] for u in U], float)
    rel26 = np.array([u.get("rel26") or 0.0 for u in U], float)
    rel24 = np.array([u.get("rel24") or 0.0 for u in U], float)
    rel20 = np.array([u.get("rel20") or 0.0 for u in U], float)
    G = np.array([u["G"] for u in U], float)
    F = np.array([u["F"] for u in U], float)
    sid = np.array([u["sigma_idio"] for u in U], float)
    parent = [u.get("parent") for u in U]
    pidx = np.array([ids.index(p) if p else -1 for p in parent])
    dflt = (model.get("errors") or {}).get("district_sd", 1.5)
    dsd = np.array([(u.get("district_sd", dflt) if u["type"] == "district" else 0.0) for u in U], float)
    # districts use the parent state's G, hence the parent's k (matches site/src/lib/sim/bank.js)
    G = np.array([G[pidx[i]] if pidx[i] >= 0 else G[i] for i in range(len(U))])
    return ids, ev, m24, rel26, rel24, rel20, G, F, sid, pidx, dsd


def build_bank(model, n=10000, seed=1, u=0.0, psi=None, phi=None, zero_error=False, base=None):
    ids, ev, m24, rel26, rel24, rel20, G, F, sid, pidx, dsd = unit_arrays(model)
    if psi is None:
        psi = model["lean"]["psi"]
    if phi is None:
        phi = model["lean"]["phi"]
    rng = np.random.default_rng(seed)
    nu = len(ids)
    if zero_error:
        eps = np.zeros((n, nu))
    else:
        f = rng.standard_normal((n, F.shape[1]))
        v = t5_unit(rng, (n, nu))
        eps = f @ F.T + sid[None, :] * v
        # district units: parent's full error plus N(0, district_sd^2)
        isd = pidx >= 0
        eps[:, isd] = eps[:, pidx[isd]] + dsd[isd][None, :] * rng.standard_normal((n, isd.sum()))
    b = m24 if base is None else base
    a = b[None, :] + psi * rel26[None, :] + phi * (rel24 - rel20)[None, :] + eps
    k = 1 + u * (G - 1)
    assert np.all(k > 0)
    theta = -a / k[None, :]
    order = np.argsort(theta, axis=1)
    th_sorted = np.take_along_axis(theta, order, axis=1)
    cum = np.cumsum(ev[order], axis=1)
    need = model["national"]["ev_win"]
    pos = np.argmax(cum >= need, axis=1)
    t = th_sorted[np.arange(n), pos]
    tip = order[np.arange(n), pos]
    tie = cum[np.arange(n), pos] - ev[order][np.arange(n), pos] == need - 1
    return {"a": a, "theta": theta, "k": k, "t": t, "t_sorted": np.sort(t), "tip": tip, "tie269_below": tie, "ev": ev, "ids": ids}


def p_win_point(bank, E, delta, E24):
    """P(win | E, p) = F_t(E - E24 + delta) for an array of per-draw deltas."""
    S = E - E24 + np.asarray(delta, float)
    return np.searchsorted(bank["t_sorted"], S, side="left") / len(bank["t_sorted"])


def ev_dist(bank, S):
    """Electoral votes for D given a scalar national swing S, per outcome draw."""
    win = S > bank["theta"]
    return (win * bank["ev"][None, :]).sum(1)


def estar(bank, delta, E24):
    return E24 + np.median(bank["t"]) - np.asarray(delta, float)


def sample_E(preset, n, rng):
    if preset["type"] == "point":
        return np.full(n, preset["value"], float)
    if preset["type"] == "t":
        return preset["loc"] + preset["scale"] * rng.standard_t(preset["df"], n)
    if preset["type"] == "normal":
        return rng.normal(preset["mean"], preset["sd"], n)
    raise ValueError(preset)


def v_dist(bank, Edraws, delta, E24):
    """Distribution mode: D_j = E_j - E24 - t_j; P(win|p) = 1 - F_D(-delta_p)."""
    Dj = np.sort(Edraws - E24 - bank["t"])
    return 1 - np.searchsorted(Dj, -np.asarray(delta, float), side="right") / len(Dj)


# =============================================================================== JS-stream port (V2 parity)
# Exact port of site/src/lib/sim/rng.js (xoshiro128**, splitmix32 seeding, FNV-1a sub-streams,
# cached Box-Muller normals, Marsaglia-Tsang gamma) and of the draw order in bank.js getDraws().
import math as _m

_M32 = 0xFFFFFFFF


def _imul(a, b):
    return (a * b) & _M32


def _rotl(x, k):
    return ((x << k) | (x >> (32 - k))) & _M32


def hash_label(label):
    h = 0x811C9DC5
    for ch in str(label):
        h ^= ord(ch)
        h = _imul(h, 0x01000193)
    return h


class JsRng:
    def __init__(self, seed=1):
        s = seed & _M32
        st = []
        for _ in range(4):
            s = (s + 0x9E3779B9) & _M32
            z = s
            z = _imul(z ^ (z >> 16), 0x85EBCA6B)
            z = _imul(z ^ (z >> 13), 0xC2B2AE35)
            st.append((z ^ (z >> 16)) & _M32)
        self.s0, self.s1, self.s2, self.s3 = st
        if (self.s0 | self.s1 | self.s2 | self.s3) == 0:
            self.s0 = 1
        self._spare = 0.0
        self._has = False

    def next_u32(self):
        s0, s1, s2, s3 = self.s0, self.s1, self.s2, self.s3
        r = _imul(_rotl(_imul(s1, 5), 7), 9)
        t = (s1 << 9) & _M32
        n2 = s2 ^ s0
        n3 = s3 ^ s1
        n1 = s1 ^ n2
        n0 = s0 ^ n3
        n2 ^= t
        n3 = _rotl(n3, 11)
        self.s0, self.s1, self.s2, self.s3 = n0 & _M32, n1 & _M32, n2 & _M32, n3 & _M32
        return r

    def uniform(self):
        return (self.next_u32() + 0.5) * 2.0 ** -32

    def normal(self):
        if self._has:
            self._has = False
            return self._spare
        u1 = self.uniform()
        u2 = self.uniform()
        r = _m.sqrt(-2 * _m.log(u1))
        th = 2 * _m.pi * u2
        self._spare = r * _m.sin(th)
        self._has = True
        return r * _m.cos(th)

    def gamma(self, shape):
        if shape < 1:
            g = self.gamma(shape + 1)
            return g * self.uniform() ** (1 / shape)
        d = shape - 1 / 3
        c = 1 / _m.sqrt(9 * d)
        while True:
            while True:
                x = self.normal()
                v = 1 + c * x
                if v > 0:
                    break
            v = v * v * v
            u = self.uniform()
            x2 = x * x
            if u < 1 - 0.0331 * x2 * x2:
                return d * v
            if _m.log(u) < 0.5 * x2 + d * (1 - v + _m.log(v)):
                return d * v

    def student_t(self, df):
        z = self.normal()
        chi2 = 2 * self.gamma(df / 2)
        return z / _m.sqrt(chi2 / df)

    def t5_unit(self):
        return self.student_t(5) * _m.sqrt(3 / 5)


def substream(seed, label):
    h = hash_label(label)
    s = (_imul((seed & _M32) ^ 0x5BD1E995, 0x27D4EB2D) ^ h) & _M32
    return JsRng(s)


def build_bank_js(model, n=2000, seed=1, u=0.0, psi=None, phi=None):
    """Bank built from the JS engine's exact random stream (float64)."""
    ids, ev, m24, rel26, rel24, rel20, G, F, sid, pidx, dsd = unit_arrays(model)
    psi = model["lean"]["psi"] if psi is None else psi
    phi = model["lean"]["phi"] if phi is None else phi
    Un, K = len(ids), F.shape[1]
    rng = substream(seed, "errors")
    eps = np.zeros((n, Un))
    for j in range(n):
        f = [rng.normal() for _ in range(K)]
        row = np.zeros(Un)
        for s in range(Un):
            if pidx[s] >= 0:
                continue
            e = 0.0
            for k in range(K):
                e += F[s, k] * f[k]
            row[s] = e + sid[s] * rng.t5_unit()
        for s in range(Un):
            if pidx[s] >= 0:
                row[s] = row[pidx[s]] + dsd[s] * rng.normal()
        eps[j] = row
    Ed = {}
    for name, spec in model["environment"]["presets"].items():
        if spec["type"] == "point":
            continue
        r = substream(seed, f"env:{name}")
        Ed[name] = np.array([spec["loc"] + spec["scale"] * r.student_t(spec["df"]) if spec["type"] == "t" else spec["mean"] + spec["sd"] * r.normal()
                             for _ in range(n)])
    k = 1 + u * (G - 1)
    lean = m24 + psi * rel26 + phi * (rel24 - rel20)
    a = lean[None, :] + eps
    theta = -a / k[None, :]
    need = model["national"]["ev_win"]
    tRaw = np.empty(n)
    for j in range(n):
        order = sorted(range(Un), key=lambda s: theta[j, s])  # stable, like insertion sort
        cum = 0.0
        tRaw[j] = np.inf
        for s in order:
            cum += ev[s]
            if cum >= need:
                tRaw[j] = theta[j, s]
                break
    return {"theta": theta, "tRaw": tRaw, "t_sorted": np.sort(tRaw), "Edraws": Ed, "ev": ev}
