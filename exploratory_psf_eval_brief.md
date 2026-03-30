# Briefing Note: Independent Evaluation of GCF's Portfolio of and Approach to the Private Sector
**Prepared for:** Meeting with Aiko (IEU Project Lead)
**Prepared by:** Evaluation Quant Specialist
**Date:** March 2026
**Evaluation mandate:** B.43 approved → report due B.46 (October 2026)

---

## 1. Purpose of This Note

This briefing summarises the quantitative evidence base available from the GCF public API to support the evaluation. It is structured around three topics:

1. **Preliminary portfolio snapshot** — what the API data already shows about the PSF
2. **Proposed quantitative indicator set** — mapped to each TOR evaluation question
3. **Suggested country case study candidates** — using the IMF DSA sovereign risk overlay

---

## 2. PSF Portfolio Snapshot (TOR Baseline vs API Data)

| Indicator | TOR Baseline (B.43) | API Cross-check | Notes |
|---|---|---|---|
| PSF projects (n) | 78 | Run PSF-1 cell | API uses entity_type/entity_access proxy — confirm headcount with GCF data team |
| GCF commitment | USD 6.9B | Run PSF-1 cell | Aggregated from TotalGCFFunding |
| Total portfolio value | ~USD 37B implied | Run PSF-1 cell | TotalValue = GCF + co-financing |
| Leverage ratio | 4.41x | Run PSF-1 cell | Median likely lower; mean driven by large outliers |
| Disbursement rate | 32% | Run PSF-2 cell | API Disbursements[] field; TOR figure from GCF monitoring |
| Cancellation rate | Not stated in TOR | Computed in EQ3 | Status == 'Cancelled' / total PSF projects |

> **Action before meeting:** Run cells PSF-1 and PSF-2 in gcf_pipeline.ipynb (Section 7) to generate live numbers. The API is open at `http://api.gcfund.org/v1/projects`.

---

## 3. Data/Evidence Metrics Table: TOR EQ → Quantitative Indicators

| EQ | TOR Evaluation Question | Primary Metric | Secondary Metrics | API Fields | Availability |
|---|---|---|---|---|---|
| **EQ1** | Has GCF mobilised private capital consistent with its PSF mandate? | Leverage ratio (total value / GCF commitment) | Co-financing by source; GCF share of project cost; leverage distribution (median, CoV) | TotalGCFFunding, TotalCoFinancing, TotalValue, Funding[].Source | HIGH |
| **EQ2** | Is the instrument mix appropriate for private sector market development? | Debt/equity/guarantee share (% of GCF USD) | Subordinated vs senior loan split; instrument mix shift over time; guarantee utilisation | Funding[].Instrument, Funding[].BudgetUSDeq | HIGH |
| **EQ3** | What is implementation performance and disbursement pace? | Disbursement rate (disbursed / committed) | Time-to-first-disbursement; cancellation rate; overdue implementation share | Disbursements[], Status, DateImplementationStart, DateClosing | MEDIUM |
| **EQ4** | How does performance vary by access modality? | Direct vs International AE leverage and disbursement comparison | HHI of accredited entities within PSF; top-5 AE concentration | Entities[].Access, Entities[].Type, Entities[].Name | HIGH |
| **EQ5** | Does PSF reach the most vulnerable countries? | PSF USD to LDC/SIDS/AF as % of total PSF | PSF vulnerability share vs full portfolio benchmark; high-risk country exposure | Countries[].LDCs, Countries[].SIDS, RiskCategory | HIGH |
| **EQ6** | What are co-financing risks and contingent liability exposures? | Contingent exposure (equity + guarantee USD) | IMF four-quadrant fiscal risk matrix; co-financing withdrawal stress (30% shock) | Funding[].Instrument, Countries[] + IMF DSA lookup | MEDIUM |
| **EQ7** | Are results and impact claims credible? | USD per tCO2e averted; USD per direct beneficiary | % projects with missing impact data; impact ratio by instrument type | LifeTimeCO2, DirectBeneficiaries, TotalGCFFunding | MEDIUM |
| **EQ8** | How has GCF's PSF approach evolved and what are the strategic gaps? | Private sector share of annual approvals (% of USD) | Instrument mix shift by vintage year; average PSF project size trend; cancellation trend | ApprovalDate, TotalGCFFunding, Funding[].Instrument, Status | HIGH |

**Availability legend:** HIGH = directly computable from live GCF API | MEDIUM = partial API data; may require supplementary GCF monitoring data

---

## 4. Proposed Country Case Study Candidates

The pipeline's EQ7 IMF DSA overlay identifies countries receiving PSF investment categorised by sovereign fiscal stress level. Suggested selection criteria for case studies:

