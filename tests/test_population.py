"""Population facts the eligibility rules depend on.

These run against the real downloaded data. They are the project's primary
evidence that the pipeline is reading the study it claims to read.
"""

from __future__ import annotations

import pytest

from p2d.ingest.reader import read_domain

pytestmark = pytest.mark.requires_data


def test_demographics_arm_split(raw_dir) -> None:
    dm = read_domain(raw_dir, "dm")
    counts = dm["ARM"].value_counts().to_dict()

    assert len(dm) == 306
    assert counts == {
        "Placebo": 86,
        "Xanomeline High Dose": 84,
        "Xanomeline Low Dose": 84,
        "Screen Failure": 52,
    }
    assert 86 + 84 + 84 + 52 == len(dm)


def test_randomized_population_is_254(raw_dir) -> None:
    dm = read_domain(raw_dir, "dm")

    randomized = dm[dm["ARM"] != "Screen Failure"]

    assert len(randomized) == 254


def test_screen_failures_have_no_collected_data(raw_dir) -> None:
    """Why eligibility is evaluated on the randomized set, not all 306."""
    dm = read_domain(raw_dir, "dm")
    screen_failures = set(dm.loc[dm["ARM"] == "Screen Failure", "USUBJID"])

    for domain in ("qs", "lb", "mh"):
        subjects = set(read_domain(raw_dir, domain)["USUBJID"])
        assert not (screen_failures & subjects), f"{domain} unexpectedly covers screen failures"


def test_no_subject_is_younger_than_the_protocol_minimum(raw_dir) -> None:
    """INCL01 requires at least 50 years of age."""
    dm = read_domain(raw_dir, "dm")

    assert dm["AGE"].min() >= 50


def test_trial_inclusion_criteria_domain_holds_31_criteria(raw_dir) -> None:
    """TI supplies the canonical identifiers Phase 4 aligns extractions to."""
    ti = read_domain(raw_dir, "ti")

    assert len(ti) == 31
    assert set(ti["IECAT"]) == {"INCLUSION", "EXCLUSION"}
    assert (ti["IECAT"] == "INCLUSION").sum() == 8
    assert (ti["IECAT"] == "EXCLUSION").sum() == 23
    assert ti["IETESTCD"].is_unique


def test_no_adverse_events_domain_is_published(raw_dir) -> None:
    """Recorded as a test so the README's claim cannot drift from the data."""
    assert not (raw_dir / "sdtm" / "ae.xpt").exists()
