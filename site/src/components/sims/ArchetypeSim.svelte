<script>
  // Sim 1 (METHODOLOGY §6.5 simArchetypes / archetypeCurves, §6.6 Sim 1).
  //   mode 'environment': P(win) vs national environment E, one curve per archetype; E slider
  //                       writes ctx.reader.env; tap/drag the chart to set it too.
  //   mode 'breakeven':   E* (coin-flip environment) per archetype with 80% intervals.
  //   mode 'run':         pick a lane → 10,000 simulated elections stack into an EV histogram.
  // Archetype colors only (no party colors) in 'environment' and 'breakeven'; the 'run'
  // histogram is party-colored (win/lose) and carries no archetype marks inside the chart.
  import { onDestroy, untrack } from 'svelte';
  import { scaleLinear } from 'd3-scale';
  import { line, area, curveMonotoneX } from 'd3-shape';
  import { timer } from 'd3-timer';
  import { ARCHETYPES, ARCHETYPE_BY_ID, shapePath } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import Slider from './Slider.svelte';
  import Segmented from './Segmented.svelte';
  import ArchChip from './ArchChip.svelte';
  import ArchWheel from './ArchWheel.svelte';
  import {
    fmtE, pct, pctRange, signed, fmtInt, params, envSlider, piOpt, envHistory, envPoint, envHistoryLabel, envChoices, envFor, envLabelFor, thinNote, lanes2028,
    defaultEnvCenter, priorOnly, unitName, latest, isStale, prefersReducedMotion, tokens, onSchemeChange,
    prng, histQuantile, clamp, c7Licensed,
  } from './shared.js';

  let { ctx, nodes, mode = 'environment' } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once

  const P = params(ctx0);
  const slider = envSlider(ctx0);
  const prior = priorOnly(ctx0);
  const c7 = c7Licensed(ctx0);
  // 2028 lanes (center populists left out when the estimates use past elections, O-9).
  const LANES = lanes2028(ctx0, ARCHETYPES);
  const ids = LANES.map((a) => a.id);
  // Win probabilities near the ends are not 0% or 100%: say so.
  const pctE = (p) => (p == null || !Number.isFinite(p) ? '–' : p >= 0.995 ? '>99%' : p < 0.005 ? '<1%' : pct(p));
  const article = (e) => (fmtE(e) === 'Even' ? 'an even' : fmtE(e).startsWith('R') ? `an ${fmtE(e)}` : `a ${fmtE(e)}`);

  if (ctx0.reader && ctx0.reader.env == null) ctx0.reader.env = defaultEnvCenter(ctx0);

  let error = $state('');
  let w = $state(0);
  let h = $state(0);

  // ================================================================ environment mode
  let curves = $state(null);
  let focus = $state(ctx0.reader?.guess ?? null);
  let hoverE = $state(null);

  const fetchCurves = latest(
    (pi) => ctx.simReady.then(() => ctx.sim.archetypeCurves({ pi, opponent: 'generic' }, {}, { channel: 'arch-curves' })),
    (r) => (curves = r),
    (e) => (error = e.message),
  );
  $effect(() => {
    if (mode !== 'environment') return;
    fetchCurves(piOpt(ctx.reader));
  });

  const M = $derived(w < 520 ? { l: 38, r: 12, t: 26, b: 40 } : { l: 46, r: 18, t: 28, b: 44 });
  const chartH = $derived(Math.max(220, h));
  const xE = $derived(scaleLinear().domain([slider.min, slider.max]).range([M.l, Math.max(M.l + 50, w - M.r)]));
  const yP = $derived(scaleLinear().domain([0, 1]).range([chartH - M.b, M.t]));
  const xTicks = $derived(xE.ticks(w < 520 ? 5 : 6).filter((v) => Number.isInteger(v)));

  function interp(arr, E) {
    if (!curves || !arr) return null;
    const Es = curves.E;
    if (E <= Es[0]) return arr[0];
    if (E >= Es[Es.length - 1]) return arr[arr.length - 1];
    const i = Es.findIndex((x) => x > E) - 1;
    const f = (E - Es[i]) / (Es[i + 1] - Es[i]);
    return arr[i] + f * (arr[i + 1] - arr[i]);
  }
  const inDomain = (E) => E >= slider.min - 1e-9 && E <= slider.max + 1e-9;
  const curvePath = (a, key = 'med') => {
    if (!curves) return '';
    const c = curves.byArchetype[a];
    const pts = curves.E.map((E, i) => [E, c[key][i]]).filter(([E]) => inDomain(E));
    return line().x((d) => xE(d[0])).y((d) => yP(d[1])).curve(curveMonotoneX)(pts);
  };
  const bandPath = (a) => {
    if (!curves) return '';
    const c = curves.byArchetype[a];
    const pts = curves.E.map((E, i) => [E, c.lo[i], c.hi[i]]).filter(([E]) => inDomain(E));
    return area().x((d) => xE(d[0])).y0((d) => yP(d[1])).y1((d) => yP(d[2])).curve(curveMonotoneX)(pts);
  };
  const atEnv = $derived(
    curves
      ? ids.map((a) => ({
          a,
          med: interp(curves.byArchetype[a].med, ctx.reader.env),
          lo: interp(curves.byArchetype[a].lo, ctx.reader.env),
          hi: interp(curves.byArchetype[a].hi, ctx.reader.env),
        }))
      : [],
  );
  const spread = $derived(atEnv.length ? [Math.min(...atEnv.map((d) => d.med)), Math.max(...atEnv.map((d) => d.med))] : null);
  /** Environment at which an archetype's median curve crosses 50%. */
  function e50(a) {
    if (!curves) return null;
    const m = curves.byArchetype[a].med;
    const Es = curves.E;
    for (let i = 1; i < Es.length; i++) {
      if (m[i] >= 0.5 && m[i - 1] < 0.5) return Es[i - 1] + ((0.5 - m[i - 1]) / (m[i] - m[i - 1])) * (Es[i] - Es[i - 1]);
    }
    return null;
  }
  // The lane furthest behind mainstream liberals at the coin-flip point, and by how much.
  const trailer = $derived.by(() => {
    if (!curves) return null;
    const ref = e50('mainstream_liberal');
    if (ref == null) return null;
    let worst = null;
    for (const a of ids) {
      if (a === 'mainstream_liberal') continue;
      const e = e50(a);
      if (e != null && (worst == null || e - ref > worst.gap)) worst = { a, gap: e - ref };
    }
    return worst;
  });
  const gapWords = (g) => {
    const r = Math.round(g);
    return r <= 1 ? 'about a point' : r === 2 ? 'a couple of points' : `about ${r} points`;
  };

  function eFromPointer(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const v = xE.invert(e.clientX - r.left);
    return clamp(Math.round(v / slider.step) * slider.step, slider.min, slider.max);
  }
  let dragging = false;
  function envDown(e) {
    dragging = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    ctx.reader.env = eFromPointer(e);
  }
  function envMove(e) {
    const v = eFromPointer(e);
    if (dragging) ctx.reader.env = v;
    if (e.pointerType === 'mouse') hoverE = v;
  }
  function envUp() {
    dragging = false;
  }

  // ================================================================ breakeven mode
  let be = $state(null);
  const fetchBE = latest(
    (pi) =>
      ctx.simReady.then(() =>
        ctx.sim.simArchetypes({ env: envHistory(ctx), pi, opponent: 'generic', map: false }, {}, { channel: 'arch-be' }),
      ),
    (r) => (be = r),
    (e) => (error = e.message),
  );
  // Break-even environments are the claims-ledger C5 numbers, which the pipeline computes
  // (10_validate.py headline()) with the transfer factor π sampled from its posterior draws,
  // a generic opponent and the default bank; a fixed π = 1 moves the ranges by a point.
  // So this view always uses sampled π, whatever the reader's π setting.
  $effect(() => {
    if (mode !== 'breakeven') return;
    fetchBE({ mode: 'sampled' });
  });
  const beNarrow = $derived(w < 560);
  const BM = $derived(beNarrow ? { l: 12, r: 16, t: 34, b: 40, row: 50 } : { l: 170, r: 150, t: 34, b: 44, row: 50 });
  const beDomain = $derived.by(() => {
    if (!be) return [-5, 10];
    const lo = Math.min(...ids.map((a) => be.byArchetype[a].Estar[1]));
    const hi = Math.max(...ids.map((a) => be.byArchetype[a].Estar[2]));
    const env = ctx.reader.env;
    const e24 = P.national?.E24 ?? 0;
    return [Math.floor(Math.min(lo - 2, env - 1, e24 - 1)), Math.ceil(Math.max(hi + 2, env + 1))];
  });
  const xB = $derived(scaleLinear().domain(beDomain).range([BM.l, Math.max(BM.l + 60, w - BM.r)]));
  const beH = $derived(BM.t + ids.length * BM.row + BM.b);
  const featured = $derived(ctx.reader.guess && ctx.reader.guess !== 'mainstream_liberal' ? ctx.reader.guess : 'progressive');

  // ================================================================ run mode
  let lane = $state(ids.includes(ctx0.reader?.guess) ? ctx0.reader.guess : 'mainstream_liberal');
  let runEnv = $state('default');
  let phase = $state('idle'); // idle | loading | running | done
  let run = $state(null); // { hist, runs, n, V, V80, dV, tipping, lane, envLabel }
  let shown = $state(0);
  let wins = $state(0);
  let canvas = $state(null);
  let stopTimer = null;
  const reduced = prefersReducedMotion();

  async function start() {
    error = '';
    stop();
    phase = 'loading';
    const env = envFor(ctx, runEnv, ctx.reader.env);
    try {
      await ctx.simReady;
      const r = await ctx.sim.simArchetypes(
        { env, pi: piOpt(ctx.reader), opponent: 'generic', archetypes: [lane], map: true },
        {},
        { channel: 'arch-run' },
      );
      const a = r.byArchetype[lane];
      const hist = a.evHist;
      let n = 0;
      for (let i = 0; i < hist.length; i++) n += hist[i];
      const runs = new Int16Array(n);
      let k = 0;
      for (let v = 0; v < hist.length; v++) for (let c = 0; c < hist[v]; c++) runs[k++] = v;
      const rnd = prng(P.meta?.seed ?? 7);
      for (let i = n - 1; i > 0; i--) {
        const j = Math.floor(rnd() * (i + 1));
        const t = runs[i];
        runs[i] = runs[j];
        runs[j] = t;
      }
      const tip = Object.entries(r.tipping ?? {}).sort((x, y) => y[1] - x[1]);
      run = {
        hist,
        runs,
        n,
        V: a.V,
        V80: a.V80,
        dV: a.dV,
        pTie: a.pTie,
        tipping: tip.slice(0, 3),
        lane,
        envLabel: envLabelFor(ctx, runEnv, ctx.reader.env),
        med: histQuantile(hist, 0.5),
        lo: histQuantile(hist, 0.1),
        hi: histQuantile(hist, 0.9),
      };
      shown = 0;
      wins = 0;
      phase = 'running';
      if (reduced) {
        finish();
      } else {
        const dur = 5200;
        const t = timer((el) => {
          const f = Math.min(1, el / dur);
          const target = Math.floor(run.n * Math.pow(f, 2.4));
          drawUpTo(target);
          if (f >= 1) finish();
        });
        stopTimer = () => t.stop();
      }
    } catch (e) {
      if (isStale(e)) return;
      error = e.message;
      phase = 'idle';
    }
  }
  function stop() {
    stopTimer?.();
    stopTimer = null;
  }
  function finish() {
    stop();
    if (run) drawUpTo(run.n);
    phase = 'done';
  }
  function reset() {
    stop();
    run = null;
    phase = 'idle';
    shown = 0;
    wins = 0;
    redraw();
  }
  onDestroy(stop);

  // layout of the dot histogram (depends on result + size)
  const RM = $derived({ l: 12, r: 12, t: 30, b: 36 });
  const layout = $derived.by(() => {
    if (!run || w < 50 || h < 50) return null;
    const W = w - RM.l - RM.r;
    const H = Math.max(80, h - RM.t - RM.b);
    let lo = histQuantile(run.hist, 0.003);
    let hi = histQuantile(run.hist, 0.997);
    lo = Math.min(lo, 250);
    hi = Math.max(hi, 290);
    let bw = 2;
    for (const c of [2, 5, 10, 20, 25, 50]) {
      bw = c;
      if ((hi - lo) / c <= W / 14) break;
    }
    const x0 = 270 - bw * Math.ceil((270 - lo) / bw);
    const x1 = 270 + bw * Math.ceil((hi + 1 - 270) / bw);
    const nb = Math.round((x1 - x0) / bw);
    const colW = W / nb;
    const counts = new Int32Array(nb);
    for (let v = 0; v < run.hist.length; v++) {
      if (!run.hist[v]) continue;
      counts[clamp(Math.floor((v - x0) / bw), 0, nb - 1)] += run.hist[v];
    }
    const maxC = Math.max(...counts);
    let pick = null;
    outer: for (const unit of [1, 2, 5, 10, 20, 50]) {
      for (let sq = 8; sq >= (unit === 50 ? 1 : 2.5); sq -= 0.5) {
        const perRow = Math.floor((colW - 1) / sq);
        if (perRow < 1) continue;
        const rows = Math.ceil(maxC / unit / perRow);
        if (rows * sq <= H) {
          pick = { unit, sq, perRow };
          break outer;
        }
      }
    }
    pick ??= { unit: 50, sq: 1, perRow: Math.max(1, Math.floor(colW - 1)) };
    const xEV = scaleLinear().domain([x0, x1]).range([RM.l, RM.l + W]);
    return { ...pick, x0, x1, bw, nb, colW, W, H, xEV, base: RM.t + H, counts };
  });
  let stack = null;
  let colors = null;

  function prepCanvas() {
    if (!canvas || !w || !h) return null;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const g = canvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    return g;
  }
  function redraw() {
    const g = prepCanvas();
    if (!g) return;
    g.clearRect(0, 0, w, h);
    colors = tokens(canvas, ['--dem', '--rep']);
    stack = layout ? new Int32Array(layout.nb) : null;
    const upTo = shown;
    shown = 0;
    wins = 0;
    if (run && layout) drawUpTo(upTo);
  }
  function drawUpTo(target) {
    if (!run || !layout) {
      shown = target;
      return;
    }
    const g = prepCanvas();
    if (!g) return;
    if (!stack || stack.length !== layout.nb) {
      g.clearRect(0, 0, w, h);
      stack = new Int32Array(layout.nb);
      shown = 0;
      wins = 0;
    }
    colors ??= tokens(canvas, ['--dem', '--rep']);
    const { x0, bw, nb, colW, sq, perRow, unit, xEV, base } = layout;
    const s = sq >= 4 ? sq - 1 : sq - 0.5;
    let wn = wins;
    for (let i = shown; i < target; i++) {
      const v = run.runs[i];
      if (v >= 270) wn++;
      const b = clamp(Math.floor((v - x0) / bw), 0, nb - 1);
      const c = stack[b]++;
      if (c % unit !== 0) continue;
      const k = c / unit;
      const col = k % perRow;
      const row = Math.floor(k / perRow);
      const left = xEV(x0 + b * bw) + (colW - perRow * sq) / 2 + col * sq;
      g.fillStyle = x0 + b * bw >= 270 ? colors['--dem'] : colors['--rep'];
      g.fillRect(left, base - (row + 1) * sq, s, s);
    }
    wins = wn;
    shown = Math.max(shown, target);
  }
  $effect(() => {
    if (mode !== 'run') return;
    // redraw on size/layout change
    void layout;
    void canvas;
    void w;
    void h;
    untrack(redraw);
  });
  $effect(() => {
    if (mode !== 'run') return;
    return onSchemeChange(() => {
      colors = null;
      redraw();
    });
  });
  // a lane or environment change invalidates the finished run
  $effect(() => {
    if (mode !== 'run') return;
    const l = lane;
    untrack(() => {
      if (run && run.lane !== l) reset();
    });
  });
  const evTicks = $derived(
    layout ? layout.xEV.ticks(w < 520 ? 4 : 8).filter((v) => v >= layout.x0 && v <= layout.x1 && Math.abs(v - 270) > (layout.x1 - layout.x0) * 0.06) : [],
  );
  const laneLabel = (a) => ARCHETYPE_BY_ID[a]?.label ?? a;
  const titles = {
    environment: 'How the national mood moves every lane',
    breakeven: 'The environment each lane needs to be a coin flip',
    run: 'Run the 2028 election 10,000 times',
  };
