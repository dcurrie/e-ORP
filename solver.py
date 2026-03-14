# solver.py — e-ORP SCIP optimizer and high-level run functions
# Extracted from e-ORP.ipynb for PyWebView desktop app (R3 plan).
# Copyright (c) 2020-5 Doug Currie

from planner import make_planning_datadict, hd, set_nut, get_nut, squirrel_map
import statistics
import pandas as pd
import pyscipopt


VARS = [
    # Initial Values for year 0
    'afterTax',
    'e_Roth',
    'e_Taxd',
    'j_Roth',
    'j_Taxd',
    # AAA
    'aTax__cash',
    'aTax_bonds',
    'aTax_basis',
    'aTax_unrlz_gain',
    'aTax_unrlz_loss',
    # Configuration Values
    'disp_income',   #  year 0 (for option A & B); year 1..N for option A
    # LP Vars for years 1..N
    'discretionary_spend',
    'from_eRoth',
    'from_jRoth',
    'from_eTaxd',
    'from_jTaxd',
    'from_aTax',
    'to_aTax',
    'fm_aTax__cash',
    'fm_aTax_bonds',
    'fm_aTax_basis',
    'fm_aTax_unrlz',
    'to_aTax__cash',
    'to_aTax_bonds',
    'to_aTax_basis',
    'to_aTax_unrlz',
    'fm_aTax_unrlz_gain',
    'fm_aTax_unrlz_loss',
    'fm_aTax_frac',
    # Intermediate Calculated values
    'e_RMD',
    'j_RMD',
    'QCD',
    'nQCD',
    'auto_income', #  = e_RMD + j_RMD + SSA_income + misc_income + pension_income
    'e_RothConv',
    'j_RothConv',
    'taxable_income',
    'dividends',
    'capgains',
    'caplosss',
    'caplossz',
    'tax0',  # 0% income tax bucket
    'tax1',  # next (10%) income tax bucket, ...
    'tax2',
    'tax3',
    'tax4',
    'tax5',
    'tax6',
    'tax7',
    'taxb',  # OBBBA extra retirement deduction
    'MAGI',
    'IRMAA',
    'obbba_exc',
    'cgt0',  #  0% capital gains tax bucket
    'cgt15', # 15% capital gains tax bucket, ...
    'cgt20',
    #'ncgt0', # 0% offset capital gains tax bucket (filled with ordinary income), ...
    #'ncgt15',
    #'ncgt20',
    'ncgt', # not-capital-gains portion of highest income bucket 
    'income_tax',
    'net_pretax'
]

BINS = [
    'IRMAA-bin0', # IRMAA levels
    'IRMAA-bin1',
    'IRMAA-bin2',
    'IRMAA-bin3',
    'IRMAA-bin4',
    'IRMAA-bin5',
    'cgbin15', # taxable_income >= 15% capital gains bracket
    'cgbin20', # taxable_income >= 20% capital gains bracket
]

def lop_to_cents(x):
    """Truncate model (float) data to 5 decimal digits"""
    if x == None:
        return -0.0 # unique value to identify unconstrained/unused values
    else:
        return max(0,round(x, 3))

def lop_to_cents_signed(x):
    """Truncate model (float) data to 5 decimal digits"""
    if x == None:
        return -0.0 # unique value to identify unconstrained/unused values
    else:
        return round(x, 3)

