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
on your local machine. The files in the `params` directory are available in the Jupyter notebook, and
can be opened or downloaded using the Jupyter menus. You may need to turn off the *Simple* switch at 
the bottom of the Jupyter window to see the file browser and notebook tabs. Alternatively, you can
use the *Dump* and *Restore* buttons to place the CSV text representation of the parameters in the 
text box to their left labeled *Param CSV*. Then you can use your browser's Copy and Paste commands
to put the text representation in your local clipboard to do with as you please.

OK, so what are these parameters?

## User Input, aka Model Parameters

TODO

## User Controls

TODO

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

The *name* is the one used in the code and in the csv file column name. *I/O* defines 
whether this column is an input to the solver, an output from the solver, or both. The *S* 
column indicates whether the cell at row 0 is used for "squirreled away" parameters. See below.

All dollar amounts are in $000s.

| Name   | I/O   | S     | Description |
| :---   | :---: | :---: | :--- |
| `year`           | in     |  | Calendar year |
| `e`              | in     |  | Spouse e age at end of this year |
| `j`              | in     |  | Spouse j age at end of this year |
| `surplus`        | in     |  | Desired surplus (FTAB) for the plan, adjusted for inflation for this year |
| `SSA_income`     | in     |  | Total of both spouses annual Social Security Income for this year |
| `misc_income`    | in     |  | Miscellaneous income for the year |
| `spend-δ`        | in     |  | Factor to increase spending relative to the prior year |
| `charity`        | in     |  | Amount of income to be spent annually on charity ; used only for QCD calculation |
| `income_reqd`    | in/out |  | For the default optimization option: the disposable income for the year; for the alternate (max FTAB) optimization option, the required DI for the year |
| `afterTax`       | in/out |  | Value of the after tax account for the year, year 0 is input |
| `aTax_basis`     | in/out |  | Cost basis of `afterTax` used in Capital Gains Tax calculations, year 0 is input |
| `e_Roth`         | in/out |  | Value of the spouse e Roth portion of the estate for the year, year 0 is input |
| `e_Taxd`         | in/out |  | Value of the spouse e tax deferred portion of the estate for the year, year 0 is input |
| `j_Roth`         | in/out |  | Value of the spouse j Roth portion of the estate for the year, year 0 is input |
| `j_Taxd`         | in/out |  | Value of the spouse j tax deferred portion of the estate for the year, year 0 is input |
| `e_RothConv`     | out    |  | The amount of the spouse e Roth conversion for the year |
| `j_RothConv`     | out    |  | The amount of the spouse j Roth conversion for the year |
| `e_RMD`          | out    |  | The amount of the spouse e Required Minimum Distribution (RMD) for the year |
| `j_RMD`          | out    |  | The amount of the spouse j Required Minimum Distribution (RMD) for the year |
| `auto_income`    | out    |  | The sum of "guaranteed income" for the year, Social Security, RMDs, Miscellaneous income, dividends, less IRMAA |
| `taxable_income` | out    |  | The calculated taxable income for the year, excluding capital gains |
| `IRMAA`          | out    |  | The calculated IRMAA, the full cost of Medicare Part B plus the Part D adjustment |
| `dividends`      | out    |  | The dividends generated by the after tax account and subject to income tax |
| `capgains`       | out    |  | The capital gains for the year on withdrawals from the after tax account, subject to income tax |
| `QCD`            | out    |  | The Qualified Charitable Distribution for the year, used in tax calculations |
| `income_tax`     | out    |  | Calculated income tax for the year |
| `tax_bracket`    | out    |  | Marginal income tax bracket for the year |
| `cgains_rate`    | out    |  | Marginal capital gains tax rate for the year |
| `MAGI`           | in/out |  | Modified Adjusted Gross Income for the year, used in IRMAA calculation two years later |
| `from_aTax`      | out    |  | The amount of the after tax account withdrawn for the year, or deposited there if negative |
| `from_eRoth`     | out    |  | The amount of the spouse e Roth withdrawn for the year, excluding Roth conversion  |
| `from_jRoth`     | out    |  | The amount of the spouse j Roth withdrawn for the year, excluding Roth conversion  |
| `from_eTaxd`     | out    |  | The amount of the spouse e tax deferred account withdrawn for the year, excluding Roth conversion and RMD |
| `from_jTaxd`     | out    |  | The amount of the spouse j tax deferred account withdrawn for the year, excluding Roth conversion and RMD |
| `e_RMD_factor`   | in     |  | The portion of the spouse e tax deferred account that must be withdrawn for RMD this year |
| `j_RMD_factor`   | in     |  | The portion of the spouse j tax deferred account that must be withdrawn for RMD this year |
| `QCD_limit`      | in     |  | The dollar limit for combined spouse QCDs for the year |
| `tax0`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax1`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax2`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax3`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax4`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax5`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `tax6`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `cgt0`           | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `cgt15`          | in     |  | Size of tax bracket in dollars calculated from tax tables, filing status, calendar year  |
| `obbba_pax`      | in     |  | Number of people qualifying for OBBBA retirement deduction based on filing status, calendar year |
| `IRMAA-buk0`     | in     |  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk1`     | in     |  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk2`     | in     |  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk3`     | in     |  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk4`     | in     |  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-buk5`     | in     |  | Size of IRMAA income bracket calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg0`     | in     |  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg1`     | in     |  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg2`     | in     |  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg3`     | in     |  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg4`     | in     |  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-chg5`     | in     |  | Size of IRMAA amount calculated from IRMAA tables, filing status, calendar year |
| `IRMAA-bins`     | out    |  | Base one encoding of the years's IRMAA level (1 is the base, 3 is level 2, 7 is level 3, etc.) |
| `net_pretax`     | out    |  | Total Account Balance, the sum of all accounts for the year |
| `net_postax`     | out    |  | The Total Account Balance adjusted by this year's marginal tax rates |

