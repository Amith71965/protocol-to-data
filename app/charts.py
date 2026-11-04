"""Chart builders.

Every chart here carries a visible value label and sits beside a table view.
That is not decoration: the validated palette reports two slots below 3:1
contrast on the light surface, and the relief for that is labels or a table.

Colour is assigned by the job it does — a single hue for plain magnitude,
reserved status colours for outcome and severity, and the fixed categorical
order for treatment arms. Arms keep their colour whatever the filter selects,
so narrowing the view never repaints the survivors.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from app.palette import ARM_ORDER, OUTCOME, SEQUENTIAL, SERIES, SEVERITY, TEXT_SECONDARY

LABEL_OFFSET = 4
BAR_SIZE = 18
#: Vega drops axis labels rather than overlapping them, which silently hides a
#: category, so each row is given room instead.
ROW_HEIGHT = 44
#: Sites are many and short-labelled, so they need less room than a criterion.
SITE_ROW_HEIGHT = 30
CHART_PADDING = 40


def _base(frame: pd.DataFrame, height: int) -> alt.Chart:
    return alt.Chart(frame).properties(height=height)


def _with_labels(bars: alt.Chart, text_field: str) -> alt.LayerChart:
    """Put the value beside each bar, which is the relief the palette requires."""
    labels = bars.mark_text(
        align="left", dx=LABEL_OFFSET, baseline="middle", color=TEXT_SECONDARY, fontSize=11
    ).encode(text=alt.Text(text_field, format=","))
    return (bars + labels).configure_view(stroke=None)


def outcomes(counts: pd.DataFrame) -> alt.LayerChart:
    """How every criterion-subject pair resolved."""
    order = list(counts["outcome"])
    bars = (
        _base(counts, ROW_HEIGHT * len(counts) + CHART_PADDING)
        .mark_bar(cornerRadiusEnd=4, height=BAR_SIZE)
        .encode(
            x=alt.X("evaluations:Q", title="Evaluations", axis=alt.Axis(grid=True, tickCount=5)),
            y=alt.Y("outcome:N", title=None, sort=order),
            color=alt.Color(
                "outcome:N",
                scale=alt.Scale(domain=order, range=[OUTCOME[o] for o in order]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("outcome:N", title="Outcome"),
                alt.Tooltip("evaluations:Q", title="Evaluations", format=","),
            ],
        )
    )
    return _with_labels(bars, "evaluations:Q")


def deviations_by_criterion(counts: pd.DataFrame) -> alt.LayerChart:
    """Subjects flagged per criterion. One series, so no legend."""
    order = list(counts["criterion_id"])
    bars = (
        _base(counts, ROW_HEIGHT * len(counts) + CHART_PADDING)
        .mark_bar(cornerRadiusEnd=4, height=BAR_SIZE, color=SEQUENTIAL)
        .encode(
            x=alt.X("subjects:Q", title="Subjects flagged", axis=alt.Axis(grid=True, tickCount=5)),
            y=alt.Y("criterion_id:N", title=None, sort=order),
            tooltip=[
                alt.Tooltip("criterion_id:N", title="Criterion"),
                alt.Tooltip("subjects:Q", title="Subjects", format=","),
            ],
        )
    )
    return _with_labels(bars, "subjects:Q")


def validation_by_severity(counts: pd.DataFrame) -> alt.LayerChart:
    """Conformance findings by severity, in reserved status colours."""
    order = list(counts["severity"])
    bars = (
        _base(counts, ROW_HEIGHT * len(counts) + CHART_PADDING)
        .mark_bar(cornerRadiusEnd=4, height=BAR_SIZE)
        .encode(
            x=alt.X("issues:Q", title="Findings", axis=alt.Axis(grid=True, tickCount=5)),
            y=alt.Y("severity:N", title=None, sort=order),
            color=alt.Color(
                "severity:N",
                scale=alt.Scale(domain=order, range=[SEVERITY[s] for s in order]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("severity:N", title="Severity"),
                alt.Tooltip("issues:Q", title="Findings", format=","),
            ],
        )
    )
    return _with_labels(bars, "issues:Q")


def enrollment(frame: pd.DataFrame) -> alt.Chart:
    """Subjects per site, split by arm.

    Four series, so the legend is always shown and arm identity never rests on
    colour alone. The 2px stroke is the surface gap between stacked segments.
    """
    n_sites = frame["SITEID"].nunique()
    return (
        _base(frame, SITE_ROW_HEIGHT * n_sites + CHART_PADDING)
        .mark_bar(cornerRadiusEnd=3, stroke="#fcfcfb", strokeWidth=2)
        .encode(
            x=alt.X("subjects:Q", title="Subjects", stack="zero", axis=alt.Axis(grid=True)),
            y=alt.Y("SITEID:N", title="Site"),
            color=alt.Color(
                "ARM:N",
                title="Arm",
                scale=alt.Scale(domain=ARM_ORDER, range=SERIES),
                legend=alt.Legend(orient="bottom", columns=2),
            ),
            order=alt.Order("ARM:N"),
            tooltip=[
                alt.Tooltip("SITEID:N", title="Site"),
                alt.Tooltip("ARM:N", title="Arm"),
                alt.Tooltip("subjects:Q", title="Subjects"),
            ],
        )
        .configure_view(stroke=None)
    )


def coverage(table: pd.DataFrame) -> alt.Chart:
    """Which criteria have an executable rule, in protocol order."""
    frame = table.assign(status=table["has_rule"].map({True: "Executable rule", False: "No rule"}))
    return (
        _base(frame, 36 + 17 * len(frame))
        .mark_bar(cornerRadiusEnd=3, height=14, stroke="#fcfcfb", strokeWidth=2)
        .encode(
            x=alt.X("count():Q", title=None, axis=None),
            y=alt.Y("criterion_id:N", title=None, sort=list(frame["criterion_id"])),
            color=alt.Color(
                "status:N",
                title=None,
                scale=alt.Scale(
                    domain=["Executable rule", "No rule"], range=[SEQUENTIAL, "#d9d8d2"]
                ),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("criterion_id:N", title="Criterion"),
                alt.Tooltip("testability:N", title="Gold testability"),
                alt.Tooltip("status:N", title="Rule"),
                alt.Tooltip("deviations:Q", title="Deviations"),
                alt.Tooltip("text:N", title="Criterion"),
            ],
        )
        .configure_view(stroke=None)
    )
