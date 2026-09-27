# renderer.py — output generation for PyWebView (R3 plan)
# Replaces display_dd with render_dd returning typed items; adds render_three_peat.

import json
import pandas as pd
import plotly.express as px
from planner import get_nut

pd.options.display.max_columns = None
pd.options.display.precision = 3


def render_diagnosis(diag):
    """Render an infeasibility diagnosis from solver.diagnose_infeasible().

    Called instead of render_dd on infeasible runs: dd has been fudged to zeros by
    then, so render_dd would draw fifteen charts of nothing around the answer.

    Returns the same item types render_dd uses, plus {'type': 'note', 'text': ...}.
    """
    items = [{'type': 'heading', 'text': 'Infeasible — nothing satisfies this plan'}]
    if not diag:
        items.append({'type': 'note', 'text': 'No diagnosis was produced.'})
        return items
    items.append({'type': 'note', 'text': diag.get('headline', '')})
    rows = diag.get('rows') or []
    if rows:
        cols = ['lever', 'year', 'shortfall_real', 'shortfall_nominal',
                'current', 'suggested']
        df = pd.DataFrame(rows)
        df = df[[c for c in cols if c in df.columns]]
        df = df.rename(columns={
            'lever': 'Lever', 'year': 'Year',
            'shortfall_real': 'Short by ($k, base-year)',
            'shortfall_nominal': 'Short by ($k, nominal)',
            'current': 'Current', 'suggested': 'Suggested',
        })
        items.append({'type': 'table',
                      'html': df.to_html(classes='orp-table', border=0, index=False)})
    if diag.get('approximate'):
        items.append({'type': 'note',
                      'text': 'A probe hit its time limit, so these figures are approximate.'})
    for n in diag.get('notes') or []:
        items.append({'type': 'note', 'text': n})
    return items


