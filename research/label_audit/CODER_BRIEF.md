# Blind coder brief: 2026 Democratic nominee lane labels

You are a blind second coder. You get only each nominee's name, state, district, office and Republican
opponent. Code the Democratic nominee's ideology and campaign posture **as they stood before election day
(2026-11-03)**.

## Blinding rules (strict)
- Do NOT open any file in this project other than this brief and your batch file. In particular never open
  `analysis/`, `research/house`, `research/senate.json`, `research/governors.json`, `research/candidates_*.json`
  or `research/history/`. They contain the labels you are auditing.
- Ignore election results. If a page mentions who won, the margin, or post-election commentary
  ("overperformed", "populist wave", etc.), do not use it and do not record it.
- Use only evidence dated **before 2026-11-03**:
  - Wayback Machine snapshots: `https://web.archive.org/web/<timestamp>/<url>` with timestamp < 20261103
    (e.g. `https://web.archive.org/web/20261015000000*/ballotpedia.org/...` style; fetch a concrete snapshot such as
    `https://web.archive.org/web/20261020/https://ballotpedia.org/Jane_Doe`, and record the snapshot timestamp the
    archive actually served, from the final URL).
  - Dated news articles (publication date before 2026-11-03; record the date).
  - Endorsement lists of Justice Democrats, DSA, Our Revolution, WFP, Congressional Progressive Caucus (PAC/members),
    Blue Dog Coalition / Blue Dog PAC, New Democrat Coalition / NewDem Action Fund, Problem Solvers Caucus,
    DCCC Red to Blue — ideally archived snapshots dated before 2026-11-03.
- Prior-knowledge (memory) is allowed as a fallback only; mark `verified_fetch: false` and `source_date: null`.
- Do not send personal data in any request (no email addresses, names of the user, etc.).

## Fields
- `ideology`: `left` | `liberal` | `moderate` | `conservative` (conservative only for a Democrat right of the Blue Dogs).
- `posture`: `populist` | `mixed` | `establishment`.
- `archetype` — derived, do not choose freely:
  - left + populist → `left_populist`; liberal + populist → `left_populist`
  - left + mixed/establishment → `progressive`
  - moderate/conservative + populist → `center_populist`
  - moderate/conservative + mixed/establishment → `moderate`
  - liberal + mixed/establishment → `mainstream_liberal`
- `confidence`: `high` (explicit marker/self-description in a fetched dated source), `medium` (consistent profile,
  no single explicit marker), `low` (thin evidence).
- `evidence`: one or two lines naming the markers/quotes used.
- `source_url`: best single URL (a web.archive.org snapshot URL or dated article).
- `source_date`: YYYY-MM-DD of the snapshot/article, or null.
- `pre_election_verified`: true only if you actually fetched that URL this run and its date is before 2026-11-03.
- `verified_fetch`: true if you fetched any page this run supporting the label.

## Ideology
- `left`: Justice Democrats; DSA member/endorsed; self-described democratic socialist; insurgent from the left
  (beat/challenged a party-backed or incumbent Democrat from the left); Squad; prominent CPC leaders known as
  left; or a Medicare-for-All campaign with Sanders / Our Revolution / WFP / Sunrise / PCCC backing.
  Plain CPC membership alone is NOT left. A single Our Revolution / PCCC / WFP endorsement with an otherwise
  conventional profile → `liberal`.
- `moderate`: Blue Dog member or Blue Dog PAC endorsed; Problem Solvers member; explicit centrist branding
  ("moderate", "independent voice", "bipartisan problem-solver", opposes Medicare for All, won't back party
  leadership); NewDem Action Fund endorsed AND centrist branding; New Dem member running as swing-seat centrist.
  Plain New Dem membership in a safe seat → `liberal`.
- `liberal`: everyone else (Red to Blue recruits without left or centrist markers, EMILY's List, conventional
  party-line Democrats).

## Posture
- `populist`: outsider / anti-establishment, working-class identity central to the campaign, anti-corporate
  economic message (no-corporate-PAC pledge plus "rigged", "billionaires", "special interests", "not a career
  politician"), or an insurgent who beat the party-backed candidate on that message. Examples: a former janitor
  running as "an independent, working-class voice"; a blue-collar centrist running a "moderate version of
  Democratic populism".
- `mixed`: some populist elements alongside institutional backing (no-corporate-PAC pledge or labour background
  in an otherwise conventional campaign; a left insurgent who is now an incumbent).
- `establishment`: conventional, party-backed, institutional framing; most incumbents.

## Output
Write JSON to `research/label_audit/coded/coded_batch_<N>.json`:
`{"batch": N, "labels": {"<id>": {"name":..., "ideology":..., "posture":..., "archetype":..., "confidence":...,
"evidence":..., "source_url":..., "source_date":..., "pre_election_verified": bool, "verified_fetch": bool}}}`
One entry for every race. If you find nothing, still give your best label with `low` confidence.
