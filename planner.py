# planner.py — e-ORP planning datadict, tax tables, RMD, squirrel_map
# Extracted from e-ORP.ipynb for PyWebView desktop app (R3 plan).
# Copyright (c) 2020-5 Doug Currie

import os
import math
import pandas as pd

_here = os.path.dirname(os.path.abspath(__file__))
hd = pd.read_csv(os.path.join(_here, 'historical', 'rates.csv'), index_col='year')
min_hd_year = min(hd.index)
max_hd_year = max(hd.index)
hd = pd.concat([hd,
                hd.copy().set_index(pd.Index(
                    (x + max_hd_year - min_hd_year + 1
                     for x in range(min_hd_year, max_hd_year + 1)),
                    name='year'))])

# Canonical default values for all parameters (widget percent values, not fractions).
PARAM_DEFAULTS = {
    'rorb':  3.0,   'rors':  7.0,   'dvdd':  3.26,
    'infl':  2.0,   'infs':  4.0,
    'frasa': 60.0,  'frasr': 60.0,  'frasd': 60.0,
    'fraba': 40.0,  'frabr': 40.0,  'frabd': 40.0,
    'frhsa': 60.0,  'frhsr': 60.0,  'frhsd': 60.0,
    'frhba': 40.0,  'frhbr': 40.0,  'frhbd': 40.0,
    'spndm': 0,     'incn':  50.0,  'chty':  0.0,
    'xinc':  1.0,   'xinr':  0.0,
    'byear': 2024,
    'aage1': 65,    'aage2': 65,
    'fage1': 92,    'fage2': 92,
    'atax1': 50.0,  'atax2': 50.0,
    'bsis1': 10.0,  'bsis2': 10.0,
    'taxd1': 100.0, 'taxd2': 100.0,
    'roth1': 100.0, 'roth2': 100.0,
    'ssar1': 36.0,  'ssar2': 36.0,
    'refa1': 65,    'refa2': 65,
    'reta1': 70,    'reta2': 65,
    'popt1': 0,     'popt2': 0,
    'pens1': 0.0,   'pens2': 0.0,
    'page1': 65,    'page2': 65,
    'pinh1': 0.0,   'pinh2': 0.0,
    'magib': 42.0,  'magip': 40.0,
    'fstat': 1,     'ftab':  0.0,
    'yr01': 2025, 'yr02': 2025, 'yr03': 2025, 'yr04': 2025,
    'yr05': 2025, 'yr06': 2025, 'yr07': 2025, 'yr08': 2025,
    'pr01': 0, 'pr02': 0, 'pr03': 0, 'pr04': 0,
    'pr05': 0, 'pr06': 0, 'pr07': 0, 'pr08': 0,
    'va01': 0.0, 'va02': 0.0, 'va03': 0.0, 'va04': 0.0,
    'va05': 0.0, 'va06': 0.0, 'va07': 0.0, 'va08': 0.0,
    'tx01': '', 'tx02': '', 'tx03': '', 'tx04': '',
    'tx05': '', 'tx06': '', 'tx07': '', 'tx08': '',
    'glide': 0,     'ssabr': 1,
    'rothl': 'unlimited',
    'hist':  'Use Values Below',
}

# ##############      Tax Data       ##############

# Income tax rates

tax_rates =    [ 0.100,   0.120,   0.220,   0.240,   0.320,   0.350,   0.370 ]

# Capital Gains tax rates

cgt_rates =     [0.000, 0.150, 0.200]

# Tax brackets

# Data from 2025; update by applying inflation rate for projections beyond 2026

base_year_irs_brackets = 2025
last_year_irs_brackets = 2026

# each entry in the ordered list is top of income bracket in 000s

tax_brk_2025 = [[11.925,  48.475, 103.350, 197.300, 250.525, 626.350], # Single
                [23.850,  96.950, 206.700, 394.600, 501.050, 751.600], # MFJ Married Filing Jointly
                [17.000,  64.850, 103.350, 197.300, 250.500, 626.350]] # Head of Household

tax_brk_2026 = [[12.400,  50.400, 105.700, 201.775, 256.225, 640.600], # Single
                [24.800, 100.800, 211.400, 403.550, 512.450, 768.700], # MFJ Married Filing Jointly
                [17.700,  67.450, 105.700, 201.750, 256.200, 640.600]] # Head of Household

cgt_brk_2025 =  [[48.35, 600.05], # Single
                 [96.70, 533.40], # MFJ Married Filing Jointly
                 [64.75, 566.70]] # Head of Household

