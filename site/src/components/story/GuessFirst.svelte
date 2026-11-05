<script>
  // Card: "which kind of Democrat ran furthest ahead of Harris?" Five archetype buttons.
  // Stores ctx.reader.guess, then calls onnext. "Skip" advances without a guess.
  import ArchChip from './ArchChip.svelte';
  import { ARCHETYPES, prefersReducedMotion } from './util.js';

  let { ctx, nodes = [], onnext, prompt = '', ...rest } = $props();

  let picked = $state(ctx?.reader?.guess ?? null);
  let timer;

  function pick(id) {
    picked = id;
    if (ctx?.reader) ctx.reader.guess = id;
    clearTimeout(timer);
    // A short beat so the selection registers before the step advances.
    timer = setTimeout(() => onnext?.(), prefersReducedMotion() ? 0 : 280);
  }
  function skip(e) {
    e.preventDefault();
    if (ctx?.reader) ctx.reader.guess = null;
    picked = null;
    onnext?.();
  }
</script>

<div class="guess ui">
  {#if prompt}<p class="prompt">{prompt}</p>{/if}
  <div class="opts" role="group" aria-label="Your guess">
    {#each ARCHETYPES as a (a.id)}
      <button class="opt" aria-pressed={picked === a.id} onclick={() => pick(a.id)}>
        <ArchChip id={a.id} size={14} />
      </button>
    {/each}
  </div>
  <a class="skip" href="#skip" onclick={skip}>Skip, just show me</a>
</div>

<style>
  .guess {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .prompt {
    margin: 0;
    font-size: 14px;
    color: var(--ink-2);
  }
  .opts {
    display: grid;
    /* Wide enough for "Mainstream liberal" on one line: one column in the desktop side card,
       two side by side on a phone, where the card is the full screen width. */
    grid-template-columns: repeat(auto-fill, minmax(172px, 1fr));
    gap: 8px;
  }
  .opt {
    min-height: 44px;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    border: 1px solid var(--ring);
    border-radius: var(--radius);
    background: var(--surface);
    cursor: pointer;
    text-align: left;
    font-size: 14px;
    transition: border-color 0.15s, background 0.15s;
  }
  .opt:hover {
    border-color: var(--axis);
    background: var(--surface-2);
  }
  .opt[aria-pressed='true'] {
    border-color: var(--ink);
    box-shadow: inset 0 0 0 1px var(--ink);
  }
  .skip {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    font-size: 13px;
    color: var(--ink-2);
  }
</style>
