// Dev harness for the simulation stage components: /dev/sims.html?c=Name&mode=…&frame=desktop|mobile|full
import { mount } from 'svelte';
import '../app.css';
import Harness from './sims-harness.svelte';

export default mount(Harness, { target: document.getElementById('app') });
