# Rate Lab

**What are the 20 companies from my Sector Teardown worth at a different interest rate?**

A live, interactive companion to my [20-company Sector Teardown](https://architchawla26.github.io/Sector-Teardown-20/):
two sliders — the US 10Y risk-free rate (3.0%–7.0%) and terminal growth (2.0%–4.0%) — reprice all 20 DCF models
in the browser, with fair values, implied upsides and BUY / HOLD / PASS calls recomputing in real time.

**Live site:** https://architchawla26.github.io/Rate-Lab/
**Author:** Archit Chawla · Models as of October 19, 2026

## What it demonstrates

- **Valuation mechanics, not just valuation output** — the discount rate is rebuilt company by company from CAPM
  (beta × 4.5% ERP over the scenario risk-free rate), each model's own capital-structure weights and after-tax cost
  of debt, so rate sensitivity differs by name for identifiable reasons (duration, beta, leverage).
- **Model reverse-engineering with a verification gate** — inputs were extracted from the 20 published models and
  only accepted if they reproduced each published base-case value within 1% (see below).
- **Two DCF architectures handled correctly** — enterprise FCFF models with a net-debt bridge, and distribution
  (dividend + buyback) models discounted at cost of equity for JPM, GS, MS and BLK, where leverage is the product
  and an enterprise bridge would be wrong.
- **A living artefact** — a weekly GitHub Actions job pulls fresh closing prices from the Sector Teardown feed,
  updates the data file, and redeploys the site in the same run. Vanilla HTML/CSS/JS; no frameworks, no CDN.

## The method

Cash flows are the published models' own base-case projections (2026–2030) and never change. Only the discount
rate and terminal growth move:

- Enterprise DCF: WACC(Rf) = wE × (Rf + beta × ERP) + wD × after-tax cost of debt; value =
  [PV of FCF + CF5 × (1 + g) / (WACC − g) discounted 5 years − net debt] / shares.
- Distribution DCF: discount at cost of equity k(Rf) = Rf + beta × ERP; no debt bridge.
- Calls: BUY ≥ +20% implied upside, HOLD −10% to +20%, PASS below −10% — the teardown's bands.

Finding at publication: at the published 5.1% rate the lab reproduces the teardown exactly (1 BUY, 2 HOLD,
17 PASS; median implied upside −46.5%). Cutting the 10Y to 4.0% lifts the median only to −40.1% — rate relief
alone does not close a gap that mostly sits in cash-flow expectations.

## Verification

Every company's extraction had to re-derive its published `dcf_base` at Rf = 5.1%, g = 3.0% within 1% to use the
exact repricing method; failures would fall back to interpolation across the published bear/base/bull values and
be flagged in the data. **Result: 20 of 20 exact, worst deviation 0.015% (PLTR).** A second check recalculated
all 20 workbooks in LibreOffice and tied out every per-share value independently. Full table: [VERIFICATION.md](VERIFICATION.md).

## Rerun the extraction

```bash
python3 extract_data.py    # rebuilds site/data/lab.json and verification.json
python3 refresh_prices.py  # updates prices in lab.json from the Sector Teardown feed
```

Requires Python 3 + openpyxl, and LibreOffice for the workbook check. Source models live in the
[Sector-Teardown-20](https://github.com/ArchitChawla26/Sector-Teardown-20) repository and are read, never modified.

## Limitations

- Only the discount rate and terminal growth move; real rate shifts would also change the forecasts themselves.
- After-tax cost of debt, betas, capital-structure weights and share counts are held at the October 19, 2026
  model-date figures.
- Prices refresh weekly; fair values stay anchored to the published Sector Teardown models.

*Independent project for skill demonstration; not investment advice.*
