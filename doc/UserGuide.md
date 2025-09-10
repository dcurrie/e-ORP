# e-ORP User Guide

## Data Flow

<picture>
 <source media="(prefers-color-scheme: dark)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/img/e-ORP_dataflow.drawio.png">
 <source media="(prefers-color-scheme: light)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/img/e-ORP_dataflow.drawio.png">
 <img alt="e-ORP" src="[e-ORP](https://github.com/dcurrie/e-ORP/blob/main/doc/img/e-ORP_dataflow.drawio.png)">
</picture>

## User Interaction

`e-ORP` is implemented in a Jupyter notebook. The notebook has two cells. The top one is
simply an intro to `e-ORP` presenting some simple instructions and a link to this User Guide.
The bottom cell is hidden by default; it has all the Python code that runs the `e-ORP` solver.

The user interface is started with the ▶ run button in the ribbon on the top of the `e-ORP` 
Jupyter notebook. Running the top cell does nothing special (it transitions from edit to 
view mode, but the cell should already be in view mode when the notebook is opened). Running
the bottom cell, even hidden, presents the user interface after a few seconds of setting up.

The user is presented with two sets of widgets. The top set we'll refer to as the User Inputs, 
and the bottom set is called the User Controls. The label for the User Inputs is 
**Set Model Parameters** and the label for the User Controls is **e-ORP Explorer**.

The User Inputs can be saved to and loaded from a file to make your life easier when you want
to revisit `e-ORP` after doing some explorations. I encourage you to save the inputs often, 
perhaps using a unique name for each variation of inputs. The filename is set in the box labeled
*File Name* to the left of the *Save* and *Load* buttons. The default filename is `params/fname.csv`;
The `params` directory exists in the installation and I encourage you to use it for saving your
inputs. The `.csv` extension indicates that the parameters are saved in Comma Separated Values file,
and can be opened with spreadsheet programs or text editors.

Unfortunately, when running on Binder, the `params` directory is on the Binder virtual machine, not
on your local machine. The files in the `params` directory are available in Jupyter, and
can be opened or downloaded using the Jupyter menus. You may need to turn off the *Simple* switch at 
the bottom of the Jupyter window to see the file browser and notebook tabs. Alternatively, you can
use the *Dump* and *Restore* buttons to place the CSV text representation of the parameters in the 
text box to their left labeled *Param CSV*. Then you can use your browser's Copy and Paste commands
to put the text representation in your local clipboard to do with as you please.

OK, so what are these parameters?

## User Input, aka Model Parameters

Note that all dollar amount inputs are in thousands of dollars, ($000s), as in `i-ORP`. 

### Base Year

The first input parameter is the Base Year. This is the year for which all account values are known, or
at least well estimated, at year end. The plan begins the year following the Base Year. Typically, a user
might plan at the start of a year for withdrawals, Roth conversions, etc., to perform that year. So, the
values entered are the year end values last year, the Base Year. Of course, if it is late in a year you can 
plan for next year by instead entering this year as the Base Year, and estimating all the year end account 
values for this year.

### Plan Surplus

The Plan Surplus is the value of all accounts that you wish to leave to your beneficiaries, or have available
should you live beyond your Planning Horizon. The surplus is in current (Base Year) dollars. `e-ORP` will 
adjust it for inflation when calculating the Final Total Asset Balance (FTAB), the amount that will actually 
be left at the end of the plan. As `i-ORP` pointed out, the Plan Surplus can be used to control spending, or
as longevity insurance, or as a planned legacy for your heirs. The default value is zero, the appropriate 
amount assuming you want to spend all your money.

### Ages at Base Year and Planning Horizon

The next inputs are the ages of the two spouses at the end of the Base Year. If you are single, you should set 
the age of Person to your age, and Spouse to zero.

Then you set the ages of the two spouses at their Planning Horizon. Quoting `i-ORP`, 

