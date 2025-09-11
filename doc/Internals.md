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

The code is all on one (collapsed) Jupyter cell. This is primarily to reduce end user confusion by
minimizing distractions, but it does make the code a bit daunting to read.

The code is organized into these sections:
- Python Imports
- Historical Data
- Output Widget declarations
- Parameter Input Widgets
- Tax Data
- The Planning Data Dictionary
- The MINLP Optimization
- Controls and Outputs
- User Control Widgets

### Python Imports

This is just administrative stuff to import the libraries we use, such as `ipywidgets`, `pandas`, 
`plotly.express`, `IPython`, `math`, `io`, `time`, and `pyscipopt`

### Historical Data

An external spreadsheet has the historical data gleaned from Robert J. Schiller's published databases and
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

It might have been prudent to have put all the statutory tax data in an external spreadsheet for easier
maintenance, but the code evolved with the tax data inline here along with some supporting calculations. 

### The Planning Data Dictionary

Once all the input parameters are set, the first step in the "projection" into the future is to construct 
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

The next section of code creates the "Mixed Integer Non-Linear Programming" Optimization model, and
calls the solver. Values in the Planning Data Dictionary that are malleable by the optimizer are
created as shadow SCIP variables, often initialized from the Base Year values in the Planning Data 
Dictionary. Other SCIP variables are created for intermediate calculations. 

Limits are set on most of the SCIP variables. These limits significantly improve solution time.

The model objective is set, and then the constraints.

We set some solvers parameters (see controls below), and then call the solver.

Once done, we copy the relevant SCIP variables (the `OUTS`) back to the Planning Data Dictionary.
Many of these are rounded to a dollar or so to make the output tables cleaner.

The memory used by SCIP for the model is freed, and the status of the solution returned.

### Controls and Outputs

The Controls and Outputs section is a hodgepodge.

There is a subsection for the creation of plots and tables. These are used by the functions that
follow, which use the Planning Data Dictionary and MINLP Optimization in various ways depending on 
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

For total account values, we'll use the biggest number in the tables above, $18,316,152.
Since we don't want to limit the solver's flexibility in moving funds among the various 
account buckets, we'll use the same number for all accounts.

Roth Conversions are unlimited by law. So, we'll use the total account value limit despite the
unlikelihood of ever coming close to that.

The IRS Uniform Life Table for RMD Calculations has a Distribution Period in Years of 6.0 for 
age 101. That means the maximum RMD would be 1/6 of the total account value.

Other account withdrawals are to cover necessary expenses, like taxes and IRMAA, and to make 
disposable income. Can we all agree that $3MM a year is enough!? ;-)

Dividends depend on the configured rate of return on bonds. Even at 12% we have less than 
$500,000 on a maxed out after tax account.

The maximum Social Security retirement benefit in 2025 is $5,108/month, $61,296 annually. 
But taxable income also includes those age 101 RMDs... so we'll use double that value
plus a fudge for dividends, Social Security income, and miscellaneous income.

Income tax on that would be $2,187,171. Yikes!

Individual tax brackets are limited by definition, except for the highest bracket for which
we'll use the taxable income limit.

Here are the limits scaled for `e-ORP` ($000):

| model variable   | limit year 1 of plan |
|      ---:        |                 ---: |
| `afterTax`       |              18316.2 |
| `aTax_basis`     |              18316.2 |
| `e_Roth`         |              18316.2 |
| `e_Taxd`         |              18316.2 |
| `j_Roth`         |              18316.2 |
| `j_Taxd`         |              18316.2 |
| `net_pretax`     |              18316.2 |
| `e_RothConv`     |              18316.2 |
| `j_RothConv`     |              18316.2 |
| `e_RMD`          |               3052.7 |
| `j_RMD`          |               3052.7 |
| `from_eRoth`     |               3052.7 |
| `from_jRoth`     |               3052.7 |
| `from_eTaxd`     |               3052.7 |
| `from_jTaxd`     |               3052.7 |
| `from_aTax`      |               3052.7 |
| `to_aTax`        |               3052.7 |
| `income_reqd`    |               6969.7 |
| `auto_income`    |               6969.7 |
| `taxable_income` |               6969.7 |
| `MAGI`           |               6969.7 |
| `capgains`       |               3052.7 |
| `dividends`      |                500.0 |
| `income_tax`     |               2187.2 |
| `IRMAA`          |                 20.0 |
| `taxb`           |                 20.0 |
| `tax0`           |                 50.0 |
| `tax1`           |                 30.0 |
| `tax2`           |                 80.0 |
| `tax3`           |                120.0 |
| `tax4`           |                220.0 |
| `tax5`           |                120.0 |
| `tax6`           |                280.0 |
| `tax7`           |               6969.7 |
| `obbba_exc`      |               6969.7 |
| `cgt0`           |                140.0 |
| `cgt15`          |                 80.0 |
| `cgt20`          |               6969.7 |
| `ncgt0`          |                140.0 |
| `ncgt15`         |                 80.0 |
| `ncgt20`         |               6969.7 |
| `QCD`            |                220.0 |
| `nQCD`     c     |                220.0 |

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