def render_dd(dd, fname=None):
    """
    Returns a list of output items for the frontend:
      {'type': 'plotly',  'json': <dict>}  # figure as dict (json.loads(fig.to_json()))
      {'type': 'table',   'html': <str>}
      {'type': 'heading', 'text': <str>}
    """
    items = []
    dfr = pd.DataFrame(dd, index=dd['year'])
    if fname:
        dfr.to_csv(fname)
    df = pd.DataFrame(dfr[1:])

    def add_plotly(fig):
        items.append({'type': 'plotly', 'json': json.loads(fig.to_json())})

    def add_heading(text):
        t = text.strip()
        if t.startswith('### '):
            t = t[4:]
        items.append({'type': 'heading', 'text': t})

    def add_table(ndf, columns=None):
        if columns is not None:
            ndf = ndf[columns]
        items.append({'type': 'table', 'html': ndf.to_html(classes='orp-table', border=0)})

    # Nominal Balances (chart)
    add_plotly(px.bar(df, barmode='relative', x='year',
                y=['afterTax', 'e_Taxd', 'j_Taxd', 'e_Roth', 'j_Roth'],
                color_discrete_map={'afterTax': 'royalblue', 'e_Taxd': 'mediumorchid', 'j_Taxd': 'mediumpurple',
                                    'e_Roth': 'forestgreen', 'j_Roth': 'lawngreen'},
                title='Nominal Balances'))

    df['to_aTax'] = -df['to_aTax']
    df['net_aTax'] = df[['from_aTax', 'to_aTax']].sum(axis=1)
    add_plotly(px.bar(df, barmode='relative', x='year',
                y=['SSA_income', 'pension_income', 'e_RMD', 'j_RMD',
                   'from_eTaxd', 'from_jTaxd', 'net_aTax', 'from_eRoth', 'from_jRoth'],
                color_discrete_map={'SSA_income': 'goldenrod', 'pension_income': 'darkgoldenrod',
                                    'e_RMD': 'firebrick', 'j_RMD': 'chocolate', 'to_eTaxd': 'mediumorchid',
                                    'from_jTaxd': 'mediumpurple', 'net_aTax': 'royalblue', 'from_eTaxd': 'mediumorchid',
                                    'from_eRoth': 'forestgreen', 'from_jRoth': 'lawngreen'},
                title='Nominal Withdrawals'))

    df['from_Roth'] = df[['from_eRoth', 'from_jRoth']].sum(axis=1)
    df['from_Taxd'] = df[['e_RMD', 'j_RMD', 'from_eTaxd', 'from_jTaxd']].sum(axis=1)
    df['guaranteed'] = df[['SSA_income', 'pension_income']].sum(axis=1)
    add_plotly(px.bar(df, barmode='relative', x='year',
                y=['guaranteed', 'net_aTax', 'from_Roth', 'from_Taxd'],
                color_discrete_map={'guaranteed': 'goldenrod', 'net_aTax': 'royalblue',
                                    'from_Roth': 'forestgreen', 'from_Taxd': 'mediumorchid'},
                title='Nominal Withdrawals'))

    df['income_tax'] = -df['income_tax']
    df['Roth_conv'] = df[['e_RothConv', 'j_RothConv']].sum(axis=1)
    df['wthd_Taxd'] = df[['from_eTaxd', 'from_jTaxd']].sum(axis=1)
    df['total_RMD'] = df[['e_RMD', 'j_RMD']].sum(axis=1)
    add_plotly(px.bar(df, barmode='relative', x='year',
                y=['income_tax', 'Roth_conv', 'wthd_Taxd', 'total_RMD', 'SSA_income', 'pension_income', 'dividends'],
                color_discrete_map={'income_tax': 'firebrick', 'Roth_conv': 'forestgreen',
                                    'wthd_Taxd': 'mediumorchid', 'total_RMD': 'chocolate',
                                    'SSA_income': 'goldenrod', 'pension_income': 'darkgoldenrod',
                                    'dividends': 'royalblue'},
                title='Tax Data'))

    add_heading('\n### Nominal Balances')
    add_table(df, ['e', 'j', 'afterTax', 'aTax_basis', 'e_Roth', 'j_Roth', 'e_Taxd', 'j_Taxd', 'net_pretax', 'net_postax'])

    add_heading('\n### Nominal Withdrawals')
    add_table(df, ['e', 'j', 'e_RMD', 'j_RMD', 'from_eTaxd', 'from_jTaxd', 'from_aTax', 'to_aTax', 'from_eRoth', 'from_jRoth'])

    df['IRMAA'] = -df['IRMAA']
    df['fixed_income'] = df[['total_RMD', 'SSA_income', 'pension_income', 'taxfree_income', 'misc_income', 'dividends']].sum(axis=1)
    df['withdrawals'] = df[['wthd_Taxd', 'from_Roth', 'Roth_conv', 'from_aTax']].sum(axis=1)
    df['nRoth_conv'] = -df['Roth_conv']
    df['transfers'] = df[['nRoth_conv', 'to_aTax']].sum(axis=1)

    add_heading('\n### Nominal Fixed Income')
    add_table(df, ['e', 'j', 'total_RMD', 'SSA_income', 'pension_income', 'misc_income', 'dividends'])

    df['DI'] = df['disp_income']
    add_heading('\n### Nominal Spending')
    add_table(df, ['e', 'j', 'fixed_income', 'withdrawals', 'transfers', 'IRMAA-bins', 'IRMAA', 'income_tax', 'DI'])

    add_heading('\n### Tax Info')
    df['caplosss'] = -df['caplosss']
    add_table(df, ['Roth_conv', 'wthd_Taxd', 'fixed_income', 'capgains', 'caplosss', 'QCD',
                   'taxable_income', 'income_tax', 'tax_bracket', 'cgains_rate', 'MAGI'])

    add_heading('\n### After Tax Account Details')
    df['fm_aTax__cash'] = -df['fm_aTax__cash']
    df['fm_aTax_bonds'] = -df['fm_aTax_bonds']
    df['fm_aTax_basis'] = -df['fm_aTax_basis']
    df['fm_aTax_unrlz'] = -df['fm_aTax_unrlz']
    df['net_aTax__cash'] = df[['fm_aTax__cash', 'to_aTax__cash']].sum(axis=1)
    df['net_aTax_bonds'] = df[['fm_aTax_bonds', 'to_aTax_bonds']].sum(axis=1)
    df['net_aTax_basis'] = df[['fm_aTax_basis', 'to_aTax_basis']].sum(axis=1)
    df['net_aTax_unrlz'] = df[['fm_aTax_unrlz', 'to_aTax_unrlz']].sum(axis=1)
    add_table(df, ['net_aTax__cash', 'net_aTax_bonds', 'net_aTax_basis', 'net_aTax_unrlz',
                   'aTax__cash', 'aTax_bonds', 'aTax_basis', 'aTax_unrlz'])

    df['real spend δ'] = df.apply(lambda x: (x.spend_δ / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])) - 1.0), axis=1)
    df['nominal spend δ'] = df['spend_δ'] - 1.0
    add_plotly(px.line(df, x='year', y='nominal spend δ', title='nominal spend curve'))

    df['real DI'] = df.apply(lambda x: x.disp_income / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    add_plotly(px.line(df, x='year', y=['real DI', 'DI'], title='real and nominal spending'))

    # Real value reports
    df['afterTax'] = df.apply(lambda x: x.afterTax / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['e_Taxd'] = df.apply(lambda x: x.e_Taxd / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['j_Taxd'] = df.apply(lambda x: x.j_Taxd / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['e_Roth'] = df.apply(lambda x: x.e_Roth / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['j_Roth'] = df.apply(lambda x: x.j_Roth / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    add_plotly(px.bar(df, barmode='relative', x='year',
                y=['afterTax', 'e_Taxd', 'j_Taxd', 'e_Roth', 'j_Roth'],
                color_discrete_map={'afterTax': 'royalblue', 'e_Taxd': 'mediumorchid', 'j_Taxd': 'mediumpurple',
                                    'e_Roth': 'forestgreen', 'j_Roth': 'lawngreen'},
                title='Real Balances (Base Year $000s)'))

    df['guaranteed'] = df.apply(lambda x: x.guaranteed / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['net_aTax'] = df.apply(lambda x: x.net_aTax / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['from_Roth'] = df.apply(lambda x: x.from_Roth / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['from_Taxd'] = df.apply(lambda x: x.from_Taxd / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    add_plotly(px.bar(df, barmode='relative', x='year',
                y=['guaranteed', 'net_aTax', 'from_Roth', 'from_Taxd'],
                color_discrete_map={'guaranteed': 'goldenrod', 'net_aTax': 'royalblue',
                                    'from_Roth': 'forestgreen', 'from_Taxd': 'mediumorchid'},
                title='Real Withdrawals (Base Year $000s)'))

    df['aTax_basis'] = df.apply(lambda x: x.aTax_basis / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['net_pretax'] = df.apply(lambda x: x.net_pretax / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['net_postax'] = df.apply(lambda x: x.net_postax / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    add_heading('\n### Real Balances (Base Year $000s)')
    add_table(df, ['e', 'j', 'afterTax', 'aTax_basis', 'e_Roth', 'j_Roth', 'e_Taxd', 'j_Taxd', 'net_pretax', 'net_postax'])

    df['e_RMD'] = df.apply(lambda x: x.e_RMD / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['j_RMD'] = df.apply(lambda x: x.j_RMD / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['to_aTax'] = df.apply(lambda x: x.to_aTax / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    df['from_aTax'] = df.apply(lambda x: x.from_aTax / ((1.0 + get_nut(dd, 'inflation')) ** (x.year - dd['year'][0])), axis=1)
    add_heading('\n### Real Withdrawals (Base Year $000s)')
    add_table(df, ['e', 'j', 'e_RMD', 'j_RMD', 'from_eTaxd', 'from_jTaxd', 'from_aTax', 'to_aTax', 'from_eRoth', 'from_jRoth'])

    add_plotly(px.bar(df, barmode='group', x='year',
                y=['ror_stock', 'dvd_stock', 'ror_bonds'],
                color_discrete_map={'ror_stock': 'mediumorchid', 'dvd_stock': 'goldenrod', 'ror_bonds': 'forestgreen'},
                title='Rates of Return'))

    return items


def render_three_peat(rf, sm):
    """
    Returns a list of output items for the 3-peat summary.
    rf: DataFrame (real-values result); sm: summary dict.
    """
    items = []
    items.append({'type': 'heading', 'text': '3-Peat Real Values (Base Year $000s)'})
    cols = ['year', 'e', 'j', 'hist_year', 'ror_stock', 'dvd_stock', 'ror_bonds', 'infl_rate',
            'TAB', 'x_RothConv', 'deposits', 'withdrawals', 'IRMAA', 'income_tax', 'disp_income']
    items.append({'type': 'table', 'html': rf[cols].to_html(classes='orp-table', border=0)})
    sm_df = pd.DataFrame([sm])
    items.append({'type': 'table', 'html': sm_df.to_html(classes='orp-table', border=0)})
    return items


def display_items(items):
    """Render render_dd()/render_diagnosis()/render_three_peat() items in a notebook.

    The desktop front end ships these same items over the pywebview JSON bridge and
    renders them in `app.js`. This is the Jupyter equivalent, so both front ends draw
    from one definition of what a result looks like.
    """
    import plotly.io as pio
    from IPython.display import display, HTML, Markdown

    for item in items or []:
        kind = item.get('type')
        if kind == 'plotly':
            display(pio.from_json(json.dumps(item['json'])))
        elif kind == 'table':
            display(HTML(item['html']))
        elif kind == 'heading':
            display(Markdown('### ' + (item.get('text') or '').lstrip('# ')))
        elif kind == 'note':
            display(Markdown((item.get('text') or '')))
