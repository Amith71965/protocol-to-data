"""Build the hand-labelled gold set of eligibility criteria.

The labels are a human judgement about what the *published data* can answer,
made by reading the criterion against the data inventory. They are the
reference the LLM extraction is scored against, so they are recorded once,
committed, and not regenerated from a model.

Only the CDISC-published criterion text is stored. The sponsor's full protocol
prose is Copyright 2006 Eli Lilly and Company and is not redistributed here.

Usage:
    uv run python scripts/build_gold_set.py
"""

from __future__ import annotations

import sys

import pandas as pd

from p2d.criteria.schema import Operator, Testability
from p2d.ingest.reader import read_domain
from p2d.paths import GOLD_DIR, RAW_DIR

T, P, N = Testability.TESTABLE, Testability.PARTIALLY_TESTABLE, Testability.NOT_TESTABLE

# criterion_id -> (testability, domain, variable, operator, low, high, unit, window_days, rationale)
LABELS: dict[str, tuple] = {
    "INCL01": (
        P,
        "DM",
        "AGE",
        Operator.GE,
        50,
        None,
        "YEARS",
        None,
        "Age is in DM.AGE and checkable. Postmenopausal status is not collected anywhere, so the sex clause cannot be evaluated.",
    ),
    "INCL02": (
        P,
        "MH",
        "MHCAT",
        Operator.EXISTS,
        None,
        None,
        None,
        None,
        "MH records a PRIMARY DIAGNOSIS for every randomized subject, but the NINCDS-ADRDA determination behind it is not recorded.",
    ),
    "INCL03": (
        T,
        "QS",
        "MMSETOT",
        Operator.BETWEEN,
        10,
        23,
        None,
        None,
        "MMSE items are in QS; the total is derived by summing them and reproduces the range and mean printed in the CSR.",
    ),
    "INCL04": (
        T,
        "QS",
        "MHISTOT",
        Operator.LE,
        None,
        4,
        None,
        None,
        "All 13 Modified Hachinski items are in QS and sum to the published scale maximum.",
    ),
    "INCL05": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        365,
        "No imaging domain is published, so CNS imaging compatibility cannot be evaluated.",
    ),
    "INCL06": (
        P,
        "DM",
        "RFICDTC",
        Operator.EXISTS,
        None,
        None,
        None,
        None,
        "DM.RFICDTC shows a consent date exists; whether the document was signed by patient and caregiver is not recorded.",
    ),
    "INCL07": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "Geographic proximity to the site is not collected.",
    ),
    "INCL08": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "Caregiver reliability and willingness are not collected.",
    ),
    "EXCL09": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "Participation in prior xanomeline studies is not recorded in this study's data.",
    ),
    "EXCL10": (
        P,
        "CM",
        "CMDECOD",
        Operator.EXISTS,
        None,
        None,
        None,
        30,
        "CM is fully coded with start days, so approved Alzheimer's therapies are identifiable; 'any investigational agent' is not.",
    ),
    "EXCL11": (
        P,
        "MH",
        "MHDECOD",
        Operator.EXISTS,
        None,
        None,
        None,
        90,
        "MH carries coded terms and dates, but neither seriousness nor hospitalisation is recorded.",
    ),
    "EXCL12": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        None,
        "Nervous system conditions are identifiable by MedDRA body system; 'serious' is not defined in the data.",
    ),
    "EXCL13": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        90,
        "A DSM-IV determination is not recorded, and depression alone does not establish the criterion.",
    ),
    "EXCL14": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Psychiatric disorders are identifiable by body system; the specific illnesses the protocol lists are narrower than the SOC.",
    ),
    "EXCL15": (
        P,
        "MH",
        "MHDECOD",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Syncope would appear as a coded MH term, but 254 of 1,818 MH records are uncoded.",
    ),
    "EXCL16": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "No ECG domain is published, so no ECG finding can be evaluated. Verified absent in the data inventory.",
    ),
    "EXCL17": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Cardiac and vascular body systems are identifiable; 'serious' is not defined in the data.",
    ),
    "EXCL18": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Gastrointestinal body system is identifiable; 'serious' is not defined in the data.",
    ),
    "EXCL19": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Endocrine body system is identifiable; 'serious' is not defined in the data.",
    ),
    "EXCL20": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Respiratory body system is identifiable; the protocol's specific list is narrower than the SOC.",
    ),
    "EXCL21": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Renal and urinary body system is identifiable; 'serious' is not defined in the data.",
    ),
    "EXCL22": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Musculoskeletal body system is identifiable; 'serious' is not defined in the data.",
    ),
    "EXCL23": (
        P,
        "MH",
        "MHDECOD",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "HIV would appear as a coded MH term; absence of a term is weaker evidence than a negative test.",
    ),
    "EXCL24": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Infections body system is identifiable; the protocol's list of serious infections is narrower.",
    ),
    "EXCL25": (
        P,
        "MH",
        "MHBODSYS",
        Operator.EXISTS,
        None,
        None,
        None,
        1825,
        "Neoplasms body system is identifiable; the protocol's carve-outs are not encoded.",
    ),
    "EXCL26": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "Visual, hearing and communication disabilities are not collected.",
    ),
    "EXCL27": (
        P,
        "LB",
        "LBNRIND",
        Operator.OUT_OF_RANGE,
        None,
        None,
        None,
        None,
        "Every named analyte is in LB with a reference range, but the protocol's Lilly Reference Range III is proprietary and unavailable; the study's own range is a documented proxy.",
    ),
    "EXCL28": (
        P,
        "LB",
        "LBNRIND",
        Operator.OUT_OF_RANGE,
        None,
        None,
        None,
        None,
        "Vitamin B12 and TSH are in LB; folate, total T4, thyroid uptake and the free thyroid index are not published.",
    ),
    "EXCL29": (
        N,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "No syphilis test is among the 43 analytes in LB.",
    ),
    "EXCL30": (
        P,
        "LB",
        "HBA1C",
        Operator.GT,
        9.5,
        None,
        "%",
        None,
        "HbA1c is in LB and the 9.5% threshold is in the protocol, but the criterion applies only to insulin-dependent diabetics, which the data does not reliably identify.",
    ),
    "EXCL31": (
        P,
        "CM",
        "CMCLAS",
        Operator.EXISTS,
        None,
        None,
        None,
        30,
        "CM carries an ATC-style class and start day, but the protocol's 19-class washout table maps imperfectly and some records are UNCODED.",
    ),
}

