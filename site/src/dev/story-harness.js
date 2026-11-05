// Dev harness for one story component at a time: /dev/story.html?c=RawVsAdjusted
// Optional: &theme=dark|light, &p={"phase":"raw"} (JSON props).
import { mount } from 'svelte';
import '../app.css';
import Harness from './story-harness.svelte';

const q = new URLSearchParams(location.search);
const theme = q.get('theme');
if (theme) document.documentElement.dataset.theme = theme;

export default mount(Harness, { target: document.getElementById('app') });
