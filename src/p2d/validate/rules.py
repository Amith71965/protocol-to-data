"""Conformance rules.

Each rule takes a dataset and returns the issues it found. They are written in
the spirit of the Pinnacle 21 / CDISC CORE checks a submission would be run
through: structural requirements, controlled terminology, date formats, key
uniqueness and cross-domain consistency.

Every rule is independent and individually tested, so a finding can always be
traced to one named check rather than to "the validator".
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from p2d.mapping.derive import study_day
from p2d.validate.issues import Issue, Severity
from p2d.validate.terminology import Terminology

#: SDTM identifier variables every observation domain must carry.
REQUIRED_IDENTIFIERS = ["STUDYID", "DOMAIN", "USUBJID"]

#: ISO 8601 date or date-time, permitting the partial forms SDTM allows.
ISO_8601 = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?)?)?)?$")

#: Largest difference tolerated between a published and recomputed study day.
STUDY_DAY_TOLERANCE = 0


@dataclass(frozen=True)
class Dataset:
    """One domain, with what a rule needs to judge it."""

    domain: str
    frame: pd.DataFrame
    #: DM, for cross-domain checks. None when the dataset *is* DM.
    demographics: pd.DataFrame | None = None
    terminology: Terminology | None = None

    @property
    def seq_variable(self) -> str:
        return f"{self.domain}SEQ"

    @property
    def date_variable(self) -> str:
        return f"{self.domain}DTC"

    @property
    def day_variable(self) -> str:
        return f"{self.domain}DY"


Rule = Callable[[Dataset], list[Issue]]


def _record_key(frame: pd.DataFrame, index, seq_variable: str) -> str:
    if seq_variable in frame.columns:
        value = frame.at[index, seq_variable]
        return f"{seq_variable}={value}"
    return f"row={index}"


def required_variables(dataset: Dataset) -> list[Issue]:
    """SD0001 — required identifier variables are present."""
    expected = [*REQUIRED_IDENTIFIERS]
    if dataset.domain != "DM":
        expected.append(dataset.seq_variable)

    return [
        Issue(
            rule_id="SD0001",
            severity=Severity.ERROR,
            domain=dataset.domain,
            variable=variable,
            message=f"Required variable {variable} is missing from {dataset.domain}.",
        )
        for variable in expected
        if variable not in dataset.frame.columns
    ]


def domain_value_matches(dataset: Dataset) -> list[Issue]:
    """SD0002 — DOMAIN holds the domain's own code on every record."""
    frame = dataset.frame
    if "DOMAIN" not in frame.columns:
        return []

    wrong = frame[frame["DOMAIN"].astype("string").fillna("") != dataset.domain]
    return [
        Issue(
            rule_id="SD0002",
            severity=Severity.ERROR,
            domain=dataset.domain,
            variable="DOMAIN",
            usubjid=str(frame.at[i, "USUBJID"]) if "USUBJID" in frame.columns else "",
            record_key=_record_key(frame, i, dataset.seq_variable),
            observed=str(frame.at[i, "DOMAIN"]),
            message=f"DOMAIN should be {dataset.domain}.",
        )
        for i in wrong.index
    ]


def key_uniqueness(dataset: Dataset) -> list[Issue]:
    """SD0003 — STUDYID + USUBJID + --SEQ identifies exactly one record."""
    frame = dataset.frame
    key = [c for c in ["STUDYID", "USUBJID", dataset.seq_variable] if c in frame.columns]
    if len(key) < 3:
        return []

    duplicated = frame[frame.duplicated(subset=key, keep=False)]
    return [
        Issue(
            rule_id="SD0003",
            severity=Severity.ERROR,
            domain=dataset.domain,
            variable=dataset.seq_variable,
            usubjid=str(frame.at[i, "USUBJID"]),
            record_key=_record_key(frame, i, dataset.seq_variable),
            observed=str(frame.at[i, dataset.seq_variable]),
            message="Duplicate STUDYID + USUBJID + sequence number.",
        )
        for i in duplicated.index
    ]


def sequence_is_a_positive_integer(dataset: Dataset) -> list[Issue]:
    """SD0004 — --SEQ is a whole number of at least one."""
    frame = dataset.frame
    if dataset.seq_variable not in frame.columns:
        return []

    values = pd.to_numeric(frame[dataset.seq_variable], errors="coerce")
    invalid = frame[values.isna() | (values < 1) | (values % 1 != 0)]
    return [
        Issue(
            rule_id="SD0004",
            severity=Severity.ERROR,
            domain=dataset.domain,
            variable=dataset.seq_variable,
            usubjid=str(frame.at[i, "USUBJID"]) if "USUBJID" in frame.columns else "",
            record_key=_record_key(frame, i, dataset.seq_variable),
            observed=str(frame.at[i, dataset.seq_variable]),
            message="Sequence number must be a positive whole number.",
        )
        for i in invalid.index
    ]


def iso_8601_dates(dataset: Dataset) -> list[Issue]:
    """SD0005 — date variables use ISO 8601."""
    frame = dataset.frame
    date_columns = [c for c in frame.columns if c.endswith("DTC")]

    issues = []
    for column in date_columns:
        text = frame[column].astype("string").fillna("").str.strip()
        populated = text != ""
        malformed = populated & ~text.str.match(ISO_8601)
        issues += [
            Issue(
                rule_id="SD0005",
                severity=Severity.ERROR,
                domain=dataset.domain,
                variable=column,
                usubjid=str(frame.at[i, "USUBJID"]) if "USUBJID" in frame.columns else "",
                record_key=_record_key(frame, i, dataset.seq_variable),
                observed=str(frame.at[i, column]),
                message=f"{column} is not an ISO 8601 date or date-time.",
            )
            for i in frame.index[malformed]
        ]
    return issues


