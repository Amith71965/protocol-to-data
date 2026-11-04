"""Turning protocol prose into structured criteria.

The model is given two things: the criteria as the protocol words them, and an
honest inventory of what the study actually collected. Without the inventory it
cannot judge testability — it would have no way to know that no ECG domain was
published, and would label an ECG criterion testable because ECGs are normally
collected.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from p2d.criteria.provider import LLMProvider
from p2d.criteria.schema import CriteriaExtraction

SYSTEM_PROMPT = """\
You are a clinical data standards analyst. You turn protocol eligibility criteria \
into machine-checkable rules against CDISC SDTM data.

Judge each criterion only against the data inventory you are given. A criterion is:

- TESTABLE when every clause can be evaluated from the available data.
- PARTIALLY_TESTABLE when some clauses can be evaluated and others have no data \
behind them. This is the common case: say which part is unevaluable.
- NOT_TESTABLE when nothing in the available data speaks to it.

Be conservative. Labelling something testable that is not produces a rule that \
quietly checks the wrong thing, which is worse than reporting no rule at all. \
Never invent a domain or variable that is not in the inventory.

Preserve the protocol's own numbering: criterion [3] is INCL03, criterion [16] is \
EXCL16. Inclusion criteria are numbered 1 to 8, exclusion criteria 9 to 31.\
"""

DATA_INVENTORY = """\
Available SDTM domains and the variables that matter for eligibility:

- DM  demographics, one row per subject. AGE, AGEU, SEX, RACE, ETHNIC, ARM,
      RFSTDTC (reference start), RFICDTC (informed consent date).
      306 subjects, of whom 254 were randomized and 52 were screen failures.
- QS  questionnaires, item level only. Instruments present: Mini-Mental State
      (6 items, derived total MMSETOT, 0-30), Modified Hachinski Ischemic Score
      (13 items, derived total MHISTOT, 0-12), ADAS-Cog, CIBIC+, DAD, NPI-X.
      No total score is published; totals are derived by summing items.
- LB  laboratory, 43 analytes including CREAT, BILI, AST, ALT, ALP, GGT, HGB,
      WBC, PLAT, SODIUM, K, CA, HBA1C, VITB12, TSH, GLUC, CHOL, URATE.
      Carries reference ranges (LBSTNRLO, LBSTNRHI) and an indicator (LBNRIND).
      NOT present: folate, total T4, thyroid uptake, free thyroid index, syphilis.
- MH  medical history, MedDRA coded (MHDECOD, MHBODSYS across 27 body systems),
      with MHCAT including PRIMARY DIAGNOSIS, and start dates (MHSTDTC).
      254 of 1,818 records are uncoded. Seriousness is not recorded.
- CM  concomitant medications, coded (CMDECOD) with an ATC-style class (CMCLAS)
      and start day relative to reference (CMSTDY). Some records are UNCODED.
- VS  vital signs. EX exposure. DS disposition. SV visits. TI trial criteria.

NOT published for this study, so nothing can be checked against them:
- EG  no ECG domain at all.
- IE  no subject-level inclusion/exclusion domain.
- DV  no protocol deviations domain.
- No imaging data of any kind.
- No prior-study participation data.
- No menopausal status, caregiver, geography, consent-content or disability data.\
"""

USER_PROMPT = """\
Extract every eligibility criterion below into the structured schema.

{inventory}

---

{criteria_text}
"""


def build_prompt(criteria_text: str, inventory: str = DATA_INVENTORY) -> str:
    return USER_PROMPT.format(inventory=inventory, criteria_text=criteria_text)


def extraction_schema() -> dict:
    """JSON schema the model's output is constrained to."""
    return CriteriaExtraction.model_json_schema()


class ExtractionError(RuntimeError):
    """The model's response could not be parsed into the schema."""


def extract(provider: LLMProvider, criteria_text: str) -> CriteriaExtraction:
    """Run one extraction and validate the result."""
    prompt = build_prompt(criteria_text)
    schema = extraction_schema()
    raw = provider.complete(SYSTEM_PROMPT, prompt, schema)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Model response was not valid JSON: {exc}") from exc

    try:
        return CriteriaExtraction.model_validate(payload)
    except ValidationError as exc:
        raise ExtractionError(f"Model response did not match the schema: {exc}") from exc
