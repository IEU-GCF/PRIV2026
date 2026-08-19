"""
Convert data/outputs/pilot_results.jsonl into an Excel workbook for manual
review:
  - "Criteria" sheet: a plain-language reference for what each criterion
    captures (static content, not derived from pilot data).
  - "Summary" sheet: one row per FP -- its GCF-tagged sector, then the
    `qa_summary` block added by synthesize_summary.py (an overall
    likelihood judgment, a plain-language summary, named entities, and
    QA flags -- all reasoned from the actual evidence, not a fixed
    lookup table), then each criterion's detailed fields.
  - "Entities Unmatched" sheet: Criterion 3's unmatched-counterparty list
    (a list field that doesn't flatten into one row).

Run `python src/synthesize_summary.py` before this, or the headline
columns will just say "not yet synthesized".

The .jsonl file stays the source of truth (still written by run_pilot.py
and synthesize_summary.py) -- this is just a more reviewable view on top
of it, rebuilt from scratch every time this script runs. Re-run any time
to refresh. Manual edits made directly in a generated sheet (Summary,
Entities Unmatched) will be overwritten on the next run; the Criteria
sheet is safe because it's defined in code, below.

Usage:
    python src/export_to_excel.py
"""

from pathlib import Path
import json

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CRITERION_KEYS = {
    "c1": "criterion_1_market_creation",
    "c2": "criterion_2_risk_profile",
    "c3": "criterion_3_capital_mobilization",
}

# Sector used to be hardcoded here as a dict disconnected from the actual
# pipeline JSON -- GCF's ground-truth Public/Private tag now flows through
# fp_metadata.csv -> build_evidence_packet.py -> run_pilot.py's own output
# row (row["sector"]), so this sheet reads it from `rows` like every other
# field instead of keeping a second, easily-stale copy of the same fact.

# (prefix, field) -- the detailed per-criterion columns, unchanged from before.
SUMMARY_FIELDS = [
    ("c1", "status"),
    ("c1", "engagement_level"),
    ("c1", "evidence_strength"),
    ("c1", "evidence_strength_source"),
    ("c1", "status_supported_by_quote"),
    ("c1", "location"),
    ("c1", "quote"),
    ("c1", "justification"),
    ("c2", "status"),
    ("c2", "evidence_strength"),
    ("c2", "status_supported_by_quote"),
    ("c2", "location"),
    ("c2", "quote"),
    ("c2", "justification"),
    ("c3", "status"),
    ("c3", "mechanism_class"),
    ("c3", "counterparty_name"),
    ("c3", "counterparty_ownership"),
    ("c3", "evidence_strength"),
    ("c3", "status_supported_by_quote"),
    ("c3", "location"),
    ("c3", "quote"),
    ("c3", "justification"),
]

WIDE_FIELDS = {"quote", "justification"}

CRITERIA_SHEET_ROWS = [
    ("Criteria", "Pillar", "Question"),
    (1, " Market creation",
     "does the project intentionally build up a local private actor (an MSME, local bank, "
     "climate-tech firm, etc.) as its own named component or output, not just a passing mention."),
    (2, "Risk profile",
     "does GCF's own financing carry a private-sector-like function (loan, equity, guarantee, "
     "first-loss) rather than being a plain grant with no repayment or risk-sharing role."),
    (3, "Verified mobilization",
     'is there a named mechanism (co-financing, guarantee, etc.) paired with a counterparty '
     'confirmed private against an ownership list. This is the "proof" criterion, deliberately '
     "strict, because an earlier review (Aiko's) found a looser version of this rule marked 100% "
     'of sampled projects as "met" just for naming any co-financier, public or private'),
]


def _value(row: dict, prefix: str, field: str):
    criterion = row.get(CRITERION_KEYS[prefix], {}) or {}
    if "error" in criterion:
        if field == "status":
            return "ERROR"
        if field in WIDE_FIELDS:
            return criterion["error"][:300]
        return ""
    return criterion.get(field, "")


def load_rows(jsonl_path: Path) -> list[dict]:
    rows = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


NOT_YET_SYNTHESIZED = {
    "overall_likelihood": "not yet synthesized",
    "likelihood_score": None,
    "summary": "Run `python src/synthesize_summary.py` to generate this.",
    "key_entities": [],
    "qa_flags": [],
}


def build_criteria_sheet(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Criteria"
    for row in CRITERIA_SHEET_ROWS:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 100


def build_summary_sheet(wb: Workbook, rows: list[dict]) -> None:
    ws = wb.create_sheet("Summary")

    headline_headers = [
        "fp_id", "Sector", "overall_likelihood", "likelihood_score", "summary", "key_entities", "qa_flags",
    ]
    detail_headers = [f"{prefix}_{field}" for prefix, field in SUMMARY_FIELDS]
    headers = headline_headers + detail_headers
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in rows:
        qa = row.get("qa_summary", NOT_YET_SYNTHESIZED)
        headline_values = [
            row["fp_id"],
            row.get("sector") or "Unknown",
            qa.get("overall_likelihood", ""),
            qa.get("likelihood_score"),
            qa.get("summary", ""),
            "; ".join(qa.get("key_entities") or []),
            "; ".join(qa.get("qa_flags") or []),
        ]
        detail_values = [_value(row, prefix, field) for prefix, field in SUMMARY_FIELDS]
        ws.append(headline_values + detail_values)

    ws.freeze_panes = "C2"
    for i, header in enumerate(headers, start=1):
        if header in ("summary", "key_entities", "qa_flags"):
            width = 70
        elif header.endswith(("quote", "justification")):
            width = 60
        else:
            width = 20
        ws.column_dimensions[get_column_letter(i)].width = width


def build_entities_unmatched_sheet(wb: Workbook, rows: list[dict]) -> None:
    ws = wb.create_sheet("Entities Unmatched")
    headers = ["fp_id", "entity_name", "role", "proposed_ownership", "rationale"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in rows:
        c3 = row.get(CRITERION_KEYS["c3"], {}) or {}
        for entity in c3.get("entities_unmatched") or []:
            ws.append([
                row["fp_id"],
                entity.get("entity_name", ""),
                entity.get("role", ""),
                entity.get("proposed_ownership", ""),
                entity.get("rationale", ""),
            ])

    for i, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(i)].width = 40 if header == "rationale" else 20


def main():
    jsonl_path = PROJECT_ROOT / "data" / "outputs" / "pilot_results.jsonl"
    xlsx_path = PROJECT_ROOT / "data" / "outputs" / "pilot_results.xlsx"

    if not jsonl_path.exists():
        print(f"{jsonl_path} not found -- run `python src/run_pilot.py` first.")
        return

    rows = load_rows(jsonl_path)
    if not rows:
        print(f"{jsonl_path} is empty.")
        return

    wb = Workbook()
    build_criteria_sheet(wb)
    build_summary_sheet(wb, rows)
    build_entities_unmatched_sheet(wb, rows)
    wb.save(xlsx_path)
    print(f"Wrote {len(rows)} row(s) to {xlsx_path}")


if __name__ == "__main__":
    main()
