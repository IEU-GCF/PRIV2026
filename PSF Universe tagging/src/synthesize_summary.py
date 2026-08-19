"""
Add a QA-ready summary + likelihood judgment to each row already in
data/outputs/pilot_results.jsonl, by sending the three already-computed
criterion results (not the original proposal text) to the model and
asking it to synthesize them, weighing the actual semantic strength of
the evidence rather than a fixed lookup table on the met/not_met/unclear
labels alone.

This does not touch data/raw_pdfs/ or data/extracted_text/ at all -- it
only reads the small JSON your three criteria already produced, so this
extra call per FP is cheap and fast. Run this after run_pilot.py and
before export_to_excel.py.

Usage:
    python src/synthesize_summary.py
    python src/synthesize_summary.py --force   # redo rows that already have a qa_summary
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SynthesisQASummaryPrompt
from foundry_client import ask_json, FoundryCallError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRITERION_KEYS = [
    "criterion_1_market_creation",
    "criterion_2_risk_profile",
    "criterion_3_capital_mobilization",
]


def _insufficient_evidence_summary(reason: str) -> dict:
    return {
        "overall_likelihood": "insufficient_evidence",
        "likelihood_score": None,
        "summary": reason,
        "key_entities": [],
        "qa_flags": ["rerun needed"],
    }


def synthesize_row(row: dict) -> dict:
    if any("error" in row.get(key, {}) for key in CRITERION_KEYS):
        return _insufficient_evidence_summary(
            "One or more criteria failed to score (model/API error) for this FP -- "
            "re-run run_pilot.py for it before trusting any summary."
        )

    prompt = SynthesisQASummaryPrompt(
        criterion_1_result=row[CRITERION_KEYS[0]],
        criterion_2_result=row[CRITERION_KEYS[1]],
        criterion_3_result=row[CRITERION_KEYS[2]],
    )
    return ask_json(prompt.system_prompt(), prompt.user_prompt())


def main():
    parser = argparse.ArgumentParser(
        description="Synthesize a QA summary + likelihood judgment per FP from already-scored criteria."
    )
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data", help="Data directory (default: ./data).")
    parser.add_argument("--force", action="store_true", help="Re-synthesize rows that already have a qa_summary.")
    args = parser.parse_args()

    jsonl_path = args.data_dir / "outputs" / "pilot_results.jsonl"
    if not jsonl_path.exists():
        print(f"{jsonl_path} not found -- run `python src/run_pilot.py` first.")
        return

    rows = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    if not rows:
        print(f"{jsonl_path} is empty.")
        return

    try:
        ask_json(
            system='Reply with exactly this JSON object and nothing else: {"ok": true}',
            user="ping",
        )
    except FoundryCallError as exc:
        print(f"Foundry connection check failed: {exc}")
        print("Fix the issue above (network/VPN/sign-in) before synthesizing summaries.")
        return

    def already_synthesized(row: dict) -> bool:
        qa = row.get("qa_summary")
        if qa is None:
            return False
        # "insufficient_evidence" here means an upstream criterion errored last
        # time -- always retry automatically once that's fixed, rather than
        # skip forever until someone remembers --force.
        return qa.get("overall_likelihood") != "insufficient_evidence"

    print(f"Synthesizing {len(rows)} row(s)...")
    for i, row in enumerate(rows, start=1):
        if already_synthesized(row) and not args.force:
            print(f"[{i}/{len(rows)}] {row['fp_id']} -- already synthesized, skipping (use --force to redo)")
            continue

        print(f"[{i}/{len(rows)}] {row['fp_id']}")
        try:
            row["qa_summary"] = synthesize_row(row)
        except FoundryCallError as exc:
            print(f"  Failed: {exc}")
            row["qa_summary"] = _insufficient_evidence_summary(f"Synthesis call failed: {exc}")

    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"Done. Updated {jsonl_path}")


if __name__ == "__main__":
    main()
