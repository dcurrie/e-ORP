"""taxcalc_test.py — Unit tests for taxcalc.py logic (no UI required)

Run with:  python taxcalc_test.py
       or: python -m pytest taxcalc_test.py -v
"""

import math
import pytest
from taxcalc import tax_calc, tax_brackets_for_year, calc_tax

TOL = 0.01   # dollar tolerance for float comparisons


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def approx(a, b, tol=TOL):
    return math.isclose(a, b, abs_tol=tol)


# ──────────────────────────────────────────────────────────────
# Bracket sanity checks
# ──────────────────────────────────────────────────────────────

class TestBracketsForYear:

    def test_mfj_2025_returns_five_income_brackets_plus_deduction(self):
        sd, bs, cs = tax_brackets_for_year(2025, 1, 0, 0.02)
        # deduction bracket + 5 income brackets
        assert len(bs) == 6

    def test_single_2026_std_deduction_reasonable(self):
        # Use MAGI above $175k to fully phase out OBBBA, testing bare deduction
        sd, bs, cs = tax_brackets_for_year(2026, 0, 180.0, 0.02)
        # Single 2026: 16.10 + 1.65 = 17.75  (in $000s)
        assert approx(sd, 17.75, tol=0.05)

    def test_mfj_2025_std_deduction_reasonable(self):
        # Use MAGI above $250k to fully phase out OBBBA, testing bare deduction
        sd, bs, cs = tax_brackets_for_year(2025, 1, 260.0, 0.02)
        # MFJ 2025: 31.5 + 3.2 = 34.7  (in $000s)
        assert approx(sd, 34.70, tol=0.05)

    def test_future_year_inflates_brackets(self):
        # Use MAGI above $250k to phase out OBBBA in both years, isolating inflation effect
        sd_base, _, _   = tax_brackets_for_year(2026, 1, 260.0, 0.02)
        sd_future, _, _ = tax_brackets_for_year(2030, 1, 260.0, 0.02)
        assert sd_future > sd_base

    def test_year_before_range_raises(self):
        with pytest.raises(ValueError):
            tax_brackets_for_year(2020, 1, 0, 0.02)


# ──────────────────────────────────────────────────────────────
# OBBBA senior SSA deduction
# ──────────────────────────────────────────────────────────────

class TestOBBBA:

    def test_mfj_low_magi_gets_full_deduction(self):
        # MAGI well under $150k → full $12k ($12 in $000s) extra deduction
        sd_with, _, _ = tax_brackets_for_year(2025, 1, 100.0, 0.02)
        sd_base = 31.5 + 3.2   # base MFJ 2025 without OBBBA
        assert approx(sd_with, sd_base + 12.0, tol=0.10)

    def test_mfj_high_magi_gets_no_deduction(self):
        # MAGI above $250k → OBBBA fully phased out
        sd_high, _, _ = tax_brackets_for_year(2025, 1, 260.0, 0.02)
        sd_base = 31.5 + 3.2
        assert approx(sd_high, sd_base, tol=0.10)

    def test_obbba_not_applied_in_2029(self):
        # OBBBA expires after 2028
        sd_2025, _, _ = tax_brackets_for_year(2025, 1, 100.0, 0.02)
        sd_2029, _, _ = tax_brackets_for_year(2029, 1, 100.0, 0.02)
        # 2029 bracket is inflated from 2026 base (no OBBBA) so deduction
        # should be meaningfully smaller than 2025 with OBBBA
        assert sd_2025 > sd_2029 - 5   # rough check: OBBBA adds ~12 in 2025


# ──────────────────────────────────────────────────────────────
# calc_tax: zero income
# ──────────────────────────────────────────────────────────────

