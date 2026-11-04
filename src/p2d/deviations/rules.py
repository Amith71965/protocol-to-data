"""Executable eligibility rules.

A rule is only written where the published data genuinely answers the
criterion. Several criteria are labelled partially testable in the gold set and
still get no rule here, because the evaluable fragment would not be a fair
reading of what the protocol asked. Which criteria have a rule, and which do
not and why, is the substance of the coverage report — not a detail.

Every rule returns one evaluation per subject, including the subjects it cannot
judge, so the denominator is always visible.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from p2d.deviations.outcomes import Evaluation, Outcome
from p2d.mapping.scores import HACHINSKI, MMSE, derive_total


@dataclass(frozen=True)
class EvaluationContext:
    """The data a rule may consult."""

    subjects: pd.DataFrame
    dm: pd.DataFrame
    qs: pd.DataFrame
    lb: pd.DataFrame

    @property
    def subject_ids(self) -> list[str]:
        return list(self.subjects["USUBJID"])


Rule = Callable[[EvaluationContext], list[Evaluation]]


def _score_rule(
    context: EvaluationContext,
    criterion_id: str,
    instrument,
    *,
    passes: Callable[[float], bool],
    description: str,
) -> list[Evaluation]:
    """Evaluate a derived questionnaire total against a threshold."""
    totals = derive_total(context.qs, instrument, require_complete=False)
    by_subject = {
        row.USUBJID: (row.total, row.n_items, row.complete) for row in totals.itertuples()
    }

    evaluations = []
    for usubjid in context.subject_ids:
        record = by_subject.get(usubjid)
        if record is None:
            evaluations.append(
                Evaluation(
                    usubjid=usubjid,
                    criterion_id=criterion_id,
                    outcome=Outcome.NOT_EVALUABLE,
                    reason=f"No {instrument.name} records for this subject.",
                    source_domain="QS",
                )
            )
            continue

        total, n_items, complete = record
        if not complete or pd.isna(total):
            evaluations.append(
                Evaluation(
                    usubjid=usubjid,
                    criterion_id=criterion_id,
                    outcome=Outcome.NOT_EVALUABLE,
                    reason=(
                        f"{instrument.name} is incomplete "
                        f"({n_items} of {instrument.n_items} items), so no total is derived."
                    ),
                    source_domain="QS",
                    source_key=f"QSCAT={instrument.category}",
                )
            )
            continue

        met = passes(float(total))
        evaluations.append(
            Evaluation(
                usubjid=usubjid,
                criterion_id=criterion_id,
                outcome=Outcome.PASS if met else Outcome.DEVIATION,
                reason=(
                    f"{instrument.name} total {total:.0f} {'meets' if met else 'does not meet'} "
                    f"{description}."
                ),
                observed=f"{total:.0f}",
                source_domain="QS",
                source_key=f"QSCAT={instrument.category}",
            )
        )
    return evaluations


def incl03_mmse_in_range(context: EvaluationContext) -> list[Evaluation]:
    """INCL03 — MMSE total between 10 and 23 inclusive."""
    return _score_rule(
        context,
        "INCL03",
        MMSE,
        passes=lambda total: 10 <= total <= 23,
        description="the required range of 10 to 23",
    )


def incl04_hachinski_at_most_four(context: EvaluationContext) -> list[Evaluation]:
    """INCL04 — Modified Hachinski Ischemic Score of 4 or less."""
    return _score_rule(
        context,
        "INCL04",
        HACHINSKI,
        passes=lambda total: total <= 4,
        description="the required maximum of 4",
    )


def incl01_age_at_least_fifty(context: EvaluationContext) -> list[Evaluation]:
    """INCL01 — at least 50 years of age.

    Only the age clause. The criterion also requires female subjects to be
    postmenopausal, which nothing in the data records, so a subject passing
    here has satisfied part of the criterion, not all of it.
    """
    ages = dict(zip(context.dm["USUBJID"], context.dm["AGE"], strict=True))

    evaluations = []
    for usubjid in context.subject_ids:
        age = ages.get(usubjid)
        if age is None or pd.isna(age):
            evaluations.append(
                Evaluation(
                    usubjid=usubjid,
                    criterion_id="INCL01",
                    outcome=Outcome.NOT_EVALUABLE,
                    reason="No age recorded in DM.",
                    source_domain="DM",
                )
            )
            continue
        met = float(age) >= 50
        evaluations.append(
            Evaluation(
                usubjid=usubjid,
                criterion_id="INCL01",
                outcome=Outcome.PASS if met else Outcome.DEVIATION,
                reason=(
                    f"Age {age:.0f} {'meets' if met else 'is below'} the minimum of 50. "
                    "Postmenopausal status is not collected and is not checked."
                ),
                observed=f"{age:.0f}",
                source_domain="DM",
                source_key="DM.AGE",
            )
        )
    return evaluations


def incl06_consent_recorded(context: EvaluationContext) -> list[Evaluation]:
    """INCL06 — a date of informed consent is on record.

    The criterion requires consent signed by the patient and the caregiver.
    Only the date is captured, so this rule establishes that consent was
    recorded, not that it was signed by both parties.
    """
    consent = dict(zip(context.dm["USUBJID"], context.dm["RFICDTC"], strict=True))

    evaluations = []
    for usubjid in context.subject_ids:
        value = str(consent.get(usubjid) or "").strip()
        if not value:
            # An empty variable means the date was not captured, not that
            # consent was never obtained. Reporting this as a deviation would
            # flag every subject in the study for a documentation gap.
            evaluations.append(
                Evaluation(
                    usubjid=usubjid,
                    criterion_id="INCL06",
                    outcome=Outcome.NOT_EVALUABLE,
                    reason="DM.RFICDTC is not populated for this study, so consent cannot be confirmed from the data.",
                    source_domain="DM",
                    source_key="DM.RFICDTC",
                )
            )
            continue
        evaluations.append(
            Evaluation(
                usubjid=usubjid,
                criterion_id="INCL06",
                outcome=Outcome.PASS,
                reason=(
                    "Informed consent date is recorded. Signatures are not captured "
                    "and are not checked."
                ),
                observed=value,
                source_domain="DM",
                source_key="DM.RFICDTC",
            )
        )
    return evaluations


#: Analytes EXCL27 names that the study publishes.
EXCL27_ANALYTES = ["CREAT", "BILI", "AST", "ALT", "ALP", "GGT", "HGB", "WBC", "PLAT"]

#: Analytes EXCL28 names that the study publishes. Folate, total T4, thyroid
#: uptake and the free thyroid index are not published and cannot be checked.
EXCL28_ANALYTES = ["VITB12", "TSH"]


def _lab_out_of_range_rule(
    context: EvaluationContext,
    criterion_id: str,
    analytes: list[str],
    caveat: str,
) -> list[Evaluation]:
    """Flag a subject whose baseline result for any named analyte is out of range.

    The protocol's own thresholds are the Lilly Reference Range III, which is
    proprietary and unavailable. The study's reference ranges are used instead,
    which is a documented proxy rather than the protocol's rule.
    """
    lb = context.lb
    baseline = lb[(lb["LBBLFL"].astype("string").fillna("") == "Y") & lb["LBTESTCD"].isin(analytes)]

    flagged: dict[str, list[str]] = {}
    for row in baseline.itertuples():
        indicator = str(getattr(row, "LBNRIND", "") or "").strip()
        if indicator in {"HIGH", "LOW", "ABNORMAL"}:
            flagged.setdefault(row.USUBJID, []).append(f"{row.LBTESTCD}={indicator}")

    tested = set(baseline["USUBJID"])
    evaluations = []
    for usubjid in context.subject_ids:
        if usubjid not in tested:
            evaluations.append(
                Evaluation(
                    usubjid=usubjid,
                    criterion_id=criterion_id,
                    outcome=Outcome.NOT_EVALUABLE,
                    reason=f"No baseline results for any of {', '.join(analytes)}.",
                    source_domain="LB",
                )
            )
            continue

        abnormal = flagged.get(usubjid, [])
        evaluations.append(
            Evaluation(
                usubjid=usubjid,
                criterion_id=criterion_id,
                outcome=Outcome.DEVIATION if abnormal else Outcome.PASS,
                reason=(
                    f"Baseline result outside the study reference range: {', '.join(sorted(abnormal))}. {caveat}"
                    if abnormal
                    else f"All baseline results within the study reference range. {caveat}"
                ),
                observed=", ".join(sorted(abnormal)),
                source_domain="LB",
                source_key="LBBLFL=Y",
            )
        )
    return evaluations


def excl27_laboratory_values(context: EvaluationContext) -> list[Evaluation]:
    """EXCL27 — laboratory values outside the reference range."""
    return _lab_out_of_range_rule(
        context,
        "EXCL27",
        EXCL27_ANALYTES,
        "The protocol's Lilly Reference Range III is proprietary; the study's own range is used.",
    )


def excl28_vitamin_and_thyroid(context: EvaluationContext) -> list[Evaluation]:
    """EXCL28 — vitamin B12 and thyroid function outside the reference range."""
    return _lab_out_of_range_rule(
        context,
        "EXCL28",
        EXCL28_ANALYTES,
        "Folate, total T4, thyroid uptake and the free thyroid index are not published.",
    )


def excl30_glycosylated_haemoglobin(context: EvaluationContext) -> list[Evaluation]:
    """EXCL30 — HbA1c above 9.5 percent.

    The protocol restricts this to insulin-dependent diabetics. The data does
    not reliably identify them, so the rule runs on every subject with a
    result, which may over-report.
    """
    lb = context.lb
    baseline = lb[(lb["LBBLFL"].astype("string").fillna("") == "Y") & (lb["LBTESTCD"] == "HBA1C")]
    results = {
        row.USUBJID: (row.LBORRES, pd.to_numeric(pd.Series([row.LBORRES]), errors="coerce").iloc[0])
        for row in baseline.itertuples()
    }

    evaluations = []
    for usubjid in context.subject_ids:
        record = results.get(usubjid)
        if record is None or pd.isna(record[1]):
            evaluations.append(
                Evaluation(
                    usubjid=usubjid,
                    criterion_id="EXCL30",
                    outcome=Outcome.NOT_EVALUABLE,
                    reason="No baseline HbA1c result.",
                    source_domain="LB",
                )
            )
            continue

        raw, value = record
        exceeded = float(value) > 9.5
        evaluations.append(
            Evaluation(
                usubjid=usubjid,
                criterion_id="EXCL30",
                outcome=Outcome.DEVIATION if exceeded else Outcome.PASS,
                reason=(
                    f"HbA1c {raw}% {'exceeds' if exceeded else 'is within'} the 9.5% limit. "
                    "The protocol restricts this criterion to insulin-dependent diabetics, "
                    "whom the data does not identify."
                ),
                observed=str(raw),
                source_domain="LB",
                source_key="LBTESTCD=HBA1C, LBBLFL=Y",
            )
        )
    return evaluations


#: Criteria with an executable rule.
EXECUTABLE_RULES: dict[str, Rule] = {
    "INCL01": incl01_age_at_least_fifty,
    "INCL03": incl03_mmse_in_range,
    "INCL04": incl04_hachinski_at_most_four,
    "INCL06": incl06_consent_recorded,
    "EXCL27": excl27_laboratory_values,
    "EXCL28": excl28_vitamin_and_thyroid,
    "EXCL30": excl30_glycosylated_haemoglobin,
}

#: Criteria the gold set marks as having some evaluable content, but for which
#: no rule is written, with the reason. Stated so the coverage report can
#: explain the gap rather than leave it blank.
NO_RULE_REASONS: dict[str, str] = {
    "INCL02": "MH records a primary diagnosis, but not the NINCDS-ADRDA determination the criterion names.",
    "EXCL10": "Approved Alzheimer's therapies are identifiable in CM, but 'any investigational agent' is not, so a rule would under-report by an unknown amount.",
    "EXCL11": "Neither seriousness nor hospitalisation is recorded in MH.",
    "EXCL12": "A body-system match would flag far more subjects than 'serious neurological conditions' means.",
    "EXCL14": "The psychiatric body system is much broader than the three illnesses the protocol lists.",
    "EXCL15": "Syncope relies on coded MH terms, and 254 of 1,818 MH records are uncoded.",
    "EXCL17": "'Serious' is not recorded, so a cardiac body-system match would over-report.",
    "EXCL18": "'Serious' is not recorded, so a gastrointestinal body-system match would over-report.",
    "EXCL19": "'Serious' is not recorded, so an endocrine body-system match would over-report.",
    "EXCL20": "The protocol names a specific list of respiratory disorders, narrower than the body system.",
    "EXCL21": "'Serious' is not recorded, so a renal body-system match would over-report.",
    "EXCL22": "'Serious' is not recorded, so a musculoskeletal body-system match would over-report.",
    "EXCL23": "Absence of an HIV term is weaker evidence than a negative test, which is not published.",
    "EXCL24": "The protocol names a specific list of serious infections, narrower than the body system.",
    "EXCL25": "The protocol's carve-outs for prior malignancy are not encoded in the data.",
    "EXCL31": "The protocol's 19-class washout table maps imperfectly onto CMCLAS, and some records are UNCODED.",
}
