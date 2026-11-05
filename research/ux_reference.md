# UX reference: story site for "2026 midterms and Democratic candidate styles"

Compiled 2026-11-04. Purpose: design and build guidance for an interactive, story-driven piece (desktop and mobile web) modeled on The Pudding's "The Real Kevin Bacon." This file is about **form**, not election results. It contains no 2026 outcome data. Every claim about a reference is tied to a URL in the "Sources" list at the end; where something is my own recommendation or calculation, it says so.

---

## 1. Anatomy of "The Real Kevin Bacon" (pudding.cool/2026/10/kevin-bacon)

### What the page is made of

- **Stack, confirmed from the markup.** The served HTML loads `/_app/immutable/entry/start.*.js` and `app.*.js` and has `svelte-xxxx` scoped class names. That is a prerendered SvelteKit build, which matches The Pudding's public `svelte-starter` template (SvelteKit + Vite, static build output, `Scrolly` component, and `Slider`/`Tap` components for "swipe/slide stories" with "edge-of-screen tapping").
- **Accessibility scaffolding in the markup.** There is a visually hidden `<h1 class="sr-only">`, a "Skip to main content" link to `#content`, and two `role="status"` live regions, probably used to announce step changes and simulation results. The forward control has `aria-label="Next step"`, and a full-screen "Continue" tap layer has `tabindex="-1" aria-hidden="true"`, so the big tap zone is for pointers only and keyboard users get a single real button. The actor search is an ARIA combobox (`role="combobox"`, `aria-autocomplete="list"`, `aria-label="Search for an actor…"`, Bits UI ids). Fourteen `aria-haspopup="dialog"` triggers point to per-actor detail dialogs. The page also has `aria-hidden` SVG halo `<defs>` used for dot glows.
- **Story arc** (from a fetch of the page's text): a hook (14 actors, each with a Bacon number) → the rules of the game → the reversal (Bacon is not the center; he ranks 175th, and Samuel L. Jackson is #1) → a secondary finding (gender gap: 16 of the top 100 are women) → "Go back in time" plus a year slider (1980 onward) → why: film count, then co-star film count → **guess-first quiz** ("Pair 1 of 5": two actors with similar film counts; which one works with better-connected co-stars?) → Gen Z contenders (99 actors, "Show Gen Z actors" toggle) → method via career analogues → **"Start Simulation"** (10,000 runs, ranked top five with win percentages) → conclusion with medians and a caveat about uncertainty.

### Why the pacing works

1. **One persistent stage.** A single full-screen visualization stays put while short centered text cards change over it. The reader never loses the "map." Each step changes one thing: highlight, filter, re-layout or zoom. That makes the transition the explanation.
2. **Reader-paced stepping, not scroll-jacking.** Advancing happens through edge chevrons, a tap anywhere, or the arrow keys, and segmented progress bars at the top show where you are and how much is left. This is a "stories" (Instagram-style) metaphor that mobile readers already know. Note the tension: The Pudding's own responsive-scrollytelling guide advises *against* steppers and tap interfaces because they override native scrolling. Kevin Bacon accepts that cost because a stepper guarantees one discrete state per card, with no half-finished transitions and no trigger jitter from mobile toolbar resizes.
3. **Hook → reversal → mechanism → test → prediction.** The headline premise is debunked early (Bacon is #175), which earns curiosity for the "why." The mechanism (co-star quality beats raw volume) is then **tested on the reader** with the quiz before the model gives its answer. The finale hands the reader the button that runs the model, so the reader sees the uncertainty being produced.
4. **Exploration is fenced.** Search, the time slider and the Gen Z toggle are each offered at one card, inside the linear story. Free play never replaces the narrative.
5. **Uncertainty is shown, not asserted.** The simulation reports a leader at only 11.6%, then medians, then a caveat about timing. Readers are left knowing the answer is a distribution.

### Implications for our piece

- Stage = **one unit visualization of ~500–600 races** (each dot one House, Senate or governor race, or one Democratic nominee), re-laid out by category across steps: by 2024 margin → by 2026 swing → grouped by candidate style → split by district lean.
- Reversal candidates: whichever pre-election conventional wisdom the data contradicts (for example, "moderates overperform" or "progressives underperform"). **Decide this only after the analysis.**
- Quiz: "Race 1 of 5: which nominee beat the district's baseline by more?" with pairs matched on district partisanship, like the Bacon pairs matched on film count.
- Finale: a "2028 simulation" button that resamples the 2026 over/under-performance by style (bootstrap) and shows a distribution, never a single number.

---

## 2. Election-specific patterns worth borrowing

### Unit visualizations of races (one dot = one race)

- **538 (2020) "ball swarm":** 100 representative outcomes drawn from about 40,000 simulations as dots on an Electoral College margin axis. Hovering shows that simulation's map. Commentary at the time said you cannot leave that chart without knowing it shows a *range* of outcomes. The 2024 538/ABC forecast redesigned the "snake chart" to push the same point.
- **50+1 (2026 forecast, design write-up):** draws a subset of 40,000 simulations as **individual squares**, colored by which party wins the chamber, and gives every exact seat count its own x position instead of binning. Annotations sit on the chart to teach the reader how to read it. Districts are drawn as **circles at centroids** to avoid the land-area bias of choropleths, with dense metros spread out and backed by search.
- **Borrow:** dots are races, color is the party that won, and position carries the variable the current step is about. A swing dot plot puts each race's dot at its 2026-minus-baseline margin, grouped in rows by candidate style. Re-layout transitions (grid → beeswarm → grouped rows) should interpolate positions, not fade.

### Dot-plot swings

- Use a horizontal axis of *swing relative to a baseline* (2024 presidential margin, or partisan lean). Put candidate-style groups on separate rows (progressive / populist / moderate / mainstream). Draw a median tick per row and a light band for the interquartile range. Label the 3–5 named races the story discusses. Everything else stays anonymous until searched or tapped. (My recommendation.)
- Avoid hover-only labels. The Pudding responsive guide says to replace hover content with fixed annotations on mobile.

### Tile-grid or centroid maps

- For the House, use centroid circles (50+1 pattern) or a hex/tile cartogram with one equal-area cell per district. For the Senate and governors, use a 50-state tile grid. Equal-area cells stop rural geography from dominating a story about candidates. (Centroid rationale per 50+1. The tile-grid suggestion is mine.)
- On phones, 50+1 shows half the US at a time with an East/West toggle to avoid pinch-zoom conflicts, and docks the tooltip to the bottom of the map. Copy both.

### Fan charts and histograms of simulations

- Draw simulation output as **individual units** (538 dots, 50+1 squares), not a smooth density. A finale that runs a resampling of "how would a style-X nominee do in 2028 swing states" should animate squares stacking into a histogram, then report a median and an 80% interval in text.
- **NYT needle cautionary tale:** in 2016 the needle jittered randomly within the 25th–75th percentile band to signal uncertainty. Quartz reported that most of that motion was not new data, and readers read it as trends. **Do not use decorative motion to encode uncertainty.** Animate only when the data or the reader's action changes. The Times' later approach (per the Reuters Institute) stresses explicit priors, showing what remains to be counted, and keeping the display separate from race calls.

### "Build your candidate" controls

- A constrained control panel with four style chips (progressive / populist / moderate / mainstream) × district lean (a slider from D+10 to R+10) × incumbency (toggle). The output is the distribution of observed 2026 over/under-performance for matching races, shown as the subset of dots lighting up plus an n-count. **Always show n**, and grey out cells with fewer than about 5 races rather than extrapolating. (My recommendation. It mirrors 538's "what-if" tool, which filters its simulations to those consistent with the user's picks and recomputes from what remains.)
- Use accessible `ButtonSet` and `Toggle` patterns (both are in the Pudding starter), not custom divs.

### Quizzes and guess-first

- The Kevin Bacon "Pair 1 of 5" pattern works because the pairs are **matched** (similar film counts), which isolates the variable the story is about. Our version: pairs of Democratic nominees in similar-lean districts with different styles. "Which one ran ahead of the baseline?"
- Evidence, read honestly: a 2024 study of predict-first ("elicitation") news charts found that elicitation **increased engagement and surprise** but had **no significant effect on attitude change**, and no significant recall difference against no elicitation. Use guess-first for engagement, not as a persuasion device. Keep it to 3–5 items, show the score, and allow skipping.

---

## 3. Mobile-specific guidance

- **Tap targets.** WCAG 2.2 SC 2.5.8 (AA) requires pointer targets of at least 24×24 CSS px, or enough spacing. The enhanced criterion 2.5.5 (AAA) is recommended for important controls; 44×44 is the commonly cited enhanced size, though the fetched WCAG page did not state that number. Make the left/right "continue" zones full-height strips (about 25–30% of width each) and keep the visible chevron at 44px or more. Dots are **not** tap targets on their own. Use nearest-dot hit testing (a Delaunay/quadtree `find`) with a radius of about 20px, and a search box for exact lookup.
- **Viewport height.** Plain `vh` equals `lvh` (the large viewport) on mobile, so `100vh` content can sit under the browser toolbars. Use `100svh` for the stage and text cards so content always fits (with a `100vh` fallback), and use `lvh` only for decorative backgrounds. Avoid `dvh` on elements that animate, because it resizes during scroll (MDN). Pudding/Scrollama guidance is the same idea: do not size scroll steps in `vh`; compute pixels from `window.innerHeight`, or use pixel offsets.
- **Text-card placement.** Kevin Bacon centers cards over the stage. On phones, dock cards to the bottom third with a max height of about 40svh. Shift the visualization's focal area up (set the layout's y-center to about 35% of height on narrow screens). Keep cards to 1–3 sentences, since the Pudding guide notes long sequences tire mobile readers. Respect `env(safe-area-inset-*)` on the progress bar and chevrons.
- **Reduced motion.** Honor `prefers-reduced-motion: reduce`. Swap position tweens for a 150ms crossfade (or an instant cut) and auto-skip the simulation's stacking animation to its final state. Also give a visible in-page toggle (the Pudding starter lists a `MotionToggle` component).
- **Canvas vs SVG for ~600 dots.** Per Bocoup (Peter Beshai), d3 transitions on SVG nodes are fine for hundreds of points but get slow past about 1,000. Canvas holds up to roughly 5,000–10,000, and WebGL (regl) goes beyond that. At about 600 dots, SVG is *probably* fine on desktop. The risk is low-end Android during simultaneous re-layout of every dot plus halo filters. **Recommendation:** draw dots on `<canvas>` (devicePixelRatio-scaled) using Bocoup's source→target interpolation with a single `d3.timer`/rAF loop, and put labels, axes and annotations in an absolutely positioned SVG/HTML layer above it. Avoid SVG filters (glows) on animated elements; pre-render a halo sprite instead. Profile on a real mid-range phone.
- **Hover replacements.** Tap shows a docked detail sheet (50+1 pattern), never a floating tooltip under the thumb.

---

## 4. Accessibility

- **Keyboard.** Arrow keys and Space/Enter advance (as in Kevin Bacon). There is one real focusable "Next step" button. The full-screen tap layer is `aria-hidden` and `tabindex=-1`, as Kevin Bacon does. Move focus to the new card's heading on each step, or announce it. Make the progress segments buttons, each with `aria-label="Step 4 of 18: …"`. Any modal (race detail) traps focus and returns it on close (the starter's `focusTrap.js`).
- **Screen readers.** Use a `role="status"` live region that announces each step's text plus a one-line description of what the chart now shows ("Dots regrouped into four rows by candidate style; progressives median +1.2", with the number filled from data). For every stage state, provide a **data table alternative** (a semantic sortable table, like the starter's `SortTable`), reachable through a "View as table" link. The canvas gets `role="img"` and an `aria-label`, and the table holds the real data. The search combobox should follow the ARIA pattern, as Kevin Bacon's does.
- **Color contrast against the #13051d background** (my computation, WCAG relative-luminance formula): white 19.7:1; light lavender #b9a8c7 8.9:1 (good for secondary text); #8c7a99 5.0:1 (minimum for small text; use for tertiary text only); candidate blue #5b9cff 7.2:1; candidate red #ff6b5e 7.0:1. All pass the 3:1 non-text minimum, and the text-sized ones pass 4.5:1.
- **Colorblind-safe partisan palette.** Blue and red stay distinguishable for red-green color vision deficiency (guides list blue/red, blue/orange as safe pairs and warn against red/green). However, #5b9cff and #ff6b5e have nearly equal luminance (1.02:1 between them, my computation), so **add a non-hue cue**: GOP dots as filled circles and Dem dots as rings, or a lightness offset (lighter blue, deeper red). Label groups directly instead of relying on a legend. **Do not use a second color channel for candidate style.** Encode style by row/position (the unit-viz re-layout) and keep color for party only. If a style color is unavoidable, draw from Okabe-Ito/Wong, keep it off the red-blue axis, and test with a CVD simulator.
- **Language.** Spell out ratings ("Lean R") and never encode them in color alone. Mark uncalled races and partial counts in text and with a hatched or hollow style, and show "% of expected vote counted" next to any live margin. (The NYT practice per the Reuters Institute is to explain what remains to be counted.)

