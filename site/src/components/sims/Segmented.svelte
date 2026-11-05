<script>
  // Radio-group segmented control: arrow keys move the selection, 44px targets.
  let { options, value = $bindable(), label, onchange = null, small = false, item = null } = $props();
  let root;

  function pick(v) {
    if (v === value) return;
    value = v;
    onchange?.(v);
  }
  function onkey(e, i) {
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const j = (i + d + options.length) % options.length;
    pick(options[j].value);
    root?.querySelectorAll('button')[j]?.focus();
  }
</script>

<div class="seg" class:small role="radiogroup" aria-label={label} bind:this={root}>
  {#each options as o, i (o.value)}
    <button
      type="button"
      role="radio"
      aria-checked={o.value === value}
      tabindex={o.value === value ? 0 : -1}
      onclick={() => pick(o.value)}
      onkeydown={(e) => onkey(e, i)}
      title={o.title ?? null}
    >
      {#if item}{@render item(o)}{:else}<span>{o.label}</span>{/if}
    </button>
  {/each}
</div>

<style>
  .seg {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 3px;
    border-radius: 12px;
    background: var(--surface-2);
    max-width: 100%;
  }
  button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 40px;
    min-width: 44px;
    padding: 0 12px;
    border: 0;
    border-radius: 9px;
    background: transparent;
    color: var(--ink-2);
    font: 500 13px/1.2 var(--font-ui);
    cursor: pointer;
    text-align: left;
  }
  .small button {
    padding: 0 10px;
    font-size: 12.5px;
  }
  button[aria-checked='true'] {
    background: var(--surface);
    color: var(--ink);
    font-weight: 600;
    box-shadow: 0 0 0 1px var(--ring), 0 1px 2px rgba(0, 0, 0, 0.06);
  }
  button:hover {
    color: var(--ink);
  }
  @media (pointer: coarse) {
    button {
      min-height: 44px;
    }
  }
</style>
