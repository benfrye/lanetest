<script>
  import { untrack } from 'svelte';
  // Sim 5 (METHODOLOGY §6.5 sim5, §6.6 Sim 5; claim C14): the 2026 House vote as an
  // electoral tile map. Two views: raw (as it happened) and durable (the same 2026 state
  // leans with the national vote reset to the default environment, an even vote). EV totals,
  // the "translation, not a forecast" banner, and the states that change between the two.
  import SimFrame from './SimFrame.svelte';
  import Segmented from './Segmented.svelte';
  import TileMap from './TileMap.svelte';
  import { fmtE, signed, params, defaultEnvCenter, unitList, unitName, latest } from './shared.js';

  let { ctx, nodes, view: view0 = 'raw' } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once
  const init = untrack(() => ({ view0 }));

  const P = params(ctx0);
  const s5 = P.sim5 ?? {};
  const units = unitList(ctx0);
  const evOf = Object.fromEntries(units.map((u) => [u.id, u.ev]));
  const Ecenter = defaultEnvCenter(ctx0);
  const nat = s5.national_house26;
  const VIEWS = ['raw', 'durable'];
  const evenYear = Math.abs(Ecenter) < 0.05 ? 'an even year' : `a ${fmtE(Ecenter)} year`;
  const viewLabel = {
    raw: `As it happened (${fmtE(nat)})`,
    durable: `In ${evenYear}`,
  };
  const shortLabel = { raw: 'As it happened', durable: Math.abs(Ecenter) < 0.05 ? 'Even year' : fmtE(Ecenter) };
  let bw = $state(0);

  // hatching: units still counting / imputed (flag precomputed in params; districts roll up)
  const hatched = new Set();
  for (const r of s5.units ?? []) if (r.hatched) hatched.add(r.id);
  for (const u of units) if (u.parent && hatched.has(u.id)) hatched.add(u.parent);

  let view = $state(VIEWS.includes(init.view0) ? init.view0 : 'raw');
  let res = $state({}); // view → result
  let error = $state('');

  const pointEV = (r) => {
    let d = 0;
    for (const x of r.units) if (x.margin > 0) d += evOf[x.id] ?? 0;
    return d;
  };

  // both views once (cheap), so the states that change between them can be listed
  $effect(() => {
    ctx.simReady
      .then(() => Promise.all(['durable', 'raw'].map((v) => ctx.sim.sim5({ view: v }))))
      .then(([d, r]) => (res = { ...res, durable: d, raw: r }))
      .catch((e) => (error = e.message));
  });
  const cur = $derived(res[view]);
  const margins = $derived(cur ? Object.fromEntries(cur.units.map((x) => [x.id, x.margin])) : {});
  const evD = $derived(cur ? pointEV(cur) : null);
  const evTotal = P.national?.ev_total ?? 538;
  const evWin = P.national?.ev_win ?? 270;
  const diffVs = (a, b) => {
    if (!res[a] || !res[b]) return [];
    const mb = new Map(res[b].units.map((x) => [x.id, x.margin]));
    return res[a].units.filter((x) => (x.margin > 0) !== (mb.get(x.id) > 0)).map((x) => x.id);
  };
  const backToR = $derived(diffVs('raw', 'durable'));
  const names = (ids) => ids.map((id) => unitName(ctx, id)).join(', ');
</script>

<SimFrame
  {ctx}
  title="If 2026 had picked a president"
  dek="Each state colored by how it voted for the House in 2026, counted up as electoral votes."
  banner={bannerSnip}
