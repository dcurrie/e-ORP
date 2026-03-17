# taxcalc Spreadsheet Implementation Plan

## Overview

Build a standalone spreadsheet implementation of the taxcalc logic using formula-only
techniques (no scripting). The workbook targets Apple Numbers v15 (XLSX import).
All monetary values are in **dollars** throughout.

---

## Sheet Inventory

| Sheet | Purpose |
|---|---|
| `TaxTables` | Static bracket, rate, and deduction data |
| `TaxCalc` | Calculation engine — inputs, intermediates, helpers, results |
| `2025`, `2026`, … | One per tax year — input panels + results display |

---

## Phase 1 — TaxTables Sheet

### 1.1 Bracket Tables

Four tables, one per filing status per bracket type (ordinary income and capital gains).
Each table has one row per bracket level. Columns represent years — each year occupies
two adjacent columns (Top and Rate). The index column (col 0) is for readability only.

Layout per table:
```
Idx | 2025 Top | 2025 Rate | 2026 Top | 2026 Rate | …
```

**Ordinary Income — MFJ**

| Idx | 2025 Top | 2025 Rate | 2026 Top | 2026 Rate |
|---|---|---|---|---|
| 1 | 23,850 | 10.0% | 24,800 | 10.0% |
| 2 | 96,950 | 12.0% | 100,800 | 12.0% |
| 3 | 206,700 | 22.0% | 211,400 | 22.0% |
| 4 | 394,600 | 24.0% | 403,550 | 24.0% |
| 5 | 501,050 | 32.0% | 512,450 | 32.0% |
| 6 | 9,999,999 | 37.0% | 9,999,999 | 37.0% |

The final row is always a sentinel (Top = 9,999,999) to catch income above all
defined brackets. Do not delete it; update its Rate if the top marginal rate
changes via legislation.

Repeat the same structure for Ordinary Income — Single, Capital Gains — MFJ,
and Capital Gains — Single.

### 1.2 Standard Deductions Table

One row per year, five columns:

| Year | MFJ Base | MFJ Over-65 Each | Single Base | Single Over-65 Each |
|---|---|---|---|---|
| 2025 | 31,500 | 1,600 | 15,750 | 1,600 |
| 2026 | 32,200 | 1,650 | 16,100 | 1,650 |

### 1.3 Global Parameters

A small named-cell block:

| Name | Value | Notes |
|---|---|---|
| `InflationRate` | 0.02 | Annual inflation for post-LastAdjYear extrapolation |
| `LastAdjYear` | 2026 | Last year with IRS-published bracket data |
| `OBBBAFirstYear` | 2025 | First year OBBBA senior SSA deduction applies |
| `OBBBALastYear` | 2028 | Last year OBBBA senior SSA deduction applies |

Assign each a defined name so TaxCalc can reference them symbolically.

### 1.4 Maintenance Guide

A prominent amber-highlighted note block at the top of TaxTables explains how to
add a new tax year, covering both the script path (preferred) and the manual path.
See section "Adding a New Year" below.

---

## Phase 2 — TaxCalc Sheet

TaxCalc is organised into fixed row ranges. **Each scenario occupies one column**,
starting at column B. Column A holds row labels. Adding a scenario means copying
column B rightward.

**Critical**: header rows must not use merged cells. Style each cell in the header
row individually (background color, font) with text only in column A. Merged headers
prevent column duplication in Numbers.

### 2.1 Input Block (Rows 1–12)

Values linked from a year sheet input panel, or entered directly for standalone use.

| Row | Label |
|---|---|
| 1 | Tax Year |
| 2 | Filing Status (0=Single, 1=MFJ) |
| 3 | Net Earnings |
| 4 | IRA Distribution |
| 5 | QCD |
| 6 | Interest |
| 7 | Dividends |
| 8 | SSA Income |
| 9 | ST Capital Gains |
| 10 | LT Capital Gains |
| 11 | Gains Carryover (may be negative) |
| 12 | Inflation Rate (= InflationRate named cell) |

### 2.2 Intermediate Calculations

