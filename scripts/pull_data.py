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
    ticker_text = "   ★   ".join(ticker_items) if ticker_items else "No data available"

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live Mandi Price Dashboard</title>
<script>__CHARTJS__</script>
<style>
  * { box-sizing: border-box; }
  html { color-scheme: dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 0; background: #0e1013; color: #f0f0f0; }
  .ticker-wrap { background: #b00020; overflow: hidden; white-space: nowrap; padding: 10px 0; border-bottom: 2px solid #ff4d4d; }
  .ticker { display: inline-block; padding-left: 100%; animation: scroll-left 140s linear infinite; font-weight: 600; font-size: 0.95rem; }
  .ticker-wrap:hover .ticker { animation-play-state: paused; }
  .ticker span.live-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#fff; margin-right:8px; animation: blink 1s infinite; }
  @keyframes scroll-left { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
  @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
  .content { padding: 24px; }
  h1 { font-size: 1.5rem; margin-bottom: 4px; color: #ffffff; }
  .sub { color: #9aa0a6; margin-bottom: 20px; font-size: 0.9rem; }
  .controls { margin-bottom: 16px; display: flex; gap: 12px; flex-wrap: wrap; }
  select, input { padding: 8px 12px; border-radius: 6px; border: 1px solid #3a3d42; font-size: 0.9rem; background: #23262b; color: #f0f0f0; }
  table { border-collapse: collapse; width: 100%; background: #1c1f24; border-radius: 8px; overflow: hidden; }
  th, td { padding: 10px 14px; text-align: left; font-size: 0.85rem; border-bottom: 1px solid #2c2f34; color: #f0f0f0; }
  th { background: #23262b; cursor: pointer; color: #ffffff; font-weight: 600; }
  tbody tr:nth-child(even) { background: #1a1d22; }
  tbody tr:hover { background: #262a30; }
  .chart-wrap { max-width: 700px; margin: 24px 0; background: #1c1f24; padding: 16px; border-radius: 8px; }
  #chartError { color: #ff8080; font-size: 0.85rem; display: none; }
  footer { text-align: center; color: #6a6f75; font-size: 0.75rem; padding: 20px; }
</style>
</head>
<body>

<div class="ticker-wrap">
  <div class="ticker"><span class="live-dot"></span>__TICKER_TEXT__</div>
</div>

<div class="content">
<h1>Live Mandi Price Dashboard</h1>
<div class="sub">Last updated: __PULLED_ON__ &middot; __RECORD_COUNT__ records &middot; Source: data.gov.in</div>

<div class="controls">
  <select id="stateFilter"><option value="">All states</option></select>
  <select id="commodityFilter"><option value="">All commodities</option></select>
  <select id="districtFilter"><option value="">All districts</option></select>
  <input id="search" placeholder="Search market...">
</div>

<div class="chart-wrap">
  <canvas id="priceChart"></canvas>
  <div id="chartError">Chart could not load.</div>
</div>

<table id="priceTable">
  <thead>
    <tr>
      <th data-key="state">State</th>
      <th data-key="commodity">Commodity</th>
      <th data-key="district">District</th>
      <th data-key="market">Market</th>
      <th data-key="variety">Variety</th>
      <th data-key="grade">Grade</th>
      <th data-key="min_price">Min Price</th>
      <th data-key="max_price">Max Price</th>
      <th data-key="modal_price">Modal Price</th>
      <th data-key="arrival_date">Arrival Date</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>
</div>

<footer>Auto-updated daily via GitHub Actions &middot; Data: Ministry of Agriculture &amp; Farmers Welfare, data.gov.in</footer>

<script>
const rows = __DATA__;

const stateFilter = document.getElementById('stateFilter');
const commodityFilter = document.getElementById('commodityFilter');
const districtFilter = document.getElementById('districtFilter');
const search = document.getElementById('search');
const tbody = document.querySelector('#priceTable tbody');

function unique(key) {
  return [...new Set(rows.map(r => r[key]).filter(Boolean))].sort();
}
unique('state').forEach(s => stateFilter.innerHTML += `<option value="${s}">${s}</option>`);
unique('commodity').forEach(c => commodityFilter.innerHTML += `<option value="${c}">${c}</option>`);
unique('district').forEach(d => districtFilter.innerHTML += `<option value="${d}">${d}</option>`);

let sortKey = null, sortAsc = true;

function render() {
  let filtered = rows.filter(r =>
    (!stateFilter.value || r.state === stateFilter.value) &&
    (!commodityFilter.value || r.commodity === commodityFilter.value) &&
    (!districtFilter.value || r.district === districtFilter.value) &&
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
  tbody.innerHTML = filtered.slice(0, 2000).map(r => `
    <tr>
      <td>${r.state}</td><td>${r.commodity}</td><td>${r.district}</td><td>${r.market}</td>
      <td>${r.variety}</td><td>${r.grade}</td>
      <td>₹${r.min_price}</td><td>₹${r.max_price}</td><td>₹${r.modal_price}</td>
      <td>${r.arrival_date}</td>
    </tr>`).join('');
  updateChart(filtered);
}

document.querySelectorAll('#priceTable th').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    sortAsc = (sortKey === key) ? !sortAsc : true;
    sortKey = key;
    render();
  });
});

[stateFilter, commodityFilter, districtFilter, search].forEach(el => el.addEventListener('input', render));

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
      data: { labels, datasets: [{ label: 'Modal Price (₹)', data, backgroundColor: '#4f7cff' }] },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          title: { display: true, text: 'Modal Price by Market (first 12 rows)', color: '#f0f0f0' }
        },
        scales: {
          x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 30, color: '#c0c4c9' }, grid: { color: '#2c2f34' } },
          y: { ticks: { color: '#c0c4c9' }, grid: { color: '#2c2f34' } }
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
