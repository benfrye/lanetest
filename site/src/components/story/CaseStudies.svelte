<script>
  // Stage: four case-study panels, each a mini "2024 baseline -> 2026 result" chart and
  // two or three lines. Every number is read from races.json / story data.
  // Desktop: 2x2 grid. Narrow: one column. Every panel shows its full story; no expanding.
  import StageFrame from './StageFrame.svelte';
  import { resultsSource, resultsShort, nytSource } from './sources.js';
  import ArchChip from './ArchChip.svelte';
  import Tip from './Tip.svelte';
  import { scaleLinear } from 'd3-scale';
  import { signed, margin, num, asOfLabel, archOfRace, median, ARCHETYPE_BY_ID } from './util.js';

  let { ctx, nodes = [], title = 'Four races worth a closer look', ...rest } = $props();

  const d = $derived(ctx?.data ?? {});
  const races = $derived(d.races ?? []);
  const byId = $derived(Object.fromEntries(races.map((r) => [r.id, r])));
  const flags = $derived(d.params?.copy_flags ?? {});
  const disc = $derived(d.story?.nine?.maine_discrepancy ?? d.validation?.data_issues?.maine_discrepancy ?? null);
  const nytImplied = $derived(disc?.nyt_9state_implied ?? d.params?.reveal?.maine?.nyt_implied ?? null);

  const lastName = (n) => (n ?? '').replace(/\s*\(.*\)$/, '').split(' ').slice(-1)[0];
  const first = (n) => (n ?? '').replace(/\s*\(.*\)$/, '');
  const alabel = (r) => ARCHETYPE_BY_ID[archOfRace(r)]?.label?.toLowerCase() ?? '';

  // Senate ranking for "biggest gain" claims, computed from the race table.
  const senate = $derived(
    races.filter((r) => r.office === 'Senate' && r.overperformance != null && r.margin_2p != null).sort((a, b) => b.overperformance - a.overperformance),
  );
  const senateMedian = $derived(median(senate.map((r) => r.overperformance)));
  const ORD = ['', 'biggest', 'second-biggest', 'third-biggest'];

  function row(id, office) {
    const r = byId[id];
    if (!r) return null;
    const nonComparable = /independent/i.test(r.rep_name ?? '') || r.office === 'Validation2025' && r.id.startsWith('NYC');
    return {
      id,
      r,
      name: first(r.dem_name),
      office,
      arch: archOfRace(r),
      base: r.pres2024_margin_2p ?? r.pres2024_margin,
      res: r.margin_2p ?? r.margin,
      gain: r.overperformance,
      nonComparable,
    };
  }

  const panels = $derived.by(() => {
    const out = [];
    const me = byId['SEN-ME'];
    if (me) {
      const prim = (d.story?.primaries?.contests ?? []).find((c) => c.contest === 'ME-SEN-D-primary');
      const rows = [row('SEN-ME', 'Senate')];
      out.push({
        key: 'maine',
        title: 'Maine',
        rows,
        extra: [
          nytImplied != null ? { x: (rows[0].base ?? 0) + nytImplied, label: 'NYT estimate' } : null,
          senateMedian != null ? { x: (rows[0].base ?? 0) + senateMedian, label: 'with a typical Senate gain' } : null,
        ].filter(Boolean),
        lines: [
          prim && prim.winner !== first(me.dem_name)
            ? `${prim.winner} won the Democratic primary, then withdrew. ${first(me.dem_name)}, also a ${alabel(me)}, replaced him against ${first(me.rep_name)}, the Republican incumbent.`
            : `${first(me.dem_name)} (${alabel(me)}) ran against ${first(me.rep_name)}, the Republican incumbent.`,
          `${lastName(me.dem_name)} won, but Democrats gained far less here than elsewhere: he ran ${num(Math.abs(me.overperformance), 1)} points ${me.overperformance >= 0 ? 'ahead of' : 'behind'} Harris’s margin, while the typical Senate Democrat gained ${num(senateMedian, 0)} points.`,
          flags.maine_explained_by_incumbent
            ? `That looks like ${first(me.rep_name)}’s personal vote, not a populism penalty. One race can’t separate the candidate from the opponent.`
            : 'One race can’t separate the candidate from the opponent.',
          nytImplied != null
            ? `Those numbers are from the count so far (${num(me.pct_counted, 0)}% in). The New York Times’s voter estimates put Maine ${nytImplied < me.overperformance ? 'a little worse for Democrats' : 'a little better for Democrats'}, at ${signed(nytImplied)} vs. Harris.`
            : `Those numbers are from the count so far (${num(me.pct_counted, 0)}% in).`,
        ],
      });
    }
    const tx = byId['SEN-TX'];
    if (tx) {
      const rank = senate.findIndex((r) => r.id === 'SEN-TX') + 1;
      const gov = byId['GOV-TX'];
      const opp = tx.rep_style === 'maga' ? 'a MAGA-aligned Republican' : 'a Republican';
      out.push({
        key: 'texas',
        title: 'Texas',
        rows: [row('SEN-TX', 'Senate'), gov && row('GOV-TX', 'Governor')].filter(Boolean),
        lines: [
          `${first(tx.dem_name)}, a ${alabel(tx)}, posted the ${ORD[rank] ?? `No. ${rank}`} gain of any Senate Democrat: ${signed(tx.overperformance)} vs. Harris. He faced ${first(tx.rep_name)}, ${opp}; one race can’t separate the candidate from the opponent.`,
          gov
            ? `On the same ballot, ${first(gov.dem_name)} (${alabel(gov)}) gained ${signed(gov.overperformance)} against ${gov.rep_incumbent ? 'incumbent ' : ''}${first(gov.rep_name)}.`
            : '',
        ],
      });
    }
    const ks = byId['SEN-KS'];
    const ia = byId['SEN-IA'];
    if (ks && ia) {
      const extra = ['GOV-IA', 'GOV-KS'].filter((id) => byId[id]);
      const flipVerb = (r) => (r.rep_incumbent ? `beat incumbent ${first(r.rep_name)}` : 'won an open seat');
      const govKs = byId['GOV-KS'];
      out.push({
        key: 'plains',
        title: 'Kansas and Iowa',
        rows: [row('SEN-KS', 'Senate'), row('SEN-IA', 'Senate'), ...extra.map((id) => row(id, 'Governor'))],
        lines: [
          `Moderates flipped Senate seats in states Trump carried by ${num(Math.abs(ks.pres2024_margin_2p), 0)} (Kansas) and ${num(Math.abs(ia.pres2024_margin_2p), 0)} (Iowa) points: ${first(ks.dem_name)} ${flipVerb(ks)}; ${first(ia.dem_name)} ${flipVerb(ia)}.`,
          govKs
            ? `Kansas’s governor race is a same-ballot check: ${first(govKs.dem_name)}, a ${alabel(govKs)}, gained ${signed(govKs.overperformance)}${govKs.called ? '' : ' (not yet called)'}.`
            : '',
        ],
      });
    }
    const va = byId['VA_GOV_2025'];
    const nj = byId['NJ_GOV_2025'];
    const nyc = byId['NYC_MAYOR_2025'];
    if (va || nj || nyc) {
      out.push({
        key: '2025',
        title: 'The 2025 contrast',
        rows: [va && row('VA_GOV_2025', 'Virginia governor'), nj && row('NJ_GOV_2025', 'New Jersey governor'), nyc && row('NYC_MAYOR_2025', 'NYC mayor')].filter(Boolean),
        lines: [
          va && nj
            ? `A year earlier, ${first(va.dem_name)} and ${first(nj.dem_name)}, both ${alabel(va)}s, won governorships running ${signed(va.overperformance)} and ${signed(nj.overperformance)} ahead of Harris.`
            : '',
          nyc
            ? `${first(nyc.dem_name)}, a ${alabel(nyc)}, won New York City’s mayoralty; his main rival ran as an independent, so there is no like-for-like baseline.`
            : '',
          'These off-year races are a check on the story; they aren’t part of the 2026 averages.',
        ],
      });
    }
    return out;
  });

  let showTable = $state(false);
  let hover = $state(null);
  let pinned = $state(null);
  const tip = $derived(pinned ?? hover);
  const toggle = (key) => (pinned = pinned?.key === key ? null : { key });

  function tipFor(rw) {
    const r = rw.r;
    return {
      title: `${rw.name} · ${rw.office}`,
      lines: [
        `2024 president: ${margin(rw.base)}`,
        rw.nonComparable ? 'Three-way race; no like-for-like 2026 margin' : `2026: ${margin(rw.res)}${r.pct_counted != null && r.pct_counted < 100 ? ` (${num(r.pct_counted, 0)}% counted)` : ''}`,
        rw.nonComparable ? null : `Gain vs. 2024: ${signed(rw.gain)}`,
        `Opponent: ${first(r.rep_name)}`,
      ],
    };
  }
