<script>
  // Card: plain-language methodology note (METHODOLOGY.md §9), data as-of time, sources,
  // sample and exclusion counts, validation status, and download links.
  import { asOfLabel, dataAsOf, modelStatus } from './util.js';
  import { resultsOutlets } from './sources.js';

  let { ctx, nodes = [], onnext, ...rest } = $props();

  const data = $derived(ctx?.data ?? {});
  const sample = $derived(data.story?.sample ?? {});
  const status = $derived(modelStatus(ctx));
  const items = $derived(Object.entries(data.validation?.items ?? {}));
  const counts = $derived({
    pass: items.filter(([, v]) => v.status === 'PASS').length,
    blockingFail: items.filter(([, v]) => v.blocking && v.status === 'FAIL'),
    notRun: items.filter(([, v]) => v.status === 'NOT_RUN'),
    softFail: items.filter(([, v]) => !v.blocking && v.status === 'FAIL'),
    total: items.length,
  });
  const totalRows = $derived(data.races?.length ?? null);
  const nyt = $derived(data.story?.nyt ?? {});

  const EXCLUSION_LABELS = {
    partial_count_lt_80pct: 'Less than 80% of the vote counted',
    uncontested_or_no_major_party_opponent: 'Uncontested or no major-party opponent',
    no_democrat_on_ballot: 'No Democrat on the ballot',
    house_outside_main_lean_window: 'House seat outside the competitive window',
    third_candidate_ge_10pct: 'A third candidate won 10% or more',
    independent_backed: 'Democrats backed an independent',
    validation_only_2025_offyear: '2025 off-year race (used only as a check)',
    combined_multi_dem_vote: 'Two Democrats on the final ballot',
  };
  const exclusions = $derived(
    Object.entries(sample.counts ?? {})
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => ({ label: EXCLUSION_LABELS[k] ?? k.replace(/_/g, ' '), n: v })),
  );
  // Plain-language notes for the checks that fail without blocking publication.
  const SOFT_FAIL_TEXT = {
    V7: (v) => {
      const c = v.numbers?.coverage80;
      return `Our 80% ranges are conservative: they contained ${c != null ? Math.round(c * 100) + '%' : 'more than 80%'} of the actual results, so the true uncertainty is probably a little smaller than shown.`;
    },
    V15: () => 'The quick “trust dial” approximation for blending 2026 with prior research did not match the exact calculation closely enough, so it is switched off; only the exact preset views are offered.',
  };
  const softFails = $derived(
    counts.softFail.map(([k, v]) => ({ id: k, text: SOFT_FAIL_TEXT[k]?.(v) ?? `${v.name ?? k} did not pass; it does not block publication.` })),
  );
  // Source names come from the as-of strings shipped with the data.
  const resultsSource = $derived((dataAsOf(ctx).match(/\((.*)\)/)?.[1] ?? '').trim());

  // Citation inventory (sources.json): every URL in research/*.json, counted by dataset.
  const inv = $derived(data.story?.sources ?? null);
  const fmt = (n) => (n == null ? '–' : Number(n).toLocaleString('en-US'));
  // Merge rows that share a readable name (census.gov, api.census.gov, www2.census.gov).
  const datasets = $derived(
    (inv?.datasets ?? []).map((d) => {
      const by = new Map();
      for (const t of d.top ?? []) {
        const k = t.name.replace(/\s*\(data sheets\)$/, '');
        by.set(k, (by.get(k) ?? 0) + t.citations);
      }
      return { ...d, outlets: [...by].map(([name, n]) => ({ name, n })).sort((a, b) => b.n - a.n) };
    }),
  );
  const nytPct = $derived(inv?.total_citations ? (100 * inv.nyt_citations) / inv.total_citations : null);
</script>

