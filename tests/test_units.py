"""Unit conversion, response codes and reference ranges."""

from __future__ import annotations

import pandas as pd

from p2d.mapping.units import (
    Conversion,
    ConversionTable,
    ResponseCodes,
    normal_range_indicator,
    round_half_up,
)


def test_rounds_half_away_from_zero_like_sas() -> None:
    """Banker's rounding would send 98.885 to 98.88 and break reconstruction."""
    values = pd.Series([98.885, 0.125, 2.5])

    assert list(round_half_up(values, 2)) == [98.89, 0.13, 2.5]


def test_rounding_preserves_missing() -> None:
    assert pd.isna(round_half_up(pd.Series([None], dtype="float64"), 2).iloc[0])


def test_multiplicative_conversion() -> None:
    rule = Conversion("LB", "ALB", "g/dL", "g/L", 10.0, 0.0, 0)

    assert rule.apply(pd.Series([3.8])).iloc[0] == 38


def test_affine_conversion_handles_fahrenheit() -> None:
    rule = Conversion("VS", "TEMP", "F", "C", 5 / 9, -32 * 5 / 9, 2)

    assert rule.apply(pd.Series([98.6])).iloc[0] == 37.0


def test_table_leaves_unknown_tests_untouched() -> None:
    """A test already reported in standard units needs no rule."""
    table = ConversionTable([Conversion("VS", "TEMP", "F", "C", 5 / 9, -32 * 5 / 9, 2)])
    frame = pd.DataFrame({"VSTESTCD": ["PULSE"], "VSORRES": [72.0], "VSORRESU": ["BEATS/MIN"]})

    values, units = table.standardise(frame, "VS", "VSTESTCD", "VSORRES", "VSORRESU")

    assert values.iloc[0] == 72.0
    assert units.iloc[0] == "BEATS/MIN"


def test_table_converts_a_known_test() -> None:
    table = ConversionTable([Conversion("VS", "HEIGHT", "IN", "cm", 2.54, 0.0, 2)])
    frame = pd.DataFrame({"VSTESTCD": ["HEIGHT"], "VSORRES": [58.0], "VSORRESU": ["IN"]})

    values, units = table.standardise(frame, "VS", "VSTESTCD", "VSORRES", "VSORRESU")

    assert values.iloc[0] == 147.32
    assert units.iloc[0] == "cm"


def test_response_codes_map_text_to_score() -> None:
    codes = ResponseCodes({("ACITM01", "NO CHANGE"): ("4", 4.0)})
    frame = pd.DataFrame({"QSTESTCD": ["ACITM01"], "QSORRES": ["NO CHANGE"]})

    characters, numbers = codes.standardise(frame, "QSTESTCD", "QSORRES")

    assert characters.iloc[0] == "4"
    assert numbers.iloc[0] == 4.0


def test_response_codes_keep_scores_textual() -> None:
    """A score of 3 must stay "3", not become "3.0"."""
    codes = ResponseCodes.load()
    frame = pd.DataFrame({"QSTESTCD": ["ACITM01"], "QSORRES": ["3"]})

    characters, _ = codes.standardise(frame, "QSTESTCD", "QSORRES")

    assert characters.iloc[0] == "3"


def test_range_indicator_classifies_against_bounds() -> None:
    values = pd.Series([5.0, 0.5, 20.0])
    low = pd.Series([1.0, 1.0, 1.0])
    high = pd.Series([10.0, 10.0, 10.0])

    assert list(normal_range_indicator(values, low, high)) == ["NORMAL", "LOW", "HIGH"]


def test_range_indicator_is_blank_without_a_range() -> None:
    """No reference range means no judgement, not a default of normal."""
    result = normal_range_indicator(pd.Series([5.0]), pd.Series([None]), pd.Series([None]))

    assert result.iloc[0] == ""
