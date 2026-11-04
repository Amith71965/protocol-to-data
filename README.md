# Protocol-to-Data Compliance Pipeline

Checks whether clinical trial subjects actually met the protocol's eligibility criteria, by going
from protocol prose all the way down to subject-level CDISC SDTM records — and keeping every flag
traceable back to the source row that produced it.

Built on the public **CDISC SDTM/ADaM Pilot Project** data (study `CDISCPILOT01`), a xanomeline
transdermal trial in mild-to-moderate Alzheimer's disease.

> **Status:** under construction. Phases are landing one at a time; see the plan in
> `docs/` and the honest limitations in `docs/limitations.md`.

## What it does

1. **Map** a CRF-shaped source layer to CDISC SDTM domains against a written mapping spec
2. **Validate** the result with Pinnacle 21-style conformance checks
3. **Extract** the protocol's eligibility criteria into structured, machine-checkable rules with an LLM
4. **Evaluate** those rules against the data and flag protocol deviations with full traceability
5. **Present** deviations, validation issues, enrollment and criteria coverage in a dashboard

## Headline result

The pipeline derives the MMSE total score from item-level SDTM `QS` records (the published data has
no total and no derived flag), and that derivation independently reproduces the figures printed in
the study's own Clinical Study Report:

| | Pipeline | CSR section 11 |
|---|---|---|
| MMSE range | 10 – 24 | "ranged from 10 to 24" |
| MMSE mean | 18.14 | "mean score of 18.1" |

Applying inclusion criterion `INCL03` (MMSE 10–23) to that derived score finds **two subjects who
were randomized and dosed despite falling outside the protocol's eligibility window**.

## Data and licensing

All study data is downloaded at runtime — nothing is committed, because the SDTM datasets total
roughly 100 MB.

| Artifact | Source | License |
|---|---|---|
| SDTM datasets, `define.xml`, CSR | [`phuse-org/phuse-scripts`](https://github.com/phuse-org/phuse-scripts) | [MIT](https://github.com/phuse-org/phuse-scripts/blob/master/LICENSE.md) |
| CDISC SDTM Controlled Terminology | [NCI EVS](https://www.cancer.gov/research/resources/terminology/cdisc) | Free, no licensing restrictions |

The protocol text embedded in the CSR is **Copyright 2006 Eli Lilly and Company** and is not
redistributed here. The committed gold set stores criterion identifiers, the CDISC-published
`IETEST` text, our own testability labels and protocol section references — not the sponsor's prose.

## Quick start

```bash
uv venv --python 3.12
uv sync --all-extras
uv run python scripts/download_data.py
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
