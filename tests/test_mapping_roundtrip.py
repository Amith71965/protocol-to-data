"""Round-trip verification of the mapping against the published data.

This is the evidence behind the mapping specification: each domain is
transposed to the CRF page it came from and mapped back, then compared with
what the study actually published.
"""

from __future__ import annotations

import pytest

from p2d.ingest.reader import read_domain
from p2d.mapping import demographics
from p2d.mapping.domains import COMPARISON_KEYS, FINDINGS_DOMAINS, reference_dates, roundtrip
from p2d.mapping.findings import split_collected
from p2d.mapping.scores import HACHINSKI, MMSE, derive_total
from p2d.mapping.verify import compare

pytestmark = pytest.mark.requires_data

#: Variables that do not fully reconcile, with the floor each must stay above.
#: A regression below these is a real defect, not a tolerance to be widened.
LB_FLOORS = {
    "LBSTRESC": 0.999,
    "LBSTRESN": 0.999,
    "LBSTRESU": 0.98,
    "LBNRIND": 0.94,
}


@pytest.fixture(scope="module")
def references(raw_dir):
    return reference_dates(raw_dir)


def test_demographics_round_trips_exactly(raw_dir) -> None:
    dm = read_domain(raw_dir, "dm")

    report = compare(dm, demographics.roundtrip(dm), ["USUBJID"], "DM")

    assert report.exact, report.summary()


@pytest.mark.parametrize("name", ["VS", "QS"])
def test_findings_domain_round_trips_exactly(raw_dir, references, name) -> None:
    spec = FINDINGS_DOMAINS[name]
    frame = read_domain(raw_dir, name.lower())

    report = compare(
        split_collected(frame, spec).collected,
        roundtrip(frame, spec, references),
        COMPARISON_KEYS[name],
        name,
        ignore=list(spec.not_reproducible),
    )

    assert report.exact, report.summary()


def test_laboratory_reconstruction_holds_its_measured_floors(raw_dir, references) -> None:
    """LB does not reconcile fully; the gaps are known and bounded."""
    spec = FINDINGS_DOMAINS["LB"]
    frame = read_domain(raw_dir, "lb")

    report = compare(
        split_collected(frame, spec).collected,
        roundtrip(frame, spec, references),
        COMPARISON_KEYS["LB"],
        "LB",
        ignore=list(spec.not_reproducible),
    )

    assert report.rows_original == report.rows_rebuilt
    assert {r.variable for r in report.mismatched} == set(LB_FLOORS)
    for result in report.mismatched:
        assert result.match_rate >= LB_FLOORS[result.variable], result.variable


def test_no_record_is_lost_or_invented(raw_dir, references) -> None:
    for name, spec in FINDINGS_DOMAINS.items():
        frame = read_domain(raw_dir, name.lower())
        split = split_collected(frame, spec)
        rebuilt = roundtrip(frame, spec, references)

        assert len(rebuilt) == len(split.collected), name
        assert len(split.collected) + len(split.sponsor_derived) == len(frame), name


def test_derived_mmse_total_reproduces_the_study_report(raw_dir) -> None:
    """The CSR states a baseline MMSE range of 10 to 24 and a mean of 18.1.

    Reproducing both from item-level data is independent evidence that the
    derivation is correct, before any eligibility rule depends on it.
    """
    qs = read_domain(raw_dir, "qs")

    totals = derive_total(qs, MMSE)["total"]

    assert len(totals) == 254
    assert totals.min() == 10
    assert totals.max() == 24
    assert round(float(totals.mean()), 1) == 18.1


def test_derived_hachinski_total_stays_within_its_scale(raw_dir) -> None:
    qs = read_domain(raw_dir, "qs")

    totals = derive_total(qs, HACHINSKI)["total"]

    assert len(totals) == 254
    assert totals.min() >= 0
    assert totals.max() <= HACHINSKI.max_total
