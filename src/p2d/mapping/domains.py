"""Per-domain mapping configuration and entry points.

Each configuration records what a CRF page for that domain actually holds, and
which SDTM variables the mapper is expected to rebuild from it. Where the
sponsor's value cannot be reproduced from collected data, that is stated here
rather than approximated — see ``seq_order``.
"""

from __future__ import annotations

import pandas as pd

from p2d.ingest.reader import read_domain
from p2d.mapping.findings import FindingsDomain, from_crf, test_decode_map, to_crf
from p2d.mapping.units import ConversionTable

VS = FindingsDomain(
    domain="VS",
    row_key=[
        "VISITNUM",
        "VISIT",
        "VISITDY",
        "VSDTC",
        "VSPOS",
        "VSTPT",
        "VSTPTNUM",
        "VSELTM",
        "VSTPTREF",
    ],
    test_attributes=["VSORRESU", "VSSTAT", "VSLOC"],
    presence_attributes=["VSSTAT"],
    seq_order=["VSTESTCD", "VISITNUM", "VSTPTNUM"],
)

LB = FindingsDomain(
    domain="LB",
    row_key=["VISITNUM", "VISIT", "VISITDY", "LBDTC", "LBCAT"],
    test_attributes=[
        "LBORRESU",
        "LBORNRLO",
        "LBORNRHI",
        # The laboratory supplies the standardised reference range directly;
        # converting the collected range reproduces only about 66% of it, so
        # the supplied values are carried rather than invented. The normal
        # range indicator is then derived from them, which does reconcile.
        "LBSTNRLO",
        "LBSTNRHI",
    ],
    baseline_visit="SCREENING 1",
    range_indicator="LBNRIND",
    indicator_bounds=("LBSTNRLO", "LBSTNRHI"),
    # The sponsor's LBSEQ follows an internal dataset ordering that no CRF
    # records; a visit-based sort reproduces only about 99% of it, so the
    # published value is carried rather than invented.
    seq_order=None,
    not_reproducible={
        "LBSEQ": (
            "Sponsor record sequence; follows an internal dataset ordering that "
            "no CRF records. Carried from source so traceability is preserved."
        )
    },
)

QS = FindingsDomain(
    domain="QS",
    row_key=["VISITNUM", "VISIT", "VISITDY", "QSDTC", "QSCAT", "QSSCAT"],
    test_attributes=["QSORRESU"],
    seq_order=None,
    standardisation="responses",
    not_reproducible={
        "QSSEQ": (
            "Sponsor record sequence; follows an internal dataset ordering that "
            "no CRF records. Carried from source so traceability is preserved."
        ),
        "QSDRVFL": (
            "Marks derived values, including within collected records. The "
            "sponsor's derivation rule is not recoverable from collected data."
        ),
    },
)

FINDINGS_DOMAINS: dict[str, FindingsDomain] = {"VS": VS, "LB": LB, "QS": QS}

#: Natural sort key per domain, used to line a reconstruction up against the
#: published data for comparison.
COMPARISON_KEYS: dict[str, list[str]] = {
    "VS": ["USUBJID", "VSTESTCD", "VISITNUM", "VSDTC", "VSPOS", "VSTPTNUM"],
    "LB": ["USUBJID", "LBTESTCD", "VISITNUM", "LBDTC", "LBCAT"],
    "QS": ["USUBJID", "QSTESTCD", "VISITNUM", "QSDTC", "QSCAT"],
}


def reference_dates(raw_dir) -> pd.DataFrame:
    """Subject reference start dates, for study-day derivation."""
    return read_domain(raw_dir, "dm")[["USUBJID", "RFSTDTC"]].copy()


def roundtrip(
    frame: pd.DataFrame,
    spec: FindingsDomain,
    references: pd.DataFrame,
    conversions: ConversionTable | None = None,
) -> pd.DataFrame:
    """SDTM to CRF shape and back, for verifying the mapping spec."""
    conversions = conversions or ConversionTable.load()
    return from_crf(
        to_crf(frame, spec),
        spec,
        decode=test_decode_map(frame, spec),
        reference_dates=references,
        conversions=conversions,
    )


def attach_carried(
    original: pd.DataFrame,
    rebuilt: pd.DataFrame,
    spec: FindingsDomain,
    key: list[str],
) -> pd.DataFrame:
    """Re-attach the variables a CRF cannot determine.

    "Carried from source" has to mean exactly that: the published value is
    joined back onto the reconstruction. Without this the mapped dataset would
    simply be missing its record sequence, and traceability back to the
    published data would break.

    The two frames hold the same records, so they are aligned by sorting on the
    domain's natural key rather than merged, which would multiply rows wherever
    the key repeats.
    """
    carried = [c for c in spec.not_reproducible if c in original.columns]
    if not carried:
        return rebuilt
    if len(original) != len(rebuilt):
        raise ValueError(
            f"{spec.domain}: cannot carry {carried} — "
            f"{len(original)} published records against {len(rebuilt)} rebuilt."
        )

    left = original.sort_values(key).reset_index(drop=True)
    right = rebuilt.sort_values(key).reset_index(drop=True)
    for column in carried:
        right[column] = left[column].to_numpy()
    return right
