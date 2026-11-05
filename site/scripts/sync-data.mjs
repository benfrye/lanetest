// Copies analysis outputs into public/data so the site ships a self-contained snapshot.
// Uses model_params.json when the pipeline has cleared validation, otherwise the
// schema-identical model_params.BLOCKED.json (flagged in data/manifest.json so the UI can say so).
import { cpSync, existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const site = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(site, '..', 'analysis', 'output');
const dest = join(site, 'public', 'data');
mkdirSync(join(dest, 'story'), { recursive: true });

const cleared = existsSync(join(out, 'model_params.json'));
cpSync(join(out, cleared ? 'model_params.json' : 'model_params.BLOCKED.json'), join(dest, 'model_params.json'));
for (const f of ['races.json', 'validation.json']) cpSync(join(out, f), join(dest, f));
for (const f of readdirSync(join(out, 'story_data'))) cpSync(join(out, 'story_data', f), join(dest, 'story', f));
cpSync(join(site, '..', 'research', 'nyt_voter_trends.json'), join(dest, 'story', 'nyt_voter_trends.json'));
writeFileSync(join(dest, 'manifest.json'), JSON.stringify({ params_cleared: cleared, synced_at: new Date().toISOString() }, null, 2));
console.log(`synced data (params ${cleared ? 'cleared' : 'BLOCKED placeholder'})`);
