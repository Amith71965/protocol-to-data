"""Run conformance validation over the mapped SDTM layer.

Usage:
    uv run python scripts/validate_sdtm.py
"""

from __future__ import annotations

import sys

from p2d.paths import DOCS_DIR, RAW_DIR, REPORTS_DIR, SDTM_DIR, ensure_dirs
from p2d.validate import report
from p2d.validate.runner import counts_by_severity, load_sdtm, summarise, validate
from p2d.validate.terminology import Terminology


def main() -> int:
    ensure_dirs()
    if not any(SDTM_DIR.glob("*.parquet")):
        print("No mapped SDTM. Run scripts/build_sdtm.py first.", file=sys.stderr)
        return 1

    terminology_path = RAW_DIR / "ct" / "sdtm_terminology.txt"
    terminology = Terminology.load(terminology_path) if terminology_path.exists() else None
    if terminology is None:
        print("Controlled terminology not downloaded; SD0006 will not run.", file=sys.stderr)

    domains = load_sdtm(SDTM_DIR)
    issues = validate(domains, terminology)

    summary = summarise(issues)
    if not summary.empty:
        print(summary.to_string(index=False))
    counts = counts_by_severity(issues)
    print(
        f"\n{counts['error']} errors, {counts['warning']} warnings, "
        f"{counts['notice']} notices across {len(domains)} domains"
    )

    report.write(issues, DOCS_DIR, REPORTS_DIR)
    print(f"  {DOCS_DIR / 'validation_rules.md'}")
    print(f"  {REPORTS_DIR / 'validation_issues.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
