"""Transposing between CRF pages and SDTM findings domains.

SDTM findings domains (VS, LB, QS) are *long*: one row per subject, visit and
test. A CRF page is *wide*: one row per subject and visit, with a column per
field on the page. That transposition is the substance of a findings mapping,
so it is implemented once and configured per domain.

A page carries more than one value per test. A laboratory page records the
result, its unit and the lab's reference range; a vitals page records the
result, its unit, where it was taken and whether it was done at all. Each of
those is pivoted into its own ``<TESTCD>__<attribute>`` column, so nothing
collected is lost in the transposition.

Two kinds of record are distinguished. A **collected** record is one a site
wrote down — including one marked NOT DONE, because "not done" is itself
collected information. A **sponsor-derived** record has only a standardised
result, such as a total score the sponsor computed; it was never on a CRF, so
it is excluded from the CRF layer and reported separately rather than silently
dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from p2d.mapping.derive import (
    STUDY_ID,
    baseline_flag,
    make_usubjid,
    sequence_number,
    study_day,
)
from p2d.mapping.units import ConversionTable, ResponseCodes, normal_range_indicator

ATTRIBUTE_SEPARATOR = "__"


@dataclass(frozen=True)
class FindingsDomain:
    """How one findings domain maps to and from its CRF page."""

    domain: str
    #: Columns identifying a single CRF page, besides subject and site.
    row_key: list[str]
    #: Columns collected once per test on the page, besides the result itself.
    test_attributes: list[str] = field(default_factory=list)
    #: Attributes whose presence means the test appeared on the page even
    #: though it has no result (a NOT DONE status, for instance).
    presence_attributes: list[str] = field(default_factory=list)
    #: Sort reproducing the sponsor's ``--SEQ``, when one exists. Where it is
    #: None the sequence reflects an internal dataset ordering that no CRF
    #: records, so the published value is carried rather than invented.
    seq_order: list[str] | None = None
    has_baseline_flag: bool = True
    #: Visit whose records carry ``--BLFL``. Differs by domain.
    baseline_visit: str = "BASELINE"
    #: Reference-range columns to convert alongside the result, as
    #: (collected, standardised) pairs.
    range_columns: list[tuple[str, str]] = field(default_factory=list)
    #: Column holding the normal-range indicator, derived from the result and
    #: the standardised range.
    range_indicator: str | None = None
    #: The (low, high) columns the indicator is computed against.
    indicator_bounds: tuple[str, str] | None = None
    #: Published variables a CRF cannot determine, with the reason. These are
    #: excluded from round-trip comparison and listed in the mapping spec
    #: rather than approximated.
    not_reproducible: dict[str, str] = field(default_factory=dict)
    #: "units" converts the result between units; "responses" maps a
    #: questionnaire answer to its score through the instrument's codelist.
    standardisation: str = "units"

    @property
    def prefix(self) -> str:
        return self.domain

    @property
    def testcd(self) -> str:
        return f"{self.prefix}TESTCD"

    @property
    def test(self) -> str:
        return f"{self.prefix}TEST"

    @property
    def orres(self) -> str:
        return f"{self.prefix}ORRES"

    @property
    def orresu(self) -> str:
        return f"{self.prefix}ORRESU"

    @property
    def seq(self) -> str:
        return f"{self.prefix}SEQ"

    @property
    def dtc(self) -> str:
        return f"{self.prefix}DTC"

    @property
    def day(self) -> str:
        return f"{self.prefix}DY"

    @property
    def blfl(self) -> str:
        return f"{self.prefix}BLFL"

    @property
    def derives_seq(self) -> bool:
        return self.seq_order is not None


@dataclass(frozen=True)
class SplitRecords:
    collected: pd.DataFrame
    sponsor_derived: pd.DataFrame


def split_collected(frame: pd.DataFrame, spec: FindingsDomain) -> SplitRecords:
    """Separate site-collected records from sponsor-derived ones."""
    present = _non_blank(frame[spec.orres])
    for attribute in spec.presence_attributes:
        if attribute in frame.columns:
            present = present | _non_blank(frame[attribute])
    return SplitRecords(collected=frame[present].copy(), sponsor_derived=frame[~present].copy())


def test_decode_map(frame: pd.DataFrame, spec: FindingsDomain) -> dict[str, str]:
    """``--TESTCD`` to ``--TEST``, the domain's own controlled terminology."""
    pairs = frame[[spec.testcd, spec.test]].drop_duplicates()
    return dict(zip(pairs[spec.testcd], pairs[spec.test], strict=True))


