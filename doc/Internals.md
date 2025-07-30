# e-ORP Internals

The model is fairly simple...

<picture>
 <source media="(prefers-color-scheme: dark)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/e-ORP_model_dark.drawio.png">
 <source media="(prefers-color-scheme: light)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/e-ORP_model.drawio.png">
 <img alt="e-ORP Model" src="[e-ORP](https://github.com/dcurrie/e-ORP/blob/main/doc/e-ORP_model.drawio.png)">
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

With my hands tied on the "correct" approach, I added a tunable parameter to the UI for the fast 
LP solver to set the fraction of cost basis that may be applied to reduce capital gains annually. 
This gives me a satisfactory view of the benefits of realizing capital gains at various 
liquidation rates, or deferring altogether if the solver determines that it would be optimal. 


