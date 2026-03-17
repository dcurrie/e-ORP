"""phase4_validation.py — Compute expected values for Phase 4 spreadsheet validation.

Run with:  python phase4_validation.py
Requires taxcalc.py in the same directory or on the path.
"""

from taxcalc import tax_calc

FS_LABEL = {0: "Single", 1: "MFJ"}

scenarios = [
    # (desc, year, fs, net, ira, qcd, intr, dvdd, ssa, stgn, ltgn, carry)
    ("1  Zero income",           2025, 1,       0,     0,    0,    0,    0,     0,  0,      0,      0),
    ("2  Income only, low",      2025, 1,  60_000,     0,    0,    0,    0,     0,  0,      0,      0),
    ("3  Income only, mid",      2025, 1, 100_000,     0,    0,    0,    0,     0,  0,      0,      0),
    ("4  OBBBA phase-in",        2025, 1,       0,     0,    0,    0,    0, 85_000, 0,      0,      0),
    ("5  OBBBA phase-out",       2025, 1, 200_000,     0,    0,    0,    0, 85_000, 0,      0,      0),
    ("6  Cap gains 0%",          2025, 1, 100_000,     0,    0,    0,    0,     0,  0, 50_000,      0),
    ("7  Cap gains 15%",         2025, 1, 200_000,     0,    0,    0,    0,     0,  0, 50_000,      0),
    ("8  Future year 2030",      2030, 1, 100_000,     0,    0,    0,    0,     0,  0,      0,      0),
    ("9  Single filer",          2025, 0,  80_000,     0,    0,    0,    0,     0,  0,      0,      0),
    ("10 Negative carryover",    2025, 1, 100_000,     0,    0,    0,    0,     0,  0, 50_000, -10_000),
    ("11 Sample data",           2026, 1,     960, 73_342, 2000,   75, 1170, 85_735, 0,     0,      0),
]

print(f"{'Scenario':<28} {'Year':>4}  {'FS':<6}  {'Income':>10}  {'CapGains':>10}  "
      f"{'AGI':>10}  {'StdDed':>8}  {'TotalTax':>9}  {'MRateInc':>9}  {'MRateCG':>8}  {'EffRate':>8}")
print("-" * 130)

for row in scenarios:
    (desc, year, fs, net, ira, qcd, intr, dvdd, ssa, stgn, ltgn, carry) = row

    taxable_ssa = ssa * 0.85
    income      = net + ira - qcd + intr + dvdd + taxable_ssa + stgn
    capgains    = ltgn + carry
    agi         = income + capgains
    magi        = agi + ssa * 0.15 + qcd

    (total, mrate, crate, brend, sd, ibtax, cgtax) = tax_calc(year, fs, income, capgains, magi)
    total_r = round(total, 0)

    print(f"{desc:<28} {year:>4}  {FS_LABEL[fs]:<6}  {income:>10,.0f}  {capgains:>10,.0f}  "
          f"{agi:>10,.0f}  {sd:>8,.0f}  {total_r:>9,.0f}  {mrate:>9.0%}  {crate:>8.0%}  "
          f"{total_r/agi:.1%}" if agi > 0 else f"{desc:<28} {year:>4}  {FS_LABEL[fs]:<6}  "
          f"{income:>10,.0f}  {capgains:>10,.0f}  {agi:>10,.0f}  {sd:>8,.0f}  "
          f"{total_r:>9,.0f}  {mrate:>9.0%}  {crate:>8.0%}  {'n/a':>8}")
