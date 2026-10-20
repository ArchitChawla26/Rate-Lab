#!/usr/bin/env python3
"""Rate Lab — data extraction and verification.

Pulls the valuation inputs out of the 20 published Sector Teardown models
(~/workspace/sector-teardown-20/companies/<TICKER>/, read-only) so the Rate Lab
site can reprice every company as a function of the US 10Y risk-free rate and
terminal growth, live in the browser.

Method
------
Each company's own build_model.py contains a Python mirror of its workbook.
I execute a *copy* of that script in a temp directory (nothing in the source
tree is written to) and call its dcf("base") to recover the projected cash-flow
stream (years 1-5), beta, shares, net debt and the discount-rate build. Fair
value as a function of the risk-free rate Rf and terminal growth g:

  enterprise DCF:   WACC(Rf) = wE x (Rf + beta x ERP) + wD x cod_pre x (1-tax)
                    value = [PV of FCF at WACC + TV - net debt] / shares
  distribution DCF: k(Rf)    = Rf + beta x ERP            (cost of equity)
                    value = [PV of distributable CF at k + TV] / shares
  TV = CF5 x (1 + g) / (r - g), discounted 5 years. ERP fixed at 4.5%;
  the after-tax cost of debt is held at the model's own figure.

Verification gate
-----------------
At the published settings (Rf = 5.1%, g = 3.0%) the recomputed value must match
summary.json's dcf_base within 1%. A company that fails falls back to
piecewise-linear interpolation across its published bear/base/bull values
(anchored at Rf = 6.1% / 5.1% / 4.1%, the cases' embedded -/+100 bps discount
adjustments) and is flagged method="interpolated". A second, independent check
recalculates each workbook in LibreOffice and compares the DCF_Base per-share
cell with the published dcf_base.

Outputs: site/data/lab.json (site data) and verification.json (gate results,
consumed by VERIFICATION.md).

Rerun:  python3 extract_data.py        (from ~/workspace/rate-lab/)
Requires: python3 stdlib + openpyxl; LibreOffice (soffice) for check 2.
Author: Archit Chawla.
"""

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
TEARDOWN = Path.home() / "workspace" / "sector-teardown-20"
HOOD_BUILD = Path.home() / "workspace" / "equity-teardown-hood" / "build_model.py"
PRICES_URL = "https://architchawla26.github.io/Sector-Teardown-20/data/companies.json"

RF_BASE, ERP, G_BASE = 0.051, 0.045, 0.030
GATE_PCT = 1.0

TICKERS = ["HOOD", "COIN", "SOFI", "SCHW",
           "NVDA", "AVGO", "AMD", "ALAB",
           "CRM", "NOW", "SNOW", "PLTR",
           "AAPL", "AMZN", "META", "GOOGL",
           "JPM", "GS", "MS", "BLK"]


# ---------------------------------------------------------------- primitives
def fair_value(rec, rf, g):
    """Per-share fair value of one extracted record at risk-free rate rf."""
    cf = rec["cash_flows"]
    if rec["model_type"] == "enterprise":
        coe = rf + rec["beta"] * ERP
        r = rec["w_equity"] * coe + rec["w_debt"] * rec["after_tax_cost_of_debt"]
    else:  # distribution: discount at cost of equity
        r = rf + rec["beta"] * ERP
    pv = sum(c / (1 + r) ** (t + 1) for t, c in enumerate(cf))
    tv = cf[-1] * (1 + g) / (r - g)
    eq = pv + tv / (1 + r) ** 5 - (rec["net_debt"] or 0.0)
    return eq / rec["shares"]


def interpolated_value(rec, rf, g):
    """Fallback: piecewise-linear across published bear/base/bull, anchored at
    Rf = 6.1% / 5.1% / 4.1% (the cases embed -/+100 bps on the discount rate),
    with the terminal-growth move applied through the Gordon factor using the
    cost of equity as the discount-rate proxy."""
    pub = rec["published"]
    anchors = [(0.041, pub["bull"]), (0.051, pub["base"]), (0.061, pub["bear"])]
    if rf <= anchors[0][0]:
        (x0, y0), (x1, y1) = anchors[0], anchors[1]
    elif rf >= anchors[-1][0]:
        (x0, y0), (x1, y1) = anchors[-2], anchors[-1]
    else:
        for i in range(2):
            if anchors[i][0] <= rf <= anchors[i + 1][0]:
                (x0, y0), (x1, y1) = anchors[i], anchors[i + 1]
                break
    v = y0 + (y1 - y0) * (rf - x0) / (x1 - x0)
    k = RF_BASE + rec["beta"] * ERP
    v *= ((1 + g) / (k - g)) / ((1 + G_BASE) / (k - G_BASE))
    return v