def _non_blank(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip() != ""


def _attribute_column(testcd: str, attribute: str) -> str:
    return f"{testcd}{ATTRIBUTE_SEPARATOR}{attribute}"


def to_crf(frame: pd.DataFrame, spec: FindingsDomain) -> pd.DataFrame:
    """Build the wide CRF page from an SDTM findings domain."""
    collected = split_collected(frame, spec).collected

    wide = collected.copy()
    wide["SITENUM"] = wide["USUBJID"].str.split("-").str[1]
    wide["SUBJID"] = wide["USUBJID"].str.split("-").str[2]
    index = ["SITENUM", "SUBJID", *spec.row_key]

    # Blank context fields are part of a page's identity, so they are held as
    # empty strings; left as NaN they would drop out of the index entirely.
    for column in index:
        if not pd.api.types.is_numeric_dtype(wide[column]):
            wide[column] = wide[column].astype("string").fillna("")

    # ``pivot`` rather than ``pivot_table``: the latter builds the cartesian
    # product of every index level, which for a page key this wide is
    # astronomically large.
    page = wide.pivot(index=index, columns=spec.testcd, values=spec.orres)
    for attribute in spec.test_attributes:
        if attribute not in wide.columns:
            continue
        pivoted = wide.pivot(index=index, columns=spec.testcd, values=attribute)
        pivoted.columns = [_attribute_column(c, attribute) for c in pivoted.columns]
        page = page.join(pivoted)

    page = page.reset_index()
    page.columns.name = None
    return page.sort_values(index).reset_index(drop=True)


def from_crf(
    page: pd.DataFrame,
    spec: FindingsDomain,
    *,
    decode: dict[str, str],
    reference_dates: pd.DataFrame,
    conversions: ConversionTable,
    response_codes: ResponseCodes | None = None,
) -> pd.DataFrame:
    """Rebuild the SDTM findings domain from its CRF page."""
    tests = [c for c in page.columns if c in decode]
    identifiers = ["SITENUM", "SUBJID", *spec.row_key]

    long = page.melt(
        id_vars=identifiers, value_vars=tests, var_name=spec.testcd, value_name=spec.orres
    )
    for attribute in spec.test_attributes:
        columns = [_attribute_column(t, attribute) for t in tests]
        if not all(c in page.columns for c in columns):
            continue
        melted = page.melt(id_vars=identifiers, value_vars=columns, value_name=attribute)
        long[attribute] = melted[attribute].to_numpy()

    # The pivot created a cell for every test on every page; a cell with no
    # result and no status is a test that page did not collect.
    present = _non_blank(long[spec.orres])
    for attribute in spec.presence_attributes:
        if attribute in long.columns:
            present = present | _non_blank(long[attribute])
    long = long[present].copy()

    long["STUDYID"] = STUDY_ID
    long["DOMAIN"] = spec.domain
    long["USUBJID"] = make_usubjid(long["SITENUM"], long["SUBJID"])
    long[spec.test] = long[spec.testcd].map(decode)

    if spec.standardisation == "responses":
        codes = response_codes or ResponseCodes.load()
        characters, values = codes.standardise(long, spec.testcd, spec.orres)
        long[f"{spec.prefix}STRESC"] = characters
        long[f"{spec.prefix}STRESN"] = values
        long[f"{spec.prefix}STRESU"] = long[spec.orresu].astype("string").fillna("")
    else:
        values, units = conversions.standardise(
            long, spec.domain, spec.testcd, spec.orres, spec.orresu
        )
        long[f"{spec.prefix}STRESN"] = values
        long[f"{spec.prefix}STRESU"] = units
        long[f"{spec.prefix}STRESC"] = format_character_result(values, long[spec.orres])

    # Reference ranges are collected in the lab's own units and standardised
    # with the same rule as the result, so the comparison stays like for like.
    for collected_col, standard_col in spec.range_columns:
        if collected_col not in long.columns:
            continue
        standard, _ = conversions.standardise(
            long, spec.domain, spec.testcd, collected_col, spec.orresu
        )
        long[standard_col] = standard

    if spec.range_indicator and spec.indicator_bounds:
        low_col, high_col = spec.indicator_bounds
        long[spec.range_indicator] = normal_range_indicator(
            long[f"{spec.prefix}STRESN"], long[low_col], long[high_col]
        )

    long = long.merge(reference_dates, on="USUBJID", how="left")
    long[spec.day] = study_day(long[spec.dtc], long["RFSTDTC"])
    if spec.has_baseline_flag:
        long[spec.blfl] = baseline_flag(long["VISIT"], spec.baseline_visit)

    if spec.derives_seq:
        long = long.sort_values(["USUBJID", *spec.seq_order], kind="stable")
        long[spec.seq] = sequence_number(long, "USUBJID", spec.seq_order)

    return long.drop(columns=["SITENUM", "SUBJID", "RFSTDTC"]).reset_index(drop=True)


def format_character_result(values: pd.Series, collected: pd.Series) -> pd.Series:
    """``--STRESC``: the standardised result in character form.

    Numeric results are rendered without trailing zeros. A result that is not
    numeric at all — a questionnaire response such as "NEVER" — has no numeric
    standardisation, so the collected text carries through unchanged.
    """

    def render(value, original) -> str:
        if pd.isna(value):
            return "" if pd.isna(original) else str(original).strip()
        text = f"{float(value):.10f}".rstrip("0").rstrip(".")
        return text or "0"

    return pd.Series(
        [render(v, o) for v, o in zip(values, collected, strict=True)],
        index=values.index,
        dtype="object",
    )