>
  <div class="bar" bind:clientWidth={bw}>
    <Segmented label="Map" options={VIEWS.map((v) => ({ value: v, label: bw > 0 && bw < 480 ? shortLabel[v] : viewLabel[v] }))} bind:value={view} small />
  </div>

  {#if cur && evD != null}
    <div class="ev" role="img" aria-label={`Democrats ${evD} electoral votes, Republicans ${evTotal - evD}; ${evWin} needed to win.`}>
      <div class="evbar">
        <span class="d" style:width="{(100 * evD) / evTotal}%"></span>
        <span class="r" style:width="{(100 * (evTotal - evD)) / evTotal}%"></span>
        <span class="line" style:left="{(100 * evWin) / evTotal}%"></span>
      </div>
      <div class="evlab tabular">
        <span><i class="dem-text"></i><b>{evD}</b> Democrats</span>
        <span class="mid">{evWin} to win</span>
        <span>Republicans <b>{evTotal - evD}</b><i class="rep-text"></i></span>
      </div>
      <p class="note">
        Allowing for votes still being counted: {Math.round(cur.ev[1])} to {Math.round(cur.ev[2])} electoral votes for Democrats.
      </p>
    </div>
    <TileMap
      {ctx}
      values={margins}
      kind="margin"
      {hatched}
      hatchLabel="Still counting"
      label={`Map of 2026 House margins by state, ${viewLabel[view]} view`}
      maxHeight={320}
    />
    <div class="flips">
      {#if backToR.length}
        <p class="note">Democratic in 2026 but back to Republican {evenYear === 'an even year' ? 'at an even vote' : `at ${fmtE(Ecenter)}`}: <b>{names(backToR)}</b>.</p>
      {/if}
      {#if cur.flipsVs2024?.length}
        <p class="note">Different winner than in 2024: {names(cur.flipsVs2024)}.</p>
      {/if}
    </div>
  {:else if error}
    <p class="error">Simulation error: {error}</p>
  {:else}
    <p class="note">Translating…</p>
  {/if}

  {#snippet table()}
    <table class="data">
      <caption>2026 House margin by state (points; positive = Democratic)</caption>
      <thead>
        <tr><th scope="col">State</th><th scope="col">EV</th>{#each VIEWS as v (v)}<th scope="col">{viewLabel[v]}</th>{/each}</tr>
      </thead>
      <tbody>
        {#each units as u (u.id)}
          <tr>
            <th scope="row">{u.name}{hatched.has(u.id) ? ' *' : ''}</th>
            <td>{u.ev}</td>
            {#each VIEWS as v (v)}<td>{res[v] ? fmtE(res[v].units.find((x) => x.id === u.id)?.margin, 1) : '…'}</td>{/each}
          </tr>
        {/each}
        <tr>
          <th scope="row">Democratic EV</th><td></td>
          {#each VIEWS as v (v)}<td>{res[v] ? pointEV(res[v]) : '…'}</td>{/each}
        </tr>
      </tbody>
    </table>
    <p class="note">* still counting (under 90% in) or partly imputed.</p>
  {/snippet}

  {#snippet notes()}
    {#if res.raw && res.durable}
      <p>As it happened, the 2026 House vote would give Democrats {pointEV(res.raw)} electoral votes; in {evenYear}, {pointEV(res.durable)}.</p>
    {/if}
  {/snippet}
</SimFrame>

{#snippet bannerSnip()}
  <p class="warn">Not a forecast. Midterm voters are older and whiter than presidential-year voters.</p>
{/snippet}

<style>
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .ev {
    display: grid;
    gap: 4px;
  }
  .evbar {
    position: relative;
    display: flex;
    gap: 2px;
    height: 12px;
  }
  .evbar .d {
    background: var(--dem);
    border-radius: 4px 0 0 4px;
    transition: width 0.6s var(--ease);
  }
  .evbar .r {
    background: var(--rep);
    border-radius: 0 4px 4px 0;
    transition: width 0.6s var(--ease);
  }
  .evbar .line {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 2px;
    margin-left: -1px;
    background: var(--ink);
    box-shadow: 0 0 0 1.5px var(--bg);
  }
  .evlab {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 13px;
  }
  .evlab b {
    font-size: 17px;
  }
  .evlab i::before {
    margin: 0 0.3em;
  }
  .evlab .mid {
    color: var(--ink-2);
    font-size: 12px;
  }
  .flips {
    display: grid;
    gap: 3px;
  }
</style>
