"""
Extract text from a funding proposal PDF, once, and cache it as a .txt file.

Why cache: PDF text extraction is free (it runs locally, no LLM call), but
re-running it every time we re-score a project wastes time. Once a PDF's
text has been pulled out, later steps in the pipeline read the cached .txt
file instead of re-opening the PDF.
"""

from pathlib import Path

import fitz  # PyMuPDF


def extract_pdf_text(pdf_path: Path, cache_dir: Path) -> str:
    """
    Return the full text of a funding-proposal PDF.

    If a cached .txt file already exists for this PDF (same filename, in
    `cache_dir`), that is read instead of re-extracting.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{pdf_path.stem}.txt"

    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    with fitz.open(pdf_path) as doc:
        pages = [page.get_text() for page in doc]
    text = "\n".join(pages)

    cache_path.write_text(text, encoding="utf-8")
    return text
