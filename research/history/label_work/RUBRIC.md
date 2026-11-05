# Lane-labeling rubric for historical House Democratic nominees (2018, 2022)

Input for the label coders. Same rubric as the 2026 coding in `research/house/*.json`, calibrated to how
it was actually applied there.

## Fields per nominee
- `ideology`: `left` | `liberal` | `moderate` (`conservative` only for a Democrat to the right of the Blue Dogs).
- `posture`: `populist` | `mixed` | `establishment`.
- `archetype` (derived, do not choose freely):
  - left + populist → `left_populist`; **liberal + populist → `left_populist`** (2026 rule)
  - left + mixed/establishment → `progressive`
  - moderate (or conservative) + populist → `center_populist`
  - moderate + mixed/establishment → `moderate`
  - liberal + mixed/establishment → `mainstream_liberal`
- `style_confidence`: `high` (an explicit marker or self-description found in a source you fetched),
  `medium` (consistent profile from fetched sources, no single explicit marker), `low` (thin evidence).
- `style_evidence`: one line naming the markers or quotes used.
- `label_source_url`: the best single URL supporting the label (ideally one you fetched).
- `verified_fetch`: true if you fetched a page this run that supports the label; false if from memory.

## Evidence rule
Only evidence that existed **before that election day** (2018-11-06 or 2022-11-08): campaign positions,
endorsements, caucus membership at the time, pre-election coverage. Do NOT use the result, later caucus
joins (e.g. someone elected in 2018 who joined the Blue Dogs in 2019), later votes, or post-election narratives.

## Ideology
- `left`: Justice Democrats; DSA member or DSA-endorsed; Brand New Congress; self-described democratic
  socialist; insurgent from the left (beat or challenged a party-backed/incumbent Democrat from the left);
  Squad; CPC chair/whip-level leaders who are prominently left (e.g. Jayapal, Khanna, Grijalva, Pocan in 2018 era);
  or a campaign built on Medicare for All plus Sanders / Our Revolution / WFP / Sunrise / PCCC backing.
  **Plain CPC membership alone is NOT left** (in 2026 most CPC members were coded liberal).
  A single Our Revolution / PCCC / WFP endorsement with an otherwise conventional profile → `liberal`.
- `moderate`: Blue Dog member, or Blue Dog PAC endorsed; Problem Solvers member; explicit centrist branding
  ("moderate", "independent voice", "bipartisan problem-solver", opposes Medicare for All, pledged not to
  back Pelosi for leader); NewDem Action Fund endorsed AND centrist branding; New Democrat Coalition member who
  runs as a swing-seat centrist. Plain New Dem membership in a safe seat → `liberal`.
- `liberal`: everyone else (DCCC Red to Blue recruits with no left or centrist markers, EMILY's List,
  conventional party-line Democrats).

## Posture
- `populist`: outsider / anti-establishment, working-class identity at the centre of the campaign,
  anti-corporate economic message (no-corporate-PAC pledge plus "rigged", "billionaires", "special interests",
  "not a career politician"), or an insurgent who beat the party-backed candidate on that message.
  Examples from 2026: a former janitor/mail carrier running as "an independent, working-class voice";
  "NOT AN INSIDER ... working-class campaign ... not corporate interests"; a blue-collar centrist
  ("moderate version of Democratic populism").
- `mixed`: some of those elements alongside institutional backing (e.g. no-corporate-PAC pledge or labour
  background, but a conventional campaign; or a left insurgent who is now an incumbent).
- `establishment`: conventional, party-backed, institutional framing; most incumbents.

## Calibration (2026 coding)
- progressive: AOC, Omar, Tlaib, Pressley, Summer Lee, Casar, Delia Ramirez, Jayapal, Khanna, Frost (incumbents, left + mixed/establishment).
- moderate: Gottheimer, Cuellar, Spanberger-type frontliners, Houlahan (New Dem + Problem Solvers), Susie Lee, Sharice Davids, Lizzie Fletcher, Josh Harder, Adam Gray, Don Davis, Sanford Bishop.
- center_populist: Marie Gluesenkamp Perez, Rebecca Cooke.
- left_populist: working-class outsider challengers (often long shots in red seats), Richard Ojeda (NC-9 2026).
- mainstream_liberal: Raskin, Pocan (2026), Scanlon, Dean, McGovern, most CPC members, most Red to Blue recruits.

## Output file
JSON: `{"cycle": <year>, "coder": "<batch name>", "labels": {"<race id>": {"name": ..., "ideology": ..., "posture": ...,
"archetype": ..., "style_confidence": ..., "style_evidence": ..., "label_source_url": ..., "verified_fetch": true|false}}}`
One entry for every race in the batch. If you cannot find anything, still enter your best label with `low` confidence.
