// Small numeric helpers shared by the engine. No dependencies.

/** Number of elements of sorted array `arr` strictly less than x. */
export function countLess(arr, x) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Number of elements of sorted array `arr` less than or equal to x. */
export function countLessEq(arr, x) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Sorted Float64 copy. */
export function sortedCopy(arr) {
  const out = Float64Array.from(arr);
  out.sort();
  return out;
}

/** Quantile (type 7, linear interpolation) of an already-sorted array. */
export function quantileSorted(sorted, q) {
  const n = sorted.length;
  if (n === 0) return NaN;
  if (n === 1) return sorted[0];
  const h = (n - 1) * q;
  const lo = Math.floor(h);
  const hi = Math.min(n - 1, lo + 1);
  return sorted[lo] + (h - lo) * (sorted[hi] - sorted[lo]);
}

/** [median, q10, q90] of an unsorted array. */
export function medLoHi(arr, lo = 0.1, hi = 0.9) {
  const s = sortedCopy(arr);
  return [quantileSorted(s, 0.5), quantileSorted(s, lo), quantileSorted(s, hi)];
}

export function mean(arr) {
  let s = 0;
  for (let i = 0; i < arr.length; i++) s += arr[i];
  return arr.length ? s / arr.length : NaN;
}

export function sd(arr) {
  const m = mean(arr);
  let s = 0;
  for (let i = 0; i < arr.length; i++) s += (arr[i] - m) ** 2;
  return arr.length > 1 ? Math.sqrt(s / (arr.length - 1)) : 0;
}

export function median(arr) {
  return quantileSorted(sortedCopy(arr), 0.5);
}

export function now() {
  return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now();
}

/** Round to the nearest 5-point bin, as a probability (0.05 steps). */
export function bin5(p) {
  return Math.round(p * 20) / 20;
}

export function round(x, digits = 0) {
  const f = 10 ** digits;
  return Math.round(x * f) / f;
}

/**
 * Exact O(1)-expected "count of sorted t strictly below x" via a bucket index.
 * Same answers as countLess(t, x), without binary-search branch misses.
 */
export class EcdfIndex {
  constructor(sorted) {
    const n = sorted.length;
    this.t = sorted;
    this.n = n;
    this.t0 = sorted[0];
    this.t1 = sorted[n - 1];
    this.nb = Math.max(1, 2 * n);
    const span = this.t1 - this.t0;
    this.h = span > 0 && Number.isFinite(span) ? span / this.nb : 1;
    const idx = new Int32Array(this.nb + 1);
    let i = 0;
    for (let k = 0; k <= this.nb; k++) {
      const thr = this.t0 + k * this.h;
      while (i < n && sorted[i] < thr) i++;
      idx[k] = i;
    }
    this.idx = idx;
  }

  countLess(x) {
    if (!(x > this.t0)) return 0;
    if (x > this.t1) return this.n;
    let k = Math.floor((x - this.t0) / this.h);
    if (k > this.nb) k = this.nb;
    if (this.t0 + k * this.h > x) k--; // guard against rounding: bucket start must be ≤ x
    const t = this.t;
    let i = this.idx[k];
    while (i < this.n && t[i] < x) i++;
    return i;
  }
}

/** Sort small non-negative integer keys in place (LSD radix, 2 × 8 bits, keys < 65536). */
export function sortIntKeys(keys, tmp = new Int32Array(keys.length)) {
  const n = keys.length;
  const cnt = new Int32Array(256);
  let src = keys, dst = tmp;
  for (let shift = 0; shift < 16; shift += 8) {
    cnt.fill(0);
    for (let i = 0; i < n; i++) cnt[(src[i] >> shift) & 255]++;
    let sum = 0;
    for (let b = 0; b < 256; b++) { const c = cnt[b]; cnt[b] = sum; sum += c; }
    for (let i = 0; i < n; i++) dst[cnt[(src[i] >> shift) & 255]++] = src[i];
    const t = src; src = dst; dst = t;
  }
  return src; // after two passes the sorted data is back in `keys`
}
