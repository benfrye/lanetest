# Sources: state presidential results 1976-2024

- `raw/1976-2024-president.csv` — MIT Election Data and Science Lab, "U.S. President 1976–2024",
  Harvard Dataverse, doi:10.7910/DVN/42MVDX, dataset version 10.1 (released 2026-09-04).
  Downloaded via https://dataverse.harvard.edu/api/access/datafile/13887042 on 2026-11-04.
  (The dataset now includes 2024, so `research/states.json` is used only as a cross-check.)
- `raw/codebook-us-president-1976-2020.md` — codebook, https://dataverse.harvard.edu/api/access/datafile/7241480, retrieved 2026-11-04.
- `state_two_party.csv` — derived by `analysis/errors_history/build_history.py`: D and R nominee votes per state-year
  (summed across all ballot lines carrying the nominee's name, so NY/CT fusion lines are included), two-party margin
  = 100*(D-R)/(D+R), national two-party margin from summed state votes (51 units incl. DC).
