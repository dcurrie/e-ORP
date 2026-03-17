"""taxcalc_ui.py — Standalone Tkinter front-end for taxcalc.py"""

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from taxcalc import tax_calc, tax_brackets_for_year, calc_tax

import pandas as pd

FILING_OPTIONS = ["Single", "Married Filing Jointly"]
FILING_STATUS  = {"Single": 0, "Married Filing Jointly": 1}

PAD = {"padx": 6, "pady": 3}


# ############## Helpers ##############

def _write(widget, text):
    widget.config(state=tk.NORMAL)
    widget.insert(tk.END, text + "\n")
    widget.config(state=tk.DISABLED)
    widget.see(tk.END)

def _clear(widget):
    widget.config(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.config(state=tk.DISABLED)

def _float(var, default=0.0):
    try:
        return float(var.get().replace(",", ""))
    except ValueError:
        return default

def _int(var, default=2025):
    try:
        return int(var.get().replace(",", ""))
    except ValueError:
        return default


# ############## Validation ##############

def _make_float_validator(root, lo, hi):
    """Return a (vcmd, 'focusout') pair that clamps entry to [lo, hi] on focus-out."""
    def validate(val):
        try:
            v = float(val.replace(",", ""))
            return lo <= v <= hi
        except ValueError:
            return val == "" or val == "-"
    vcmd = (root.register(validate), "%P")
    return vcmd


# ############## Main Window ##############

class TaxCalcApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("e Tax Calc")
        self.resizable(True, True)
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Title ──
        ttk.Label(main, text="e Tax Calc",
                  font=("TkDefaultFont", 14, "bold"),
                  foreground="forestgreen").grid(row=0, column=0, columnspan=3,
                                                  sticky="w", **PAD)

        ttk.Label(main, text="Inputs",
                  font=("TkDefaultFont", 11, "bold")).grid(row=1, column=0,
                                                            columnspan=3,
                                                            sticky="w", **PAD)

        # ── Input rows ──
        fields = [
            # (label,           var_name,      lo,        hi,       hint)
            ("Tax Year:",       "year",        2000,      9999,     "The tax year for the calculation"),
            ("Net Earnings:",   "npay",        0,         250000,   "Net pay exclusive of pre-tax deductions (e.g. 401k)"),
            ("IRA Distrib.:",   "irad",        0,         250000,   "Taxable IRA distributions (including QCD)"),
            ("QCD:",            "iqcd",        0,         250000,   "Qualified Charitable Distribution (QCD)"),
            ("Interest:",       "intr",        0,         250000,   "Taxable interest"),
            ("Dividends:",      "dvdd",        0,         250000,   "Dividends"),
            ("SSA Income:",     "ssai",        0,         250000,   "Social Security benefit income"),
            ("ST Gains:",       "stgn",        0,         250000,   "Short-term capital gains"),
            ("LT Gains:",       "ltgn",        0,         250000,   "Long-term capital gains"),
            ("Gains Carry:",    "gcry",       -250000,    250000,   "LT capital gains carryover from prior year"),
        ]

        self._vars = {}
        for i, (lbl, name, lo, hi, hint) in enumerate(fields):
            row = i + 2
            ttk.Label(main, text=lbl, anchor="e").grid(row=row, column=0, sticky="e", **PAD)
            var = tk.StringVar(value="0")
            self._vars[name] = var
            ent = ttk.Entry(main, textvariable=var, width=14, justify="right")
            ent.grid(row=row, column=1, sticky="w", **PAD)
            ttk.Label(main, text=hint, foreground="gray").grid(row=row, column=2, sticky="w", **PAD)

        # ── Filing Status ──
        fs_row = len(fields) + 2
        ttk.Label(main, text="Filing Status:", anchor="e").grid(row=fs_row, column=0, sticky="e", **PAD)
        self._fs_var = tk.StringVar(value="Married Filing Jointly")
        fs_cb = ttk.Combobox(main, textvariable=self._fs_var,
                             values=FILING_OPTIONS, state="readonly", width=22)
        fs_cb.grid(row=fs_row, column=1, columnspan=2, sticky="w", **PAD)

        # ── Buttons ──
        btn_row = fs_row + 1
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=btn_row, column=0, columnspan=3, sticky="w", **PAD)
        ttk.Button(btn_frame, text="Run Tax Calc",
                   command=self._run_calc).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Clear Output",
                   command=self._clear_all).pack(side="left", padx=(0, 8))

        # ── Test section ──
        test_row = btn_row + 1
        ttk.Separator(main, orient="horizontal").grid(row=test_row, column=0,
                                                       columnspan=3, sticky="ew",
                                                       pady=6)
        ttk.Label(main, text="Test e-ORP file:").grid(row=test_row+1, column=0,
                                                       sticky="e", **PAD)
        self._fname_var = tk.StringVar(value="../data/_explore.csv")
        ttk.Entry(main, textvariable=self._fname_var, width=36).grid(
            row=test_row+1, column=1, columnspan=2, sticky="ew", **PAD)
        ttk.Button(main, text="Test e-ORP Tax Calc",
                   command=self._run_test).grid(row=test_row+2, column=0,
                                                columnspan=3, sticky="w", **PAD)

        # ── Output panes ──
        out_row = test_row + 3
        ttk.Label(main, text="Errors:",
                  font=("TkDefaultFont", 9, "bold")).grid(row=out_row, column=0,
                                                           columnspan=3, sticky="w", **PAD)
        self._err_box = ScrolledText(main, height=4, state=tk.DISABLED,
                                     background="#fff0f0", font=("Courier", 10))
        self._err_box.grid(row=out_row+1, column=0, columnspan=3, sticky="nsew", **PAD)

        ttk.Label(main, text="Results:",
                  font=("TkDefaultFont", 9, "bold")).grid(row=out_row+2, column=0,
                                                           columnspan=3, sticky="w", **PAD)
        self._out_box = ScrolledText(main, height=16, state=tk.DISABLED,
                                     font=("Courier", 10))
        self._out_box.grid(row=out_row+3, column=0, columnspan=3, sticky="nsew", **PAD)

        main.columnconfigure(2, weight=1)
        main.rowconfigure(out_row+1, weight=1)
        main.rowconfigure(out_row+3, weight=3)

    # ──────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────

    def _clear_all(self):
        _clear(self._err_box)
        _clear(self._out_box)

    def _run_calc(self):
        _clear(self._err_box)

        try:
            year     = _int  (self._vars["year"])
            npay     = _float(self._vars["npay"])
            irad     = _float(self._vars["irad"])
            iqcd     = _float(self._vars["iqcd"])
            intr     = _float(self._vars["intr"])
            dvdd     = _float(self._vars["dvdd"])
            ssai     = _float(self._vars["ssai"])
            stgn     = _float(self._vars["stgn"])
            ltgn     = _float(self._vars["ltgn"])
            gcry     = _float(self._vars["gcry"])
            fs       = FILING_STATUS[self._fs_var.get()]

            income   = npay + irad + intr - iqcd + dvdd + ssai * 0.85 + stgn
            capgains = ltgn + gcry
            MAGI     = income + capgains + ssai * 0.15 + iqcd

            (tax, mrate, crate, brend, sd, ibtax, cgtax) = tax_calc(
                year, fs, income, capgains, MAGI)

            _write(self._out_box,
                   f"\n{'─'*38}"
                   f"\n{year:>11d}  Tax Year"
                   f"\n{income:>14,.2f}  Income"
                   f"\n{capgains:>14,.2f}  LTCG"
                   f"\n{income + capgains:>14,.2f}  AGI"
                   f"\n{tax:>14,.2f}  Total Tax"
                   f"\n{ibtax:>14,.2f}  Tax on Income"
                   f"\n{cgtax:>14,.2f}  Tax on Capital Gains"
                   f"\n{mrate:>14.0%}  Marginal rate on Income"
                   f"\n{crate:>14.0%}  Marginal rate on Capital Gains"
                   f"\n{brend:>14,.2f}  End of income bracket"
                   f"\n{sd:>14,.2f}  Standard deduction")

        except Exception as exc:
            _write(self._err_box, f"ERROR: {exc}")

    def _run_test(self):
        _clear(self._err_box)

        try:
            dd = pd.read_csv(self._fname_var.get())
        except Exception as exc:
            _write(self._err_box, f"ERROR reading file: {exc}")
            return

        try:
            YRS                 = len(dd["e"]) - 1
            infl                = dd["IRMAA-buk0"][0]
            y_spouse_leaves     = dd["IRMAA-buk3"][0]
            filing_status       = round(dd["tax_bracket"][0])

            for y in range(1, YRS + 1):
                year       = dd["year"][y]
                income     = dd["taxable_income"][y]
                capgains   = dd["capgains"][y]
                ssa_income = dd["SSA_income"][y]
                MAGI       = income + capgains + 0.15 * ssa_income + dd["QCD"][y]

                if filing_status != 1 or y >= y_spouse_leaves:
                    filing_status = 0

                tb = tax_brackets_for_year(year, filing_status, MAGI / 1000, infl)
                (tax, mrate, crate, brend, sd, ibtax, cgtax) = calc_tax(
                    year, infl, income / 1000, capgains / 1000, MAGI / 1000,
                    filing_status, tb)
                tax = max(0, round(tax * 1000, 3))

                expected = dd["income_tax"][y]
                if tax == expected:
                    _write(self._out_box, f"{year}  ok")
                else:
                    _write(self._out_box,
                           f"{year}  MISMATCH  "
                           f"ti={income:.1f}  cg={capgains:.1f}  "
                           f"computed={tax:.3f}  expected={expected:.3f}  "
                           f"fs={filing_status}")

        except Exception as exc:
            _write(self._err_box, f"ERROR during test: {exc}")


# ############## Entry Point ##############

if __name__ == "__main__":
    app = TaxCalcApp()
    app.mainloop()