### Squirreled Away Parameters

There are some cells in row 0 that are unused by the solver, such as all of the output-only columns, and many of the 
calculated input columns (as opposed to the user input columns). These otherwise unused cells are used to hold 
miscellaneous inputs to the model, such as rates of return and inflation rate. This makes the `dd` csv file a 
complete record of the projection.

This `squirrel_map` shows the names of these miscellaneous parameters and the column name of the squirrel away location.

| Name            | Column        | Description |
| :---            | :---          | :---        |
| `inflation`     | `IRMAA-buk0`  | User input: inflation rate used for tax brackets, Social Security, etc. |
| `frac_bonds`    | `from_eRoth`  | User input: fraction of the account that is invested in bond-like securities |
| `frac_stock`    | `from_jRoth`  | User input: fraction of the account that is invested in stock-like securities |
| `ror_bonds`     | `from_eTaxd`  | User input: Rate of Return on the bond-like portion of the account |
| `ror_stock`     | `from_jTaxd`  | User input: Rate of Return on the stock-like portion of the account |
| `filing_status` | `tax_bracket` | User input: Federal Income Tax filing status, 0: Single, 1: MFJ, 2: Head of Household |
| `MAGI_prebase`  | `QCD_limit`   | User input: Modified Adjusted Gross Income for the year prior to the base year |
| `rothconv_enab` | `IRMAA-buk1`  | User control: Enabled Roth Conversions |
| `orp_objtv`     | `IRMAA-buk2`  | User control: Objective, `0.0` → max DI, the default; `net_pretax` → max FTAB  |
| `nlp_enab`      | `IRMAA-buk3`  | User control: MINLP Solver enabled |
| `basis_limit`   | `IRMAA-buk4`  | User control: Portion of after tax basis that may be applied in one year (non-MINLP only) |
| `gap_limit`     | `IRMAA-buk5`  | User control: Minimum primal/dual relative gap for solver (MINLP only) |
| `time_limit`    | `IRMAA-chg4`  | User control: Maximum time in seconds for solver to run |
| `scip_status`   | `IRMAA-chg0`  | Output: Solver status |
| `scip_stage`    | `IRMAA-chg1`  | Output: Solver stage |
| `scip_gap`      | `IRMAA-chg2`  | Output: Solver primal/dual relative gap achieved |
| `scip_time`     | `IRMAA-chg3`  | Output: Solver time in seconds |
|                 | `IRMAA-chg5`  |   |
| `e-ORP_version` | `from_aTax`   | Version number of the e-ORP implementation that calculated this projection |