cgt_brk_2026 =  [[49.45, 545.50], # Single
                 [98.90, 613.70], # MFJ Married Filing Jointly
                 [66.20, 579.60]] # Head of Household

std_ded_2025 = [15.750, 31.500, 23.625] # Single, MFJ, HoH

std_ded_2026 = [16.100, 32.200, 24.150] # Single, MFJ, HoH

std_deductions_ = [std_ded_2025, std_ded_2026]
tax_brackets_   = [tax_brk_2025, tax_brk_2026]
cgt_brackets_   = [cgt_brk_2025, cgt_brk_2026]
# additional standard deduction based on age >= 65 or blindness
add_ded_aged_   = [       1.600,        1.650] 


#
# OBBBA adds an additional $6,000 per person deduction based on age >= 65 through 2028
# taxpayers with modified adjusted gross income over $75,000 ($150,000 for joint filers).
#
addl_obbba_deduction_age65 = 6.000

def bkts_for_year(year, rate_infla):
    infla = 1.0
    if year < base_year_irs_brackets:
        # no tax info for years before 2025; use base year
        year = base_year_irs_brackets
    elif year <= last_year_irs_brackets:
        infla = 1.0
    else:
        infla = (1.0 + rate_infla) ** (year - last_year_irs_brackets)
        year = last_year_irs_brackets
    i = year - base_year_irs_brackets
    return (std_deductions_[i], tax_brackets_[i], cgt_brackets_[i], add_ded_aged_[i], infla)

# filing_status: 0: Single, 1: MFJ, 2: Head of Household
#
def tax_bucket_n_size(year, n, age1, age2, filing_status=1, rate_infla=0.02):
    (std_deductions, tax_brackets, cgt_brackets, addl_deduction_age65, infla) = bkts_for_year(year, rate_infla)
    size = 0.0 # the size of this tax bucket
    if n == 0:
        size = std_deductions[filing_status] * infla
        if age1 >= 65:
            size += addl_deduction_age65 * infla
            #if year <= 2028: size += addl_obbba_deduction_age65
        if filing_status == 1 and age2 >= 65:
            size += addl_deduction_age65 * infla
            #if year <= 2028: size += addl_obbba_deduction_age65
    elif n == 1:
        size = tax_brackets[filing_status][0] * infla
    else:
        size = (tax_brackets[filing_status][n-1] - tax_brackets[filing_status][n-2]) * infla
    return size

def cgt_bucket_n_size(year, n, filing_status=1, rate_infla=0.02):
    (std_deductions, tax_brackets, cgt_brackets, _, infla) = bkts_for_year(year, rate_infla)
    size = 0.0 # the size of this tax bucket
    if n == 0:
        size = cgt_brackets[filing_status][0] * infla
    else:
        size = (tax_brackets[filing_status][1] - tax_brackets[filing_status][0]) * infla
    return size

def obbba_pax_in_year(year, age1, age2):
    return 0 if year > 2028 else ((1 if age1 >= 65 else 0) + (1 if age2 >= 65 else 0))

# IRMAA 2025 rates and brackets

IRMAA_buks = [[106, (133 - 106), (167 - 133), (200 - 167), (500 - 200), 9999], # Single
              [212, (266 - 212), (334 - 266), (400 - 334), (750 - 400), 9999], # MFJ Married Filing Jointly
              [106, (133 - 106), (167 - 133), (200 - 167), (500 - 200), 9999]] # Head of Household

IRMAA_chgs =  [(12 *  185.0        ) / 1000,
               (12 * (259.0 + 13.7)) / 1000,
               (12 * (370.0 + 35.3)) / 1000,
               (12 * (480.9 + 57.0)) / 1000,
               (12 * (591.9 + 78.6)) / 1000,
               (12 * (628.9 + 85.8)) / 1000]

def IRMAA_buk_n_size(year, n, filing_status=1, rate_infla=0.02):
    infla = (1.0 + rate_infla) ** (year - base_year_irs_brackets)
    return IRMAA_buks[filing_status][n] * infla

def IRMAA_chg_n_size(year, n, pax, rate_infla=0.02):
    infla = (1.0 + rate_infla) ** (year - base_year_irs_brackets)
    return pax * (IRMAA_chgs[n] - (0 if n == 0 else IRMAA_chgs[n-1])) * infla

# RMD table

