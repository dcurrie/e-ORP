# e-ORP History

The evolution of e-ORP may be of interest to developers, maybe.

## OORP

OORP was maintained in a private repository... it embedded some personal data.

### OORP.jl

Using i-ORP in the years preceding my retirement, I formed an opinion about the 
rules-of-thumb to manage my drawdown. These rules related to Roth conversions,
IRMAA avoidance, realizing capital gains during the pre-SSA pre-RMD years, 
withdrawal order, etc.  Without i-ORP I'd have developed an inferior plan.

About that time I was learning Julia on a whim. So, I decided to create a tool
in Julia that would apply my rules-of-thumb to my evolving portfolio taking into 
account IRS and SSA inflation related changes. Since this tool was applying my
heuristics, I called it the Opinionated Optimal Retirement Planner, OORP.

The first version of OORP in 2020 was a native Julia app with plots using 
`StatsPlots`, data entry embedded in the code with `DataFrames`, and a local
optimizer using `Optim`. The optimizer was limited to using `NelderMead` to 
determine optimal withdrawals from tax deferred accounts for spending or 
Roth conversions, constrained by avoiding a big IRMAA hit.

### OORPnb.jl

Tired of editing the text file to construct data inputs to the model, the next
version of OORP utilized Jupyter and PlutoUI. I created it about the time it 
was necessary to update tax tables for 2021. It features UI widgets for data 
input, and could save and load the inputs using a Javascript hack with PlutoUI.
Otherwise the features were identical to OORP.jl.

I maintained OORPnb.jl into 2023.

## OORPy

Annoyed with the fragility of the PlutoUI/Javascript hack (no disrespect for 
PlutoUI intended! it's a nice tool, but not what I needed), I decided to port
the Julia notebook to Python when the 2024 tax tables update was needed.

### OORPy.ipynb

The Python version of OORP was initially even more opinionated than the Julia one.
I scrapped the Nelder-Mead numerical optimization when I determined that in my 
case it was always simply a matter of stopping tax deferred withdrawals at the 
top of some tax bracket. The more interesting variations on the plan were related
to things out of my control: possible expiration of the TCJA tax cuts, and possible
cut in SSA benefits in 2035 due to a federal government funding shortfall. So, the 
Julia optimizer was replaced with a "Plan Explorer" that ran the projection code
many times with variations of yes/no TCJA expiration in 2026, yes/no SSA cuts in 
2035, yes/no Roth conversions, and topping out those conversions and tax deferred
withdrawals at each of the tax brackets. The resulting 8 x 8 grid showed the pre- 
and post-tax Final Total Account Balance (FTAB) for each variation. A nice boxplot
 gave me a good picture of the range of outcomes. A second tool plotted the 
performance of the plan for a selected variation.

### taxcalc.ipynb

The tax calculation was a big piece of the code, and useful in its own right, so
I extracted it from OORPy.ipynb and created a separate tax calculator notebook 
in 2024 called taxcalc.ipynb.

## e-ORP

Reading about i-ORP's disappearance, and peoples' wishes for it's features, and 
looking for a hobby project now that I'm mostly retired, I decided to look into 
the world of Linear Programming Optimization in Python. This was also about the 
time of the OBBBA legislation that revised the tax code, and eliminated the TCJA
expiration uncertainty. (Unfortunately, it also increased the possible cut in 
SSA benefits in 2035 uncertainty.) 

### oorpylp.ipynb

Using PuLP for the linear programming bit, and the input widgets and output plots 
and tables from OORPy.ipynb made the creation of oorpylp.ipynb fairly 
straightforward. Unfortunately I hit a couple snags. One was that on my ARM64 based
Mac, PuLP installs the i64 version of the CBC solver. COIN-OR's plan is to un-bundle 
the solvers going forward, so I installed the CBC solver with Homebrew. Unfortunately,
this installs a boatload of dependencies, which seems extremely excessive since the 
older PuLP versions got away with a one file binary release of CBC, but at least it 
seems to work. The next problem is that the calculation of capital gains depends on 
maintaining a cost basis for the taxable "aftertax" account, and applying the ratio
of account basis to total account value to determine the realized gain. Thus the 
capital gains calculation is not linear (or at least I'm not clever enough to find
a way to make it so). I employed an inaccurate hack to prove to myself that the model
otherwise works well. The I sought out a non-linear solver.

### oorpynlp.ipynb

For the non-linear programming solver I turned to [PySCIPopt](https://pyscipopt.readthedocs.io/en/latest/index.html).
The transition was easy, and it handles the capital gains calculation... usually. 
See [my issue](https://github.com/scipopt/PySCIPOpt/issues/1039)... still pending.

### e-ORP

I used Binder to serve up the notebook. To do this I needed a public repo, so I renamed
oorpynlp.ipynb to e-ORP.ipnb and created the new (this) repo.
 

## Credits

Reference: [the i-ORP paper](https://issuu.com/iarfcregister/docs/vol.14issue1)
by James S. Welch, Jr.
Published in the Journal of Personal Finance Vol 14 issue 1 on Mar 4, 2015

