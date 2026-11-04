# Limitations

What this project cannot do, and why. Written plainly because a compliance pipeline that overstates
its own coverage is worse than no pipeline.

## 1. The CRF source layer is derived, not real

The CDISC pilot publishes **mapped SDTM only**. A recursive listing of the whole PHUSE repository
(1,501 files, listing not truncated) contains no raw, CRF-shaped or CDASH data for this study, and
none exists elsewhere.

So the CRF layer here is **reconstructed by de-normalising the published SDTM**, using `define.xml`
origin annotations for page structure. It is labelled a derived fixture in its own directory, in each
file's header, in the mapping specification and here. It is never presented as trial data.

What makes it worth having is the round-trip: `SDTM → CRF shape → SDTM'` must reproduce the published
data. That is evidence the mapping specification is complete, in the sense that nothing the CRF layer
holds is lost or invented on the way back.

**Consequence:** this demonstrates a mapping discipline, not a mapping of genuinely unseen source data.

## 2. There is no deviation ground truth

Neither the `IE` domain (subject-level inclusion/exclusion criteria not met) nor the `DV` domain
(protocol deviations) is published for this study.

**Consequence:** the 115 flagged deviations cannot be scored for precision or recall against the
study's own record of deviations. The two MMSE findings are independently checkable — the derived
total reproduces the CSR, and the subjects' arms confirm they were randomized — but the laboratory
findings are not corroborated by anything outside this pipeline.

## 3. Criteria coverage is 23%

7 of 31 criteria have an executable rule. The remaining 24 are listed with reasons in
`reports/coverage.md`. The two reasons, in short:

- **No data exists.** No ECG domain is published, so `EXCL16` cannot be evaluated at all. The same
  applies to CNS imaging, prior xanomeline participation, caregiver arrangements, geographic
  proximity, disabilities and syphilis screening.
- **The evaluable fragment would mislead.** Medical history is MedDRA-coded, so a body-system match
  is possible — but the protocol says *serious* neurological conditions, and seriousness is not
  recorded. Matching the body system would flag far more subjects than the criterion means.

## 4. Rules that run still have caveats

| Criterion | Caveat |
|---|---|
| `INCL01` | Only the age clause is checked. Postmenopausal status is not collected. |
| `INCL06` | `DM.RFICDTC` is unpopulated for every subject, so all 254 are reported **not evaluable**. An empty variable is a documentation gap, not 254 protocol violations. |
| `EXCL27`, `EXCL28` | The protocol's threshold is the **Lilly Reference Range III**, which is proprietary and unavailable. The study's own reference ranges are used as a documented proxy, which is looser and likely over-reports. |
| `EXCL28` | Vitamin B12 and TSH are present; folate, total T4, thyroid uptake and the free thyroid index are not published. |
| `EXCL30` | The protocol restricts this to insulin-dependent diabetics, whom the data does not reliably identify, so the rule runs on everyone with a result. Only 5 of 254 have one. |

## 5. Four laboratory variables do not fully reconcile

| Variable | Match rate | Why |
|---|---:|---|
| `LBSTRESC` | 99.987% | 8 censored results (`<40`) whose converted form the pipeline does not reproduce |
| `LBSTRESN` | 99.997% | 2 records at the limit of the vitamin B12 conversion factor |
| `LBSTRESU` | 98.041% | Some unitless tests carry a blank standard unit where others carry `NO UNITS` |
| `LBNRIND` | 94.810% | Qualitative results (urinalysis colour and similar) have no numeric range to judge against |

`LBSEQ` and `QSSEQ` are **carried from source rather than derived**: the sponsor's sequence follows an
internal dataset ordering that no CRF records. `QSDRVFL` is carried for the same reason.

## 6. The LLM extraction is scored against one annotator

The gold set's 31 testability labels are a single person's reading of each criterion against the data
inventory. There is no second annotator and no inter-rater agreement figure, so the extraction
metrics measure agreement with one judgement, not with ground truth.

## 7. Scope

One study, one protocol. The mapping configuration, the eligibility rules and the data inventory in
the extraction prompt are specific to `CDISCPILOT01`. The machinery generalises; the content does not.