RMD_divisor = [ 27.4, 26.5, 25.5, 24.6, 23.7, 22.9, 22.0, 21.1, 20.2, 19.4, 18.5,
                17.7, 16.8, 16.0, 15.2, 14.4, 13.7, 12.9, 12.2, 11.5, 10.8, 10.1,
                 9.5,  8.9,  8.4,  7.8,  7.3,  6.8,  6.4,  6.0,  5.6,  5.2,  4.9,
                 4.6,  4.3,  4.1,  3.9,  3.7,  3.5,  3.4,  3.3,  3.1,  3.0,  2.9,
                 2.8,  2.7,  2.5,  2.3,  2.0]

# QCD rules

annual_QCD_limit_pp = 108.0 # in base_year_irs_brackets, per person over 70.5

# ############## The Planning Data Dictionary ##############

# The data dictionary (`dd` in the code) is used for inputs to the model, and outputs from the
# model. It is stored at the completion of each projection as a csv file. 
# 
# The `dd` is indexed by plan year, with year 0 being the "base year." Each row of the `dd` 
# represents one plan year, and each column a parameter.
#
# The base year has only inputs to the model. As such, there are unused cells in row 0 of 
# the output columns. These cells are used to hold miscellaneous inputs to the model, such as 
# rates of return and inflation rate. 
# 
# The `squirrel_map` is used to map names of these miscellaneous parameters and column names.
# The `set_nut` and `get_nut` functions are used to access the parameters.

squirrel_map = {'inflation':     'IRMAA-buk0',
                'filing_status': 'tax_bracket',
                'MAGI_prebase':  'QCD_limit',
                'orp_mode':      'IRMAA-buk1',
                'orp_objtv':     'IRMAA-buk2',
                'eoplan_spouse': 'IRMAA-buk3',
                'min_realized':  'IRMAA-buk4',
                'gap_limit':     'IRMAA-buk5',
                'scip_status':   'IRMAA-chg0',
                'scip_stage':    'IRMAA-chg1',
                'scip_gap':      'IRMAA-chg2',
                'scip_time':     'IRMAA-chg3',
                'time_limit':    'IRMAA-chg4',
                'Roth_conv_max': 'IRMAA-chg5',
                'e-ORP_version': 'from_aTax'}

def set_nut(dd, parm, val):
    dd[squirrel_map[parm]][0] = val

def get_nut(dd, parm):
    return dd[squirrel_map[parm]][0]
