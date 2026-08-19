"""
Per-criterion prompt configuration.

Each criterion's full prompt lives in one markdown file under `prompts/`
(system instructions, decision rules, worked examples, JSON schema),
followed by a `# USER PROMPT` marker and an input template. This file
loads each markdown file once, splits it at that marker, and wraps it
in a small class that knows how to fill in the template for one FP.

The three criteria are scored with three separate model calls rather
than one combined prompt. A colleague with pipeline-engineering
experience on a similar evaluation project recommended this: each
prompt stays focused on one decision, is easier for a mini model to
get right, and can be recalibrated on its own without touching the
other two.
"""

import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

USER_PROMPT_MARKER = "# USER PROMPT"
NOT_PROVIDED = "not provided"


def _load_halves(filename: str) -> tuple[str, str]:
    """Split a criterion prompt file into (system_instructions, user_template)."""
    text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    idx = text.index(USER_PROMPT_MARKER)
    system_part = text[:idx].rstrip()
    user_part = text[idx + len(USER_PROMPT_MARKER):].lstrip("\n")
    return system_part, user_part


def _or_not_provided(value: str | None) -> str:
    return value if value else NOT_PROVIDED


class Criterion1MarketCreationPrompt:
    """Local private-sector market creation."""

    _SYSTEM, _USER_TEMPLATE = _load_halves("criterion_1_market_creation.md")
    name = "criterion_1_market_creation"

    def __init__(
        self,
        executive_summary: str | None,
        section_rationale_and_approach: str | None,
        section_project_description: str | None,
        section_institutional_arrangements: str | None,
        fp_text: str,
    ):
        self.executive_summary = _or_not_provided(executive_summary)
        self.section_rationale_and_approach = _or_not_provided(section_rationale_and_approach)
        self.section_project_description = _or_not_provided(section_project_description)
        self.section_institutional_arrangements = _or_not_provided(section_institutional_arrangements)
        self.fp_text = fp_text

    def system_prompt(self) -> str:
        return self._SYSTEM

    def user_prompt(self) -> str:
        return self._USER_TEMPLATE.format(
            executive_summary_or_not_provided=self.executive_summary,
            section_rationale_and_approach_or_not_provided=self.section_rationale_and_approach,
            section_project_description_or_not_provided=self.section_project_description,
            section_institutional_arrangements_or_not_provided=self.section_institutional_arrangements,
            fp_text=self.fp_text,
        )


class Criterion2RiskProfilePrompt:
    """Financial instrument and risk profile."""

    _SYSTEM, _USER_TEMPLATE = _load_halves("criterion_2_risk_profile.md")
    name = "criterion_2_risk_profile"

    def __init__(
        self,
        instrument_type: str | None,
        independent_review_excerpt: str | None,
        executive_summary: str | None,
        section_total_financing: str | None,
        section_financing_structure: str | None,
        section_financial_management_procurement: str | None,
        fp_text: str,
    ):
        self.instrument_type = _or_not_provided(instrument_type)
        self.independent_review_excerpt = _or_not_provided(independent_review_excerpt)
        self.executive_summary = _or_not_provided(executive_summary)
        self.section_total_financing = _or_not_provided(section_total_financing)
        self.section_financing_structure = _or_not_provided(section_financing_structure)
        self.section_financial_management_procurement = _or_not_provided(section_financial_management_procurement)
        self.fp_text = fp_text

    def system_prompt(self) -> str:
        return self._SYSTEM

    def user_prompt(self) -> str:
        return self._USER_TEMPLATE.format(
            instrument_type_from_db_or_not_provided=self.instrument_type,
            independent_technical_review_excerpt_or_not_provided=self.independent_review_excerpt,
            executive_summary_or_not_provided=self.executive_summary,
            section_total_financing_or_not_provided=self.section_total_financing,
            section_financing_structure_or_not_provided=self.section_financing_structure,
            section_financial_management_procurement_or_not_provided=self.section_financial_management_procurement,
            fp_text=self.fp_text,
        )


class Criterion3CapitalMobilizationPrompt:
    """Verified private capital mobilization."""

    _SYSTEM, _USER_TEMPLATE = _load_halves("criterion_3_capital_mobilization.md")
    name = "criterion_3_capital_mobilization"

    def __init__(
        self,
        entity_ownership_json: str | None,
        independent_review_excerpt: str | None,
        executive_summary: str | None,
        section_total_financing: str | None,
        section_financing_structure: str | None,
        section_financial_management_procurement: str | None,
        section_expected_leverage_volume: str | None,
        section_institutional_arrangements: str | None,
        section_project_description: str | None,
        fp_text: str,
    ):
        self.entity_ownership_json = entity_ownership_json or "none matched"
        self.independent_review_excerpt = _or_not_provided(independent_review_excerpt)
        self.executive_summary = _or_not_provided(executive_summary)
        self.section_total_financing = _or_not_provided(section_total_financing)
        self.section_financing_structure = _or_not_provided(section_financing_structure)
        self.section_financial_management_procurement = _or_not_provided(section_financial_management_procurement)
        self.section_expected_leverage_volume = _or_not_provided(section_expected_leverage_volume)
        self.section_institutional_arrangements = _or_not_provided(section_institutional_arrangements)
        self.section_project_description = _or_not_provided(section_project_description)
        self.fp_text = fp_text

    def system_prompt(self) -> str:
        return self._SYSTEM

    def user_prompt(self) -> str:
        return self._USER_TEMPLATE.format(
            json_list_of_matched_entities_and_ownership_or_none_matched=self.entity_ownership_json,
            independent_technical_review_excerpt_or_not_provided=self.independent_review_excerpt,
            executive_summary_or_not_provided=self.executive_summary,
            section_total_financing_or_not_provided=self.section_total_financing,
            section_financing_structure_or_not_provided=self.section_financing_structure,
            section_financial_management_procurement_or_not_provided=self.section_financial_management_procurement,
            section_expected_leverage_volume_or_not_provided=self.section_expected_leverage_volume,
            section_institutional_arrangements_or_not_provided=self.section_institutional_arrangements,
            section_project_description_or_not_provided=self.section_project_description,
            fp_text=self.fp_text,
        )


class SynthesisQASummaryPrompt:
    """Synthesizes the three already-computed criteria results into one
    QA-ready summary + likelihood judgment. Takes no document text at
    all -- just the three small JSON verdicts -- so this call is cheap
    and doesn't need to re-read the proposal."""

    _SYSTEM, _USER_TEMPLATE = _load_halves("synthesis_qa_summary.md")
    name = "synthesis_qa_summary"

    def __init__(self, criterion_1_result: dict, criterion_2_result: dict, criterion_3_result: dict):
        self.criterion_1_result = criterion_1_result
        self.criterion_2_result = criterion_2_result
        self.criterion_3_result = criterion_3_result

    def system_prompt(self) -> str:
        return self._SYSTEM

    def user_prompt(self) -> str:
        return self._USER_TEMPLATE.format(
            criterion_1_json=json.dumps(self.criterion_1_result, indent=2),
            criterion_2_json=json.dumps(self.criterion_2_result, indent=2),
            criterion_3_json=json.dumps(self.criterion_3_result, indent=2),
        )
