<script>
  import Story from './lib/story/Story.svelte';
  import { loadContext } from './lib/data.js';
  import { buildStory } from './story/steps.js';

  let ctx = $state.raw(null);
  let story = $state.raw(null);
  // Reader state shared by every chapter: a slider moved in one sim carries forward.
  const reader = $state({ guess: null, quizAnswers: [], quizPair: null, quizPos: 0, env: 0, pi: 1 });
  let error = $state(null);

  loadContext()
    .then((c) => {
      const env = c.data.params.environment.presets[c.data.params.environment.default_preset];
      reader.env = env.loc ?? env.mean ?? env.value ?? 0;
      c.reader = reader;
      ctx = c;
      story = buildStory(c);
    })
    .catch((e) => (error = e));
</script>

{#if error}
  <p class="ui status">Couldn't load the data: {error.message}</p>
{:else if !story}
  <p class="ui status">Loading the results…</p>
{:else}
  <Story steps={story.steps} chapters={story.chapters} nodes={ctx.nodes} {ctx} title="The Lane Test" />
{/if}

<style>
  .status {
    padding: 40vh var(--gutter) 0;
    text-align: center;
    color: var(--muted);
  }
</style>
