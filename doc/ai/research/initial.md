
Simple LP solvers are unable to perform some desired optimizations,
such as those that require computing capital gains taxes, or the
effects of asset sales while maintaining cost basis.

MINLP (mixed integer nonlinear programming) solvers can handle these
complications, but at the risk of long run times or getting stuck
in some situations. Timeouts or a target "gap" on the
relative primal dual bound difference can be used to terminate the
solver for easier interactive use.

