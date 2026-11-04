"""Converting collected results to standard units.

A CRF records what the site measured, in the unit the site used — pounds,
Fahrenheit, mg/dL. SDTM additionally carries a standardised result, so the
mapping has to convert. The conversions are data, not code: they live in
``docs/unit_conversions.csv`` as one affine rule per domain, test and unit pair,
so adding a test does not mean editing a transformation.

Every rule is ``standard = collected * factor + offset``, which covers both the
multiplicative cases (mg/dL to umol/L) and the affine one (Fahrenheit to
Celsius).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

CONVERSIONS_PATH = Path(__file__).resolve().parents[3] / "docs" / "unit_conversions.csv"
RESPONSE_CODES_PATH = Path(__file__).resolve().parents[3] / "docs" / "qs_response_codes.csv"

#: Published results are rounded, so a reconstructed value is compared within
#: this tolerance rather than bit-for-bit. Observed residuals are an order of
#: magnitude below it.
ROUNDING_TOLERANCE = 0.01


def round_half_up(values: pd.Series, decimals: int) -> pd.Series:
    """Round half away from zero, the way SAS does.

    ``Series.round`` uses banker's rounding, which sends exact halves to the
    nearest even digit. The published standardised results were produced by SAS,
    so 98.885 became 98.89 rather than 98.88. Matching that rule removes the
    only systematic disagreement in the reconstruction.
    """
    quantum = Decimal(1).scaleb(-decimals)

    def _round(value: float) -> float:
        if pd.isna(value):
            return value
        return float(Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP))

    return values.map(_round)


@dataclass(frozen=True)
class Conversion:
    domain: str
    testcd: str
    from_unit: str
    to_unit: str
    factor: float
    offset: float
    decimals: int

    def apply(self, values: pd.Series) -> pd.Series:
        return round_half_up(values * self.factor + self.offset, self.decimals)


class ConversionTable:
    """Lookup of conversions by domain, test and collected unit."""

    def __init__(self, conversions: list[Conversion]):
        self._by_key = {(c.domain, c.testcd, c.from_unit): c for c in conversions}

    @classmethod
    def load(cls, path: str | Path = CONVERSIONS_PATH) -> ConversionTable:
        frame = pd.read_csv(path, keep_default_na=False)
        return cls(
            [
                Conversion(
                    domain=row.domain,
                    testcd=row.testcd,
                    from_unit=str(row.from_unit),
                    to_unit=str(row.to_unit),
                    factor=float(row.factor),
                    offset=float(row.offset),
                    decimals=int(row.decimals),
                )
                for row in frame.itertuples()
            ]
        )

    def get(self, domain: str, testcd: str, from_unit: str) -> Conversion | None:
        return self._by_key.get((domain, testcd, from_unit or ""))

    def __len__(self) -> int:
        return len(self._by_key)

    def standardise(
        self,
        frame: pd.DataFrame,
        domain: str,
        testcd_col: str,
        result_col: str,
        unit_col: str,
    ) -> tuple[pd.Series, pd.Series]:
        """Return standardised numeric results and their units.

        Rows with no matching rule keep their collected value and unit, which is
        the correct behaviour for tests that are already reported in standard
        units.
        """
        numeric = pd.to_numeric(frame[result_col], errors="coerce")
        out_values = numeric.copy()
        out_units = frame[unit_col].astype("string").fillna("")

        for (testcd, unit), group in frame.groupby([testcd_col, unit_col], dropna=False):
            rule = self.get(domain, str(testcd), "" if pd.isna(unit) else str(unit))
            if rule is None:
                continue
            out_values.loc[group.index] = rule.apply(numeric.loc[group.index])
            out_units.loc[group.index] = rule.to_unit

        return out_values, out_units


class ResponseCodes:
    """Questionnaire response to score, the other kind of standardisation.

    A questionnaire is not converted between units; each item's collected
    response maps to a score through the instrument's own codelist, so
    "NO CHANGE" becomes 4. The codelist lives in
    ``docs/qs_response_codes.csv`` and is deterministic: every
    (item, response) pair has exactly one score.
    """

    def __init__(self, mapping: dict[tuple[str, str], tuple[str, float]]):
        self._mapping = mapping

    @classmethod
    def load(cls, path: str | Path | None = None) -> ResponseCodes:
        source = Path(path) if path else RESPONSE_CODES_PATH
        # Scores are codes, not numbers: read as text so "3" stays "3".
        frame = pd.read_csv(source, keep_default_na=False, dtype=str)
        return cls(
            {
                (str(row.QSTESTCD), str(row.QSORRES)): (
                    str(row.QSSTRESC),
                    float(row.QSSTRESN) if str(row.QSSTRESN).strip() else float("nan"),
                )
                for row in frame.itertuples()
            }
        )

    def __len__(self) -> int:
        return len(self._mapping)

    def standardise(
        self, frame: pd.DataFrame, testcd_col: str, result_col: str
    ) -> tuple[pd.Series, pd.Series]:
        """Return standardised character and numeric results."""
        characters, numbers = [], []
        for testcd, response in zip(frame[testcd_col], frame[result_col], strict=True):
            key = (str(testcd), "" if pd.isna(response) else str(response).strip())
            code = self._mapping.get(key)
            if code is None:
                characters.append(key[1])
                numbers.append(pd.to_numeric(pd.Series([key[1]]), errors="coerce").iloc[0])
            else:
                characters.append(code[0])
                numbers.append(code[1])
        return (
            pd.Series(characters, index=frame.index, dtype="object"),
            pd.Series(numbers, index=frame.index, dtype="float64"),
        )


def normal_range_indicator(values: pd.Series, low: pd.Series, high: pd.Series) -> pd.Series:
    """``--NRIND``: where a result sits relative to its reference range.

    A result with no range, or no numeric value, yields a blank indicator
    rather than a guess.
    """
    low_numeric = pd.to_numeric(low, errors="coerce")
    high_numeric = pd.to_numeric(high, errors="coerce")

    indicator = pd.Series("", index=values.index, dtype="object")
    comparable = values.notna() & (low_numeric.notna() | high_numeric.notna())
    indicator[comparable] = "NORMAL"
    indicator[comparable & (values < low_numeric)] = "LOW"
    indicator[comparable & (values > high_numeric)] = "HIGH"
    return indicator
