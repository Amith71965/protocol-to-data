"""XPORT decoding corrections."""

from __future__ import annotations

import numpy as np
import pandas as pd

from p2d.ingest.reader import (
    DENORMAL_THRESHOLD,
    normalise_denormal_zeros,
    strip_character_columns,
)

#: The exact value these files decode a stored zero to.
DECODED_ZERO = 5.397605e-79


def test_decoded_zero_becomes_exact_zero() -> None:
    frame = pd.DataFrame({"score": [DECODED_ZERO, 1.0, 2.0]})

    result = normalise_denormal_zeros(frame)

    assert result["score"].iloc[0] == 0.0


def test_decoded_zero_would_otherwise_compare_as_positive() -> None:
    """This is the bug the correction exists to prevent."""
    frame = pd.DataFrame({"score": [DECODED_ZERO]})

    assert (frame["score"] > 0).all(), "precondition: the raw value is positive"
    assert not (normalise_denormal_zeros(frame)["score"] > 0).any()


def test_legitimate_small_values_are_preserved() -> None:
    """Real measurements are many orders of magnitude above the threshold."""
    frame = pd.DataFrame({"result": [1e-5, 0.001, 1e-30]})

    result = normalise_denormal_zeros(frame)

    pd.testing.assert_series_equal(result["result"], frame["result"])


def test_threshold_sits_between_the_two_cases() -> None:
    assert DECODED_ZERO < DENORMAL_THRESHOLD < 1e-30


def test_negative_denormals_are_snapped_too() -> None:
    frame = pd.DataFrame({"x": [-DECODED_ZERO]})

    assert normalise_denormal_zeros(frame)["x"].iloc[0] == 0.0


def test_nan_is_left_alone() -> None:
    frame = pd.DataFrame({"x": [np.nan, DECODED_ZERO]})

    result = normalise_denormal_zeros(frame)

    assert pd.isna(result["x"].iloc[0])
    assert result["x"].iloc[1] == 0.0


def test_non_float_columns_are_untouched() -> None:
    frame = pd.DataFrame({"n": [0, 1], "s": ["a", "b"]})

    pd.testing.assert_frame_equal(normalise_denormal_zeros(frame), frame)


def test_input_frame_is_not_mutated() -> None:
    frame = pd.DataFrame({"score": [DECODED_ZERO]})

    normalise_denormal_zeros(frame)

    assert frame["score"].iloc[0] == DECODED_ZERO


def test_character_padding_is_stripped() -> None:
    frame = pd.DataFrame({"USUBJID": ["01-701-1015   "], "SEX": ["F "]})

    result = strip_character_columns(frame)

    assert result["USUBJID"].iloc[0] == "01-701-1015"
    assert result["SEX"].iloc[0] == "F"


def test_stripping_keeps_blanks_as_empty_not_null() -> None:
    """ "Collected but blank" must stay distinguishable from "not collected"."""
    frame = pd.DataFrame({"COMMENT": ["   ", None]})

    result = strip_character_columns(frame)

    assert result["COMMENT"].iloc[0] == ""
    assert pd.isna(result["COMMENT"].iloc[1])
