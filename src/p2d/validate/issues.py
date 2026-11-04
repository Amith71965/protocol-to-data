"""The shape of a validation finding.

Every issue names the rule that fired, the record it fired on and the value
that caused it, so a reviewer can go straight to the data rather than
re-deriving what the checker saw.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class Severity(StrEnum):
    """How much a finding matters.

    ERROR blocks a submission; WARNING is worth a look; NOTICE is informational.
    """

    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"


@dataclass(frozen=True)
class Issue:
    rule_id: str
    severity: Severity
    domain: str
    message: str
    variable: str = ""
    usubjid: str = ""
    record_key: str = ""
    observed: str = ""


def to_frame(issues: list[Issue]) -> pd.DataFrame:
    """Flatten issues into the report table."""
    return pd.DataFrame(
        [
            {
                "rule_id": i.rule_id,
                "severity": i.severity.value,
                "domain": i.domain,
                "variable": i.variable,
                "usubjid": i.usubjid,
                "record_key": i.record_key,
                "observed": i.observed,
                "message": i.message,
            }
            for i in issues
        ],
        columns=[
            "rule_id",
            "severity",
            "domain",
            "variable",
            "usubjid",
            "record_key",
            "observed",
            "message",
        ],
    )
