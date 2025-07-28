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

