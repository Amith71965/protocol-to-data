"""Fetching the public study data, with integrity checks.

Roughly 100 MB of SDTM is downloaded, so nothing is committed. To keep results
reproducible anyway, the first successful download records a SHA-256 per
artifact in a committed manifest; every later run verifies against it. A
mismatch is an error rather than a warning — silently analysing different bytes
than the ones a report was written from is exactly the failure this project
exists to catch.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from p2d.sources import Artifact, all_artifacts

#: Committed record of which bytes the reports were produced from.
MANIFEST_PATH = Path(__file__).resolve().parents[3] / "docs" / "data_manifest.json"

_CHUNK = 1 << 20


class IntegrityError(RuntimeError):
    """A downloaded artifact does not match its recorded checksum or size."""


@dataclass(frozen=True)
class DownloadResult:
    key: str
    path: Path
    sha256: str
    size: int
    skipped: bool


def sha256_file(path: str | Path) -> str:
    """SHA-256 of a file, streamed so large datasets stay off the heap."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | Path = MANIFEST_PATH) -> dict[str, dict[str, object]]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def save_manifest(manifest: dict[str, dict[str, object]], path: str | Path = MANIFEST_PATH) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def verify(artifact: Artifact, path: Path, manifest: dict[str, dict[str, object]]) -> str:
    """Check a downloaded file against the manifest and its expected size.

    Returns the file's SHA-256.

    Raises:
        IntegrityError: if the size or checksum disagrees with what is recorded.
    """
    size = path.stat().st_size
    if artifact.expected_bytes is not None and size != artifact.expected_bytes:
        raise IntegrityError(
            f"{artifact.key}: expected {artifact.expected_bytes} bytes upstream, got {size}"
        )

    digest = sha256_file(path)
    recorded = manifest.get(artifact.key)
    if recorded is not None and recorded.get("sha256") != digest:
        raise IntegrityError(
            f"{artifact.key}: checksum mismatch. "
            f"Recorded {recorded.get('sha256')}, downloaded {digest}. "
            "Upstream data changed; re-run with --refresh-manifest only after "
            "confirming the change is intended."
        )
    return digest


def download(
    artifacts: Iterable[Artifact],
    dest_root: str | Path,
    *,
    manifest: dict[str, dict[str, object]] | None = None,
    force: bool = False,
    client: httpx.Client | None = None,
) -> Iterator[DownloadResult]:
    """Download artifacts into ``dest_root``, yielding one result each.

    Existing files whose size already matches are not re-fetched unless
    ``force`` is set, but they are still verified.
    """
    root = Path(dest_root)
    manifest = {} if manifest is None else manifest
    owns_client = client is None
    client = client or httpx.Client(timeout=120.0, follow_redirects=True)

    try:
        for artifact in artifacts:
            target = root / artifact.filename
            target.parent.mkdir(parents=True, exist_ok=True)

            already_sized = (
                target.exists()
                and artifact.expected_bytes is not None
                and target.stat().st_size == artifact.expected_bytes
            )
            skipped = already_sized and not force
            if not skipped:
                with client.stream("GET", artifact.url) as response:
                    response.raise_for_status()
                    with target.open("wb") as handle:
                        for chunk in response.iter_bytes(_CHUNK):
                            handle.write(chunk)

            digest = verify(artifact, target, manifest)
            yield DownloadResult(
                key=artifact.key,
                path=target,
                sha256=digest,
                size=target.stat().st_size,
                skipped=skipped,
            )
    finally:
        if owns_client:
            client.close()


def download_all(
    dest_root: str | Path,
    *,
    force: bool = False,
    refresh_manifest: bool = False,
) -> list[DownloadResult]:
    """Fetch every artifact and reconcile the manifest."""
    manifest = {} if refresh_manifest else load_manifest()
    results = list(download(all_artifacts(), dest_root, manifest=manifest, force=force))

    updated = dict(manifest)
    for result in results:
        updated[result.key] = {"sha256": result.sha256, "bytes": result.size}
    if updated != manifest:
        save_manifest(updated)

    return results
