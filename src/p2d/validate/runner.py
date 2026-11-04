"""Running the conformance rules across the mapped SDTM layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from p2d.validate.issues import Issue, Severity, to_frame
from p2d.validate.rules import ALL_RULES, Dataset, run_all
from p2d.validate.terminology import Terminology


def load_sdtm(sdtm_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Read every mapped domain written by scripts/build_sdtm.py."""
    directory = Path(sdtm_dir)
    return {
        path.stem.upper(): pd.read_parquet(path) for path in sorted(directory.glob("*.parquet"))
    }


def validate(
    domains: dict[str, pd.DataFrame], terminology: Terminology | None = None
) -> list[Issue]:
    """Validate every domain, giving each one DM for cross-domain checks."""
    demographics = domains.get("DM")
    issues: list[Issue] = []
    for name, frame in domains.items():
        dataset = Dataset(
            domain=name,
            frame=frame,
            demographics=None if name == "DM" else demographics,
            terminology=terminology,
        )
        issues.extend(run_all(dataset))
    return issues


def summarise(issues: list[Issue]) -> pd.DataFrame:
    """Issue counts by rule and severity."""
    frame = to_frame(issues)
    if frame.empty:
        return pd.DataFrame(columns=["rule_id", "severity", "description", "issues", "domains"])

    grouped = (
        frame.groupby(["rule_id", "severity"])
        .agg(issues=("rule_id", "size"), domains=("domain", lambda s: ", ".join(sorted(set(s)))))
        .reset_index()
    )
    grouped["description"] = grouped["rule_id"].map(
        {rule_id: description for rule_id, (_, description) in ALL_RULES.items()}
    )
    return grouped[["rule_id", "severity", "description", "issues", "domains"]].sort_values(
        ["severity", "rule_id"]
    )


def counts_by_severity(issues: list[Issue]) -> dict[str, int]:
    return {
        severity.value: sum(1 for i in issues if i.severity is severity) for severity in Severity
    }
