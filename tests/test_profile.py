"""Dataset profiling."""

from __future__ import annotations

import pandas as pd

from p2d.ingest.profile import profile_frame, profiles_to_frame


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "USUBJID": ["s1", "s1", "s2", "s3"],
            "LBTESTCD": ["CREAT", "ALT", "CREAT", "CREAT"],
            "LBSTRESN": [1.0, 2.0, None, 4.0],
            "COMMENT": ["", "", "note", ""],
        }
    )


def test_counts_rows_and_distinct_subjects() -> None:
    profile = profile_frame(_frame(), "LB")

    assert profile.rows == 4
    assert profile.subjects == 3
    assert profile.n_columns == 4


def test_numeric_null_rate_counts_nan() -> None:
    profile = profile_frame(_frame(), "LB")
    column = next(c for c in profile.columns if c.name == "LBSTRESN")

    assert column.null_rate == 0.25


def test_blank_strings_count_as_missing() -> None:
    """A collected-but-blank field is as unusable as an absent one."""
    profile = profile_frame(_frame(), "LB")
    column = next(c for c in profile.columns if c.name == "COMMENT")

    assert column.null_rate == 0.75


def test_distinct_counts_ignore_missing() -> None:
    profile = profile_frame(_frame(), "LB")
    column = next(c for c in profile.columns if c.name == "LBTESTCD")

    assert column.n_distinct == 2


def test_subjects_is_zero_without_a_subject_column() -> None:
    """Trial-design domains such as TI have no USUBJID."""
    profile = profile_frame(pd.DataFrame({"IETESTCD": ["INCL01"]}), "TI")

    assert profile.subjects == 0


def test_empty_frame_does_not_divide_by_zero() -> None:
    profile = profile_frame(pd.DataFrame({"USUBJID": pd.Series(dtype="str")}), "DM")

    assert profile.rows == 0
    assert profile.columns[0].null_rate == 0.0


def test_flattened_table_has_one_row_per_variable() -> None:
    profiles = [profile_frame(_frame(), "LB"), profile_frame(_frame(), "VS")]

    flat = profiles_to_frame(profiles)

    assert len(flat) == 8
    assert set(flat["domain"]) == {"LB", "VS"}
