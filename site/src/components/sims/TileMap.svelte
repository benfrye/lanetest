<script>
  // Electoral tile grid (one square per state, STATE_TILES layout). Party diverging fill by
  // P(D) or margin, optional hatching for still-counting units, optional highlighted unit.
  // Maine/Nebraska districts are folded into the state tile and listed in its tooltip.
  import { STATE_TILES, PROB_BINS, MARGIN_BINS, probFill, marginFill, pct, fmtE, unitList } from './shared.js';

  let {
    ctx,
    values,
    kind = 'prob',
    hatched = null,
    hatchLabel = 'Still counting',
    highlight = null,
    highlightLabel = '',
    label = 'Map',
    maxHeight = 360,
    legend = true,
  } = $props();

  const uid = `tm-${Math.random().toString(36).slice(2, 8)}`;
  let w = $state(0);
  let tip = $state(null);

  const units = $derived(unitList(ctx));
  const byId = $derived(new Map(units.map((u) => [u.id, u])));
  const hatchSet = $derived(hatched instanceof Set ? hatched : new Set(hatched ?? []));
  const size = $derived(Math.max(14, Math.floor(Math.min((w || 300) / 12, maxHeight / 8))));
  const fs = $derived(Math.max(8, Math.min(13, Math.round(size * 0.34))));
  // saturated fills take the dark text in both themes (light ink on them fails contrast in dark mode)
  const isStrong = (v) => v != null && (kind === 'prob' ? v < 0.2 || v >= 0.8 : Math.abs(v) >= 5);
  const fill = (v) => (kind === 'prob' ? probFill(v) : marginFill(v));
  const fmt = (v) => (kind === 'prob' ? `${pct(v)} chance for the Democrat` : `${fmtE(v, 1)} margin`);
  const bins = $derived(kind === 'prob' ? PROB_BINS : MARGIN_BINS);
  const tiles = $derived(
    Object.entries(STATE_TILES).map(([id, [c, r]]) => ({
      id,
      x: c * size,
      y: r * size,
      v: values?.[id],
      districts: units.filter((u) => u.parent === id),
    })),
  );

  function show(e, t) {
    const box = e.currentTarget.ownerSVGElement.getBoundingClientRect();
    const host = e.currentTarget.ownerSVGElement.parentElement.getBoundingClientRect();
    tip = { t, x: box.left - host.left + t.x + size / 2, y: box.top - host.top + t.y };
  }
</script>

<div class="tilemap" bind:clientWidth={w}>
  <svg
    width={size * 12}
    height={size * 8}
    role="img"
    aria-label={label}
    onpointerleave={() => (tip = null)}
  >
    <defs>
      <pattern id={uid} patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="5" style:stroke="var(--ink)" stroke-opacity="0.45" stroke-width="1.4" />
      </pattern>
    </defs>
    {#each tiles as t (t.id)}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <g
        transform="translate({t.x},{t.y})"
        onpointerenter={(e) => show(e, t)}
        onpointerdown={(e) => show(e, t)}
      >
        <rect x="1" y="1" width={size - 2} height={size - 2} rx="2" style:fill={fill(t.v)} />
        {#if hatchSet.has(t.id)}
          <rect x="1" y="1" width={size - 2} height={size - 2} rx="2" fill="url(#{uid})" />
        {/if}
        {#if highlight === t.id}
          <rect x="2" y="2" width={size - 4} height={size - 4} rx="2" fill="none" style:stroke="var(--ink)" stroke-width="2.5" />
        {/if}
        <text x={size / 2} y={size / 2 + fs * 0.36} text-anchor="middle" class="st" class:strong={isStrong(t.v)} style:font-size="{fs}px">{t.id}</text>
      </g>
    {/each}
  </svg>
  {#if tip}
    <div class="tip" style:left="{Math.min(Math.max(tip.x, 90), (w || 300) - 90)}px" style:top="{tip.y}px" role="status">
      <b>{byId.get(tip.t.id)?.name ?? tip.t.id}</b> ({byId.get(tip.t.id)?.ev ?? '?'} EV)<br />
      {fmt(tip.t.v)}
      {#each tip.t.districts as d (d.id)}
        <br /><span class="dist">{d.id} ({d.ev} EV): {kind === 'prob' ? pct(values?.[d.id]) : fmtE(values?.[d.id], 1)}</span>
      {/each}
      {#if hatchSet.has(tip.t.id)}<br /><span class="dist">{hatchLabel}</span>{/if}
      {#if highlight === tip.t.id && highlightLabel}<br /><span class="dist">{highlightLabel}</span>{/if}
    </div>
  {/if}
  {#if legend}
    <div class="legend" aria-hidden="true">
      {#each bins as b (b.label)}
        <span class="key"><i style:background={b.fill}></i>{b.label}</span>
      {/each}
      {#if hatchSet.size}
        <span class="key"><i class="hatch"></i>{hatchLabel}</span>
      {/if}
      {#if highlight && highlightLabel}
        <span class="key"><i class="hl"></i>{highlightLabel}</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .tilemap {
    position: relative;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  svg {
    display: block;
    overflow: visible;
    touch-action: manipulation;
  }
  .st {
    fill: var(--ink);
    font-weight: 600;
    pointer-events: none;
    stroke-width: 2px;
  }
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme='light'])) .st.strong {
      fill: var(--bg);
    }
  }
  :global(:root[data-theme='dark']) .st.strong {
    fill: var(--bg);
  }
  .tip {
    transform: translate(-50%, calc(-100% - 6px));
  }
  .dist {
    color: var(--ink-2);
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 2px 10px;
    font-size: 11px;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .key {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
  }
  i {
    display: inline-block;
    width: 11px;
    height: 11px;
    border-radius: 2px;
  }
  .hatch {
    background: repeating-linear-gradient(45deg, var(--ink) 0 1.2px, transparent 1.2px 4px), var(--mid);
    opacity: 0.8;
  }
  .hl {
    box-shadow: inset 0 0 0 2px var(--ink);
  }
</style>