> There is a difference between your planning horizon and your life expectancy. Your planning horizon is the age
> at which you can prudently expect for your resources to satisfy your constant spending plan.
> Your life expectancy, as estimated by actuarial mortality tables, is probably somewhere between 78 and 85. Your 
> planning horizon needs to be longer than your life expectancy because there is a reasonable
> expectation that you will outlive your life expectancy and your financial planning has to account for that. 
> (Of course, if don't exceed your life expectancy then the savings you reserved to cover spending to
> your planning horizon becomes your estate.)
> A married couple's two planning horizons should reflect their separate life expectancies. A single person's 
> planning horizon reflects her life expectancy. A married couple's combined planning horizon will
> be longer than their individual life expectancies. The IRS default value is 92 for a married couple. When the 
> specified life expectancies are the same value then the plan proceeds in a uniform manner to its
> full term. It should be noted when the couple are of different ages and the same planning horizon is specified 
> for both, then the older spouse will be leaving the plan early.

### Different Planning Horizon for Spouses

When there are different planning horizons for each spouse:
- After one spouse leaves the plan, assets are transferred to remaining spouse...
- The Tax Deferred accounts are left separate, but we use the remaining spouse's RMD_factor for the departed spouse's account
- For Roth accounts we can just leave things alone; Roth Conversions may happen, but it's ok since we assume assets are merged
- For the afterTax account there is nothing to do since it's already co-mingled
- Spending is reduced by 25% to mimic `i-ORP`
- Social Security payments are adjusted... the remaining spouse gets the larger of either of the two spouses' benefits
- Pension income of the deceased spouse may accrue to the remaining spouse depending on the setting for "Survivor %"
- Tax filing status is changed to Single for the year after the deceased spouse's horizon

### Asset Valuations at the end of the Base Year

There are separate assets valuation for each spouse's accounts. This is necessary for Tax Deferred accounts where
Required Minimum Distributions (RMDs) are based on age. Unlike `i-ORP` we also keep Roth accounts separate to 
track Roth Conversions, but mathematically for the optimization this isn't necessary, though which account the 
conversion comes from is necessary, again because the spouses may have different ages. The After Tax accounts are
combined in the model.

