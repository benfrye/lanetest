// Reader state for the harness, created outside any component (as the app's ctx would be),
// so story components can write ctx.reader without ownership warnings.
export function createReader(env = 0) {
  const reader = $state({ guess: null, quizAnswers: [], env, pi: 1 });
  return reader;
}
