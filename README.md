# Protocol-to-Data Compliance Pipeline

Checks whether clinical trial subjects actually met the protocol's eligibility criteria — going from
protocol prose down to subject-level CDISC SDTM records, and keeping every flag traceable back to the
row that produced it.

Built on the public **CDISC SDTM/ADaM Pilot Project** data (study `CDISCPILOT01`, sponsor protocol
`H2Q-MC-LZZT`): a xanomeline transdermal trial in mild-to-moderate Alzheimer's disease, 306 subjects
across 17 sites.

![Target architecture](docs/diagrams/architecture-target.svg)

## The headline result

The published data holds **no MMSE total score** — only the six individual items, with no derived
flag. The protocol's inclusion criterion is written against the total, so the pipeline derives it.

That derivation is checkable, and it checks out against the study's own Clinical Study Report:

| | Pipeline | CSR section 11 |
|---|---|---|
| Baseline MMSE range | 10 – 24 | "ranged from 10 to 24" |
| Baseline MMSE mean | **18.14** | **"mean score of 18.1"** |

Applying inclusion criterion `INCL03` (MMSE 10–23) to that derived score finds **two subjects who were
randomized and dosed despite falling outside the protocol's eligibility window**:

| Subject | Site | Age | Sex | Arm | MMSE |
|---|---|---|---|---|---|
| `01-707-1037` | 707 | 72 | F | Xanomeline Low Dose | **24** |
| `01-709-1238` | 709 | 69 | M | Xanomeline High Dose | **24** |

Both are asserted in the test suite, so they cannot quietly stop being found.

## What it does

1. **Ingest** — downloads 18 SDTM domains, `define.xml`, the CSR and CDISC terminology (120 MB),
   verifying size and SHA-256 against a committed manifest
2. **Map** — transposes SDTM to the CRF pages it came from and maps it back, proving the mapping spec
   by round-trip
3. **Validate** — runs Pinnacle 21 / CDISC CORE style conformance checks over the result
4. **Extract** — sends the protocol's eligibility prose to an LLM, returning structured rules labelled
   by how testable they are
5. **Evaluate** — runs the testable rules and reports **pass / deviation / not evaluable** per subject
6. **Present** — a dashboard over deviations, conformance findings, enrollment and coverage

## Results

| Stage | Outcome |
|---|---|
| Ingest | 18 domains, 227,889 rows, 22 artifacts checksum-pinned |
| Mapping | **DM, VS and QS round-trip exactly** (67 variables); LB reconciles on 18 of 22 |
| Validation | 9 rules; **1,828 findings**, all one real defect (below) |
| Criteria | 31 criteria hand-labelled: 2 testable, 21 partially, 8 not testable |
| Deviations | **115 flagged** across 3 criteria, over 254 randomized subjects |
| Coverage | **7 of 31 criteria (23%)** have an executable rule |

### A real conformance defect

The validator flags 1,828 laboratory records using `BUN` as the test code. `BUN` is **not** a valid
CDISC Laboratory Test Code submission value — the standard term is `UREAN`. That is a genuine
conformance issue in published regulatory-grade data, found by a rule with a test behind it.

### Why coverage is 23% and not higher

Because that is what the data supports. Of the 24 criteria without a rule:

- 8 have **no data at all** — no ECG domain is published, so no ECG criterion can be evaluated; nor
  can imaging, prior-study participation, caregiver arrangements or geography
- 16 are **partially evaluable but would mislead** — the data records a medical-history body system
  but not whether a condition was "serious", so matching the body system would flag far more
  subjects than the protocol means

Every one carries a written reason in [`reports/coverage.md`](reports/coverage.md). A rule that
evaluates part of a criterion and reports a clean pass would overstate what was checked, so a
criterion gets either a rule whose limits are stated, or no rule at all.

## Quick start

```bash
uv venv --python 3.12
uv sync --all-extras
uv run python scripts/download_data.py      # ~120 MB, checksum verified
uv run python scripts/profile_data.py       # docs/data_inventory.md
uv run python scripts/build_sdtm.py         # mapping + round-trip proof
uv run python scripts/validate_sdtm.py      # conformance findings
uv run python scripts/build_gold_set.py     # 31 hand-labelled criteria
uv run python scripts/check_deviations.py   # deviations + coverage
uv run streamlit run app/streamlit_app.py   # dashboard
```

The criteria extraction needs a model. Copy `.env.example` to `.env`, add a key, then:

```bash
uv run python scripts/extract_criteria.py --live
```

Without a key it runs cache-only and says so rather than failing silently. Responses are cached by a
hash of the request, so **the test suite and CI never make a network call**.

## Data and licensing

Nothing is committed — the SDTM datasets alone are roughly 100 MB.

| Artifact | Source | License |
|---|---|---|
| SDTM datasets, `define.xml`, CSR | [`phuse-org/phuse-scripts`](https://github.com/phuse-org/phuse-scripts) | [MIT](https://github.com/phuse-org/phuse-scripts/blob/master/LICENSE.md) |
| CDISC SDTM Controlled Terminology | [NCI EVS](https://www.cancer.gov/research/resources/terminology/cdisc) | Free, no licensing restrictions |

The same material is mirrored in `cdisc-org/sdtm-adam-pilot-project`, which carries **no license
file**, so everything is pulled from the MIT-licensed source instead.

The protocol text embedded in the CSR is **Copyright 2006 Eli Lilly and Company** and is not
redistributed here. The committed gold set stores criterion identifiers, the CDISC-published `IETEST`
text, our own testability labels and section references — not the sponsor's prose.

## Limitations

The honest version is in **[docs/limitations.md](docs/limitations.md)**. The three that matter most:

- **There is no raw CRF data for this study** — anywhere. The CRF source layer is *derived* from the
  published SDTM and labelled as a fixture throughout. The round-trip is what makes it useful.
- **There is no deviation ground truth.** No `IE` or `DV` domain is published, so the 115 findings
  cannot be scored against the study's own list of deviations.
- **Coverage is 23%, not 100%**, and the project says so everywhere rather than quietly checking the
  evaluable fragment of a criterion and calling it a pass.

## Layout

```
src/p2d/
  ingest/      download with checksums, XPORT reader, profiling
  mapping/     CRF <-> SDTM, derivations, unit conversion, round-trip verification
  validate/    conformance rules, controlled terminology, reporting
  criteria/    schema, protocol text extraction, LLM providers, response cache, scoring
  deviations/  eligibility rules and the evaluation engine
app/           Streamlit dashboard (data layer kept separate and tested headlessly)
scripts/       one entry point per pipeline stage
docs/          generated specification, inventory, rules, diagrams
```

## Tests

```bash
uv run pytest
uv run ruff check .
```

197 tests. Every transformation and every rule has its own, including the CSR anchor and the two
known deviations. Tests that need the downloaded data are marked `requires_data` and skip without it;
CI restores it from cache so they actually run.

## License

MIT — see [LICENSE](LICENSE).
