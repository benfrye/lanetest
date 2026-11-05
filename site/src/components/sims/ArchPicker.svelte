<script>
  // Archetype picker: chip segmented control on wide stages, a native select on narrow ones
  // (keeps the chart above the fold on phones). Identity is always shape + color + label.
  import { ARCHETYPES, ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import Segmented from './Segmented.svelte';
  import ArchChip from './ArchChip.svelte';

  let { value = $bindable(), ids = ARCHETYPES.map((a) => a.id), label = 'Type of Democrat', compact = false, onchange = null } = $props();
  const uid = `ap-${Math.random().toString(36).slice(2, 8)}`;
  const opts = $derived(ids.map((id) => ({ value: id, label: ARCHETYPE_BY_ID[id].label })));
</script>

{#if compact}
  <div class="sel">
    <label for={uid}>{label}</label>
    <span class="cur"><ArchChip id={value} label={false} size={14} /></span>
    <select id={uid} bind:value onchange={() => onchange?.(value)}>
      {#each opts as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
    </select>
  </div>
{:else}
  <Segmented {label} options={opts} bind:value {onchange} small>
    {#snippet item(o)}<ArchChip id={o.value} />{/snippet}
  </Segmented>
{/if}

<style>
  .sel {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  label {
    font-weight: 500;
  }
  .cur {
    display: inline-flex;
  }
  select {
    min-height: 44px;
    padding: 0 10px;
    border: 1px solid var(--axis);
    border-radius: 9px;
    background: var(--surface);
    color: var(--ink);
    font: 600 14px var(--font-ui);
  }
</style>
