"""The source manifest encodes what was actually verified upstream.

These are guard rails, not network tests — nothing here makes a request. They
exist so that a careless edit to ``sources.py`` cannot quietly drop a domain or
start pulling from the unlicensed mirror.
"""

from __future__ import annotations

from p2d import sources


def test_every_artifact_is_fetched_from_the_mit_licensed_source() -> None:
    """The cdisc-org mirror has no license file, so it must never be a download target."""
    for artifact in sources.all_artifacts():
        assert "cdisc-org" not in artifact.url, artifact.key
        assert artifact.url.startswith(
            ("https://raw.githubusercontent.com/phuse-org/", "https://evs.nci.nih.gov/")
        )


def test_published_domain_set_is_complete() -> None:
    expected = {
        "dm",
        "cm",
        "ds",
        "ex",
        "lb",
        "mh",
        "qs",
        "relrec",
        "sc",
        "se",
        "sv",
        "ta",
        "te",
        "ti",
        "ts",
        "tv",
        "vs",
        "suppdm",
    }
    assert set(sources.SDTM_DOMAINS) == expected


def test_absent_domains_are_documented_with_reasons() -> None:
    """A missing domain must carry an explanation the coverage report can cite."""
    assert set(sources.ABSENT_DOMAINS) == {"eg", "ie", "dv"}
    for domain, reason in sources.ABSENT_DOMAINS.items():
        assert len(reason) > 40, domain

    # An absent domain must not also be listed as published.
    assert not set(sources.ABSENT_DOMAINS) & set(sources.SDTM_DOMAINS)


def test_artifact_keys_are_unique() -> None:
    keys = [a.key for a in sources.all_artifacts()]
    assert len(keys) == len(set(keys))


def test_artifact_filenames_are_relative_and_safe() -> None:
    for artifact in sources.all_artifacts():
        assert not artifact.filename.startswith("/")
        assert ".." not in artifact.filename


def test_trial_inclusion_criteria_domain_is_included() -> None:
    """TI carries the 31 published eligibility criteria; the project depends on it."""
    assert "ti" in sources.SDTM_DOMAINS


def test_total_download_is_in_the_expected_ballpark() -> None:
    total_mb = sources.total_download_bytes() / 1e6
    assert 100 < total_mb < 200, f"unexpected total download size: {total_mb:.1f} MB"


def test_no_single_artifact_exceeds_the_commit_threshold() -> None:
    """Nothing is committed, but a >50 MB file would also break the download budget."""
    for artifact in sources.all_artifacts():
        if artifact.expected_bytes:
            assert artifact.expected_bytes < 50_000_000, artifact.key
