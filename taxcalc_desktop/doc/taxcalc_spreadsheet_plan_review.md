# Review: taxcalc_spreadsheet_plan.md

Review of the plan to implement the core logic in `test/taxcalc.ipynb` as a formula-only spreadsheet (Apple Numbers / XLSX). The review checks alignment with the notebook and e-ORP, and suggests corrections and clarifications.

---

## Summary

The plan is **sound and implementable**. It correctly mirrors the notebook’s tax logic (ordinary brackets, cap-gains stacking, OBBBA, standard deduction, inflation for post-2026), uses a clear sheet layout and scenario-per-column design, and includes a sensible validation phase. A few numeric/structural details need correction or clarification; the main risk is spreadsheet formula verbosity and XLOOKUP/SUMPRODUCT behaviour in Numbers.

---

## 1. Alignment with taxcalc.ipynb

### 1.1 Tax tables (Phase 1)

- **Ordinary brackets (MFJ/Single):** The plan’s dollar bracket tops match the notebook’s values in $000s (e.g. 23,850 = 23.85×1000; 501,050 = 501.05×1000). The sentinel row (9,999,999 @ 0.37) is a good addition for “above top bracket”; the notebook stops at the last real bracket.
- **Single 2025 top bracket:** The plan correctly uses **250,525** (one number). The notebook has a bug: `(250,525, 0.320)` is three Python arguments (250, 525, 0.32). It should be `(250.525, 0.320)` in $000s. The spreadsheet plan is right; when implementing `taxcalc_core.py`, fix the notebook to 250.525.
- **Cap gains brackets:** MFJ 96,700 / 600,050 and Single 48,350 / 533,400 match the notebook’s 96.70, 600.05, 48.35, 533.40 in $000s.
- **Standard deductions:** 2025/2026 base and over-65 amounts match. “Over-65 each” applied as 1 (Single) or 2 (MFJ) is consistent with the notebook’s `std_deduction = std_deductions[year] * infla + over65_additions` and the plan’s explicit “both filers over 65” assumption.
- **OBBBA:** 2025–2028, $6k per person, 6% phase-out above $75k (Single) / $150k (MFJ), MAGI-based — matches the notebook’s `OBBBA_exc`, `OBBBA_ded` logic and `oyear >= 2025 and oyear <= 2028`.

### 1.2 Calculation flow (Phase 2)

- **Income (ex cap gains):** Net Earnings + IRA Dist − QCD + Interest + Dividends + 0.85×SSA + ST Gains matches the notebook’s `income` construction.
- **Cap gains:** LT Gains + Carryover matches.
- **AGI:** Income + Cap gains — correct.
- **MAGI:** AGI + 0.15×SSA + QCD matches the notebook (non-taxable SSA portion + QCD added back).
- **OBBBA:** `OBBBA_pax = IF(B2=1, 2, 1)`, excess = MAX(0, MAGI − pax×75000), deduction = MAX(0, pax×6000 − pax×0.06×excess) in 2025–2028 — correct. Units: plan uses dollars (6000, 75000); notebook uses $000s (6.0, 75.0). Consistent.
- **Inflation:** Factor `(1 + B12)^MAX(0, B1 − LastAdjYear)` for years > 2026 matches the notebook’s `infla` for `year > last_tax_year_with_irs_adjusted_brackets`.
- **Std deduction total:** Base×infla + over65×infla + OBBBA_ded — correct.
- **Taxable income:** MAX(0, B15 − B25) is taxable ordinary income — correct.
- **Ordinary tax:** SUMPRODUCT over bracket widths × rates, with income filling from the bottom, matches the notebook’s cumulative bracket logic. The plan’s “BracketFloor_i = BracketTop_(i-1); BracketWidth_i = …; IncomeInBracket_i = MAX(0, MIN(TaxableIncome − BracketFloor_i, BracketWidth_i))” is the right pattern.
- **Cap gains tax:** Cap gains stacked above ordinary taxable income (row 31 = B15−B25), filling cap-gains brackets — matches the notebook’s loop that adds `take` to `income` and consumes `capgains` by bracket.

### 1.3 Row and block layout

- Input block (1–12), intermediates (14–25), tax (27–36), results (38–47) are clear. The gap between 12 and 14 (and 25 and 27) avoids row renumbering when inserting. Label “Cap gains base” (row 31) is correct: it’s the ordinary taxable income that cap gains stack on top of.

---

## 2. Corrections and clarifications

### 2.1 Ordinary brackets — 37% top rate

- The plan shows a **sixth** bracket 9,999,999 @ **0.370**. The notebook only has five brackets (top rate 32%). Federal 2025/2026 actually has a **37%** bracket above 501,050 (MFJ) / 250,525 (Single). So the plan is correct to add the 37% sentinel; the notebook (and any `taxcalc_core.py`) should be extended to include it for accuracy. No change needed to the plan; when extracting core logic, add the 37% bracket.

### 2.2 Row 27 label

- Row 27 is “Taxable income” — it’s **taxable ordinary income** (after standard deduction). Consider labelling it “Taxable income (ordinary)” to distinguish from “AGI” and avoid confusion with “cap gains taxable” (row 32).

### 2.3 XLOOKUP match mode

