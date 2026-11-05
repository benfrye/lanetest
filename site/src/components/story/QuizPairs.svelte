<script>
  // Card: five matched pairs (quiz_pairs.json). The reader picks which Democrat beat
  // their 2024 baseline by more; we reveal both numbers, keep score, and at the end
  // compute how often "the lane with the higher raw average" would have called it.
  import { untrack } from 'svelte';
  import ArchChip from './ArchChip.svelte';
  import { resultsOutlets } from './sources.js';
  import { ARCHETYPE_BY_ID, signed, num, margin, raceLabel, asOfLabel } from './util.js';

  let { ctx, nodes = [], onnext, onpair, count = 5, ...rest } = $props();

  const allPairs = $derived(ctx?.data?.story?.quiz?.pairs ?? []);
  const pairs = $derived(allPairs.slice(0, count));
  const rawMeans = $derived(
    Object.fromEntries(
      Object.entries(ctx?.data?.story?.raw?.main_sample ?? {}).map(([k, v]) => [k, v?.all?.mean ?? null]),
    ),
  );

  const winnerOf = (p) => (p.a.y >= p.b.y ? p.a : p.b);
  // The lane call: whichever archetype had the higher raw average gain.
  const laneCall = (p) => ((rawMeans[p.a.archetype] ?? 0) >= (rawMeans[p.b.archetype] ?? 0) ? p.a : p.b);
  const laneRight = (p) => laneCall(p).id === winnerOf(p).id;

  // Restore a finished or partial run if the reader comes back to this step. The card is
  // re-created per step, so the position lives in ctx.reader too (quizPos): an answered pair
  // comes back revealed, and "Next race" moves on as before.
  const saved = untrack(() => ctx?.reader?.quizAnswers ?? []);
  const savedPos = untrack(() => ctx?.reader?.quizPos);
  let answers = $state(saved.slice(0, count));
  const startAt = (() => {
    const n = Math.min(saved.length, count);
    if (savedPos != null && savedPos >= 0 && savedPos <= n) return Math.min(savedPos, count);
    // no saved position: the last answered pair (still revealed), or the summary when all are done
    return n >= count ? count : Math.max(0, n - 1);
  })();
  let i = $state(startAt);
  let revealed = $state(startAt < count && saved[startAt] != null);
  const done = $derived(i >= pairs.length && pairs.length > 0);
  const pair = $derived(pairs[i]);
  const score = $derived(answers.filter((a) => a.correct).length);
  const current = $derived(revealed ? answers[i] : null);

  const shown = $derived({
    right: pairs.filter(laneRight).length,
    n: pairs.length,
  });
  const overall = $derived({
    right: allPairs.filter(laneRight).length,
    n: allPairs.length,
  });
  const coinFlip = $derived(overall.n > 0 && overall.right / overall.n >= 0.3 && overall.right / overall.n <= 0.7);
  const ranked = $derived(
    Object.entries(rawMeans)
      .filter(([, v]) => v != null)
      .sort((a, b) => b[1] - a[1]),
  );

  $effect(() => {
    const ids = done || !pair ? [] : [pair.a.id, pair.b.id];
    untrack(() => onpair?.(ids));
  });

  function choose(side) {
    if (revealed || !pair) return;
    const pick = pair[side];
    const win = winnerOf(pair);
    answers[i] = { a: pair.a.id, b: pair.b.id, pick: pick.id, winner: win.id, correct: pick.id === win.id };
    if (ctx?.reader) {
      ctx.reader.quizAnswers = answers.slice();
      ctx.reader.quizPos = i;
    }
    revealed = true;
  }
  function advance() {
    revealed = false;
    i += 1;
    if (ctx?.reader) ctx.reader.quizPos = i;
  }
  function restart() {
    answers = [];
    if (ctx?.reader) {
      ctx.reader.quizAnswers = [];
      ctx.reader.quizPos = 0;
    }
    revealed = false;
    i = 0;
  }

  const maxY = $derived(pair ? Math.max(Math.abs(pair.a.y), Math.abs(pair.b.y), 1) : 1);
  const placeLabel = (c) => (c.office === 'House' ? `${c.district}` : raceLabel(c.id));
</script>

