/* Rate Lab — reprices the 20 Sector Teardown DCFs live as the risk-free rate
   and terminal growth move. Vanilla JS, no dependencies.
   Method per company (extract_data.py verification gate):
     exact        — closed-form repricing of the model's own cash flows
     interpolated — piecewise-linear across published bear/base/bull anchors  */
"use strict";

const ERP = 0.045;
const BASE_RF = 0.051;
const BASE_G = 0.030;
const BUY_MIN = 20, HOLD_MIN = -10;

let DATA = null;
let sortKey = "upside";
let sortDir = -1; // descending

const $ = (id) => document.getElementById(id);
const fmtPct = (x, dp = 1) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(dp) + "%";
const fmtRate = (x) => (x * 100).toFixed(2) + "%";
const fmtPx = (x) => x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function discountRate(c, rf) {
  const coe = rf + c.beta * ERP;
  return c.model_type === "enterprise"
    ? c.w_equity * coe + c.w_debt * c.after_tax_cost_of_debt
    : coe;
}

function fairValueExact(c, rf, g) {
  const r = discountRate(c, rf);
  let pv = 0;
  c.cash_flows.forEach((cf, t) => { pv += cf / Math.pow(1 + r, t + 1); });
  const tv = c.cash_flows[4] * (1 + g) / (r - g);
  const eq = pv + tv / Math.pow(1 + r, 5) - (c.net_debt || 0);
  return eq / c.shares;
}

function fairValueInterpolated(c, rf, g) {
  const anchors = [[0.041, c.published.bull], [BASE_RF, c.published.base], [0.061, c.published.bear]];
  let [x0, y0, x1, y1] = rf <= anchors[0][0]
    ? [...anchors[0], ...anchors[1]]
    : rf >= anchors[2][0] ? [...anchors[1], ...anchors[2]] : null;
  if (x0 === undefined) {
    for (let i = 0; i < 2; i++) {
      if (rf >= anchors[i][0] && rf <= anchors[i + 1][0]) {
        [x0, y0, x1, y1] = [...anchors[i], ...anchors[i + 1]];
        break;
      }
    }
  }
  let v = y0 + (y1 - y0) * (rf - x0) / (x1 - x0);
  const k = BASE_RF + c.beta * ERP; // cost-of-equity proxy for the Gordon factor
  v *= ((1 + g) / (k - g)) / ((1 + BASE_G) / (k - BASE_G));
  return v;
}

const fairValue = (c, rf, g) =>
  c.method === "interpolated" ? fairValueInterpolated(c, rf, g) : fairValueExact(c, rf, g);

const callOf = (u) => (u >= BUY_MIN ? "BUY" : u >= HOLD_MIN ? "HOLD" : "PASS");

function median(xs) {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[s.length >> 1] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
}

function render() {
  const rf = parseFloat($("rf").value) / 100;
  const g = parseFloat($("tg").value) / 100;
  $("rf-out").textContent = fmtRate(rf);
  $("tg-out").textContent = fmtRate(g);

  const rows = DATA.companies.map((c) => {
    const v = fairValue(c, rf, g);
    const upside = (v / c.price - 1) * 100;
    return { c, v, upside, call: callOf(upside), rate: discountRate(c, rf) };
  });

  const counts = { BUY: 0, HOLD: 0, PASS: 0 };
  rows.forEach((r) => counts[r.call]++);
  const med = median(rows.map((r) => r.upside));

  $("st-rf").textContent = fmtRate(rf);
  const medEl = $("st-median");
  medEl.textContent = fmtPct(med);
  medEl.className = "v " + (med >= 0 ? "pos" : "neg");
  $("st-buy").textContent = counts.BUY;
  $("st-hold").textContent = counts.HOLD;
  $("st-pass").textContent = counts.PASS;
  $("scenario-line").innerHTML =
    `At a <strong>${fmtRate(rf)}</strong> 10Y and <strong>${fmtRate(g)}</strong> terminal growth: ` +
    `<strong>${counts.BUY} BUY · ${counts.HOLD} HOLD · ${counts.PASS} PASS</strong> — ` +
    `the median name carries <strong>${fmtPct(med)}</strong> implied upside.`;

  const keyFns = {
    ticker: (r) => r.c.ticker, sector: (r) => r.c.sector,
    price: (r) => r.c.price, rate: (r) => r.rate, value: (r) => r.v,
    upside: (r) => r.upside, call: (r) => r.call, published: (r) => r.c.published.base,
  };
  rows.sort((a, b) => {
    const ka = keyFns[sortKey](a), kb = keyFns[sortKey](b);
    const cmp = typeof ka === "string" ? ka.localeCompare(kb) : ka - kb;
    return cmp * sortDir;
  });
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    const on = th.dataset.sort === sortKey;
    th.classList.toggle("sorted", on);
    th.classList.toggle("asc", on && sortDir === 1);
  });

  $("rows").innerHTML = rows.map((r) => `
    <tr>
      <td><span class="ticker">${r.c.ticker}</span>
          ${r.c.method === "interpolated" ? '<span class="method-tag">interp.</span>' : ""}
          <div class="cname">${r.c.name}</div></td>
      <td>${r.c.sector}</td>
      <td class="num price">$${fmtPx(r.c.price)}</td>
      <td class="num">${fmtRate(r.rate)}</td>
      <td class="num dcf">$${fmtPx(r.v)}</td>
      <td class="num"><span class="upside-chip ${r.upside >= BUY_MIN ? "pos" : r.upside >= HOLD_MIN ? "mid" : "neg"}">${fmtPct(r.upside)}</span></td>
      <td><span class="badge ${r.call.toLowerCase()}">${r.call}</span></td>
      <td class="num pub">$${fmtPx(r.c.published.base)}</td>
    </tr>`).join("");
}

document.querySelectorAll("th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const k = th.dataset.sort;
    if (k === sortKey) sortDir *= -1;
    else { sortKey = k; sortDir = (k === "ticker" || k === "sector" || k === "call") ? 1 : -1; }
    render();
  });
});
$("rf").addEventListener("input", render);
$("tg").addEventListener("input", render);
$("reset").addEventListener("click", () => {
  $("rf").value = "5.10";
  $("tg").value = "3.00";
  render();
});

fetch("data/lab.json")
  .then((r) => r.json())
  .then((d) => {
    DATA = d;
    $("price-asof").textContent = d.meta.price_asof;
    $("price-asof-f").textContent = d.meta.price_asof;
    render();
  })
  .catch(() => {
    $("scenario-line").textContent = "Data file failed to load — please refresh.";
  });
