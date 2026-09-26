"""
Runs automatically every day via GitHub Actions.
Pulls nationwide mandi prices from data.gov.in and writes:
  - index.html   (the public dashboard, with a scrolling news-ticker bar)
  - data.json    (raw latest data, in case you want to reuse it elsewhere)

The API key is read from an environment variable (DATA_GOV_API_KEY),
set as a GitHub repo secret — never hardcoded, since this repo is public.
"""

import json
import os
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("DATA_GOV_API_KEY", "")
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"

LIMIT_PER_QUERY = 500
MAX_PAGES = 25   # ~12,500 records max per run — keeps the daily job fast & reliable

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch_page(limit, offset):
    url = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
    params = {"api-key": API_KEY, "format": "json", "limit": limit, "offset": offset}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("records", [])


def fetch_all():
    collected = []
    offset = 0
    for page_num in range(MAX_PAGES):
        page = fetch_page(LIMIT_PER_QUERY, offset)
        if not page:
            break
        collected.extend(page)
        print(f"  page {page_num + 1}: {len(page)} records (total {len(collected)})")
        if len(page) < LIMIT_PER_QUERY:
            break
        offset += LIMIT_PER_QUERY
    return collected


def load_chartjs():
    path = os.path.join(SITE_DIR, "chart.umd.js")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def generate_html(rows, chartjs_code):
    pulled_on = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data_json = json.dumps(rows, ensure_ascii=False)

    ticker_items = []
    for r in rows[:40]:
        ticker_items.append(
            f"{r.get('commodity','')} ({r.get('market','')}): ₹{r.get('modal_price','')}"
        )
    ticker_text = "   ★   ".join(ticker_items) if ticker_items else "कोई डेटा उपलब्ध नहीं"

    html = """<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>लाइव मंडी भाव डैशबोर्ड</title>
<script>__CHARTJS__</script>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, Segoe UI, Roboto, Noto Sans Devanagari, sans-serif; margin: 0; padding: 0; background: #f2f5f2; color: #1a1a1a; }
  .ticker-wrap { background: #b00020; overflow: hidden; white-space: nowrap; padding: 10px 0; border-bottom: 2px solid #ff4d4d; }
  .ticker { display: inline-block; padding-left: 100%; animation: scroll-left 140s linear infinite; font-weight: 600; font-size: 0.95rem; color: #fff; }
  .ticker-wrap:hover .ticker { animation-play-state: paused; }
  .ticker span.live-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#fff; margin-right:8px; animation: blink 1s infinite; }
  @keyframes scroll-left { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
  @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
  .content { padding: 24px; max-width: 1200px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin-bottom: 4px; color: #14532d; }
  .sub { color: #555; margin-bottom: 20px; font-size: 0.9rem; }
  .controls { margin-bottom: 20px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; background: #fff; padding: 14px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .controls label { font-size: 0.8rem; color: #444; display: flex; flex-direction: column; gap: 4px; }
  select, input { padding: 8px 12px; border-radius: 6px; border: 1px solid #ccc; font-size: 0.9rem; background: #fff; color: #1a1a1a; min-width: 160px; }
  select:focus, input:focus { outline: 2px solid #2e7d32; }
  table { border-collapse: collapse; width: 100%; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  th, td { padding: 10px 14px; text-align: left; font-size: 0.85rem; border-bottom: 1px solid #eee; color: #1a1a1a; }
  th { background: #1e8449; cursor: pointer; color: #ffffff; font-weight: 600; white-space: nowrap; }
  th:hover { background: #196f3d; }
  tbody tr:nth-child(even) { background: #f7faf7; }
  tbody tr:hover { background: #eaf5ea; }
  .commodity-cell { color: #1e8449; font-weight: 600; }
  .trend { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
  .trend.up { background: #e8f8ee; color: #1e8449; }
  .trend.down { background: #fdecec; color: #c0392b; }
  .trend.flat { background: #f0f0f0; color: #777; }
  .chart-wrap { max-width: 700px; margin: 24px 0; background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  #chartError { color: #c0392b; font-size: 0.85rem; display: none; }
  .table-wrap { overflow-x: auto; }
  .note { font-size: 0.75rem; color: #777; margin-top: 8px; }
  footer { text-align: center; color: #888; font-size: 0.75rem; padding: 20px; }
</style>
</head>
<body>

<div class="ticker-wrap">
  <div class="ticker"><span class="live-dot"></span>__TICKER_TEXT__</div>
</div>

<div class="content">
<h1>लाइव मंडी भाव डैशबोर्ड</h1>
<div class="sub">अंतिम अद्यतन: __PULLED_ON__ &middot; कुल रिकॉर्ड: __RECORD_COUNT__ &middot; स्रोत: data.gov.in</div>

<div class="controls">
  <label>राज्य
    <select id="stateFilter"><option value="">सभी राज्य</option></select>
  </label>
  <label>जिला
    <select id="districtFilter"><option value="">सभी जिले</option></select>
  </label>
  <label>बाजार (मंडी)
    <select id="marketFilter"><option value="">सभी बाजार</option></select>
  </label>
  <label>जिंस
    <select id="commodityFilter"><option value="">सभी जिंस</option></select>
  </label>
  <label>खोजें
    <input id="search" placeholder="बाजार खोजें...">
  </label>
</div>

<div class="chart-wrap">
  <canvas id="priceChart"></canvas>
  <div id="chartError">चार्ट लोड नहीं हो सका।</div>
</div>

<div class="table-wrap">
<table id="priceTable">
  <thead>
    <tr>
      <th data-key="commodity">जिंस</th>
      <th data-key="state">राज्य</th>
      <th data-key="district">जिला</th>
      <th data-key="market">बाजार</th>
      <th data-key="variety">किस्म</th>
      <th data-key="max_price">अधिकतम मूल्य</th>
      <th data-key="modal_price">औसत मूल्य</th>
      <th data-key="min_price">न्यूनतम मूल्य</th>
      <th data-key="arrival_date">अंतिम अद्यतन</th>
      <th data-key="_trend">मूल्य स्थिति</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>
</div>
<div class="note">"मूल्य स्थिति" कॉलम आज के न्यूनतम-अधिकतम दायरे में औसत मूल्य की स्थिति दिखाता है (यह पिछले दिन की तुलना नहीं है, क्योंकि सरकारी डेटा प्रतिदिन केवल एक बार प्रकाशित होता है)।</div>
</div>

<footer>GitHub Actions द्वारा प्रतिदिन स्वतः अद्यतन &middot; डेटा स्रोत: कृषि एवं किसान कल्याण मंत्रालय, data.gov.in</footer>

<script>
const rows = __DATA__;

const stateFilter = document.getElementById('stateFilter');
const districtFilter = document.getElementById('districtFilter');
const marketFilter = document.getElementById('marketFilter');
const commodityFilter = document.getElementById('commodityFilter');
const search = document.getElementById('search');
const tbody = document.querySelector('#priceTable tbody');

function unique(list, key) {
  return [...new Set(list.map(r => r[key]).filter(Boolean))].sort();
}

function fillSelect(select, values, placeholder) {
  const current = select.value;
  select.innerHTML = `<option value="">${placeholder}</option>` +
    values.map(v => `<option value="${v}">${v}</option>`).join('');
  if (values.includes(current)) select.value = current;
}

// Initial state list (full)
fillSelect(stateFilter, unique(rows, 'state'), 'सभी राज्य');

function rowsForState() {
  return stateFilter.value ? rows.filter(r => r.state === stateFilter.value) : rows;
}
function rowsForStateDistrict() {
  let subset = rowsForState();
  if (districtFilter.value) subset = subset.filter(r => r.district === districtFilter.value);
  return subset;
}

function refreshCascade() {
  fillSelect(districtFilter, unique(rowsForState(), 'district'), 'सभी जिले');
  fillSelect(marketFilter, unique(rowsForStateDistrict(), 'market'), 'सभी बाजार');
}
refreshCascade();
fillSelect(commodityFilter, unique(rows, 'commodity'), 'सभी जिंस');

stateFilter.addEventListener('change', () => { districtFilter.value = ''; marketFilter.value = ''; refreshCascade(); render(); });
districtFilter.addEventListener('change', () => { marketFilter.value = ''; fillSelect(marketFilter, unique(rowsForStateDistrict(), 'market'), 'सभी बाजार'); render(); });

let sortKey = null, sortAsc = true;

function trendFor(r) {
  const min = +r.min_price || 0, max = +r.max_price || 0, modal = +r.modal_price || 0;
  if (max <= min) return 'flat';
  const pos = (modal - min) / (max - min);
  if (pos > 0.6) return 'up';
  if (pos < 0.4) return 'down';
  return 'flat';
}
const trendLabel = { up: '▲ उच्च', down: '▼ निम्न', flat: '● सामान्य' };

function render() {
  let filtered = rows.filter(r =>
    (!stateFilter.value || r.state === stateFilter.value) &&
    (!districtFilter.value || r.district === districtFilter.value) &&
    (!marketFilter.value || r.market === marketFilter.value) &&
    (!commodityFilter.value || r.commodity === commodityFilter.value) &&
    (!search.value || r.market.toLowerCase().includes(search.value.toLowerCase()))
  );
  if (sortKey) {
    filtered.sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (!isNaN(av) && !isNaN(bv)) { av = +av; bv = +bv; }
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    });
  }
  tbody.innerHTML = filtered.slice(0, 2000).map(r => {
    const t = trendFor(r);
    return `
    <tr>
      <td class="commodity-cell">${r.commodity}</td>
      <td>${r.state}</td><td>${r.district}</td><td>${r.market}</td>
      <td>${r.variety}</td>
      <td>₹${r.max_price}</td><td>₹${r.modal_price}</td><td>₹${r.min_price}</td>
      <td>${r.arrival_date}</td>
      <td><span class="trend ${t}">${trendLabel[t]}</span></td>
    </tr>`;
  }).join('');
  updateChart(filtered);
}

document.querySelectorAll('#priceTable th').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (key === '_trend') return;
    sortAsc = (sortKey === key) ? !sortAsc : true;
    sortKey = key;
    render();
  });
});

[marketFilter, commodityFilter, search].forEach(el => el.addEventListener('input', render));

let chart;
function updateChart(filtered) {
  if (typeof Chart === 'undefined') {
    document.getElementById('chartError').style.display = 'block';
    return;
  }
  try {
    const top = filtered.slice(0, 12);
    const ctx = document.getElementById('priceChart').getContext('2d');
    const labels = top.map(r => `${r.market} (${r.commodity})`);
    const data = top.map(r => +r.modal_price || 0);
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'औसत मूल्य (₹)', data, backgroundColor: '#1e8449' }] },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          title: { display: true, text: 'बाजार अनुसार औसत मूल्य (पहली 12 पंक्तियाँ)', color: '#1a1a1a' }
        },
        scales: {
          x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 30, color: '#333' }, grid: { color: '#e0e0e0' } },
          y: { ticks: { color: '#333' }, grid: { color: '#e0e0e0' } }
        }
      }
    });
  } catch (e) {
    document.getElementById('chartError').style.display = 'block';
    console.error(e);
  }
}

render();
</script>
</body>
</html>
"""
    html = html.replace("__CHARTJS__", chartjs_code)
    html = html.replace("__DATA__", data_json)
    html = html.replace("__TICKER_TEXT__", ticker_text)
    html = html.replace("__PULLED_ON__", pulled_on)
    html = html.replace("__RECORD_COUNT__", str(len(rows)))
    return html


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("DATA_GOV_API_KEY environment variable is not set.")

    print("Pulling nationwide mandi prices...")
    rows = fetch_all()
    print(f"Total records pulled: {len(rows)}")

    chartjs_code = load_chartjs()
    html = generate_html(rows, chartjs_code)

    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(SITE_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    print("index.html and data.json written.")
