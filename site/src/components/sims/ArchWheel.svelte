<script>
  // Lane picker as a small spinning wheel: the chosen lane sits in the window with its shape
  // and label; the others ride the drum above and below, tilting away and fading as they
  // turn out of view. Turn it with the arrows, a tap on a neighbor, a drag or swipe, the
  // mouse wheel, or the arrow keys. The drum loops, like a prize wheel.
  import { untrack } from 'svelte';
  import { ARCHETYPES, ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import ArchChip from './ArchChip.svelte';

  let { value = $bindable(), ids = ARCHETYPES.map((a) => a.id), label = 'Type of Democrat', onchange = null } = $props();

  const ROW = 34; // px between lanes on the drum
  const n = $derived(ids.length);
  const reduceMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  let pos = $state(Math.max(0, untrack(() => ids.indexOf(value)))); // fractional index at the window
  let dragging = null; // { y, pos }
  let anim = 0;

  const wrap = (d) => {
    const m = ((d % n) + n) % n;
    return m >= n / 2 ? m - n : m;
  };

  function animateTo(target) {
    cancelAnimationFrame(anim);
    const from = pos;
    // shortest way round the drum
    const to = from + wrap(target - from);
    if (reduceMotion) {
      pos = to;
      return;
    }
    const t0 = performance.now();
    const dur = 380;
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      pos = from + (to - from) * e;
      if (k < 1) anim = requestAnimationFrame(tick);
    };
    anim = requestAnimationFrame(tick);
  }

  // Follow outside changes to value (e.g. another control setting the lane).
  $effect(() => {
    const i = ids.indexOf(value);
    if (i < 0) return;
    untrack(() => {
      if (!dragging && Math.abs(wrap(i - pos)) > 0.001) animateTo(i);
    });
  });

  function select(i) {
    const idx = ((i % n) + n) % n;
    animateTo(idx);
    if (ids[idx] !== value) {
      value = ids[idx];
      onchange?.(value);
    }
  }
  const current = $derived(((Math.round(pos) % n) + n) % n);
  const step = (k) => select(ids.indexOf(value) + k);

  function onkey(e) {
    const k = { ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 }[e.key];
    if (k) {
      e.preventDefault();
      step(k);
    } else if (e.key === 'Home') {
      e.preventDefault();
      select(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      select(n - 1);
    }
  }

  let wheelAcc = 0;
  function onwheel(e) {
    e.preventDefault();
    wheelAcc += e.deltaY;
    if (Math.abs(wheelAcc) >= 40) {
      step(Math.sign(wheelAcc));
      wheelAcc = 0;
    }
  }

  function down(e) {
    cancelAnimationFrame(anim);
    dragging = { y: e.clientY, pos, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function move(e) {
    if (!dragging) return;
    const dy = e.clientY - dragging.y;
    if (Math.abs(dy) > 3) dragging.moved = true;
    pos = dragging.pos - dy / ROW;
  }
  function up(e) {
    if (!dragging) return;
    const d = dragging;
    dragging = null;
    if (d.moved) select(Math.round(pos));
    else {
      // a tap: on a neighbor turns the drum to it
      const r = e.currentTarget.getBoundingClientRect();
      const off = Math.round((e.clientY - (r.top + r.height / 2)) / ROW);
      select(Math.round(d.pos) + off);
    }
  }

  const items = $derived(
    ids.map((id, i) => {
      const d = wrap(i - pos);
      const a = Math.abs(d);
      return {
        id,
        d,
        style: `transform: translateY(${(d * ROW).toFixed(2)}px) rotateX(${(-d * 32).toFixed(1)}deg) scale(${(1 - 0.08 * a).toFixed(3)}); opacity: ${Math.max(0, 1 - 0.62 * a).toFixed(3)};`,
      };
    }),
  );
</script>

<div class="picker">
  <span class="lab" id="wl-{label.replace(/\W+/g, '')}">{label}</span>
  <div class="wheel-wrap">
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div
      class="wheel"
      role="spinbutton"
      tabindex="0"
      aria-labelledby="wl-{label.replace(/\W+/g, '')}"
      aria-valuenow={ids.indexOf(value) + 1}
      aria-valuemin="1"
      aria-valuemax={n}
      aria-valuetext={ARCHETYPE_BY_ID[value]?.label}
      onkeydown={onkey}
      {onwheel}
      onpointerdown={down}
      onpointermove={move}
      onpointerup={up}
      onpointercancel={() => (dragging = null)}
    >
      <span class="window" aria-hidden="true"></span>
      <span class="pointer" aria-hidden="true"></span>
      {#each items as it (it.id)}
        <span class="item" class:on={it.id === ids[current]} style={it.style} aria-hidden="true">
          <ArchChip id={it.id} size={13} />
        </span>
      {/each}
    </div>
    <div class="arrows">
      <button type="button" aria-label="Previous type" onclick={() => step(-1)}>
        <svg width="12" height="8" viewBox="0 0 12 8" aria-hidden="true"><path d="M1 7l5-5 5 5" /></svg>
      </button>
      <button type="button" aria-label="Next type" onclick={() => step(1)}>
        <svg width="12" height="8" viewBox="0 0 12 8" aria-hidden="true"><path d="M1 1l5 5 5-5" /></svg>
      </button>
    </div>
  </div>
</div>

<style>
  .picker {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  .lab {
    font-weight: 500;
  }
  .wheel-wrap {
    display: flex;
    align-items: stretch;
    border: 1px solid var(--ring);
    border-radius: 12px;
    background: var(--surface);
    overflow: hidden;
  }
  .wheel {
    position: relative;
    width: 196px;
    height: 88px;
    perspective: 260px;
    cursor: grab;
    touch-action: none;
    user-select: none;
    outline: none;
    /* the drum's top and bottom fade into the background */
    -webkit-mask-image: linear-gradient(transparent, #000 34%, #000 66%, transparent);
    mask-image: linear-gradient(transparent, #000 34%, #000 66%, transparent);
  }
  .wheel:active {
    cursor: grabbing;
  }
  .wheel:focus-visible {
    box-shadow: inset 0 0 0 2px var(--ink);
  }
  .window {
    position: absolute;
    left: 6px;
    right: 6px;
    top: 50%;
    height: 32px;
    margin-top: -16px;
    border-radius: 8px;
    background: var(--surface-2);
    border: 1px solid var(--ring);
  }
  .pointer {
    position: absolute;
    left: 0;
    top: 50%;
    margin-top: -5px;
    border: 5px solid transparent;
    border-left: 6px solid var(--ink);
  }
  .item {
    position: absolute;
    left: 18px;
    right: 8px;
    top: 50%;
    height: 32px;
    margin-top: -16px;
    display: flex;
    align-items: center;
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-2);
    white-space: nowrap;
    pointer-events: none;
    backface-visibility: hidden;
  }
  .item.on {
    color: var(--ink);
    font-weight: 650;
  }
  .arrows {
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--ring);
  }
  .arrows button {
    flex: 1;
    width: 40px;
    min-height: 44px;
    display: grid;
    place-items: center;
    border: 0;
    background: none;
    cursor: pointer;
  }
  .arrows button + button {
    border-top: 1px solid var(--ring);
  }
  .arrows button:hover {
    background: var(--surface-2);
  }
  .arrows path {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  @media (max-width: 520px) {
    .lab {
      display: none;
    }
  }
</style>
