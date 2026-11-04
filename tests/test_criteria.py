"""Criteria schema, caching, extraction and scoring."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from pydantic import ValidationError

from p2d.criteria.align import align
from p2d.criteria.cache import CacheMissError, ResponseCache, request_key
from p2d.criteria.extract import ExtractionError, build_prompt, extract
from p2d.criteria.protocol import CriteriaNotFoundError, find_criteria
from p2d.criteria.provider import CachingProvider, StubProvider
from p2d.criteria.schema import Category, Criterion, Operator, Testability

SCHEMA = {"type": "object"}


def criterion(**overrides) -> dict:
    base = {
        "criterion_id": "INCL03",
        "category": "INCLUSION",
        "text": "MMSE score of 10 to 23.",
        "testability": "TESTABLE",
        "rationale": "MMSE items are in QS and sum to a total.",
        "target_domain": "QS",
        "target_variable": "MMSETOT",
        "operator": "BETWEEN",
        "threshold_low": 10,
        "threshold_high": 23,
    }
    base.update(overrides)
    return base


# --- schema --------------------------------------------------------------------

def test_a_well_formed_criterion_validates() -> None:
    model = Criterion.model_validate(criterion())

    assert model.category is Category.INCLUSION
    assert model.operator is Operator.BETWEEN
    assert model.is_executable


def test_testable_criterion_must_say_what_it_checks() -> None:
    """A rule that claims to be testable but names no target is worse than none."""
    with pytest.raises(ValidationError, match="gives no domain"):
        Criterion.model_validate(criterion(target_domain=None, target_variable=None, operator=None))


def test_between_requires_both_bounds() -> None:
    with pytest.raises(ValidationError, match="needs both bounds"):
        Criterion.model_validate(criterion(threshold_high=None))


def test_between_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError, match="inverted"):
        Criterion.model_validate(criterion(threshold_low=23, threshold_high=10))


def test_not_testable_criterion_needs_no_target() -> None:
    model = Criterion.model_validate(
        criterion(
            criterion_id="EXCL16",
            testability="NOT_TESTABLE",
            rationale="No ECG domain is published.",
            target_domain=None,
            target_variable=None,
            operator=None,
            threshold_low=None,
            threshold_high=None,
        )
    )

    assert model.testability is Testability.NOT_TESTABLE
    assert not model.is_executable


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Criterion.model_validate(criterion(confidence=0.9))


# --- cache ---------------------------------------------------------------------

def test_request_key_is_stable() -> None:
    a = request_key("anthropic", "m", "sys", "prompt", SCHEMA)
    b = request_key("anthropic", "m", "sys", "prompt", SCHEMA)

    assert a == b


@pytest.mark.parametrize(
    "changed",
    [
        {"provider": "openrouter"},
        {"model": "other"},
        {"system": "different"},
        {"prompt": "different"},
        {"schema": {"type": "array"}},
    ],
)
def test_request_key_changes_with_every_input(changed) -> None:
    """A changed prompt must not silently reuse an answer to a different question."""
    base = {
        "provider": "anthropic",
        "model": "m",
        "system": "sys",
        "prompt": "prompt",
        "schema": SCHEMA,
    }
    assert request_key(**base) != request_key(**{**base, **changed})


def test_cache_round_trips(tmp_path) -> None:
    cache = ResponseCache(tmp_path)

    cache.put("abc", '{"ok": true}', provider="stub", model="m")

    assert cache.get("abc") == '{"ok": true}'
    assert "abc" in cache
    assert len(cache) == 1


def test_cache_miss_returns_none(tmp_path) -> None:
    assert ResponseCache(tmp_path).get("nope") is None


# --- caching provider ----------------------------------------------------------

def test_provider_is_called_once_then_served_from_cache(tmp_path) -> None:
    inner = StubProvider('{"criteria": []}')
    provider = CachingProvider(inner, ResponseCache(tmp_path))

    first = provider.complete("sys", "prompt", SCHEMA)
    second = provider.complete("sys", "prompt", SCHEMA)

    assert first == second
    assert len(inner.calls) == 1


def test_cache_only_mode_never_reaches_the_provider(tmp_path) -> None:
    """This is what keeps the test suite and CI offline."""
    inner = StubProvider('{"criteria": []}')
    provider = CachingProvider(inner, ResponseCache(tmp_path), cache_only=True)

    with pytest.raises(CacheMissError):
        provider.complete("sys", "prompt", SCHEMA)

    assert inner.calls == []


def test_cache_only_mode_serves_a_cached_answer(tmp_path) -> None:
    cache = ResponseCache(tmp_path)
    CachingProvider(StubProvider('{"criteria": []}'), cache).complete("sys", "prompt", SCHEMA)

    offline = CachingProvider(StubProvider("unused"), cache, cache_only=True)

    assert offline.complete("sys", "prompt", SCHEMA) == '{"criteria": []}'


# --- extraction ----------------------------------------------------------------

def test_extract_parses_a_valid_response() -> None:
    provider = StubProvider(json.dumps({"criteria": [criterion()]}))

    result = extract(provider, "MMSE score of 10 to 23.")

    assert [c.criterion_id for c in result.criteria] == ["INCL03"]


def test_extract_rejects_non_json() -> None:
    with pytest.raises(ExtractionError, match="not valid JSON"):
        extract(StubProvider("I think the answer is..."), "text")


def test_extract_rejects_a_response_that_breaks_the_schema() -> None:
    bad = json.dumps({"criteria": [criterion(testability="MAYBE")]})

    with pytest.raises(ExtractionError, match="did not match the schema"):
        extract(StubProvider(bad), "text")


def test_prompt_states_what_is_absent() -> None:
    """Without the inventory the model cannot judge testability honestly."""
    prompt = build_prompt("criteria go here")

    assert "no ECG domain" in prompt
    assert "criteria go here" in prompt


# --- alignment -----------------------------------------------------------------

@pytest.fixture
def gold() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "criterion_id": ["INCL03", "INCL04", "EXCL16"],
            "testability": ["TESTABLE", "TESTABLE", "NOT_TESTABLE"],
        }
    )


def _criterion(cid: str, testability: str) -> Criterion:
    payload = criterion(criterion_id=cid, testability=testability)
    if testability != "TESTABLE":
        payload.update(
            target_domain=None, target_variable=None, operator=None,
            threshold_low=None, threshold_high=None,
        )
    return Criterion.model_validate(payload)


def test_perfect_extraction_scores_one(gold) -> None:
    extracted = [
        _criterion("INCL03", "TESTABLE"),
        _criterion("INCL04", "TESTABLE"),
        _criterion("EXCL16", "NOT_TESTABLE"),
    ]

    report = align(extracted, gold)

    assert report.extraction.precision == 1.0
    assert report.extraction.recall == 1.0
    assert report.testability_accuracy == 1.0


def test_a_missed_criterion_lowers_recall_not_precision(gold) -> None:
    report = align([_criterion("INCL03", "TESTABLE")], gold)

    assert report.extraction.precision == 1.0
    assert report.extraction.recall == pytest.approx(1 / 3)
    assert report.missed == ["EXCL16", "INCL04"]


def test_an_invented_criterion_lowers_precision(gold) -> None:
    extracted = [_criterion("INCL03", "TESTABLE"), _criterion("EXCL99", "NOT_TESTABLE")]

    report = align(extracted, gold)

    assert report.extraction.precision == 0.5
    assert report.spurious == ["EXCL99"]


def test_wrong_testability_is_counted_separately(gold) -> None:
    """Finding a criterion but misjudging it is a different failure."""
    report = align([_criterion("EXCL16", "TESTABLE")], gold)

    assert report.extraction.precision == 1.0
    assert report.testability_accuracy == 0.0
    assert report.confusion.loc["NOT_TESTABLE", "TESTABLE"] == 1


# --- protocol text -------------------------------------------------------------

def test_criteria_sections_are_found_past_the_table_of_contents() -> None:
    """The contents page lists the same headings with dot leaders."""
    document = (
        "3.4.2.1. Inclusion Criteria.................11\n"
        "3.4.2.2. Exclusion Criteria.................13\n"
        "3.4.2.1. Inclusion Criteria\n[1] Males at least 50 years of age.\n"
        "3.4.2.2. Exclusion Criteria\n[9] Prior participation.\n"
        "3.4.2.3. Violation of Criteria\nignored\n"
    )

    result = find_criteria(document)

    assert "Males at least 50" in result.inclusion
    assert "Prior participation" in result.exclusion
    assert "ignored" not in result.exclusion


def test_missing_sections_raise() -> None:
    with pytest.raises(CriteriaNotFoundError):
        find_criteria("a document with no criteria sections")
