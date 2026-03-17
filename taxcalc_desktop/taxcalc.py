"""taxcalc.py — Tax data and calculation logic (no UI dependencies)"""

# ############## Tax Data ##############

# Married Filing Jointly
tax_brackets_rates_MFJ = {
    2025: [(23.85, 0.100), ( 96.95, 0.120), (206.70, 0.220), (394.60, 0.240), (501.05, 0.320)],
    2026: [(24.80, 0.100), (100.80, 0.120), (211.40, 0.220), (403.55, 0.240), (512.45, 0.320)],
}
std_deductions_MFJ = {
    2025: 31.5 + (2 * 1.60),
    2026: 32.2 + (2 * 1.65),
}
cap_brackets_rates_MFJ = {
    2025: [(96.70, 0.000), (600.05, 0.150), (999.99, 0.200)],
    2026: [(98.90, 0.000), (613.70, 0.150), (999.99, 0.200)],
}

# Single filers
tax_brackets_rates_Single = {
    2025: [(11.925, 0.100), (48.475, 0.120), (103.350, 0.220), (197.300, 0.240), (250.525, 0.320)],
    2026: [(12.400, 0.100), (50.400, 0.120), (105.700, 0.220), (201.775, 0.240), (256.225, 0.320)],
}
std_deductions_Single = {
    2025: 15.75 + (1 * 1.60),
    2026: 16.10 + (1 * 1.65),
}
cap_brackets_rates_Single = {
    2025: [(48.350, 0.000), (533.400, 0.150), (999.99, 0.200)],
    2026: [(49.450, 0.000), (545.500, 0.150), (999.99, 0.200)],
}

# Index 0 = Single, 1 = MFJ  (matches filing_status int used throughout)
tax_data = [
    (tax_brackets_rates_Single, std_deductions_Single, cap_brackets_rates_Single),
    (tax_brackets_rates_MFJ,    std_deductions_MFJ,    cap_brackets_rates_MFJ),
]

FIRST_TAX_YEAR  = 2025
LAST_ADJ_YEAR   = 2026


# ############## Core Logic ##############

def tax_brackets_for_year(year, filing_status, MAGI, rate_infla):
    """Return (std_deduction, brackets_rates, capgains_rates) for the given year.

    All monetary values are in $000s to match e-ORP conventions.
    filing_status: 0 = Single, 1 = MFJ
    """
    oyear = year
    infla = 1.0

    (tax_brackets_rates, std_deductions, cap_brackets_rates) = tax_data[filing_status]

    if year < FIRST_TAX_YEAR:
        raise ValueError(f"No tax bracket data for years before {FIRST_TAX_YEAR}")
    elif year <= LAST_ADJ_YEAR:
        infla = 1.0
    else:
        infla = (1.0 + rate_infla) ** (year - LAST_ADJ_YEAR)
        year  = LAST_ADJ_YEAR

    # OBBBA senior Social Security deduction (2025–2028)
    # Single:  up to $6,000 deduction, phases out 6% above $75k MAGI, gone at $175k
    # MFJ:     up to $12,000 deduction, phases out 6% above $150k MAGI, gone at $250k
    OBBBA_pax = [1, 2][filing_status]
    OBBBA_exc = max(0, MAGI - (OBBBA_pax * 75.0))
    OBBBA_ded = max(0, OBBBA_pax * 6.0 - (OBBBA_pax * 0.06 * OBBBA_exc))
    obbba_applies = 2025 <= oyear <= 2028

    std_deduction = std_deductions[year] * infla + (OBBBA_ded if obbba_applies else 0)

    # Build ordinary income brackets: (low, high, cumulative_tax_at_low, marginal_rate)
    brackets_rates = [(0.0, std_deduction, 0.0, 0.0)]
    last_ceil  = std_deduction
    cummu_tax  = 0.0
    for (b, r) in tax_brackets_rates[year]:
        next_ceil = std_deduction + (b * infla)
        brackets_rates.append((last_ceil, next_ceil, cummu_tax, r))
        cummu_tax += (next_ceil - last_ceil) * r
        last_ceil  = next_ceil

    # Build capital gains brackets
    capgains_rates = [(0.0, std_deduction, 0.0, 0.0)]
    last_ceil = std_deduction
    cummu_tax = 0.0
    for (b, r) in cap_brackets_rates[year]:
        next_ceil = std_deduction + (b * infla)
        capgains_rates.append((last_ceil, next_ceil, cummu_tax, r))
        cummu_tax += (next_ceil - last_ceil) * r
        last_ceil  = next_ceil

    return (std_deduction, brackets_rates, capgains_rates)


def calc_tax(year, rate_infla, income, capgains, MAGI, filing_status=1, tax_bs_for_year=None):
    """Calculate income + capital gains tax.

    All monetary values in $000s.
    Returns (total_tax, mrate, crate, brend, std_deduction, ibtax, cgtax)
    """
    if tax_bs_for_year is None:
        (sd, bs, cs) = tax_brackets_for_year(year, filing_status, MAGI, rate_infla)
    else:
        (sd, bs, cs) = tax_bs_for_year

    ibtax = 0.0
    mrate = 0.0
    brend = 0.0
    cgtax = 0.0
    crate = 0.0

    for (low, high, cummtax, rate) in bs:
        if low <= income <= high:
            ibtax = cummtax + (income - low) * rate
            mrate = rate
            brend = high
            break

    for (low, high, cummtax, rate) in cs:
        if low <= income < high:
            avail    = high - income
            take     = min(avail, capgains)
            cgtax   += take * rate
            crate    = rate
            capgains -= take
            income   += take
            if capgains <= 0:
                break

    return (ibtax + cgtax, mrate, crate, brend, sd, ibtax, cgtax)


def tax_calc(year, filing_status, income, capgains, MAGI):
    """Convenience wrapper: accepts dollar amounts, returns same tuple as calc_tax.

    Converts dollars → $000s internally (e-ORP convention), then converts tax
    results back to dollars before returning.
    Assumes 2% inflation for years beyond known brackets.
    """
    r = calc_tax(
        year, 0.02,
        income   / 1000,
        capgains / 1000,
        MAGI     / 1000,
        filing_status,
    )
    # r[0], r[5], r[6] are monetary ($000s) — scale back to dollars
    # r[1], r[2], r[3], r[4] are rates / bracket boundaries in $000s — leave as-is
    (total, mrate, crate, brend, sd, ibtax, cgtax) = r
    return (total * 1000, mrate, crate, brend * 1000, sd * 1000, ibtax * 1000, cgtax * 1000)
