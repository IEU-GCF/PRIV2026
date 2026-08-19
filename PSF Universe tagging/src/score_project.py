"""
Score one funding proposal against all three private-sector criteria.

Each criterion is a separate model call (see config.py for why), so this
module builds each of the three prompts from one evidence packet, sends
them one at a time, and assembles the three JSON replies into a single
result for that FP.

Criterion 1's `evidence_strength` is a special case: when a numeric
budget share is available, it's a fixed lookup table, not something an
LLM should be guessing at -- so the model's own answer for that field is
always overwritten here when a budget share is known.
"""

from config import (
    Criterion1MarketCreationPrompt,
    Criterion2RiskProfilePrompt,
    Criterion3CapitalMobilizationPrompt,
)
from foundry_client import ask_json, FoundryCallError


def evidence_strength_from_budget_share(budget_share_percent: float) -> str:
    """Below 30% -> weak, 30-50% -> moderate, above 50% -> strong.
    Pure arithmetic; used to be asked of the LLM, now computed here instead."""
    if budget_share_percent < 30:
        return "weak"
    if budget_share_percent <= 50:
        return "moderate"
    return "strong"


def score_criterion_1(packet: dict) -> dict:
    prompt = Criterion1MarketCreationPrompt(
        executive_summary=packet["executive_summary"],
        section_rationale_and_approach=packet["section_rationale_and_approach"],
        section_project_description=packet["section_project_description"],
        section_institutional_arrangements=packet["section_institutional_arrangements"],
        fp_text=packet["fp_text"],
    )
    result = ask_json(prompt.system_prompt(), prompt.user_prompt())

    budget_share_percent = packet.get("budget_share_percent")
    if budget_share_percent is not None:
        result["evidence_strength"] = evidence_strength_from_budget_share(budget_share_percent)
        result["evidence_strength_source"] = "computed_from_budget_share"
    else:
        result["evidence_strength_source"] = "model_qualitative_judgment"

    return result


def score_criterion_2(packet: dict) -> dict:
    prompt = Criterion2RiskProfilePrompt(
        instrument_type=packet["instrument_type"],
        independent_review_excerpt=packet["independent_review_excerpt"],
        executive_summary=packet["executive_summary"],
        section_total_financing=packet["section_total_financing"],
        section_financing_structure=packet["section_financing_structure"],
        section_financial_management_procurement=packet["section_financial_management_procurement"],
        fp_text=packet["fp_text"],
    )
    return ask_json(prompt.system_prompt(), prompt.user_prompt())


def score_criterion_3(packet: dict) -> dict:
    prompt = Criterion3CapitalMobilizationPrompt(
        entity_ownership_json=packet["entity_ownership_json"],
        independent_review_excerpt=packet["independent_review_excerpt"],
        executive_summary=packet["executive_summary"],
        section_total_financing=packet["section_total_financing"],
        section_financing_structure=packet["section_financing_structure"],
        section_financial_management_procurement=packet["section_financial_management_procurement"],
        section_expected_leverage_volume=packet["section_expected_leverage_volume"],
        section_institutional_arrangements=packet["section_institutional_arrangements"],
        section_project_description=packet["section_project_description"],
        fp_text=packet["fp_text"],
    )
    return ask_json(prompt.system_prompt(), prompt.user_prompt())


CRITERION_SCORERS = [
    ("criterion_1_market_creation", score_criterion_1),
    ("criterion_2_risk_profile", score_criterion_2),
    ("criterion_3_capital_mobilization", score_criterion_3),
]


def score_project(packet: dict) -> dict:
    """
    Run all three criteria for one FP. If one criterion's call fails, the
    other two results are still kept -- the failure is recorded in that
    criterion's slot ({"error": "..."}) instead of losing the whole row.
    """
    result = {"fp_id": packet["fp_id"]}
    for name, score_fn in CRITERION_SCORERS:
        try:
            result[name] = score_fn(packet)
        except FoundryCallError as exc:
            result[name] = {"error": str(exc)}
    return result
