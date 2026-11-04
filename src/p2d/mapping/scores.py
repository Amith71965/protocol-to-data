"""Deriving questionnaire total scores.

The published QS domain holds item-level responses only. For the Mini-Mental
State Examination and the Modified Hachinski Ischemic Score there is no total
anywhere in the data and no derived-value flag, yet the protocol's eligibility
criteria are written against totals. They therefore have to be derived.

The MMSE derivation is checkable: summing its six items reproduces the range
and mean printed in the study's own Clinical Study Report, which is independent
evidence that the derivation is right before any eligibility rule rests on it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Instrument:
    """A questionnaire whose total is derived by summing its items."""

    name: str
    category: str
    item_prefix: str
    n_items: int
    max_total: float
    #: Identifier used for the derived total record.
    total_testcd: str
    total_test: str


MMSE = Instrument(
    name="Mini-Mental State Examination",
    category="MINI-MENTAL STATE",
    item_prefix="MMITM",
    n_items=6,
    max_total=30.0,
    total_testcd="MMSETOT",
    total_test="MMSE Total Score",
)

HACHINSKI = Instrument(
    name="Modified Hachinski Ischemic Score",
    category="MODIFIED HACHINSKI ISCHEMIC SCORE",
    item_prefix="MHITM",
    n_items=13,
    max_total=12.0,
    total_testcd="MHISTOT",
    total_test="Modified Hachinski Ischemic Score Total",
)

INSTRUMENTS: dict[str, Instrument] = {MMSE.total_testcd: MMSE, HACHINSKI.total_testcd: HACHINSKI}


class IncompleteInstrument(ValueError):
    """A subject has some but not all of an instrument's items."""


def derive_total(
    qs: pd.DataFrame,
    instrument: Instrument,
    *,
    require_complete: bool = True,
) -> pd.DataFrame:
    """Sum an instrument's items into one total per subject and visit.

    A partially completed instrument is not summed: a missing item would make
    the total look lower than it is, which for MMSE would turn an ineligible
    subject into an eligible one. Such cases are reported as incomplete rather
    than scored.

    Returns:
        One row per subject and visit, with the derived total, the number of
        items found, and whether the instrument was complete.
    """
    items = qs[qs["QSCAT"] == instrument.category].copy()
    if items.empty:
        return pd.DataFrame(
            columns=["USUBJID", "VISIT", "VISITNUM", "QSDTC", "total", "n_items", "complete"]
        )

    grouped = items.groupby(["USUBJID", "VISIT", "VISITNUM", "QSDTC"], dropna=False)
    totals = grouped["QSSTRESN"].agg(["sum", "count"]).reset_index()
    totals = totals.rename(columns={"sum": "total", "count": "n_items"})
    totals["complete"] = totals["n_items"] == instrument.n_items
    totals.loc[~totals["complete"], "total"] = pd.NA

    if require_complete and not totals["complete"].all():
        incomplete = int((~totals["complete"]).sum())
        raise IncompleteInstrument(
            f"{instrument.name}: {incomplete} subject-visit(s) have fewer than "
            f"{instrument.n_items} items; totals for those are not derived."
        )

    return totals[["USUBJID", "VISIT", "VISITNUM", "QSDTC", "total", "n_items", "complete"]]


def derive_all_totals(qs: pd.DataFrame) -> pd.DataFrame:
    """Derived totals for every supported instrument, in long form."""
    frames = []
    for instrument in (MMSE, HACHINSKI):
        totals = derive_total(qs, instrument, require_complete=False)
        totals = totals.assign(
            QSTESTCD=instrument.total_testcd,
            QSTEST=instrument.total_test,
            QSCAT=instrument.category,
        )
        frames.append(totals)
    return pd.concat(frames, ignore_index=True)
