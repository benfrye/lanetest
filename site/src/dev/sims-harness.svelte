<script>
  // Loads the real ctx and renders one sim component inside a stage-sized box.
  //   ?c=ArchetypeSim&mode=run         component + its mode prop
  //   &frame=auto|desktop|mobile|full  desktop: (vw − 380) × (vh − 40) at the right, like Story;
  //                                    mobile: top ~55% of the screen above a fake text sheet
  //   &guess=progressive&env=5&pi=1.3  seed ctx.reader
  //   &theme=dark|light                force a theme (otherwise prefers-color-scheme)
  import { loadContext } from '../lib/data.js';
  import { createSimClient } from '../lib/sim/client.js';
  import { envCenter } from '../lib/sim/model.js';
  import ArchetypeSim from '../components/sims/ArchetypeSim.svelte';
  import BelieveHeatmap from '../components/sims/BelieveHeatmap.svelte';
  import MatchupMatrix from '../components/sims/MatchupMatrix.svelte';
  import PrimarySim from '../components/sims/PrimarySim.svelte';
  import BuildYourOwn from '../components/sims/BuildYourOwn.svelte';
  import AsPresident from '../components/sims/AsPresident.svelte';

  const COMPONENTS = { ArchetypeSim, BelieveHeatmap, MatchupMatrix, PrimarySim, BuildYourOwn, AsPresident };
  const q = new URLSearchParams(location.search);
  const name = q.get('c') ?? 'ArchetypeSim';
  const Comp = COMPONENTS[name];
  const props = {};
  for (const [k, v] of q) if (!['c', 'frame', 'guess', 'env', 'pi', 'theme'].includes(k)) props[k] = v;
  if (q.get('theme')) document.documentElement.dataset.theme = q.get('theme');

  let vw = $state(window.innerWidth);
  const frameQ = q.get('frame') ?? 'auto';
  const frame = $derived(frameQ === 'auto' ? (vw > 760 ? 'desktop' : 'mobile') : frameQ);

  let reader = $state({ guess: q.get('guess'), quizAnswers: [], env: 0, pi: q.get('pi') ? +q.get('pi') : null });
  let ctx = $state.raw(null);
  let err = $state('');

  loadContext()
    .then((c) => {
      // loadContext's worker resolves data/ against location (= /dev/…); give it a root-relative URL.
      c.simReady.catch(() => {});
      c.sim.terminate();
      const sim = createSimClient();
      const simReady = sim.loadUrl('/data/model_params.json');
      const env = c.data.params.environment;
      reader.env = q.get('env') != null ? +q.get('env') : envCenter(env.presets[env.default_preset]);
      ctx = { ...c, sim, simReady, reader };
      window.__ctx = ctx;
    })
    .catch((e) => (err = String(e?.stack ?? e)));
</script>

<svelte:window bind:innerWidth={vw} />

<div class="frame {frame}">
  <div class="topbar ui">
    {#each Object.keys(COMPONENTS) as k (k)}
      <a href="?c={k}&frame={frameQ}" class:on={k === name}>{k}</a>
    {/each}
  </div>
  <div class="stage">
    <div class="stage-component">
      {#if err}<pre>{err}</pre>
      {:else if !Comp}<p>Unknown component {name}</p>
      {:else if ctx}<Comp {ctx} nodes={ctx.nodes} {...props} />
      {:else}<p class="ui loading">Loading…</p>{/if}
    </div>
  </div>
  {#if frame !== 'full'}
    <div class="card">
      <p>Text card placeholder. The story's prose sits here; the stage is to the {frame === 'mobile' ? 'top' : 'right'}.</p>
      <p class="ui small">reader: guess={reader.guess ?? '–'} env={reader.env} pi={reader.pi ?? 'sampled'}</p>
    </div>
  {/if}
</div>

<style>
  .frame {
    position: fixed;
    inset: 0;
    display: grid;
  }
  .frame.desktop {
    grid-template-columns: 380px 1fr;
    grid-template-rows: 40px 1fr;
    grid-template-areas: 'top top' 'card stage';
  }
  .frame.mobile {
    grid-template-columns: 1fr;
    grid-template-rows: 30px 54dvh 1fr;
    grid-template-areas: 'top' 'stage' 'card';
  }
  .frame.full {
    grid-template-rows: 30px 1fr;
    grid-template-areas: 'top' 'stage';
  }
  .topbar {
    grid-area: top;
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 0 12px;
    font-size: 11px;
    overflow: hidden;
    white-space: nowrap;
    border-bottom: 1px solid var(--grid);
  }
  .topbar a {
    color: var(--muted);
  }
  .topbar a.on {
    color: var(--ink);
    font-weight: 600;
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
  .card {
    grid-area: card;
    padding: 16px 24px;
    border-right: 1px solid var(--grid);
    border-top: 1px solid var(--grid);
    color: var(--ink-2);
    overflow: hidden;
  }
  .small {
    font-size: 12px;
  }
  .loading {
    padding: 16px;
  }
</style>