| Selection Rationale | Criteria | Purpose |
|---|---|---|
| **High fiscal stress + large PSF exposure** | DSA = "High" or "In Distress" + top-quartile PSF USD | Contingent liability risk; stress-test leverage assumptions |
| **LDC/SIDS with large PSF portfolio** | is_ldc == True or is_sids == True + top-10 PSF USD | Vulnerability reach; test PSF mandate alignment |
| **Strong disbursement performers** | disb_rate > 50% + PSF project | Identify enabling conditions; contrast with underperformers |
| **Long-delayed / cancelled PSF projects** | status in ['Cancelled','Under Implementation'] + overdue flag | Implementation failure analysis; systemic vs project-specific |

> Run EQ7 cell in Section 4 to generate the full country-level DSA rating table. Cross-reference with PSF-1 regional breakdown.

---

## 5. Proposed Workplan (Quantitative Strand)

| Phase | Activity | Timing | Output |
|---|---|---|---|
| **Inception** | Confirm PSF project headcount with GCF data team; agree on PSF identification methodology | April 2026 | Agreed definition memo |
| **Inception** | Run full pipeline against refreshed API data; validate TOR baseline figures | April 2026 | Validation table (PSF-1 output) |
| **Data collection** | Supplement API disbursement data with GCF monitoring reports (where API Disbursements[] is sparse) | May 2026 | Enhanced disbursement dataset |
| **Analysis** | Compute all 8 EQ indicator sets; run IMF DSA overlay | May–June 2026 | Indicator tables + charts |
| **Case studies** | Select 3–4 country cases from DSA/vulnerability matrix; coordinate with qualitative team | June 2026 | Country profiles |
| **Synthesis** | Draft quantitative annex; integrate with overall evaluation findings | Aug 2026 | Draft report contribution |
| **Report** | Final report submission B.46 | October 2026 | Board document |

---

## 6. Key Data Gaps and Risks

| Gap | Risk Level | Mitigation |
|---|---|---|
| **PSF flag not available in API** — must infer from entity_type/access | HIGH | Request confirmed PSF project list from GCF data team (Secretariat) |
| **Disbursements[] sparse in API** — field may be empty for many projects | MEDIUM | Use GCF monitoring data or Annual Performance Reports as supplement |
| **Impact data missing** — LifeTimeCO2 and Beneficiaries not populated for ~30-40% of projects | MEDIUM | Flag data quality issue; compute coverage rate; caveat findings |
| **Multi-country project allocation** — funding attributed to first country only in current pipeline | LOW | For country-level analysis, use project-level totals; note limitation |
| **IMF DSA ratings vintage** — pipeline uses 2023 lookup; may not reflect latest rating changes | LOW | Update lookup table at analysis phase; cite IMF DSA source |

---

## 7. Questions for Aiko

1. **PSF definition:** What is the authoritative source for the 78-project headcount? Is there a field in GCF's internal data systems that definitively flags PSF vs non-PSF?
2. **Disbursement data:** Does the evaluation team have access to GCF monitoring/disbursement records beyond what the public API provides?
3. **Evaluation scope:** Does the TOR include the PSF Enhanced Direct Access pilot projects, or only Funding Proposals approved under the formal PSF window?
4. **Co-financing verification:** The TOR leverage figure (4.41x) is based on committed co-financing. Should the analysis also examine realised/confirmed co-financing at disbursement stage?
5. **Counterfactual method:** Is the evaluation team planning an additionality assessment (private capital that would not have been mobilised otherwise)? If so, which counterfactual approach — survey-based, portfolio comparison, or econometric?

---

## 8. Available Pipeline Outputs (Attachments to Share)

The following can be generated from `gcf_pipeline.ipynb` and shared as evidence tables:

| Output | Source Cell | Format |
|---|---|---|
| PSF portfolio validation table | Section 7 / PSF-1 | Notebook display / Excel |
| Disbursement rate by status/year/region | Section 7 / PSF-2 | Notebook display / Excel |
| TOR crosswalk table | Section 7 / PSF-3 | Notebook display |
| EQ1 concentration (HHI, Gini, effective-N) | Section 4 / EQ1 | Notebook display |
| EQ2 instrument structure table | Section 4 / EQ2 | Notebook display |
| EQ3 at-risk portfolio | Section 4 / EQ3 | Notebook display |
| EQ4 vintage cohort table | Section 4 / EQ4 | Notebook display |
| EQ5 leverage distribution | Section 4 / EQ5 | Notebook display |
| EQ6 four-quadrant contingent liability matrix | Section 4 / EQ6 | Notebook display |
| EQ7 DSA sovereign risk map | Section 4 / EQ7 | Notebook display |
| EQ8 co-financing correlation stress scenario | Section 4 / EQ8 | Notebook display |
| FT-style charts (country, sector, size, region) | Section 5 | PNG (gcf_output/) |
| Full portfolio Excel export | Section 6 | Excel (gcf_output/) |

---

*Pipeline: `gcf_pipeline.ipynb` | Data: GCF API `http://api.gcfund.org/v1/projects` (no key required) | GitHub: `awongonki/gcf_api_data`*
