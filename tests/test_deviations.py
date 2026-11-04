"""Eligibility rules and the deviation engine."""

from __future__ import annotations

import pandas as pd
import pytest

from p2d.deviations.engine import (
    build_context,
    coverage,
    evaluate,
    per_criterion_summary,
    randomized_subjects,
)
from p2d.deviations.outcomes import Outcome, to_frame
from p2d.deviations.rules import (
    EXECUTABLE_RULES,
    NO_RULE_REASONS,
    EvaluationContext,
    excl30_glycosylated_haemoglobin,
    incl01_age_at_least_fifty,
    incl03_mmse_in_range,
    incl06_consent_recorded,
)
from p2d.mapping.scores import MMSE


def dm(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def mmse_items(subject: str, scores: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "USUBJID": [subject] * len(scores),
            "QSCAT": [MMSE.category] * len(scores),
            "QSTESTCD": [f"MMITM0{i + 1}" for i in range(len(scores))],
            "QSSTRESN": scores,
            "VISIT": ["SCREENING 1"] * len(scores),
            "VISITNUM": [1.0] * len(scores),
            "QSDTC": ["2013-12-26"] * len(scores),
        }
    )


def context(dm_frame, qs=None, lb=None) -> EvaluationContext:
    empty_qs = pd.DataFrame(
        columns=["USUBJID", "QSCAT", "QSTESTCD", "QSSTRESN", "VISIT", "VISITNUM", "QSDTC"]
    )
    empty_lb = pd.DataFrame(
        columns=["USUBJID", "LBTESTCD", "LBBLFL", "LBNRIND", "LBORRES"]
    )
    return build_context(
        dm_frame,
        empty_qs if qs is None else qs,
        empty_lb if lb is None else lb,
    )


SUBJECT = {"USUBJID": "s1", "SITEID": "701", "ARM": "Placebo", "AGE": 72.0, "SEX": "F", "RFICDTC": ""}


# --- population ----------------------------------------------------------------

def test_screen_failures_are_excluded_from_evaluation() -> None:
    """The study excluded them correctly; flagging one would be a false positive."""
    frame = dm([SUBJECT, {**SUBJECT, "USUBJID": "s2", "ARM": "Screen Failure"}])

    assert list(randomized_subjects(frame)["USUBJID"]) == ["s1"]


def test_screen_failures_never_appear_in_any_outcome() -> None:
    frame = dm([SUBJECT, {**SUBJECT, "USUBJID": "sf", "ARM": "Screen Failure"}])

    results = evaluate(context(frame))

    assert "sf" not in {e.usubjid for e in results}


# --- INCL03, the flagship rule --------------------------------------------------

def test_mmse_within_range_passes() -> None:
    frame = dm([SUBJECT])
    qs = mmse_items("s1", [5, 5, 3, 5, 3, 1])  # total 22

    result = incl03_mmse_in_range(context(frame, qs=qs))[0]

    assert result.outcome is Outcome.PASS
    assert result.observed == "22"


@pytest.mark.parametrize("scores,total", [([5, 5, 3, 5, 3, 3], 24), ([2, 2, 1, 2, 1, 1], 9)])
def test_mmse_outside_range_is_a_deviation(scores, total) -> None:
    qs = mmse_items("s1", scores)

    result = incl03_mmse_in_range(context(dm([SUBJECT]), qs=qs))[0]

    assert result.outcome is Outcome.DEVIATION
    assert result.observed == str(total)


def test_mmse_boundaries_are_inclusive() -> None:
    for scores in ([5, 5, 0, 0, 0, 0], [5, 5, 3, 5, 3, 2]):  # totals 10 and 23
        result = incl03_mmse_in_range(context(dm([SUBJECT]), qs=mmse_items("s1", scores)))[0]
        assert result.outcome is Outcome.PASS


def test_missing_questionnaire_is_not_evaluable_rather_than_a_pass() -> None:
    result = incl03_mmse_in_range(context(dm([SUBJECT])))[0]

    assert result.outcome is Outcome.NOT_EVALUABLE


def test_incomplete_questionnaire_is_not_evaluable() -> None:
    """Summing five of six items could turn a deviation into a pass."""
    qs = mmse_items("s1", [5, 5, 3, 5, 3])

    result = incl03_mmse_in_range(context(dm([SUBJECT]), qs=qs))[0]

    assert result.outcome is Outcome.NOT_EVALUABLE
    assert "incomplete" in result.reason


