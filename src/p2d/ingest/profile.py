"""Profiling the ingested datasets.

The inventory this produces is the project's evidence base: later phases cite it
when they say a criterion cannot be evaluated because a variable is absent or
largely unpopulated. Counting what is *missing* matters as much as counting what
is present.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from p2d.ingest.reader import is_textual


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    dtype: str
    null_rate: float
    n_distinct: int
    sample: str


@dataclass(frozen=True)
class DatasetProfile:
    domain: str
    rows: int
    subjects: int
    columns: list[ColumnProfile] = field(default_factory=list)

    @property
    def n_columns(self) -> int:
        return len(self.columns)


def _sample_values(series: pd.Series, limit: int = 3) -> str:
    """A few representative values, for a human reading the inventory."""
    values = series.dropna()
    if values.empty:
        return ""
    unique = pd.Series(values.unique()[:limit])
    rendered = []
    for value in unique:
        text = f"{value:g}" if isinstance(value, float) else str(value)
        rendered.append(text[:28])
    return ", ".join(r for r in rendered if r)


def profile_frame(frame: pd.DataFrame, domain: str) -> DatasetProfile:
    """Profile one dataset."""
    rows = len(frame)
    subjects = int(frame["USUBJID"].nunique()) if "USUBJID" in frame.columns else 0

    columns = []
    for name in frame.columns:
        series = frame[name]
        # An empty string is "collected but blank", which is as absent as NaN
        # for our purposes, so both count toward the null rate.
        if is_textual(series):
            missing = series.isna() | (series.astype("string").fillna("") == "")
        else:
            missing = series.isna()
        columns.append(
            ColumnProfile(
                name=str(name),
                dtype=str(series.dtype),
                null_rate=round(float(missing.mean()), 4) if rows else 0.0,
                n_distinct=int(series.nunique(dropna=True)),
                sample=_sample_values(series),
            )
        )

    return DatasetProfile(domain=domain, rows=rows, subjects=subjects, columns=columns)


def profiles_to_frame(profiles: list[DatasetProfile]) -> pd.DataFrame:
    """Flatten profiles into one tidy table, for CSV or the dashboard."""
    records = [
        {
            "domain": profile.domain,
            "rows": profile.rows,
            "subjects": profile.subjects,
            "variable": column.name,
            "dtype": column.dtype,
            "null_rate": column.null_rate,
            "n_distinct": column.n_distinct,
            "sample": column.sample,
        }
        for profile in profiles
        for column in profile.columns
    ]
    return pd.DataFrame.from_records(
        records,
        columns=[
            "domain",
            "rows",
            "subjects",
            "variable",
            "dtype",
            "null_rate",
            "n_distinct",
            "sample",
        ],
    )
