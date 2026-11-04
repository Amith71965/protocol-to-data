"""Derivations shared across SDTM domains.

These are the variables a CRF does not carry: identifiers assembled from
collected parts, study days computed against a reference date, sequence numbers
and flags. Keeping them here means the mapping spec can point at one
implementation per rule, and each rule gets its own test.
"""

from __future__ import annotations

import pandas as pd

#: The study identifier is constant for this trial.
STUDY_ID = "CDISCPILOT01"

#: USUBJID is assembled as ``<prefix>-<site>-<subject>``. The prefix is a
#: study-level constant in this trial, verified against all 306 DM records.
USUBJID_PREFIX = "01"

#: Visit at which a record is flagged as baseline in this study.
BASELINE_VISIT = "BASELINE"


def make_usubjid(site: pd.Series, subject: pd.Series, prefix: str = USUBJID_PREFIX) -> pd.Series:
    """Assemble the unique subject identifier from its collected parts."""
    return prefix + "-" + site.astype("string") + "-" + subject.astype("string")


def study_day(date: pd.Series, reference: pd.Series) -> pd.Series:
    """CDISC study day, which has no day zero.

    The day of the reference date is day 1; the day before it is day -1. Both
    inputs are ISO 8601 date strings. Rows where either date is missing or
    partial yield a missing study day rather than a wrong one.
    """
    # Collection timestamps mix plain dates with date-times, so the format is
    # stated explicitly; letting pandas infer one format silently fails on the
    # minority shape.
    collected = pd.to_datetime(date, errors="coerce", format="ISO8601")
    start = pd.to_datetime(reference, errors="coerce", format="ISO8601")
    delta = (collected - start).dt.days
    return delta.where(delta < 0, delta + 1)


def sequence_number(frame: pd.DataFrame, by: str, order: list[str]) -> pd.Series:
    """``--SEQ``: a 1-based counter within each subject.

    Sorted by ``order`` so the numbering is reproducible rather than dependent
    on the incoming row order.
    """
    ordering = frame.sort_values([by, *order], kind="stable")
    numbers = ordering.groupby(by, sort=False).cumcount() + 1
    return numbers.reindex(frame.index).astype("float64")


def baseline_flag(visit: pd.Series, baseline_visit: str = BASELINE_VISIT) -> pd.Series:
    """``--BLFL``: ``Y`` on baseline-visit records, blank elsewhere.

    The sponsor flagged exactly the records collected at one nominated visit,
    which differs by domain: vital signs use BASELINE, laboratory results use
    SCREENING 1. Deriving the flag instead from "last result on or before first
    dose" reproduces neither, so that interpretation is deliberately not used.
    """
    return pd.Series(
        [("Y" if v == baseline_visit else "") for v in visit],
        index=visit.index,
        dtype="object",
    )