<div class="quiz ui">
  {#if !pairs.length}
    <p class="muted">Quiz data not available.</p>
  {:else if !done}
    <div class="row">
      <p class="q">
        <strong>Race {i + 1} of {pairs.length}:</strong> which Democrat beat their 2024 baseline by more?
      </p>
      <span class="score tabular" aria-label={`Score ${score} of ${answers.length}`}>{score}/{answers.length}</span>
    </div>
    <div class="opts">
      {#each ['a', 'b'] as side (side)}
        {@const c = pair[side]}
        {@const isWin = winnerOf(pair).id === c.id}
        <button
          class="opt"
          class:picked={current?.pick === c.id}
          class:win={revealed && isWin}
          disabled={revealed}
          onclick={() => choose(side)}
          aria-label={`${c.name}, ${placeLabel(c)}, ${ARCHETYPE_BY_ID[c.archetype]?.label}. 2024 baseline ${margin(c.m24, 0)}.` + (revealed ? ` Gain ${signed(c.y)} points.` : '')}
        >
          <span class="who">
            <span class="name">{c.name}</span>
            <span class="meta">{placeLabel(c)} · {margin(c.m24, 0)} in 2024</span>
            <ArchChip id={c.archetype} size={11} />
          </span>
          {#if revealed}
            <span class="val tabular">
              <span class="num">{signed(c.y)}</span>
              <span class="bar" style:width={(Math.max(0, c.y) / maxY) * 100 + '%'} style:background={`var(${ARCHETYPE_BY_ID[c.archetype]?.token})`}></span>
            </span>
          {/if}
        </button>
      {/each}
    </div>
    {#if revealed}
      <div class="row after">
        <p class="fb" aria-live="polite">
          {current?.correct ? 'Right.' : 'Not this time.'}
          {winnerOf(pair).name} gained {num(Math.abs(pair.a.y - pair.b.y))} points more.
        </p>
        <button class="go" onclick={advance}>{i + 1 < pairs.length ? 'Next race →' : 'See your score →'}</button>
      </div>
    {/if}
  {:else}
    <div class="summary">
      <p class="big">You got <strong>{score} of {pairs.length}</strong>.</p>
      <p>
        If you had always picked the lane with the higher raw average gain
        ({#each ranked as [id, v], k (id)}{k ? ', ' : ''}<ArchChip {id} size={10} /> {signed(v)}{/each}),
        you would have called <strong>{shown.right} of {shown.n}</strong> of these pairs{#if overall.n > shown.n}, and {overall.right} of all {overall.n} matched pairs we drew{/if}.
      </p>
      {#if coinFlip}<p>That’s about as often as a coin flip.</p>{/if}
      <div class="row">
        <button class="link" onclick={restart}>Try again</button>
        <button class="go" onclick={() => onnext?.()}>Continue →</button>
      </div>
    </div>
  {/if}
  <p class="note">Gain = 2026 margin minus Harris’s 2024 margin, points. Preliminary, as of {asOfLabel(ctx)}. Results: {resultsOutlets(ctx, 3)}.</p>
</div>

<style>
  .quiz {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 14px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .q {
    margin: 0;
    flex: 1;
    line-height: 1.35;
  }
  .score {
    flex: none;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--surface-2);
    color: var(--ink-2);
    font-size: 12px;
  }
  .opts {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .opt {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    padding: 8px 12px;
    border: 1px solid var(--ring);
    border-radius: var(--radius);
    background: var(--surface);
    text-align: left;
    cursor: pointer;
  }
  .opt:not(:disabled):hover {
    border-color: var(--axis);
    background: var(--surface-2);
  }
  .opt:disabled {
    cursor: default;
    color: var(--ink);
  }
  .opt.picked {
    box-shadow: inset 0 0 0 1px var(--ink);
    border-color: var(--ink);
  }
  .who {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
    font-size: 12px;
  }
  .name {
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta {
    color: var(--ink-2);
  }
  .val {
    flex: 0 0 34%;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 3px;
  }
  .num {
    font-size: 15px;
    font-weight: 600;
  }
  .opt.win .num::after {
    content: ' ▲';
    font-size: 10px;
    color: var(--ink-2);
  }
  .bar {
    display: block;
    height: 6px;
    min-width: 2px;
    border-radius: 0 3px 3px 0;
    align-self: flex-start;
    animation: grow 0.5s var(--ease);
    transform-origin: left;
  }
  .after .fb {
    flex: 1;
    margin: 0;
    font-size: 13px;
    color: var(--ink-2);
  }
  .go {
    flex: none;
    min-height: 44px;
    padding: 0 14px;
    border-radius: 999px;
    border: 1px solid var(--ink);
    background: var(--ink);
    color: var(--bg);
    font-weight: 600;
    cursor: pointer;
  }
  .row .go {
    margin-left: auto;
  }
  .link {
    min-height: 44px;
    border: 0;
    background: none;
    padding: 0;
    text-decoration: underline;
    color: var(--ink-2);
    cursor: pointer;
  }
  .summary p {
    margin: 0 0 8px;
    line-height: 1.45;
  }
  .summary .big {
    font-size: 17px;
  }
  .note {
    margin: 2px 0 0;
    font-size: 11px;
    color: var(--muted);
  }
  .muted {
    color: var(--muted);
  }
  @keyframes grow {
    from {
      transform: scaleX(0);
    }
  }
</style>
