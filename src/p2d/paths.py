"""Canonical filesystem layout.

Every path is derived from the repository root so the pipeline behaves the same
whether it is driven from the CLI, from pytest, or from the Streamlit app.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SOURCE_CRF_DIR = DATA_DIR / "source_crf"
SDTM_DIR = DATA_DIR / "sdtm"
GOLD_DIR = DATA_DIR / "gold"
CACHE_DIR = DATA_DIR / "llm_cache"

DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = REPO_ROOT / "reports"

#: Directories the pipeline creates on demand. ``gold`` is committed, the rest are gitignored.
DERIVED_DIRS = (RAW_DIR, SOURCE_CRF_DIR, SDTM_DIR, CACHE_DIR, REPORTS_DIR)


def ensure_dirs() -> None:
    """Create every derived directory. Safe to call repeatedly."""
    for directory in DERIVED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
