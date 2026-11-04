"""Derived questionnaire totals."""

from __future__ import annotations

import pandas as pd
import pytest

from p2d.mapping.scores import MMSE, IncompleteInstrumentError, derive_total


def _items(scores: list[float], subject: str = "01-701-1015") -> pd.DataFrame:
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


def test_total_is_the_sum_of_items() -> None:
    result = derive_total(_items([5, 5, 3, 5, 3, 9]), MMSE)

    assert result["total"].iloc[0] == 30.0
    assert result["complete"].iloc[0]


def test_a_zero_scored_item_counts_as_zero() -> None:
    """The denormal-zero correction matters here: a zero must not be dropped."""
    result = derive_total(_items([0, 5, 3, 5, 3, 9]), MMSE)

    assert result["total"].iloc[0] == 25.0
    assert result["n_items"].iloc[0] == 6


def test_incomplete_instrument_is_not_scored() -> None:
    """Summing 5 of 6 items would understate the score and flip eligibility."""
    with pytest.raises(IncompleteInstrumentError, match="fewer than 6"):
        derive_total(_items([5, 5, 3, 5, 3]), MMSE)


def test_incomplete_total_is_missing_rather_than_wrong() -> None:
    result = derive_total(_items([5, 5, 3, 5, 3]), MMSE, require_complete=False)

    assert pd.isna(result["total"].iloc[0])
    assert not result["complete"].iloc[0]


def test_one_row_per_subject_and_visit() -> None:
    frame = pd.concat([_items([5, 5, 3, 5, 3, 9], s) for s in ("s1", "s2")])

    result = derive_total(frame, MMSE)

    assert len(result) == 2
    assert set(result["USUBJID"]) == {"s1", "s2"}


def test_other_instruments_are_ignored() -> None:
    frame = _items([5, 5, 3, 5, 3, 9])
    other = frame.copy()
    other["QSCAT"] = "NEUROPSYCHIATRIC INVENTORY - REVISED (NPI-X)"

    result = derive_total(pd.concat([frame, other]), MMSE)

    assert len(result) == 1


def test_absent_instrument_returns_empty_frame() -> None:
    frame = _items([5, 5, 3, 5, 3, 9])
    frame["QSCAT"] = "SOMETHING ELSE"

    assert derive_total(frame, MMSE).empty