| Row | Label | Formula |
|---|---|---|
| — | Taxable SSA | `= SSA * 0.85` |
| — | Income (ex cap gains) | `= Net + IRA − QCD + Interest + Dividends + TaxableSSA + STGains` |
| — | Cap Gains (net) | `= LTGains + Carryover` (may be negative) |
| — | AGI | `= Income + CapGains` |
| — | MAGI | `= AGI + SSA*0.15 + QCD` |
| — | OBBBA_pax | `= IF(FS=1, 2, 1)` |
| — | OBBBA_excess | `= MAX(0, MAGI − pax*75000)` |
| — | OBBBA_deduction | `= IF(AND(year>=2025,year<=2028), MAX(0, pax*6000 − pax*0.06*excess), 0)` |
| — | Inflation Factor | `= (1 + InflationRate) ^ MAX(0, year − LastAdjYear)` |
| — | Std Deduction (base) | `= XLOOKUP(MIN(year,LastAdjYear), YearCol, BaseCol) * InflationFactor` |
| — | Std Deduction (over-65) | `= pax * XLOOKUP(MIN(year,LastAdjYear), YearCol, Over65Col) * InflationFactor` |
| — | Std Deduction (total) | `= base + over65 + OBBBA_deduction` |
| — | Taxable Income (ordinary) | `= MAX(0, Income − StdDeduction)` — distinct from AGI |

Note: `XLOOKUP` for the standard deduction references TaxTables directly by
absolute range address. This works correctly because the standard deductions table
is a simple two-row lookup, not a multi-year bracket array.

### 2.3 Per-Bracket Helper Blocks

**Numbers compatibility requirement**: Numbers does not support implicit array
expansion of `scalar OP range` operations inside SUMPRODUCT when formulas are
imported from xlsx. This rules out the standard SUMPRODUCT marginal tax pattern.
The solution is to compute each bracket's contribution in an explicit scalar row,
then sum with a plain SUM formula.

Four helper blocks, written in this order for each bracket table:

```
Ord top 1..n          ← active year + FS bracket top, one row per bracket
Ord rate 1..n         ← active year + FS bracket rate
Ord floor 1..n        ← floor of each bracket (top of previous, 0 for first)
Ord tax bracket 1..n  ← tax contribution of each bracket

CG top 1..n
CG rate 1..n
CG floor 1..n
CG tax bracket 1..n
```

**Cell formula pattern** for each top/rate/floor cell (one scalar value):

```
=IF(FS=1,
    IF(MIN(year,LastAdjYear)<=2025, mfj_2025_val,
    IF(MIN(year,LastAdjYear)<=2026, mfj_2026_val, …)),
    IF(MIN(year,LastAdjYear)<=2025, sng_2025_val, …))
```

All bracket values are **embedded as literals** — no cross-sheet cell references.
Numbers remaps cross-sheet references into table-relative coordinates on xlsx import,
producing wrong values. Literal values are immune to this.

Top and floor cells are multiplied by the Inflation Factor for years beyond
LastAdjYear. Rate cells are never inflated — rates change only via legislation.

Floor row 0 is always 0 (no inflation needed).

**Tax-per-bracket formula** (ordinary income):
```
= MAX(0, MIN(TaxableIncome, top_i) - floor_i) * rate_i
```
All three operands are individual scalar cell references — no range arithmetic.

**Tax-per-bracket formula** (capital gains):
```
= (MAX(0, MIN(TaxableIncome+CGNet, top_i) - floor_i)
 - MAX(0, MIN(TaxableIncome,       top_i) - floor_i)) * rate_i
```
This computes only the cap gains portion within each bracket by stacking cap gains
on top of ordinary taxable income.

### 2.4 Tax Calculation Rows

| Row | Label | Formula |
|---|---|---|
| — | Tax on Income | `= SUM(Ord tax bracket 1..n)` |
| — | Marginal Rate — Income | nested IF — see below |
| — | Income Bracket Ceiling | nested IF over tops |
| — | Tax on Cap Gains | `= SUM(CG tax bracket 1..n)` |
| — | Marginal Rate — Cap Gains | nested IF — see below |

**Marginal rate nested IF pattern**: walk brackets low-to-high using `<=` with
true and false branches arranged so each step falls through to the next higher rate:

```
IF(TaxableIncome <= floor_1, rate_0,
  IF(TaxableIncome <= floor_2, rate_1,
    IF(TaxableIncome <= floor_3, rate_2,
      …
        rate_{n-1})))
```

Wrapped in `IF(TaxableIncome > 0, …, 0)` for the zero-income edge case.