def oorplp(dd, mode, objective, tout, glim):
    """Run OORPyLP with specified objective, 'net_pretax', 'net_postax', 
        or a non-string value for maximum DI with a specified residual
    """
    # mode: 0: default, 1: no capital losses 2: no capgains basis averaging 3: neither 4: full slow mode
    # the default mode 0 is the same as mode 3: neither capital losses nor cost basis averaging
    no_capgains_constraints = (mode == 0) or (mode == 2) or (mode == 3)
    no_capital_losses = (mode == 0) or (mode == 1) or (mode == 3)
    #
    # (no widget output in desktop app; stdout is redirected by worker)
    # config values from UI
    def rori_r(y):
        return 1.0 + (dd['ror_stock'][y] * dd['frac_stock_r'][y] + dd['ror_bonds'][y] * dd['frac_bonds_r'][y])
    def rori_d(y):
        return 1.0 + (dd['ror_stock'][y] * dd['frac_stock_d'][y] + dd['ror_bonds'][y] * dd['frac_bonds_d'][y])
    # the model
    scip = pyscipopt.Model()
    # scip.setEmphasis(pyscipopt.SCIP_PARAMEMPHASIS.HARDLP) # ? NUMERICS, PHASEFEAS, CPSOLVER no help
    # set up problem
    YRS = len(dd['e']) - 1 # number of years of projection from base year 0
    IDX = range(0,YRS+1)   # 0 (base year) .. YRS (final year)
    ftab = dd['surplus'][YRS]
    vars = {}
    for v in VARS:
        vars[v] = {}
        for i in IDX:
            vars[v][i] = scip.addVar(vtype='C', name=f"Proje_{v}_{i}")
    for v in BINS:
        vars[v] = {}
        for i in IDX:
            vars[v][i] = scip.addVar(vtype='B', name=f"Proje_{v}_{i}")

    def MAGI_m2(y):
        # get MAGI for two years before y
        if y < 2:
            return get_nut(dd, 'MAGI_prebase') # MAGI for year before base year
        elif y == 2:
            return dd['MAGI'][0]    # MAGI for base year
        else:
            return vars['MAGI'][y-2]

    max_tab = 18316.2 # size of total account for "the 1%"
    # limit max_tab based on total starting account value
    bas_tab = dd['e_Roth'][0] + dd['j_Roth'][0] + dd['afterTax'][0] + dd['e_Taxd'][0] + dd['j_Taxd'][0]
    bas_tab = max(bas_tab, ftab)
    if bas_tab * 2.0 < max_tab:
        max_tab = bas_tab * 2.0
    max_xfr = max_tab / 6    # this is the max RMD at age 101 (was 3052.7)
    max_inc = max_xfr * 2.25 # fudge for adding in other income (was 6969.7)
    max_tax = 0.37 * max_inc # was 2187.2
    #display_warning(f'using upper bounds: {max_tab: 4.3f}, {max_xfr: 4.3f}, {max_inc: 4.3f}, {max_tax: 4.3f}')
    
    for y in range(1,YRS+1):
        infl = (1.0 + get_nut(dd, 'inflation')) ** y
        # Set bounds on variables for non-linear version
        scip.chgVarLb(vars['afterTax'][y], 0.000375) # less than $1
        scip.chgVarLb(vars['to_aTax_unrlz'][y], -max_xfr * infl)
        # Upper bounds
        scip.chgVarUb(vars[      'afterTax'][y], max_tab * infl)
        scip.chgVarUb(vars[    'aTax_basis'][y], max_tab * infl)
        scip.chgVarUb(vars['aTax_unrlz_gain'][y],max_tab * infl)
        scip.chgVarUb(vars['aTax_unrlz_loss'][y],max_tab * infl)
        scip.chgVarUb(vars[    'aTax_bonds'][y], max_tab * infl)
        scip.chgVarUb(vars[    'aTax__cash'][y], max_tab * infl)
        scip.chgVarUb(vars[        'e_Roth'][y], max_tab * infl)
        scip.chgVarUb(vars[        'e_Taxd'][y], max_tab * infl)
        scip.chgVarUb(vars[        'j_Roth'][y], max_tab * infl)
        scip.chgVarUb(vars[        'j_Taxd'][y], max_tab * infl)
        scip.chgVarUb(vars[    'net_pretax'][y], max_tab * infl)
        scip.chgVarUb(vars[    'e_RothConv'][y], max_tab * infl)
        scip.chgVarUb(vars[    'j_RothConv'][y], max_tab * infl)
        scip.chgVarUb(vars[         'e_RMD'][y], max_xfr * infl)
        scip.chgVarUb(vars[         'j_RMD'][y], max_xfr * infl)
        scip.chgVarUb(vars[    'from_eRoth'][y], max_xfr * infl)
        scip.chgVarUb(vars[    'from_jRoth'][y], max_xfr * infl)
        scip.chgVarUb(vars[    'from_eTaxd'][y], max_xfr * infl)
        scip.chgVarUb(vars[    'from_jTaxd'][y], max_xfr * infl)
        scip.chgVarUb(vars[     'from_aTax'][y], max_xfr * infl)
        scip.chgVarUb(vars[       'to_aTax'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'fm_aTax__cash'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'fm_aTax_bonds'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'fm_aTax_basis'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'fm_aTax_unrlz'][y], max_xfr * infl)
        scip.chgVarUb(vars[  'fm_aTax_frac'][y],     1.0)
        scip.chgVarUb(vars[ 'to_aTax__cash'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'to_aTax_bonds'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'to_aTax_basis'][y], max_xfr * infl)
        scip.chgVarUb(vars[ 'to_aTax_unrlz'][y], max_xfr * infl)
        scip.chgVarUb(vars[   'disp_income'][y], max_inc * infl)
        scip.chgVarUb(vars[   'auto_income'][y], max_inc * infl)
        scip.chgVarUb(vars['taxable_income'][y], max_inc * infl)
        scip.chgVarUb(vars[          'MAGI'][y], max_inc * infl)
        scip.chgVarUb(vars[      'capgains'][y], max_xfr * infl)
        scip.chgVarUb(vars[      'caplosss'][y], max_xfr * infl)
        scip.chgVarUb(vars[      'caplossz'][y], max_xfr * infl)
        scip.chgVarUb(vars[     'dividends'][y],   500.0 * infl)
        scip.chgVarUb(vars[    'income_tax'][y], max_tax * infl)
        scip.chgVarUb(vars[         'IRMAA'][y],    34.0 * infl)
        scip.chgVarUb(vars[          'taxb'][y],    20.0 * infl)
        scip.chgVarUb(vars[          'tax0'][y],    50.0 * infl)
        scip.chgVarUb(vars[          'tax1'][y],    30.0 * infl)
        scip.chgVarUb(vars[          'tax2'][y],    80.0 * infl)
        scip.chgVarUb(vars[          'tax3'][y],   120.0 * infl)
        scip.chgVarUb(vars[          'tax4'][y],   220.0 * infl)
        scip.chgVarUb(vars[          'tax5'][y],   120.0 * infl)
        scip.chgVarUb(vars[          'tax6'][y],   280.0 * infl)
        scip.chgVarUb(vars[          'tax7'][y], max_inc * infl)
        scip.chgVarUb(vars[     'obbba_exc'][y], max_inc * infl)
        scip.chgVarUb(vars[          'cgt0'][y],   140.0 * infl)
        scip.chgVarUb(vars[         'cgt15'][y],    80.0 * infl)
        scip.chgVarUb(vars[         'cgt20'][y], max_inc * infl)
        scip.chgVarUb(vars[          'ncgt'][y],   max_inc * infl)
        #scip.chgVarUb(vars[         'ncgt0'][y],   140.0 * infl)
        #scip.chgVarUb(vars[        'ncgt15'][y],    80.0 * infl)
        #scip.chgVarUb(vars[        'ncgt20'][y], max_inc * infl)
        scip.chgVarUb(vars[           'QCD'][y],   220.0 * infl)
        scip.chgVarUb(vars[          'nQCD'][y],   220.0 * infl)
        
    # Objective
    if isinstance(objective, str):
        scip.setObjective(vars[objective][YRS], sense="maximize")
        # subject to:
        for y in range(1,YRS+1):
            scip.addCons(dd['disp_income'][y] == vars['disp_income'][y])
    else:
        #scip.setObjective(vars['disp_income'][0], sense="maximize") # 'Maximize Spend'
        scip.setObjective(vars['discretionary_spend'][0], sense="maximize") # 'Maximize Spend'
        # subject to growth and minimum residual:
        scip.addCons(vars['net_pretax'][YRS] >= ftab) # 'Minimum Residual'
        # mantain spending curve
        for y in range(1,YRS+1):
            scip.addCons(vars['discretionary_spend'][y] == dd['spend_δ'][y] * vars['discretionary_spend'][y-1])
            scip.addCons(vars['disp_income'][y] == vars['discretionary_spend'][y] + dd['spend_essence'][y])
    
    # Initial Values Constraints
    scip.addCons(vars['e_Roth'][0] == dd['e_Roth'][0])
    scip.addCons(vars['e_Taxd'][0] == dd['e_Taxd'][0])
    scip.addCons(vars['j_Roth'][0] == dd['j_Roth'][0])
    scip.addCons(vars['j_Taxd'][0] == dd['j_Taxd'][0])
    scip.addCons(vars['afterTax'][0] == dd['afterTax'][0])
    scip.addCons(vars['aTax__cash'][0] == dd['aTax__cash'][0])
    scip.addCons(vars['aTax_bonds'][0] == dd['aTax_bonds'][0])
    scip.addCons(vars['aTax_basis'][0] == dd['aTax_basis'][0])
    if dd['aTax_unrlz'][0] < 0:
        scip.addCons(vars['aTax_unrlz_gain'][0] == 0)
        if no_capital_losses:
            scip.addCons(vars['aTax_unrlz_loss'][0] == 0) # make_planning_datadict will have issued a warning
        else:
            scip.addCons(vars['aTax_unrlz_loss'][0] == -dd['aTax_unrlz'][0])
    else:
        scip.addCons(vars['aTax_unrlz_loss'][0] == 0)
        scip.addCons(vars['aTax_unrlz_gain'][0] == dd['aTax_unrlz'][0])

    # Calculation Constraints
    for y in range(1,YRS+1):
        scip.addCons(vars['e_RMD'][y] == dd['e_RMD_factor'][y] * vars['e_Taxd'][y-1])
        scip.addCons(vars['j_RMD'][y] == dd['j_RMD_factor'][y] * vars['j_Taxd'][y-1])

        # AfterTax asset allocations
        scip.addCons(vars['afterTax'][y]  == vars['aTax__cash'][y] + vars['aTax_bonds'][y] + vars['aTax_basis'][y]  \
                                             + vars['aTax_unrlz_gain'][y] - vars['aTax_unrlz_loss'][y])
        scip.addCons(vars['from_aTax'][y] == vars['fm_aTax__cash'][y] + vars['fm_aTax_bonds'][y] \
                                             + vars['fm_aTax_basis'][y] \
                                             + vars['fm_aTax_unrlz_gain'][y] - vars['fm_aTax_unrlz_loss'][y])
        scip.addCons(vars['to_aTax'][y]   == vars['to_aTax__cash'][y] + vars['to_aTax_bonds'][y] \
                                             + vars['to_aTax_basis'][y] + vars['to_aTax_unrlz'][y])
        
        scip.addCons(vars['afterTax'][y] * dd['frac_stock_a'][y] \
                                 == vars['aTax_basis'][y] + vars['aTax_unrlz_gain'][y] - vars['aTax_unrlz_loss'][y])
        scip.addCons(vars['afterTax'][y] * dd['frac_bonds_a'][y] == vars['aTax_bonds'][y])
        
        scip.addCons(vars['fm_aTax__cash'][y] <= vars['aTax__cash'][y-1])
        scip.addCons(vars['fm_aTax_bonds'][y] <= vars['aTax_bonds'][y-1])

        if no_capgains_constraints:
            scip.addCons(vars['fm_aTax_basis'][y]      <= vars['aTax_basis'][y-1])
            scip.addCons(vars['fm_aTax_unrlz_gain'][y] <= vars['aTax_unrlz_gain'][y-1])
            scip.addCons(vars['fm_aTax_unrlz_loss'][y] <= vars['aTax_unrlz_loss'][y-1])
        else:
            scip.addCons(vars['fm_aTax_basis'][y]      == vars['fm_aTax_frac'][y] * vars['aTax_basis'][y-1])
            scip.addCons(vars['fm_aTax_unrlz_gain'][y] == vars['fm_aTax_frac'][y] * vars['aTax_unrlz_gain'][y-1])
            scip.addCons(vars['fm_aTax_unrlz_loss'][y] == vars['fm_aTax_frac'][y] * vars['aTax_unrlz_loss'][y-1])

        scip.addCons(vars['aTax_unrlz_gain'][y] - vars['aTax_unrlz_loss'][y] \
                         == (vars['aTax_unrlz_gain'][y-1] - vars['fm_aTax_unrlz_gain'][y]) \
                          - (vars['aTax_unrlz_loss'][y-1] - vars['fm_aTax_unrlz_loss'][y]) \
                          + vars['to_aTax_unrlz'][y])
            
        if no_capital_losses:
            scip.addCons(vars['aTax_unrlz_loss'][y] == 0)
        else:
            # unfortuately, the first form using a disjunction leads to symmetry problems in SCIP:
            #scip.addConsDisjunction([vars['aTax_unrlz_gain'][y] == 0, vars['aTax_unrlz_loss'][y] == 0])
            # so I use the multiplication instead:
            scip.addCons(vars['aTax_unrlz_gain'][y] * vars['aTax_unrlz_loss'][y] == 0)

        scip.addCons(vars['aTax__cash'][y] == vars['aTax__cash'][y-1] + vars['to_aTax__cash'][y] - vars['fm_aTax__cash'][y])
        scip.addCons(vars['aTax_bonds'][y] == vars['aTax_bonds'][y-1] + vars['to_aTax_bonds'][y] - vars['fm_aTax_bonds'][y])
        scip.addCons(vars['aTax_basis'][y] == vars['aTax_basis'][y-1] + vars['to_aTax_basis'][y] - vars['fm_aTax_basis'][y])
                
        scip.addCons(vars['to_aTax_unrlz'][y] == (dd['ror_stock'][y] - dd['dvd_stock'][y]) \
                                                     * (vars['aTax_basis'][y-1] \
                                                        + vars['aTax_unrlz_gain'][y-1]
                                                        - vars['aTax_unrlz_loss'][y-1]))
        
        scip.addCons(vars['dividends'][y] == dd['ror_bonds'][y] * vars['aTax_bonds'][y-1] \
                                             + dd['dvd_stock'][y] * (vars['aTax_basis'][y-1] \
                                                                    + vars['aTax_unrlz_gain'][y-1]
                                                                    - vars['aTax_unrlz_loss'][y-1]))
        
        scip.addCons(vars['capgains'][y] == vars['fm_aTax_unrlz_gain'][y])
        
        if no_capital_losses:
            scip.addCons(vars['caplosss'][y] == 0.0)
        else:
            scip.addCons(vars['caplosss'][y] + vars['caplossz'][y] == vars['fm_aTax_unrlz_loss'][y])
            scip.addCons(vars['caplosss'][y] <= 3.0)

        # Roth Conversions)
        scip.addCons(vars['e_RothConv'][y] <= vars['e_Taxd'][y-1])
        scip.addCons(vars['j_RothConv'][y] <= vars['j_Taxd'][y-1])
        rlim = get_nut(dd, 'Roth_conv_max')
        if rlim != 'unlimited':
            scip.addConsDisjunction([vars['e_RothConv'][y] + vars['j_RothConv'][y] == 0.0,
                                     # originally this was just: vars[rlim][y] == 0.0
                                     # but SCIP was too clever, and sometimes used the next highest tax bracket!
                                     #  ('Limit: 10% tax bracket', 'tax2'),
                                     #  ('Limit: 12% tax bracket', 'tax3'),
                                     #  ('Limit: 22% tax bracket', 'tax4'),
                                     # there must be a better way, but a working hack:
                                     vars['tax7'][y] == 0.0 if rlim == 'tax7' else
                                     vars['tax7'][y] + vars['tax6'][y] == 0.0 if rlim == 'tax6' else
                                     vars['tax7'][y] + vars['tax6'][y] + vars['tax5'][y] == 0.0 if rlim == 'tax5' else
                                     vars['tax7'][y] + vars['tax6'][y] + vars['tax5'][y] + vars['tax4'][y] == 0.0 \
                                        if rlim == 'tax4' else
                                     vars['tax7'][y] + vars['tax6'][y] + vars['tax5'][y] + vars['tax4'][y] \
                                         + vars['tax3'][y] + vars['cgbin15'][y] == 0.0 \
                                        if rlim == 'tax3' else
                                     vars['tax7'][y] + vars['tax6'][y] + vars['tax5'][y] + vars['tax4'][y] \
                                         + vars['tax3'][y] + vars['tax2'][y] + vars['cgt15'][y] == 0.0 \
                                        if rlim == 'tax2' else
                                     vars['tax7'][y] + vars['tax6'][y] + vars['tax5'][y] + vars['tax4'][y] \
                                         + vars['tax3'][y] + vars['tax2'][y] + vars['tax1'][y] \
                                         + vars['cgt15'][y] == 0.0 \
                                        if rlim == 'tax1' else
                                     vars['tax7'][y] + vars['tax6'][y] + vars['tax5'][y] + vars['tax4'][y] \
                                         + vars['tax3'][y] + vars['tax2'][y] + vars['tax1'][y] + vars['tax0'][y] \
                                         + vars['cgt15'][y] + vars['cgt0'][y] == 0.0 \
                                        if rlim == 'tax0' else
                                     vars[rlim][y] == 0.0
                                   ])

        # QCD Calculation
        scip.addCons(vars['QCD'][y] + vars['nQCD'][y] == dd['charity'][y])
        scip.addCons(vars['QCD'][y] <= dd['QCD_limit'][y])
        scip.addCons(vars['QCD'][y] <= vars['e_RMD'][y] + vars['j_RMD'][y] \
                                       + vars['from_eTaxd'][y] + vars['from_jTaxd'][y])

        # IRMAA Calculation
        # IRMAA-pax: 0, 1, 2 # individuals over 65
        # IRMAA-buk: income tier increments, 0..5
        # IRMAA-bin: binary indicator if tier is reached, 0..5
        # IRMAA-chg: (sur-)charge per tier, 0..5
        # MAGI <= IRMAA-bin[0] * IRMAA-buk[0] + ... IRMAA-bin[5] * IRMAA-buk[5]
        # IRMAA-bin[0] >= IRMAA-bin[1] >= ... IRMAA-bin[5] # fill the lower bins first
        # IRMAA = IRMAA-pax * (IRMAA-chg[n] * IRMAA-bin[n] for n in 0..5) 
        # dd has precomputed IRMAA-pax * IRMAA-chg
        
        scip.addCons(vars['IRMAA-bin0'][y] >= vars['IRMAA-bin1'][y])
        scip.addCons(vars['IRMAA-bin1'][y] >= vars['IRMAA-bin2'][y])
        scip.addCons(vars['IRMAA-bin2'][y] >= vars['IRMAA-bin3'][y])
        scip.addCons(vars['IRMAA-bin3'][y] >= vars['IRMAA-bin4'][y])
        scip.addCons(vars['IRMAA-bin4'][y] >= vars['IRMAA-bin5'][y])
        
        scip.addCons(MAGI_m2(y) <= vars['IRMAA-bin0'][y] * dd['IRMAA-buk0'][y] \
                                 + vars['IRMAA-bin1'][y] * dd['IRMAA-buk1'][y] \
                                 + vars['IRMAA-bin2'][y] * dd['IRMAA-buk2'][y] \
                                 + vars['IRMAA-bin3'][y] * dd['IRMAA-buk3'][y] \
                                 + vars['IRMAA-bin4'][y] * dd['IRMAA-buk4'][y] \
                                 + vars['IRMAA-bin5'][y] * dd['IRMAA-buk5'][y] \
                                 + 0.00001) # this <= $0.01 fudge factor seems to rescue some otherwise non-converging soltions

        scip.addCons(vars['IRMAA'][y] == vars['IRMAA-bin0'][y] * dd['IRMAA-chg0'][y] \
                                      + vars['IRMAA-bin1'][y] * dd['IRMAA-chg1'][y] \
                                      + vars['IRMAA-bin2'][y] * dd['IRMAA-chg2'][y] \
                                      + vars['IRMAA-bin3'][y] * dd['IRMAA-chg3'][y] \
                                      + vars['IRMAA-bin4'][y] * dd['IRMAA-chg4'][y] \
                                      + vars['IRMAA-bin5'][y] * dd['IRMAA-chg5'][y]) 

        # Income Calculation

        scip.addCons(vars['auto_income'][y] == vars['e_RMD'][y] + vars['j_RMD'][y] + vars['dividends'][y] \
                                                + dd['misc_income'][y] + dd['SSA_income'][y] \
                                                + dd['taxfree_income'][y] \
                                                + dd['pension_income'][y] - vars['IRMAA'][y])

        scip.addCons(vars['taxable_income'][y] == vars['e_RMD'][y] + vars['j_RMD'][y] + vars['dividends'][y] \
                                                + dd["misc_income"][y] + 0.85 * dd["SSA_income"][y] - vars['caplosss'][y] \
                                                + vars['from_eTaxd'][y] + vars['from_jTaxd'][y] - vars['QCD'][y] \
                                                + dd['pension_income'][y] + vars['e_RothConv'][y] + vars['j_RothConv'][y])

        # Spending
        
        scip.addCons(vars['disp_income'][y] == vars['auto_income'][y] + vars['from_aTax'][y] \
                                            + vars['from_eTaxd'][y] + vars['from_jTaxd'][y] \
                                            + vars['from_eRoth'][y] + vars['from_jRoth'][y] \
                                            - vars['income_tax'][y] - vars['to_aTax'][y])

        # Taxation - XXX qualified dividends?

        # OBBBA
        # MAGI used, so need to add the non-taxable portion of SSA
        # OBBBA-pax: 0, 1, 2 # individuals over 65
        # OBBBA_exc: == (MAGI - (OBBBA-pax * 75.000)
        # OBBBA-ded: <= OBBBA-pax * 6.000 - (OBBBA-pax * 0.06 * OBBBA_exc))

        scip.addCons(vars['MAGI'][y] == vars['e_RMD'][y] + vars['j_RMD'][y] + vars['dividends'][y] \
                                            + dd["misc_income"][y] + dd['pension_income'][y] + dd["SSA_income"][y] \
                                            + vars['from_eTaxd'][y] + vars['from_jTaxd'][y] - vars['caplosss'][y] \
                                            + vars['capgains'][y] + vars['e_RothConv'][y] + vars['j_RothConv'][y])
        
        scip.addCons(vars['obbba_exc'][y] >= vars['MAGI'][y] - dd['obbba_pax'][y] * 75.0) # lower bound is 0

        scip.addCons(vars['tax0'][y] <= dd['tax0'][y])
        scip.addCons(vars['tax1'][y] <= dd['tax1'][y])
        scip.addCons(vars['tax2'][y] <= dd['tax2'][y])
        scip.addCons(vars['tax3'][y] <= dd['tax3'][y])
        scip.addCons(vars['tax4'][y] <= dd['tax4'][y])
        scip.addCons(vars['tax5'][y] <= dd['tax5'][y])
        scip.addCons(vars['tax6'][y] <= dd['tax6'][y])
        scip.addCons(vars['taxb'][y] <= dd['obbba_pax'][y] * addl_obbba_deduction_age65 \
                                        - (dd['obbba_pax'][y] * 0.06 * vars['obbba_exc'][y]))

        scip.addCons(vars['taxable_income'][y] == vars['tax0'][y] \
                                                + vars['taxb'][y] \
                                                + vars['tax1'][y] \
                                                + vars['tax2'][y] \
                                                + vars['tax3'][y] \
                                                + vars['tax4'][y] \
                                                + vars['tax5'][y] \
                                                + vars['tax6'][y] \
                                                + vars['tax7'][y])
    
        # capgains tax
        
        scip.addCons(vars['capgains'][y] == vars['cgt0'][y] + vars['cgt15'][y] + vars['cgt20'][y])

        scip.addCons(vars['cgbin15'][y] >= vars['cgbin20'][y])

        scip.addCons(vars['taxable_income'][y] <= dd['cgt0'][y] + vars['taxb'][y] + 
                                                      vars['cgbin15'][y] * dd['cgt15'][y] + 
                                                      vars['cgbin20'][y] * 999.0)

        scip.addCons(vars['taxable_income'][y] == vars['cgbin15'][y] * (dd['cgt0'][y] + vars['taxb'][y]) +
                                                      vars['cgbin20'][y] * dd['cgt15'][y] + 
                                                      vars['ncgt'][y])

        scip.addCons(vars['cgt0'][y] <= (1 - vars['cgbin15'][y]) * (dd['cgt0'][y] + vars['taxb'][y] - vars['ncgt'][y]))

        scip.addCons(vars['cgt15'][y] <= (1 - vars['cgbin20'][y]) * (dd['cgt15'][y] - vars['ncgt'][y]))

        scip.addCons(vars['income_tax'][y] == 0.0 * vars['tax0'][y] \
                                            + 0.0 * vars['taxb'][y] \
                                            + 0.10 * vars['tax1'][y] \
                                            + 0.12 * vars['tax2'][y] \
                                            + 0.22 * vars['tax3'][y] \
                                            + 0.24 * vars['tax4'][y] \
                                            + 0.32 * vars['tax5'][y] \
                                            + 0.35 * vars['tax6'][y] \
                                            + 0.37 * vars['tax7'][y] \
                                            + 0.15 * vars['cgt15'][y] \
                                            + 0.20 * vars['cgt20'][y])

        # Annual Accounts Update
        
        scip.addCons(vars['e_Roth'][y] == rori_r(y) * (vars['e_Roth'][y-1] - vars['from_eRoth'][y] + vars['e_RothConv'][y]))
        scip.addCons(vars['e_Taxd'][y] == rori_d(y) * (vars['e_Taxd'][y-1] - vars['e_RMD'][y] \
                                         + dd['e_Taxd_in'][y] # lump sum pension distribution
                                         - vars['from_eTaxd'][y] - vars['e_RothConv'][y]))
        scip.addCons(vars['j_Roth'][y] == rori_r(y) * (vars['j_Roth'][y-1] - vars['from_jRoth'][y] + vars['j_RothConv'][y]))
        scip.addCons(vars['j_Taxd'][y] == rori_d(y) * (vars['j_Taxd'][y-1] - vars['j_RMD'][y] \
                                         + dd['j_Taxd_in'][y] # lump sum pension distribution
                                         - vars['from_jTaxd'][y] - vars['j_RothConv'][y]))

        # For "reasons," the optimizer moves all money into afterTax in the last year of the plan.
        # Until I figure out why, or discover a constraint to prevent that, the 0.999... hack...
        scip.addCons(vars['net_pretax'][y] \
                        == (0.999999 * vars['afterTax'][y] + vars['e_Taxd'][y] + vars['j_Taxd'][y] \
                            + vars['e_Roth'][y] + vars['j_Roth'][y]))

    scip.setParam("limits/time", tout)
    scip.setParam("limits/gap", glim / 100)
    scip.optimize()
    status = scip.getStatus()
    stage = scip.getStageName()
    
    # not effective: print('\n', flush = True)
    # not effective: sys.stdout.flush()
    time.sleep(1.0) # to flush output to the correct widget

    # with err_out:
    #     print(f'sta {status}')
    #     print(f'stg {stage}')

    if status == 'infeasible': # and stage == 'SOLVED':
        # fudge
        dd['net_pretax'][YRS] = 0
        dd['disp_income'][1] = 0

    else:
        
        #scip.writeProblem(filename="data/inital_model.mps", trans=False, genericnames=False)
        #scip.writeProblem(filename="data/xformd_model.mps", trans=True, genericnames=False)
        #scip.writeProblem(filename="data/inital_model.lp", trans=False, genericnames=False)
        #scip.writeProblem(filename="data/xformd_model.lp", trans=True, genericnames=False)
    
        OUTS = [
            'afterTax',
            'e_Roth',
            'e_Taxd',
            'j_Roth',
            'j_Taxd',
            'e_RMD',
            'j_RMD',
            'from_eRoth',
            'from_jRoth',
            'from_eTaxd',
            'from_jTaxd',
            'from_aTax',
            'to_aTax',
            'aTax__cash',
            'aTax_bonds',
            'aTax_basis',
            #'aTax_unrlz',
            'fm_aTax__cash',
            'fm_aTax_bonds',
            'fm_aTax_basis',
           #'fm_aTax_unrlz',
            'to_aTax__cash',
            'to_aTax_bonds',
            'to_aTax_basis',
           #'to_aTax_unrlz',
            'e_RothConv',
            'j_RothConv',
            'auto_income',
            'taxable_income',
            'dividends',
            'capgains',
            'caplosss',
            'disp_income',
            'income_tax',
            'QCD',
            'MAGI',
            'IRMAA',
            'net_pretax']
    
        for n in OUTS:
            for y in range(1,YRS+1):
                v = scip.getVal(vars[n][y])
                dd[n][y] = lop_to_cents(v)
    
        dd['disp_income'][0] = lop_to_cents(scip.getVal(vars['disp_income'][0])) # set if maximzing spend
        
        for y in range(1,YRS+1):
            dd['aTax_unrlz'][y] = lop_to_cents_signed(scip.getVal(vars['aTax_unrlz_gain'][y]) \
                                               - scip.getVal(vars['aTax_unrlz_loss'][y]))
            dd['fm_aTax_unrlz'][y] = lop_to_cents_signed(scip.getVal(vars['fm_aTax_unrlz_gain'][y]) \
                                                  - scip.getVal(vars['fm_aTax_unrlz_loss'][y]))
            dd['to_aTax_unrlz'][y] = lop_to_cents_signed(scip.getVal(vars['to_aTax_unrlz'][y]))
            
            dd['tax_bracket'][y] = \
                0.32 if lop_to_cents(scip.getVal(vars['tax5'][y])) != 0 else \
                0.24 if lop_to_cents(scip.getVal(vars['tax4'][y])) != 0 else \
                0.22 if lop_to_cents(scip.getVal(vars['tax3'][y])) != 0 else \
                0.12 if lop_to_cents(scip.getVal(vars['tax2'][y])) != 0 else \
                0.10 if lop_to_cents(scip.getVal(vars['tax1'][y])) != 0 else \
                0.00
            dd['cgains_rate'][y] = \
                0.20 if lop_to_cents(scip.getVal(vars['cgt20'][y])) != 0 else \
                0.15 if lop_to_cents(scip.getVal(vars['cgt15'][y])) != 0 else \
                0.00
            #
            dd['IRMAA-bins'][y] = scip.getVal(vars['IRMAA-bin0'][y]) \
                                + scip.getVal(vars['IRMAA-bin1'][y]) * 2 \
                                + scip.getVal(vars['IRMAA-bin2'][y]) * 4 \
                                + scip.getVal(vars['IRMAA-bin3'][y]) * 8 \
                                + scip.getVal(vars['IRMAA-bin4'][y]) * 16 \
                                + scip.getVal(vars['IRMAA-bin5'][y]) * 32
            #
            dd['net_postax'][y] = dd['e_Roth'][y] + dd['j_Roth'][y] \
                                    + (1.0 - dd['cgains_rate'][y]) * dd['afterTax'][y] \
                                    + (1.0 - dd['tax_bracket'][y]) * (dd['e_Taxd'][y] + dd['j_Taxd'][y])
    
        # with err_out:
        #     for y in range(1,3):
        #         print(f"00 {lop_to_cents(scip.getVal(vars['cgt0'][y]))}")
        #         print(f"15 {lop_to_cents(scip.getVal(vars['cgt15'][y]))}")
        #         print(f"20 {lop_to_cents(scip.getVal(vars['cgt20'][y]))}")
        #         print(f"b  {lop_to_cents(scip.getVal(vars['taxb'][y]))}")
        #         print(f"nc {lop_to_cents(scip.getVal(vars['ncgt'][y]))}")
        #         print(f"bn {scip.getVal(vars['cgbin15'][y] + 2 * scip.getVal(vars['cgbin20'][y]))}")
                
        # with err_out:
            # print(f'obj {scip.getObjVal()}')
            # print(f'sec {scip.getSolvingTime()}')

    gap = scip.getGap()
    stime = scip.getSolvingTime()
    
    scip.freeProb() # removes model from its cache memory
    
    return (status, dd['net_pretax'][YRS], dd['disp_income'][1], stage, gap, stime)
    