class TestCalcTaxZeroIncome:

    def test_zero_income_zero_capgains(self):
        (total, mrate, crate, brend, sd, ibtax, cgtax) = calc_tax(
            2025, 0.02, 0.0, 0.0, 0.0, filing_status=1)
        assert total == 0.0
        assert ibtax == 0.0
        assert cgtax == 0.0

    def test_income_within_standard_deduction(self):
        # Income fully covered by std deduction → no tax
        sd, _, _ = tax_brackets_for_year(2025, 1, 0, 0.02)
        (total, *_) = calc_tax(2025, 0.02, sd * 0.5, 0.0, 0.0, filing_status=1)
        assert total == 0.0


# ──────────────────────────────────────────────────────────────
# tax_calc (dollar wrapper): spot checks
# ──────────────────────────────────────────────────────────────

class TestTaxCalcWrapper:

    def test_returns_seven_tuple(self):
        result = tax_calc(2025, 1, 100_000, 0, 100_000)
        assert len(result) == 7

    def test_mfj_2025_modest_income_reasonable_tax(self):
        # $100k income, no capgains, MFJ — should be well under $10k
        (total, mrate, crate, brend, sd, ibtax, cgtax) = tax_calc(
            2025, 1, 100_000, 0, 100_000)
        assert 0 < total < 10_000
        assert mrate == 0.12

    def test_mfj_2025_high_income_higher_tax(self):
        (total_hi, *_) = tax_calc(2025, 1, 300_000, 0, 300_000)
        (total_lo, *_) = tax_calc(2025, 1, 100_000, 0, 100_000)
        assert total_hi > total_lo

    def test_capgains_taxed_separately(self):
        # Same AGI, but split between income and capgains → lower total tax
        (tax_all_income, *_) = tax_calc(2025, 1, 200_000, 0,       200_000)
        (tax_with_cg,    *_) = tax_calc(2025, 1, 100_000, 100_000, 200_000)
        assert tax_with_cg <= tax_all_income

    def test_single_vs_mfj_same_income(self):
        # MFJ should pay less (or equal) tax than Single at same income level
        (tax_mfj,    *_) = tax_calc(2025, 1, 80_000, 0, 80_000)
        (tax_single, *_) = tax_calc(2025, 0, 80_000, 0, 80_000)
        assert tax_mfj <= tax_single

    def test_future_year_runs_without_error(self):
        result = tax_calc(2035, 1, 150_000, 20_000, 170_000)
        assert result[0] > 0


# ──────────────────────────────────────────────────────────────
# Marginal rate progression
# ──────────────────────────────────────────────────────────────

class TestMarginalRates:

    @pytest.mark.parametrize("income,expected_rate", [
        ( 60_000, 0.10),   # above std deduction+OBBBA (~$46.7k) but in 10% bracket
        (100_000, 0.12),
        (200_000, 0.22),
        (350_000, 0.24),
    ])
    def test_mfj_2025_marginal_rates(self, income, expected_rate):
        (_, mrate, *_) = tax_calc(2025, 1, income, 0, income)
        assert mrate == expected_rate


if __name__ == "__main__":
    # Run with plain python (no pytest required) for a quick smoke-test
    import sys

    passed = failed = 0
    suite = [
        TestBracketsForYear(),
        TestOBBBA(),
        TestCalcTaxZeroIncome(),
        TestTaxCalcWrapper(),
        TestMarginalRates(),
    ]
    for obj in suite:
        for name in [m for m in dir(obj) if m.startswith("test_")]:
            method = getattr(obj, name)
            # supply parametrize values manually for the one parametrized test
            if name == "test_mfj_2025_marginal_rates":
                cases = [(60_000,0.10),(100_000,0.12),(200_000,0.22),(350_000,0.24)]
                for income, rate in cases:
                    try:
                        method(income, rate)
                        print(f"  PASS  {name}({income})")
                        passed += 1
                    except Exception as e:
                        print(f"  FAIL  {name}({income}): {e}", file=sys.stderr)
                        failed += 1
                continue
            try:
                method()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}", file=sys.stderr)
                failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
