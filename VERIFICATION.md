# Verification — Rate Lab data extraction

**Author:** Archit Chawla · **Extraction run:** October 20, 2026 · **Models as of:** October 19, 2026

Rate Lab reprices my 20 Sector Teardown DCF models in the browser. Before any
company was allowed to reprice, its extracted inputs had to pass a gate; this
file is the record of that test.

## The gate

For each company I extracted, from its own published build script (executed as
a copy in a temp directory — the source models were never written to):

- the base-case projected cash-flow stream, years 1–5 (free cash flow for the
  16 enterprise DCFs; distributable cash flow — dividends plus buybacks — for
  the 4 distribution DCFs: JPM, GS, MS, BLK),
- beta, shares outstanding, net debt (enterprise models), and the discount-rate
  build (cost of equity via CAPM, after-tax cost of debt, capital-structure
  weights).

Repricing is closed-form. Enterprise models discount at
WACC(Rf) = wE × (Rf + beta × 4.5%) + wD × after-tax cost of debt; distribution
models discount at the cost of equity, Rf + beta × 4.5%. The terminal value is
CF5 × (1 + g) / (r − g), discounted five years.

**Gate rule:** at the published settings (Rf = 5.1%, g = 3.0%), the recomputed
per-share value must match the published `dcf_base` in the company's
`summary.json` within 1%. A company failing the gate would be repriced by
piecewise-linear interpolation across its published bear/base/bull values
(anchored at Rf 6.1% / 5.1% / 4.1%, reflecting the cases' ∓100 bps discount
adjustments, with the terminal-growth move applied through the Gordon factor)
and flagged `method = "interpolated"` in `site/data/lab.json` and on the site.

**Result: 20 of 20 companies passed. Zero use the interpolated fallback.**
The worst deviation is PLTR at −0.015% — rounding in the published two-decimal
values, nothing more.

## Second check: the workbooks themselves

Independently of the extraction, all 20 published workbooks were recalculated
headlessly in LibreOffice and the DCF_Base "Implied value per share" cell was
tied back to the published `dcf_base`. All 20 agree to within 0.015%.

## Per-company results

| Ticker | Model type | Published base ($) | Recomputed ($) | Gate diff | Method | Workbook recalc ($) | Workbook diff |
|---|---|---:|---:|---:|---|---:|---:|
| HOOD | enterprise | 29.15 | 29.15 | +0.004% | exact | 29.15 | +0.003% |
| COIN | enterprise | 93.99 | 93.99 | -0.003% | exact | 93.99 | -0.003% |
| SOFI | enterprise | 11.62 | 11.62 | -0.006% | exact | 11.62 | -0.005% |
| SCHW | enterprise | 161.09 | 161.09 | +0.000% | exact | 161.09 | +0.000% |
| NVDA | enterprise | 103.36 | 103.36 | -0.002% | exact | 103.36 | -0.002% |
| AVGO | enterprise | 198.72 | 198.72 | -0.002% | exact | 198.72 | -0.002% |
| AMD | enterprise | 101.50 | 101.50 | -0.003% | exact | 101.50 | -0.003% |
| ALAB | enterprise | 35.27 | 35.27 | +0.013% | exact | 35.27 | +0.011% |
| CRM | enterprise | 223.72 | 223.72 | +0.001% | exact | 223.72 | +0.002% |
| NOW | enterprise | 101.98 | 101.98 | +0.001% | exact | 101.98 | +0.001% |
| SNOW | enterprise | 137.47 | 137.47 | -0.001% | exact | 137.47 | -0.002% |
| PLTR | enterprise | 31.79 | 31.79 | -0.015% | exact | 31.79 | -0.015% |
| AAPL | enterprise | 146.75 | 146.75 | -0.000% | exact | 146.75 | -0.001% |
| AMZN | enterprise | 79.68 | 79.68 | -0.006% | exact | 79.68 | -0.006% |
| META | enterprise | 409.83 | 409.83 | +0.001% | exact | 409.83 | +0.001% |
| GOOGL | enterprise | 164.95 | 164.95 | +0.002% | exact | 164.95 | +0.002% |
| JPM | distribution | 313.42 | 313.42 | +0.001% | exact | 313.42 | +0.001% |
| GS | distribution | 775.17 | 775.17 | +0.000% | exact | 775.17 | +0.000% |
| MS | distribution | 136.93 | 136.93 | -0.002% | exact | 136.93 | -0.002% |
| BLK | distribution | 575.01 | 575.01 | -0.000% | exact | 575.01 | -0.001% |

## Reproduce it

```bash
python3 extract_data.py   # rewrites site/data/lab.json + verification.json
```

Requires Python 3 with openpyxl, and LibreOffice (`soffice`) for the workbook
recalculation check. Prices embedded in `lab.json` come from the Sector
Teardown feed at extraction time; `refresh_prices.py` keeps them current
weekly thereafter.
