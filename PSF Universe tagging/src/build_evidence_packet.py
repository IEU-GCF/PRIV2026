"""
Combine locally-extracted PDF text with any structured metadata you have
on hand (budget share, instrument type, entity ownership, independent
review excerpt) into one evidence packet per FP, cached as JSON.

Structured metadata is optional. Supply it via `data/fp_metadata.csv`
(one row per FP, keyed by `fp_id` = the PDF's filename without ".pdf").
A missing file, or a blank cell, just means the model sees "not
provided" for that field -- every criterion prompt is written to
handle that gracefully.

fp_metadata.csv columns:
    fp_id, sector, budget_share_percent, instrument_type,
    independent_review_excerpt, entity_ownership_json

`sector` is GCF's own pre-assigned Public/Private tag for the FP -- not
derived or judged by the model at all, just carried through as
structured ground-truth metadata (same treatment as the other columns),
so it ends up in the pipeline's own JSON output instead of living only
as a separate hardcoded lookup in the Excel export step.
"""

import csv
import json
from pathlib import Path

from chunk_fp import build_fp_chunks

# `entity_ownership_json` in fp_metadata.csv has been blank for every FP since
# that column was added, so Criterion 3 always saw "none matched" and treated
# every named counterparty as unmatched -- including entities the team already
# has classified (e.g. GCF itself, XacBank), cluttering the "Entities
# Unmatched" export tab with non-findings. data/taxonomy/AE_partners_taxonomy_EM.xlsx
# is the team's own AE/PSAA ownership taxonomy; entity_ownership_reference.json
# is generated from it (see scratchpad build script) and used here as the
# default entity-ownership list for every FP unless fp_metadata.csv supplies
# a more specific one for that row. NGO/CSO entities are deliberately left out
# of the reference (not applicable to private-capital-mobilization ownership
# calls) so they still route to entities_unmatched for human judgment.
_ENTITY_OWNERSHIP_REFERENCE_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy" / "entity_ownership_reference.json"


def _load_default_entity_ownership_json() -> str | None:
    if not _ENTITY_OWNERSHIP_REFERENCE_PATH.exists():
        return None
    raw = json.loads(_ENTITY_OWNERSHIP_REFERENCE_PATH.read_text(encoding="utf-8"))
    lean = {name: entry["ownership"] for name, entry in raw.items()}
    return json.dumps(lean, ensure_ascii=False)


_DEFAULT_ENTITY_OWNERSHIP_JSON = _load_default_entity_ownership_json()


def load_metadata(metadata_csv: Path) -> dict:
    """Return {fp_id: {column: value}}. Empty dict if the file doesn't exist."""
    if not metadata_csv.exists():
        return {}
    with metadata_csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return {row["fp_id"]: row for row in reader}


def _parse_budget_share(raw_value: str | None, fp_id: str) -> float | None:
    if not raw_value or not raw_value.strip():
        return None
    try:
        return float(raw_value)
    except ValueError:
        print(f"  Warning: could not parse budget_share_percent '{raw_value}' for {fp_id} -- ignoring it.")
        return None


def build_evidence_packet(fp_id: str, full_text: str, metadata_row: dict | None, cache_dir: Path) -> dict:
    """Build (or load from cache) the evidence packet for one FP."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{fp_id}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    metadata_row = metadata_row or {}
    chunks = build_fp_chunks(full_text)  # keys: executive_summary, section_*, fp_text

    packet = {
        "fp_id": fp_id,
        "sector": metadata_row.get("sector") or None,
        **chunks,
        "budget_share_percent": _parse_budget_share(metadata_row.get("budget_share_percent"), fp_id),
        "instrument_type": metadata_row.get("instrument_type") or None,
        "independent_review_excerpt": metadata_row.get("independent_review_excerpt") or None,
        "entity_ownership_json": metadata_row.get("entity_ownership_json") or _DEFAULT_ENTITY_OWNERSHIP_JSON,
    }

    cache_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return packet
