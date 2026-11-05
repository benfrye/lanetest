<script>
  // Archetype identity mark: shape + color + label (never color alone).
  import { ARCHETYPE_BY_ID, shapePath } from '../../lib/archetypes.js';
  let { id, label = true, size = 12, short = false } = $props();
  const a = $derived(ARCHETYPE_BY_ID[id]);
</script>

{#if a}
  <span class="achip">
    <svg width={size} height={size} viewBox="-7 -7 14 14" aria-hidden="true">
      <path d={shapePath(a.shape, 5.2)} style:fill="var({a.token})" />
    </svg>
    {#if label}<span>{short ? a.label.replace('Mainstream liberal', 'Mainstream') : a.label}</span>{/if}
  </span>
{/if}

<style>
  .achip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
  }
  svg {
    flex: none;
    overflow: visible;
  }
</style>