---

## 5. Recommended tech approach (static site, no server at view time)

### Option A: SvelteKit (or plain Svelte) + Vite, `adapter-static`

- **How it works:** `adapter-static` prerenders the whole site to static files (`build/`). Set `prerender = true` in the root layout and keep SSR on, or pages come out empty. On GitHub Pages, set `paths.base` to the repo name, use `fallback: '404.html'`, and add `.nojekyll` if pushing manually. `precompress` emits .br/.gz files.
- **Pros:** This is the reference's own stack. The Pudding `svelte-starter` gives you `Scrolly`, accessible `ButtonSet`/`Toggle`/`SortTable`, `focusTrap`, `.sr-only`, ArchieML copy from Google Docs, and design tokens. Svelte's reactive state makes the "step index → stage state" mapping trivial. Output is plain HTML/JS/CSS (hashed `/_app/immutable` assets, as seen on the Kevin Bacon page). Prerendered card text is good for SEO, share previews and no-JS readers.
- **Cons:** It needs Node and a build step to *author* (not to view). The starter's `Slider`/`Tap`/`MotionToggle` components are listed as "needing migration" to Svelte 5, so we would write the stepper ourselves. Base-path pitfalls on subpath hosting. Do not use The Pudding's fonts or logos without permission (starter README). Tiempos and Atlas Grotesk are commercial, so pick licensed or open alternatives (for example Source Serif 4 + Inter/IBM Plex Sans from Google Fonts).

