<script>
  // Archetype identity: shape + color + label, always together. Text stays in ink.
  import { ARCHETYPE_BY_ID, ARCHETYPES } from './util.js';
  import { shapePath } from '../../lib/archetypes.js';

  let { id, label = true, size = 12, muted = false } = $props();
  const a = $derived(ARCHETYPE_BY_ID[id] ?? ARCHETYPES[ARCHETYPES.length - 1]);
</script>

<span class="ac ui" class:muted>
  <svg width={size} height={size} viewBox="-7 -7 14 14" aria-hidden="true">
    <path d={shapePath(a.shape, 5.2)} style:fill={`var(${a.token})`} />
  </svg>
  {#if label}<span class="lbl">{a.label}</span>{/if}
</span>

<style>
  .ac {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    white-space: nowrap;
    color: var(--ink);
    font-weight: 600;
  }
  .ac svg {
    flex: none;
    overflow: visible;
  }
  .muted .lbl {
    color: var(--ink-2);
    font-weight: 500;
  }
</style>
