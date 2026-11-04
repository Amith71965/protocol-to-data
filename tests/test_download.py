"""Integrity checking of downloaded artifacts."""

from __future__ import annotations

import hashlib

import pytest

from p2d.ingest.download import (
    IntegrityError,
    load_manifest,
    save_manifest,
    sha256_file,
    verify,
)
from p2d.sources import Artifact


@pytest.fixture
def artifact_file(tmp_path):
    path = tmp_path / "dm.xpt"
    payload = b"fake xport bytes"
    path.write_bytes(payload)
    return path, payload


def test_sha256_matches_hashlib(artifact_file) -> None:
    path, payload = artifact_file

    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_verify_passes_when_size_and_checksum_agree(artifact_file) -> None:
    path, payload = artifact_file
    digest = hashlib.sha256(payload).hexdigest()
    artifact = Artifact("sdtm.dm", "https://example.test/dm.xpt", "dm.xpt", "DM", len(payload))

    assert verify(artifact, path, {"sdtm.dm": {"sha256": digest}}) == digest


def test_verify_rejects_a_size_mismatch(artifact_file) -> None:
    """A truncated or replaced upstream file must not be analysed silently."""
    path, payload = artifact_file
    artifact = Artifact("sdtm.dm", "https://example.test/dm.xpt", "dm.xpt", "DM", len(payload) + 1)

    with pytest.raises(IntegrityError, match="expected"):
        verify(artifact, path, {})


def test_verify_rejects_a_checksum_mismatch(artifact_file) -> None:
    """Same size, different bytes — the case a size check alone would miss."""
    path, payload = artifact_file
    artifact = Artifact("sdtm.dm", "https://example.test/dm.xpt", "dm.xpt", "DM", len(payload))
    wrong = hashlib.sha256(b"different bytes!").hexdigest()

    with pytest.raises(IntegrityError, match="checksum mismatch"):
        verify(artifact, path, {"sdtm.dm": {"sha256": wrong}})


def test_verify_records_a_new_artifact_without_failing(artifact_file) -> None:
    """A first download has nothing to compare against yet."""
    path, payload = artifact_file
    artifact = Artifact("sdtm.dm", "https://example.test/dm.xpt", "dm.xpt", "DM", len(payload))

    assert verify(artifact, path, {}) == hashlib.sha256(payload).hexdigest()


def test_verify_skips_size_check_when_none_expected(artifact_file) -> None:
    path, payload = artifact_file
    artifact = Artifact("ct", "https://example.test/ct.txt", "ct.txt", "CT", None)

    assert verify(artifact, path, {}) == hashlib.sha256(payload).hexdigest()


def test_manifest_round_trips(tmp_path) -> None:
    path = tmp_path / "nested" / "manifest.json"
    manifest = {"sdtm.dm": {"sha256": "abc", "bytes": 10}}

    save_manifest(manifest, path)

    assert load_manifest(path) == manifest


def test_missing_manifest_reads_as_empty(tmp_path) -> None:
    assert load_manifest(tmp_path / "absent.json") == {}
