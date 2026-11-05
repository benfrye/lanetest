<script>
  // Bottom fade + "Scroll for more" pill for a stage whose content is taller than its area.
  // Place it as the last child inside the scrolling content: it finds the nearest scrollable
  // ancestor, sticks to that ancestor's bottom edge, and disappears for good once the reader
  // scrolls (or when everything fits).
  import { onMount } from 'svelte';

  let anchor = $state();
  let show = $state(false);
  let scroller = null;
  let dismissed = false;

  function findScroller(el) {
    for (let n = el?.parentElement; n; n = n.parentElement) {
      const oy = getComputedStyle(n).overflowY;
      if (oy === 'auto' || oy === 'scroll') return n;
    }
    return null;
  }
  function update() {
    if (!scroller) return;
    if (scroller.scrollTop > 16) dismissed = true;
    const more = scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop > 6;
    show = !dismissed && more;
  }
  function nudge() {
    if (!scroller) return;
    const reduce = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller.scrollBy({ top: Math.round(scroller.clientHeight * 0.7), behavior: reduce ? 'auto' : 'smooth' });
  }

  onMount(() => {
    scroller = findScroller(anchor);
    if (!scroller) return;
    const ro = new ResizeObserver(update);
    ro.observe(scroller);
    for (const c of scroller.children) ro.observe(c);
    if (anchor.parentElement) ro.observe(anchor.parentElement);
    // content that loads later (simulation results) changes the height without resizing children
    const mo = new MutationObserver(update);
    mo.observe(scroller, { childList: true, subtree: true });
    scroller.addEventListener('scroll', update, { passive: true });
    update();
    return () => {
      ro.disconnect();
      mo.disconnect();
      scroller?.removeEventListener('scroll', update);
    };
  });
</script>

<div class="cue" class:on={show} bind:this={anchor} aria-hidden={!show}>
  <div class="fade"></div>
  <button class="pill" tabindex={show ? 0 : -1} onclick={(e) => { e.stopPropagation(); nudge(); }}>Scroll for more <span aria-hidden="true">↓</span></button>
</div>

<style>
  .cue {
    position: sticky;
    bottom: 0;
    height: 0;
    z-index: 6;
    pointer-events: none;
    margin-top: 0;
    flex: none;
  }
  .fade {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 56px;
    background: linear-gradient(to bottom, transparent, var(--bg) 85%);
    opacity: 0;
    transition: opacity 0.2s;
  }
  .pill {
    position: absolute;
    right: 8px;
    bottom: 6px;
    transform: translateY(6px);
    min-height: 36px;
    padding: 0 14px;
    border: 1px solid var(--ring);
    border-radius: 999px;
    background: var(--surface);
    color: var(--ink);
    font: 600 12px/1 var(--font-ui);
    white-space: nowrap;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    opacity: 0;
    transition: opacity 0.2s, transform 0.2s;
    cursor: pointer;
  }
  .on .fade {
    opacity: 1;
  }
  .on .pill {
    opacity: 1;
    transform: none;
    pointer-events: auto;
  }
  @media (prefers-reduced-motion: reduce) {
    .fade,
    .pill {
      transition: none;
    }
  }
</style>
