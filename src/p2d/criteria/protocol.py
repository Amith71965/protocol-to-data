"""Pulling the eligibility criteria text out of the Clinical Study Report.

There is no standalone protocol document for this study. The 2006 CSR embeds
the full protocol as Appendix 1, with inclusion criteria at section 3.4.2.1 and
exclusion criteria at 3.4.2.2. That prose is what the extraction reads.

The text is held in memory and written only to gitignored working files: the
protocol is Copyright 2006 Eli Lilly and Company and is not redistributed in
this repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

INCLUSION_HEADING = re.compile(r"3\.4\.2\.1\.?\s+Inclusion\s+Criteria", re.IGNORECASE)
EXCLUSION_HEADING = re.compile(r"3\.4\.2\.2\.?\s+Exclusion\s+Criteria", re.IGNORECASE)
AFTER_EXCLUSION = re.compile(r"3\.4\.2\.3\.?\s+", re.IGNORECASE)


class CriteriaNotFoundError(RuntimeError):
    """The criteria sections could not be located in the document."""


@dataclass(frozen=True)
class ProtocolCriteriaText:
    inclusion: str
    exclusion: str

    @property
    def combined(self) -> str:
        return f"INCLUSION CRITERIA\n\n{self.inclusion}\n\nEXCLUSION CRITERIA\n\n{self.exclusion}"

    def __len__(self) -> int:
        return len(self.combined)


def extract_text(pdf_path: str | Path, max_pages: int | None = None) -> str:
    """Read the document's text, page by page."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    return "\n".join(page.extract_text() or "" for page in pages)


#: A heading in the table of contents is followed by dot leaders and a page
#: number rather than by the section itself.
TOC_LEADER = re.compile(r"^[\s.]*\.{4,}")


def _real_heading(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    """The occurrence that starts the section, not the one in the contents."""
    for match in pattern.finditer(text):
        following = text[match.end() : match.end() + 120]
        if not TOC_LEADER.match(following):
            return match
    return None


def find_criteria(text: str) -> ProtocolCriteriaText:
    """Slice the inclusion and exclusion sections out of the document text."""
    inclusion_match = _real_heading(INCLUSION_HEADING, text)
    exclusion_match = _real_heading(EXCLUSION_HEADING, text)
    if not inclusion_match or not exclusion_match:
        raise CriteriaNotFoundError(
            "Could not locate protocol sections 3.4.2.1 and 3.4.2.2 in the document."
        )
    if exclusion_match.start() <= inclusion_match.start():
        raise CriteriaNotFoundError("Exclusion section precedes the inclusion section.")

    inclusion = text[inclusion_match.end() : exclusion_match.start()]

    tail = text[exclusion_match.end() :]
    end = AFTER_EXCLUSION.search(tail)
    exclusion = tail[: end.start()] if end else tail

    return ProtocolCriteriaText(
        inclusion=_tidy(inclusion),
        exclusion=_tidy(exclusion),
    )


def _tidy(section: str) -> str:
    """Drop page furniture and collapse the ragged line breaks of PDF text."""
    lines = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Running headers and page numbers repeat on every page of the appendix.
        if re.fullmatch(r"(Page\s+)?\d+", line):
            continue
        if "Copyright" in line or re.match(r"H2Q-MC-LZZT", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def load_criteria_text(pdf_path: str | Path) -> ProtocolCriteriaText:
    """Read the CSR and return its eligibility criteria sections."""
    return find_criteria(extract_text(pdf_path))
