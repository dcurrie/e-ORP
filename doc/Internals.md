# e-ORP Internals

The model is fairly simple...

<picture>
 <source media="(prefers-color-scheme: dark)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/img/e-ORP_model_dark.drawio.png">
 <source media="(prefers-color-scheme: light)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/img/e-ORP_model.drawio.png">
 <img alt="e-ORP Model" src="[e-ORP](https://github.com/dcurrie/e-ORP/blob/main/doc/img/e-ORP_model.drawio.png)">
</picture>

We set up PySCIPopt to maintain the model and either

1. Maximize spending subject to the constraints
    - spending in year 1 is at least as large as the input income required 
    - each year's income increases by the spend inflation rate
    - the Final Total Account Balance equals the input amount
2. Maximize the Final Total Account Balance subject to the constraints
    - spending in each year is equal to the input income required
    - each year's income increases by the spend inflation rate

## Code Organization

The model is shared by the notebook and the desktop app, so both produce identical results:

- `planner.py` — parameter defaults and types, Historical Data, Tax Data, and the Planning Data Dictionary
- `solver.py` — The MINLP Optimization, the infeasibility diagnosis, and the `oorp` / `walk` / `three_peat` drivers
- `renderer.py` — the plots and tables, as a list of result items

Each front end is only a user interface over these. The notebook's UI code is on one (collapsed)
Jupyter cell, to reduce end user confusion by minimizing distractions; the desktop app's is
`backend.py` plus `frontend/` (see DESKTOP.md). A new kind of result item from `renderer.py` must be
drawn in two places: `display_items` in `renderer.py` for the notebook, and `renderResults` in
`frontend/app.js` for the desktop app.

The notebook cell is organized into these sections:
- Python Imports (including the shared model modules)
- Output Widget declarations
- Parameter Input Widgets
- Controls and Outputs
- User Control Widgets

The sections below describe both the notebook cell and the shared modules.

### Python Imports

This is just administrative stuff to import the libraries we use, such as `ipywidgets`, `pandas`, 
`IPython`, and `time`, and the shared `planner`, `solver`, and `renderer` modules. The notebook
locates those modules from the directory Jupyter was started in (or one of its parents).
`pyscipopt` is imported only by `solver.py`.

### Historical Data

In `planner.py`. An external spreadsheet has the historical data gleaned from Robert J. Schiller's published databases and
other public sources. This small section of code reads in the CSV file, and replicates it so that using a 
starting year near the end of the data wraps around back to the beginning (1970).

### Output Widget declarations

The general purpose standard output and error stream widgets are defined early so we can use them from 
anywhere. These widgets (`drb_out` and `err_out`) are displayed in the last line of i-ORP code!

### Parameter Input Widgets

Next we define the parameter input widgets and lay them out. This also includes the code to dump and 
load these parameters. Again, these widgets (in the `winputs` widget) is displayed in the last line of 
i-ORP code in the Jupyter cell!

