<script>
  // Tooltip for stage charts. x/y are in the container's pixel space; the tip flips
  // to stay inside it. Pinned tips (tap on touch, click/Enter on desktop) get a close button.
  let { x = 0, y = 0, width = 0, height = 0, title = '', lines = [], pinned = false, onclose } = $props();
  let el = $state();
  let tw = $state(180);
  let th = $state(60);
  const left = $derived(Math.max(4, Math.min(x + 14 + tw > width ? x - 14 - tw : x + 14, width - tw - 4)));
  const top = $derived(Math.max(4, Math.min(y - th / 2, height - th - 4)));
</script>

<div class="tip ui" class:pinned bind:this={el} bind:clientWidth={tw} bind:clientHeight={th} style:left={left + 'px'} style:top={top + 'px'} role="status">
  <div class="t">{title}</div>
  {#each lines.filter(Boolean) as l, i (i)}<div class="l">{l}</div>{/each}
  {#if pinned && onclose}
    <button class="x" aria-label="Close details" onclick={(e) => { e.stopPropagation(); onclose(); }}>×</button>
  {/if}
</div>

<style>
  .tip {
    position: absolute;
    z-index: 5;
    max-width: min(260px, 80%);
    padding: 8px 10px;
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--ring);
    border-radius: 8px;
    box-shadow: 0 4px 16px var(--ring);
    font-size: 12px;
    line-height: 1.4;
    pointer-events: none;
  }
  .tip.pinned {
    pointer-events: auto;
    padding-right: 40px;
  }
  .t {
    font-weight: 600;
    margin-bottom: 2px;
  }
  .l {
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .x {
    position: absolute;
    top: -4px;
    right: -4px;
    width: 44px;
    height: 44px;
    border: 0;
    background: none;
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
    color: var(--ink-2);
  }
</style>
