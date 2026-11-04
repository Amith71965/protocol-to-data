"""Mapping the demographics CRF page to SDTM DM.

DM needs no transposition — a demographics page is already one row per subject.
What it does need is identifier assembly and a study day, which is exactly the
part a CRF cannot carry.
"""

from __future__ import annotations

import pandas as pd

from p2d.mapping.derive import STUDY_ID, make_usubjid, study_day

#: Columns a demographics page collects, in CRF order.
COLLECTED = [
    "SITENUM",
    "SUBJID",
    "RFSTDTC",
    "RFENDTC",
    "RFXSTDTC",
    "RFXENDTC",
    "RFICDTC",
    "RFPENDTC",
    "DTHDTC",
    "DTHFL",
    "AGE",
    "AGEU",
    "SEX",
    "RACE",
    "ETHNIC",
    "ARMCD",
    "ARM",
    "ACTARMCD",
    "ACTARM",
    "COUNTRY",
    "DMDTC",
]

#: Variables the mapper rebuilds rather than reads.
DERIVED = ["STUDYID", "DOMAIN", "USUBJID", "SITEID", "DMDY"]


def to_crf(dm: pd.DataFrame) -> pd.DataFrame:
    """Reduce SDTM DM to the demographics page it came from."""
    page = dm.copy()
    page["SITENUM"] = page["USUBJID"].str.split("-").str[1]
    page["SUBJID"] = page["USUBJID"].str.split("-").str[2]
    return page[[c for c in COLLECTED if c in page.columns]].reset_index(drop=True)


def from_crf(page: pd.DataFrame) -> pd.DataFrame:
    """Rebuild SDTM DM from the demographics page."""
    dm = page.copy()
    dm["STUDYID"] = STUDY_ID
    dm["DOMAIN"] = "DM"
    dm["USUBJID"] = make_usubjid(dm["SITENUM"], dm["SUBJID"])
    dm["SITEID"] = dm["SITENUM"]
    dm["DMDY"] = study_day(dm["DMDTC"], dm["RFSTDTC"])
    return dm.drop(columns=["SITENUM"]).reset_index(drop=True)


def roundtrip(dm: pd.DataFrame) -> pd.DataFrame:
    return from_crf(to_crf(dm))
