# taxcalc Spreadsheet (taxcalc.xlsx)

Formula-only tax calculator workbook per `taxcalc_spreadsheet_plan.md` (workspace root). Targets Apple Numbers v15 and Excel (XLSX).

## Regenerating the workbook

From the e-ORP directory with a venv that has `openpyxl`:

```bash
python scripts/build_taxcalc_spreadsheet.py
```

Output: `taxcalc.xlsx` in the e-ORP directory.

## Contents

- **TaxTables** — Global parameters (InflationRate, LastAdjYear, OBBBA years), StdDeductions table (2025–2026), Ordinary and Cap Gains bracket tables (MFJ and Single) with BracketFloor/BracketWidth columns.
- **TaxCalc** — Calculation engine: scenario columns B (linked to 2025 sheet) and C (linked to 2026 sheet). Input block (rows 1–12), intermediates (14–25), tax block (27–36), results block (38–47) with rounding on monetary totals.
- **2025** — Input panel (Tax Year, Filing Status dropdown, dollar inputs) and results panel referencing TaxCalc column B.
- **2026** — Same layout referencing TaxCalc column C.

## Validation

See Phase 4 in the plan. Cross-check results against Python `tax_calc()` (e.g. from `test/taxcalc.ipynb` or future `taxcalc_core.py`) using the scenarios listed there; round Python output to whole dollars for comparison.
