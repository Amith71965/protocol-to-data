"""Verified provenance for every external artifact this project consumes.

Each URL below was confirmed to return HTTP 200 during planning. Everything is
pulled from ``phuse-org/phuse-scripts`` because that repository is **MIT
licensed**; the parallel ``cdisc-org/sdtm-adam-pilot-project`` repository hosts
the same material but carries *no license file*, so it is referenced in
documentation only and never downloaded.

Nothing here is committed to git — the SDTM datasets total roughly 100 MB. Use
``scripts/download_data.py`` to populate ``data/raw/``.
"""

from __future__ import annotations

from dataclasses import dataclass

STUDY_ID = "CDISCPILOT01"

#: The sponsor protocol behind the public pilot data. Useful because the pilot
#: documentation refers to protocol attachments by this identifier.
PROTOCOL_ID = "H2Q-MC-LZZT"
PROTOCOL_TITLE = (
    "Safety and Efficacy of the Xanomeline Transdermal Therapeutic System (TTS) "
    "in Patients with Mild to Moderate Alzheimer's Disease"
)

PHUSE_LICENSE = "MIT"
PHUSE_LICENSE_URL = "https://github.com/phuse-org/phuse-scripts/blob/master/LICENSE.md"
PHUSE_RAW = "https://raw.githubusercontent.com/phuse-org/phuse-scripts/master"

SDTM_BASE = f"{PHUSE_RAW}/data/sdtm/cdiscpilot01"
DOCS_BASE = f"{PHUSE_RAW}/data/adam/TDF_ADaM_v1.0/cdiscpilot_docs"

#: SDTM domains published for this study, with the byte sizes observed upstream.
#: Confirmed by HTTP HEAD against every entry. There is deliberately no ``ie``
#: (subject-level criteria-not-met) or ``dv`` (protocol deviations) domain — see
#: ``docs/limitations.md``; their absence is why this project has no deviation
#: ground truth to score against.
SDTM_DOMAINS: dict[str, int] = {
    "dm": 110_800,
    "cm": 3_758_720,
    "ds": 146_800,
    "ex": 87_120,
    "lb": 34_262_560,
    "mh": 1_586_960,
    "qs": 33_849_760,
    "relrec": 110_160,
    "sc": 30_160,
    "se": 493_120,
    "sv": 286_560,
    "ta": 10_560,
    "te": 8_880,
    "ti": 9_200,
    "ts": 22_160,
    "tv": 13_520,
    "vs": 24_014_960,
    "suppdm": 1_056_720,
}

#: Domains referenced by the eligibility rules but **not published** for this
#: study. Kept explicit so the coverage report can cite a reason rather than
#: silently dropping a criterion.
ABSENT_DOMAINS: dict[str, str] = {
    "eg": "No ECG domain is published, so EXCL16 (ECG findings) cannot be evaluated.",
    "ie": "No subject-level inclusion/exclusion domain, so there is no criteria-not-met ground truth.",
    "dv": "No protocol-deviations domain, so detected deviations cannot be scored against truth.",
}


@dataclass(frozen=True)
class Artifact:
    """A single downloadable file."""

    key: str
    url: str
    filename: str
    description: str
    expected_bytes: int | None = None


def sdtm_artifacts() -> list[Artifact]:
    """One artifact per published SDTM domain."""
    return [
        Artifact(
            key=f"sdtm.{domain}",
            url=f"{SDTM_BASE}/{domain}.xpt",
            filename=f"sdtm/{domain}.xpt",
            description=f"SDTM {domain.upper()} domain (SAS XPORT)",
            expected_bytes=size,
        )
        for domain, size in SDTM_DOMAINS.items()
    ]


#: Study metadata and source documents.
DOC_ARTIFACTS: list[Artifact] = [
    Artifact(
        key="define.xml",
        url=f"{SDTM_BASE}/define.xml",
        filename="metadata/define.xml",
        description="SDTM define.xml — variable metadata, codelists and CRF Origin annotations",
        expected_bytes=262_416,
    ),
    Artifact(
        key="csr",
        url=f"{DOCS_BASE}/cdiscpilot01.pdf",
        filename="docs/cdiscpilot01.pdf",
        description=(
            "Final Clinical Study Report. Appendix 1 embeds the full protocol "
            "(eligibility criteria at sections 3.4.2.1 and 3.4.2.2); Appendix 9 embeds the SAP. "
            "Protocol text is Copyright 2006 Eli Lilly and Company and is NOT redistributed "
            "in this repository."
        ),
        expected_bytes=5_985_424,
    ),
    Artifact(
        key="dataguide",
        url=f"{DOCS_BASE}/dataguide.pdf",
        filename="docs/dataguide.pdf",
        description="Pilot data guide",
        expected_bytes=92_216,
    ),
]

#: CDISC Controlled Terminology, published by NCI EVS. Freely available with no
#: licensing restrictions. Release observed: 2026-09-25.
NCI_CT_ARTIFACTS: list[Artifact] = [
    Artifact(
        key="ct.sdtm.txt",
        url="https://evs.nci.nih.gov/ftp1/CDISC/SDTM/SDTM%20Terminology.txt",
        filename="ct/sdtm_terminology.txt",
        description="CDISC SDTM Controlled Terminology, tab-delimited (NCI EVS, 2026-09-25)",
        expected_bytes=13_848_826,
    ),
]

CT_LICENSE_NOTE = (
    "CDISC Terminology is freely available without licensing restrictions via NCI EVS: "
    "https://www.cancer.gov/research/resources/terminology/cdisc"
)


def all_artifacts() -> list[Artifact]:
    """Every file ``scripts/download_data.py`` fetches."""
    return [*sdtm_artifacts(), *DOC_ARTIFACTS, *NCI_CT_ARTIFACTS]


def total_download_bytes() -> int:
    """Approximate total download size, for the script's progress reporting."""
    return sum(a.expected_bytes or 0 for a in all_artifacts())
