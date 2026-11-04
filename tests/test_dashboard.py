"""Dashboard data layer, tested headlessly.

The app itself is a thin view; everything it computes lives here so it can be
checked without a browser.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app import charts
from app import data_access as data
from app.palette import ARM_ORDER, OUTCOME, SERIES


@pytest.fixture
def evaluations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "usubjid": ["s1", "s2", "s1", "s2"],
            "criterion_id": ["INCL03", "INCL03", "EXCL27", "EXCL27"],
            "outcome": ["PASS", "DEVIATION", "DEVIATION", "NOT_EVALUABLE"],
            "reason": ["ok", "too high", "out of range", "no result"],
            "observed": ["22", "24", "AST=HIGH", ""],
            "source_domain": ["QS", "QS", "LB", "LB"],
            "source_key": ["a", "b", "c", ""],
        }
    )


@pytest.fixture
def deviations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "usubjid": ["s2", "s1"],
            "criterion_id": ["INCL03", "EXCL27"],
            "observed": ["24", "AST=HIGH"],
            "SITEID": ["701", "709"],
            "ARM": ["Placebo", "Xanomeline Low Dose"],
        }
    )


def test_outcome_counts_keep_a_fixed_order(evaluations) -> None:
    counts = data.outcome_counts(evaluations)

    assert list(counts["outcome"]) == ["PASS", "DEVIATION", "NOT_EVALUABLE"]
    assert list(counts["evaluations"]) == [1, 2, 1]


def test_outcome_order_is_stable_when_a_category_is_absent() -> None:
    frame = pd.DataFrame({"outcome": ["PASS"], "usubjid": ["s1"]})

    counts = data.outcome_counts(frame)

    assert list(counts["outcome"]) == ["PASS", "DEVIATION", "NOT_EVALUABLE"]
    assert list(counts["evaluations"]) == [1, 0, 0]


def test_deviations_are_counted_by_distinct_subject(deviations) -> None:
    counts = data.deviations_by_criterion(deviations)

    assert dict(zip(counts["criterion_id"], counts["subjects"], strict=True)) == {
        "INCL03": 1,
        "EXCL27": 1,
    }


def test_empty_deviations_do_not_raise(deviations) -> None:
    assert data.deviations_by_criterion(deviations.iloc[0:0]).empty


def test_filters_narrow_without_reordering(deviations) -> None:
    filtered = data.filter_deviations(deviations, criteria=["INCL03"])

    assert list(filtered["usubjid"]) == ["s2"]


def test_an_empty_filter_selection_means_no_filter(deviations) -> None:
    assert len(data.filter_deviations(deviations, criteria=[], sites=[], arms=[])) == 2


def test_filters_combine(deviations) -> None:
    assert data.filter_deviations(deviations, criteria=["INCL03"], sites=["709"]).empty


def test_severity_order_is_fixed() -> None:
    issues = pd.DataFrame({"severity": ["warning", "warning", "error"]})

    counts = data.validation_by_severity(issues)

    assert list(counts["severity"]) == ["error", "warning", "notice"]
    assert list(counts["issues"]) == [1, 2, 0]


def test_coverage_table_marks_criteria_without_a_rule(evaluations) -> None:
    gold = pd.DataFrame(
        {
            "criterion_id": ["INCL03", "EXCL27", "EXCL16"],
            "category": ["INCLUSION", "EXCLUSION", "EXCLUSION"],
            "testability": ["TESTABLE", "PARTIALLY_TESTABLE", "NOT_TESTABLE"],
            "text": ["MMSE", "Labs", "ECG"],
            "rationale": ["a", "b", "no ECG domain"],
        }
    )

    table = data.coverage_table(gold, evaluations)

    assert dict(zip(table["criterion_id"], table["has_rule"], strict=True)) == {
        "INCL03": True,
        "EXCL27": True,
        "EXCL16": False,
    }


def test_status_colours_are_never_reused_as_series_colours() -> None:
    """A status colour must not be able to impersonate a treatment arm."""
    assert not set(OUTCOME.values()) & set(SERIES)


def test_arm_order_is_fixed_so_filtering_never_repaints() -> None:
    assert ARM_ORDER[0] == "Placebo"
    assert len(ARM_ORDER) == len(set(ARM_ORDER))


def test_charts_build_from_minimal_data(evaluations, deviations) -> None:
    assert charts.outcomes(data.outcome_counts(evaluations)).to_dict()
    assert charts.deviations_by_criterion(data.deviations_by_criterion(deviations)).to_dict()


def test_chart_height_grows_with_the_number_of_rows() -> None:
    """Too little height makes Vega silently drop a category's axis label."""
    small = charts.outcomes(pd.DataFrame({"outcome": ["PASS"], "evaluations": [1]}))
    large = charts.outcomes(
        pd.DataFrame({"outcome": ["PASS", "DEVIATION", "NOT_EVALUABLE"], "evaluations": [1, 2, 3]})
    )

    assert large.to_dict()["height"] > small.to_dict()["height"]
