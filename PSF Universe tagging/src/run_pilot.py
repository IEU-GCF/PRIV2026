"""
Run the low-cost IEU Foundry pilot: score a small batch of funding
proposal PDFs against the three private-sector criteria and write one
JSON line per project to data/outputs/pilot_results.jsonl.

Usage (from the project root, with the venv active):
    python src/run_pilot.py --limit 10
    python src/run_pilot.py --fp-ids FP008,FP018,FP033,SAP004
    python src/run_pilot.py --fp-ids FP008,FP018,FP033,SAP004 --force
    python src/run_pilot.py --criteria 3 --force   # re-run ONLY criterion 3 across all FPs,
                                                    # e.g. after a prompt/section-targeting fix
                                                    # that only touches that criterion -- keeps
                                                    # criteria 1 and 2's existing results as-is

What this script does, in plain terms:
  1. Checks the Foundry connection with one tiny test call, so a broken
     VPN/sign-in fails fast instead of after burning through several FPs.
  2. Finds funding proposals to score: either a PDF in data/raw_pdfs/, or
     a .txt already sitting in data/extracted_text/ (e.g. from running
     load_from_gcf_json.py, which skips PDF parsing entirely for
     proposals already in the GCF documents database).
  3. Extracts each PDF's text once, if it wasn't already cached as .txt.
  4. Builds one compact "evidence packet" per FP (cached in
     data/evidence_packets/), pulling in any structured metadata you
     supplied in data/fp_metadata.csv.
  5. Sends three separate, focused prompts per FP to the model -- one
     per criterion -- and collects the JSON verdicts.
  6. Writes one row per FP to data/outputs/pilot_results.jsonl.

If a previous run already scored an FP with no errors, re-running the
same FP list SKIPS it and reuses that result rather than re-scoring (and
re-paying for) it -- only FPs that are new or that errored last time get
sent to the model again. Pass --force to re-score everything regardless.

You will see one browser sign-in prompt (Microsoft Entra ID) the first
time this process calls the model. You must be on the GCF office
network or GCF VPN.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow `import config` etc. from src/

from extract_text import extract_pdf_text
from build_evidence_packet import build_evidence_packet, load_metadata
from score_project import score_project, CRITERION_SCORERS
from foundry_client import ask_json, FoundryCallError

CRITERION_NAMES = [name for name, _ in CRITERION_SCORERS]
CRITERION_SCORER_BY_NAME = dict(CRITERION_SCORERS)

# Lets you re-run a single criterion across every FP (e.g. after a prompt
# or section-targeting fix that only affects one criterion) without
# re-paying for the other two, which didn't change.
CRITERION_SHORTHAND = {"1": CRITERION_NAMES[0], "2": CRITERION_NAMES[1], "3": CRITERION_NAMES[2]}

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def check_foundry_connection() -> bool:
    print("Checking Foundry connection...")
    try:
        ask_json(
            system='Reply with exactly this JSON object and nothing else: {"ok": true}',
            user="ping",
        )
    except FoundryCallError as exc:
        print(f"Foundry connection check failed: {exc}")
        return False
    print("Foundry connection OK.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Score a small batch of FPs against 3 private-sector criteria.")
    parser.add_argument("--limit", type=int, default=10, help="Max number of FPs to score (default: 10, ignored if --fp-ids is given).")
    parser.add_argument("--fp-ids", type=str, default=None, help="Comma-separated exact FP IDs to score, e.g. FP008,FP018,SAP004.")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data", help="Data directory (default: ./data).")
    parser.add_argument("--force", action="store_true", help="Re-score every FP even if it already succeeded last run.")
    parser.add_argument(
        "--criteria", type=str, default=None,
        help="Comma-separated subset of criteria to (re)score, e.g. --criteria 3 or --criteria 1,3. "
             "Accepts shorthand 1/2/3 or full names. Default: all three. Other criteria's existing "
             "results are kept as-is, so you don't re-pay for criteria that didn't change.",
    )
    args = parser.parse_args()

    if args.criteria:
        requested = [c.strip() for c in args.criteria.split(",") if c.strip()]
        selected_criteria = {CRITERION_SHORTHAND.get(c, c) for c in requested}
        unknown = selected_criteria - set(CRITERION_NAMES)
        if unknown:
            print(f"Unknown --criteria value(s): {unknown}. Valid: 1, 2, 3, or {CRITERION_NAMES}.")
            return
    else:
        selected_criteria = set(CRITERION_NAMES)

    raw_pdfs_dir = args.data_dir / "raw_pdfs"
    extracted_text_dir = args.data_dir / "extracted_text"
    evidence_packets_dir = args.data_dir / "evidence_packets"
    outputs_dir = args.data_dir / "outputs"
    metadata_csv = args.data_dir / "fp_metadata.csv"

    fp_ids_with_pdf = {p.stem for p in raw_pdfs_dir.glob("*.pdf")}
    fp_ids_with_cached_text = {p.stem for p in extracted_text_dir.glob("*.txt")}
    available_fp_ids = fp_ids_with_pdf | fp_ids_with_cached_text

    if args.fp_ids:
        wanted = [fp_id.strip() for fp_id in args.fp_ids.split(",") if fp_id.strip()]
        fp_ids = [fp_id for fp_id in wanted if fp_id in available_fp_ids]
        missing = [fp_id for fp_id in wanted if fp_id not in available_fp_ids]
        if missing:
            print(f"Not available locally yet, skipping: {missing}")
            print(f"  Run `python src/load_from_gcf_json.py --fp-ids {','.join(missing)}` "
                  "to pull them from the GCF documents database first, or drop matching PDFs into "
                  f"{raw_pdfs_dir}.")
    else:
        fp_ids = sorted(available_fp_ids)[: args.limit]

    if not fp_ids:
        print(f"No funding proposals found. Either add PDFs to {raw_pdfs_dir}, "
              "or run `python src/load_from_gcf_json.py --limit 10` to pull proposal text "
              "directly from the GCF documents database instead.")
        return

    if not check_foundry_connection():
        print("Fix the issue above (network/VPN/sign-in) before scoring any proposals.")
        return

    metadata = load_metadata(metadata_csv)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / "pilot_results.jsonl"

    # Reuse anything that already succeeded last run instead of re-scoring
    # (and re-paying for) it -- always loaded (even with --force) so a
    # --criteria subset run can merge forward the criteria it isn't
    # touching, instead of only ever seeing all-or-nothing per FP.
    previous_results = {}
    if output_path.exists():
        with output_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    previous_results[row["fp_id"]] = row

    def needs_scoring(row: dict | None, criterion_name: str) -> bool:
        if row is None:
            return True  # never scored at all -- must score regardless of --criteria selection
        if criterion_name not in selected_criteria:
            return criterion_name not in row  # only fill a genuine gap; otherwise leave as-is
        return args.force or "error" in row.get(criterion_name, {})

    try:
        output_file = output_path.open("w", encoding="utf-8")
    except PermissionError:
        print(f"Could not write to {outputs_dir} -- check that the file isn't open in another "
              "program, and that you have write access to this folder.")
        return

    print(f"Scoring {len(fp_ids)} funding proposal(s) "
          f"(criteria: {', '.join(sorted(selected_criteria)) if len(selected_criteria) < 3 else 'all'}).")

    fp_ids_set = set(fp_ids)
    carried_forward = [fid for fid in previous_results if fid not in fp_ids_set]
    if carried_forward:
        print(f"Note: {len(carried_forward)} previously-scored FP(s) not in this run's --fp-ids "
              f"are being carried forward unchanged, not dropped: {carried_forward}")

    with output_file:
        # Any FP scored in a prior run but NOT targeted by this invocation's
        # --fp-ids must still be written back -- otherwise a narrow, targeted
        # rerun (e.g. retrying one FP's failed criterion) silently truncates
        # the whole results file down to just the FPs named this time, which
        # is a real data-loss bug this fixes, not just a style choice.
        for fp_id in carried_forward:
            row = previous_results[fp_id]
            row["sector"] = metadata.get(fp_id, {}).get("sector") or None
            output_file.write(json.dumps(row) + "\n")
        output_file.flush()

        for i, fp_id in enumerate(fp_ids, start=1):
            prev_row = previous_results.get(fp_id)
            criteria_to_run = [name for name in CRITERION_NAMES if needs_scoring(prev_row, name)]

            if not criteria_to_run:
                print(f"[{i}/{len(fp_ids)}] {fp_id} -- nothing to do for the selected criteria, reusing")
                # Sector is GCF's own pre-assigned metadata, not model output --
                # cheap to keep in sync on every write, even when reusing.
                prev_row["sector"] = metadata.get(fp_id, {}).get("sector") or None
                output_file.write(json.dumps(prev_row) + "\n")
                output_file.flush()
                continue

            print(f"[{i}/{len(fp_ids)}] {fp_id} -- scoring: {', '.join(criteria_to_run)}")

            try:
                # If fp_id.txt is already cached (e.g. from load_from_gcf_json.py),
                # extract_pdf_text returns it directly without touching the PDF path.
                full_text = extract_pdf_text(raw_pdfs_dir / f"{fp_id}.pdf", extracted_text_dir)
            except Exception as exc:
                print(f"  Skipped -- could not extract text from PDF: {exc}")
                continue

            # Rebuild the packet from scratch rather than trusting the cache --
            # a --criteria rerun is typically happening BECAUSE section-targeting
            # or prompt wiring changed, so a stale cached packet would silently
            # undo the fix. This is a local text-processing step, not a model
            # call, so it costs nothing to redo.
            cache_path = evidence_packets_dir / f"{fp_id}.json"
            cache_path.unlink(missing_ok=True)
            packet = build_evidence_packet(
                fp_id=fp_id,
                full_text=full_text,
                metadata_row=metadata.get(fp_id),
                cache_dir=evidence_packets_dir,
            )

            result = dict(prev_row) if prev_row else {"fp_id": fp_id}
            result["sector"] = packet["sector"]
            for name in CRITERION_NAMES:
                if name in criteria_to_run:
                    try:
                        result[name] = CRITERION_SCORER_BY_NAME[name](packet)
                    except FoundryCallError as exc:
                        result[name] = {"error": str(exc)}
            output_file.write(json.dumps(result) + "\n")
            output_file.flush()

    print(f"Done. Results written to {output_path}")


if __name__ == "__main__":
    main()
