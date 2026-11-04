"""Protocol-to-Data compliance dashboard.

A view over what the pipeline produced. Nothing is computed here that the
reports do not already contain, so what the dashboard shows and what the
repository publishes cannot drift apart.

Run with:
    uv run streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Streamlit puts the script's own directory on sys.path, not the project root,
# so the sibling packages are not importable without this.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import charts  # noqa: E402
from app import data_access as data  # noqa: E402

st.set_page_config(page_title="Protocol-to-Data", page_icon="🧪", layout="wide")


@st.cache_data
def _load():
    return data.load()


def _metric_row(board: data.Dashboard) -> None:
    randomized, deviations, coverage, criteria = st.columns(4)
    randomized.metric("Randomized subjects", f"{board.n_subjects:,}")
    deviations.metric("Deviations flagged", f"{board.n_deviations:,}")
    coverage.metric(
        "Criteria with a rule",
        f"{board.n_with_rules} of {board.n_criteria}",
        help="Share of protocol criteria this pipeline can actually evaluate.",
    )
    criteria.metric("Rule coverage", f"{board.rule_coverage:.0%}")


def _deviations_tab(board: data.Dashboard) -> None:
    st.subheader("Protocol deviations")
    st.caption(
        "Subjects randomized despite not meeting an eligibility criterion. "
        "Every row names the record the conclusion was drawn from."
    )

    frame = board.deviations
    left, middle, right = st.columns(3)
    criteria = left.multiselect("Criterion", sorted(frame["criterion_id"].unique()))
    sites = middle.multiselect("Site", sorted(frame["SITEID"].astype(str).unique()))
    arms = right.multiselect("Arm", sorted(frame["ARM"].unique()))

    filtered = data.filter_deviations(frame, criteria, sites, arms)

    counts = data.deviations_by_criterion(filtered)
    if counts.empty:
        st.info("No deviations match this selection.")
        return

    st.altair_chart(charts.deviations_by_criterion(counts), use_container_width=True)
    st.caption(f"{len(filtered):,} flagged subject-criterion pairs.")
    st.dataframe(
        filtered[
            [
                "usubjid",
                "criterion_id",
                "observed",
                "SITEID",
                "ARM",
                "source_domain",
                "source_key",
                "reason",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _validation_tab(board: data.Dashboard) -> None:
    st.subheader("Conformance findings")
    st.caption(
        "Pinnacle 21 / CDISC CORE style checks over the mapped SDTM. Each finding "
        "traces to one named rule."
    )

    st.altair_chart(
        charts.validation_by_severity(data.validation_by_severity(board.validation)),
        use_container_width=True,
    )

    issues = board.validation
    if issues.empty:
        st.success("No conformance findings.")
        return

    domains = st.multiselect("Domain", sorted(issues["domain"].unique()))
    shown = issues[issues["domain"].isin(domains)] if domains else issues
    st.dataframe(
        shown[["rule_id", "severity", "domain", "variable", "observed", "message"]].head(2000),
        use_container_width=True,
        hide_index=True,
    )
    if len(shown) > 2000:
        st.caption(f"Showing the first 2,000 of {len(shown):,} findings.")


def _enrollment_tab(board: data.Dashboard) -> None:
    st.subheader("Enrollment")
    st.caption(
        "Subjects per site and arm, across all 306 in demographics. Screen failures "
        "are shown because they are part of enrollment, but no eligibility rule is "
        "evaluated against them."
    )

    frame = data.enrollment_by_site(board.demographics)
    st.altair_chart(charts.enrollment(frame), use_container_width=True)
    st.dataframe(
        frame.pivot(index="SITEID", columns="ARM", values="subjects").fillna(0).astype(int),
        use_container_width=True,
    )


def _coverage_tab(board: data.Dashboard) -> None:
    st.subheader("Criteria coverage")
    st.caption(
        "What the pipeline can and cannot check. A criterion either has a rule whose "
        "limits are stated, or no rule and a reason — never a partial check reported "
        "as a clean pass."
    )

    table = data.coverage_table(board.gold, board.evaluations)
    st.altair_chart(charts.coverage(table), use_container_width=True)

    st.markdown("**Why a criterion has no rule**")
    st.dataframe(
        table[
            [
                "criterion_id",
                "category",
                "testability",
                "has_rule",
                "deviations",
                "not_evaluable",
                "text",
                "rationale",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    st.title("Protocol-to-Data Compliance Pipeline")
    st.caption(
        "CDISC pilot study CDISCPILOT01 — xanomeline in mild to moderate Alzheimer's disease."
    )

    try:
        board = _load()
    except data.PipelineOutputMissingError as exc:
        st.error(str(exc))
        st.stop()

    _metric_row(board)
    st.altair_chart(
        charts.outcomes(data.outcome_counts(board.evaluations)), use_container_width=True
    )

    deviations, validation, enrollment, coverage = st.tabs(
        ["Deviations", "Conformance", "Enrollment", "Coverage"]
    )
    with deviations:
        _deviations_tab(board)
    with validation:
        _validation_tab(board)
    with enrollment:
        _enrollment_tab(board)
    with coverage:
        _coverage_tab(board)


main()