### Option B: Vanilla JS + D3 from a CDN (single `index.html`, ES modules)

- **How it works:** Pin `d3@7.x` from cdnjs/jsDelivr. The story steps are a JSON array, and one `render(stepIndex)` function maps step → layout targets → canvas tween. Copy lives in the HTML so it renders without JS.
- **Pros:** No toolchain. Any static host or even a file share works, and it is easy for collaborators to edit. Smallest conceptual surface. D3 is all you need for scales, Delaunay hit-testing and timers.
- **Cons:** You hand-roll state management, accessibility components (combobox, focus trap, toggles), and DOM diffing for the text cards. It depends on a third-party CDN at view time (pinning plus SRI hashes mitigates this, or vendor the file). It gets harder to maintain past about 15 steps and 3 interactive widgets.

### Recommendation

**Svelte 5 + Vite with a static build** (SvelteKit `adapter-static`, or plain Vite + Svelte if routing is not needed), with **D3 modules imported only for math** (`d3-scale`, `d3-delaunay`, `d3-force` or a beeswarm, `d3-timer`, `d3-ease`) and a **canvas dot layer plus an SVG/HTML annotation layer**. Data ships as pre-computed static JSON (race list, styles, margins, % counted, call status) produced by the analysis pipeline, so re-running the analysis only means rebuilding. Vendor all JS into the bundle (no CDN at view time). Keep the simulation client-side (bootstrapping about 600 races 10,000 times is cheap; run it in a Web Worker so the UI does not stall) **and** ship a precomputed result for reduced-motion and no-JS readers. Fallback plan if timelines are tight: Option B with the same JSON contract. The data format and the step list carry over unchanged between the two options.

