# solver.py — e-ORP SCIP optimizer and high-level run functions
# Extracted from e-ORP.ipynb for PyWebView desktop app (R3 plan).
# Copyright (c) 2020-5 Doug Currie

from planner import (
    make_planning_datadict,
    asset_ceiling,
    hd,
    set_nut,
    get_nut,
    squirrel_map,
    addl_obbba_deduction_age65,
)
import statistics
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import pyscipopt


@dataclass
class SolveResult:
    """Outcome of one oorplp() solve.

    slacks and diagnosis are empty/None except on the infeasibility-diagnosis path;
    see diagnose_infeasible().
    """
    status: str
    net_pretax: float
    di: float
    stage: str
    gap: float
    stime: float
    has_solution: bool = True                    # False when SCIP found no incumbent
    slacks: dict = field(default_factory=dict)   # (tag, y) -> shortfall, nominal $k
    bound_culprits: list = field(default_factory=list)  # set only by a bounds probe
    diagnosis: Optional[dict] = None             # JSON-ready; set by the oorp driver

    def ok(self):
        """True when this result carries a usable plan."""
        return self.has_solution and self.status in ('timelimit', 'optimal', 'gaplimit')


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


def oorplp(dd, mode, objective, tout, glim, elastic=None, bounds_scale=1.0):
    """Run OORPyLP with specified objective, 'net_pretax', 'net_postax',
        or a non-string value for maximum DI with a specified residual.

    elastic: None for a normal solve. Otherwise 'residual' or 'spending' — adds
        non-negative slack variables to that family of user-controllable
        constraints and minimizes them, so an infeasible plan yields "this dial is
        off by $X" instead of just 'infeasible'. See diagnose_infeasible().

    bounds_scale: multiplier on the hand-tuned variable upper bounds. 1.0 ships.
        A probe at 4.0 that turns feasible means the bounds, not the user's plan,
        caused the infeasibility.

    Returns a SolveResult.
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
    _cons_seq = [0]

    def add_cons(expr, name=None):
        """Add a linear/nonlinear constraint with a unique name.

        Pass ``name=`` for the thin set of high-signal constraints that the
        infeasibility diagnostic can attach slacks to; otherwise names are
        sequential ``eorp_NNNNN``, which keeps SCIP's own presolve messages and
        any ``writeProblem()`` dump traceable back to this source.
        """
        _cons_seq[0] += 1
        cname = name if name is not None else ("eorp_%05d" % _cons_seq[0])
        return scip.addCons(expr, name=cname)

    _slacks = {}   # (tag, y) -> (var, weight)
    _ub_at_1 = {}  # (varname, y) -> the cap this run would have had at bounds_scale 1

    def slk(tag, y, weight, ub):
        """A non-negative slack variable when ``elastic == tag``; literal 0.0 otherwise.

        ``expr + 0.0`` is a no-op in PySCIPopt, so a normal solve (and the other
        family's probe) builds exactly the model it built before this feature existed.
        Slacks are one-sided: surplus cash can always be parked via to_aTax, so only
        the shortfall direction is ever binding.
        """
        if elastic != tag:
            return 0.0
        v = scip.addVar(vtype='C', lb=0.0, ub=max(float(ub), 1.0),
                        name=f"slack_{tag}_{y}")
        _slacks[(tag, y)] = (v, weight)
        return v

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

    # Upper bound on any single account. Applied per year as `max_tab * infl`.
    #
    # This used to be `min(18316.2, 2 * bas_tab)` -- a flat multiple of the starting
    # balance, with the cap growing only at the rate of INFLATION. A plan compounds at
    # the rate of RETURN, so over a long horizon the cap fell behind the balances it was
    # meant to bound and the model became infeasible with nothing wrong with the plan.
    # params/example_p.csv was one such: 27 years at 7% needed 3280 against a cap of
    # 1707. (The old 18316.2 "the 1%" ceiling had the same defect in the other
    # direction: any portfolio above $18.3M got a cap below its own opening balance.)
    #
    # asset_ceiling() is a rigorous per-year ceiling on total assets, so it bounds every
    # individual account too. Express it in this code's `max_tab * infl` shape by taking
    # the largest constant any year demands.
    bas_tab = dd['e_Roth'][0] + dd['j_Roth'][0] + dd['afterTax'][0] + dd['e_Taxd'][0] + dd['j_Taxd'][0]
    bas_tab = max(bas_tab, ftab)
    _ceiling = asset_ceiling(dd)
    _infl = 1.0 + get_nut(dd, 'inflation')
    _needed = max(_ceiling[y] / (_infl ** y) for y in range(1, YRS + 1)) if YRS else bas_tab
    # max() with the old 2x rule so this can only ever loosen the bounds, never tighten
    # them: a regression here would show up as a brand-new infeasibility.
    max_tab = max(2.0 * bas_tab, _needed, ftab)
    # Scale last. max_xfr/max_inc/max_tax derive from max_tab, so they scale with it --
    # do not scale them again.
    bs = float(bounds_scale)
    max_tab = max_tab * bs
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
        scip.chgVarUb(vars[     'dividends'][y],   500.0 * bs * infl)
        scip.chgVarUb(vars[    'income_tax'][y], max_tax * infl)
        scip.chgVarUb(vars[         'IRMAA'][y],    34.0 * bs * infl)
        scip.chgVarUb(vars[          'taxb'][y],    20.0 * bs * infl)
        scip.chgVarUb(vars[          'tax0'][y],    50.0 * bs * infl)
        scip.chgVarUb(vars[          'tax1'][y],    30.0 * bs * infl)
        scip.chgVarUb(vars[          'tax2'][y],    80.0 * bs * infl)
        scip.chgVarUb(vars[          'tax3'][y],   120.0 * bs * infl)
        scip.chgVarUb(vars[          'tax4'][y],   220.0 * bs * infl)
        scip.chgVarUb(vars[          'tax5'][y],   120.0 * bs * infl)
        scip.chgVarUb(vars[          'tax6'][y],   280.0 * bs * infl)
        scip.chgVarUb(vars[          'tax7'][y], max_inc * infl)
        scip.chgVarUb(vars[     'obbba_exc'][y], max_inc * infl)
        scip.chgVarUb(vars[          'cgt0'][y],   140.0 * bs * infl)
        scip.chgVarUb(vars[         'cgt15'][y],    80.0 * bs * infl)
        scip.chgVarUb(vars[         'cgt20'][y], max_inc * infl)
        scip.chgVarUb(vars[          'ncgt'][y],   max_inc * infl)
        #scip.chgVarUb(vars[         'ncgt0'][y],   140.0 * infl)
        #scip.chgVarUb(vars[        'ncgt15'][y],    80.0 * infl)
        #scip.chgVarUb(vars[        'ncgt20'][y], max_inc * infl)
        scip.chgVarUb(vars[           'QCD'][y],   220.0 * bs * infl)
        # nQCD is the non-QCD remainder of charitable giving; no statute caps it, and
        # QCD + nQCD == charity, so a fixed 220 made any plan giving more than about
        # $440k/yr infeasible for no real reason. Bound it by the input instead.
        scip.chgVarUb(vars[          'nQCD'][y], dd['charity'][y])

        if bs != 1.0:
            # Remember what each cap WOULD have been at the shipped scale, so a probe
            # that turns feasible can name the bound that was actually binding.
            # nQCD and fm_aTax_frac are excluded: neither is scaled.
            for _n in VARS:
                if _n in ('nQCD', 'fm_aTax_frac'):
                    continue
                _u = vars[_n][y].getUbOriginal()
                if _u < 1e19:
                    _ub_at_1[(_n, y)] = _u / bs
        
    # Objective
    _infl_rate = get_nut(dd, 'inflation')

    def dfl(y):
        """Nominal $k in year y -> base-year $k, so slacks across years are comparable."""
        return (1.0 + _infl_rate) ** (-y)

    if isinstance(objective, str):
        tie_var = vars[objective][YRS]
        scip.setObjective(tie_var, sense="maximize")
        # subject to: spending is pinned to the user's stated curve, so a shortfall
        # here means "your stated spending exceeds what the plan can fund".
        for y in range(1,YRS+1):
            add_cons(
                dd['disp_income'][y]
                    == vars['disp_income'][y] + slk('spending', y, dfl(y), dd['disp_income'][y]),
                name=f"eorp_fix_disp_y{y}",
            )
    else:
        #scip.setObjective(vars['disp_income'][0], sense="maximize") # 'Maximize Spend'
        tie_var = vars['discretionary_spend'][0]
        scip.setObjective(tie_var, sense="maximize") # 'Maximize Spend'
        # subject to growth and minimum residual:
        add_cons(
            vars['net_pretax'][YRS] + slk('residual', YRS, dfl(YRS), ftab) >= ftab,
            name="eorp_min_residual_final",
        )  # Minimum Residual
        # mantain spending curve
        for y in range(1,YRS+1):
            add_cons(
                vars['discretionary_spend'][y] == dd['spend_δ'][y] * vars['discretionary_spend'][y-1],
                name=f"eorp_spend_delta_y{y}",
            )
            # discretionary_spend >= 0 is free, so the binding part of this is the
            # essential-spending floor -- which is the dial the slack reports on.
            add_cons(
                vars['disp_income'][y] + slk('spending', y, dfl(y), dd['spend_essence'][y])
                    == vars['discretionary_spend'][y] + dd['spend_essence'][y],
                name=f"eorp_disp_from_disc_y{y}",
            )

    # Initial Values Constraints
    add_cons(vars['e_Roth'][0] == dd['e_Roth'][0], name="eorp_init_e_roth_0")
    add_cons(vars['e_Taxd'][0] == dd['e_Taxd'][0], name="eorp_init_e_taxd_0")
    add_cons(vars['j_Roth'][0] == dd['j_Roth'][0], name="eorp_init_j_roth_0")
    add_cons(vars['j_Taxd'][0] == dd['j_Taxd'][0], name="eorp_init_j_taxd_0")
    add_cons(vars['afterTax'][0] == dd['afterTax'][0], name="eorp_init_aftertax_0")
    add_cons(vars['aTax__cash'][0] == dd['aTax__cash'][0], name="eorp_init_atax_cash_0")
    add_cons(vars['aTax_bonds'][0] == dd['aTax_bonds'][0], name="eorp_init_atax_bonds_0")
    add_cons(vars['aTax_basis'][0] == dd['aTax_basis'][0], name="eorp_init_atax_basis_0")
    if dd['aTax_unrlz'][0] < 0:
        add_cons(vars['aTax_unrlz_gain'][0] == 0, name="eorp_init_unrlz_gain_0")
        if no_capital_losses:
            add_cons(vars['aTax_unrlz_loss'][0] == 0, name="eorp_init_unrlz_loss_0")  # make_planning_datadict will have issued a warning
        else:
            add_cons(vars['aTax_unrlz_loss'][0] == -dd['aTax_unrlz'][0], name="eorp_init_unrlz_loss_0")
    else:
        add_cons(vars['aTax_unrlz_loss'][0] == 0, name="eorp_init_unrlz_loss_0")
        add_cons(vars['aTax_unrlz_gain'][0] == dd['aTax_unrlz'][0], name="eorp_init_unrlz_gain_0")

    # Calculation Constraints
    for y in range(1,YRS+1):
        add_cons(vars['e_RMD'][y] == dd['e_RMD_factor'][y] * vars['e_Taxd'][y-1], name=f"eorp_e_rmd_y{y}")
        add_cons(vars['j_RMD'][y] == dd['j_RMD_factor'][y] * vars['j_Taxd'][y-1], name=f"eorp_j_rmd_y{y}")

        # AfterTax asset allocations
        add_cons(vars['afterTax'][y]  == vars['aTax__cash'][y] + vars['aTax_bonds'][y] + vars['aTax_basis'][y]  \
                                             + vars['aTax_unrlz_gain'][y] - vars['aTax_unrlz_loss'][y])
        add_cons(vars['from_aTax'][y] == vars['fm_aTax__cash'][y] + vars['fm_aTax_bonds'][y] \
                                             + vars['fm_aTax_basis'][y] \
                                             + vars['fm_aTax_unrlz_gain'][y] - vars['fm_aTax_unrlz_loss'][y])
        add_cons(vars['to_aTax'][y]   == vars['to_aTax__cash'][y] + vars['to_aTax_bonds'][y] \
                                             + vars['to_aTax_basis'][y] + vars['to_aTax_unrlz'][y])
        
        add_cons(vars['afterTax'][y] * dd['frac_stock_a'][y] \
                                 == vars['aTax_basis'][y] + vars['aTax_unrlz_gain'][y] - vars['aTax_unrlz_loss'][y])
        add_cons(vars['afterTax'][y] * dd['frac_bonds_a'][y] == vars['aTax_bonds'][y])
        
        add_cons(vars['fm_aTax__cash'][y] <= vars['aTax__cash'][y-1])
        add_cons(vars['fm_aTax_bonds'][y] <= vars['aTax_bonds'][y-1])

        if no_capgains_constraints:
            add_cons(vars['fm_aTax_basis'][y]      <= vars['aTax_basis'][y-1])
            add_cons(vars['fm_aTax_unrlz_gain'][y] <= vars['aTax_unrlz_gain'][y-1])
            add_cons(vars['fm_aTax_unrlz_loss'][y] <= vars['aTax_unrlz_loss'][y-1])
        else:
            add_cons(vars['fm_aTax_basis'][y]      == vars['fm_aTax_frac'][y] * vars['aTax_basis'][y-1])
            add_cons(vars['fm_aTax_unrlz_gain'][y] == vars['fm_aTax_frac'][y] * vars['aTax_unrlz_gain'][y-1])
            add_cons(vars['fm_aTax_unrlz_loss'][y] == vars['fm_aTax_frac'][y] * vars['aTax_unrlz_loss'][y-1])

        add_cons(vars['aTax_unrlz_gain'][y] - vars['aTax_unrlz_loss'][y] \
                         == (vars['aTax_unrlz_gain'][y-1] - vars['fm_aTax_unrlz_gain'][y]) \
                          - (vars['aTax_unrlz_loss'][y-1] - vars['fm_aTax_unrlz_loss'][y]) \
                          + vars['to_aTax_unrlz'][y])
            
        if no_capital_losses:
            add_cons(vars['aTax_unrlz_loss'][y] == 0)
        else:
            # unfortuately, the first form using a disjunction leads to symmetry problems in SCIP:
            #scip.addConsDisjunction([vars['aTax_unrlz_gain'][y] == 0, vars['aTax_unrlz_loss'][y] == 0])
            # so I use the multiplication instead:
            add_cons(vars['aTax_unrlz_gain'][y] * vars['aTax_unrlz_loss'][y] == 0)

        add_cons(vars['aTax__cash'][y] == vars['aTax__cash'][y-1] + vars['to_aTax__cash'][y] - vars['fm_aTax__cash'][y])
        add_cons(vars['aTax_bonds'][y] == vars['aTax_bonds'][y-1] + vars['to_aTax_bonds'][y] - vars['fm_aTax_bonds'][y])
        add_cons(vars['aTax_basis'][y] == vars['aTax_basis'][y-1] + vars['to_aTax_basis'][y] - vars['fm_aTax_basis'][y])
                
        add_cons(vars['to_aTax_unrlz'][y] == (dd['ror_stock'][y] - dd['dvd_stock'][y]) \
                                                     * (vars['aTax_basis'][y-1] \
                                                        + vars['aTax_unrlz_gain'][y-1]
                                                        - vars['aTax_unrlz_loss'][y-1]))
        
        add_cons(vars['dividends'][y] == dd['ror_bonds'][y] * vars['aTax_bonds'][y-1] \
                                             + dd['dvd_stock'][y] * (vars['aTax_basis'][y-1] \
                                                                    + vars['aTax_unrlz_gain'][y-1]
                                                                    - vars['aTax_unrlz_loss'][y-1]))
        
        add_cons(vars['capgains'][y] == vars['fm_aTax_unrlz_gain'][y])
        
        if no_capital_losses:
            add_cons(vars['caplosss'][y] == 0.0)
        else:
            add_cons(vars['caplosss'][y] + vars['caplossz'][y] == vars['fm_aTax_unrlz_loss'][y])
            add_cons(vars['caplosss'][y] <= 3.0)

        # Roth Conversions)
        add_cons(vars['e_RothConv'][y] <= vars['e_Taxd'][y-1], name=f"eorp_rothconv_e_le_taxd_y{y}")
        add_cons(vars['j_RothConv'][y] <= vars['j_Taxd'][y-1], name=f"eorp_rothconv_j_le_taxd_y{y}")
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
                                   ], name="eorp_rothlim_y%d" % y)

        # QCD Calculation
        add_cons(vars['QCD'][y] + vars['nQCD'][y] == dd['charity'][y], name=f"eorp_qcd_charity_y{y}")
        add_cons(vars['QCD'][y] <= dd['QCD_limit'][y], name=f"eorp_qcd_limit_y{y}")
        add_cons(
            vars['QCD'][y]
            <= vars['e_RMD'][y]
            + vars['j_RMD'][y]
            + vars['from_eTaxd'][y]
            + vars['from_jTaxd'][y],
            name=f"eorp_qcd_le_rmd_wthd_y{y}",
        )

        # IRMAA Calculation
        # IRMAA-pax: 0, 1, 2 # individuals over 65
        # IRMAA-buk: income tier increments, 0..5
        # IRMAA-bin: binary indicator if tier is reached, 0..5
        # IRMAA-chg: (sur-)charge per tier, 0..5
        # MAGI <= IRMAA-bin[0] * IRMAA-buk[0] + ... IRMAA-bin[5] * IRMAA-buk[5]
        # IRMAA-bin[0] >= IRMAA-bin[1] >= ... IRMAA-bin[5] # fill the lower bins first
        # IRMAA = IRMAA-pax * (IRMAA-chg[n] * IRMAA-bin[n] for n in 0..5) 
        # dd has precomputed IRMAA-pax * IRMAA-chg
        
        add_cons(vars['IRMAA-bin0'][y] >= vars['IRMAA-bin1'][y])
        add_cons(vars['IRMAA-bin1'][y] >= vars['IRMAA-bin2'][y])
        add_cons(vars['IRMAA-bin2'][y] >= vars['IRMAA-bin3'][y])
        add_cons(vars['IRMAA-bin3'][y] >= vars['IRMAA-bin4'][y])
        add_cons(vars['IRMAA-bin4'][y] >= vars['IRMAA-bin5'][y])
        
        add_cons(MAGI_m2(y) <= vars['IRMAA-bin0'][y] * dd['IRMAA-buk0'][y] \
                                 + vars['IRMAA-bin1'][y] * dd['IRMAA-buk1'][y] \
                                 + vars['IRMAA-bin2'][y] * dd['IRMAA-buk2'][y] \
                                 + vars['IRMAA-bin3'][y] * dd['IRMAA-buk3'][y] \
                                 + vars['IRMAA-bin4'][y] * dd['IRMAA-buk4'][y] \
                                 + vars['IRMAA-bin5'][y] * dd['IRMAA-buk5'][y] \
                                 + 0.00001) # this <= $0.01 fudge factor seems to rescue some otherwise non-converging soltions

        add_cons(vars['IRMAA'][y] == vars['IRMAA-bin0'][y] * dd['IRMAA-chg0'][y] \
                                      + vars['IRMAA-bin1'][y] * dd['IRMAA-chg1'][y] \
                                      + vars['IRMAA-bin2'][y] * dd['IRMAA-chg2'][y] \
                                      + vars['IRMAA-bin3'][y] * dd['IRMAA-chg3'][y] \
                                      + vars['IRMAA-bin4'][y] * dd['IRMAA-chg4'][y] \
                                      + vars['IRMAA-bin5'][y] * dd['IRMAA-chg5'][y]) 

        # Income Calculation

        add_cons(vars['auto_income'][y] == vars['e_RMD'][y] + vars['j_RMD'][y] + vars['dividends'][y] \
                                                + dd['misc_income'][y] + dd['SSA_income'][y] \
                                                + dd['taxfree_income'][y] \
                                                + dd['pension_income'][y] - vars['IRMAA'][y])

        add_cons(vars['taxable_income'][y] == vars['e_RMD'][y] + vars['j_RMD'][y] + vars['dividends'][y] \
                                                + dd["misc_income"][y] + 0.85 * dd["SSA_income"][y] - vars['caplosss'][y] \
                                                + vars['from_eTaxd'][y] + vars['from_jTaxd'][y] - vars['QCD'][y] \
                                                + dd['pension_income'][y] + vars['e_RothConv'][y] + vars['j_RothConv'][y])

        # Spending
        
        add_cons(
            vars['disp_income'][y]
            == vars['auto_income'][y]
            + vars['from_aTax'][y]
            + vars['from_eTaxd'][y]
            + vars['from_jTaxd'][y]
            + vars['from_eRoth'][y]
            + vars['from_jRoth'][y]
            - vars['income_tax'][y]
            - vars['to_aTax'][y],
            name=f"eorp_disp_balance_y{y}",
        )

        # Taxation - XXX qualified dividends?

        # OBBBA
        # MAGI used, so need to add the non-taxable portion of SSA
        # OBBBA-pax: 0, 1, 2 # individuals over 65
        # OBBBA_exc: == (MAGI - (OBBBA-pax * 75.000)
        # OBBBA-ded: <= OBBBA-pax * 6.000 - (OBBBA-pax * 0.06 * OBBBA_exc))

        add_cons(vars['MAGI'][y] == vars['e_RMD'][y] + vars['j_RMD'][y] + vars['dividends'][y] \
                                            + dd["misc_income"][y] + dd['pension_income'][y] + dd["SSA_income"][y] \
                                            + vars['from_eTaxd'][y] + vars['from_jTaxd'][y] - vars['caplosss'][y] \
                                            + vars['capgains'][y] + vars['e_RothConv'][y] + vars['j_RothConv'][y])
        
        add_cons(vars['obbba_exc'][y] >= vars['MAGI'][y] - dd['obbba_pax'][y] * 75.0) # lower bound is 0

        add_cons(vars['tax0'][y] <= dd['tax0'][y])
        add_cons(vars['tax1'][y] <= dd['tax1'][y])
        add_cons(vars['tax2'][y] <= dd['tax2'][y])
        add_cons(vars['tax3'][y] <= dd['tax3'][y])
        add_cons(vars['tax4'][y] <= dd['tax4'][y])
        add_cons(vars['tax5'][y] <= dd['tax5'][y])
        add_cons(vars['tax6'][y] <= dd['tax6'][y])
        add_cons(vars['taxb'][y] <= dd['obbba_pax'][y] * addl_obbba_deduction_age65 \
                                        - (dd['obbba_pax'][y] * 0.06 * vars['obbba_exc'][y]))

        add_cons(vars['taxable_income'][y] == vars['tax0'][y] \
                                                + vars['taxb'][y] \
                                                + vars['tax1'][y] \
                                                + vars['tax2'][y] \
                                                + vars['tax3'][y] \
                                                + vars['tax4'][y] \
                                                + vars['tax5'][y] \
                                                + vars['tax6'][y] \
                                                + vars['tax7'][y])
    
        # capgains tax
        
        add_cons(vars['capgains'][y] == vars['cgt0'][y] + vars['cgt15'][y] + vars['cgt20'][y])

        add_cons(vars['cgbin15'][y] >= vars['cgbin20'][y])

        add_cons(vars['taxable_income'][y] <= dd['cgt0'][y] + vars['taxb'][y] + 
                                                      vars['cgbin15'][y] * dd['cgt15'][y] + 
                                                      vars['cgbin20'][y] * 999.0)

        add_cons(vars['taxable_income'][y] == vars['cgbin15'][y] * (dd['cgt0'][y] + vars['taxb'][y]) +
                                                      vars['cgbin20'][y] * dd['cgt15'][y] + 
                                                      vars['ncgt'][y])

        add_cons(vars['cgt0'][y] <= (1 - vars['cgbin15'][y]) * (dd['cgt0'][y] + vars['taxb'][y] - vars['ncgt'][y]))

        add_cons(vars['cgt15'][y] <= (1 - vars['cgbin20'][y]) * (dd['cgt15'][y] - vars['ncgt'][y]))

        add_cons(vars['income_tax'][y] == 0.0 * vars['tax0'][y] \
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
        
        add_cons(vars['e_Roth'][y] == rori_r(y) * (vars['e_Roth'][y-1] - vars['from_eRoth'][y] + vars['e_RothConv'][y]))
        add_cons(vars['e_Taxd'][y] == rori_d(y) * (vars['e_Taxd'][y-1] - vars['e_RMD'][y] \
                                         + dd['e_Taxd_in'][y] # lump sum pension distribution
                                         - vars['from_eTaxd'][y] - vars['e_RothConv'][y]))
        add_cons(vars['j_Roth'][y] == rori_r(y) * (vars['j_Roth'][y-1] - vars['from_jRoth'][y] + vars['j_RothConv'][y]))
        add_cons(vars['j_Taxd'][y] == rori_d(y) * (vars['j_Taxd'][y-1] - vars['j_RMD'][y] \
                                         + dd['j_Taxd_in'][y] # lump sum pension distribution
                                         - vars['from_jTaxd'][y] - vars['j_RothConv'][y]))

        # For "reasons," the optimizer moves all money into afterTax in the last year of the plan.
        # Until I figure out why, or discover a constraint to prevent that, the 0.999... hack...
        add_cons(
            vars['net_pretax'][y]
            == (
                0.999999 * vars['afterTax'][y]
                + vars['e_Taxd'][y]
                + vars['j_Taxd'][y]
                + vars['e_Roth'][y]
                + vars['j_Roth'][y]
            ),
            name=f"eorp_net_pretax_def_y{y}",
        )

    if _slacks:
        # Replace the objective rather than penalizing it: a big-M penalty would have
        # to be tuned against the spend scale on a model that already needs two numeric
        # fudges to converge. The 1e-6 tie-break keeps the reported secondary numbers
        # well-defined; it can shift the slack sum by at most a few dollars.
        scip.setObjective(
            1e-6 * tie_var
            - pyscipopt.quicksum(w * v for (v, w) in _slacks.values()),
            sense="maximize",
        )

    scip.setParam("limits/time", tout)
    scip.setParam("limits/gap", glim / 100)
    scip.optimize()
    status = scip.getStatus()
    stage = scip.getStageName()

    # not effective: print('\n', flush = True)
    # not effective: sys.stdout.flush()
    # (desktop app: stdout redirected to queue; frontend polls)

    # with err_out:
    #     print(f'sta {status}')
    #     print(f'stg {stage}')

    # A time/gap limit can stop the solver before any incumbent is found. SCIP then
    # reports 'timelimit' but getVal() is meaningless -- it used to be extracted and
    # charted as if it were a plan (seen: net_pretax 4.99e96). Treat it as no result.
    has_sol = scip.getNSols() > 0
    slack_vals = {}
    bound_culprits = []
    if status == 'infeasible' or not has_sol:
        if status != 'infeasible':
            print(
                f'No feasible solution found within the limits (status {status}); '
                f'raise the timeout or the gap limit.\n',
                flush=True,
            )
        # fudge
        dd['net_pretax'][YRS] = 0
        dd['disp_income'][1] = 0

    else:
        for (tag, y), (v, _w) in _slacks.items():
            val = scip.getVal(v)
            if val > 1e-4:
                slack_vals[(tag, y)] = val

        for (nm, y), ub1 in _ub_at_1.items():
            val = scip.getVal(vars[nm][y])
            # Above the shipped cap, but strictly inside the relaxed one. The second
            # test matters: some variables (obbba_exc, ncgt) are only constrained from
            # below, so they park at whatever ceiling they are given and would
            # otherwise be reported at every scale as a false culprit.
            if val > ub1 * 1.000001 and val < ub1 * bs * 0.999999:
                bound_culprits.append({'var': nm, 'year': int(dd['year'][y]),
                                       'needed': round(val, 1), 'capped_at': round(ub1, 1)})
        bound_culprits.sort(key=lambda d: -(d['needed'] - d['capped_at']))

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
                0.37 if lop_to_cents(scip.getVal(vars['tax7'][y])) != 0 else \
                0.35 if lop_to_cents(scip.getVal(vars['tax6'][y])) != 0 else \
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

    return SolveResult(
        status=status,
        net_pretax=dd['net_pretax'][YRS],
        di=dd['disp_income'][1],
        stage=stage,
        gap=gap,
        stime=stime,
        has_solution=has_sol,
        slacks=slack_vals,
        bound_culprits=bound_culprits,
    )




# Infeasibility diagnosis budgets. The probes are cheap (a relaxed solve at mode 0 is
# ~0.1 s on the scenarios measured), and a 5% gap is plenty: "your residual target is
# $1,575k too high, give or take 5%" is exactly as actionable as an exact figure.
DIAG_GLIM = 5.0
BOUNDS_PROBE_SCALE = 4.0


def _diag_tout(tout):
    try:
        t = float(tout)
    except (TypeError, ValueError):
        return 20.0
    return max(5.0, min(t, 20.0)) if t > 0 else 20.0


def diagnose_infeasible(p, mode, objt, test, tout, ftab_input=None):
    """Work out WHY a plan is infeasible and return a JSON-ready diagnosis dict.

    Order matters. The bounds probe runs first because mis-attributing one of e-ORP's
    own hand-tuned variable bounds to the user's plan is the worst thing this feature
    could do; running it first also means the elastic probes run at the shipped bounds,
    so a suggested ftab is achievable in the model the user will actually re-run.

    Probes always build a fresh dd: oorplp() zeroes dd['net_pretax'][YRS] and
    dd['disp_income'][1] when infeasible, and dd['disp_income'] is a model *input*
    under the 'net_pretax' objective.
    """
    dtout = _diag_tout(tout)
    notes = []

    def fresh():
        return make_planning_datadict(p, test_mode=test, warn_cb=None)

    def probe(elastic=None, bounds_scale=1.0, pmode=0):
        dd = fresh()
        return dd, oorplp(dd, pmode, objt, dtout, DIAG_GLIM,
                          elastic=elastic, bounds_scale=bounds_scale)

    if mode != 0:
        notes.append('Diagnostic ran in simplified mode (no capital-loss harvesting, '
                     'no cost-basis averaging) so it stays fast.')

    # 1. Are e-ORP's own variable bounds the cause?
    print('Diagnosing infeasibility: checking model bounds...', flush=True)
    _dd, r = probe(bounds_scale=BOUNDS_PROBE_SCALE)
    if r.ok():
        rows = [{'lever': f"model cap on {c['var']}", 'year': c['year'],
                 'shortfall_real': round(c['needed'] - c['capped_at'], 1),
                 'current': c['capped_at'], 'suggested': c['needed']}
                for c in r.bound_culprits[:10]]
        named = ', '.join(sorted({c['var'] for c in r.bound_culprits[:10]}))
        return {
            'kind': 'bounds',
            'headline': 'This looks like a bug in e-ORP, not a problem with your plan.',
            'rows': rows,
            'notes': notes + [
                'The plan became solvable when e-ORP\'s internal variable bounds were '
                f'relaxed {BOUNDS_PROBE_SCALE:g}x, so those bounds -- not your inputs -- '
                'made it infeasible. Please report this scenario.',
            ] + ([f'Binding caps: {named}. "Current" is the shipped cap; "Suggested" is '
                  f'what the solution actually needed.'] if named else []),
            'approximate': False,
        }
    notes.append('Model upper bounds were checked and are not the cause.')

    # 2. Which user dial is short, and by how much? Two independent questions.
    rows = []
    approximate = False
    probes = [('residual', 'Minimum residual (Plan Surplus)', 'ftab'),
              ('spending', 'Spending', None)]
    if isinstance(objt, str):
        probes = [('spending', 'Stated spending', None)]   # no residual constraint here

    for tag, label, param in probes:
        print(f'Diagnosing infeasibility: testing {label.lower()}...', flush=True)
        dd, r = probe(elastic=tag)
        if not r.ok():
            continue
        if r.status == 'timelimit':
            approximate = True
        infl = get_nut(dd, 'inflation')
        YRS = len(dd['e']) - 1
        for (_tag, y), val in sorted(r.slacks.items(), key=lambda kv: -kv[1]):
            real = val * ((1.0 + infl) ** (-y))
            row = {'lever': label, 'year': int(dd['year'][y]),
                   'shortfall_real': round(real, 1),
                   'shortfall_nominal': round(val, 1)}
            if param == 'ftab' and ftab_input is not None:
                row['param'] = 'ftab'
                row['current'] = round(float(ftab_input), 1)
                row['suggested'] = round(max(0.0, float(ftab_input) - real), 1)
            rows.append(row)

    if rows:
        top = rows[0]
        if top.get('param') == 'ftab':
            headline = (f"Minimum residual is about ${top['shortfall_real']:,.0f}k "
                        f"(base-year $) too high.")
        else:
            headline = (f"Spending in {top['year']} exceeds what the plan can fund by "
                        f"about ${top['shortfall_real']:,.0f}k (base-year $).")
        return {'kind': 'elastic', 'headline': headline,
                'rows': rows[:10],
                'notes': notes + ([f'...and {len(rows) - 10} more years.'] if len(rows) > 10 else []),
                'approximate': approximate}

    # 3. Nothing in the user's dials. Structural?
    rlim = None
    try:
        rlim = get_nut(fresh(), 'Roth_conv_max')
    except Exception:
        pass
    if rlim is not None and rlim != 'unlimited':
        print('Diagnosing infeasibility: testing the Roth conversion cap...', flush=True)
        dd = fresh()
        set_nut(dd, 'Roth_conv_max', 'unlimited')
        r = oorplp(dd, 0, objt, dtout, DIAG_GLIM)
        if r.ok():
            return {
                'kind': 'structural',
                'headline': 'The Roth conversion limit is what makes this plan infeasible.',
                'rows': [],
                'notes': notes + ['Removing the Roth conversion cap makes the plan '
                                  'solvable; raising it should too.'],
                'approximate': False,
            }

    return {
        'kind': 'inconclusive',
        'headline': 'The plan is infeasible, but no single input explains it.',
        'rows': [],
        'notes': notes + [
            'Relaxing the minimum residual and the spending floor separately did not '
            'make it solvable, so the cause is an interaction. The dials most likely '
            'to matter: minimum residual, essential spending, Roth conversion cap, '
            'charitable giving, and the planning horizon.',
        ],
        'approximate': approximate,
    }


def oorp(p, mode, objt, test, tout, glim, fname=None, warn_cb=None, diagnose=True):
    """Run the projection; returns (dd, SolveResult).

    On infeasible, and when `diagnose`, runs the cheap probes in
    diagnose_infeasible() and attaches the result as `SolveResult.diagnosis`.
    """
    dd = make_planning_datadict(p, test_mode=test, warn_cb=warn_cb, objective=objt)
    set_nut(dd, 'orp_mode', mode)
    set_nut(dd, 'orp_objtv', objt)
    set_nut(dd, 'time_limit', tout)
    set_nut(dd, 'gap_limit', glim)
    # The user's entry, in base-year $ -- the same units as the diagnosis's
    # shortfall_real. dd['surplus'][YRS] is that entry inflated to the final year.
    ftab_input = p.get('ftab')
    r = oorplp(dd, mode, objt, tout, glim)
    print('\n', flush=True)
    set_nut(dd, 'scip_status', r.status)
    set_nut(dd, 'scip_stage', r.stage)
    set_nut(dd, 'scip_gap', r.gap)
    set_nut(dd, 'scip_time', r.stime)
    if r.ok():
        print(f'FTAB: {r.net_pretax: 4.3f} DI 1st year: {r.di: 3.3f} Status: {r.status} at stage {r.stage} gap {100 * r.gap: 1.3f}% in {r.stime: 2.3f} s')
    else:
        print(f'Optimization failed, status {r.status} gap {100 * r.gap: 1.3f}% in {r.stime: 2.3f} s')
        if r.status == 'infeasible' and diagnose:
            r.diagnosis = diagnose_infeasible(p, mode, objt, test, tout,
                                              ftab_input=ftab_input)
            print('\n' + r.diagnosis['headline'], flush=True)
            for row in r.diagnosis['rows']:
                print(f"  {row['lever']} {row['year']}: short by "
                      f"${row['shortfall_real']:,.1f}k (base-year $)", flush=True)
            for n in r.diagnosis['notes']:
                print(f'  - {n}', flush=True)
    return (dd, r)


def walk_lap(p, fromyear, mode, tout, glim, warn_cb=None):
    objt = 0
    dd = make_planning_datadict(p, test_mode='', historical_year_for_rates=fromyear, warn_cb=warn_cb)
    set_nut(dd, 'orp_mode', mode)
    set_nut(dd, 'orp_objtv', objt)
    set_nut(dd, 'time_limit', tout)
    set_nut(dd, 'gap_limit', glim)
    r = oorplp(dd, mode, objt, tout, glim)
    print('\n', flush=True)
    set_nut(dd, 'scip_status', r.status)
    set_nut(dd, 'scip_stage', r.stage)
    set_nut(dd, 'scip_gap', r.gap)
    set_nut(dd, 'scip_time', r.stime)
    return (dd, r)


def walk(p, mode, tout, glim, fname, warn_cb=None):
    worst_di = 1000000.0
    worst_di_dd = None
    worst_year = 1970
    sta_yr = 1970
    nyears = 10
    if p.get('hist') != 'Use Values Below':
        sta_yr = int(p['hist'])
    worst_year = sta_yr
    for y in range(sta_yr, sta_yr + nyears):
        (dd, r) = walk_lap(p, y, mode, tout, glim, warn_cb=warn_cb)
        if r.ok():
            print(f'{y} | DI 1st year: {r.di: 3.3f} Status: {r.status} at stage {r.stage} gap {100 * r.gap: 1.3f}% in {r.stime: 2.3f} s')
            if dd['disp_income'][1] < worst_di:
                worst_di = dd['disp_income'][1]
                worst_di_dd = dd
                worst_year = y
        else:
            print(f'{y} | Optimization failed, status {r.status} gap {100 * r.gap: 1.3f}% in {r.stime: 2.3f} s')
            if worst_di_dd is None:
                worst_di_dd = dd
                worst_year = y
    print(f'{worst_year} | DI 1st year: {worst_di: 3.3f} is lowest...')
    return (worst_di_dd, worst_year, worst_di, fname)


def three_peat(p, mode, tout, glim, fname, warn_cb=None):
    """Run 3-peat; returns (rf, sm, fname) for render_three_peat."""
    verbose = True
    objt = 0
    dd = make_planning_datadict(p, test_mode='3-peat', warn_cb=warn_cb)
    set_nut(dd, 'orp_mode', mode)
    set_nut(dd, 'orp_objtv', objt)
    set_nut(dd, 'time_limit', tout)
    set_nut(dd, 'gap_limit', glim)

    def fnvers(i):
        parts = fname.split('.')
        ext = parts.pop()
        parts.append(str(i))
        parts.append(ext)
        return '.'.join(parts)

    historical_year_for_rates = 1970
    if p.get('hist') != 'Use Values Below':
        historical_year_for_rates = int(p['hist'])

    rs = {
        'year': list(dd['year']),
        'e': list(dd['e']),
        'j': list(dd['j']),
        'hist_year': list(dd['year']),
        'ror_stock': dd['ror_stock'].copy(),
        'dvd_stock': dd['dvd_stock'].copy(),
        'ror_bonds': dd['ror_bonds'].copy(),
        'infl_rate': dd['spend_δ'].copy(),
        'TAB': dd['net_pretax'].copy(),
        'disp_income': dd['disp_income'].copy(),
        'IRMAA': dd['IRMAA'].copy(),
        'income_tax': dd['income_tax'].copy(),
        'deposits': dd['SSA_income'].copy(),
        'withdrawals': dd['from_aTax'].copy(),
        'x_RothConv': dd['e_RothConv'].copy(),
    }
    sm = {'initial_DI': 0, 'smallest_DI': 0, 'mean_DI': 0, 'sdtdev_DI': 0, 'FTAB': 0, 'sum_DI': 0}
    cumm_infl = 1.0
    rs['TAB'][1] = dd['afterTax'][0] + dd['e_Taxd'][0] + dd['j_Taxd'][0] + dd['e_Roth'][0] + dd['j_Roth'][0]
    i = 0
    for year, row in hd[:].loc[historical_year_for_rates:historical_year_for_rates + len(dd['year']) - 2].iterrows():
        r = oorplp(dd, mode, objt, tout, glim)
        print('\n', flush=True)
        set_nut(dd, 'scip_status', r.status)
        set_nut(dd, 'scip_stage', r.stage)
        set_nut(dd, 'scip_gap', r.gap)
        set_nut(dd, 'scip_time', r.stime)
        if r.ok():
            print(f'FTAB: {r.net_pretax: 4.3f} DI 1st year: {r.di: 3.3f} Status: {r.status} at stage {r.stage} gap {100 * r.gap: 1.3f}% in {r.stime: 2.3f} s')
        else:
            print(f'Optimization failed, status {r.status} gap {100 * r.gap: 1.3f}% in {r.stime: 2.3f} s')
        i = year - historical_year_for_rates + 1
        if verbose:
            dfr = pd.DataFrame(dd, index=dd['year'])
            dfr.to_csv(fnvers(i))
        rs['hist_year'][i] = year
        rs['ror_stock'][i] = ror_stock = row['S']
        rs['ror_bonds'][i] = ror_bonds = row['B']
        rs['dvd_stock'][i] = dvd_stock = row['D']
        rs['infl_rate'][i] = infl_rate = row['I']

        def rori_r(y):
            return 1.0 + (ror_stock * dd['frac_stock_r'][y] + ror_bonds * dd['frac_bonds_r'][y])

        def rori_d(y):
            return 1.0 + (ror_stock * dd['frac_stock_d'][y] + ror_bonds * dd['frac_bonds_d'][y])

        dd['e_Taxd'][1] = rori_d(1) * (dd['e_Taxd'][0] - dd['e_RMD'][1] - dd['e_RothConv'][1] - dd['from_eTaxd'][1] + dd['e_Taxd_in'][1])
        dd['j_Taxd'][1] = rori_d(1) * (dd['j_Taxd'][0] - dd['j_RMD'][1] - dd['j_RothConv'][1] - dd['from_jTaxd'][1] + dd['j_Taxd_in'][1])
        dd['e_Roth'][1] = rori_r(1) * (dd['e_Roth'][0] - dd['from_eRoth'][1] + dd['e_RothConv'][1])
        dd['j_Roth'][1] = rori_r(1) * (dd['j_Roth'][0] - dd['from_jRoth'][1] + dd['j_RothConv'][1])
        assumed_div = dd['dividends'][1]
        actual_divd = ror_bonds * dd['aTax_bonds'][0] + dvd_stock * (dd['aTax_basis'][0] + dd['aTax_unrlz'][0])
        if actual_divd < assumed_div:
            if dd['aTax__cash'][1] > (assumed_div - actual_divd):
                dd['aTax__cash'][1] -= (assumed_div - actual_divd)
                dd['afterTax'][1] -= (assumed_div - actual_divd)
            else:
                dd['disp_income'][1] -= (assumed_div - actual_divd)
        else:
            dd['aTax__cash'][1] -= (assumed_div - actual_divd)
            dd['afterTax'][1] -= (assumed_div - actual_divd)
        cumm_infl *= (1.0 + infl_rate)
        infl_adj = 1.0 + (infl_rate - get_nut(dd, 'inflation'))
        rs['deposits'][i] = (dd['SSA_income'][1] + dd['misc_income'][1] + dd['pension_income'][1] + dd['taxfree_income'][1] + dd['dividends'][1]) / cumm_infl
        rs['withdrawals'][i] = (dd['e_RMD'][1] + dd['j_RMD'][1] + dd['from_eTaxd'][1] + dd['from_jTaxd'][1] + dd['from_aTax'][1] - dd['to_aTax'][1] + dd['from_eRoth'][1] + dd['from_jRoth'][1]) / cumm_infl
        rs['x_RothConv'][i] = (dd['e_RothConv'][1] + dd['j_RothConv'][1]) / cumm_infl
        rs['disp_income'][i] = dd['disp_income'][1] / cumm_infl
        rs['income_tax'][i] = dd['income_tax'][1] / cumm_infl
        rs['IRMAA'][i] = dd['IRMAA'][1] / cumm_infl
        rs['TAB'][i + 1] = (dd['afterTax'][1] + dd['e_Taxd'][1] + dd['j_Taxd'][1] + dd['e_Roth'][1] + dd['j_Roth'][1]) / cumm_infl
        if len(dd['e']) < 5:
            break
        for _, n in squirrel_map.items():
            dd[n][1] = dd[n][0]
        for y in range(2, len(dd['e'])):
            dd['QCD_limit'][y] *= infl_adj
            dd['IRMAA-buk0'][y] *= infl_adj
            dd['IRMAA-buk1'][y] *= infl_adj
            dd['IRMAA-buk2'][y] *= infl_adj
            dd['IRMAA-buk3'][y] *= infl_adj
            dd['IRMAA-buk4'][y] *= infl_adj
            dd['IRMAA-buk5'][y] *= infl_adj
            dd['IRMAA-chg0'][y] = float(dd['IRMAA-chg0'][y]) * infl_adj
            dd['IRMAA-chg1'][y] = float(dd['IRMAA-chg1'][y]) * infl_adj
            dd['IRMAA-chg2'][y] = float(dd['IRMAA-chg2'][y]) * infl_adj
            dd['IRMAA-chg3'][y] = float(dd['IRMAA-chg3'][y]) * infl_adj
            dd['IRMAA-chg4'][y] = float(dd['IRMAA-chg4'][y]) * infl_adj
            dd['IRMAA-chg5'][y] = float(dd['IRMAA-chg5'][y]) * infl_adj
            dd['tax0'][y] *= infl_adj
            dd['tax1'][y] *= infl_adj
            dd['tax2'][y] *= infl_adj
            dd['tax3'][y] *= infl_adj
            dd['tax4'][y] *= infl_adj
            dd['tax5'][y] *= infl_adj
            dd['tax6'][y] *= infl_adj
            dd['cgt0'][y] *= infl_adj
            dd['cgt15'][y] *= infl_adj
            dd['SSA_income'][y] *= infl_adj
            dd['surplus'][y] *= infl_adj
        for k, v in dd.items():
            dd[k] = v[1:]
        set_nut(dd, 'eoplan_spouse', get_nut(dd, 'eoplan_spouse') - 1)

    sm['initial_DI'] = rs['disp_income'][1]
    sm['smallest_DI'] = min(rs['disp_income'][1:i + 1])
    sm['mean_DI'] = statistics.mean(rs['disp_income'][1:i + 1])
    sm['sdtdev_DI'] = statistics.stdev(rs['disp_income'][1:i + 1])
    sm['FTAB'] = rs['TAB'][i + 1]
    sm['sum_DI'] = sum(rs['disp_income'][1:i + 1])
    rsf = pd.DataFrame(rs, index=rs['year'])
    rf = pd.DataFrame(rsf[1:i + 1])
    if verbose:
        rf.to_csv(fnvers(99))
    return (rf, sm, fname)