# ---------------------------------------------------------------- extraction
def load_module(script: Path, tag: str, workdir: Path):
    """Execute a copy of a company's build_model.py in workdir and return the
    module namespace. All of the script's own writes (workbook, summary.json)
    land in workdir, never in the source tree."""
    local = workdir / f"build_{tag}.py"
    shutil.copy(script, local)
    shared = TEARDOWN / "model_lib.py"  # some scripts import the shared builder
    if shared.exists() and not (workdir / "model_lib.py").exists():
        shutil.copy(shared, workdir / "model_lib.py")
    spec = importlib.util.spec_from_file_location(f"build_{tag}", local)
    mod = importlib.util.module_from_spec(spec)
    import os
    cwd = os.getcwd()
    os.chdir(workdir)
    sys.path.insert(0, str(workdir))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
        sys.path.remove(str(workdir))
        sys.modules.pop(f"build_{tag}", None)
    return mod


def extract(ticker: str, workdir: Path) -> dict:
    folder = TEARDOWN / "companies" / ticker
    summary = json.loads((folder / "summary.json").read_text())
    script = HOOD_BUILD if ticker == "HOOD" else folder / "build_model.py"
    mod = load_module(script, ticker, workdir)
    cfg = getattr(mod, "CONFIG", None) or getattr(mod, "C", None)
    if hasattr(mod, "dcf"):
        res = mod.dcf("base")
    else:  # AI Infra & Semis names delegate to the shared model_lib mirror
        spec = importlib.util.spec_from_file_location("model_lib",
                                                       workdir / "model_lib.py")
        ml = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(ml)
        res = ml.dcf(cfg, "base")

    def pick(name_cfg, name_glob, default=None):
        if cfg is not None and name_cfg in cfg:
            return cfg[name_cfg]
        return getattr(mod, name_glob, default)

    beta = float(pick("beta", "BETA"))
    shares = float(pick("shares", "SHARES"))
    erp = float(pick("erp", "ERP", ERP))
    assert abs(erp - ERP) < 1e-9, f"{ticker}: ERP {erp} != framework {ERP}"

    if "fcf" in res:
        model_type = "enterprise"
        cash_flows = [float(x) for x in res["fcf"]]
        net_debt = float(pick("net_debt", "NET_DEBT"))
        cod_pre = float(pick("cod_pre", "COD_PRE"))
        tax = float(pick("tax", "TAX"))
        mcap = float(pick("mcap", "MCAP"))
        debt_book = float(pick("debt_book", "DEBT_BOOK"))
        w_e = mcap / (mcap + debt_book)
        w_d = debt_book / (mcap + debt_book)
        atcod = cod_pre * (1 - tax)
        discount_base = float(res["wacc"])
    else:
        model_type = "distribution"
        cash_flows = [float(x) for x in res["dist"]]
        net_debt = None
        cod_pre = tax = mcap = debt_book = None
        w_e, w_d, atcod = 1.0, 0.0, 0.0
        discount_base = float(res["coe"])

    rec = {
        "ticker": ticker,
        "name": summary["name"],
        "sector": summary["sector"],
        "model_type": model_type,
        "beta": beta,
        "shares": shares,
        "net_debt": net_debt,
        "pre_tax_cost_of_debt": cod_pre,
        "tax_rate": tax,
        "after_tax_cost_of_debt": atcod,
        "w_equity": w_e,
        "w_debt": w_d,
        "discount_rate_base": discount_base,
        "cash_flows": [round(c, 1) for c in cash_flows],
        "published": {"bear": summary["dcf_bear"], "base": summary["dcf_base"],
                      "bull": summary["dcf_bull"]},
        "mirror_base": float(res["ps"]),
    }
    recomputed = fair_value(rec, RF_BASE, G_BASE)
    diff_pct = (recomputed - summary["dcf_base"]) / summary["dcf_base"] * 100
    rec["recomputed_base"] = recomputed
    rec["gate_diff_pct"] = diff_pct
    rec["method"] = "exact" if abs(diff_pct) <= GATE_PCT else "interpolated"
    return rec


