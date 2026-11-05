<script>
  // Sim 2 (METHODOLOGY §6.5 simMatchups / matchupDetail, §6.6 Sim 2; claim C12).
  // Democratic contenders (rows) × Republican contenders (columns) from model params, ordered
  // by betting-market nomination odds. Cells show P(Democrat wins) in 5-point bins with the
  // indistinguishability banner; a cell opens the pairing's tile map and tipping point.
  import { tick, untrack } from 'svelte';
  import { ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import { simSource } from '../story/sources.js';
  import Segmented from './Segmented.svelte';
  import TileMap from './TileMap.svelte';
  import {
    fmtE, pct, pctRange, signed, params, piOpt, envHistory, envPoint, envChoices, envFor, defaultEnvCenter, unitName, lastName,
    latest, isStale,
  } from './shared.js';

  let { ctx, nodes } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once

  const P = params(ctx0);
  if (ctx0.reader && ctx0.reader.env == null) ctx0.reader.env = defaultEnvCenter(ctx0);
  const byMarket = (a, b) => (b.market_nom ?? 0) - (a.market_nom ?? 0);
  const dems = (P.candidates_dem ?? []).filter((c) => c.include_default !== false).sort(byMarket);
  const gopsAll = (P.candidates_gop ?? []).filter((c) => c.include_default !== false).sort(byMarket);

  let envMode = $state('default');
  // Every Republican, every Democrat: one full grid that scrolls sideways, names pinned left.
  const gops = gopsAll;

  let cells = $state(new Map()); // `${dem}|${gop}` → cell
  let indist = $state(null);
  let loading = $state(true);
  let error = $state('');

  const go = latest(
    (o) =>
      ctx.simReady.then(() =>
        ctx.sim.simMatchups(o, {}, {
          channel: 'matrix',
          onProgress: (pr) => {
            const m = new Map(cells);
            for (const c of pr.cells) m.set(`${c.dem}|${c.gop}`, c);
            cells = m;
          },
        }),
      ),
    (r) => {
      cells = new Map(r.cells.map((c) => [`${c.dem}|${c.gop}`, c]));
      indist = r.indistinguishable;
      loading = false;
    },
    (e) => {
      error = e.message;
      loading = false;
    },
  );
  const env = $derived(envFor(ctx, envMode, ctx.reader.env));
  $effect(() => {
    loading = true;
    go({ dems: dems.map((d) => d.id), gops: gops.map((g) => g.id), env, pi: piOpt(ctx.reader) });
  });

  // 5-point bins, party diverging fill (capped so ink text stays readable)
  function cellFill(p) {
    if (p == null) return 'var(--surface-2)';
    const d = p - 0.5;
    const amt = Math.min(80, Math.round((Math.abs(d) / 0.5) * 100));
    if (amt === 0) return 'var(--mid)';
    return `color-mix(in oklab, var(${d > 0 ? '--dem' : '--rep'}) ${amt}%, var(--mid))`;
  }
  const oppLabel = (g) => (/maga/i.test(g.opp_type ?? '') ? 'MAGA' : 'Traditional');
  const archLabel = (id) => ARCHETYPE_BY_ID[id]?.label ?? id;
  const threshold = $derived(indist ? Math.max(1, Math.round(indist.thresholdPts)) : null);
  const nPairs = $derived(dems.length * (gops.length - 1) + (dems.length - 1) * gops.length);

  // ---------------------------------------------------------------- detail
  let sel = $state(null); // { dem, gop }
  let detail = $state(null);
  let detailErr = $state('');
  let lastBtn = null;
  let panel = $state(null);

  async function open(dem, gop, e) {
    lastBtn = e?.currentTarget ?? null;
    sel = { dem, gop };
    detail = null;
    detailErr = '';
    await tick();
    panel?.focus();
    try {
      await ctx.simReady;
      detail = await ctx.sim.matchupDetail(dem.id, gop.id, { env, pi: piOpt(ctx.reader) }, {}, { channel: 'matrix-detail' });
    } catch (err) {
      if (!isStale(err)) detailErr = err.message;
    }
  }
  async function close() {
    sel = null;
    detail = null;
    await tick();
    lastBtn?.focus();
  }
  const tipTop = $derived(detail ? Object.entries(detail.tipping ?? {}).sort((a, b) => b[1] - a[1]) : []);
  const decompRows = $derived(
    detail
      ? [
          ['National mood', detail.decomposition.env],
          ['Electoral College map', detail.decomposition.lean],
          ['Democrat’s lane', detail.decomposition.style],
          ['Republican type', detail.decomposition.opponent],
          ['Track records', detail.decomposition.personal],
          ['Home states', detail.decomposition.home],
        ]
      : [],
  );
  let w = $state(0);
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && sel && close()} />