</script>

{#snippet mini(p, w)}
  {@const rows = p.rows}
  {@const vals = rows.flatMap((r) => (r.nonComparable ? [r.base] : [r.base, r.res])).concat((p.extra ?? []).map((e) => e.x), [0])}
  {@const lo = Math.floor(Math.min(...vals) / 10) * 10}
  {@const hi = Math.ceil(Math.max(...vals) / 10) * 10}
  {@const labW = Math.min(150, w * 0.38)}
  {@const valW = 44}
  {@const x = scaleLinear().domain([lo, hi === lo ? lo + 10 : hi]).range([labW + 8, w - valW - 6])}
  {@const rh = 34}
  {@const top = 16}
  {@const H = top + rows.length * rh + ((p.extra ?? []).length ? 14 : 0)}
  <div class="mini" style:height={H + 'px'}>
    <svg width={w} height={H} role="img" aria-label={`${p.title}: 2024 presidential margin and 2026 result for ${rows.map((r) => r.name).join(', ')}.`}>
      <line class="zero" x1={x(0)} x2={x(0)} y1={top - 4} y2={H} />
      <text class="ax" x={x(0)} y="9" text-anchor="middle">even</text>
      {#if x(0) - x(lo) > 40}<text class="ax" x={x(lo)} y="9" text-anchor="start">{margin(lo, 0)}</text>{/if}
      {#if x(hi) - x(0) > 40}<text class="ax" x={x(hi)} y="9" text-anchor="end">{margin(hi, 0)}</text>{/if}
      {#each rows as rw, i (rw.id)}
        {@const y = top + i * rh + rh / 2}
        {@const k = p.key + ':' + rw.id}
        <g
          class="mr"
          class:active={tip?.key === k}
          role="button"
          tabindex="0"
          aria-label={tipFor(rw).title + '. ' + tipFor(rw).lines.filter(Boolean).join('; ')}
          onpointerenter={(e) => e.pointerType === 'mouse' && (hover = { key: k })}
          onpointerleave={() => (hover = null)}
          onfocus={() => (hover = { key: k })}
          onblur={() => (hover = null)}
          onclick={(e) => { e.stopPropagation(); toggle(k); }}
          onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(k))}
        >
          <rect class="hit" x="0" y={y - rh / 2} width={w} height={rh} />
          <text class="nm" x="0" y={y - 3}>{rw.name}</text>
          <text class="of" x="0" y={y + 10}>{rw.office}</text>
          {#if rw.nonComparable}
            <circle class="b" cx={x(rw.base)} cy={y} r="4.5" />
            <text class="of" x={x(rw.base) + (x(rw.base) > w * 0.6 ? -9 : 9)} y={y + 4} text-anchor={x(rw.base) > w * 0.6 ? 'end' : 'start'}>no like-for-like result</text>
          {:else}
            <line class="conn" x1={x(rw.base)} x2={x(rw.res)} y1={y} y2={y} />
            <circle class="b" cx={x(rw.base)} cy={y} r="4.5" />
            <circle class="r" cx={x(rw.res)} cy={y} r="5.5" />
            <text class="gv" x={w} y={y + 4} text-anchor="end">{signed(rw.gain)}</text>
          {/if}
        </g>
      {/each}
      {#each p.extra ?? [] as e, ei (e.label)}
        {@const y = top + rh / 2}
        <line class="nyt" x1={x(e.x)} x2={x(e.x)} y1={y - 8} y2={y + 8} />
        <text class="of" x={Math.max(labW + 8, Math.min(x(e.x), w - 4))} y={ei % 2 ? y - 11 : y + 22} text-anchor={x(e.x) > w - 70 ? 'end' : x(e.x) < labW + 60 ? 'start' : 'middle'}>{e.label}</text>
      {/each}
    </svg>
    {#each rows as rw, i (rw.id)}
      {#if tip?.key === p.key + ':' + rw.id}
        {@const tt = tipFor(rw)}
        <Tip x={x(rw.nonComparable ? rw.base : rw.res)} y={top + i * rh + rh / 2} width={w} height={Math.max(H, 120)} title={tt.title} lines={tt.lines} pinned={!!pinned} onclose={() => (pinned = null)} />
      {/if}
    {/each}
  </div>
{/snippet}

<StageFrame
  {title}
  dek="2024 presidential margin (open circle) to the 2026 result (filled), with the gain in points."
  note={`Preliminary, as of ${asOfLabel(ctx)}.`}
  source={`${resultsSource(ctx)}${nytImplied != null ? ` Maine group estimate: ${nytSource(ctx).replace(/^Source: /, '')}` : ''}`}
  sourceShort={resultsShort(ctx)}
  bind:showTable
  onbackground={() => (pinned = null)}
>
  {#snippet legend()}
    <span class="lg"><svg width="12" height="12" viewBox="-6 -6 12 12"><circle r="4" class="b" /></svg>2024 president</span>
    <span class="lg"><svg width="12" height="12" viewBox="-6 -6 12 12"><circle r="5" class="r" /></svg>2026 result</span>
  {/snippet}

  {#snippet chart(w, h)}
    {@const wide = w >= 680}
    <div class="panels" class:wide>
      {#each panels as p (p.key)}
        <section class="panel">
          <h3 class="pt">{p.title}</h3>
          <div class="chips">
            {#each [...new Set(p.rows.map((r) => r.arch))] as a (a)}<ArchChip id={a} size={10} />{/each}
          </div>
          <div class="mw">
            {@render mini(p, wide ? Math.floor((w - 24) / 2) - 24 : w - 24)}
          </div>
          {#each p.lines.filter(Boolean) as l, i (i)}<p class="ln">{l}</p>{/each}
        </section>
      {/each}
    </div>
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Case-study races: margins in points (D+ / R+)</caption>
      <thead><tr><th>Race</th><th>Democrat</th><th>Lane</th><th class="n">2024 pres.</th><th class="n">2026</th><th class="n">Gain</th></tr></thead>
      <tbody>
        {#each panels as p (p.key)}
          {#each p.rows as rw (rw.id)}
            <tr>
              <td>{p.title}: {rw.office}</td>
              <td>{rw.name}</td>
              <td>{ARCHETYPE_BY_ID[rw.arch]?.label ?? ''}</td>
              <td class="n">{margin(rw.base)}</td>
              <td class="n">{rw.nonComparable ? 'n/a' : margin(rw.res)}</td>
              <td class="n">{rw.nonComparable ? 'n/a' : signed(rw.gain)}</td>
            </tr>
          {/each}
        {/each}
      </tbody>
    </table>
    {#each panels as p (p.key)}
      <p class="ln"><strong>{p.title}.</strong> {p.lines.filter(Boolean).join(' ')}</p>
    {/each}
  {/snippet}
</StageFrame>

<style>
  .lg {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .panels {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .panels.wide {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .panel {
    min-width: 0;
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid var(--ring);
    border-radius: var(--radius);
  }
  .pt {
    margin: 0 0 4px;
    font-size: 15px;
    font-weight: 700;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
    font-size: 11px;
    margin-bottom: 4px;
  }
  .mini {
    position: relative;
  }
  .mini svg {
    display: block;
    overflow: visible;
    font-family: var(--font-ui);
  }
  .zero {
    stroke: var(--axis);
    stroke-width: 1.5;
  }
  .ax {
    font-size: 10px;
    fill: var(--muted);
  }
  .hit {
    fill: transparent;
  }
  .mr {
    cursor: pointer;
    outline: none;
  }
  .mr:hover .hit,
  .mr.active .hit,
  .mr:focus-visible .hit {
    fill: var(--surface-2);
  }
  .mr:focus-visible .hit {
    stroke: var(--dem);
    stroke-width: 2;
  }
  .nm {
    font-size: 12px;
    font-weight: 600;
    fill: var(--ink);
  }
  .of {
    font-size: 10.5px;
    fill: var(--muted);
  }
  .gv {
    font-size: 12px;
    font-weight: 700;
    fill: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .conn {
    stroke: var(--ink-2);
    stroke-width: 1.5;
  }
  circle.b {
    fill: var(--surface);
    stroke: var(--ink-2);
    stroke-width: 1.5;
  }
  circle.r {
    fill: var(--ink);
    stroke: var(--surface);
    stroke-width: 1.5;
  }
  .lg circle.b {
    fill: var(--bg);
  }
  .nyt {
    stroke: var(--ink-2);
    stroke-width: 1.5;
    stroke-dasharray: 2 2;
  }
  .ln {
    margin: 6px 0 0;
    font-size: 12.5px;
    line-height: 1.45;
    color: var(--ink-2);
  }
</style>