*After Tax* includes all accounts on which income taxes have already been paid, and so can generally be spent without
tax implications, and have no mandatory distributions. The exception to the previous sentence are capital gains taxes.
See [Capital Gains](#capital-gains) for the gorey details. 

*Cost Basis* is the portion of the After Tax account that is the original purchase price of stocks. (Note when I say
*stocks* I mean all stock-like securities, ETFs, mutual funds, etc., basically anything that fluctuates in value and
upon which capital gains taxes apply.) If the Cost Basis exceeds the value of the stock portion of the account, then
you have unrealized losses, and if it's smaller then you have unrealized gains. The size of the stock portion of the 
account is determined using [Asset Allocation](#asset-allocation--glide-path) settings below.

*Tax Deferred* is a catch-all for all tax deferred accounts: as `i-ORP` put it: Keogh, profit sharing, IRA, 401(k), 
457(b), and 403(b) accounts are examples of Tax-deferred accounts.

*Roth IRA* is a catch-all for Roth accounts, Roth IRAs and Roth 401(k)s. These are accounts for which taxes have 
already been paid, including on gains, and may be withdrawn without tax implications after age 59.5.

### Social Security

If you will/do receive Social Security payments, this is the place to set them up. The value *SSA/year* is the 
person's annual Social Security benefit at the *Reference Age*. `e-ORP` adjusts this value for inflation based on 
the difference between the person's age in the current year less the *Reference Age*. If you are already receiving
Social Security payments, use the person's age at the end of the *Base Year* as the *Reference Age*, use your
current monthly Social Security benefit times 12 as the *SSA/year* value, and use a *Claim Age* lower than the the 
person's age at the end of the *Base Year*... 62 will do. If you expect to claim Social Security benefits in the 
future, use the person's expected annual benefit as *SSA/year* at the *Reference Age*. For example, if you plan to
claim benefits after your SSA full retirement age, you could use your full retirement age as the *Reference Age*,
your Primary Insurance Amount (PIA) as *SSA/year*, and the age you expect to claim benefits as *Claim Age*.

### Pensions

`e-ORP` provides the same three options for pensions as `i-ORP` did. If you have a tax-exempt pension, you should 
not enter it into `e-ORP` at all... just add your pension amount to `e-ORP`'s output to find your Disposable Income.

Each spouse may enter one pension. The three payout options are: fixed annual payments, annual inflation adjusted 
("COLA") payments, or one lump-sum payment. You can experiment with lump-sum versus annual distributions by switching
the parameters and observing the effect on Disposable Income. The *Claim Age* is the person's age when the payments
begin (or the one-time lump-sum payment is made). 

The *Survivor (%)* is the portion of the pension payments that accrue to a surviving spouse.

### Other Income

If you have other income, such as a part time job, or an inherited IRA, enter the expected annual taxable income here.
The *Misc. Inc. δ (%)* provides means to adjust this income over time. For example, if you expect your part time job 
hours to decrease by half each year, use -50.

### Phases of Retirement: Spending Model

`e-ORP` provides a subset of the spending models offered by `i-ORP`. There are two options: the Traditional Spending
Model (TSM), and the Changing Consumption model. 

The Traditional Spending Model is governed strictly by inflation, though an inflation rate for spending is provided
that is separate from the inflation rate used for tax brackets and pension/SSA adjustments. `i-ORP` calculates the 
Disposable Income for the plan so that it increases by the *SpendRate (%)* each year. 

The Changing Consumption model is based on David Blanchett's Estimating the True Cost of Retirement research. As `i-ORP`
explains, "it uses increased spending early in retirement and toward the end with reduced spending in mid plan. Normally 
Blanchett's values reduce the increase in spending caused by inflation. A zero inflation rate will cause retirement 
spending to form the shape of a smile." `i-ORP` adjusts the original Blanchett (and `i-ORP`) formula to account for 
actual inflation values since the research was conducted. The formula depends on expected annual spending since different
levels of affluence affect spending patterns. So, the *Spending $* input is used to shape the "smile" curve, and the 
*SpendRate (%)* is used as the spending inflation value. `i-ORP` plots the spending curve as part of the outputs.

### Phases of Retirement: Essential Spending and Extraordinary Expenses

TODO

### Asset Allocation & Glide Path

TODO

### Rates

This section is for the rates to use for general inflation, and returns on investments. 

The Inflation Rate is used to adjust IRS tax brackets annually, and to adjust Social Security payments.
Your entered Charitable Contributions are adjusted fot inflation, as well as the entered Plan Surplus.
You can also adjust pension payments if you choose the COLA option for that pension.

The Federal Reserve's long-term target inflation rate is 2%; over the last 25 years the inflation rate
averages 2.58%. Use your best judgement!

Note that the inflation rate used for spending is independent of this rate. 
See [Spending Model](#phases-of-retirement-spending-model)

Next you have the option of using historical rates of return, or fixed average rates per asset class.

`i-ORP` assumes that bond holdings are held to maturity and never result in a loss. My personal portfolio
only has Treasury bonds (and TIPS) arranged in a 10-year ladder of 10-year bonds at least one bond maturing
annually. So, the historical bond return used is simply the 10-year Treasury rate by year.

For annual historical stock returns, `i-ORP` uses the return on the S&P 500 Index and S&P 500 Annual 
Dividend rate.

The default is to use the average rates you enter for Stocks, Bonds, and Dividends.

### Taxes

TODO

### Modeling Assumptions and Constraints

TODO

### Parameter Save & Load

TODO

## User Controls

TODO

### Optimizer Controls

TODO

### Developer & SCIP Controls

TODO

## Capital Gains

Capital Gains calculations only pertain to the After Tax portion of the portfolio. 

`e-ORP` maintains the After Tax account as four separate sub-accounts: Bonds, Cash, Cost Basis of Stock sub-account, 
Unrealized Gains of Stock sub-account. These are initialized using the user inputs: After Tax account balance, 
Cost Basis of Stock sub-account, and percentage of After Tax account in stocks, and in bonds (the rest is cash).

The `e-ORP` LP Optimizer is then free to withdraw from any of these sub-accounts independently, or deposit to them,
subject to the constraints that deposits from outside the stock sub-accounts go to the Cost Basis, and growth 
of the stock sub-accounts based on the ROR specified by the user goes to the Unrealized Gains.

Capital Gains are a difficult calculation for an LP Optimizer. It would like to keep taxable gains as low as 
possible when tax rates are high, so if there is a Cost Basis the optimizer would like to spend the Cost Basis 
portion of the account, but not the Realized Gain portion. In reality we can't do this. Even if we could choose
the stock lots in our portfolio with the highest Cost Basis percentage, that percentage is unlikely to be 100%
unless we have no Realized Gains in the account. We'd like to limit the optimizer's ability to do this.

On the other hand, spending as much of the Realized Gains as possible when capital gains taxes are low is 
perfectly fine. This is just tax-gain harvesting, and can be accomplished in real life by selling the entire stock 
portion of the account and buying back whatever isn't otherwise spent.

The solution I used in earlier simulators was to constrain withdrawals from the After Tax account so that the 
same percentage was taken from each sub account, or at least the same percentage from the Cost Basis and 
Unrealized Gains. Unfortunately, this is not a linear calculation (since it needs to find the ratio of Cost Basis
and Unrealized Gains), so it can't be done in an LP optimizer.

One solution is to just let the optimizer go and let it take unrealistic withdrawals from the Cost Basis. This
was not fully satisfying to me. So, `e-ORP` provides a User Control to select between unconstrained withdrawals
from the Cost Basis, or to do "Basis Averaging" where the same proportion of the Unrealized Gains and Cost Basis
are withdrawn (and, so, Capital Gains are realized). Unfortunately, this mode is much slower than the 
unconstrained mode, and rarely makes much of a difference, hence the User Control, which defaults to the faster
option.

Handling Capital Losses is similarly fraught with non-linear-programming aspects. The Unrealized Gains sub-account
is optionally allowed to be a negative number, one of the few in the optimizer. So, `e-ORP` provides a User Control 
to select between allowing losses or not. Typically, when the starting Unrealized Gains is zero or more, and the 
rates of return are all positive, there will be no losses. So, selecting the faster No Capital Losses mode is the
obvious choice since it is much faster and equally accurate. Unfortunately, Capital Losses are needed for the 
negative rates of return introduced by Monte Carlo or 3-PEAT, if/when these are released.

## Reports

### Nominal Spending Table

| Column Name    | Description |
| :---:          | :--- |
| `year`         | The calendar year |
| `e`            | Age of spouse 1 |
| `j`            | Age of spouse 2 |
| `fixed_income` | The sum of RMDs, SSA and pension income, miscellaneous income, and dividends (+) |
| `withdrawals`  | Withdrawals from all accounts (+), including Roth Conversions (+) |
| `transfers`    | Transfers into the After Tax account (-) and Roth Conversions (-) |
| `IRMAA-bins`   | The IRMAA bracket as a unary number |
| `IRMAA`        | The calculated IRMAA, the full cost of Medicare Part B plus the Part D adjustment (-) |
| `income_tax`   | Federal Income Tax (-) |
| `DI`           | Disposable Income (+) |

The disposable income `DI` 
is the sum of the columns: `fixed_income`, `withdrawals`, `transfers`, `IRMAA`, and `income_tax`.

## Printing and Accessing Output Data

Browsers don't print, or export to PDF, Jupyter notebook outputs well, or at all.

Take a look at the *GoFullPage* plugin for Chrome if you'd really like to print `e-ORP` output. So
far it's the only thing I've found that works.

You can also copy, and download plots using the Plotly.js controls in the upper right corner of each plot.

If you select and copy the text of output tables it will paste nicely into a spreadsheet.

The entire **Data Dictionary** for the `e-ORP` projection is also downloaded automatically to a file. 
The filename is configured at the bottom of the User Controls section in the textbox with label
*Output to:*. By default the output goes to the filename `data/explore.csv`. 
As with the input parameters, a directory exists in the installation for this purpose, `data`.
See the description of how to retrieve files when running on Binder above.

## Data Dictionary

The data dictionary (`dd` in the code) is used for inputs to the model, and outputs from the
model. It is stored at the completion of each projection as a csv file. 

The `dd` is indexed by plan year, with year 0 being the "base year." Each row of the `dd` 
represents one plan year, and each column a parameter. Here is a guide to the parameters.

The *name* is the one used in the code and in the csv file column name. The *0* column shows *in* for
base year inputs to the solver, and a nut 🌰 for  "squirreled away" parameters (see below). The *1...*
column shows *in* for inputs to the solver for projection years, and *out* for outputs from the solver.

All dollar amounts are in $000s.

| Name   | 0  | 1...     | Description |
| :---   | :---: | :---: | :--- |
| `year`           |    | in  | Calendar year |
| `e`              |    | in  | Spouse e age at end of this year |
| `j`              |    | in  | Spouse j age at end of this year |
| `surplus`        |    | in  | Desired surplus (FTAB) for the plan, adjusted for inflation for this year |
| `SSA_income`     |    | in  | Total of both spouses annual Social Security Income for this year |
| `misc_income`    |    | in  | Miscellaneous income for the year |
| `spend-δ`        |    | in  | Factor to increase spending relative to the prior year |
| `charity`        |    | in  | Amount of income to be spent annually on charity ; used only for QCD calculation |
| `frac_bonds`     |    | in  | Fraction of the account that is invested in bond-like securities for this year |
| `frac_stock`     |    | in  | Fraction of the account that is invested in stock-like securities for this year |
| `ror_bonds`      |    | in  | Rate of Return on the bond-like portion of the account for this year |
| `ror_stock`      |    | in  | Rate of Return on the stock-like portion of the account for this year |
| `afterTax`       | in | out | Value of the after tax account for the year, year 0 is input |
| `aTax_basis`     | in | out | Cost basis of `afterTax` used in Capital Gains Tax calculations, year 0 is input |
| `e_Roth`         | in | out | Value of the spouse e Roth portion of the estate for the year, year 0 is input |
| `e_Taxd`         | in | out | Value of the spouse e tax deferred portion of the estate for the year, year 0 is input |
| `j_Roth`         | in | out | Value of the spouse j Roth portion of the estate for the year, year 0 is input |
| `j_Taxd`         | in | out | Value of the spouse j tax deferred portion of the estate for the year, year 0 is input |
| `MAGI`           | in | out | Modified Adjusted Gross Income for the year, used in IRMAA calculation two years later |
| `disp_income`    | *  | *** | The disposable income for the year, for the default optimization option: an output; for the alternate (max FTAB) optimization option, an input |
| `e_RothConv`     |    | out | The amount of the spouse e Roth conversion for the year |
| `j_RothConv`     |    | out | The amount of the spouse j Roth conversion for the year |
| `e_RMD`          |    | out | The amount of the spouse e Required Minimum Distribution (RMD) for the year |
| `j_RMD`          |    | out | The amount of the spouse j Required Minimum Distribution (RMD) for the year |
| `auto_income`    |    | out | The sum of "guaranteed income" for the year, Social Security, RMDs, Miscellaneous income, dividends, less IRMAA |
| `taxable_income` |    | out | The calculated taxable income for the year, excluding capital gains |
| `IRMAA`          |    | out | The calculated IRMAA, the full cost of Medicare Part B plus the Part D adjustment |
| `dividends`      |    | out | The dividends generated by the after tax account and subject to income tax |
| `capgains`       |    | out | The capital gains for the year on withdrawals from the after tax account, subject to income tax |
| `QCD`            |    | out | The Qualified Charitable Distribution for the year, used in tax calculations |
| `income_tax`     |    | out | Calculated income tax for the year |
| `tax_bracket`    | 🌰 | out | Marginal income tax bracket for the year |
| `cgains_rate`    |    | out | Marginal capital gains tax rate for the year |
| `from_aTax`      | 🌰 | out | The amount withdrawn from the after tax account for the year |
| `to_aTax`        |    | out | The amount deposited to the after tax account for the year |
| `from_eRoth`     |    | out | The amount of the spouse e Roth withdrawn for the year, excluding Roth conversion  |
| `from_jRoth`     |    | out | The amount of the spouse j Roth withdrawn for the year, excluding Roth conversion  |
| `from_eTaxd`     |    | out | The amount of the spouse e tax deferred account withdrawn for the year, excluding Roth conversion and RMD |
| `from_jTaxd`     |    | out | The amount of the spouse j tax deferred account withdrawn for the year, excluding Roth conversion and RMD |
| `e_Taxd_in`      |    | in  | Amount to add to the spouse e tax deferred portion for the year, e.g., lump sum pension distribution |
| `j_Taxd_in`      |    | in  | Amount to add to the spouse j tax deferred portion for the year, e.g., lump sum pension distribution |
| `e_RMD_factor`   |    | in  | The portion of the spouse e tax deferred account that must be withdrawn for RMD this year |
| `j_RMD_factor`   |    | in  | The portion of the spouse j tax deferred account that must be withdrawn for RMD this year |
| `QCD_limit`      | 🌰 | in  | The dollar limit for combined spouse QCDs for the year |
| `tax0`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax1`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax2`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax3`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax4`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax5`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax6`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `cgt0`           |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `cgt15`          |    | in  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `obbba_pax`      |    | in  | Number of people qualifying for OBBBA retirement deduction based on filing status, calendar year |
| `IRMAA-buk0`     | 🌰 | in  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk1`     | 🌰 | in  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk2`     | 🌰 | in  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk3`     | 🌰 | in  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk4`     | 🌰 | in  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk5`     | 🌰 | in  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg0`     | 🌰 | in  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg1`     | 🌰 | in  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg2`     | 🌰 | in  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg3`     | 🌰 | in  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg4`     | 🌰 | in  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg5`     | 🌰 | in  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-bins`     |    | out | Base one encoding of the years's IRMAA level (1 is the base, 3 is level 2, 7 is level 3, etc.) |
| `net_pretax`     |    | out | Total Account Balance, the sum of all accounts for the year |
| `net_postax`     |    | out | The Total Account Balance adjusted by this year's marginal tax rates |

### Squirreled Away Parameters

There are some cells in row 0 that are unused by the solver, such as all of the output-only columns, and many of the 
calculated input columns (as opposed to the user input columns). These otherwise unused cells are used to hold 
miscellaneous inputs to the model, such as rates of return and inflation rate. This makes the `dd` csv file a 
complete record of the projection.

This `squirrel_map` shows the names of these miscellaneous parameters and the column name of the squirrel away location.

| Name            | Column        | Description |
| :---            | :---          | :---        |
| `inflation`     | `IRMAA-buk0`  | User input: inflation rate used for tax brackets, Social Security, etc. |
| `filing_status` | `tax_bracket` | User input: Federal Income Tax filing status, 0: Single, 1: MFJ, 2: Head of Household |
| `MAGI_prebase`  | `QCD_limit`   | User input: Modified Adjusted Gross Income for the year prior to the base year |
| `orp_mode`      | `IRMAA-buk1`  | User control: Mode: 0 → default==mode3, 1 → no capital losses, 2 → no capgains basis averaging, 3 → neither, 4 → full slow mode |
| `orp_objtv`     | `IRMAA-buk2`  | User control: Objective, `0.0` → max DI, the default; `net_pretax` → max FTAB  |
|                 | `IRMAA-buk3`  |  |
| `min_realized`  | `IRMAA-buk4`  | User control: Minimum realized gain as a percentage of cost basis withdrawn that must be taken in any year (non-MINLP only) |
| `gap_limit`     | `IRMAA-buk5`  | User control: Minimum primal/dual relative gap for solver (MINLP only) |
| `time_limit`    | `IRMAA-chg4`  | User control: Maximum time in seconds for solver to run |
| `Roth_conv_max` | `IRMAA-chg5`  | User control: Maximum tax bracket for Roth conversions |
| `scip_status`   | `IRMAA-chg0`  | Output: Solver status |
| `scip_stage`    | `IRMAA-chg1`  | Output: Solver stage |
| `scip_gap`      | `IRMAA-chg2`  | Output: Solver primal/dual relative gap achieved |
| `scip_time`     | `IRMAA-chg3`  | Output: Solver time in seconds |
| `e-ORP_version` | `from_aTax`   | Version number of the e-ORP implementation that calculated this projection |

Deprecated:

| Name            | Column        | Description |
| :---            | :---          | :---        |
| `nlp_enab`      | `IRMAA-buk3`  | User control: MINLP Solver enabled |
| `rothconv_enab` | `IRMAA-buk1`  | User control: Enabled Roth Conversions |