<SimFrame
  {ctx}
  title="Every pairing, under one set of assumptions"
  source={simSource(ctx, "candidates' past results (Wikipedia, checked against official results)")}
  dek="Chance the Democrat wins the Electoral College, in 5-point steps. Tap a cell for its map."
  banner={bannerSnip}
>
  <div class="bar" bind:clientWidth={w}>
    <Segmented
      label="National mood"
      options={envChoices(ctx, ctx.reader.env, w < 520)}
      bind:value={envMode}
      small
    />
  </div>

  <div class="scroller" aria-busy={loading}>
    <table class="matrix">
      <caption class="sr-only">Chance the Democrat wins, by pairing, in 5-point steps</caption>
      <thead>
        <tr>
          <th class="corner" scope="col"><span>Democrat ↓</span><span>Republican →</span></th>
          {#each gops as g (g.id)}
            <th scope="col" class="gh" title={g.name}><span class="nm">{lastName(g.name)}</span><span class="sub">{oppLabel(g)}</span></th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each dems as d (d.id)}
          <tr>
            <th scope="row" class="dh" title={d.name}><span class="nm full">{d.name}</span><span class="nm short">{lastName(d.name)}</span><span class="sub">{archLabel(d.archetype)}</span></th>
            {#each gops as g (g.id)}
              {@const c = cells.get(`${d.id}|${g.id}`)}
              <td>
                <button
                  class="cell"
                  style:background={cellFill(c?.pWinBinned)}
                  aria-label={c ? `${d.name} vs ${g.name}: about ${pct(c.pWinBinned)} for the Democrat. Open map.` : `${d.name} vs ${g.name}: computing`}
                  onclick={(e) => open(d, g, e)}
                  disabled={!c}
                ><span class="tabular">{c ? pct(c.pWinBinned) : '·'}</span></button>
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="legend" aria-hidden="true">
    <span>Democrat's chance</span>
    {#each [0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9] as v (v)}<i style:background={cellFill(v)}><b>{pct(v)}</b></i>{/each}
  </div>
  <p class="note">Under these assumptions; not a forecast of any person's chances. Rows and columns are ordered by betting-market nomination odds.</p>
  {#if error}<p class="error">Simulation error: {error}</p>{/if}

  {#if sel}
    <div class="detail" role="dialog" aria-modal="true" aria-labelledby="mm-detail-title" tabindex="-1" bind:this={panel}>
      <div class="dhead">
        <button class="btn ghost back" onclick={close}>← Back to all pairings</button>
        <h3 id="mm-detail-title">{sel.dem.name} vs {sel.gop.name}</h3>
      </div>
      {#if detail}
        <p class="big">
          The Democrat wins about <b>{pct(Math.round(detail.V * 20) / 20)}</b> of the simulated elections.
          To make it a coin flip, the national vote would need to be about {fmtE(detail.Estar[0])}.
          {#if tipTop.length}The state most likely to decide it: <b>{unitName(ctx, tipTop[0][0])}</b>.{/if}
        </p>
        <div class="dgrid">
          <TileMap
            {ctx}
            values={detail.stateP}
            kind="prob"
            highlight={tipTop[0]?.[0] ?? null}
            highlightLabel="Likeliest tipping point"
            label={`Map of each state's chance for ${sel.dem.name} against ${sel.gop.name}`}
            maxHeight={300}
          />
          <table class="data decomp">
            <caption>What moved this pairing, in points of margin in the deciding state (+ helps the Democrat)</caption>
            <tbody>
              {#each decompRows as [k, v] (k)}
                <tr><th scope="row">{k}</th><td>{signed(v, 1)}</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
        <p class="note">{sel.dem.name}: {archLabel(sel.dem.archetype).toLowerCase()}{sel.dem.home ? `, home state ${sel.dem.home}` : ''}. {sel.gop.name}: {oppLabel(sel.gop).toLowerCase()} Republican{sel.gop.home ? `, home state ${sel.gop.home}` : ''}.</p>
      {:else if detailErr}
        <p class="error">Simulation error: {detailErr}</p>
      {:else}
        <p class="note">Simulating this pairing…</p>
      {/if}
    </div>
  {/if}

  {#snippet table()}
    <table class="data">
      <caption>Chance the Democrat wins (5-point steps)</caption>
      <thead><tr><th scope="col">Democrat</th><th scope="col">Republican</th><th scope="col">Chance</th><th scope="col">80% range</th></tr></thead>
      <tbody>
        {#each dems as d (d.id)}
          {#each gops as g (g.id)}
            {@const c = cells.get(`${d.id}|${g.id}`)}
            <tr><th scope="row">{d.name}</th><td>{g.name}</td><td>{c ? pct(c.pWinBinned) : '…'}</td><td>{c ? pctRange(c.pWin80) : ''}</td></tr>
          {/each}
        {/each}
      </tbody>
    </table>
  {/snippet}
</SimFrame>

{#snippet bannerSnip()}
  {#if indist && indist.pairs.length}
    <p class="warn" role="status">
      Cells within about <b>{threshold} points</b> of each other are too close to call. Read the colors as rough bands, not a ranking.
    </p>
  {/if}
{/snippet}

<style>
  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
  }
  .scroller {
    overflow: auto;
    max-width: 100%;
    flex: 0 1 auto;
    min-height: 0;
    -webkit-overflow-scrolling: touch;
  }
  .matrix {
    border-collapse: separate;
    border-spacing: 2px;
    font-size: 12.5px;
  }
  .matrix th {
    font-weight: 500;
    color: var(--ink);
    background: var(--bg);
  }
  .corner {
    position: sticky;
    left: 0;
    top: 0;
    z-index: 3;
    text-align: left;
    vertical-align: bottom;
    font-size: 11px;
    color: var(--muted) !important;
    padding: 0 6px 4px 0;
  }
  .corner span {
    display: block;
    font-weight: 500;
  }
  .gh {
    position: sticky;
    top: 0;
    z-index: 2;
    vertical-align: bottom;
    padding: 0 2px 4px;
    min-width: 52px;
  }
  .dh {
    position: sticky;
    left: 0;
    z-index: 1;
    text-align: left;
    padding: 0 8px 0 0;
    max-width: 150px;
  }
  .nm,
  .sub {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .gh .nm {
    font-weight: 600;
  }
  .sub {
    font-size: 10.5px;
    color: var(--muted);
  }
  td {
    padding: 0;
  }
  .short {
    display: none;
  }
  @container (max-width: 520px) {
    .dh .full {
      display: none;
    }
    .dh .short {
      display: block;
    }
    .dh {
      max-width: 84px;
    }
    .cell,
    .gh {
      min-width: 42px;
    }
    .cell {
      font-size: 11.5px;
    }
  }
  .cell {
    display: grid;
    place-items: center;
    width: 100%;
    min-width: 52px;
    height: 34px;
    border: 0;
    border-radius: 4px;
    color: var(--ink);
    font: 600 12.5px var(--font-ui);
    cursor: pointer;
  }
  @media (pointer: coarse) {
    .cell {
      height: 44px;
    }
  }
  .cell:hover {
    box-shadow: inset 0 0 0 2px var(--ink);
  }
  .cell:disabled {
    cursor: progress;
    color: var(--muted);
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 3px;
    font-size: 11px;
    color: var(--ink-2);
  }
  .legend span {
    margin-right: 6px;
  }
  .legend i {
    display: inline-grid;
    place-items: center;
    min-width: 36px;
    height: 18px;
    border-radius: 3px;
    font-style: normal;
  }
  .legend b {
    font-weight: 600;
    color: var(--ink);
    font-size: 10.5px;
  }
  .detail {
    position: absolute;
    inset: -4px;
    z-index: 10;
    overflow: auto;
    background: var(--bg);
    display: flex;
    flex-direction: column;
    gap: 10px;
    outline: none;
  }
  .dhead {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 14px;
  }
  .back {
    padding: 0 12px;
  }
  h3 {
    margin: 0;
    font-size: 16px;
  }
  .dgrid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 16px;
    align-items: start;
  }
  .decomp {
    min-width: 0 !important;
  }
  @container (max-width: 700px) {
    .dgrid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
