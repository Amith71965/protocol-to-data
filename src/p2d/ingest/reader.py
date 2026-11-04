"""Reading SAS XPORT (``.xpt``) transport files into tidy DataFrames.

The published pilot datasets are SAS V5 transport files. ``pandas.read_sas``
handles the format natively, but two quirks have to be dealt with before the
data is safe to compute on.

**Denormal zeros.** IBM hexadecimal floating point has representations that
decode to a denormal value rather than a clean ``0.0``. In these datasets a
stored zero comes back as ``5.397605e-79``. Summing is unaffected, but any
comparison, rounding or null test silently does the wrong thing — a questionnaire
item scored zero would compare as greater than zero. Every float column is
therefore snapped to exact zero below :data:`DENORMAL_THRESHOLD`.

**Byte strings and padding.** Character columns decode with trailing spaces,
which breaks equality against controlled terminology. They are stripped, and
empty strings are left as empty rather than coerced to NaN so that "collected
but blank" stays distinguishable from "not collected".
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

#: Any float whose magnitude falls below this is a decoded zero, not a real
#: measurement. The smallest legitimate value anywhere in these datasets is
#: many orders of magnitude larger (lab results, scores, days).
DENORMAL_THRESHOLD = 1e-60


def normalise_denormal_zeros(frame: pd.DataFrame) -> pd.DataFrame:
    """Snap decoded denormal floats to exact zero, in place-safe fashion.

    Returns a new frame; the input is not modified.
    """
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_float_dtype(out[column]):
            values = out[column]
            tiny = values.abs() < DENORMAL_THRESHOLD
            if tiny.any():
                out[column] = values.where(~tiny, 0.0)
    return out


def is_textual(series: pd.Series) -> bool:
    """True for character data under either pandas string representation.

    pandas 3 gives character columns a dedicated ``str`` dtype, for which
    ``is_object_dtype`` is False. Checking only for object dtype silently
    skips every character column.
    """
    return pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)


def strip_character_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Trim the fixed-width padding off character columns."""
    out = frame.copy()
    for column in out.columns:
        if is_textual(out[column]):
            out[column] = out[column].map(lambda v: v.strip() if isinstance(v, str) else v)
    return out


def read_xpt(path: str | Path) -> pd.DataFrame:
    """Read an XPORT file and apply both corrections.

    Args:
        path: Location of the ``.xpt`` file.

    Returns:
        A DataFrame with padding stripped and denormal zeros snapped to ``0.0``.
    """
    frame = pd.read_sas(Path(path), format="xport", encoding="latin-1")
    return normalise_denormal_zeros(strip_character_columns(frame))


def read_domain(raw_dir: str | Path, domain: str) -> pd.DataFrame:
    """Read one SDTM domain from a populated ``data/raw`` directory."""
    return read_xpt(Path(raw_dir) / "sdtm" / f"{domain.lower()}.xpt")
