<script>
  // Slide 22: the state ladder. Every state (and the Maine/Nebraska districts) lined up from
  // most Democratic to most Republican, each as wide as its electoral votes, with the 270 line.
  // In the model a lane and the national mood move every state by the same amount, so the
  // ladder's order is fixed (each state's starting lean: 2024 margin plus psi × its 2026
  // swing; the home state gets its bonus) and what changes is how far along it the
  // candidate's states reach. Colors are each state's chance from simCustom; the moving
  // marker is the electoral votes in states the candidate is favored to carry.
  import { untrack } from 'svelte';
  import { ARCHETYPES, ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import Slider from './Slider.svelte';
  import ArchWheel from './ArchWheel.svelte';
  import { PROB_BINS, probFill, fmtE, pct, pctRange, params, envSlider, piOpt, envPoint, defaultEnvCenter, latest, thinNote, lanes2028 } from './shared.js';

  let { ctx, nodes } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once

  const P = params(ctx0);
  const es = envSlider(ctx0);
  const coords = P.style?.coords ?? {};
  const psi = P.lean?.psi ?? 0;
  const homeBonus = P.home_effect?.mean ?? 2;
  const units = (P.units ?? []).map((u) => ({ id: u.id, name: u.name, ev: u.ev, parent: u.parent ?? null, lean: u.m24 + psi * (u.rel26 ?? 0) }));
  const evTotal = P.national?.ev_total ?? 538;
  const evWin = P.national?.ev_win ?? 270;
  const states = units.filter((u) => !u.parent).sort((a, b) => a.name.localeCompare(b.name));
  if (ctx0.reader && ctx0.reader.env == null) ctx0.reader.env = defaultEnvCenter(ctx0);

  let lane = $state(ctx0.reader?.guess && coords[ctx0.reader.guess] && ctx0.reader.guess !== 'center_populist' ? ctx0.reader.guess : 'mainstream_liberal');
  let home = $state('');

  let res = $state(null);
  let error = $state('');
  const go = latest(
    (o) => ctx.simReady.then(() => ctx.sim.simCustom(o, {}, { channel: 'ladder' })),
    (r) => (res = r),
    (e) => (error = e.message),
  );
  $effect(() => {
    const c = coords[lane] ?? { L: 1, P: 0 };
    go({ L: c.L, P: c.P, home: home || null, opponent: 'generic', env: envPoint(ctx.reader.env), pi: piOpt(ctx.reader), u: 0 });
  });

  // Ladder order: most Democratic first. The home state (and its districts) jump by the bonus.
  const homeOf = (u) => u.id === home || u.parent === home;
  const order = $derived([...units].sort((a, b) => b.lean + (homeOf(b) ? homeBonus : 0) - (a.lean + (homeOf(a) ? homeBonus : 0))));
  const ladder = $derived.by(() => {
    let cum = 0;
    return order.map((u) => {
      const row = { ...u, start: cum, p: res?.stateP?.[u.id] ?? null };
      cum += u.ev;
      return row;
    });
  });
  // Electoral votes in states the candidate is favored in, and the state that casts vote 270.
  const reach = $derived(ladder.reduce((s, u) => s + (u.p != null && u.p >= 0.5 ? u.ev : 0), 0));
  const tipping = $derived(ladder.find((u) => u.start < evWin && u.start + u.ev >= evWin));
  // The closest states: the ones nearest the tipping point on either side.
  const close = $derived.by(() => {
    if (!tipping) return [];
    const i = ladder.indexOf(tipping);
    return ladder.slice(Math.max(0, i - 3), i + 4).filter((u) => !u.parent || u.ev >= 1);
  });

  let w = $state(0);
  const x = (ev) => (ev / evTotal) * w;
  const label = (a) => ARCHETYPE_BY_ID[a]?.label ?? a;
  const voteLabel = (e) => (Math.abs(e) < 0.05 ? 'exactly even' : fmtE(e, 1));
  const short = (u) => (u.parent ? u.id.replace(/^(..)-?(\d)$/, '$1-$2') : u.id);
</script>

<SimFrame
  {ctx}
  title="Which states does it come down to?"
  dek="Every state, from most Democratic to most Republican, each as wide as its electoral votes."
>
  <div class="controls">
    <ArchWheel bind:value={lane} ids={lanes2028(ctx0, ARCHETYPES).map((a) => a.id)} />
    <div class="sliders">
      <Slider
        label="National mood"
        bind:value={ctx.reader.env}
        min={es.min}
        max={es.max}
        step={es.step}
        format={(v) => fmtE(+v, 1)}
        ends={[fmtE(es.min), fmtE(es.max)]}
      />
      <div class="field">
        <label for="ladder-home">Home state (about +{homeBonus} points there)</label>
        <select id="ladder-home" bind:value={home}>
          <option value="">None</option>
          {#each states as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
        </select>
      </div>
    </div>
  </div>

  <p class="headline" role="status">
    <span class="pw tabular">{res ? pct(res.V) : '–'}</span>
    <span class="pwtext">chance a {label(lane).toLowerCase()} reaches 270 with a national vote of {voteLabel(ctx.reader.env)}<br /><span class="sub">{res ? `Likely range ${pctRange(res.V80)}` : 'Simulating…'}</span></span>
  </p>

  <div class="ladder" bind:clientWidth={w}>
    {#if w > 0}
      <div class="marks" aria-hidden="true">
        <span class="mark win" style:left="{x(evWin)}px"><b>{evWin}</b> to win</span>
        <span class="mark reach" style:left="{x(reach)}px">Favored in <b>{reach}</b></span>
      </div>
      <div class="bar" role="img" aria-label={`States in order from most Democratic to most Republican. The ${label(lane).toLowerCase()} is favored in states worth ${reach} electoral votes; ${evWin} are needed. The state that would cast the 270th vote is ${tipping?.name ?? 'unknown'}.`}>
        {#each ladder as u (u.id)}
          <span
            class="blk"
            class:tip={tipping?.id === u.id}
            class:homeblk={homeOf(u)}
            style:left="{x(u.start)}px"
            style:width="{Math.max(1, x(u.ev) - 1)}px"
            style:background={probFill(u.p)}
            title={`${u.name}: ${u.ev} EV, ${u.p == null ? '…' : pct(u.p)} chance for the Democrat`}
          >{#if x(u.ev) >= 22}<i>{short(u)}</i>{/if}</span>
        {/each}
        <span class="line win" style:left="{x(evWin)}px"></span>
        <span class="line reach" style:left="{x(reach)}px"></span>
      </div>
      <div class="ends" aria-hidden="true"><span>← Most Democratic</span><span>Most Republican →</span></div>
    {/if}
  </div>

  <div class="legend" aria-hidden="true">
    {#each PROB_BINS as b (b.label)}<span class="key"><i style:background={b.fill}></i>{b.label}</span>{/each}
  </div>

  {#if tipping}
    <div class="close">
      <p class="lab">Where it's decided: the states around the 270th vote</p>
      <div class="chips">
        {#each close as u (u.id)}
          <span class="chip" class:tipchip={tipping.id === u.id} style:border-color={probFill(u.p)}>
            <b>{u.parent ? short(u) : u.name}</b>
            <span class="tabular">{u.p == null ? '…' : pct(u.p)}</span>
          </span>
        {/each}
      </div>
    </div>
  {/if}
  {#if thinNote(ctx0, lane)}<p class="note">{thinNote(ctx0, lane)}</p>{/if}
  {#if error}<p class="error">Simulation error: {error}</p>{/if}

  {#snippet table()}
    <table class="data">
      <caption>States in ladder order, with the chance the {label(lane).toLowerCase()} carries each</caption>
      <thead><tr><th scope="col">State</th><th scope="col">EV</th><th scope="col">Running total</th><th scope="col">Democrat's chance</th></tr></thead>
      <tbody>
        {#each ladder as u (u.id)}
          <tr><th scope="row">{u.name}</th><td>{u.ev}</td><td>{u.start + u.ev}</td><td>{u.p == null ? '…' : pct(u.p)}</td></tr>
        {/each}
      </tbody>
    </table>
  {/snippet}
</SimFrame>

<style>
  .controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 20px;
  }
  .sliders {
    flex: 1 1 220px;
    min-width: 0;
    display: grid;
    gap: 8px;
  }
  .field {
    display: grid;
    gap: 4px;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  .field select {
    min-height: 40px;
    padding: 0 8px;
    border: 1px solid var(--ring);
    border-radius: 9px;
    background: var(--surface);
    color: var(--ink);
    font: 500 13px var(--font-ui);
  }
  .headline {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 0;
  }
  .pw {
    flex: none;
    font-size: 40px;
    font-weight: 700;
    line-height: 1;
    min-width: 2.6ch;
  }
  .pwtext {
    font-size: 14px;
    color: var(--ink);
  }
  .pwtext .sub {
    font-size: 12.5px;
    color: var(--ink-2);
  }
  .ladder {
    position: relative;
    padding-top: 34px;
  }
  .marks {
    position: absolute;
    inset: 0 0 auto;
    height: 30px;
    font-size: 11.5px;
    color: var(--ink-2);
  }
  .mark {
    position: absolute;
    white-space: nowrap;
    transform: translateX(-50%);
    transition: left 0.5s var(--ease);
  }
  .mark.win {
    top: 0;
  }
  .mark.reach {
    top: 15px;
    color: var(--ink);
  }
  .bar {
    position: relative;
    height: 46px;
  }
  .blk {
    position: absolute;
    top: 0;
    bottom: 0;
    display: grid;
    place-items: center;
    overflow: hidden;
    border-radius: 2px;
    transition: left 0.5s var(--ease), background-color 0.4s;
  }
  .blk i {
    font-style: normal;
    font-size: 10px;
    font-weight: 600;
    color: var(--ink);
  }
  .blk.tip {
    box-shadow: inset 0 0 0 2px var(--ink);
  }
  .blk.homeblk {
    outline: 2px dashed var(--ink);
    outline-offset: 1px;
  }
  .line {
    position: absolute;
    top: -6px;
    bottom: -6px;
    width: 2px;
    margin-left: -1px;
    transition: left 0.5s var(--ease);
  }
  .line.win {
    background: var(--ink);
  }
  .line.reach {
    background: repeating-linear-gradient(var(--ink-2) 0 3px, transparent 3px 6px);
  }
  .ends {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 11px;
    color: var(--muted);
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    font-size: 11px;
    color: var(--ink-2);
  }
  .legend .key {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .legend i {
    width: 12px;
    height: 10px;
    border-radius: 2px;
  }
  .close .lab {
    margin: 0 0 6px;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .chip {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    padding: 5px 9px;
    border: 2px solid var(--ring);
    border-radius: 8px;
    background: var(--surface);
    font-size: 12.5px;
    transition: border-color 0.4s;
  }
  .chip.tipchip {
    box-shadow: 0 0 0 1px var(--ink);
  }
  @container (max-width: 520px) {
    /* Phones: the answer and the ladder first, the controls under them. */
    .controls {
      order: 10;
    }
    .pw {
      font-size: 32px;
    }
    .bar {
      height: 38px;
    }
  }
</style>