def controlled_terminology(dataset: Dataset) -> list[Issue]:
    """SD0006 — values come from the codelist that governs the variable."""
    if dataset.terminology is None:
        return []

    frame = dataset.frame
    issues = []
    for column in frame.columns:
        permitted = dataset.terminology.values_for(column)
        if not permitted:
            continue
        text = frame[column].astype("string").fillna("").str.strip()
        # A blank is an absent value, which this rule does not judge.
        offending = (text != "") & ~text.isin(permitted)
        issues += [
            Issue(
                rule_id="SD0006",
                severity=Severity.WARNING,
                domain=dataset.domain,
                variable=column,
                usubjid=str(frame.at[i, "USUBJID"]) if "USUBJID" in frame.columns else "",
                record_key=_record_key(frame, i, dataset.seq_variable),
                observed=str(frame.at[i, column]),
                message=f"{column} value is not in its CDISC codelist.",
            )
            for i in frame.index[offending]
        ]
    return issues


def subject_exists_in_demographics(dataset: Dataset) -> list[Issue]:
    """SD0007 — every subject in a domain is registered in DM."""
    frame = dataset.frame
    if dataset.demographics is None or "USUBJID" not in frame.columns:
        return []

    known = set(dataset.demographics["USUBJID"])
    unknown = frame[~frame["USUBJID"].isin(known)]
    return [
        Issue(
            rule_id="SD0007",
            severity=Severity.ERROR,
            domain=dataset.domain,
            variable="USUBJID",
            usubjid=str(frame.at[i, "USUBJID"]),
            record_key=_record_key(frame, i, dataset.seq_variable),
            observed=str(frame.at[i, "USUBJID"]),
            message="Subject does not appear in DM.",
        )
        for i in unknown.index
    ]


def study_day_consistency(dataset: Dataset) -> list[Issue]:
    """SD0008 — --DY agrees with --DTC and the subject's reference start date."""
    frame = dataset.frame
    if dataset.demographics is None:
        return []
    if dataset.day_variable not in frame.columns or dataset.date_variable not in frame.columns:
        return []

    merged = frame.merge(dataset.demographics[["USUBJID", "RFSTDTC"]], on="USUBJID", how="left")
    expected = study_day(merged[dataset.date_variable], merged["RFSTDTC"])
    published = pd.to_numeric(merged[dataset.day_variable], errors="coerce")

    comparable = expected.notna() & published.notna()
    wrong = comparable & ((expected - published).abs() > STUDY_DAY_TOLERANCE)

    return [
        Issue(
            rule_id="SD0008",
            severity=Severity.ERROR,
            domain=dataset.domain,
            variable=dataset.day_variable,
            usubjid=str(merged.at[i, "USUBJID"]),
            record_key=_record_key(frame, frame.index[i], dataset.seq_variable),
            observed=f"{published.iloc[i]:.0f} (expected {expected.iloc[i]:.0f})",
            message="Study day disagrees with the collection date and reference start date.",
        )
        for i in merged.index[wrong]
    ]


def standard_result_present(dataset: Dataset) -> list[Issue]:
    """SD0009 — a numeric original result has a standardised result."""
    frame = dataset.frame
    original, standard = f"{dataset.domain}ORRES", f"{dataset.domain}STRESN"
    if original not in frame.columns or standard not in frame.columns:
        return []

    numeric_original = pd.to_numeric(frame[original], errors="coerce")
    missing = frame[numeric_original.notna() & frame[standard].isna()]
    return [
        Issue(
            rule_id="SD0009",
            severity=Severity.WARNING,
            domain=dataset.domain,
            variable=standard,
            usubjid=str(frame.at[i, "USUBJID"]),
            record_key=_record_key(frame, i, dataset.seq_variable),
            observed=str(frame.at[i, original]),
            message="Numeric original result has no standardised result.",
        )
        for i in missing.index
    ]


#: Every rule, with the one-line description the documentation is built from.
ALL_RULES: dict[str, tuple[Rule, str]] = {
    "SD0001": (required_variables, "Required identifier variables are present."),
    "SD0002": (domain_value_matches, "DOMAIN holds the domain's own code."),
    "SD0003": (key_uniqueness, "STUDYID + USUBJID + --SEQ is unique."),
    "SD0004": (sequence_is_a_positive_integer, "--SEQ is a positive whole number."),
    "SD0005": (iso_8601_dates, "Date variables use ISO 8601."),
    "SD0006": (controlled_terminology, "Values come from their CDISC codelist."),
    "SD0007": (subject_exists_in_demographics, "Every subject is registered in DM."),
    "SD0008": (study_day_consistency, "--DY agrees with --DTC and RFSTDTC."),
    "SD0009": (standard_result_present, "A numeric result has a standardised result."),
}


def run_all(dataset: Dataset) -> list[Issue]:
    """Run every rule against one dataset."""
    issues: list[Issue] = []
    for rule, _ in ALL_RULES.values():
        issues.extend(rule(dataset))
    return issues
