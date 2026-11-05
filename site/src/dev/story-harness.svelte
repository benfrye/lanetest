<script>
  // Mirrors Story.svelte's geometry: desktop = 380px card column + stage; mobile (<=760px)
  // = stage on top, card as a bottom sheet capped at 46dvh.
  import { untrack } from 'svelte';
  import { loadContext } from '../lib/data.js';
  import { createReader } from './story-harness.state.svelte.js';

  const modules = import.meta.glob('../components/story/*.svelte', { eager: true });
  const COMPONENTS = Object.fromEntries(
    Object.entries(modules).map(([path, m]) => [path.split('/').pop().replace('.svelte', ''), m.default]),
  );
  const CARDS = new Set(['GuessFirst', 'QuizPairs', 'Methodology']);
  const SAMPLE_PROSE = {
    GuessFirst: 'Before we show you: which kind of Democrat ran furthest ahead of Harris?',
    QuizPairs: 'Try it yourself. Each pair ran in places that voted about the same in 2024.',
    Methodology: '',
  };

  const q = new URLSearchParams(location.search);
  const name = q.get('c') ?? 'RawVsAdjusted';
  let extra = {};
  try {
    extra = JSON.parse(q.get('p') ?? '{}');
  } catch {
    extra = {};
  }
  const Comp = COMPONENTS[name];
  const isCard = CARDS.has(name);

  let ctx = $state.raw(null);
  let err = $state('');
  let log = $state([]);

  loadContext()
    .then((c) => {
      const env = c.data.params?.environment?.presets?.history?.loc ?? 0;
      c.reader = createReader(env);
      // The sim worker resolves data/ against /dev/ here; the harness doesn't need it.
      c.simReady?.catch(() => {});
      ctx = c;
    })
    .catch((e) => (err = String(e)));

  const push = (s) => untrack(() => (log = [...log, s]));
  const onnext = () => push('onnext()');
  const onpair = (ids) => push('onpair(' + JSON.stringify(ids) + ')');
</script>

{#if err}
  <p class="err ui">{err}</p>
{:else if !Comp}
  <p class="err ui">Unknown component “{name}”. Available: {Object.keys(COMPONENTS).join(', ')}</p>
{:else if ctx}
  <div class="h">
    <header class="top ui">{name} · <span class="log">{log.slice(-2).join(' · ')}</span></header>
    <div class="stage">
      {#if !isCard}
        <div class="stage-component">
          <Comp {...extra} {ctx} nodes={ctx.nodes} />
        </div>
      {:else}
        <div class="placeholder ui">stage</div>
      {/if}
    </div>
    <section class="card">
      <div class="card-inner">
        {#if isCard}
          {#if SAMPLE_PROSE[name]}<div class="prose"><p>{SAMPLE_PROSE[name]}</p></div>{/if}
          <Comp {...extra} {ctx} nodes={ctx.nodes} {onnext} {onpair} />
        {:else}
          <div class="prose"><p>Card text for this step sits here. The stage component fills the area to the right.</p></div>
        {/if}
      </div>
      <div class="nav ui"><button>←</button><button class="next">Next →</button></div>
    </section>
  </div>
{/if}

<style>
  .h {
    position: fixed;
    inset: 0;
    display: grid;
    grid-template-columns: minmax(300px, 380px) 1fr;
    grid-template-rows: 60px 1fr;
    grid-template-areas: 'top top' 'card stage';
    height: 100dvh;
    overflow: hidden;
  }
  .top {
    grid-area: top;
    padding: 12px 16px;
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
  }
  .stage {
    grid-area: stage;
    position: relative;
    min-height: 0;
  }
  .stage-component {
    position: absolute;
    inset: 0;
    background: var(--bg);
    overflow: auto;
  }
  .placeholder {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    color: var(--muted);
    background: var(--surface-2);
  }
  .card {
    grid-area: card;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 18px;
    padding: 12px 24px 24px 32px;
    min-height: 0;
    overflow-y: auto;
  }
  .prose p {
    margin: 0 0 0.8em;
    font-size: 1.12rem;
    line-height: 1.5;
  }
  .nav {
    display: flex;
    gap: 12px;
  }
  .nav button {
    min-height: 44px;
    min-width: 44px;
    padding: 0 16px;
    border-radius: 999px;
    border: 1px solid var(--ring);
    background: var(--surface);
  }
  .nav .next {
    margin-left: auto;
    background: var(--ink);
    color: var(--bg);
  }
  .err {
    padding: 20px;
  }
  @media (max-width: 760px) {
    .h {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: 40px minmax(0, 1fr) auto;
      grid-template-areas: 'top' 'stage' 'card';
    }
    .card {
      max-height: 46dvh;
      min-height: 40dvh;
      padding: 14px 16px 12px;
      gap: 10px;
      justify-content: flex-start;
      border-top: 1px solid var(--ring);
    }
    .prose p {
      font-size: 1.02rem;
    }
  }
</style>
