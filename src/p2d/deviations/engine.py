"""Running the eligibility rules and reporting coverage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from p2d.deviations.outcomes import Evaluation, Outcome, to_frame
from p2d.deviations.rules import EXECUTABLE_RULES, NO_RULE_REASONS, EvaluationContext

#: Subjects the rules are evaluated against. Screen failures were correctly
#: excluded by the study, so flagging one would be a false positive.
RANDOMIZED_EXCLUSION = "Screen Failure"


def randomized_subjects(dm: pd.DataFrame) -> pd.DataFrame:
    return dm[dm["ARM"] != RANDOMIZED_EXCLUSION][["USUBJID", "SITEID", "ARM", "AGE", "SEX"]].copy()


def build_context(dm: pd.DataFrame, qs: pd.DataFrame, lb: pd.DataFrame) -> EvaluationContext:
    return EvaluationContext(subjects=randomized_subjects(dm), dm=dm, qs=qs, lb=lb)


def evaluate(context: EvaluationContext) -> list[Evaluation]:
    """Run every executable rule over every randomized subject."""
    evaluations: list[Evaluation] = []
    for rule in EXECUTABLE_RULES.values():
        evaluations.extend(rule(context))
    return evaluations


@dataclass(frozen=True)
class Coverage:
    total_criteria: int
    executable: int
    no_rule: int
    subjects: int
    outcomes: dict[str, int]

    @property
    def rule_coverage(self) -> float:
        return self.executable / self.total_criteria if self.total_criteria else 0.0


def coverage(
    evaluations: list[Evaluation], gold: pd.DataFrame, context: EvaluationContext
) -> Coverage:
    counts = {outcome.value: 0 for outcome in Outcome}
    for evaluation in evaluations:
        counts[evaluation.outcome.value] += 1

    return Coverage(
        total_criteria=len(gold),
        executable=len(EXECUTABLE_RULES),
        no_rule=len(gold) - len(EXECUTABLE_RULES),
        subjects=len(context.subjects),
        outcomes=counts,
    )


def deviations_with_subject_detail(
    evaluations: list[Evaluation], context: EvaluationContext
) -> pd.DataFrame:
    """Flagged subjects, joined to the demographics a reviewer would want."""
    frame = to_frame(evaluations)
    flagged = frame[frame["outcome"] == Outcome.DEVIATION.value]
    subjects = context.subjects.rename(columns={"USUBJID": "usubjid"})
    return flagged.merge(subjects, on="usubjid", how="left")


def per_criterion_summary(evaluations: list[Evaluation], gold: pd.DataFrame) -> pd.DataFrame:
    """One row per criterion: how it was handled and what it found."""
    frame = to_frame(evaluations)
    counts = (
        frame.pivot_table(
            index="criterion_id", columns="outcome", values="usubjid", aggfunc="count"
        )
        .fillna(0)
        .astype(int)
    )

    rows = []
    for record in gold.itertuples():
        cid = record.criterion_id
        has_rule = cid in EXECUTABLE_RULES
        row = {
            "criterion_id": cid,
            "category": record.category,
            "gold_testability": record.testability,
            "has_executable_rule": has_rule,
            "pass": int(counts.loc[cid, "PASS"]) if has_rule and "PASS" in counts.columns else 0,
            "deviation": int(counts.loc[cid, "DEVIATION"])
            if has_rule and "DEVIATION" in counts.columns
            else 0,
            "not_evaluable": int(counts.loc[cid, "NOT_EVALUABLE"])
            if has_rule and "NOT_EVALUABLE" in counts.columns
            else 0,
            "reason_no_rule": "" if has_rule else NO_RULE_REASONS.get(cid, ""),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def load_domains(sdtm_dir: str | Path) -> dict[str, pd.DataFrame]:
    directory = Path(sdtm_dir)
    return {p.stem.upper(): pd.read_parquet(p) for p in directory.glob("*.parquet")}
