"""Chart colours.

The categorical slots are used in fixed order and never cycled; a fifth series
would fold into "Other" rather than take a generated hue. Status colours are
reserved for outcome and severity and never reused as a series.

The four-slot categorical palette was validated against the light chart surface:
all checks pass, with a contrast warning on the aqua and yellow slots. That
warning is not dismissable, so every chart here ships visible value labels and
a table view beside it.
"""

from __future__ import annotations

#: Categorical slots, in fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

#: Single hue for one-series magnitude charts.
SEQUENTIAL = "#2a78d6"

#: Reserved status colours. Never used for a series.
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
    "muted": "#8a8984",
}

#: Outcome colours. NOT_EVALUABLE is deliberately neutral: it is an absence of
#: evidence, not a state of the subject.
OUTCOME = {
    "PASS": STATUS["good"],
    "DEVIATION": STATUS["critical"],
    "NOT_EVALUABLE": STATUS["muted"],
}

SEVERITY = {
    "error": STATUS["critical"],
    "warning": STATUS["warning"],
    "notice": STATUS["muted"],
}

#: Arms, in a fixed order so a filter never repaints the survivors.
ARM_ORDER = [
    "Placebo",
    "Xanomeline Low Dose",
    "Xanomeline High Dose",
    "Screen Failure",
]

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
