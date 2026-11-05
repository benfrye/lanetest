<script>
  // Common chrome for every simulation stage: title, "preliminary data" note, review badge,
  // optional banner, the chart body, and a "Show as table" toggle for the text alternative.
  // Also hosts the shared control styles (.btn, .seg, .data tables, notes) under .sim.
  import { asOf, underReview } from './shared.js';
  import ScrollCue from '../story/ScrollCue.svelte';
  import { simSource } from '../story/sources.js';

  // `source` overrides the default line (our model + its inputs, named from sources.json).
  let { ctx, title, dek = '', children, table = null, banner = null, notes = null, tableLabel = 'Show as table', source = null } = $props();
  const sourceLine = $derived(source ?? simSource(ctx));

  const stamp = $derived(asOf(ctx));
  const review = $derived(underReview(ctx));
  let showTable = $state(false);
</script>

<div class="sim ui">
  <header class="head">
    <div class="titles">
      <h2>{title}</h2>
      {#if dek}<p class="dek">{dek}</p>{/if}
    </div>
    <p class="meta">
      <span class="asof" title={stamp.full}>Preliminary data, as of {stamp.short}</span>
      {#if review}<span class="badge" title="The model's style estimates are being re-checked; numbers can change.">Model under review</span>{/if}
    </p>
  </header>

  {#if banner}{@render banner()}{/if}

  <div class="body">
    {#if showTable && table}
      <div class="table-wrap">{@render table()}</div>
    {:else}
      {@render children()}
    {/if}
  </div>

  {#if notes || table || sourceLine}
    <footer class="foot">
      <div class="notes">
        {#if notes}{@render notes()}{/if}
        {#if sourceLine}<p class="src">{sourceLine}</p>{/if}
      </div>
      {#if table}
        <button class="linkbtn" aria-pressed={showTable} onclick={() => (showTable = !showTable)}>
          {showTable ? 'Show chart' : tableLabel}
        </button>
      {/if}
    </footer>
  {/if}
  <div class="cue-slot"><ScrollCue /></div>
</div>

<style>
  .sim {
    position: relative;
    container-type: inline-size;
    display: flex;
    flex-direction: column;
    min-height: 100%;
    padding: 20px clamp(20px, 4vw, 48px) 18px;
    gap: 8px;
    color: var(--ink);
    font-size: 14px;
    line-height: 1.4;
  }
  .cue-slot {
    display: contents;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 4px 16px;
  }
  .titles {
    min-width: 0;
    flex: 1 1 260px;
  }
  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 650;
    letter-spacing: -0.005em;
  }
  .dek {
    margin: 2px 0 0;
    color: var(--ink-2);
    font-size: 13px;
  }
  .meta {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    color: var(--muted);
  }
  .badge {
    display: inline-block;
    padding: 1px 7px;
    border: 1px solid var(--axis);
    border-radius: 999px;
    color: var(--ink-2);
    font-weight: 600;
    font-size: 11px;
    white-space: nowrap;
  }
  .body {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .table-wrap {
    overflow: auto;
    max-height: 100%;
  }
  .foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 2px 16px;
    font-size: 11.5px;
    color: var(--muted);
  }
  .notes {
    flex: 1 1 260px;
    min-width: 0;
  }
  .notes :global(p) {
    margin: 0;
  }
  .src {
    margin-top: 2px !important;
    font-size: 11px;
    color: var(--muted);
  }
  .linkbtn {
    min-height: 44px;
    padding: 0 2px;
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: 12.5px;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
  }

  /* ---- shared controls ---- */
  .sim :global(.btn) {
    min-height: 44px;
    padding: 0 16px;
    border: 1px solid var(--ink);
    border-radius: 999px;
    background: var(--ink);
    color: var(--bg);
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    white-space: nowrap;
  }
  .sim :global(.btn.ghost) {
    background: transparent;
    color: var(--ink);
    border-color: var(--axis);
  }
  .sim :global(.btn:disabled) {
    opacity: 0.5;
    cursor: default;
  }
  .sim :global(.controls) {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 6px 18px;
  }
  .sim :global(.warn) {
    margin: 0;
    padding: 7px 10px;
    border-left: 3px solid var(--ink-2);
    background: var(--surface-2);
    border-radius: 0 6px 6px 0;
    color: var(--ink);
    font-size: 12.5px;
  }
  .sim :global(.note) {
    margin: 0;
    color: var(--ink-2);
    font-size: 12.5px;
  }
  .sim :global(.big) {
    font-size: 15px;
    color: var(--ink);
  }
  .sim :global(.tabular) {
    font-variant-numeric: tabular-nums;
  }
  .sim :global(table.data) {
    border-collapse: collapse;
    font-size: 12.5px;
    font-variant-numeric: tabular-nums;
    min-width: 100%;
  }
  .sim :global(table.data caption) {
    text-align: left;
    font-weight: 600;
    padding: 0 0 6px;
    color: var(--ink);
  }
  .sim :global(table.data th),
  .sim :global(table.data td) {
    padding: 5px 10px 5px 0;
    border-bottom: 1px solid var(--grid);
    text-align: right;
    white-space: nowrap;
  }
  .sim :global(table.data th:first-child),
  .sim :global(table.data td:first-child) {
    text-align: left;
  }
  .sim :global(table.data thead th) {
    color: var(--ink-2);
    font-weight: 600;
    border-bottom-color: var(--axis);
  }
  .sim :global(.tip) {
    position: absolute;
    z-index: 5;
    pointer-events: none;
    padding: 7px 9px;
    border-radius: 6px;
    background: var(--surface);
    box-shadow: 0 0 0 1px var(--ring), 0 4px 14px rgba(0, 0, 0, 0.12);
    color: var(--ink);
    font-size: 12px;
    line-height: 1.35;
    max-width: 240px;
  }
  .sim :global(.tip b) {
    font-weight: 650;
  }
  .sim :global(svg text) {
    font-family: var(--font-ui);
  }
  .sim :global(.axis-line) {
    stroke: var(--axis);
    stroke-width: 1;
  }
  .sim :global(.gridline) {
    stroke: var(--grid);
    stroke-width: 1;
  }
  .sim :global(.tick) {
    fill: var(--muted);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .sim :global(.axis-title) {
    fill: var(--ink-2);
    font-size: 12px;
  }
  .sim :global(.lbl) {
    fill: var(--ink);
    font-size: 12px;
  }
  .sim :global(.lbl-2) {
    fill: var(--ink-2);
    font-size: 11.5px;
  }
  .sim :global(.halo) {
    paint-order: stroke;
    stroke: var(--bg);
    stroke-width: 3px;
    stroke-linejoin: round;
  }
  .sim :global(.error) {
    color: var(--ink);
    font-size: 13px;
  }
  @media (max-width: 760px) {
    .dek {
      display: none;
    }
  }
  @media (max-width: 520px) {
    .sim {
      padding: 12px 20px 10px;
      gap: 6px;
    }
    h2 {
      font-size: 15px;
    }
  }
</style>
