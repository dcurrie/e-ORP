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