<div class="method ui">
  <h3>How we did this</h3>
  <p class="asof">Results as of {asOfLabel(ctx)}. Every number is preliminary.</p>
  <div class="prose">
    <p>
      Democrats gained almost everywhere in 2026, so the real question isn’t who did well but who did better than the wave.
      For every House, Senate and governor race, we compared the Democrat’s margin with how the same place voted for president
      in 2024. Then we compared candidates of different styles (progressive, populist, mainstream liberal, moderate) who were on
      the same state ballot, in places with similar partisanship, facing similar Republicans. That matters because the races
      differed in ways that have nothing to do with the candidate: who was an incumbent, which Republican was on the ballot,
      how far the whole state swung. Raw averages mix up the candidate with the circumstances.
    </p>
    <p>
      Small numbers of races give jumpy answers, so we pull every estimate toward “no difference” unless the evidence is strong,
      and we show the range, not just the middle. Some Western states are still counting.
    </p>
    {#if import.meta.env.VITE_NO2028 !== '1'}
    <details>
      <summary>How the 2028 scenarios work</summary>
      <p>
        We simulated the Electoral College thousands of times, letting similar states move together as they have historically.
        Three things nobody knows are left to you: how good a year 2028 is for Democrats (we do not assume 2026’s landslide carries
        over), how much of a midterm candidate’s edge survives a presidential campaign, and whether presidential-year voters behave
        like 2026’s. These are scenarios under stated assumptions, not forecasts. They can’t tell you whether any particular person
        would win.
      </p>
    </details>
    {/if}
  </div>

  <p class="facts">
    {#if sample.main_n != null}<strong>{sample.main_n}</strong> races in the main comparison{#if totalRows}, of {totalRows} loaded{/if}.{/if}
    {#if counts.blockingFail.length}
      {counts.blockingFail.length} required {counts.blockingFail.length === 1 ? 'check fails' : 'checks fail'} ({counts.blockingFail.map(([k]) => k).join(', ')}){#if counts.notRun.length}; {counts.notRun.length} not yet run{/if}.
    {:else if counts.total}
      Required validation checks pass{#if counts.notRun.length}; {counts.notRun.length} not yet run{/if}.
    {/if}
    {#if softFails.length}
      {softFails.length} non-blocking {softFails.length === 1 ? 'check fails' : 'checks fail'}:
      {#each softFails as f, i (f.id)}{i ? ' ' : ''}<span class="sf">{f.id}: {f.text}</span>{/each}
    {/if}
    <span class="status" class:ok={status.cleared}>
      {status.cleared
        ? 'Model parameters cleared for publication.'
        : 'Model not yet cleared: adjusted style estimates are provisional and under review.'}
    </span>
  </p>

  {#if exclusions.length}
    <details>
      <summary>Why races were left out</summary>
      <ul class="ex">
        {#each exclusions as e (e.label)}<li><span>{e.label}</span><span class="tabular">{e.n}</span></li>{/each}
      </ul>
      <p class="sub">A race can be left out for more than one reason; each row in the download lists its reason.</p>
    </details>
  {/if}
  <section class="sources" aria-labelledby="m-sources">
    <h4 id="m-sources">Sources</h4>
    {#if inv}
      <p class="lead">
        The research files cite <strong>{fmt(inv.total_citations)}</strong> source pages from <strong>{fmt(inv.total_domains)}</strong> sites.
        Only {fmt(inv.nyt_citations)} ({nytPct < 1 ? 'under 1' : Math.round(nytPct)}%) are from nytimes.com; race results come mostly from {resultsOutlets(ctx)}.
        {#each inv.user_supplied ?? [] as u (u)}Also used: the {u}.{' '}{/each}
      </p>
    {/if}
  </section>
  <details>
    <summary>What each part uses</summary>
    <ul class="src">
      <li>2026 results: {resultsSource || 'network results pages'}.</li>
      <li>Baselines: 2024 presidential results by state and by congressional district (current lines).</li>
      {#if nyt.source}<li>Voter groups: {#if nyt.url}<a href={nyt.url} rel="noopener" target="_blank">{nyt.source}</a>{:else}{nyt.source}{/if}.</li>{/if}
      <li>Candidate styles: our classification of each Democratic nominee from platforms, endorsements and primary coverage.</li>
      <li>Candidate track records (2028 scenarios): each politician’s past margins compared with the national result of the same year, using the House popular vote for 2006–2022 and the presidential popular vote for 2004–2024, both checked against official results.</li>
      <li>Ballot measures: state results pages.</li>
      {#if data.story?.groupSources}<li>Voter-group comparison: {data.story.groupSources.sources?.nyt?.name}, the {data.story.groupSources.sources?.ssrs?.name?.replace(/^Network/, 'network')} and the {data.story.groupSources.sources?.ap?.name}.</li>{/if}
      {#if data.story?.geo}<li>County and district swings: results pages for each race, compared with the same race statewide.</li>{/if}
    </ul>
  </details>
  {#each datasets as d (d.dataset)}
    <details class="ds">
      <summary><span class="dsn">{d.dataset}</span><span class="dsc tabular">{fmt(d.citations)} citations · {d.domains} sites</span></summary>
      <ol class="top">
        {#each d.outlets as o (o.name)}<li><span>{o.name}</span><span class="tabular">{fmt(o.n)}</span></li>{/each}
      </ol>
      {#if d.domains > d.outlets.length}<p class="sub">Top {d.outlets.length} of {d.domains} sites shown.</p>{/if}
    </details>
  {/each}

  <div class="dl">
    <a class="btn" href="data/races.json" download="lane-test-races.json">Race data (JSON)</a>
    <a class="btn ghost" href="data/validation.json" download="lane-test-validation.json">Validation report</a>
  </div>
</div>

<style>
  .method {
    font-size: 13px;
    line-height: 1.45;
  }
  h3 {
    margin: 0;
    font-size: 16px;
  }
  .asof {
    margin: 2px 0 8px;
    font-size: 12px;
    color: var(--muted);
  }
  .prose p {
    margin: 0 0 8px;
    font-family: var(--font-prose);
    font-size: 14px;
    line-height: 1.45;
  }
  details {
    margin: 0;
    border-top: 1px solid var(--grid);
  }
  details > :not(summary) {
    margin-bottom: 8px;
  }
  summary {
    min-height: 44px;
    display: flex;
    align-items: center;
    cursor: pointer;
    font-weight: 600;
    color: var(--ink-2);
    list-style-position: inside;
  }
  summary::before {
    content: '▸';
    margin-right: 6px;
    font-size: 11px;
  }
  details[open] summary::before {
    content: '▾';
  }
  summary::-webkit-details-marker {
    display: none;
  }
  .facts {
    margin: 0;
    border-top: 1px solid var(--grid);
    padding: 8px 0;
  }
  .sub {
    display: block;
    color: var(--muted);
    font-size: 11px;
  }
  .ex,
  .src {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .ex li {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 3px 0;
    border-bottom: 1px solid var(--grid);
    font-size: 12px;
  }
  .src li {
    margin-bottom: 4px;
  }
  .src a {
    color: var(--ink);
  }
  .status {
    color: var(--ink-2);
  }
  .sources {
    border-top: 1px solid var(--grid);
    padding-top: 8px;
  }
  h4 {
    margin: 0 0 4px;
    font-size: 14px;
  }
  .lead {
    margin: 0 0 8px;
    color: var(--ink);
  }
  .ds summary {
    gap: 8px;
    font-weight: 500;
  }
  .dsn {
    flex: 1;
    min-width: 0;
  }
  .dsc {
    flex: none;
    color: var(--muted);
    font-size: 11.5px;
    font-weight: 400;
  }
  .top {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .top li {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 3px 0;
    border-bottom: 1px solid var(--grid);
    font-size: 12px;
  }
  .status:not(.ok) {
    font-weight: 600;
  }
  .dl {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    padding: 0 14px;
    border-radius: 999px;
    background: var(--ink);
    color: var(--bg);
    font-weight: 600;
    font-size: 13px;
    text-decoration: none;
  }
  .btn.ghost {
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--ring);
  }
  @media (max-width: 760px) {
    .prose p {
      font-size: 14px;
    }
  }
</style>
