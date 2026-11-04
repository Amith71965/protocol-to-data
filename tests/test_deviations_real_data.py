"""The deviation engine against the real study data.

These are the project's headline claims, written as assertions so they cannot
quietly stop being true.
"""

from __future__ import annotations

import pandas as pd
import pytest

from p2d.deviations.engine import build_context, evaluate, load_domains
from p2d.deviations.outcomes import Outcome, to_frame
from p2d.ingest.reader import read_domain
from p2d.paths import SDTM_DIR

pytestmark = pytest.mark.requires_data

#: Subjects randomized and dosed despite an MMSE outside the protocol's 10-23
#: window. Both scored 24.
KNOWN_INCL03_DEVIATIONS = {"01-707-1037", "01-709-1238"}


@pytest.fixture(scope="module")
def evaluations(raw_dir):
    if not any(SDTM_DIR.glob("*.parquet")):
        pytest.skip("mapped SDTM not built; run scripts/build_sdtm.py")
    domains = load_domains(SDTM_DIR)
    context = build_context(domains["DM"], domains["QS"], domains["LB"])
    return context, evaluate(context)


def test_the_two_known_mmse_deviations_are_found(evaluations) -> None:
    _, results = evaluations

    flagged = {
        e.usubjid for e in results if e.criterion_id == "INCL03" and e.outcome is Outcome.DEVIATION
    }

    assert flagged == KNOWN_INCL03_DEVIATIONS


def test_both_mmse_deviations_scored_twenty_four(evaluations) -> None:
    _, results = evaluations

    observed = {
        e.usubjid: e.observed
        for e in results
        if e.criterion_id == "INCL03" and e.outcome is Outcome.DEVIATION
    }

    assert observed == dict.fromkeys(KNOWN_INCL03_DEVIATIONS, "24")


def test_the_flagged_subjects_were_actually_randomized(raw_dir, evaluations) -> None:
    """A screen failure scoring 24 would be correct behaviour, not a deviation."""
    dm = read_domain(raw_dir, "dm")

    arms = dm[dm["USUBJID"].isin(KNOWN_INCL03_DEVIATIONS)]["ARM"]

    assert set(arms) == {"Xanomeline Low Dose", "Xanomeline High Dose"}


def test_every_randomized_subject_is_evaluated_for_every_rule(evaluations) -> None:
    context, results = evaluations
    frame = to_frame(results)

    per_criterion = frame.groupby("criterion_id")["usubjid"].nunique()

    assert (per_criterion == len(context.subjects)).all()
    assert len(context.subjects) == 254


def test_no_screen_failure_is_ever_flagged(raw_dir, evaluations) -> None:
    _, results = evaluations
    dm = read_domain(raw_dir, "dm")
    screen_failures = set(dm.loc[dm["ARM"] == "Screen Failure", "USUBJID"])

    assert not screen_failures & {e.usubjid for e in results}


def test_every_deviation_traces_to_a_named_source(evaluations) -> None:
    """A flag a reviewer cannot check is not usable."""
    _, results = evaluations

    for evaluation in results:
        if evaluation.outcome is Outcome.DEVIATION:
            assert evaluation.source_domain, evaluation.criterion_id
            assert evaluation.reason
            assert evaluation.observed


def test_mmse_deviations_resolve_to_real_questionnaire_records(raw_dir, evaluations) -> None:
    """Walk one finding back to the published data it came from."""
    qs = read_domain(raw_dir, "qs")

    for usubjid in KNOWN_INCL03_DEVIATIONS:
        items = qs[(qs["USUBJID"] == usubjid) & (qs["QSCAT"] == "MINI-MENTAL STATE")]
        assert len(items) == 6
        assert items["QSSTRESN"].sum() == 24


def test_not_evaluable_is_used_rather_than_a_silent_pass(evaluations) -> None:
    """Absent data must not be reported as compliance."""
    _, results = evaluations
    frame = to_frame(results)

    not_evaluable = frame[frame["outcome"] == Outcome.NOT_EVALUABLE.value]

    assert len(not_evaluable) > 0
    assert (not_evaluable["reason"].str.len() > 0).all()


def test_consent_criterion_reports_no_false_deviations(evaluations) -> None:
    """DM.RFICDTC is empty for this study; that is a gap, not 254 violations."""
    _, results = evaluations

    outcomes = {e.outcome for e in results if e.criterion_id == "INCL06"}

    assert outcomes == {Outcome.NOT_EVALUABLE}


def test_reported_deviation_count_matches_the_published_report() -> None:
    """The committed report and a fresh run must agree."""
    report = pd.read_csv("reports/deviations.csv", keep_default_na=False)

    assert len(report) == 115
    assert set(report[report["criterion_id"] == "INCL03"]["usubjid"]) == KNOWN_INCL03_DEVIATIONS
