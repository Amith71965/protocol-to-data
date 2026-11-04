"""Download the public CDISC pilot study data.

Roughly 100 MB, fetched from the MIT-licensed PHUSE repository and from NCI EVS.
Nothing downloaded here is committed; see docs/data_manifest.json for the
checksums that pin which bytes the reports were produced from.

Usage:
    uv run python scripts/download_data.py [--force] [--refresh-manifest]
"""

from __future__ import annotations

import argparse
import sys

from p2d.ingest.download import IntegrityError, download_all
from p2d.paths import RAW_DIR, ensure_dirs
from p2d.sources import CT_LICENSE_NOTE, PHUSE_LICENSE_URL, total_download_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    parser.add_argument(
        "--refresh-manifest",
        action="store_true",
        help="rebuild the checksum manifest from what is downloaded now",
    )
    args = parser.parse_args(argv)

    ensure_dirs()
    print(f"Downloading ~{total_download_bytes() / 1e6:.0f} MB into {RAW_DIR}")
    print(f"  study data : {PHUSE_LICENSE_URL}")
    print(f"  terminology: {CT_LICENSE_NOTE}")
    print()

    try:
        results = download_all(RAW_DIR, force=args.force, refresh_manifest=args.refresh_manifest)
    except IntegrityError as exc:
        print(f"\nIntegrity check failed:\n  {exc}", file=sys.stderr)
        return 1

    fetched = sum(1 for r in results if not r.skipped)
    total = sum(r.size for r in results)
    for result in results:
        marker = "cached" if result.skipped else "fetched"
        print(f"  {marker:7s} {result.key:18s} {result.size / 1e6:8.2f} MB  {result.sha256[:12]}")

    print(f"\n{len(results)} artifacts, {fetched} newly fetched, {total / 1e6:.1f} MB total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
