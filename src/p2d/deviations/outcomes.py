"""What evaluating a criterion against a subject can conclude."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class Outcome(StrEnum):
    """Three outcomes, not two.

    Treating absent data as a pass would understate deviations; treating it as
    a deviation would invent them. Not evaluable is reported as its own
    outcome and counted separately in the coverage report.
    """

    PASS = "PASS"
    DEVIATION = "DEVIATION"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class Evaluation:
    """One criterion evaluated against one subject.

    ``source_domain`` and ``source_key`` are what make a finding checkable:
    they point at the published record the conclusion was drawn from.
    """

    usubjid: str
    criterion_id: str
    outcome: Outcome
    reason: str
    observed: str = ""
    source_domain: str = ""
    source_key: str = ""


def to_frame(evaluations: list[Evaluation]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "usubjid": e.usubjid,
                "criterion_id": e.criterion_id,
                "outcome": e.outcome.value,
                "reason": e.reason,
                "observed": e.observed,
                "source_domain": e.source_domain,
                "source_key": e.source_key,
            }
            for e in evaluations
        ],
        columns=[
            "usubjid",
            "criterion_id",
            "outcome",
            "reason",
            "observed",
            "source_domain",
            "source_key",
        ],
    )