# ------------------------------------------------------- LibreOffice check
def libreoffice_check() -> dict:
    """Recalculate every workbook headlessly and read the DCF_Base per-share
    value — an independent check that the workbook itself reproduces the
    published dcf_base."""
    tmp = Path(tempfile.mkdtemp(prefix="ratelab-lo-"))
    src, out = tmp / "src", tmp / "out"
    src.mkdir(); out.mkdir()
    for t in TICKERS:
        shutil.copy(TEARDOWN / "companies" / t / f"{t}_valuation_model.xlsx",
                    src / f"{t}.xlsx")
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx",
                    "--outdir", str(out)] + [str(p) for p in sorted(src.glob("*.xlsx"))],
                   check=True, capture_output=True, timeout=900)
    import openpyxl
    results = {}
    for t in TICKERS:
        wb = openpyxl.load_workbook(out / f"{t}.xlsx", data_only=True)
        ws = wb["DCF_Base"]
        val = None
        for row in ws.iter_rows(min_col=1, max_col=2):
            label = row[0].value
            if isinstance(label, str) and label.strip().lower().startswith("implied value per share"):
                val = row[1].value
                break
        results[t] = float(val) if val is not None else None
    shutil.rmtree(tmp, ignore_errors=True)
    return results


# --------------------------------------------------------------------- main
def main():
    with urllib.request.urlopen(PRICES_URL, timeout=60) as fh:
        feed = json.load(fh)
    prices = {c["ticker"]: c for c in feed["companies"]}
    price_asof = feed["meta"]["price_asof"]

    workdir = Path(tempfile.mkdtemp(prefix="ratelab-extract-"))
    records, verification = [], []
    for t in TICKERS:
        rec = extract(t, workdir)
        rec["price"] = prices[t]["price"]
        rec["price_asof"] = prices[t]["price_asof"]
        records.append(rec)
        verification.append({
            "ticker": t, "model_type": rec["model_type"], "method": rec["method"],
            "published_base": rec["published"]["base"],
            "mirror_base": round(rec["mirror_base"], 2),
            "recomputed_base": round(rec["recomputed_base"], 2),
            "gate_diff_pct": round(rec["gate_diff_pct"], 3),
        })
        print(f"{t:5s} {rec['model_type']:12s} method={rec['method']:12s} "
              f"published={rec['published']['base']:9.2f} recomputed={rec['recomputed_base']:9.2f} "
              f"diff={rec['gate_diff_pct']:+.3f}%")
    shutil.rmtree(workdir, ignore_errors=True)

    print("\nLibreOffice workbook recalculation check...")
    lo = libreoffice_check()
    for row in verification:
        t = row["ticker"]
        v = lo.get(t)
        row["workbook_base"] = round(v, 2) if v is not None else None
        row["workbook_diff_pct"] = (round((v - row["published_base"]) / row["published_base"] * 100, 3)
                                    if v is not None else None)
        print(f"{t:5s} workbook={row['workbook_base']} diff={row['workbook_diff_pct']}")

    lab = {
        "meta": {
            "project": "Rate Lab",
            "author": "Archit Chawla",
            "model_asof": "2026-10-19",
            "price_asof": price_asof,
            "base_risk_free": RF_BASE,
            "erp": ERP,
            "base_terminal_growth": G_BASE,
            "bands": {"buy_min_upside_pct": 20, "hold_min_upside_pct": -10},
            "source": "Sector Teardown 20-company DCF models (Archit Chawla)",
            "disclaimer": "Independent project for skill demonstration; not investment advice.",
        },
        "companies": [{
            "ticker": r["ticker"], "name": r["name"], "sector": r["sector"],
            "price": r["price"], "price_asof": r["price_asof"],
            "model_type": r["model_type"], "method": r["method"],
            "beta": r["beta"], "shares": r["shares"], "net_debt": r["net_debt"],
            "after_tax_cost_of_debt": round(r["after_tax_cost_of_debt"], 6),
            "w_equity": round(r["w_equity"], 6), "w_debt": round(r["w_debt"], 6),
            "cash_flows": r["cash_flows"],
            "published": r["published"],
        } for r in records],
    }
    out_json = BASE / "site" / "data" / "lab.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(lab, indent=1))
    (BASE / "verification.json").write_text(json.dumps(verification, indent=1))

    exact = sum(1 for v in verification if v["method"] == "exact")
    worst = max(verification, key=lambda v: abs(v["gate_diff_pct"]))
    print(f"\nGate: {exact}/20 exact, {20 - exact} interpolated. "
          f"Worst diff: {worst['ticker']} {worst['gate_diff_pct']:+.3f}%")
    print(f"Wrote {out_json} and verification.json")


if __name__ == "__main__":
    sys.exit(main())
