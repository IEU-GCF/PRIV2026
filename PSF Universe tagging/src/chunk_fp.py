"""
Pull out the specific sections of a funding proposal where a colleague
with direct FP-template knowledge says evidence for these criteria
actually lives, instead of sending the whole document to the model on
every call. This targets extraction (higher precision) and cuts the
amount of text sent per call (lower cost) at the same time.

GCF's FP template is NOT one fixed layout -- the same review turned up
at least three different section schemes in real proposals:

  "Current"-style numbering (originally confirmed section-by-section):
    A.18    Project/Programme rationale, objectives and approach
    B.2.1   Project/Programme description
    C.7     Institutional / Implementation Arrangements (that word order --
            confirmed against real FP text; originally described as "B.3
            Implementation / institutional arrangements", number and word
            order were both off)
    C.1     Total financing                                (number unconfirmed)
    C.2.1   Financing structure (private-sector proposals only, max. 300 words)
    C.6     Financial management / procurement
    D.6.2   Expected volume of finance to be leveraged, by public/private source

  "SAP"-style top-level sections (different lettering, same rough topics):
    Section A - Project/Programme Summary
    Section B - Financing / Cost Information
    Section C - Detailed Project/Programme Description
    Section D - Rationale for GCF Involvement
    Section E - Expected Performance Against Investment Criteria
    Section F - Appraisal Summary
    Section G - Risk Assessment and Management
    Section H - Results Monitoring and Reporting
    Section I - Annexes

  Earliest-version proposals: different again (e.g. "Section D. Logic
  Framework, Monitoring, Reporting and Evaluation" is a different topic
  than either of the above).

Because even the SECTION TITLE, not just the number, can differ by
template vintage, every pattern below matches on title wording with an
OPTIONAL, unconstrained section-number/letter prefix -- never a fixed
letter. Where a second known phrasing exists (from the SAP template),
it's included as an alternative. Sections with only one known phrasing
are noted below; they are more likely to come back "not found" on
SAP-style or earliest-version proposals, and that's a real gap, not a
bug -- the fallback PROPOSAL_TEXT excerpt exists precisely to catch
some of what these patterns miss. Check data/evidence_packets/*.json on
a few real FPs (ideally spanning different template vintages) before
trusting a full batch.
"""

import re

_FLAGS = re.IGNORECASE | re.MULTILINE | re.DOTALL

# An optional, unconstrained "this looks like a heading label" prefix --
# e.g. "A.18.", "C.2.1.", "Section B -", "Section D." -- matched loosely
# because the actual letter/number is known to vary by template vintage.
# Never anchor on a specific letter: SAP's Section D is "Rationale for
# GCF Involvement", but the earliest-version Section D is a completely
# different topic (Logic Framework/M&E).
_OPTIONAL_HEADING_PREFIX = r"(?:(?:Section\s+)?[A-Z]\.?\s?\d{0,2}\.?\d{0,2}\.?\s*[-–—:.]?\s*)?"

# Stop a section's excerpt at the next thing that looks like a heading,
# in either numbering style, or end of document.
_NEXT_HEADING = r"(?=\n\s*[A-Z]\.\s?\d|\n\s*Section\s+[A-Z]\b|\Z)"

# FP277 (manually reviewed) surfaced a real truncation bug at the old
# 2,000-char cap: its Project/Programme description excerpt was cut off
# mid-sentence before reaching the paragraph naming the actual private
# Executing Entity, so neither criterion 1 nor criterion 3 ever saw it.
# The GCF template's own guidance caps this section at ~2,500 words;
# sized for that (roughly 6 chars/word incl. spaces, plus headroom for
# longer technical vocabulary) so a full section is no longer clipped.
MAX_SECTION_EXCERPT_CHARS = 16_000

# Safety net for proposals that don't match any named section at all
# (non-standard formatting, or a template vintage not accounted for
# above). Kept short since it's a fallback, not the primary source.
FALLBACK_TEXT_CHARS = 4_000

