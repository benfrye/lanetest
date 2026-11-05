# SCHEMA_NOTES: deviations from METHODOLOGY §6.4

Generated 2026-11-05T03:06:00+00:00. Read with `model_params.json`.

1. **File name / gate.** No blocking FAIL: the file is `analysis/output/model_params.json`. On a blocked run the pipeline instead writes the schema-identical `model_params.BLOCKED.json` and deletes any stale `model_params.json` (§7 gate).
2. **`meta.fit_level = 3`.** At Level 5 (not this run unless stated) every `style.presets.*` block would hold prior draws with an extra `source` string and `dial_enabled = false`. New in this run: `copy_flags.models_disagree` ({archetype: bool}); when true for an archetype, `reveal.adjusted[a]` carries `delta_range_models` [lo, hi] (Gibbs median and OLS-FE EB estimate) and `delta_range_sources`, and copy must name both numbers (decision O-1c).
3. **`national.E24 = -1.500`**, computed from certified state totals in `states.json` (two-party). METHODOLOGY quotes −1.43; it cannot be reproduced from the file. `environment.presets.rerun2024.value` uses the same number so the identity test (V1) holds.
4. **District units** (`ME-1`, `ME-2`, `NE-1..3`) carry `district_sd = 1.5`, and `errors.district_sd = 1.5` is written explicitly (decision O-5; matches the JS default in `site/src/lib/sim/model.js`). District `F`, `sigma_idio` and `G` are copies of the parent state's (the JS engine uses the parent's k anyway). Both engines draw `eps_district = eps_parent + N(0, district_sd^2)`; V2 parity of the bank is exact (see validation.json).
5. **`errors.backtest.cov80_2016 = null`**: no 2012 results on disk. `cov80_2020` and `cov80_2024` are the 2016→20 and 2020→24 transitions. `errors.calibrated = false`.
6. **`style.presets.*.beta_PW` / `beta_LY`** are arrays of 1000 zeros (gated off; "set to 0, not prior draws"). In `style.gaussian`, the γ rows of `Vhat` have variance 1e4 (no data information) and zero covariance.
7. **δ reference point.** `delta[a] = beta_L*(Lbar_a - 1) + beta_P*Pbar_a + u_a` uses empirical centroids, so `delta.mainstream_liberal` = beta_P × 0.094 (small, not exactly 0). ΔV is still V_a − V_mainstream_liberal under common random numbers.
8. **`reveal` additions**: `adjusted[a]` adds `min_n_ok`, `mostly_prior`; `decomposition[a]` adds `office` (office/period intercepts); `maine` adds `incumbency_pts`, `style_pts`, `nominee`, `nyt_implied`; `nyt9` = {table, sd_across_states, psi_P}. `reveal.raw[a].dist_wnc / dist_y1829 / dist_urban` are **state-level** proxies (no district ACS).
9. **Nullable fields**: `candidates_*.home`, `poll_nat_primary`, `market_nom` can be null; `sim5.units[DC].pct_counted` is null; `transfer_pi.evidence.historical_pres_mid_ratio` is null.
10. **`primary`**: `zeta.{left,moderate}` and `b_populist` are 1000 draws; `eta.{left,moderate}` are 1000×4 draws. `validation.coalition_enabled = False`: the engine should use η = 0 (prior means) when it is false. Delegates and the `dnc2024` calendar are approximations of the 2024 rules and dates.
11. **`copy_flags.placebo_flag` / `direction_depends_on_prior`** have keys for the four non-reference archetypes only.
12. **`meta.pipeline_commit`** is a content hash of `analysis/pipeline/*` (`nogit-…`); the project is not a git repository.
13. **`meta.validation_summary`** (extra) maps V1–V20 to status.
14. **`style.gaussian.dial_enabled = False`**: V15 checks the Gaussian dial against the exact preset fits; when it fails (as for the literature and discount presets after the O-1 model changes), only the four exact presets should be offered.
15. `races.json` and `story_data/*` are not in §6.4; their fields are described inside each file.