Note: using `>` with the true/false branches in the opposite order (returning higher
rates in the true branch) does not work — the lowest floor (0) is always satisfied
first, short-circuiting to the lowest rate.

### 2.5 Rounding Policy

Rounding is applied only in the Results Summary block, not in intermediate rows.

| Result | Rounding |
|---|---|
| Total Tax | `ROUND(…, 0)` — nearest dollar |
| Tax on Income | `ROUND(…, 0)` |
| Tax on Cap Gains | `ROUND(…, 0)` |
| All other monetary results | `ROUND(…, 0)` |
| Marginal rates, effective rate | No rounding — display as percentage |

**Python alignment**: apply `round(value, 0)` in Python before comparing to
spreadsheet results during validation.

### 2.6 Results Summary Block

Referenced by year sheets. All values rounded per 2.5.

| Row | Label |
|---|---|
| — | Income (ex cap gains) |
| — | Cap Gains |
| — | AGI |
| — | Standard Deduction |
| — | Total Tax |
| — | Tax on Income |
| — | Tax on Cap Gains |
| — | Marginal Rate — Income |
| — | Marginal Rate — Cap Gains |
| — | Effective Rate |

---

## Phase 3 — Year Sheets

### 3.1 Input Panel

Each year sheet has one input panel per scenario. The Tax Year field defaults to
the sheet year but is editable. Filing Status is entered as 0 or 1.

### 3.2 Results Panel

All cells reference TaxCalc Results Summary rows — no logic, no formulas.

```
Income (ex cap gains):        = TaxCalc!B[results_row]
…
```

### 3.3 Multiple Scenarios

To add a second scenario:
1. In TaxCalc, duplicate column B into column C
2. Re-link the input block (rows 1–11, column C) to the new input panel
3. Update results panel references from column B to column C

Because TaxCalc uses row-absolute column-relative references (`B$row` not `$B$row`),
duplicating the column requires no adjustment to bracket helper formulas. Only
the input links in rows 1–11 need to be re-pointed.

---

## Phase 4 — Validation

Cross-check spreadsheet results against `taxcalc.py` for each scenario.
Run `phase4_validation.py` to generate expected values.

| # | Description | Year | FS | Key inputs | Total Tax |
|---|---|---|---|---|---|
| 1 | Zero income | 2025 | MFJ | all zeros | 0 |
| 2 | Income only, low | 2025 | MFJ | net=60,000 | 1,330 |
| 3 | Income only, mid | 2025 | MFJ | net=100,000 | 5,919 |
| 4 | OBBBA phase-in | 2025 | MFJ | SSA=85,000 | 2,589 |
| 5 | OBBBA phase-out | 2025 | MFJ | net=200,000 SSA=85,000 | 42,706 |
| 6 | Cap gains 0% | 2025 | MFJ | net=100,000 LT=50,000 | 6,909 |
| 7 | Cap gains 15% | 2025 | MFJ | net=200,000 LT=50,000 | 33,694 |
| 8 | Future year | 2030 | MFJ | net=100,000 | 6,852 |
| 9 | Single filer | 2025 | Single | net=80,000 | 7,443 |
| 10 | Negative carryover | 2025 | MFJ | net=100,000 LT=50,000 carry=−10,000 | 5,919 |
| 11 | Sample data | 2026 | MFJ | net=960 IRA=73,342 QCD=2,000 int=75 div=1,170 SSA=85,735 | 11,537 |

---

## Adding a New Year

Each November the IRS publishes inflation-adjusted brackets for the coming year.

**Preferred — via script:**
Append a new `(year, […])` tuple to each of the four bracket lists in
`build_taxcalc.py` and a new row to `STD_DEDUCTIONS`. Re-run the script.
Update `LastAdjYear` in TaxTables Global Parameters.

**Manual — spreadsheet only:**
1. In each bracket table, add two columns (Top, Rate) to the right of the last year
2. Add a new row to the Standard Deductions table
3. Update `LastAdjYear` in Global Parameters
4. In TaxCalc, extend the nested-IF literal value formula in each helper block row
   to include the new year's values. Pattern:
   ```
   IF(MIN(year,LastAdjYear)<=2025, val_2025,
   IF(MIN(year,LastAdjYear)<=2026, val_2026, val_2027))
   ```
   Repeat for tops, rates, and floors for every bracket level in all four tables.

