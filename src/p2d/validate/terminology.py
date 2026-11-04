"""CDISC controlled terminology, as published by NCI EVS.

Only the codelists this study's variables actually bind to are used. Where a
variable has no usable published codelist the binding is omitted rather than
approximated, so a missing check is visible in the rule list instead of
silently passing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

#: SDTM variable to the NCI codelist that governs it.
CODELIST_BINDINGS: dict[str, str] = {
    "SEX": "Sex",
    "RACE": "Race As Collected",
    "ETHNIC": "Ethnicity As Collected",
    "VSTESTCD": "Vital Signs Test Code",
    "VSPOS": "Position",
    "VSSTAT": "Not Done",
    "LBTESTCD": "Laboratory Test Code",
    "LBNRIND": "Reference Range Indicator",
}

#: Variables deliberately left unchecked, with the reason. Listed in the rule
#: documentation so the gap is stated rather than hidden.
UNBOUND_VARIABLES: dict[str, str] = {
    "COUNTRY": "Governed by ISO 3166, which is not part of CDISC SDTM terminology.",
    "QSTESTCD": (
        "Questionnaire item codes are instrument-specific and are not published "
        "as a single SDTM codelist."
    ),
    "ARM": "Arm names are study-specific and defined by the trial design domains.",
}


@dataclass(frozen=True)
class Terminology:
    codelists: dict[str, frozenset[str]]

    @classmethod
    def load(cls, path: str | Path) -> Terminology:
        frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
        grouped = frame.groupby("Codelist Name")["CDISC Submission Value"]
        return cls({name: frozenset(values) for name, values in grouped})

    def values_for(self, variable: str) -> frozenset[str] | None:
        """Permitted values for a variable, or None when it has no binding."""
        codelist = CODELIST_BINDINGS.get(variable)
        if codelist is None:
            return None
        return self.codelists.get(codelist)

    def __len__(self) -> int:
        return len(self.codelists)