SECTION_PATTERNS = {
    # Unnumbered in every known template vintage.
    "executive_summary": re.compile(
        _OPTIONAL_HEADING_PREFIX + r"Executive\s+Summary\b.*?" + _NEXT_HEADING, _FLAGS
    ),
    # "Current" wording, SAP's "Rationale for GCF Involvement", OR a third
    # layout's "Justification for GCF funding request" -- confirmed against
    # real FP text (FP148/172/247/253): it asks exactly the rationale
    # questions (why GCF funding, which market failure, why this
    # instrument), just under a different heading.
    "section_rationale_and_approach": re.compile(
        _OPTIONAL_HEADING_PREFIX
        + r"(?:Project\s*/?\s*Programme\s+rationale.*?approach|Rationale\s+for\s+GCF\s+Involvement"
        + r"|Justification\s+for\s+GCF\s+funding\s+request)\b.*?"
        + _NEXT_HEADING,
        _FLAGS,
    ),
    # "Current" wording, SAP's "Detailed Project/Programme Description", or
    # (confirmed against real text, FP041) plain "Detailed Project
    # Description" with no "Programme" at all -- "Programme" made optional
    # throughout rather than adding a third near-duplicate alternative.
    "section_project_description": re.compile(
        _OPTIONAL_HEADING_PREFIX
        + r"(?:Project(?:\s*/?\s*Programme)?\s+description|Detailed\s+Project(?:\s*/?\s*Programme)?\s+Description)\b.*?"
        + _NEXT_HEADING,
        _FLAGS,
    ),
    # Confirmed against real FP text in two different forms: "Institutional
    # / Implementation Arrangements" (that word order) in some proposals,
    # plain "Implementation Arrangements" (no "Institutional" at all) in
    # others (FP148/172/247/253). No SAP-equivalent identified yet.
    "section_institutional_arrangements": re.compile(
        _OPTIONAL_HEADING_PREFIX
        + r"(?:Institutional\s*/?\s*Implementation\s+Arrangements"
        + r"|Implementation\s*/?\s*Institutional\s+Arrangements"
        + r"|Implementation\s+Arrangements)\b.*?"
        + _NEXT_HEADING,
        _FLAGS,
    ),
    # "Total financing", SAP's "Financing / Cost Information", or (confirmed
    # against real text, SAP004) a shorter SAP variant "Financing
    # Information" with no "Cost" at all -- SAP templates have had more
    # than one revision themselves, not just one fixed layout. Also
    # confirmed against real text (FP076): "Project Financing Information",
    # with "Project" wedged between the section number and the topic words
    # -- without the optional "Project " prefix here, this heading was never
    # matched at all, and the regex instead matched a different, wrong
    # "FINANCING / COST INFORMATION" heading elsewhere in the same document,
    # one that led into unrelated output/activity narrative rather than the
    # actual financing table -- so the model never saw the real GCF
    # instrument breakdown (e.g. a Senior Loans line) for that proposal.
    "section_total_financing": re.compile(
        _OPTIONAL_HEADING_PREFIX
        + r"(?:Total\s+financing\b|(?:Project\s+)?Financing\s*/?\s*(?:Cost\s+)?Information\b).*?"
        + _NEXT_HEADING,
        _FLAGS,
    ),
    # Private-sector-specific, max. 300 words per the template guidance --
    # short and dense with instrument/structure detail. Only one known phrasing.
    "section_financing_structure": re.compile(
        _OPTIONAL_HEADING_PREFIX + r"Financing\s+structure\b.*?" + _NEXT_HEADING, _FLAGS
    ),
    # Confirmed against real FP text in two forms: "Financial management /
    # procurement" and "Financial management and procurement" (the word,
    # not a slash -- FP148/172/247/253). No SAP-equivalent identified yet.
    "section_financial_management_procurement": re.compile(
        _OPTIONAL_HEADING_PREFIX + r"Financial\s+management\s*(?:/|and)?\s*procurement\b.*?" + _NEXT_HEADING, _FLAGS
    ),
    # Best-effort second alternative: GCF's six investment criteria include
    # effectiveness/efficiency, where leverage/co-financing ratios are
    # often discussed -- plausible but NOT confirmed for this exact field,
    # unlike the first alternative. Treat a hit via this branch as lower
    # confidence than a hit on the first branch.
    "section_expected_leverage_volume": re.compile(
        _OPTIONAL_HEADING_PREFIX
        + r"(?:Expected\s+volume\s+of\s+finance\s+to\s+be\s+leveraged|Expected\s+Performance\s+Against\s+Investment\s+Criteria)\b.*?"
        + _NEXT_HEADING,
        _FLAGS,
    ),
}


# Some proposals (confirmed in SAP004/SAP057/FP041) list every section
# heading with a one-sentence preview in a table of contents up front,
# THEN the real section appears later in the document. Taking the first
# regex match picked up that TOC preview instead of the real content --
# and a length threshold isn't reliable either (one real TOC blurb was
# 264 characters, comfortably over a 200-char bar and still just a
# preview). Comparing all occurrences and keeping the longest is simpler
# and correct here: a genuine section body is reliably longer than a
# one-sentence preview of it, and MAX_SECTION_EXCERPT_CHARS below still
# bounds the worst case if a match runs on too long.
#
# But "longest wins" alone has the opposite failure mode too (confirmed in
# FP076): some FP PDFs repeat a running page header (e.g. "GREEN CLIMATE
# FUND FUNDING PROPOSAL | PAGE X OF Y") on every page, and when a section
# heading also happens to appear as page-header text elsewhere in the
# document, a single regex match can swallow many unrelated pages before
# hitting the next real heading -- in that case a 45,000+ character match
# of narrative text from later in the document beat the real, correct
# ~5,300 character financing table, and the model never saw the table at
# all. A genuine single section's match should contain at most one
# occurrence of that running header (its own); two or more is a reliable
# sign the match ran on across page boundaries it shouldn't have. Known
# tradeoff: a real section that legitimately spans several pages could in
# principle be excluded by this rule too -- not observed yet, but worth
# checking if a future FP's excerpt looks suspiciously short.
_PAGE_HEADER_MARKER = "GREEN CLIMATE FUND FUNDING PROPOSAL"
_MAX_PAGE_HEADER_REPEATS = 1


def _best_match(pattern: re.Pattern, text: str) -> str | None:
    candidates = list(pattern.finditer(text))
    if not candidates:
        return None
    plausible = [m for m in candidates if m.group(0).count(_PAGE_HEADER_MARKER) <= _MAX_PAGE_HEADER_REPEATS]
    pool = plausible or candidates  # fall back to all candidates if every one runs long
    longest = max(pool, key=lambda m: len(m.group(0)))
    return longest.group(0).strip()[:MAX_SECTION_EXCERPT_CHARS]


def build_fp_chunks(full_text: str) -> dict:
    """
    Return a dict with one key per section in SECTION_PATTERNS (str or
    None if not found), plus:
      - fp_text: str  (a short truncated-from-the-start fallback slice
                        of the raw text, sent alongside the named
                        sections as a safety net)
    """
    chunks = {name: _best_match(pattern, full_text) for name, pattern in SECTION_PATTERNS.items()}
    chunks["fp_text"] = full_text[:FALLBACK_TEXT_CHARS]
    return chunks
