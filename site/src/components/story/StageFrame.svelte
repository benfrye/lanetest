<script>
  import ScrollCue from './ScrollCue.svelte';
  // Common chrome for stage components: title, legend, a chart area that reports its
  // size, a "Show as table" toggle (the text alternative) and the preliminary note.
  let {
    title = '',
    dek = '',
    // Alternative deks for a chart with a toggle: all are laid out in one cell and only
    // deks[dekIndex] shows, so the header keeps the tallest one's height and nothing shifts.
    deks = null,
    dekIndex = 0,
    note = '',
    source = '',
    sourceShort = '',
    showTable = $bindable(false),
    legend,
    banner,
    chart,
    table,
    onbackground,
  } = $props();
  let w = $state(0);
  let h = $state(0);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="frame ui" onclick={(e) => e.target === e.currentTarget && onbackground?.()}>
  <header class="head">
    <div class="titles">
      {#if title}<h2 class="title">{title}</h2>{/if}
      {#if deks}
        <div class="deks">
          {#each deks as d, i (i)}<p class="dek" class:off={i !== dekIndex} aria-hidden={i !== dekIndex}>{d}</p>{/each}
        </div>
      {:else if dek}<p class="dek">{dek}</p>{/if}
    </div>
    {#if table}
      <button class="toggle" aria-pressed={showTable} onclick={(e) => { e.stopPropagation(); showTable = !showTable; }}>
        {showTable ? 'Show chart' : 'Show as table'}
      </button>
    {/if}
  </header>
  {#if legend && !showTable}<div class="legend">{@render legend()}</div>{/if}
  {#if banner}<div class="banner">{@render banner()}</div>{/if}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="body" bind:clientWidth={w} bind:clientHeight={h} onclick={(e) => e.target === e.currentTarget && onbackground?.()}>
    {#if showTable && table}
      <div class="table-wrap">{@render table()}</div>
    {:else if w > 0 && h > 0}
      {@render chart(w, h)}
    {/if}
    <ScrollCue />
  </div>
  {#if note || source}
    <p class="note wide-only">
      {#if note}<span class="prelim">{note}</span>{/if}
      {#if source}<span class="src">{source}</span>{/if}
    </p>
    <!-- Phones: the source line stays visible (one line); the rest opens on tap. -->
    <details class="note note-m">
      <summary><span class="sum">{sourceShort || source || 'Notes'}</span></summary>
      {#if note}<span class="prelim">{note}</span>{/if}
      {#if source && sourceShort && source !== sourceShort}<span class="src">{source}</span>{/if}
    </details>
  {/if}
</div>

<style>
  .frame {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    padding: 20px clamp(20px, 4vw, 48px) 18px;
    color: var(--ink);
    background: var(--bg);
    font-size: 13px;
  }
  .head {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .titles {
    flex: 1;
    min-width: 0;
  }
  .title {
    margin: 0;
    font-size: clamp(15px, 1.6vw, 19px);
    line-height: 1.25;
    font-weight: 700;
  }
  .deks {
    display: grid;
  }
  .deks > .dek {
    grid-area: 1 / 1;
    transition: opacity 0.25s;
  }
  .deks > .off {
    visibility: hidden;
    opacity: 0;
  }
  .dek {
    margin: 3px 0 0;
    color: var(--ink-2);
    font-size: 13px;
    line-height: 1.35;
  }
  .toggle {
    flex: none;
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid var(--ring);
    border-radius: 999px;
    background: var(--surface);
    color: var(--ink);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }
  .legend {
    margin-top: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px 14px;
    color: var(--ink-2);
    font-size: 12px;
  }
  .banner {
    margin-top: 8px;
  }
  .body {
    position: relative;
    flex: 1;
    min-height: 0;
    margin-top: 8px;
  }
  .body {
    overflow-x: hidden;
    overflow-y: auto;
  }
  .table-wrap {
    position: absolute;
    inset: 0;
    overflow: auto;
  }
  .table-wrap :global(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .table-wrap :global(th),
  .table-wrap :global(td) {
    padding: 5px 8px 5px 0;
    border-bottom: 1px solid var(--grid);
    text-align: left;
    vertical-align: top;
  }
  .table-wrap :global(th) {
    color: var(--ink-2);
    font-weight: 600;
    position: sticky;
    top: 0;
    background: var(--bg);
  }
  .table-wrap :global(td.n),
  .table-wrap :global(th.n) {
    text-align: right;
  }
  .table-wrap :global(caption) {
    text-align: left;
    color: var(--ink-2);
    padding-bottom: 6px;
  }
  .note {
    margin: 6px 0 0;
    font-size: 11px;
    line-height: 1.35;
    color: var(--muted);
    display: flex;
    flex-wrap: wrap;
    gap: 0 10px;
  }
  .note-m {
    display: none;
  }
  .note-m summary {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 28px;
    cursor: pointer;
    list-style: none;
  }
  .note-m summary::-webkit-details-marker {
    display: none;
  }
  .note-m .sum {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .note-m summary::after {
    content: 'More';
    flex: none;
    color: var(--ink-2);
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .note-m[open] summary::after {
    content: 'Less';
  }
  .note-m[open] .sum {
    white-space: normal;
  }
  .note-m[open] {
    max-height: 40vh;
    overflow-y: auto;
  }
  .note-m > span {
    display: block;
    margin-top: 2px;
  }
  @media (max-width: 760px) {
    .wide-only {
      display: none;
    }
    .note-m {
      display: block;
    }
    .frame {
      padding: 12px 20px 10px;
    }
    .dek {
      display: none;
    }
    .title {
      font-size: 15px;
    }
    .legend {
      margin-top: 4px;
      font-size: 11px;
      gap: 4px 10px;
    }
    .note {
      font-size: 10.5px;
    }
  }
</style>