def make_planning_datadict(p, test_mode='', historical_year_for_rates=None, warn_cb=None):
    """Create the datadict to be used by OORPy, populated from params dict p."""
    def display_warning(msg):
        if warn_cb:
            warn_cb(msg)

    age1 = p['aage1']
    age2 = p['aage2']
    taxd2 = p['taxd2']
    roth2 = p['roth2']

    fstat = p['fstat']

    # Sanity and consistency checks
    
    if fstat != 1 and (roth2 != 0 or taxd2 != 0 or age2 != 0):
        display_warning(f'Filing status is not MFJ but spouse values are not zero')
        display_warning(f'Defaulting Spouse Roth and TaxD from {roth2} {taxd2} to zero.')
        age2 = 0
        taxd2 = 0
        roth2 = 0

    # Base year asset allocation 
    fraba = p['fraba']
    frasa = p['frasa']
    if (fraba + frasa) > 100.0:
        display_warning(f'Percent of savings in stocks {frasa: 2.3f}% + bonds {fraba: 2.3f}% exceeds 100%')
        redu = 100.0 / (fraba + frasa)
        fraba = fraba * redu
        frasa = frasa * redu
        display_warning(f'Reducing percentages proportionally to {frasa: 2.3f}% stocks + {fraba: 2.3f}% bonds')
    frabr = p['frabr']
    frasr = p['frasr']
    if (frabr + frasr) > 100.0:
        display_warning(f'Percent of savings in stocks {frasr: 2.3f}% + bonds {frabr: 2.3f}% exceeds 100%')
        redu = 100.0 / (frabr + frasr)
        frabr = frabr * redu
        frasr = frasr * redu
        display_warning(f'Reducing percentages proportionally to {frasr: 2.3f}% stocks + {frabr: 2.3f}% bonds')
    frabd = p['frabd']
    frasd = p['frasd']
    if (frabd + frasd) > 100.0:
        display_warning(f'Percent of savings in stocks {frasd: 2.3f}% + bonds {frabd: 2.3f}% exceeds 100%')
        redu = 100.0 / (frabd + frasd)
        frabd = frabd * redu
        frasd = frasd * redu
        display_warning(f'Reducing percentages proportionally to {frasd: 2.3f}% stocks + {frabd: 2.3f}% bonds')
    # Horizon year asset allocation 
    frhba = p['frhba']
    frhsa = p['frhsa']
    if (frhba + frhsa) > 100.0:
        display_warning(f'Percent of savings in stocks {frhsa: 2.3f}% + bonds {frhba: 2.3f}% exceeds 100%')
        redu = 100.0 / (frhba + frhsa)
        frhba = frhba * redu
        frhsa = frhsa * redu
        display_warning(f'Reducing percentages proportionally to {frhsa: 2.3f}% stocks + {frhba: 2.3f}% bonds')
    frhbr = p['frhbr']
    frhsr = p['frhsr']
    if (frhbr + frhsr) > 100.0:
        display_warning(f'Percent of savings in stocks {frhsr: 2.3f}% + bonds {frhbr: 2.3f}% exceeds 100%')
        redu = 100.0 / (frhbr + frhsr)
        frhbr = frhbr * redu
        frhsr = frhsr * redu
        display_warning(f'Reducing percentages proportionally to {frhsr: 2.3f}% stocks + {frhbr: 2.3f}% bonds')
    frhbd = p['frhbd']
    frhsd = p['frhsd']
    if (frhbd + frhsd) > 100.0:
        display_warning(f'Percent of savings in stocks {frhsd: 2.3f}% + bonds {frhbd: 2.3f}% exceeds 100%')
        redu = 100.0 / (frhbd + frhsd)
        frhbd = frhbd * redu
        frhsd = frhsd * redu
        display_warning(f'Reducing percentages proportionally to {frhsd: 2.3f}% stocks + {frhbd: 2.3f}% bonds')

    dvdd = p['dvdd']
    rors = p['rors']
    if dvdd > p['rors']:
        display_warning(f'Dividends of {dvdd: 2.3f}% exceed stocks total return {rors: 2.3f}%')
        display_warning(f'Reducing the annual dividend rate to {rors/2: 2.3f}%')
        dvdd = rors/2

    fage1 = p['fage1']
    fage2 = p['fage2']
    if fage1 <= age1:
        display_warning(f'The person 1 planning horizon {fage1} is being extended to provide one planning year')
        fage1 = age1 + 1
    if age2 != 0 and fage2 <= age2:
        display_warning(f'The person 2 planning horizon {fage2} is being extended to provide one planning year')
        display_warning(f'You can use a base year age of 0 to exclude person 2 from the plan')
        fage2 = age2 + 1

    # Planning Horizons
    
    byear = p['byear']
    years = 24
    y_spouse_leaves_plan = years + 1
    if age2 == 0:
        years = 1 + fage1 - age1
        y_spouse_leaves_plan = years + 1
    else:
        years1 = 1 + fage1 - age1
        years2 = 1 + fage2 - age2
        years = max(years1, years2)
        y_spouse_leaves_plan = min(years1, years2)

    idx = range(byear, byear + years)
    
    infl = p['infl'] / 100
    infs = p['infs'] / 100

    def ssa_calc(y):
        """Calculate SSA annual income based on age and initial data from the widgets"""
        e = age1 + y
        j = age2 + y
        reduce_SSAb = (p['ssabr'] == 1)
        e_ssa = p['ssar1'] * ((1.0 + infl) ** (e - p['refa1'])) if e > p['reta1'] else 0.0
        j_ssa = p['ssar2'] * ((1.0 + infl) ** (j - p['refa2'])) if j >= p['reta2'] else 0.0
        t_ssa = j_ssa + e_ssa
        if y >= y_spouse_leaves_plan:
            t_ssa = max(j_ssa, e_ssa)
        return t_ssa * (0.77 if (reduce_SSAb and ((byear + y) >= 2034)) else 1.0)

    def pension_calc(y):
        """Calculate pension annual income based on age and initial data from the widgets"""
        e = age1 + y
        j = age2 + y
        e_p = 0 if (p['popt1'] == 2 or e < p['page1']) else \
                    p['pens1'] if p['popt1'] == 0 else \
                        p['pens1'] * ((1.0 + infl) ** (e - p['page1'])) # use y for number of years of COLA?
        j_p = 0 if (p['popt2'] == 2 or j < p['page2']) else \
                    p['pens2'] if p['popt2'] == 0 else \
                        p['pens2'] * ((1.0 + infl) ** (j - p['page2']))
        # Inherited pension calculation
        e_p = e_p * (1.0 if e <= fage1 else (p['pinh1'] / 100))
        j_p = j_p * (1.0 if j <= fage2 else (p['pinh2'] / 100))
        return (j_p + e_p)

    dd = {'e':              range(age1, age1 + years),
          'j':              range(age2, age2 + years),
          'afterTax':       [0.0 for x in idx],
          #'aTax_basis':     [0.0 for x in idx],
          'e_Roth':         [0.0 for x in idx],
          'e_Taxd':         [0.0 for x in idx],
          'j_Roth':         [0.0 for x in idx],
          'j_Taxd':         [0.0 for x in idx],
          'e_RMD':          [0.0 for x in idx],
          'j_RMD':          [0.0 for x in idx],
          'to_aTax':        [0.0 for x in idx],
          'from_aTax':      [0.0 for x in idx],
          'from_eRoth':     [0.0 for x in idx],
          'from_jRoth':     [0.0 for x in idx],
          'from_eTaxd':     [0.0 for x in idx],
          'from_jTaxd':     [0.0 for x in idx],
          'e_RothConv' :    [0.0 for x in idx],
          'j_RothConv' :    [0.0 for x in idx],
          'SSA_income':     [ssa_calc(y) for y in range(len(idx))],
          'pension_income': [pension_calc(y) for y in range(len(idx))],
          'misc_income':    [max(0,round(p['xinc'] * (1.0 + p['xinr'] / 100) ** y, 3)) for y in range(len(idx))],
          'charity':        [p['chty'] * (1.0 + infl) ** y for y in range(len(idx))],
          'e_Taxd_in':      [0.0 for x in idx],
          'j_Taxd_in':      [0.0 for x in idx],
          'spend_essence':  [0.0 for x in idx],
          'taxfree_income': [0.0 for x in idx],
          'auto_income':    [0.0 for x in idx], # sum of previous five
          'disp_income':    [p['incn'] * (1.0 + infs) ** y for y in range(len(idx))],
          'taxable_income': [0.0 for x in idx],
          'IRMAA':          [0.0 for x in idx],
          'dividends':      [0.0 for x in idx],
          'capgains':       [0.0 for x in idx],
          'caplosss':       [0.0 for x in idx],
          'QCD_limit':      [0.0 for x in idx],
          'QCD':            [0.0 for x in idx],
          'income_tax':     [0.0 for x in idx],
          'tax_bracket':    [0.0 for x in idx],
          'cgains_rate':    [0.0 for x in idx],
          'MAGI':           [0.0 for x in idx],
          # 
          'ror_bonds':      [p['rorb'] / 100 for x in idx],
          'ror_stock':      [p['rors'] / 100 for x in idx],
          'dvd_stock':      [dvdd  / 100 for x in idx],
          'frac_bonds_a':   [fraba / 100 for x in idx],
          'frac_stock_a':   [frasa / 100 for x in idx],
          'frac_bonds_r':   [frabr / 100 for x in idx],
          'frac_stock_r':   [frasr / 100 for x in idx],
          'frac_bonds_d':   [frabd / 100 for x in idx],
          'frac_stock_d':   [frasd / 100 for x in idx],
          # asset allocations for afterTax account
          'aTax__cash':     [0.0 for x in idx],
          'aTax_bonds':     [0.0 for x in idx],
          'aTax_basis':     [0.0 for x in idx],
          'aTax_unrlz':     [0.0 for x in idx],
          'fm_aTax__cash':  [0.0 for x in idx],
          'fm_aTax_bonds':  [0.0 for x in idx],
          'fm_aTax_basis':  [0.0 for x in idx],
          'fm_aTax_unrlz':  [0.0 for x in idx],
          'to_aTax__cash':  [0.0 for x in idx],
          'to_aTax_bonds':  [0.0 for x in idx],
          'to_aTax_basis':  [0.0 for x in idx],
          'to_aTax_unrlz':  [0.0 for x in idx],
          # 
          'e_RMD_factor':  [(0.0 if e < 73 else 1 / RMD_divisor[e - 72])
                            for e in range(age1, age1 + years)],
          'j_RMD_factor':  [(0.0 if j < 73 else 1 / RMD_divisor[j - 72])
                            for j in range(age2, age2 + years)],
          # Tax buckets
          'tax0':          [0.0 for x in idx],
          'tax1':          [0.0 for x in idx],
          'tax2':          [0.0 for x in idx],
          'tax3':          [0.0 for x in idx],
          'tax4':          [0.0 for x in idx],
          'tax5':          [0.0 for x in idx],
          'tax6':          [0.0 for x in idx],
          'cgt0':          [0.0 for x in idx],
          'cgt15':         [0.0 for x in idx],
          'obbba_pax':     [0 for x in idx],
          # IRMAA buckets (brackets and surcharges per bracket)
          'IRMAA-buk0':    [0.0 for x in idx],
          'IRMAA-buk1':    [0.0 for x in idx],
          'IRMAA-buk2':    [0.0 for x in idx],
          'IRMAA-buk3':    [0.0 for x in idx],
          'IRMAA-buk4':    [0.0 for x in idx],
          'IRMAA-buk5':    [0.0 for x in idx],
          'IRMAA-chg0':    [0.0 for x in idx],
          'IRMAA-chg1':    [0.0 for x in idx],
          'IRMAA-chg2':    [0.0 for x in idx],
          'IRMAA-chg3':    [0.0 for x in idx],
          'IRMAA-chg4':    [0.0 for x in idx],
          'IRMAA-chg5':    [0.0 for x in idx],
          'IRMAA-bins':    [0   for x in idx],
          #
          'spend_δ':       [1.0 + infs for y in idx],   
          'surplus':       [p['ftab'] * (1.0 + infl) ** y for y in range(len(idx))],
          'net_pretax':    [0.0 for x in idx],
          'net_postax':    [0.0 for x in idx],
          'year':          idx,
        }

    # squirrel away miscellaneous inputs for reference by solver and to record with the dd'd csv dump
    set_nut(dd, 'inflation'    , infl)
    set_nut(dd, 'filing_status', fstat)
    set_nut(dd, 'eoplan_spouse', y_spouse_leaves_plan)
    set_nut(dd, 'MAGI_prebase' , p['magip'])
    set_nut(dd, 'Roth_conv_max', p['rothl']) # limit Roth Conversions
    set_nut(dd, 'e-ORP_version', 0.5)

    dd['e_Taxd'][0] = p['taxd1']
    dd['j_Taxd'][0] = taxd2
    dd['e_Roth'][0] = p['roth1']
    dd['j_Roth'][0] = roth2
    dd['MAGI'][0]   = p['magib']
    # AAA
    dd['afterTax'][0]   = p['atax1'] + p['atax2']
    dd['aTax_basis'][0] = p['bsis1'] + p['bsis2']
    # loss # limit aTax_basis to stock portion of afterTax
    # loss if dd['aTax_basis'][0] > (dd['afterTax'][0] * frasa / 100):
    # loss     display_warning(f'AfterTax account basis exceeds total stock position {dd["aTax_basis"][0]} > {dd["afterTax"][0] * frasa / 100}')
    # loss     display_warning(f'Ignoring unrealized loss of {dd["aTax_basis"][0] - dd["afterTax"][0] * frasa / 100}')
    # loss dd['aTax_basis'][0] = min(dd['aTax_basis'][0], dd['afterTax'][0] * frasa / 100)
    # or report it as a warning
    if dd['aTax_basis'][0] > (dd['afterTax'][0] * frasa / 100):
        display_warning(f'AfterTax account basis exceeds total stock position {dd["aTax_basis"][0]} > {dd["afterTax"][0] * frasa / 100}')
        display_warning(f'This will result in a starting unrealized gain of {dd["afterTax"][0] * frasa / 100 - dd["aTax_basis"][0]}')
    dd['aTax_bonds'][0] = dd['afterTax'][0] * fraba / 100
    dd['aTax_unrlz'][0] = dd['afterTax'][0] * frasa / 100 - dd['aTax_basis'][0]
    dd['aTax__cash'][0] = dd['afterTax'][0] * (100.0 - frasa - fraba)

    # fix RMD_factors for unequal planning horizons
    if y_spouse_leaves_plan < years:
        for y in range(y_spouse_leaves_plan, years):
            # use remaining spouse's RMD_factor
            if dd['e'][y] > fage1:
                dd['e_RMD_factor'][y] = dd['j_RMD_factor'][y]
            else: # dd['j'][y] > fage2:
                dd['j_RMD_factor'][y] = dd['e_RMD_factor'][y]

    # lump sum pensions
    if p['popt1'] == 2:
        # The pension is added to 'e_Taxd' at the year when e reaches p['page1']
        y = p['page1'] - age1
        if y > 0 and y < years:
            if p['page1'] > fage1:
                display_warning(f"Lump sum pension distribution of {p['pens1']} not in plan horizon at year {y}")
                display_warning(f"Reducing to {p['pens1'] * (p['pinh1'] / 100)}, the spousal benefit")
                dd['e_Taxd_in'][y] = p['pens1'] * (p['pinh1'] / 100)
            else:
                dd['e_Taxd_in'][y] = p['pens1']
        else:
            display_warning(f"Lump sum pension distribution of {p['pens1']} not in plan horizon at year {y}")
    if p['popt2'] == 2:
        # The pension is added to 'j_Taxd' at the year when j reaches p['page2']
        y = p['page2'] - age2
        if y > 0 and y < years:
            if p['page2'] > fage2:
                display_warning(f"Lump sum pension distribution of {p['pens2']} not in plan horizon at year {y}")
                display_warning(f"Reducing to {p['pens2'] * (p['pinh2'] / 100)}, the spousal benefit")
                dd['j_Taxd_in'][y] = p['pens2'] * (p['pinh2'] / 100)
            else:
                dd['j_Taxd_in'][y] = p['pens2']
        else:
            display_warning(f"Lump sum pension distribution of {p['pens2']} not in plan horizon at year {y}")

    # Phases of Retirement
    def pormt_event(year, event, amount):
        if event == 0: # ('None', 0)
            return
        if year <= byear or year > byear + years:
            display_warning(f'Phase of Retirement Event in {year} is beyond planning horizon, and ignored')
            return
        else:
            evy = year - byear
        if event == 1: # ('Ongoing Essential Spending Set To:', 1)
            for y in range(evy,years):
                dd['spend_essence'][y] = amount * (1.0 + infl) ** y
        elif event == 2: # ('One Time Expense:', 2)
            dd['spend_essence'][evy] += amount * (1.0 + infl) ** evy
        elif event == 3: # ('One Time Income:', 3)
            dd['taxfree_income'][evy] += amount * (1.0 + infl) ** evy

    pormt_event(p['yr01'], p['pr01'], p['va01'])
    pormt_event(p['yr02'], p['pr02'], p['va02'])
    pormt_event(p['yr03'], p['pr03'], p['va03'])
    pormt_event(p['yr04'], p['pr04'], p['va04'])
    pormt_event(p['yr05'], p['pr05'], p['va05'])
    pormt_event(p['yr06'], p['pr06'], p['va06'])
    pormt_event(p['yr07'], p['pr07'], p['va07'])
    pormt_event(p['yr08'], p['pr08'], p['va08'])

    # compute spending deltas based on David Blanchett's "Estimating the True Cost of Retirement"
    # and incorporating the input spending inflation rate
    # We adjust Blanchett's formula for the 2012..2025 CPI-E delta
    # June 2012	246.716
    # June 2025	352.769
    # so use 0.0066 * ln(targetspend * 246.716 / 352.769) 
    # = 0.0066 * ln(targetspend) + 0.0066 * ln(246.716 / 352.769)
    # 0.546 + 0.0066 * math.log(246.716 / 352.769) = 0.54364
    
    if p['spndm'] == 1:
        # handle individual vs married
        age1s = dd['e']
        age2s = dd['j'] if age2 != 0 else dd['e']
        for y in range(1,years):
            dd['spend_δ'][y] = dd['spend_δ'][0] \
                                * (1.0 + ((0.00008 * (age1s[y] * age2s[y]))
                                           - (0.0125 * (age1s[y] + age2s[y]) / 2)
                                           - 0.0066 * math.log(dd['disp_income'][0] * 1000.0)
                                           + 0.54364)) # Blanchett's 2013 number was 0.546
            if y == y_spouse_leaves_plan:
                # reduce spending by 25% when spouse leaves plan
                dd['spend_δ'][y] = 0.75 * dd['spend_δ'][y]
            dd['disp_income'][y] = dd['spend_δ'][y] * dd['disp_income'][y-1]

    # compute tax brackets and number of people (pax) qualifying for OBBBA retirement $6000 kicker
    # compute IRMAA buckets and surcharges
    for y in range(1,years):
        fs = fstat if y < y_spouse_leaves_plan else 0 # Single after spouse leaves plan
        ag1 = dd['e'][y] if dd['e'][y] <= fage1 else 0 # use age 0 for spouse who leaves plan
        ag2 = dd['j'][y] if dd['j'][y] <= fage2 else 0 # since the only purpose is to check >= 65 or >= 70
        dd['tax0'][y] = tax_bucket_n_size(dd['year'][y], 0, ag1, ag2, fs, infl)
        dd['tax1'][y] = tax_bucket_n_size(dd['year'][y], 1, ag1, ag2, fs, infl)
        dd['tax2'][y] = tax_bucket_n_size(dd['year'][y], 2, ag1, ag2, fs, infl)
        dd['tax3'][y] = tax_bucket_n_size(dd['year'][y], 3, ag1, ag2, fs, infl)
        dd['tax4'][y] = tax_bucket_n_size(dd['year'][y], 4, ag1, ag2, fs, infl)
        dd['tax5'][y] = tax_bucket_n_size(dd['year'][y], 5, ag1, ag2, fs, infl)
        dd['tax6'][y] = tax_bucket_n_size(dd['year'][y], 6, ag1, ag2, fs, infl)
        dd['cgt0'][y] = dd['tax0'][y] + cgt_bucket_n_size(dd['year'][y], 0, fs, infl)
        dd['cgt15'][y] = cgt_bucket_n_size(dd['year'][y], 1, fs, infl)
        dd['obbba_pax'][y] = obbba_pax_in_year(dd['year'][y], ag1, ag2)
        IRMAA_pax = (1 if ag1 >= 65 else 0) + (1 if ag2 >= 65 else 0)
        fsi = fstat if y < (y_spouse_leaves_plan + 2) else 0 # Single after spouse leaves plan delayed 2 years
        dd['IRMAA-buk0'][y] = IRMAA_buk_n_size(dd['year'][y], 0, fsi, infl)
        dd['IRMAA-buk1'][y] = IRMAA_buk_n_size(dd['year'][y], 1, fsi, infl)
        dd['IRMAA-buk2'][y] = IRMAA_buk_n_size(dd['year'][y], 2, fsi, infl)
        dd['IRMAA-buk3'][y] = IRMAA_buk_n_size(dd['year'][y], 3, fsi, infl)
        dd['IRMAA-buk4'][y] = IRMAA_buk_n_size(dd['year'][y], 4, fsi, infl)
        dd['IRMAA-buk5'][y] = IRMAA_buk_n_size(dd['year'][y], 5, fsi, infl)
        dd['IRMAA-chg0'][y] = IRMAA_chg_n_size(dd['year'][y], 0, IRMAA_pax, infl)
        dd['IRMAA-chg1'][y] = IRMAA_chg_n_size(dd['year'][y], 1, IRMAA_pax, infl)
        dd['IRMAA-chg2'][y] = IRMAA_chg_n_size(dd['year'][y], 2, IRMAA_pax, infl)
        dd['IRMAA-chg3'][y] = IRMAA_chg_n_size(dd['year'][y], 3, IRMAA_pax, infl)
        dd['IRMAA-chg4'][y] = IRMAA_chg_n_size(dd['year'][y], 4, IRMAA_pax, infl)
        dd['IRMAA-chg5'][y] = IRMAA_chg_n_size(dd['year'][y], 5, IRMAA_pax, infl)
        # QCD
        n = 0 if dd['year'][y] < base_year_irs_brackets else dd['year'][y] - base_year_irs_brackets
        QCD_pax = (1 if ag1 >= 70 else 0) + (1 if ag2 >= 70 else 0)
        dd['QCD_limit'][y] = annual_QCD_limit_pp * ((1.0 + infl) ** n) * QCD_pax

    # Asset Allocation Glide Path
    if p['glide'] != 0:
        # linear interpolation: v = v0 + (y - y0) * (vn - v0)/(yn - y0)
        # y0 is 0, yn is years-1, y is y (below), v0 is fraZZ, vn is frhZZ
        yn = years - 1
        dba = frhba - fraba
        dsa = frhsa - frasa
        dbr = frhbr - frabr
        dsr = frhsr - frasr
        dbd = frhbd - frabd
        dsd = frhsd - frasd
        for y in range(1,years):
            dd['frac_bonds_a'][y] = (fraba + y * dba / yn) / 100
            dd['frac_stock_a'][y] = (frasa + y * dsa / yn) / 100
            dd['frac_bonds_r'][y] = (frabr + y * dbr / yn) / 100
            dd['frac_stock_r'][y] = (frasr + y * dsr / yn) / 100
            dd['frac_bonds_d'][y] = (frabd + y * dbd / yn) / 100
            dd['frac_stock_d'][y] = (frasd + y * dsd / yn) / 100

    # the historical_year_for_rates argument, if provided, overrides the user input
    #
    if historical_year_for_rates == None and p['hist'] != 'Use Values Below' and test_mode != '3-peat':
        historical_year_for_rates = int(p['hist'])
    if historical_year_for_rates != None:
        # historical_year_for_rates is the plan base year + 1
        for year, row in hd[:].loc[historical_year_for_rates:historical_year_for_rates+len(dd['year'])-2].iterrows():
            i = year - historical_year_for_rates + 1
            dd['ror_stock'][i] = row['S']
            dd['ror_bonds'][i] = row['B']
            dd['dvd_stock'][i] = row['D']

    ##### TESTING! #####
    if test_mode == 'test_losses':
        for y in range(1,years,2):
            dd['ror_stock'][y] = -0.5 * dd['ror_stock'][y]
    
    return dd