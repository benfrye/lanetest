<script>
  import { untrack } from 'svelte';
  // Labeled range input with a live value readout. The input itself is 44px tall for touch.
  let { label, value = $bindable(), min, max, step, format = (v) => v, oninput = null, hint = '', id, ends = null } = $props();
  const uid = untrack(() => id) ?? `sl-${Math.random().toString(36).slice(2, 8)}`;
</script>

<div class="slider">
  <div class="row">
    <label for={uid}>{label}</label>
    <output for={uid} class="tabular">{format(value)}</output>
  </div>
  <input
    id={uid}
    type="range"
    {min}
    {max}
    {step}
    bind:value
    aria-valuetext={String(format(value))}
    oninput={() => oninput?.(+value)}
  />
  {#if ends}
    <div class="ends" aria-hidden="true"><span>{ends[0]}</span><span>{ends[1]}</span></div>
  {/if}
  {#if hint}<p class="hint">{hint}</p>{/if}
</div>

<style>
  .slider {
    min-width: 0;
    flex: 1 1 200px;
  }
  .row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    font-size: 12.5px;
  }
  label {
    color: var(--ink-2);
    font-weight: 500;
  }
  output {
    color: var(--ink);
    font-weight: 650;
    font-size: 14px;
  }
  input {
    display: block;
    width: 100%;
    height: 32px;
    margin: 0;
    background: transparent;
    accent-color: var(--ink);
    cursor: pointer;
    -webkit-appearance: none;
    appearance: none;
  }
  input::-webkit-slider-runnable-track {
    height: 4px;
    border-radius: 2px;
    background: var(--axis);
  }
  input::-moz-range-track {
    height: 4px;
    border-radius: 2px;
    background: var(--axis);
  }
  input::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 24px;
    height: 24px;
    margin-top: -10px;
    border-radius: 50%;
    background: var(--ink);
    border: 3px solid var(--bg);
    box-shadow: 0 0 0 1px var(--ink);
  }
  input::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--ink);
    border: 3px solid var(--bg);
  }
  /* bigger hit area without a bigger visual */
  @media (pointer: coarse) {
    input {
      height: 44px;
    }
  }
  .ends {
    display: flex;
    justify-content: space-between;
    margin-top: -4px;
    font-size: 11px;
    color: var(--muted);
  }
  .hint {
    margin: 2px 0 0;
    font-size: 11.5px;
    color: var(--muted);
  }
</style>
