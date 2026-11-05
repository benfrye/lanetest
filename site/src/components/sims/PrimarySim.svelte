<script>
  import { untrack } from 'svelte';
  // Sim 3 (METHODOLOGY §6.5 simPrimary, §6.6 Sim 3; claim C13).
  // 10,000 simulated Democratic primaries → ranked bars of the share each candidate wins a
  // pledged majority, betting markets shown beside (never as input), "polls plus priors"
  // caveat with the V17 back-test, and the chained P(presidency) behind an off-by-default
  // toggle with its compounding-uncertainty warning.
  import { ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import { outlets } from '../story/sources.js';
  import Segmented from './Segmented.svelte';
  import ArchChip from './ArchChip.svelte';
  import { pct, pctRange, params, piOpt, envHistory, envHistoryLabel, latest, isStale, fmtInt, lastName } from './shared.js';

  let { ctx, nodes, n = 10000 } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once

  const P = params(ctx0);
  const pr = P.primary ?? {};
  // Pollsters and markets cited in research/candidates_dem.json.
  const census = outlets(ctx0, 'State demographics', { n: 4 })?.names.includes('U.S. Census Bureau') ?? true;
  const primarySource = `Source: our model, built on national 2028 primary polls (Echelon Insights, Harvard-Harris, Emerson and others)${census ? ' and Census data' : ''}; market ticks: Kalshi, Polymarket.`;
  const field = (P.candidates_dem ?? []).filter((c) => c.include_default !== false);
  const calendars = Object.keys(pr.calendars ?? { dnc2024: 1 });
  const CAL_LABEL = { dnc2024: 'DNC 2024 order', traditional: 'Iowa first' };
  const LANE_SHORT = { left: 'left-lane', mainstream: 'mainstream', moderate: 'moderate-lane' };
  const coalitionOff = pr.validation?.coalition_enabled === false;
  const brier = pr.validation ?? {};

  let calendar = $state(calendars[0]);
  let seedBump = $state(0);
  let res = $state(null);
  let running = $state(false);
  let error = $state('');
  let chainOn = $state(false);
  let chained = $state(null);
  let chainBusy = $state(false);

  const go = latest(
    (o) => ctx.simReady.then(() => ctx.sim.simPrimary(o, {}, { channel: 'primary' })),
    (r) => {
      res = r;
      running = false;
    },
    (e) => {
      error = e.message;
      running = false;
    },
  );
  $effect(() => {
    running = true;
    go({ field: field.map((c) => c.id), calendar, n: +n, seed: (P.meta?.seed ?? 1) + seedBump });
  });

  $effect(() => {
    if (!chainOn) return;
    const o = {
      field: field.map((c) => c.id),
      calendar,
      n: +n,
      seed: (P.meta?.seed ?? 1) + seedBump,
      chain: { env: envHistory(ctx), pi: piOpt(ctx.reader), opponent: 'generic' },
    };
    chainBusy = true;
    chained = null;
    ctx.simReady
      .then(() => ctx.sim.simPrimary(o, {}, { channel: 'primary-chain' }))
      .then((r) => {
        chained = r.chained;
        chainBusy = false;
      })
      .catch((e) => {
        if (!isStale(e)) {
          error = e.message;
          chainBusy = false;
        }
      });
  });

  const rows = $derived(
    res
      ? field
          .map((c) => ({ ...c, p: res.pNominee[c.id] ?? 0 }))
          .sort((a, b) => b.p - a.p)
      : field.map((c) => ({ ...c, p: 0 })),
  );
  const maxV = $derived(Math.max(0.25, ...rows.map((r) => Math.max(r.p, r.market_nom ?? 0)), res?.pNoMajority ?? 0));
  const scale = (v) => `${(100 * v) / maxV}%`;
  let w = $state(0);
  const narrow = $derived(w > 0 && w < 520);
</script>

<SimFrame
  {ctx}
  title="Run the Democratic primary 10,000 times"
  source={primarySource}
  dek="Share of simulated primaries each candidate wins with a majority of pledged delegates. Ticks show betting markets for comparison."
>
  <div class="bar">
    <Segmented
      label="Primary calendar"
      options={calendars.map((k) => ({ value: k, label: CAL_LABEL[k] ?? k }))}
      bind:value={calendar}
      small
    />
    <button class="btn" onclick={() => seedBump++} disabled={running}>{running ? 'Simulating…' : `Run ${fmtInt(+n)} more`}</button>
  </div>

  <div class="bars" bind:clientWidth={w} role="img" aria-label={res ? `Ranked nomination shares: ${rows.slice(0, 3).map((r) => `${r.name} ${pct(r.p)}`).join(', ')}; no pledged majority ${pct(res.pNoMajority)}.` : 'Simulating primaries'}>
    {#each rows as r (r.id)}
      <div class="row">
        <div class="who" title={r.name}>
          <span class="nm">{narrow ? lastName(r.name) : r.name}</span>
          <span class="lane"><ArchChip id={r.archetype} short size={10} /></span>
        </div>
        <div class="track">
          <span class="fill" style:width={scale(r.p)}></span>
          {#if r.market_nom != null}<span class="mk" style:left={scale(r.market_nom)} title="Betting markets: {pct(r.market_nom)}"></span>{/if}
        </div>
        <span class="val tabular">{res ? pct(r.p) : '…'}</span>
      </div>
    {/each}
    {#if res}
      <div class="row nomaj">
        <div class="who"><span class="nm">No pledged majority</span><span class="lane">contested convention</span></div>
        <div class="track"><span class="fill" style:width={scale(res.pNoMajority)}></span></div>
        <span class="val tabular">{pct(res.pNoMajority)}</span>
      </div>
    {/if}
  </div>
  <div class="legend" aria-hidden="true">
    <span><i class="sw"></i>Simulated primaries won outright</span>
    <span><i class="tk"></i>Betting markets (not an input)</span>
  </div>

  {#if res}
    <p class="note">
      In {fmtInt(+n)} simulated primaries,
      {#each Object.entries(res.pLane) as [lane, p], i (lane)}{i ? ', ' : ''}{LANE_SHORT[lane] ?? lane} candidates win {pct(p)}{/each}
      of the time; nobody clinches in {pct(res.pNoMajority)}.
    </p>
  {/if}
  <p class="warn">
    {#if coalitionOff}<b>Polls plus priors.</b> The coalition model is switched off, so these shares mostly reflect early national polls and random campaign shocks.{/if}
    {P.banners?.primary_weak_proxy ?? ''}
    {#if brier.brier_model != null}Back-test on 2026 House primaries: Brier score {brier.brier_model.toFixed(2)} vs {brier.brier_baseline.toFixed(2)} for a polls-only baseline (lower is better){brier.brier_model > brier.brier_baseline ? '; the model did worse' : ''}.{/if}
  </p>

  <div class="chain">
    <button class="btn ghost" aria-pressed={chainOn} onclick={() => (chainOn = !chainOn)}>
      {chainOn ? 'Hide the combined estimate' : 'Combine with the general election'}
    </button>
    {#if chainOn}
      <div class="chainbox" role="status">
        <p class="warn"><b>Uncertainty compounds.</b> {chained?.warning ?? 'Chained estimate: a weak primary proxy multiplied by a conditional general-election scenario. Not a forecast.'}</p>
        {#if chained}
          <p class="note">
            Weighting each candidate's general-election chance by how often they lead the delegate count, in {envHistoryLabel(ctx)}:
            Democrats win the presidency in about {pct(chained.pDemWins)} of runs (80% range {pctRange(chained.p80)}).
          </p>
        {:else if chainBusy}
          <p class="note">Combining…</p>
        {/if}
      </div>
    {/if}
  </div>
  {#if error}<p class="error">Simulation error: {error}</p>{/if}

  {#snippet table()}
    <table class="data">
      <caption>{fmtInt(+n)} simulated primaries ({CAL_LABEL[calendar] ?? calendar})</caption>
      <thead><tr><th scope="col">Candidate</th><th scope="col">Type</th><th scope="col">Wins outright</th><th scope="col">Leads delegates</th><th scope="col">Betting markets</th></tr></thead>
      <tbody>
        {#each rows as r (r.id)}
          <tr><th scope="row">{r.name}</th><td>{ARCHETYPE_BY_ID[r.archetype]?.label ?? r.archetype}</td><td>{pct(r.p)}</td><td>{res ? pct(res.pPlurality?.[r.id]) : ''}</td><td>{r.market_nom != null ? pct(r.market_nom) : '–'}</td></tr>
        {/each}
        {#if res}<tr><th scope="row">No pledged majority</th><td></td><td>{pct(res.pNoMajority)}</td><td></td><td></td></tr>{/if}
      </tbody>
    </table>
  {/snippet}

  {#snippet notes()}
    <p>Calendar and delegate rules approximate 2024's; the order is an assumption. Candidates drop out after the 4th contest and Super Tuesday if they trail badly.</p>
  {/snippet}
</SimFrame>

<style>
  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
  }
  .bars {
    display: grid;
    gap: 5px;
  }
  .row {
    display: grid;
    grid-template-columns: minmax(96px, 190px) minmax(0, 1fr) 38px;
    align-items: center;
    gap: 10px;
  }
  .who {
    min-width: 0;
    line-height: 1.15;
  }
  .nm {
    display: block;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .lane {
    display: block;
    font-size: 11px;
    color: var(--ink-2);
  }
  .track {
    position: relative;
    height: 10px;
    border-radius: 0 4px 4px 0;
  }
  .track::before {
    content: '';
    position: absolute;
    left: 0;
    top: -3px;
    bottom: -3px;
    width: 1px;
    background: var(--axis);
  }
  .fill {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    border-radius: 0 4px 4px 0;
    background: var(--ink-2);
    transition: width 0.7s var(--ease);
  }
  .mk {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 2px;
    margin-left: -1px;
    background: var(--ink);
    box-shadow: 0 0 0 1.5px var(--bg);
  }
  .nomaj .fill {
    background: repeating-linear-gradient(45deg, var(--muted) 0 2px, transparent 2px 5px);
    box-shadow: inset 0 0 0 1px var(--muted);
  }
  .nomaj .nm {
    font-weight: 500;
    color: var(--ink-2);
  }
  .val {
    font-size: 13px;
    font-weight: 600;
    text-align: right;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 16px;
    font-size: 11.5px;
    color: var(--ink-2);
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .sw {
    width: 16px;
    height: 10px;
    border-radius: 0 3px 3px 0;
    background: var(--ink-2);
  }
  .tk {
    width: 2px;
    height: 14px;
    background: var(--ink);
  }
  .chain {
    display: grid;
    gap: 8px;
    justify-items: start;
  }
  .chainbox {
    display: grid;
    gap: 6px;
  }
  @container (min-width: 600px) {
    .row {
      grid-template-columns: minmax(120px, 300px) minmax(0, 1fr) 38px;
    }
    .who {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }
    .lane {
      display: inline;
      white-space: nowrap;
    }
  }
  @container (max-width: 520px) {
    .row {
      grid-template-columns: 92px minmax(0, 1fr) 34px;
      gap: 8px;
    }
  }
</style>