COLUMNS = [
    "criterion_id",
    "category",
    "text",
    "testability",
    "target_domain",
    "target_variable",
    "operator",
    "threshold_low",
    "threshold_high",
    "unit",
    "window_days",
    "rationale",
]


def main() -> int:
    ti_path = RAW_DIR / "sdtm" / "ti.xpt"
    if not ti_path.exists():
        print("No data. Run scripts/download_data.py first.", file=sys.stderr)
        return 1

    ti = read_domain(RAW_DIR, "ti")
    missing = set(ti["IETESTCD"]) - set(LABELS)
    if missing:
        print(f"Unlabelled criteria: {sorted(missing)}", file=sys.stderr)
        return 1

    rows = []
    for record in ti.itertuples():
        testability, domain, variable, operator, low, high, unit, window, rationale = LABELS[
            record.IETESTCD
        ]
        rows.append(
            {
                "criterion_id": record.IETESTCD,
                "category": record.IECAT,
                "text": record.IETEST,
                "testability": testability.value,
                "target_domain": domain or "",
                "target_variable": variable or "",
                "operator": operator.value if operator else "",
                "threshold_low": low if low is not None else "",
                "threshold_high": high if high is not None else "",
                "unit": unit or "",
                "window_days": window if window is not None else "",
                "rationale": rationale,
            }
        )

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=COLUMNS).sort_values("criterion_id")
    frame.to_csv(GOLD_DIR / "criteria_gold.csv", index=False)

    counts = frame["testability"].value_counts().to_dict()
    print(f"{len(frame)} criteria -> {GOLD_DIR / 'criteria_gold.csv'}")
    for label in ("TESTABLE", "PARTIALLY_TESTABLE", "NOT_TESTABLE"):
        print(f"  {label:20s} {counts.get(label, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