Note that there is an odd looking hack here to support restoring non-textual widgets. See
[the Discourse Forum discussion](https://discourse.jupyter.org/t/save-and-restore-widget-values-the-right-way/37719)
for background or any possible workarounds.

### Tax Data

In `planner.py`. It might have been prudent to have put all the statutory tax data in an external spreadsheet for easier
maintenance, but the code evolved with the tax data inline here along with some supporting calculations. 

### The Planning Data Dictionary

In `planner.py`. Once all the input parameters are set, the first step in the "projection" into the future is to construct 
a data dictionary indexed by parameter and year. Essentially, anything that is preordained by the input 
parameters is calculated in advance of the optimization phase in this data dictionary. This includes 
some argument checking, and then year by year calculation of:
- Ages
- RMD factors
- Tax rates
- SSA and Pension incomes
- Miscellaneous Incomes
- Charitable Contributions
- Phases of Retirement Expenses and Incomes
- Asset Allocation glide path percentages
- Spend curve
- Rates of Return

This code also manages the "squirreled away" parameters.

The Planning Data Dictionary is organized so that every cell has one writer, either it is set by the 
`make_planning_datadict` function, or perhaps some calls to `set_nut` for "squirreled away" parameters,
or set by the optimizer, below. It represents a complete picture of the projection, and it should be
possible to completely reconstruct the projection/optimization from the result Planning Data Dictionary.

After the construction and optimization (below) phases, The Planning Data Dictionary is used as the
sole input to the reports and plots code. 

The Planning Data Dictionary is saved in a CSV file named by an input parameter. 

### The MINLP Optimization

In `solver.py`, function `oorplp`. It creates the "Mixed Integer Non-Linear Programming" Optimization model, and
calls the solver. Values in the Planning Data Dictionary that are malleable by the optimizer are
created as shadow SCIP variables, often initialized from the Base Year values in the Planning Data 
Dictionary. Other SCIP variables are created for intermediate calculations. 

Limits are set on most of the SCIP variables. These limits significantly improve solution time.

The model objective is set, and then the constraints.

We set some solvers parameters (see controls below), and then call the solver.

Once done, we copy the relevant SCIP variables (the `OUTS`) back to the Planning Data Dictionary.
Many of these are rounded to a dollar or so to make the output tables cleaner.

The memory used by SCIP for the model is freed, and the status of the solution returned as a
`SolveResult`. Its `ok()` is true only when the solver both stopped acceptably (optimal, or at the
time or gap limit) and found a solution; a time limit reached before any solution is found is not
a result.

#### Infeasibility diagnosis

When the solve is infeasible, `oorp` calls `diagnose_infeasible`, which re-solves a few cheap
variants of the model (always in the fastest mode, with a short time limit and a 5% gap):

0. Only when the user's mode is 1 or 4: the model as-is in mode 0. Mode 0 is not simply a
   relaxation of those modes — it drops basis averaging but forbids capital losses — so if this
   solves, the mode is reported as the cause. Otherwise step 1 would change the mode and the
   limits at once, and could blame the limits for what the mode did.
1. With the variable limits (see Limits, below) relaxed 4x. If that solves, the limits — not the
   user's inputs — were the cause, and the variables that exceeded them are reported.
2. "Elastic" versions in which a non-negative slack variable is added to the user-controllable
   constraints — the minimum residual, and the spending floor (or the fixed spending curve when
   maximizing the Final Total Account Balance) — and the objective is replaced by minimizing the
   inflation-deflated slack. The two families are relaxed separately, so each answers one question:
   how far must the Plan Surplus drop, or how far must spending drop? Without `elastic`, the slack
   terms are the literal `0.0`, so the normal model is unchanged.
3. With the Roth conversion limit removed.

`renderer.render_diagnosis` presents the result in place of the usual plots and tables.

Separately, `planner.triage_feasibility` runs at the end of `make_planning_datadict` — before any
solve — and warns when simple arithmetic shows a plan cannot work (essential spending exhausts every
account even with no tax and the best available return), or when the final-balance headroom is thin.

### Controls and Outputs

The Controls and Outputs section is a hodgepodge.

The creation of plots and tables is in `renderer.py`. These are used by the driver functions in
`solver.py`, which use the Planning Data Dictionary and MINLP Optimization in various ways depending on 
the User Control Widgets, below.

The functions implemented so far are the primary ORP optimization, `oorp`, the historical back test 
`walk`, and a barely begun `three_peat`.

### User Control Widgets

The User Controls provide a means to vary some SCIP parameters to see how they affect optimizer 
performance (I wish this wasn't necessary), and to select among solver modes (ditto), and to 
select between primary ORP optimization and historical back test (and maybe some day, 3-PEAT).

There's also a control for debugging use.

## Capital Gains are hard

The NLP solver really doesn't like to compute the optimal withdrawal from the afterTax account when 
Capital Gains are calculated "correctly." Correctly here means based on the assumption that each 
withdrawal from the afterTax account realizes a gain in proportion to the ratio of the
unrealized gain divided by the afterTax account balance. I.e., 

```
Gain = Withdrawal * (1 - (Basis / Account_Balance))
```

Taking after i-ORP, we assume that only the stock portion of the afterTax account has gains,
and that the basis is for that portion, so the calculation is a tiny bit more complicated: 

```
Gain = stock_fraction * Withdrawal * (1 - (Basis / (stock_fraction * Account_Balance)))
```

Anyway, the calculation chokes the solver for many portfolio configurations. (The solver  
runs for hours on my portfolio and makes little headway.)

The "correct" calculation above is suspicious anyway... each security in the afterTax account
has a separate basis, and can be sold independently. Blending the gains is not how a reasonable
person might approach divesting these positions. In some cases it makes sense to harvest
all gains in early years, while in others there are more nuanced approaches. 

With some optimizations in the code, such as range limits on some variables, and use of an
auxiliary variable holding the ratio, the time for the NLP version came down to minutes instead 
of hours, and typically reaches a reasonably small primal/dual gap in a handfulf of seconds.
So, I added User Control to select between the unconstrained approach and the ratio-metric approach.

## Limits

The limits are based on US household retirement savings statistics from the US Federal Reserve 2022 
Survey of Consumer Finances, which includes 2023 data. It is scheduled to be updated next in 2026.

Here are the data (inflation indexed to 2022) for the age bracket 65-69:

| category|  strict definition | expansive definition |
| :---    |          ---:      |                 ---: |
| average |           $337,197 |             $785,099 |
| top 1%  |	        $4,574,000 |          $10,424,000 |

Strict definition of retirement savings – "retirement accounts" and any defined benefit plans which have a cash value;
it includes IRAs, Keoghs, Pensions, and Thrift-type accounts (such as your 401(k) or 403(b)).

Expansive definition of retirement savings - adds "non-retirement accounts;" it includes all financial assets
other than the cash value of Whole Life Insurance, Trust, and non-liquid assets like collectables.

Adjusting these values to 2025 I considered a 3% adjustment per year, which matches or exceeds the CPI inflation rates 
measured in June 2023, 2024, 2025; 1.03^3 = 1.093. The markets did much better than that over the period, though, 
with the allocation fund category 3-year return currently at 11%; 1.11^3 = 1.368. If we use the higher number, the 
2025 adjusted values are:

| category|  strict definition | expansive definition |
| :---    |          ---:      |                 ---: |
| average |           $461,285 |           $1,074,015 |
| top 1%  |	        $6,257,232 |          $14,260,032 |

For age 80+ the 2025 adjusted values are:

| category|  strict definition | expansive definition |
| :---    |          ---:      |                 ---: |
| average |           $212,528 |           $1,001,075 |
| top 1%  |	        $4,296,888 |          $18,316,152 |

I suspect that any household in "the 1%" has a real financial advisor, and wouldn't need one who only plays
a financial advisor on GitHub. So, the model limits are based on the top 1% values. For each year in the 
model we'll adjust them by the input inflation factor. 

These were the original limits, and the fixed figures below (IRMAA, dividends, the lower tax
brackets) still come from this reasoning. The account limit no longer does; see *Account limit*.

The IRS Uniform Life Table for RMD Calculations has a Distribution Period in Years of 6.0 for 
age 101. That means the maximum RMD would be 1/6 of the total account value.

Other account withdrawals are to cover necessary expenses, like taxes and IRMAA, and to make 
disposable income. These use the same 1/6 limit as RMDs. Note that this is a heuristic rather
than a true bound, since a voluntary withdrawal could be a whole account; it can occasionally
clip the optimum slightly.

Dividends depend on the configured rate of return on bonds. Even at 12% we have less than 
$500,000 on a maxed out after tax account.

The maximum Social Security retirement benefit in 2025 is $5,108/month, $61,296 annually. 
But taxable income also includes those age 101 RMDs... so we'll use 2.25 times the RMD limit
as a fudge for dividends, Social Security income, and miscellaneous income.

Income tax is limited to 37% of that.

Individual tax brackets are limited by definition, except for the highest bracket for which
we'll use the taxable income limit.

Roth Conversions are unlimited by law. So, we'll use the account limit despite the
unlikelihood of ever coming close to that.

The non-QCD part of charitable giving (`nQCD`) is not limited by statute, so it is limited
only by the Charitable Contributions input.

### Account limit

The account limit, `max_tab`, is sized for each plan by `planner.asset_ceiling`. That is a
per-year upper bound on total assets: balances cannot compound faster than the best rate of
return available to any account, only external income (Social Security, pensions,
miscellaneous and tax-free income, lump-sum pension deposits) adds to them, and spending, taxes
and IRMAA only subtract. `max_tab` is the largest value of that ceiling in any year, deflated to
the base year, and is never less than twice the starting total, nor less than the Plan Surplus (inflated to
the final year).

Earlier versions used the smaller of $18,316,152 (the "top 1%" figure above) and twice the
starting total, indexed only to inflation. Because balances grow at the rate of return rather
than inflation, that limit fell behind over long planning horizons and made some valid plans
infeasible, and portfolios above $18.3M got a limit below their own opening balance.

Here are the limits for `e-ORP` ($000). Each is multiplied by the inflation factor for the year,
except `nQCD`, which follows the (already inflation-indexed) Charitable Contributions input:

| model variable   | limit year 1 of plan |
|      ---:        |                 ---: |
| `afterTax`       |       `max_tab` |
| `aTax_basis`     |       `max_tab` |
| `e_Roth`         |       `max_tab` |
| `e_Taxd`         |       `max_tab` |
| `j_Roth`         |       `max_tab` |
| `j_Taxd`         |       `max_tab` |
| `net_pretax`     |       `max_tab` |
| `e_RothConv`     |       `max_tab` |
| `j_RothConv`     |       `max_tab` |
| `e_RMD`          |       `max_xfr` = `max_tab` / 6 |
| `j_RMD`          |       `max_xfr` |
| `from_eRoth`     |       `max_xfr` |
| `from_jRoth`     |       `max_xfr` |
| `from_eTaxd`     |       `max_xfr` |
| `from_jTaxd`     |       `max_xfr` |
| `from_aTax`      |       `max_xfr` |
| `to_aTax`        |       `max_xfr` |
| `disp_income`    |       `max_inc` = 2.25 × `max_xfr` |
| `auto_income`    |       `max_inc` |
| `taxable_income` |       `max_inc` |
| `MAGI`           |       `max_inc` |
| `capgains`       |       `max_xfr` |
| `dividends`      |           500.0 |
| `income_tax`     |       `max_tax` = 0.37 × `max_inc` |
| `IRMAA`          |            34.0 |
| `taxb`           |            20.0 |
| `tax0`           |            50.0 |
| `tax1`           |            30.0 |
| `tax2`           |            80.0 |
| `tax3`           |           120.0 |
| `tax4`           |           220.0 |
| `tax5`           |           120.0 |
| `tax6`           |           280.0 |
| `tax7`           |       `max_inc` |
| `obbba_exc`      |       `max_inc` |
| `cgt0`           |           140.0 |
| `cgt15`          |            80.0 |
| `cgt20`          |       `max_inc` |
| `ncgt`           |       `max_inc` |
| `QCD`            |           220.0 |
| `nQCD`           | Charitable Contributions input |

If a plan is infeasible only because of these limits, the infeasibility diagnosis detects it
and says so (see *Infeasibility diagnosis*, above).

## Qualified Charitable Distributions (QCD)

I considered using a percentage of RMD, or a fixed amount contingent on RMD, but settled
on a defined annual charitable contribution that the plan maker intends to make independent
of any qualification. In other words, the charitable contribution does not enter into the 
calculations anywhere except taxes. As long as there are sufficient tax deferred withdrawals,
the amount of the withdrawals up to the specified annual charitable contribution amount, and
also limited by the statute, will be considered a Qualified Charitable Distribution for tax 
purposes. Since `e-ORP` is a spending optimizer, it will maximize the available tax deduction.

The defined annual charitable contribution is indexed to inflation.

## Squirreling away parameters

The data dictionary (`dd` in the code) is used for inputs to the model, and outputs from the
model. It is stored at the completion of each projection as a csv file. 

The `dd` is indexed by plan year, with year 0 being the "base year." Each row of the `dd` 
represents one plan year, and each column a parameter. The base year has only 
inputs to the model. As such, there are some unused cells in row 0, such as many of 
the output columns, and calculated columns. 
These cells are used to hold miscellaneous inputs to the model, such as rates of return
and inflation rate. 

The `squirrel_map` is used to map names of these miscellaneous parameters and column names.
The `set_nut` and `get_nut` functions are used to access the parameters.

## References

### Implementation References

[PyScipOpt documents](https://pyscipopt.readthedocs.io/en/latest/index.html)

[PyScipOpt API](https://pyscipopt.readthedocs.io/en/latest/api.html)

[SCIP documents](https://www.scipopt.org/doc/html/modules.php)

[Plotly](https://plotly.com/python/figure-labels/)

[ipywidgets](https://ipywidgets.readthedocs.io/en/latest/examples/Widget%20List.html)

[Binder](https://mybinder.readthedocs.io/en/latest/about/user-guidelines.html)

### Background references for setting limits in the i-ORP model

[Total portfolio size](https://dqydj.com/average-retirement-savings/)

[Total portfolio growth](https://dqydj.com/retirement-savings-by-age/)

[The 1%](https://peaceofmindinvesting.com/investing/american-retirement-savings-by-age-averages-medians-and-percentiles)

### i-ORP on the Wayback Machine

[Extended Input Form](https://web.archive.org/web/20210203192353/https://i-orp.com/Plans/extended.html)

[FAQ](https://web.archive.org/web/20201129140344/https://www.i-orp.com/Plans/faq.html)


### Academic Papers on Retirement Planning

[James S. Welch, Jr., Mitigating the Impact of Personal Income Taxes on Retirement Savings Distributions](https://issuu.com/iarfcregister/docs/vol.14issue1)
the paper describing i-ORP

[Lewis W. Coopersmith, Ph.D., and Alan R. Sumutka, CPA Tax-Efficient Retirement Withdrawal Planning Using a Linear Programming Model](https://www.financialplanningassociation.org/sites/default/files/2021-02/SEP11%20Tax-Efficient%20Retirement%20Withdrawal%20Planning%20Using%20a%20Linear%20Programming%20Model.pdf)
another linear programming optimization tool for retirement planning

### Historical Data

[Robert J. Schiller](http://www.econ.yale.edu/~shiller/data.htm)

[Treasury Rates](https://www.multpl.com/10-year-treasury-rate/table/by-year)

[Dividend Yields](https://www.multpl.com/s-p-500-dividend-yield/table/by-year)

[NYU data](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html)