</script>

<SimFrame
  {ctx}
  title={titles[mode] ?? titles.environment}
  dek={mode === 'environment'
    ? 'Chance of winning the Electoral College for a generic Democrat of each type, by national popular-vote margin.'
    : mode === 'breakeven'
      ? 'National environment at which each type of Democrat is a 50–50 bet; lines show the 80% range.'
      : 'Each square is one simulated election. The pile shows how many electoral votes Democrats got across all of them.'}
>
  {#if mode === 'environment'}
    <div class="legend" role="group" aria-label="Highlight one type of Democrat">
      {#each LANES as a (a.id)}
        <button
          class="lg"
          aria-pressed={focus === a.id}
          onclick={() => (focus = focus === a.id ? null : a.id)}
        ><ArchChip id={a.id} short={w < 520} /></button>
      {/each}
    </div>
    <div class="chart" bind:clientWidth={w} bind:clientHeight={h}>
      {#if w > 0}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <svg
          width={w}
          height={chartH}
          role="img"
          aria-label={spread
            ? `Win-probability curves for five types of Democrat. At ${fmtE(ctx.reader.env, 1)} they range from ${pctE(spread[0])} to ${pctE(spread[1])}.`
            : 'Win-probability curves loading'}
          onpointerdown={envDown}
          onpointermove={envMove}
          onpointerup={envUp}
          onpointercancel={envUp}
          onpointerleave={() => (hoverE = null)}
          style="touch-action: pan-y"
        >
          {#each [0, 0.25, 0.5, 0.75, 1] as v (v)}
            <line class={v === 0.5 ? 'axis-line' : 'gridline'} x1={M.l} x2={w - M.r} y1={yP(v)} y2={yP(v)} />
            <text class="tick" x={M.l - 6} y={yP(v) + 4} text-anchor="end">{v * 100}%</text>
          {/each}
          <text class="lbl-2 halo" x={w - M.r} y={yP(0.5) - 5} text-anchor="end">Coin flip</text>
          {#each xTicks as v (v)}
            <text class="tick" x={xE(v)} y={chartH - M.b + 16} text-anchor="middle">{fmtE(v)}</text>
          {/each}
          <text class="axis-title" x={(M.l + w - M.r) / 2} y={chartH - 6} text-anchor="middle">
            National environment (Democratic popular-vote margin)
          </text>
          {#if curves}
            {#if focus}
              <path d={bandPath(focus)} style:fill="var({ARCHETYPE_BY_ID[focus].token})" opacity="0.16" />
            {/if}
            {#each LANES as a (a.id)}
              <path
                d={curvePath(a.id)}
                fill="none"
                style:stroke="var({a.token})"
                stroke-width={focus === a.id ? 3 : 2}
                opacity={focus && focus !== a.id ? 0.35 : 1}
              />
            {/each}
          {/if}
          <!-- reader's environment -->
          <line class="envline" x1={xE(ctx.reader.env)} x2={xE(ctx.reader.env)} y1={M.t - 6} y2={chartH - M.b} />
          <text
            class="lbl halo"
            x={clamp(xE(ctx.reader.env), M.l + 60, w - M.r - 60)}
            y={M.t - 12}
            text-anchor="middle"
            font-weight="600">Your environment: {fmtE(ctx.reader.env, 1)}</text
          >
          {#if curves}
            {#each atEnv as d (d.a)}
              <path
                transform="translate({xE(ctx.reader.env)},{yP(d.med)})"
                d={shapePath(ARCHETYPE_BY_ID[d.a].shape, 5)}
                style:fill="var({ARCHETYPE_BY_ID[d.a].token})"
                style:stroke="var(--bg)"
                stroke-width="1.5"
                opacity={focus && focus !== d.a ? 0.4 : 1}
              />
            {/each}
          {/if}
          {#if hoverE != null && curves && Math.abs(hoverE - ctx.reader.env) > 1e-9}
            <line class="hover" x1={xE(hoverE)} x2={xE(hoverE)} y1={M.t} y2={chartH - M.b} />
          {/if}
        </svg>
        {#if hoverE != null && curves && Math.abs(hoverE - ctx.reader.env) > 1e-9}
          <div class="tip" style:left="{clamp(xE(hoverE) + 10, 0, w - 200)}px" style:top="{M.t + 8}px">
            <b>At {fmtE(hoverE, 1)}</b> (click to set)<br />
            {#each LANES as a (a.id)}
              <span class="tiprow"><ArchChip id={a.id} short size={10} /> <span class="tabular">{pctE(interp(curves.byArchetype[a.id].med, hoverE))}</span></span>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
    <div class="controls">
      <Slider
        label="National environment in 2028"
        bind:value={ctx.reader.env}
        min={slider.min}
        max={slider.max}
        step={slider.step}
        format={(v) => fmtE(+v, 1)}
        ends={[fmtE(slider.min), fmtE(slider.max)]}
      />
    </div>
    {#if spread}
      <p class="big" role="status">
        At {fmtE(ctx.reader.env, 1)}, the five types' chances run from <b>{pctE(spread[0])}</b> to <b>{pctE(spread[1])}</b>.
        {#if c7}
          How good a year 2028 is moves every lane far more than lane choice does{#if trailer && trailer.gap >= 0.5}; the
            {laneLabel(trailer.a).toLowerCase()} lane trails by {gapWords(trailer.gap)}{/if}.
        {/if}
      </p>
    {/if}
    {#if error}<p class="error">Simulation error: {error}</p>{/if}
  {:else if mode === 'breakeven'}
    <div class="chart be" bind:clientWidth={w} style:height="{beH}px">
      {#if w > 0 && be}
        <svg width={w} height={beH} role="img" aria-label="Break-even environment for each type of Democrat with 80% ranges">
          {#each xB.ticks(beNarrow ? 5 : 8).filter(Number.isInteger) as v (v)}
            <line class="gridline" x1={xB(v)} x2={xB(v)} y1={BM.t} y2={beH - BM.b} />
            <text class="tick" x={xB(v)} y={beH - BM.b + 16} text-anchor="middle">{fmtE(v)}</text>
          {/each}
          <text class="axis-title" x={(BM.l + w - BM.r) / 2} y={beH - 6} text-anchor="middle">Environment needed for a 50% chance</text>
          <!-- references -->
          {#if P.national?.E24 != null}
            <line class="ref" x1={xB(P.national.E24)} x2={xB(P.national.E24)} y1={BM.t - 4} y2={beH - BM.b} />
            <text class="lbl-2 halo" x={xB(P.national.E24) - 4} y={BM.t - 8} text-anchor="end">2024: {fmtE(P.national.E24, 1)}</text>
          {/if}
          <line class="envline" x1={xB(ctx.reader.env)} x2={xB(ctx.reader.env)} y1={BM.t - 4} y2={beH - BM.b} />
          <text class="lbl halo" x={xB(ctx.reader.env) + 4} y={BM.t - 8} font-weight="600">Yours: {fmtE(ctx.reader.env, 1)}</text>
          {#each LANES as a, i (a.id)}
            {@const es = be.byArchetype[a.id].Estar}
            {@const cy = BM.t + i * BM.row + (beNarrow ? BM.row - 16 : BM.row / 2)}
            {#if beNarrow}
              <foreignObject x={BM.l} y={cy - 31} width={w - BM.l - BM.r} height="22">
                <div class="rowlab"><ArchChip id={a.id} /> <span class="tabular est">{fmtE(es[0])} ({fmtE(es[1])} to {fmtE(es[2])})</span></div>
              </foreignObject>
            {:else}
              <foreignObject x="0" y={cy - 11} width={BM.l - 14} height="22">
                <div class="rowlab right"><ArchChip id={a.id} /></div>
              </foreignObject>
              <text class="lbl tabular halo" x={xB(es[2]) + 10} y={cy + 4}>{fmtE(es[0])} <tspan class="lbl-2">({fmtE(es[1])} to {fmtE(es[2])})</tspan></text>
            {/if}
            <line x1={xB(es[1])} x2={xB(es[2])} y1={cy} y2={cy} style:stroke="var({a.token})" stroke-width="2.5" stroke-linecap="round" />
            <path
              transform="translate({xB(es[0])},{cy})"
              d={shapePath(a.shape, 6.5)}
              style:fill="var({a.token})"
              style:stroke="var(--bg)"
              stroke-width="2"
            />
          {/each}
        </svg>
      {:else if !error}
        <p class="note">Simulating…</p>
      {/if}
    </div>
    {#if be}
      {@const f = be.byArchetype[featured].Estar}
      {@const ml = be.byArchetype.mainstream_liberal.Estar}
      <p class="big">
        A {laneLabel(featured).toLowerCase()} Democrat needs roughly {article(f[0])} national environment to be a coin flip
        (range {fmtE(f[1])} to {fmtE(f[2])}); a mainstream liberal needs {fmtE(ml[0])}.
      </p>
      <p class="note">{['history', 'blend'].includes(P.style?.default_preset) ? 'Lane effects blend 2026 House races with competitive House races in 2018 and 2022, read at an even national mood' : 'Lane effects come from 2026 House races'}, and carry over to a presidential race at a reduced, uncertain rate (presidential years have shown about half the midterm gap). Center populists are left out: too few ran in any year. Whole points only: the differences are smaller than the ranges.</p>
    {/if}
    {#if error}<p class="error">Simulation error: {error}</p>{/if}
  {:else}
    <div class="runbar">
      <ArchWheel bind:value={lane} ids={ids} />
    </div>
    <div class="runbar">
      <Segmented
        label="National mood"
        options={envChoices(ctx, ctx.reader.env, w > 0 && w < 560)}
        bind:value={runEnv}
        onchange={() => run && reset()}
        small
      />
      {#if phase === 'running'}
        <button class="btn ghost" onclick={finish}>Skip animation</button>
      {:else}
        <button class="btn" onclick={start} disabled={phase === 'loading'}>
          {phase === 'done' ? 'Run again' : phase === 'loading' ? 'Simulating…' : 'Start simulation'}
        </button>
      {/if}
    </div>
    <p class="counter tabular" aria-hidden="true">
      {#if run}
        Runs: <b>{fmtInt(shown)}</b> / {fmtInt(run.n)} · Democrat wins <b>{fmtInt(wins)}</b>
        {#if shown}({pct(wins / shown)}){/if}
      {:else}
        Pick a type, then start: {fmtInt(10000)} elections.
      {/if}
    </p>
    <div class="chart run" bind:clientWidth={w} bind:clientHeight={h}>
      <canvas bind:this={canvas} style:width="{w}px" style:height="{h}px" aria-hidden="true"></canvas>
      {#if w > 0 && h > 0}
        <svg class="overlay" width={w} height={h} role="img" aria-label={run && phase === 'done'
          ? `Histogram of ${fmtInt(run.n)} simulated Electoral College results for a ${laneLabel(run.lane).toLowerCase()} Democrat: median ${run.med} electoral votes, 80% between ${run.lo} and ${run.hi}; Democrat wins ${pct(run.V)} of runs.`
          : 'Electoral-vote histogram, not yet run'}>
          {#if layout}
            <line class="axis-line" x1={RM.l} x2={w - RM.r} y1={layout.base + 0.5} y2={layout.base + 0.5} />
            {#each evTicks as v (v)}
              <text class="tick" x={layout.xEV(v)} y={layout.base + 16} text-anchor="middle">{v}</text>
            {/each}
            <line class="win" x1={layout.xEV(270)} x2={layout.xEV(270)} y1={RM.t - 8} y2={layout.base + 4} />
            <text class="lbl halo" x={layout.xEV(270)} y={RM.t - 12} text-anchor="middle" font-weight="600">270 to win</text>
            <text class="lbl-2 halo" x={layout.xEV(270) - 8} y={RM.t + 8} text-anchor="end">← Republican wins</text>
            <text class="lbl-2 halo" x={layout.xEV(270) + 8} y={RM.t + 8}>Democrat wins →</text>
            <text class="axis-title" x={w / 2} y={h - 4} text-anchor="middle">Democratic electoral votes{layout.unit > 1 ? ` · one square = ${layout.unit} runs` : ''}</text>
          {:else}
            <line class="axis-line" x1={RM.l} x2={w - RM.r} y1={h - RM.b} y2={h - RM.b} />
            <text class="axis-title" x={w / 2} y={h - 4} text-anchor="middle">Democratic electoral votes</text>
          {/if}
        </svg>
      {/if}
    </div>
    <!-- The result's space is held from the start (a hidden sample of the same text sits in the
         same grid cell), so the chart doesn't shrink when the run ends; the text fades in. -->
    <div role="status" class="result">
      <div class="layer sizer" aria-hidden="true">
        <p class="big">
          With a left populist nominee and an unknown national mood, Democrats win <b>57%</b> of the runs.
          In a typical run they get about <b>285</b> electoral votes; most runs land between 200 and 360.
          The state most likely to decide it: <b>Pennsylvania</b>, then Michigan.
        </p>
        <p class="note">That's about +7 points better than a mainstream liberal (could be anywhere from 0 to +17). Not a forecast.</p>
        <p class="note">Left populists rest on only 14 races from 2026, so their number comes mostly from the model's overall pattern, not their own results. Treat it as a rough guess.</p>
      </div>
      <div class="layer real" class:shown={run && phase === 'done'}>
        {#if run && phase === 'done'}
          <p class="big">
            With a {laneLabel(run.lane).toLowerCase()} nominee and {run.envLabel}, Democrats win <b>{pct(run.V)}</b> of the runs.
            In a typical run they get about <b>{run.med}</b> electoral votes; most runs land between {run.lo} and {run.hi}.
            {#if run.tipping.length}
              The state most likely to decide it: <b>{unitName(ctx, run.tipping[0][0])}</b>{run.tipping[1] ? `, then ${unitName(ctx, run.tipping[1][0])}` : ''}.
            {/if}
          </p>
          {#if run.lane !== 'mainstream_liberal'}
            <p class="note">
              That's about {signed(run.dV[0] * 100, 0)} points {run.dV[0] >= 0 ? 'better' : 'worse'} than a mainstream liberal (could be anywhere from {signed(run.dV[1] * 100, 0)} to {signed(run.dV[2] * 100, 0)}). Not a forecast.
            </p>
          {:else}
            <p class="note">Mainstream liberals are the yardstick the other types are compared with. Not a forecast.</p>
          {/if}
          {#if thinNote(ctx, run.lane)}<p class="note">{thinNote(ctx, run.lane)}</p>{/if}
        {/if}
      </div>
    </div>
    {#if error}<p class="error">Simulation error: {error}</p>{/if}
  {/if}

  {#snippet table()}
    {#if mode === 'environment'}
      {#if curves}
        <table class="data">
          <caption>Chance of winning the Electoral College (median across model draws)</caption>
          <thead><tr><th scope="col">Environment</th>{#each LANES as a (a.id)}<th scope="col">{a.label}</th>{/each}</tr></thead>
          <tbody>
            {#each curves.E.filter((E) => inDomain(E) && E % 2 === 0) as E (E)}
              <tr>
                <th scope="row">{fmtE(E)}</th>
                {#each LANES as a (a.id)}<td>{pctE(interp(curves.byArchetype[a.id].med, E))}</td>{/each}
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    {:else if mode === 'breakeven'}
      {#if be}
        <table class="data">
          <caption>Environment needed for a 50% chance</caption>
          <thead><tr><th scope="col">Type</th><th scope="col">Median</th><th scope="col">80% range</th><th scope="col">P(win), default range</th></tr></thead>
          <tbody>
            {#each LANES as a (a.id)}
              {@const r = be.byArchetype[a.id]}
              <tr><th scope="row">{a.label}</th><td>{fmtE(r.Estar[0])}</td><td>{fmtE(r.Estar[1])} to {fmtE(r.Estar[2])}</td><td>{pct(r.V)} ({pctRange(r.V80)})</td></tr>
            {/each}
          </tbody>
        </table>
      {/if}
    {:else if run && layout}
      <table class="data">
        <caption>{fmtInt(run.n)} simulated elections, {laneLabel(run.lane).toLowerCase()} nominee</caption>
        <thead><tr><th scope="col">Democratic electoral votes</th><th scope="col">Runs</th><th scope="col">Share</th></tr></thead>
        <tbody>
          {#each Array.from(layout.counts) as c, b (b)}
            {#if c > 0}
              <tr><th scope="row">{layout.x0 + b * layout.bw}–{layout.x0 + (b + 1) * layout.bw - 1}</th><td>{fmtInt(c)}</td><td>{(c / run.n * 100).toFixed(1)}%</td></tr>
            {/if}
          {/each}
        </tbody>
      </table>
    {:else}
      <p class="note">Run the simulation to fill this table.</p>
    {/if}
  {/snippet}

  {#snippet notes()}
    {#if prior}
      <p>Style effects here come from the prior while the 2026 fit is under review, so differences between lanes are mostly noise.</p>
    {/if}
    {#if mode !== 'run'}<p>Generic Republican opponent; lane effects carried to a presidential race at an uncertain rate.</p>{/if}
  {/snippet}
</SimFrame>

<style>
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 4px;
    margin: 0 -6px;
  }
  .lg {
    min-height: 36px;
    padding: 0 8px;
    border: 1px solid transparent;
    border-radius: 999px;
    background: none;
    color: var(--ink);
    font: 500 12.5px/1 var(--font-ui);
    cursor: pointer;
  }
  .lg[aria-pressed='true'] {
    border-color: var(--axis);
    background: var(--surface-2);
    font-weight: 600;
  }
  @media (pointer: coarse) {
    .lg {
      min-height: 44px;
    }
  }
  .chart {
    position: relative;
    flex: 1 1 auto;
    min-height: 220px;
  }
  .chart.run {
    min-height: 200px;
  }
  @media (max-width: 760px) {
    /* phones: keep the curves readable and let the stage scroll for the rest */
    .chart {
      min-height: 240px;
    }
    .chart.run {
      min-height: 220px;
    }
    .lg {
      min-height: 36px;
    }
  }
  .chart svg {
    position: absolute;
    inset: 0;
    display: block;
    overflow: visible;
  }
  canvas {
    position: absolute;
    inset: 0;
    display: block;
  }
  .overlay {
    pointer-events: none;
  }
  .envline {
    stroke: var(--ink);
    stroke-width: 1.5;
  }
  .hover {
    stroke: var(--ink-2);
    stroke-width: 1;
    stroke-dasharray: 3 3;
  }
  .ref {
    stroke: var(--muted);
    stroke-width: 1;
    stroke-dasharray: 2 3;
  }
  .win {
    stroke: var(--ink);
    stroke-width: 1.5;
  }
  .tip {
    display: grid;
    gap: 2px;
  }
  .tiprow {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .rowlab {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 22px;
    font: 500 12.5px/1 var(--font-ui);
    color: var(--ink);
  }
  .rowlab > :global(*) {
    background: var(--bg);
    padding: 0 3px;
    border-radius: 3px;
  }
  .chart.be {
    flex: none;
    min-height: 0;
  }
  .rowlab.right {
    justify-content: flex-end;
  }
  .est {
    color: var(--ink-2);
  }
  .runbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
  }
  .counter {
    margin: 0;
    font-size: 13px;
    color: var(--ink-2);
    min-height: 1.4em;
    /* one line always, so the chart below doesn't move when a run starts */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result {
    display: grid;
  }
  .result .layer {
    grid-area: 1 / 1;
    min-width: 0;
  }
  .result .sizer {
    visibility: hidden;
  }
  .result .real {
    opacity: 0;
    transition: opacity 0.5s var(--ease);
  }
  .result .real.shown {
    opacity: 1;
  }
  .result p + p {
    margin-top: 4px;
  }
  .result :global(p) {
    margin: 0;
  }
  p.big {
    margin: 0;
  }
</style>
