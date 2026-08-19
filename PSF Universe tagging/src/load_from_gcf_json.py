"""
Alternative to dropping PDFs into data/raw_pdfs/: load funding proposal
text directly from the pre-scraped GCF documents database that already
sits in your PRIV_LLM_FP_pilot folder.

That JSON (`gcf_documents_database (1).json`, ~400MB) has one record per
GCF public document, and for "Approved funding proposal" records the
full text is already extracted into the `content` field -- no PDF
parsing needed. This script streams it (it's too big to load whole),
pulls out just the approved funding proposals, and writes each one's
text to data/extracted_text/<project_id>.txt -- the exact cache path
extract_text.py already checks before it would otherwise open a PDF.
Once these .txt files exist, run_pilot.py picks them up automatically
and never touches raw_pdfs/ or PyMuPDF for that project.

Usage:
    python src/load_from_gcf_json.py --limit 10
    python src/load_from_gcf_json.py --fp-ids FP008,FP018,FP033,SAP004
"""

import argparse
from pathlib import Path

import ijson

DEFAULT_SOURCE_JSON = Path(
    r"C:\Users\onkiwong\OneDrive - GCF\VS_code_app\tpr\4 Climate Fund benmarking -climate explorer"
    r"\PRIV_LLM_FP_pilot\gcf_documents_database (1).json"
)
FP_DOCUMENT_TYPE = "Approved funding proposal"

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Load FP text from the GCF documents database JSON.")
    parser.add_argument("--limit", type=int, default=10, help="Max number of proposals to load (default: 10, ignored if --fp-ids is given).")
    parser.add_argument("--fp-ids", type=str, default=None, help="Comma-separated exact FP IDs to load, e.g. FP008,FP018,SAP004.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_JSON, help="Path to gcf_documents_database.json.")
    parser.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data", help="Pilot data directory (default: ./data)."
    )
    parser.add_argument("--overwrite", action="store_true", help="Re-write .txt files even if they already exist.")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Source JSON not found at {args.source}")
        print("Pass --source <path> if it's been moved, or check the PRIV_LLM_FP_pilot folder.")
        return

    extracted_text_dir = args.data_dir / "extracted_text"
    extracted_text_dir.mkdir(parents=True, exist_ok=True)

    wanted_ids = None
    if args.fp_ids:
        wanted_ids = {fp_id.strip().upper() for fp_id in args.fp_ids.split(",") if fp_id.strip()}
        remaining = set(wanted_ids)

    written, skipped, seen = 0, 0, 0
    print(f"Streaming {args.source.name} (this is a large file; may take a minute)...")
    with open(args.source, "rb") as f:
        for item in ijson.items(f, "item"):
            if wanted_ids is not None:
                if not remaining:
                    break
            elif written >= args.limit:
                break
            if item.get("document_type") != FP_DOCUMENT_TYPE:
                continue

            project_id = item.get("project_id")
            if not project_id:
                continue

            if wanted_ids is not None:
                if project_id.upper() not in remaining:
                    continue
                remaining.discard(project_id.upper())

            seen += 1
            out_path = extracted_text_dir / f"{project_id}.txt"
            if out_path.exists() and not args.overwrite:
                skipped += 1
                continue

            out_path.write_text(item.get("content", ""), encoding="utf-8")
            written += 1
            print(f"  {project_id}: {item.get('project_title', '')[:70]}")

    print(f"\nScanned {seen} approved funding proposal record(s), wrote {written}, skipped {skipped} (already cached).")
    if wanted_ids is not None and remaining:
        print(f"NOT FOUND in the source JSON: {sorted(remaining)} -- check the ID spelling, or they may not be "
              "'Approved funding proposal' records (e.g. withdrawn, or a different document_type).")
    print(f"Text saved to {extracted_text_dir}")
    print("Now run: python src/run_pilot.py --limit <N>  (or --fp-ids to match exactly)")


if __name__ == "__main__":
    main()
