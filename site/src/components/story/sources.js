// Source lines for stages and sims. Outlet names come from data/story/sources.json (every
// URL cited in research/*.json, counted by dataset) so the lines track the research files;
// the fallbacks only apply if that file failed to load.

// State election offices: named ones, or *.gov hosts that are not federal statistics agencies.
const OFFICE_NAME = /secretary of state|division of elections|board of elections/i;
const OFFICE_HOST = /(^|\.)(sos|elections?|electionfiles|ncsbe|er)\.|\.(state\.[a-z]{2}\.us)$/i;
const isOffice = (t) => OFFICE_NAME.test(t.name) || (OFFICE_HOST.test(t.domain) && !/census|bls/.test(t.domain));
const short = (name) => name.replace(/\s*\(.*\)$/, '');
const NICK = { 'Associated Press': 'AP' };

// Readable top outlets for one dataset (matched by label prefix). Domains without a readable
// name are local outlets; election-office domains are folded into "state election offices".
export function outlets(ctx, prefix, { n = 4, skip = [], nick = false } = {}) {
  const ds = (ctx?.data?.story?.sources?.datasets ?? []).find((d) => d.dataset.startsWith(prefix));
  if (!ds) return null;
  const names = [];
  let offices = false;
  let local = false;
  for (const t of ds.top) {
    if (isOffice(t)) {
      offices = true;
      continue;
    }
    if (t.name === t.domain) {
      local = true;
      continue;
    }
    let nm = short(t.name);
    if (nick) nm = NICK[nm] ?? nm;
    if (!skip.includes(nm) && !names.includes(nm)) names.push(nm);
  }
  return { names: names.slice(0, n), offices, local, citations: ds.citations, domains: ds.domains };
}

export function list(items) {
  const a = items.filter(Boolean);
  if (a.length <= 1) return a.join('');
  return `${a.slice(0, -1).join(', ')} and ${a[a.length - 1]}`;
}

// "Wikipedia, NBC News, The Downballot, AP and state election offices"
export function resultsOutlets(ctx, n = 4) {
  const o = outlets(ctx, 'Race results', { n, nick: true });
  if (!o) return 'NBC News, AP, Wikipedia, The Downballot and state election offices';
  return list([...o.names, o.offices ? 'state election offices' : null]);
}

export const resultsSource = (ctx) =>
  `Source: 2026 results and 2024 baselines from ${resultsOutlets(ctx)}. Model: our analysis.`;

export function measuresSource(ctx) {
  const o = outlets(ctx, 'Ballot measures', { n: 3 });
  const who = o ? list([...o.names, o.local ? 'local outlets' : null]) : 'NBC News, Wikipedia and local outlets';
  return `Source: measure results from ${who}; top-of-ticket margins from the race results (${resultsOutlets(ctx, 2)}).`;
}

export function nytSource(ctx) {
  const s = ctx?.data?.story?.groupSources?.sources?.nyt;
  return `Source: ${s?.name ?? 'New York Times Voter Trends'}${s?.method ? `, ${s.method}` : ''}.`;
}

// Short form for sims, which all run on the same model.
export function simSource(ctx, extra = '') {
  const o = outlets(ctx, 'Race results', { n: 2, nick: true, skip: ['Wikipedia', 'The Downballot'] });
  const res = o ? [...o.names, o.offices ? 'state offices' : null].filter(Boolean).join(', ') : 'NBC News, AP, state offices';
  const census = outlets(ctx, 'State demographics', { n: 3 })?.names.includes('U.S. Census Bureau') ?? true;
  return `Source: our model, built on 2026 results (${res}), 2024 results${census ? ' and Census data' : ''}${extra ? `; ${extra}` : ''}.`;
}

const DOMAIN_NAMES = {
  'nbcnews.com': 'NBC News results pages',
  'bridgemi.com': 'Bridge Michigan',
  'nytimes.com': 'New York Times',
  'apnews.com': 'AP',
};
export function domainOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}
export function domainName(url, ctx) {
  const d = domainOf(url);
  if (DOMAIN_NAMES[d]) return DOMAIN_NAMES[d];
  for (const ds of ctx?.data?.story?.sources?.datasets ?? []) {
    const t = ds.top.find((x) => x.domain === d);
    if (t) return t.name;
  }
  return d;
}

export const resultsShort = (ctx) => `Source: ${resultsOutlets(ctx, 3)}; our analysis.`;

export function measuresShort(ctx) {
  const o = outlets(ctx, 'Ballot measures', { n: 2 });
  return `Source: ${o ? list([...o.names, o.local ? 'local outlets' : null]) : 'NBC News, Wikipedia and local outlets'}.`;
}
