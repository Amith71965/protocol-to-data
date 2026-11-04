"""Verifying a mapping by round-tripping it.

The mapping spec claims that a set of SDTM variables can be rebuilt from the
CRF layer. That claim is checked rather than asserted: the SDTM domain is
transposed to its CRF page and mapped back, and the reconstruction is compared
against the published data variable by variable.

Numeric comparison uses a tolerance. Published results are decimal strings
decoded from IBM hexadecimal floats, so two values that display identically can
differ in their last bits; an exact equality test reports those as differences
when nothing is actually wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

#: Half of the smallest published decimal place, which is the largest a
#: correct reconstruction can differ by.
NUMERIC_TOLERANCE = 1e-6


@dataclass(frozen=True)
class VariableResult:
    variable: str
    mismatches: int
    total: int
    examples: list[tuple[object, object]] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        return 1.0 if not self.total else 1.0 - self.mismatches / self.total


@dataclass(frozen=True)
class RoundTripReport:
    domain: str
    rows_original: int
    rows_rebuilt: int
    results: list[VariableResult]
    not_rebuilt: list[str]

    @property
    def exact(self) -> bool:
        return (
            self.rows_original == self.rows_rebuilt
            and not self.not_rebuilt
            and all(r.mismatches == 0 for r in self.results)
        )

    @property
    def mismatched(self) -> list[VariableResult]:
        return [r for r in self.results if r.mismatches]

    def summary(self) -> str:
        if self.exact:
            return (
                f"{self.domain}: {self.rows_rebuilt:,} records rebuilt, "
                f"{len(self.results)} variables, exact"
            )
        parts = [f"{self.domain}: {self.rows_rebuilt:,}/{self.rows_original:,} records"]
        if self.not_rebuilt:
            parts.append(f"not rebuilt: {', '.join(self.not_rebuilt)}")
        for result in self.mismatched:
            parts.append(f"{result.variable} {result.mismatches}/{result.total}")
        return "; ".join(parts)


def _values_differ(left: pd.Series, right: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        both_missing = left.isna() & right.isna()
        close = (left - right).abs() <= NUMERIC_TOLERANCE
        return ~(close.fillna(False) | both_missing)
    as_text = lambda s: s.astype("string").fillna("").str.strip()  # noqa: E731
    return as_text(left) != as_text(right)


def compare(
    original: pd.DataFrame,
    rebuilt: pd.DataFrame,
    key: list[str],
    domain: str,
    *,
    ignore: list[str] | None = None,
) -> RoundTripReport:
    """Compare a reconstruction against the published data."""
    ignore = ignore or []
    left = original.sort_values(key).reset_index(drop=True)
    right = rebuilt.sort_values(key).reset_index(drop=True)

    shared = [c for c in left.columns if c in right.columns and c not in ignore]
    not_rebuilt = [c for c in left.columns if c not in right.columns and c not in ignore]

    results = []
    if len(left) == len(right):
        for column in shared:
            differs = _values_differ(left[column], right[column])
            examples = [
                (left[column].iloc[i], right[column].iloc[i]) for i in differs[differs].index[:3]
            ]
            results.append(VariableResult(column, int(differs.sum()), len(left), examples))

    return RoundTripReport(
        domain=domain,
        rows_original=len(left),
        rows_rebuilt=len(right),
        results=results,
        not_rebuilt=not_rebuilt,
    )