### Build checklist (my recommendation)

1. `steps.json`: id, card text, stage layout key, highlighted race ids, a11y description template.
2. `races.json`: id, office, state, district, lean, 2024 margin, 2026 margin, % expected vote counted, called (bool), caller, dem_style, source URL.
3. The stage component exposes `setLayout(key, {highlight})` and owns canvas, hit-testing and the reduced-motion branch.
4. The stepper owns the progress bar, keyboard handling, tap zones, the live region and URL hash (`#step-7`) for deep links and sharing.
5. Table view generated from the same data; a "View as table" link on every chart state.
6. Test matrix: iOS Safari (toolbar resize), low-end Android Chrome (canvas fps), VoiceOver + NVDA, 200% zoom, `prefers-reduced-motion`, CVD simulation.

---

## Sources

- The Real Kevin Bacon (The Pudding), page text and served markup: https://pudding.cool/2026/10/kevin-bacon
- The Pudding svelte-starter README: https://github.com/the-pudding/svelte-starter
- The Pudding, "Responsive scrollytelling best practices": https://pudding.cool/process/responsive-scrollytelling/
- The Pudding, "How to implement scrollytelling with six different libraries": https://pudding.cool/process/how-to-implement-scrollytelling/
- Scrollama README (Russell Goldenberg): https://github.com/russellsamora/scrollama
- 50+1, "How 50+1 designed our 2026 election forecast page": https://blog.fiftyplusone.news/p/how-501-designed-our-2026-election
- 538 2020 "ball swarm" design (original 538 URL now redirects to ABC; description via search results and commentary): https://fivethirtyeight.com/features/how-we-designed-the-look-of-our-2020-forecast and https://reallifemag.com/what-the-chart-wants/
- 538/ABC 2024 "what-if" simulation filtering and histogram of simulations (search-result summaries of ABC/538 explainers): https://projects.fivethirtyeight.com/trump-harris-2024-election-map
- Reuters Institute on the NYT needle: https://reutersinstitute.politics.ox.ac.uk/news/moving-needle-how-new-york-times-aims-guide-readers-through-americas-most-uncertain-election
- Quartz on needle jitter: https://qz.com/831944/the-new-york-times-election-result-projections-are-mostly-random-jitters
- FlowingData on needle uncertainty: https://flowingdata.com/2016/11/15/showing-uncertainty-during-the-live-election-forecast/
- Bocoup, "Smoothly animate thousands of points with HTML5 Canvas and D3": https://bocoup.com/blog/smoothly-animate-thousands-of-points-with-html5-canvas-and-d3
- SvelteKit adapter-static docs: https://svelte.dev/docs/kit/adapter-static
- MDN, CSS length / viewport units: https://developer.mozilla.org/en-US/docs/Web/CSS/length
- W3C, Understanding SC 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Elicitation study (predict-first charts): https://arxiv.org/abs/2401.05511
- Colorblind map guidance: https://mapcreator.io/see-the-world-differently-a-guide-to-colorblind-friendly-maps/ and https://brand.design-system.service.gov.uk/colour/maps
- Northwestern MU Collective on forecast trust: https://mccormick.northwestern.edu/news/articles/2024/07/building-informative-and-trustworthy-election-forecasts