---

## Numbers/xlsx Compatibility Notes

These issues were discovered during implementation and are recorded here for
reference if the workbook is ever rebuilt or ported.

**No SUMPRODUCT with range arithmetic.** Numbers does not expand `scalar OP range`
element-wise inside SUMPRODUCT when formulas are imported from xlsx. The standard
marginal tax SUMPRODUCT pattern fails silently, returning only the first bracket's
contribution. Solution: explicit per-bracket scalar rows summed with plain SUM.

**No dynamic arrays as XLOOKUP lookup arrays.** Passing `IF(cond, range_a, range_b)`
as the lookup array argument to XLOOKUP fails on import. Same root cause. Solved
by the per-bracket scalar approach, which eliminates the need for XLOOKUP over
bracket arrays entirely.

**Cross-sheet references become table-relative.** Numbers wraps each sheet's content
in a default table called "Table 1" and remaps cross-sheet cell references into
table-local row/column coordinates on xlsx import. A reference intended to point
to sheet row 15 may resolve to a completely different cell. Solution: embed all
bracket values as literals in helper cell formulas. Named range references
(InflationRate, LastAdjYear etc.) and XLOOKUP over small static ranges
(Standard Deductions) are not affected.

**No merged header cells if columns will be duplicated.** Numbers cannot paste
into a column that contains merged cells spanning into adjacent columns. Solution:
style header rows by coloring each cell individually without merging. Text goes
in column A only; remaining cells get background and border styling only.

**Marginal rate nested IF direction.** Using `IF(income > floor_i, rate_i, lower_expr)`
walking from high to low fails because the lowest floor (0) is always satisfied,
short-circuiting to the lowest rate. The correct pattern walks low to high using
`IF(income <= floor_i, lower_expr, rate_i)` so each step falls through to the
next higher rate until the correct bracket is found.

---

## Script / openpyxl Implementation Notes

These notes apply when (re)building the workbook with a Python script (e.g.
`e-ORP/scripts/build_taxcalc_spreadsheet.py`) using openpyxl. They complement
the Numbers/xlsx notes above.

**Defined names API.** In openpyxl, add workbook-level defined names with
`wb.defined_names.add(DefinedName(name, attr_text="=..."))`. Do not use
`wb.defined_names.append(...)` — `defined_names` is a `DefinedNameDict` and has
no `append` method.

**Duplicating a scenario column (B → C).** When copying formulas from one column
to another, replace only *this sheet’s* column references (e.g. `B27` → `C27`).
Do not replace column letters in references to other sheets (e.g. `TaxTables!$B$1`
must remain `$B$1`). A safe approach is a regex that matches the source column
letter only when not preceded by `$`, e.g. `(?<!\$)B(\d+)` → `C\1`, so that
absolute refs like `$B$1` are unchanged.

**Filing Status input.** Two workable options: (1) User enters 0 or 1 directly in
TaxCalc or the year sheet. (2) User chooses "Single" or "MFJ" from a dropdown on
the year sheet; a helper cell (e.g. `=IF(B2="MFJ",1,0)`) feeds TaxCalc. Data
validation with `formula1='"Single,MFJ"'` provides the list. TaxCalc then links to
the helper cell for the numeric value.

**Pre-building two scenarios.** The script can create two scenario columns (B and
C) and two year sheets (2025, 2026), link B to 2025 and C to 2026, and set each
year sheet’s results panel to reference the corresponding TaxCalc column. That
gives two independent scenarios (e.g. compare 2025 vs 2026) without manual
copy/link. After copying B → C, overwrite only the input-block rows (1–11) and
row 12 (Inflation Rate) in column C with the new links; the rest of the column
formulas are already correct.

**Excel-only build vs Numbers-compatible build.** The asbuilt design (per-bracket
scalar rows, literals, nested IF marginal rates) is required for correct behavior
in Apple Numbers after xlsx import. An Excel-only build can use SUMPRODUCT with
INDIRECT over named bracket ranges and XLOOKUP with IF(cond, range_a, range_b)
for lookups; those formulas are valid in Excel but break or mis-evaluate in
Numbers as described in "Numbers/xlsx Compatibility Notes" above. If the workbook
is ever generated only for Excel, the simpler SUMPRODUCT/INDIRECT approach can
be used; if it must open in Numbers, follow the asbuilt pattern.
