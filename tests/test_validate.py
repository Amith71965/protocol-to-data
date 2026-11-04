"""Conformance rules, each with a passing and a failing case."""

from __future__ import annotations

import pandas as pd
import pytest

from p2d.validate.issues import Severity, to_frame
from p2d.validate.rules import (
    ALL_RULES,
    Dataset,
    controlled_terminology,
    domain_value_matches,
    iso_8601_dates,
    key_uniqueness,
    required_variables,
    run_all,
    sequence_is_a_positive_integer,
    standard_result_present,
    study_day_consistency,
    subject_exists_in_demographics,
)
from p2d.validate.terminology import Terminology


def vs_frame(**overrides) -> pd.DataFrame:
    base = {
        "STUDYID": ["CDISCPILOT01"],
        "DOMAIN": ["VS"],
        "USUBJID": ["01-701-1015"],
        "VSSEQ": [1.0],
        "VSTESTCD": ["SYSBP"],
        "VSORRES": ["120"],
        "VSSTRESN": [120.0],
        "VSDTC": ["2014-01-05"],
        "VSDY": [4.0],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def dm_frame() -> pd.DataFrame:
    return pd.DataFrame({"USUBJID": ["01-701-1015"], "RFSTDTC": ["2014-01-02"]})


def dataset(frame: pd.DataFrame, **kwargs) -> Dataset:
    return Dataset(domain="VS", frame=frame, **kwargs)


# --- SD0001 required variables -------------------------------------------------


def test_required_variables_pass() -> None:
    assert required_variables(dataset(vs_frame())) == []


def test_required_variables_flags_a_missing_identifier() -> None:
    frame = vs_frame().drop(columns=["USUBJID"])

    issues = required_variables(dataset(frame))

    assert [i.variable for i in issues] == ["USUBJID"]
    assert issues[0].severity is Severity.ERROR


def test_demographics_needs_no_sequence_variable() -> None:
    frame = pd.DataFrame({"STUDYID": ["S"], "DOMAIN": ["DM"], "USUBJID": ["01-701-1015"]})

    assert required_variables(Dataset(domain="DM", frame=frame)) == []


# --- SD0002 domain value -------------------------------------------------------


def test_domain_value_pass() -> None:
    assert domain_value_matches(dataset(vs_frame())) == []


def test_domain_value_flags_the_wrong_code() -> None:
    issues = domain_value_matches(dataset(vs_frame(DOMAIN=["LB"])))

    assert len(issues) == 1
    assert issues[0].observed == "LB"


# --- SD0003 key uniqueness -----------------------------------------------------


def test_key_uniqueness_pass() -> None:
    frame = pd.concat([vs_frame(), vs_frame(VSSEQ=[2.0])], ignore_index=True)

    assert key_uniqueness(dataset(frame)) == []


def test_key_uniqueness_flags_both_duplicates() -> None:
    frame = pd.concat([vs_frame(), vs_frame()], ignore_index=True)

    issues = key_uniqueness(dataset(frame))

    assert len(issues) == 2


# --- SD0004 sequence numbers ---------------------------------------------------


def test_sequence_pass() -> None:
    assert sequence_is_a_positive_integer(dataset(vs_frame())) == []


@pytest.mark.parametrize("bad", [0.0, -1.0, 1.5, None])
def test_sequence_rejects_invalid_values(bad) -> None:
    assert len(sequence_is_a_positive_integer(dataset(vs_frame(VSSEQ=[bad])))) == 1


# --- SD0005 ISO 8601 dates -----------------------------------------------------


@pytest.mark.parametrize("good", ["2014", "2014-01", "2014-01-05", "2014-01-05T09:30"])
def test_iso_dates_accept_full_and_partial_forms(good) -> None:
    """SDTM permits partial dates; they are not malformed."""
    assert iso_8601_dates(dataset(vs_frame(VSDTC=[good]))) == []


@pytest.mark.parametrize("bad", ["05/01/2014", "2014-1-5", "Jan 2014"])
def test_iso_dates_reject_other_formats(bad) -> None:
    assert len(iso_8601_dates(dataset(vs_frame(VSDTC=[bad])))) == 1


def test_blank_date_is_not_a_format_error() -> None:
    assert iso_8601_dates(dataset(vs_frame(VSDTC=[""]))) == []


# --- SD0006 controlled terminology ---------------------------------------------


@pytest.fixture
def terminology(tmp_path):
    path = tmp_path / "ct.txt"
    rows = [
        ("Codelist Name", "CDISC Submission Value"),
        ("Vital Signs Test Code", "SYSBP"),
        ("Vital Signs Test Code", "DIABP"),
        ("Sex", "F"),
        ("Sex", "M"),
    ]
    path.write_text("\n".join("\t".join(r) for r in rows))
    return Terminology.load(path)


def test_terminology_pass(terminology) -> None:
    assert controlled_terminology(dataset(vs_frame(), terminology=terminology)) == []


def test_terminology_flags_a_value_outside_its_codelist(terminology) -> None:
    issues = controlled_terminology(
        dataset(vs_frame(VSTESTCD=["NOTACODE"]), terminology=terminology)
    )

    assert len(issues) == 1
    assert issues[0].observed == "NOTACODE"
    assert issues[0].severity is Severity.WARNING


def test_terminology_ignores_unbound_variables(terminology) -> None:
    """A variable with no published codelist is not judged against a guess."""
    frame = vs_frame(COUNTRY=["USA"])

    assert controlled_terminology(dataset(frame, terminology=terminology)) == []


def test_terminology_skipped_when_not_loaded() -> None:
    assert controlled_terminology(dataset(vs_frame(VSTESTCD=["NOPE"]))) == []


# --- SD0007 referential integrity ----------------------------------------------


def test_referential_integrity_pass() -> None:
    assert subject_exists_in_demographics(dataset(vs_frame(), demographics=dm_frame())) == []


def test_referential_integrity_flags_an_unknown_subject() -> None:
    frame = vs_frame(USUBJID=["01-999-9999"])

    issues = subject_exists_in_demographics(dataset(frame, demographics=dm_frame()))

    assert len(issues) == 1
    assert issues[0].observed == "01-999-9999"


# --- SD0008 study day ----------------------------------------------------------


def test_study_day_pass() -> None:
    """2014-01-05 against a start of 2014-01-02 is day 4."""
    assert study_day_consistency(dataset(vs_frame(), demographics=dm_frame())) == []


def test_study_day_flags_a_disagreement() -> None:
    issues = study_day_consistency(dataset(vs_frame(VSDY=[99.0]), demographics=dm_frame()))

    assert len(issues) == 1
    assert "expected 4" in issues[0].observed


def test_study_day_ignores_records_without_a_date() -> None:
    frame = vs_frame(VSDTC=[""], VSDY=[None])

    assert study_day_consistency(dataset(frame, demographics=dm_frame())) == []


# --- SD0009 standardised result ------------------------------------------------


def test_standard_result_pass() -> None:
    assert standard_result_present(dataset(vs_frame())) == []


def test_standard_result_flags_a_missing_standardisation() -> None:
    issues = standard_result_present(dataset(vs_frame(VSSTRESN=[None])))

    assert len(issues) == 1


def test_non_numeric_result_needs_no_standardisation() -> None:
    frame = vs_frame(VSORRES=["NOT DONE"], VSSTRESN=[None])

    assert standard_result_present(dataset(frame)) == []


# --- wiring --------------------------------------------------------------------


def test_every_rule_is_registered() -> None:
    assert set(ALL_RULES) == {f"SD000{n}" for n in range(1, 10)}


def test_run_all_finds_issues_from_more_than_one_rule() -> None:
    frame = vs_frame(DOMAIN=["LB"], VSSEQ=[-1.0])

    rule_ids = {i.rule_id for i in run_all(dataset(frame))}

    assert {"SD0002", "SD0004"} <= rule_ids


def test_issue_table_has_a_stable_shape() -> None:
    issues = run_all(dataset(vs_frame(DOMAIN=["LB"])))

    frame = to_frame(issues)

    assert list(frame.columns) == [
        "rule_id",
        "severity",
        "domain",
        "variable",
        "usubjid",
        "record_key",
        "observed",
        "message",
    ]
