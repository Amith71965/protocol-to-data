"""Profile every downloaded dataset and write docs/data_inventory.md.

The inventory records what is present *and* what is absent, because later
phases cite the absences when explaining why a criterion cannot be evaluated.

Usage:
    uv run python scripts/profile_data.py
"""

from __future__ import annotations

import sys

from p2d.ingest.inventory import write_inventory
from p2d.paths import DOCS_DIR, RAW_DIR, REPORTS_DIR, ensure_dirs


def main() -> int:
    ensure_dirs()
    sdtm_dir = RAW_DIR / "sdtm"
    if not sdtm_dir.exists():
        print(
            "No data found. Run `uv run python scripts/download_data.py` first.",
            file=sys.stderr,
        )
        return 1

    summary = write_inventory(
        raw_dir=RAW_DIR,
        markdown_path=DOCS_DIR / "data_inventory.md",
        csv_path=REPORTS_DIR / "data_profile.csv",
    )
    print(f"Profiled {summary.n_domains} domains, {summary.total_rows:,} rows")
    print(f"  {DOCS_DIR / 'data_inventory.md'}")
    print(f"  {REPORTS_DIR / 'data_profile.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
