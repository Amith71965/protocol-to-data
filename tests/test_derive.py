"""Shared SDTM derivations."""

from __future__ import annotations

import pandas as pd

from p2d.mapping.derive import baseline_flag, make_usubjid, sequence_number, study_day


def test_usubjid_is_assembled_from_site_and_subject() -> None:
    result = make_usubjid(pd.Series(["701"]), pd.Series(["1015"]))

    assert result.iloc[0] == "01-701-1015"


def test_study_day_one_is_the_reference_date() -> None:
    """CDISC study day has no day zero."""
    result = study_day(pd.Series(["2014-01-02"]), pd.Series(["2014-01-02"]))

    assert result.iloc[0] == 1


def test_day_before_reference_is_minus_one() -> None:
    result = study_day(pd.Series(["2014-01-01"]), pd.Series(["2014-01-02"]))

    assert result.iloc[0] == -1


def test_no_day_zero_exists() -> None:
    dates = pd.Series(["2013-12-31", "2014-01-01", "2014-01-02", "2014-01-03"])
    reference = pd.Series(["2014-01-02"] * 4)

    assert 0 not in set(study_day(dates, reference))


def test_study_day_handles_date_times_and_plain_dates() -> None:
    """Collection timestamps mix both shapes."""
    result = study_day(
        pd.Series(["2014-01-05T09:30", "2014-01-05"]),
        pd.Series(["2014-01-02", "2014-01-02"]),
    )

    assert list(result) == [4, 4]


def test_missing_date_yields_missing_day_not_a_wrong_one() -> None:
    result = study_day(pd.Series([None, ""]), pd.Series(["2014-01-02", "2014-01-02"]))

    assert result.isna().all()


def test_sequence_numbers_start_at_one_within_each_subject() -> None:
    frame = pd.DataFrame({"USUBJID": ["b", "a", "a", "b"], "VISITNUM": [2, 2, 1, 1]})

    result = sequence_number(frame, "USUBJID", ["VISITNUM"])

    assert dict(zip(frame["USUBJID"] + frame["VISITNUM"].astype(str), result, strict=True)) == {
        "a1": 1.0,
        "a2": 2.0,
        "b1": 1.0,
        "b2": 2.0,
    }


def test_sequence_is_independent_of_incoming_row_order() -> None:
    frame = pd.DataFrame({"USUBJID": ["a"] * 3, "VISITNUM": [3, 1, 2]})

    shuffled = frame.iloc[[1, 2, 0]]

    assert sorted(sequence_number(frame, "USUBJID", ["VISITNUM"])) == [1.0, 2.0, 3.0]
    assert sorted(sequence_number(shuffled, "USUBJID", ["VISITNUM"])) == [1.0, 2.0, 3.0]


def test_baseline_flag_marks_only_the_nominated_visit() -> None:
    visits = pd.Series(["SCREENING 1", "BASELINE", "WEEK 2"])

    assert list(baseline_flag(visits)) == ["", "Y", ""]


def test_baseline_visit_differs_by_domain() -> None:
    """Laboratory baseline is SCREENING 1, not BASELINE."""
    visits = pd.Series(["SCREENING 1", "BASELINE"])

    assert list(baseline_flag(visits, "SCREENING 1")) == ["Y", ""]
