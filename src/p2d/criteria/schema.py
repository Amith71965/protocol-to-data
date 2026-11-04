"""Structured form of a protocol eligibility criterion.

The schema is the contract the LLM has to fill. Keeping it strict matters more
than keeping it expressive: a criterion the model cannot express without
guessing should come back labelled not testable, rather than as a rule that
looks executable and quietly checks the wrong thing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Category(StrEnum):
    INCLUSION = "INCLUSION"
    EXCLUSION = "EXCLUSION"


class Testability(StrEnum):
    """How much of a criterion the collected data can actually answer."""

    #: Every clause can be evaluated from published data.
    TESTABLE = "TESTABLE"
    #: Some clauses can be evaluated; others have no data behind them.
    PARTIALLY_TESTABLE = "PARTIALLY_TESTABLE"
    #: Nothing in the published data speaks to this criterion.
    NOT_TESTABLE = "NOT_TESTABLE"


class Operator(StrEnum):
    BETWEEN = "BETWEEN"
    LE = "LE"
    LT = "LT"
    GE = "GE"
    GT = "GT"
    EQ = "EQ"
    NE = "NE"
    #: A matching record exists for the subject.
    EXISTS = "EXISTS"
    #: No matching record exists for the subject.
    NOT_EXISTS = "NOT_EXISTS"
    #: The result sits outside its reference range.
    OUT_OF_RANGE = "OUT_OF_RANGE"


class Criterion(BaseModel):
    """One eligibility criterion, in machine-checkable form."""

    model_config = {"extra": "forbid", "frozen": True}

    criterion_id: str = Field(description="Published identifier, e.g. INCL03.")
    category: Category
    text: str = Field(min_length=1, description="The criterion as written.")
    testability: Testability
    rationale: str = Field(
        min_length=1,
        description="Why this testability, naming the data that is or is not available.",
    )

    target_domain: str | None = Field(
        default=None, description="SDTM domain holding the evidence, e.g. QS."
    )
    target_variable: str | None = Field(
        default=None, description="Variable or derived score, e.g. MMSETOT."
    )
    operator: Operator | None = None
    threshold_low: float | None = None
    threshold_high: float | None = None
    threshold_text: str | None = Field(
        default=None, description="Non-numeric comparison value, e.g. a coded term."
    )
    unit: str | None = None
    window_days: int | None = Field(
        default=None, description="Look-back window in days, where the criterion names one."
    )

    @model_validator(mode="after")
    def _executable_criteria_need_a_target(self) -> Criterion:
        """A criterion claimed testable must say what it would check."""
        if self.testability is Testability.TESTABLE and not (
            self.target_domain and self.target_variable and self.operator
        ):
            raise ValueError(
                f"{self.criterion_id}: labelled TESTABLE but gives no domain, "
                "variable and operator to check."
            )
        return self

    @model_validator(mode="after")
    def _between_needs_both_bounds(self) -> Criterion:
        if self.operator is Operator.BETWEEN:
            if self.threshold_low is None or self.threshold_high is None:
                raise ValueError(f"{self.criterion_id}: BETWEEN needs both bounds.")
            if self.threshold_low > self.threshold_high:
                raise ValueError(f"{self.criterion_id}: BETWEEN bounds are inverted.")
        return self

    @property
    def is_executable(self) -> bool:
        """Whether a rule can be compiled and run for this criterion."""
        return (
            self.testability is not Testability.NOT_TESTABLE
            and self.target_domain is not None
            and self.target_variable is not None
            and self.operator is not None
        )


class CriteriaExtraction(BaseModel):
    """What one extraction call returns."""

    model_config = {"extra": "forbid"}

    criteria: list[Criterion]

    def by_id(self) -> dict[str, Criterion]:
        return {c.criterion_id: c for c in self.criteria}
