<script>
  // Reader-paced stepper: one persistent stage, one short card per step.
  // Advance by the Next button, arrow keys / space, swipe, or tapping the stage
  // (right side forward, left quarter back) on steps that aren't interactive.
  // Each step: { id, chapter, html? | card?: { component, props }, cardMode?: 'side'|'center'|'wide',
  //              stage?: dot spec | { component, props }, interactive?: bool }
  import { onMount } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import DotField from '../stage/DotField.svelte';

  let { steps, chapters, nodes = [], ctx = {}, title = '' } = $props();

  let index = $state(0);
  let cardEl = $state(null);
  // The card element is reused from step to step, so a new step would open wherever the last
  // one was scrolled to; start every step at the top, ready to read.
  $effect(() => {
    index;
    if (cardEl) cardEl.scrollTop = 0;
  });
  let plain = $state(false);
  let touchStart = null;

  const step = $derived(steps[index]);
  const mode = $derived(step.cardMode ?? 'side');
  // A component stage can name the dot layout to keep underneath it (stage.under).
  const dotSpec = $derived(step.stage && !step.stage.component ? step.stage : (step.stage?.under ?? lastDotSpec(index)));
  const stageComponent = $derived(step.stage?.component ? step.stage : null);

  // Component stages sit over the dots; keep the last dot layout underneath for continuity.
  function lastDotSpec(i) {
    for (let j = i; j >= 0; j--) if (steps[j].stage && !steps[j].stage.component) return steps[j].stage;
    return { layout: 'cloud', color: 'none' };
  }

  const chapterStats = $derived(
    chapters.map((c) => {
      const idx = steps.map((s, i) => (s.chapter === c.id ? i : -1)).filter((i) => i >= 0);
      const first = idx[0] ?? 0;
      const last = idx[idx.length - 1] ?? 0;
      const fill = index < first ? 0 : index >= last ? 1 : (index - first + 1) / idx.length;
      return { ...c, first, fill, active: index >= first && index <= last };
    }),
  );
  const currentChapter = $derived(chapterStats.find((c) => c.active));

  function go(i) {
    const next = Math.max(0, Math.min(steps.length - 1, i));
    if (next === index) return;
    index = next;
    history.replaceState(null, '', '#' + steps[index].id);
  }
  const next = () => go(index + 1);
  const prev = () => go(index - 1);

  function onKey(e) {
    // A control that already handled the key (radio groups, heatmap cells) keeps it.
    if (plain || e.defaultPrevented) return;
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    if (['ArrowRight', 'PageDown'].includes(e.key) || (e.key === ' ' && t?.tagName !== 'BUTTON')) {
      e.preventDefault();
      next();
    } else if (['ArrowLeft', 'PageUp'].includes(e.key)) {
      e.preventDefault();
      prev();
    } else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(steps.length - 1);
  }

  function onStageTap(e) {
    if (step.interactive) return;
    const rect = e.currentTarget.getBoundingClientRect();
    if (e.clientX - rect.left < rect.width * 0.25) prev();
    else next();
  }

  // A swipe that starts on something that handles horizontal drags itself (sliders, charts
  // with touch-action: pan-y, horizontally scrolling tables) belongs to that control.
  function ownsDrag(el, root) {
    for (let n = el; n && n !== root; n = n.parentElement) {
      if (n.matches?.('input, select, textarea, [role=slider], [contenteditable]')) return true;
      const cs = getComputedStyle(n);
      if (cs.touchAction !== 'auto' && cs.touchAction !== 'manipulation') return true;
      if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && n.scrollWidth > n.clientWidth + 1) return true;
    }
    return false;
  }
  function onTouchStart(e) {
    const t = e.changedTouches[0];
    touchStart = ownsDrag(e.target, e.currentTarget) ? null : { x: t.clientX, y: t.clientY, time: e.timeStamp };
  }
  function onTouchEnd(e) {
    if (!touchStart) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStart.x;
    const dy = t.clientY - touchStart.y;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5 && e.timeStamp - touchStart.time < 600) {
      if (dx < 0) next();
      else prev();
    }
    touchStart = null;
  }

  // Deep links: on load, and when the reader edits the hash or follows an in-page #step link.
  function fromHash() {
    const id = decodeURIComponent(location.hash.slice(1));
    const i = steps.findIndex((s) => s.id === id);
    if (i >= 0) index = i;
  }
  onMount(fromHash);
