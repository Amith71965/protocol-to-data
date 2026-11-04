"""Build the SDTM layer from the derived CRF source layer, and prove the mapping.

Writes:
  data/source_crf/*.csv   the CRF-shaped source layer (derived fixture)
  data/sdtm/*.parquet     the mapped SDTM datasets
  docs/mapping_spec.{csv,md}  the specification, with measured match rates
  reports/roundtrip.csv   per-variable reconstruction results

Usage:
    uv run python scripts/build_sdtm.py
"""

from __future__ import annotations

import sys

import pandas as pd

from p2d.ingest.reader import read_domain
from p2d.mapping import demographics, spec
from p2d.mapping.domains import (
    COMPARISON_KEYS,
    FINDINGS_DOMAINS,
    attach_carried,
    reference_dates,
    roundtrip,
)
from p2d.mapping.findings import split_collected, to_crf
from p2d.mapping.verify import compare
from p2d.paths import DOCS_DIR, RAW_DIR, REPORTS_DIR, SDTM_DIR, SOURCE_CRF_DIR, ensure_dirs

PROVENANCE = (
    "# DERIVED FIXTURE - not trial data. Reconstructed from published CDISC pilot SDTM "
    "to exercise the mapping; see docs/mapping_spec.md.\n"
)


def _write_crf(page: pd.DataFrame, name: str) -> None:
    path = SOURCE_CRF_DIR / f"{name}.csv"
    with path.open("w", newline="") as handle:
        handle.write(PROVENANCE)
        page.to_csv(handle, index=False)


def main() -> int:
    ensure_dirs()
    if not (RAW_DIR / "sdtm" / "dm.xpt").exists():
        print("No data. Run scripts/download_data.py first.", file=sys.stderr)
        return 1

    SOURCE_CRF_DIR.mkdir(parents=True, exist_ok=True)
    SDTM_DIR.mkdir(parents=True, exist_ok=True)

    reports, rows = [], []

    dm = read_domain(RAW_DIR, "dm")
    _write_crf(demographics.to_crf(dm), "demographics")
    rebuilt_dm = demographics.roundtrip(dm)
    rebuilt_dm.to_parquet(SDTM_DIR / "dm.parquet", index=False)
    dm_report = compare(dm, rebuilt_dm, ["USUBJID"], "DM")
    reports.append(dm_report)
    rows += spec.build_rows(
        None, dm_report, collected=demographics.COLLECTED[2:], derived=demographics.DERIVED
    )
    print(dm_report.summary())

    references = reference_dates(RAW_DIR)
    for name, domain_spec in FINDINGS_DOMAINS.items():
        frame = read_domain(RAW_DIR, name.lower())
        split = split_collected(frame, domain_spec)

        _write_crf(to_crf(frame, domain_spec), name.lower())
        rebuilt = roundtrip(frame, domain_spec, references)
        rebuilt = attach_carried(split.collected, rebuilt, domain_spec, COMPARISON_KEYS[name])
        rebuilt.to_parquet(SDTM_DIR / f"{name.lower()}.parquet", index=False)

        report = compare(
            split.collected,
            rebuilt,
            COMPARISON_KEYS[name],
            name,
            ignore=list(domain_spec.not_reproducible),
        )
        reports.append(report)

        derived = [
            c
            for c in rebuilt.columns
            if any(
                c.endswith(s)
                for s in (
                    "STUDYID",
                    "DOMAIN",
                    "USUBJID",
                    "SEQ",
                    "DY",
                    "BLFL",
                    "TEST",
                    "STRESN",
                    "STRESU",
                    "STRESC",
                    "NRIND",
                )
            )
            and c != domain_spec.testcd
        ]
        collected = [c for c in rebuilt.columns if c not in derived]
        rows += spec.build_rows(domain_spec, report, collected=collected, derived=derived)

        extra = f"  [derived-only records excluded: {len(split.sponsor_derived):,}]"
        print(report.summary() + (extra if len(split.sponsor_derived) else ""))

    frame = spec.to_frame(rows)
    spec.write(frame, reports, DOCS_DIR)

    pd.DataFrame(
        [
            {
                "domain": report.domain,
                "variable": r.variable,
                "mismatches": r.mismatches,
                "total": r.total,
                "match_rate": r.match_rate,
            }
            for report in reports
            for r in report.results
        ]
    ).to_csv(REPORTS_DIR / "roundtrip.csv", index=False)

    exact = sum(1 for r in reports if r.exact)
    print(f"\n{exact} of {len(reports)} domains reconstruct exactly")
    print(f"  {DOCS_DIR / 'mapping_spec.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
