"""Scoring an extraction against the hand-labelled gold set.

Two things are measured and reported separately, because they fail for
different reasons:

**Extraction** — did the model find each published criterion, and nothing that
is not one? Scored as precision and recall against the 31 identifiers the study
publishes in its TI domain.

**Testability** — of the criteria it found, did it judge correctly what the data
can answer? Scored as accuracy plus a per-label breakdown, because a model that
calls everything partially testable would otherwise look respectable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from p2d.criteria.schema import Criterion, Testability


@dataclass(frozen=True)
class Scores:
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        found = self.true_positives + self.false_positives
        return self.true_positives / found if found else 0.0

    @property
    def recall(self) -> float:
        expected = self.true_positives + self.false_negatives
        return self.true_positives / expected if expected else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass(frozen=True)
class AlignmentReport:
    extraction: Scores
    missed: list[str]
    spurious: list[str]
    testability_correct: int
    testability_total: int
    confusion: pd.DataFrame

    @property
    def testability_accuracy(self) -> float:
        return self.testability_correct / self.testability_total if self.testability_total else 0.0


def load_gold(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False)


def align(criteria: list[Criterion], gold: pd.DataFrame) -> AlignmentReport:
    """Compare an extraction against the gold set."""
    extracted = {c.criterion_id: c for c in criteria}
    expected = set(gold["criterion_id"])

    found = set(extracted) & expected
    missed = sorted(expected - set(extracted))
    spurious = sorted(set(extracted) - expected)

    gold_labels = dict(zip(gold["criterion_id"], gold["testability"], strict=True))
    pairs = [(gold_labels[cid], extracted[cid].testability.value) for cid in sorted(found)]
    correct = sum(1 for expected_label, actual in pairs if expected_label == actual)

    labels = [t.value for t in Testability]
    confusion = pd.DataFrame(0, index=labels, columns=labels, dtype=int)
    confusion.index.name = "gold"
    for expected_label, actual in pairs:
        confusion.loc[expected_label, actual] += 1

    return AlignmentReport(
        extraction=Scores(len(found), len(spurious), len(missed)),
        missed=missed,
        spurious=spurious,
        testability_correct=correct,
        testability_total=len(pairs),
        confusion=confusion,
    )