- Plan says “match_mode=1: next larger” for marginal rate (row 29). In Excel, `XLOOKUP(..., 1)` is “exact or next larger”. Numbers may use different syntax; document the exact Numbers equivalent (e.g. “next larger” or “ascending match”) so marginal rate at bracket boundaries is correct.

### 2.4 SUMPRODUCT and IF(B2=1, …) for MFJ vs Single

- Using `IF(B2=1, TaxTables!OrdinaryBrackets_MFJ[...], TaxTables!OrdinaryBrackets_Single[...])` inside SUMPRODUCT is the right idea. In Apple Numbers, table references and conditional array selection can be verbose or require helper columns. The plan’s fallback (“add helper rows 28a/28b that materialise the chosen bracket arrays”) is practical; recommend starting with one or two helper columns (e.g. “BracketTop” and “Rate” for the chosen status) and then SUMPRODUCT on those.

### 2.5 Filing status 0 vs 1

- Plan: 0 = Single, 1 = MFJ. Notebook uses `tax_data[filing_status]` with 0 = Single, 1 = MFJ. Consistent. The year-sheet dropdown “Single” / “MFJ” mapping to 0/1 via `=IF(FilingStatusCell="MFJ", 1, 0)` is correct.

### 2.6 Results block row numbers

- Results block is rows 38–47 (labels) with values in scenario columns. Row 47 is “Effective Rate”; the table in 2.4 lists up to 47. No change needed.

---

## 3. Gaps and risks

### 3.1 Head of Household (HoH)

- The notebook and plan only implement Single and MFJ. e-ORP’s `planner.py` has HoH (filing_status=2) with different brackets and standard deduction. The plan’s “Open Questions” mention over-65 count; if HoH is ever needed, add a third filing status and a third set of tables (and possibly over-65 count) so the spreadsheet stays aligned with code.

### 3.2 Negative gains carryover

- Plan allows “Gains Carryover” to be negative (row 11). Cap gains = B10 + B11 can therefore be negative. Row 32 “Cap gains taxable = MAX(0, B16)” correctly zeros out negative cap gains for tax. The validation scenario “Negative carryover” is good; add a note in Phase 2 that B16 can be negative and only the positive part is taxed.

### 3.3 Rounding

- The notebook uses float arithmetic; the plan doesn’t specify rounding. IRS rounds to whole dollars in some places. For Phase 4 validation “to the nearest dollar”, decide whether the spreadsheet rounds total tax (and/or intermediate amounts) to integers; if so, document where (e.g. row 35 Total Tax = ROUND(..., 0)) so cross-checks are consistent.

### 3.4 Numbers compatibility

- Plan targets “Apple Numbers v15 (XLSX import)”. XLOOKUP and structured table references (e.g. `TaxTables!OrdinaryBrackets_MFJ[BracketTop]`) are Excel-style. Verify that Numbers supports these when opening XLSX (or that an Excel-built workbook imports correctly into Numbers without breaking formulas). If Numbers differs, add a short “Numbers notes” subsection listing any formula adjustments.

---

## 4. Relationship to taxcalc_core and PyWebView plan

- **taxcalc_pywebview_plan.md** proposes extracting logic into **taxcalc_core.py** for the notebook and a PyWebView desktop app. The spreadsheet plan does not depend on that extraction: the spreadsheet is formula-only and can be built in parallel. Once **taxcalc_core.py** exists:
  - **Phase 4 (Validation)** should use `taxcalc_core.tax_calc(...)` (or equivalent) with inputs in dollars and compare to spreadsheet results. The plan’s “Run the Python `tax_calc()` function” is exactly that.
  - Keeping **tax tables in one place** (e.g. taxcalc_core or a small data file) and generating the TaxTables sheet or documenting “source of truth” in the plan would reduce drift between Python and spreadsheet.
- The spreadsheet plan’s **core logic** (brackets, OBBBA, std deduction, inflation, ordinary + cap gains tax) is the same as the notebook; implementing the plan does not conflict with the PyWebView plan.

---

## 5. Recommendations

1. **Fix notebook Single 2025 bracket** when touching the notebook: change `(250,525, 0.320)` to `(250.525, 0.320)` (one value in $000s).
2. **Add 37% bracket** to the notebook / taxcalc_core for 2025/2026 so Python and spreadsheet match the real code and IRS.
3. **Document rounding** in the plan (e.g. “Total Tax and results block rounded to whole dollars for display and validation”).
4. **Add one sentence** in Phase 2.2 or 2.3: “B16 (Cap Gains) may be negative; only the positive part is taxed (row 32).”
5. **Keep Phase 4 as written** and run validation against the notebook (or taxcalc_core once it exists) with the scenarios listed; add a “Rounding” row to the checklist if you round in the sheet.
6. **Optional:** Add a “Source of truth” note: “Bracket and deduction values in this plan match test/taxcalc.ipynb (and, when present, taxcalc_core.py) as of [date].”

---

## 6. Verdict

**Approve the plan** with the small corrections above. The structure (TaxTables → TaxCalc → year sheets), the formula sketches, and the validation approach are correct and consistent with the notebook. Implementing in the suggested order (TaxTables → intermediates → tax formulas → results → year sheet → second scenario → validation) is reasonable. The open questions (over-65 count, AMT, NIIT, state tax) are appropriately deferred.
