"""Loading and shaping the pipeline's outputs for the dashboard.

Kept free of Streamlit so every function here is testable headlessly. The
dashboard is a view over files the pipeline already wrote; it computes nothing
the reports do not already contain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from p2d.paths import GOLD_DIR, REPORTS_DIR, SDTM_DIR


class PipelineOutputMissingError(FileNotFoundError):
    """A required report has not been generated yet."""


def _read_csv(path: Path, what: str) -> pd.DataFrame:
    if not path.exists():
        raise PipelineOutputMissingError(
            f"{what} not found at {path}. Run the pipeline scripts first "
            "(see the README's quick start)."
        )
    return pd.read_csv(path, keep_default_na=False)


@dataclass(frozen=True)
class Dashboard:
    evaluations: pd.DataFrame
    deviations: pd.DataFrame
    validation: pd.DataFrame
    gold: pd.DataFrame
    demographics: pd.DataFrame

    @property
    def n_subjects(self) -> int:
        return int(self.evaluations["usubjid"].nunique())

    @property
    def n_deviations(self) -> int:
        return len(self.deviations)

    @property
    def n_criteria(self) -> int:
        return len(self.gold)

    @property
    def n_with_rules(self) -> int:
        return int(self.evaluations["criterion_id"].nunique())

    @property
    def rule_coverage(self) -> float:
        return self.n_with_rules / self.n_criteria if self.n_criteria else 0.0


def load(
    reports_dir: Path = REPORTS_DIR,
    gold_dir: Path = GOLD_DIR,
    sdtm_dir: Path = SDTM_DIR,
) -> Dashboard:
    dm_path = sdtm_dir / "dm.parquet"
    if not dm_path.exists():
        raise PipelineOutputMissingError(
            f"Mapped demographics not found at {dm_path}. Run scripts/build_sdtm.py."
        )

    return Dashboard(
        evaluations=_read_csv(reports_dir / "evaluations.csv", "Evaluations"),
        deviations=_read_csv(reports_dir / "deviations.csv", "Deviations"),
        validation=_read_csv(reports_dir / "validation_issues.csv", "Validation issues"),
        gold=_read_csv(gold_dir / "criteria_gold.csv", "Criteria gold set"),
        demographics=pd.read_parquet(dm_path),
    )


def outcome_counts(evaluations: pd.DataFrame) -> pd.DataFrame:
    """Totals per outcome, in a fixed order."""
    order = ["PASS", "DEVIATION", "NOT_EVALUABLE"]
    counts = evaluations["outcome"].value_counts()
    return pd.DataFrame({"outcome": order, "evaluations": [int(counts.get(o, 0)) for o in order]})


def deviations_by_criterion(deviations: pd.DataFrame) -> pd.DataFrame:
    """Flagged subjects per criterion, most first."""
    if deviations.empty:
        return pd.DataFrame(columns=["criterion_id", "subjects"])
    counts = (
        deviations.groupby("criterion_id")["usubjid"]
        .nunique()
        .reset_index(name="subjects")
        .sort_values("subjects", ascending=False)
    )
    return counts.reset_index(drop=True)


def validation_by_severity(issues: pd.DataFrame) -> pd.DataFrame:
    order = ["error", "warning", "notice"]
    if issues.empty:
        return pd.DataFrame({"severity": order, "issues": [0, 0, 0]})
    counts = issues["severity"].value_counts()
    return pd.DataFrame({"severity": order, "issues": [int(counts.get(s, 0)) for s in order]})


def enrollment_by_site(demographics: pd.DataFrame) -> pd.DataFrame:
    """Subjects per site and arm."""
    frame = (
        demographics.groupby(["SITEID", "ARM"])["USUBJID"].nunique().reset_index(name="subjects")
    )
    frame["SITEID"] = frame["SITEID"].astype(str)
    return frame.sort_values(["SITEID", "ARM"]).reset_index(drop=True)


def coverage_table(gold: pd.DataFrame, evaluations: pd.DataFrame) -> pd.DataFrame:
    """Every criterion, whether it has a rule, and what it found."""
    with_rules = set(evaluations["criterion_id"])
    counts = (
        evaluations.pivot_table(
            index="criterion_id", columns="outcome", values="usubjid", aggfunc="count"
        )
        .fillna(0)
        .astype(int)
    )

    rows = []
    for record in gold.itertuples():
        cid = record.criterion_id
        has_rule = cid in with_rules
        rows.append(
            {
                "criterion_id": cid,
                "category": record.category,
                "testability": record.testability,
                "has_rule": has_rule,
                "deviations": int(counts.loc[cid, "DEVIATION"])
                if has_rule and "DEVIATION" in counts.columns
                else 0,
                "not_evaluable": int(counts.loc[cid, "NOT_EVALUABLE"])
                if has_rule and "NOT_EVALUABLE" in counts.columns
                else 0,
                "text": record.text,
                "rationale": record.rationale,
            }
        )
    return pd.DataFrame(rows)


def filter_deviations(
    deviations: pd.DataFrame,
    criteria: list[str] | None = None,
    sites: list[str] | None = None,
    arms: list[str] | None = None,
) -> pd.DataFrame:
    """Narrow the deviation list. An empty selection means no filter."""
    frame = deviations
    if criteria:
        frame = frame[frame["criterion_id"].isin(criteria)]
    if sites:
        frame = frame[frame["SITEID"].astype(str).isin([str(s) for s in sites])]
    if arms:
        frame = frame[frame["ARM"].isin(arms)]
    return frame.reset_index(drop=True)