def test_every_evaluation_names_its_source() -> None:
    result = incl03_mmse_in_range(context(dm([SUBJECT]), qs=mmse_items("s1", [5, 5, 3, 5, 3, 1])))[0]

    assert result.source_domain == "QS"
    assert result.source_key


# --- INCL01 --------------------------------------------------------------------

def test_age_at_the_minimum_passes() -> None:
    result = incl01_age_at_least_fifty(context(dm([{**SUBJECT, "AGE": 50.0}])))[0]

    assert result.outcome is Outcome.PASS


def test_age_below_the_minimum_is_a_deviation() -> None:
    result = incl01_age_at_least_fifty(context(dm([{**SUBJECT, "AGE": 49.0}])))[0]

    assert result.outcome is Outcome.DEVIATION


def test_age_rule_states_what_it_does_not_check() -> None:
    result = incl01_age_at_least_fifty(context(dm([SUBJECT])))[0]

    assert "ostmenopausal" in result.reason


# --- INCL06 --------------------------------------------------------------------

def test_unpopulated_consent_date_is_not_evaluable_not_a_deviation() -> None:
    """An empty variable is a documentation gap, not a protocol violation."""
    result = incl06_consent_recorded(context(dm([SUBJECT])))[0]

    assert result.outcome is Outcome.NOT_EVALUABLE


def test_recorded_consent_date_passes() -> None:
    frame = dm([{**SUBJECT, "RFICDTC": "2013-12-20"}])

    result = incl06_consent_recorded(context(frame))[0]

    assert result.outcome is Outcome.PASS


# --- EXCL30 --------------------------------------------------------------------

def _lb(value: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"USUBJID": ["s1"], "LBTESTCD": ["HBA1C"], "LBBLFL": ["Y"], "LBNRIND": [""], "LBORRES": [value]}
    )


def test_hba1c_above_the_limit_is_a_deviation() -> None:
    result = excl30_glycosylated_haemoglobin(context(dm([SUBJECT]), lb=_lb("10.1")))[0]

    assert result.outcome is Outcome.DEVIATION


def test_hba1c_within_the_limit_passes() -> None:
    result = excl30_glycosylated_haemoglobin(context(dm([SUBJECT]), lb=_lb("6.2")))[0]

    assert result.outcome is Outcome.PASS


def test_absent_hba1c_is_not_evaluable() -> None:
    result = excl30_glycosylated_haemoglobin(context(dm([SUBJECT])))[0]

    assert result.outcome is Outcome.NOT_EVALUABLE


# --- coverage honesty ----------------------------------------------------------

def test_criteria_without_a_rule_all_carry_a_reason() -> None:
    """A blank in the coverage report would read as an oversight."""
    gold = pd.read_csv("data/gold/criteria_gold.csv", keep_default_na=False)
    testable_ish = gold[gold["testability"] != "NOT_TESTABLE"]["criterion_id"]

    for criterion_id in testable_ish:
        if criterion_id not in EXECUTABLE_RULES:
            assert NO_RULE_REASONS.get(criterion_id), criterion_id


def test_coverage_is_not_rounded_up() -> None:
    gold = pd.read_csv("data/gold/criteria_gold.csv", keep_default_na=False)
    results = evaluate(context(dm([SUBJECT])))

    cov = coverage(results, gold, context(dm([SUBJECT])))

    assert cov.total_criteria == 31
    assert cov.executable == len(EXECUTABLE_RULES)
    assert cov.rule_coverage == len(EXECUTABLE_RULES) / 31
    assert cov.rule_coverage < 1.0


def test_summary_covers_every_criterion() -> None:
    gold = pd.read_csv("data/gold/criteria_gold.csv", keep_default_na=False)

    summary = per_criterion_summary(evaluate(context(dm([SUBJECT]))), gold)

    assert len(summary) == 31
    assert summary["has_executable_rule"].sum() == len(EXECUTABLE_RULES)


def test_evaluation_table_has_a_stable_shape() -> None:
    frame = to_frame(evaluate(context(dm([SUBJECT]))))

    assert list(frame.columns) == [
        "usubjid",
        "criterion_id",
        "outcome",
        "reason",
        "observed",
        "source_domain",
        "source_key",
    ]