</script>

<svelte:window onkeydown={onKey} onhashchange={fromHash} />

{#if plain}
  <article class="plain">
    <button class="ui link" onclick={() => (plain = false)}>Back to the interactive story</button>
    <!-- move focus into the article so keyboard and screen-reader users land at its start -->
    <h1 tabindex="-1" {@attach (el) => el.focus()}>{title}</h1>
    {#each chapters as c (c.id)}
      <h2>{c.title}</h2>
      {#each steps.filter((s) => s.chapter === c.id && (s.plainHtml || s.html)) as s (s.id)}
        {@const h = s.plainHtml ?? s.html}
        <div class="plain-step">{@html typeof h === 'function' ? h(ctx) : h}</div>
      {/each}
    {/each}
  </article>
{:else}
  <div class="story" class:center={mode === 'center'} class:wide={mode === 'wide'}>
    <a class="skip ui" href="#plain" onclick={(e) => { e.preventDefault(); plain = true; }}>Read as a plain article</a>
    <h1 class="sr-only">{title}</h1>

    <header class="top ui">
      <nav class="segments" aria-label="Chapters">
        {#each chapterStats as c (c.id)}
          <button
            class="seg"
            class:active={c.active}
            onclick={() => go(c.first)}
            aria-label={`Go to chapter: ${c.title}`}
            aria-current={c.active ? 'step' : undefined}
          >
            <span class="bar"><span class="fill" style:width={c.fill * 100 + '%'}></span></span>
            <span class="seg-title">{c.title}</span>
          </button>
        {/each}
      </nav>
    </header>

    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div
      class="stage"
      class:tappable={!step.interactive}
      onclick={onStageTap}
      ontouchstart={onTouchStart}
      ontouchend={onTouchEnd}
    >
      <!-- Behind a full chart the dots are hidden outright: their layer reaches under the
           (transparent) text column, where they would otherwise show. -->
      <div class="dots" class:dimmed={!!stageComponent?.overlay} class:hidden={!!stageComponent && !stageComponent.overlay}>
        <DotField {nodes} spec={dotSpec} interactive={!!step.interactive && !stageComponent} />
      </div>
      {#if stageComponent}
        <!-- Consecutive overlay steps share one card (keyed 'overlay'), so moving between them
             swaps the chart inside it in place instead of fading the card out and back in. -->
        {#key stageComponent.overlay ? 'overlay' : step.id}
          {#if stageComponent.overlay}
            <!-- A chart that interrupts a run of dot steps floats over the faded dots as a card,
                 so the dots never leave the screen. Transitions are |global because Svelte only
                 plays local ones when their own block toggles, not a parent {#if}/{#key}. -->
            <div
              class="stage-component overlay"
              in:scale|global={{ start: 0.97, opacity: 0, duration: 500, delay: 120 }}
              out:fade|global={{ duration: 250 }}
            >
              <!-- Inside the card, one chart fades out and the next fades in (local transitions:
                   they play when this key changes, not when the card itself appears or leaves). -->
              {#key step.id}
                <div class="overlay-page" in:fade={{ duration: 260, delay: 180 }} out:fade={{ duration: 180 }}>
                  <stageComponent.component {...stageComponent.props ?? {}} {ctx} {nodes} />
                </div>
              {/key}
            </div>
          {:else}
            <!-- Local on purpose: it cross-fades between two charts, but appears without fading
                 over the dots, which only the overlay card does. -->
            <div class="stage-component" transition:fade={{ duration: 280 }}>
              <stageComponent.component {...stageComponent.props ?? {}} {ctx} {nodes} />
            </div>
          {/if}
        {/key}
      {/if}
    </div>

    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <section class="card" aria-live="polite" ontouchstart={onTouchStart} ontouchend={onTouchEnd} bind:this={cardEl}>
      {#key step.id}
        <div class="card-inner">
          {#if currentChapter && step.id === steps[currentChapter.first].id && mode !== 'center'}
            <p class="kicker ui">{currentChapter.title}</p>
          {/if}
          {#if step.html}<div class="prose">{@html typeof step.html === 'function' ? step.html(ctx) : step.html}</div>{/if}
          {#if step.card}<step.card.component {...step.card.props ?? {}} {ctx} {nodes} onnext={next} />{/if}
        </div>
      {/key}
      <div class="nav ui">
        <button class="prev" onclick={prev} disabled={index === 0} aria-label="Previous step">←</button>
        <span class="count tabular" aria-hidden="true">{index + 1} / {steps.length}</span>
        <button class="next" onclick={next} disabled={index === steps.length - 1} aria-label="Next step">
          {index === 0 ? 'Start' : 'Next'} →
        </button>
      </div>
    </section>
  </div>
{/if}

<style>
  .story {
    position: fixed;
    inset: 0;
    display: grid;
    grid-template-columns: minmax(300px, 380px) 1fr;
    grid-template-rows: auto 1fr;
    grid-template-areas: 'top top' 'card stage';
    height: 100dvh;
    overflow: hidden;
  }
  .story.wide {
    grid-template-columns: minmax(300px, 440px) 1fr;
  }
  .top {
    grid-area: top;
    padding: env(safe-area-inset-top, 0px) var(--gutter) 2px;
    z-index: 3;
  }
  .segments {
    display: flex;
    gap: 6px;
  }
  .seg {
    flex: 1;
    min-width: 0;
    min-height: 44px;
    /* Buttons center their content vertically; pin it to the top so every bar sits on one
       line even when only the current chapter shows its title (phones). */
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding: 16px 0 2px;
    border: 0;
    background: none;
    cursor: pointer;
    text-align: left;
  }
  .bar {
    display: block;
    height: 3px;
    border-radius: 2px;
    background: var(--grid);
    overflow: hidden;
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--ink);
    transition: width 0.4s var(--ease);
  }
  .seg-title {
    display: block;
    margin-top: 5px;
    font-size: 11px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .seg.active .seg-title {
    color: var(--ink);
    font-weight: 600;
  }
  .stage {
    grid-area: stage;
    position: relative;
    min-height: 0;
  }
  .stage.tappable {
    cursor: pointer;
  }
  .stage-component {
    position: absolute;
    inset: 0;
    background: var(--bg);
    overflow: auto;
  }
  .dots {
    position: absolute;
    inset: 0;
    /* Brighten only once the card over them has mostly faded, so the two don't overlap. */
    transition: opacity 0.4s var(--ease) 0.2s;
  }
  .dots.dimmed {
    opacity: 0.55;
    transition-delay: 0s;
  }
  .dots.hidden {
    opacity: 0;
    transition: none;
  }
  /* See-through, slightly blurred card: the dots stay visible underneath, just quieter. */
  .stage-component.overlay {
    inset: 20px 24px 24px;
    border: 1px solid var(--ring);
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg) 80%, transparent);
    -webkit-backdrop-filter: blur(3px);
    backdrop-filter: blur(3px);
    box-shadow: 0 12px 40px rgb(0 0 0 / 0.18);
  }
  .overlay-page {
    position: absolute;
    inset: 0;
    overflow: auto;
  }
  .stage-component.overlay :global(.frame) {
    background: transparent;
  }
  .card {
    grid-area: card;
    display: flex;
    flex-direction: column;
    justify-content: safe center;
    gap: 18px;
    padding: 12px 24px 24px max(var(--gutter), 32px);
    min-height: 0;
    overflow-y: auto;
    z-index: 2;
  }
  .card-inner {
    animation: rise 0.45s var(--ease);
  }
  .kicker {
    margin: 0 0 10px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .prose :global(p) {
    margin: 0 0 0.8em;
    font-size: 1.12rem;
    line-height: 1.5;
  }
  .prose :global(h2) {
    margin: 0 0 0.4em;
    font-size: 2.1rem;
    line-height: 1.1;
    font-weight: 700;
  }
  .prose :global(.big) {
    font-size: 1.35rem;
  }
  .prose :global(.note) {
    font-family: var(--font-ui);
    font-size: 0.82rem;
    color: var(--muted);
  }
  /* Pinned to the bottom of the card so Next/Prev stay reachable when the text scrolls. */
  .nav {
    position: sticky;
    bottom: 0;
    margin-top: auto; /* same place on every step, however short the card */
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0;
    background: var(--bg);
    /* covers the card's bottom padding, which text would otherwise scroll through */
    box-shadow: 0 24px 0 var(--bg);
  }
  .nav button {
    min-height: 44px;
    padding: 0 16px;
    border-radius: 999px;
    border: 1px solid var(--ring);
    background: var(--surface);
    cursor: pointer;
    font-weight: 600;
  }
  .nav .prev {
    min-width: 44px;
    padding: 0;
  }
  @media (min-width: 761px) {
    /* The wide card (methodology) keeps Back/Next where every other step has them. */
    .story.wide .nav {
      max-width: calc(380px - max(var(--gutter), 32px) - 24px);
    }
  }
  .nav .next {
    margin-left: auto;
    background: var(--ink);
    color: var(--bg);
    border-color: var(--ink);
  }
  .nav button:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .count {
    font-size: 12px;
    color: var(--muted);
  }

  /* Center mode: text-only beats sit over the stage. */
  .story.center .card {
    grid-area: stage;
    grid-column: 1 / -1;
    align-items: center;
    text-align: center;
    background: var(--scrim);
    padding: 24px var(--gutter);
  }
  .story.center .card-inner,
  .story.center .nav {
    width: 100%;
    max-width: var(--card-max);
  }
  .story.center .stage {
    grid-column: 1 / -1;
  }
  /* The title card's buttons sit exactly where the side card puts them, so Start and Next
     don't jump when the first step gives way to the second. */
  @media (min-width: 761px) {
    .story.center .card {
      position: relative;
      padding-bottom: 96px;
    }
    .story.center .nav {
      position: absolute;
      left: max(var(--gutter), 32px);
      bottom: 24px;
      width: calc(380px - max(var(--gutter), 32px) - 24px);
      max-width: none;
    }
  }

  .skip {
    position: absolute;
    left: -999px;
    top: 8px;
    z-index: 10;
  }
  .skip:focus {
    left: 8px;
    padding: 8px 12px;
    background: var(--surface);
    border-radius: 6px;
  }

  @media (max-width: 760px) {
    .stage-component.overlay {
      inset: 6px 8px 8px;
    }
    .story,
    .story.wide {
      grid-template-columns: minmax(0, 1fr);
      /* The card row is reserved on every step so the stage is the same size throughout. */
      grid-template-rows: auto minmax(0, 1fr) 46dvh;
      grid-template-areas: 'top' 'stage' 'card';
    }
    .card {
      /* Fills its reserved row; long cards scroll inside it instead of resizing the stage. */
      height: 100%;
      padding: 14px var(--gutter) 12px;
      gap: 10px;
      justify-content: flex-start;
      border-top: 1px solid var(--ring);
      background: var(--bg);
    }
    .nav {
      padding-bottom: max(6px, env(safe-area-inset-bottom));
    }
    .prose :global(p) {
      font-size: 1.02rem;
    }
    .prose :global(h2) {
      font-size: 1.6rem;
    }
    .seg-title {
      display: none;
    }
    .seg.active .seg-title {
      display: block;
    }
    .seg.active {
      flex: 3;
    }
    .story.center .card {
      grid-area: auto;
      grid-row: 2 / 4;
      height: auto;
      max-height: none;
      border-top: 0;
      padding-bottom: 12px; /* same as the side card, so the buttons don't move */
      justify-content: safe center;
    }
  }

  .plain {
    max-width: 40rem;
    margin: 0 auto;
    padding: 32px var(--gutter) 80px;
    font-size: 1.1rem;
    line-height: 1.6;
  }
  .plain h1:focus {
    outline: none;
  }
  .link {
    border: 0;
    background: none;
    padding: 0;
    text-decoration: underline;
    cursor: pointer;
    color: var(--ink-2);
  }

  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
</style>
