"""
HTML dashboard generator using Google Charts.
"""
import json, os
from string import Template
from ..core.utils import html_escape

DATE_TZ_NOTE = "All times parsed as local (no timezone metadata in sources)."

def build_kpi_html(is_calls: bool, k: dict) -> str:
    if is_calls:
        items = [
            ("Total calls", f"{k.get('total',0):,}"),
            ("Unique numbers", f"{k.get('unique_numbers',0):,}"),
            ("Start", k.get('start','-')),
            ("End", k.get('end','-')),
            ("Total duration (s)", f"{k.get('total_duration',0):,}"),
        ]
    else:
        items = [
            ("Total messages", f"{k.get('total',0):,}"),
            ("Unique chats", f"{k.get('unique_chats',0):,}"),
            ("High risk %", f"<a href='javascript:void(0)' onclick=\"applyRiskLevel('High')\">{k.get('high_risk_pct',0)}%</a>"),
            ("High risk count", f"{k.get('high_risk',0):,}"),
            ("Medium risk count", f"{k.get('med_risk',0):,}"),
            ("Low risk count", f"{k.get('low_risk',0):,}"),
            ("Meter-related msgs", f"{k.get('meter_msgs',0):,}"),
            ("Start", k.get('start','-')),
            ("End", k.get('end','-')),
            ("Days covered", f"{k.get('days',0):,}"),
            ("Avg/day", f"{k.get('avg_per_day',0.0):.1f}"),
        ]
    parts = []
    for label, val in items:
        val_s = str(val)
        val_html = val_s if ("<" in val_s and ">" in val_s) else html_escape(val_s)
        parts.append(
            f"<div class='kpi'><div class='kval'>{val_html}</div>"
            f"<div class='klabel'>{html_escape(label)}</div></div>"
        )
    return "".join(parts)

def write_dashboard_html(out_path: str, title: str, kpis: dict, charts: dict,
                         records: list, is_calls: bool):
    safe_rows = []
    if is_calls:
        for r in records:
            dur = r.get("DurationSec", "")
            try:
                dur = int(dur) if str(dur).strip() != "" else ""
            except:
                dur = ""
            safe_rows.append({
                "Date_str":     str(r.get("date_str", "")),
                "Type":         str(r.get("Type", "")),
                "Name":         str(r.get("Name", "")),
                "Number":       str(r.get("Number", "")),
                "DurationSec":  dur,
                "Source":       os.path.basename(str(r.get("Source", r.get("source","")))),
            })
    else:
        for r in records:
            safe_rows.append({
                "Category":     str(r.get("category", "Other / Unclassified")),
                "RiskPct":      int(r.get("risk_pct", 0) or 0),
                "RiskLevel":    str(r.get("risk_level", "")),
                "MeterNumbers": str(r.get("meter_numbers", "")),
                "MeterTypes":   str(r.get("meter_types", "")),
                "RiskFactors":  str(r.get("risk_factors_json", "[]")),
                "Date_str":     str(r.get("date_str", "")),
                "Chat":         str(r.get("chat", "")),
                "SnippetHtml":  str(r.get("snippet_html", "")),
            })

    data_json   = json.dumps(safe_rows, ensure_ascii=False)
    cat_json    = json.dumps(charts.get("CAT_ROWS", []), ensure_ascii=False)
    top_json    = json.dumps(charts.get("TOP_ROWS", []), ensure_ascii=False)
    mon_json    = json.dumps(charts.get("MONTHLY_ROWS", []), ensure_ascii=False)
    bank_json   = json.dumps(charts.get("BANK_ROWS", []), ensure_ascii=False)
    kw_json     = json.dumps(charts.get("KW_ROWS", []), ensure_ascii=False)
    topdur_json = json.dumps(charts.get("TOP_DUR_ROWS", []), ensure_ascii=False)

    if is_calls:
        table_head = (
            "<tr>"
            "<th onclick=\"sortBy('Date_str')\" class='sort'>Date ↕</th>"
            "<th onclick=\"sortBy('Type')\" class='sort'>Type ↕</th>"
            "<th onclick=\"sortBy('Name')\" class='sort'>Name ↕</th>"
            "<th onclick=\"sortBy('Number')\" class='sort'>Number ↕</th>"
            "<th onclick=\"sortBy('DurationSec')\" class='sort'>Duration (s) ↕</th>"
            "<th>Source</th>"
            "</tr>"
        )
        section_title = "📞 Calls"
        category_filter_html = ""
        count_id = "callCount"
        table_id = "callsTable"
        right_chart_html = "<div class='card'><h2>⏱️ Top Duration</h2><div id='barTopDur'></div></div>"
    else:
        table_head = (
            "<tr>"
            "<th onclick=\"sortBy('Category')\" class='sort'>Category ↕</th>"
            "<th onclick=\"sortBy('RiskPct')\" class='sort'>Risk ↕</th>"
            "<th onclick=\"sortBy('MeterNumbers')\" class='sort'>Meter No(s) ↕</th>"
            "<th onclick=\"sortBy('Date_str')\" class='sort'>Date ↕</th>"
            "<th onclick=\"sortBy('Chat')\" class='sort'>Chat ↕</th>"
            "<th onclick=\"sortBy('SnippetHtml')\" class='sort'>Message ↕</th>"
            "</tr>"
        )
        section_title = "💬 Messages"
        cat_opts = "".join([f"<option value='{html_escape(k)}'>{html_escape(k)}</option>"
                            for k, _ in charts.get("CAT_ROWS", [])])
        category_filter_html = (
            "<span>Filter by category:</span>"
            "<select id='catSelect' class='select' onchange='onFilterCat()'>"
            "<option value='all'>All Categories</option>"
            f"{cat_opts}</select>"
        )
        count_id = "messageCount"
        table_id = "messageTable"
        right_chart_html = "<div class='card'><h2>🏦 Banks / Keywords</h2><div id='barBanks'></div><div id='barCat'></div></div>"

    kpi_html = build_kpi_html(is_calls, kpis)
    date_range_line = f"Date range: {html_escape(kpis.get('start','-'))} to {html_escape(kpis.get('end','-'))} • {html_escape(DATE_TZ_NOTE)}"

    # Use string.Template instead of f-string for the HTML template
    html_tpl = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>$TITLE</title>
<script src="https://www.gstatic.com/charts/loader.js"></script>
<style>
:root { --bg:#fafafa; --card:#fff; --muted:#6b7280; --ink:#111827; --border:#e5e7eb; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; margin: 18px; background: var(--bg); color: var(--ink); }
.grid { display:grid; grid-template-columns:1fr; gap:18px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:14px 16px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
h1 { margin:0 0 10px 0; font-size:24px; }
h2 { margin:0 0 8px 0; font-size:18px; }
p.small { color:var(--muted); margin-top:6px; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th, td { border-bottom:1px solid var(--border); padding:8px 6px; text-align:left; vertical-align:top; }
.kpis { display:flex; gap:12px; flex-wrap:wrap; }
.kpi { min-width:160px; padding:10px 12px; border:1px solid var(--border); border-radius:10px; background:#fff; }
.kval { font-size:22px; font-weight:700; }
.klabel { font-size:12px; color:var(--muted); }
#pie, #barCat, #barTop, #barBanks, #barMonthly, #barTopDur { width:100%; height:420px; }
.two { display:grid; grid-template-columns:1fr; gap:18px; }
@media (min-width:1100px) { .two { grid-template-columns:1fr 1fr; } .span-2 { grid-column:span 2; } }
.pill { display:inline-flex; align-items:center; gap:6px; background:#eef2ff; color:#3730a3; border-radius:999px; padding:4px 10px; font-size:12px; }
.controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:10px 0; justify-content:space-between; }
.select, .pagesize, .pagejump, .searchbox { border:1px solid var(--border); border-radius:8px; padding:6px 10px; min-height:36px; }
.searchbox { width:260px; }
.muted { color:var(--muted); }
.msg-table tbody tr:hover { background:#f9fafb; }
.sort { cursor:pointer; text-decoration:underline; }
.pager { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.btn { border:1px solid var(--border); background:#fff; padding:6px 10px; border-radius:8px; cursor:pointer; }
.btn[disabled] { opacity:.5; cursor:default; }

.risklink { text-decoration: underline; font-weight: 600; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45); display:none; align-items:center; justify-content:center; padding:16px; z-index:9999; }
.modal { background: #fff; border:1px solid var(--border); border-radius:14px; max-width: 860px; width: 100%; padding: 14px 16px; box-shadow:0 10px 30px rgba(0,0,0,.2); }
.modal h3 { margin:0 0 8px 0; font-size:18px; }
.modal .muted { color: var(--muted); }
.modal table { margin-top: 10px; }
.modal .close { float:right; cursor:pointer; border:1px solid var(--border); padding:6px 10px; border-radius:10px; background:#fff; }

</style>
<script>
const IS_CALLS = $IS_CALLS;
const DATA = $DATA_JSON;
const CAT_ROWS = $CAT_JSON;
const TOP_ROWS = $TOP_JSON;
const MONTHLY_ROWS = $MON_JSON;
const BANK_ROWS = $BANK_JSON;
const KW_ROWS = $KW_JSON;
const TOP_DUR_ROWS = $TOPDUR_JSON;

for (let i = 0; i < DATA.length; i++) {
  const s = DATA[i].Date_str;
  DATA[i].Date_iso = s ? s.replace(' ', 'T') : '';
}

let currentSort = "Date_iso";
let currentOrder = "desc";
let currentPage = 1;
let pageSize = 100;
let currentQuery = "";
let currentCategory = "all";

google.charts.load('current', {'packages':['corechart']}); 
google.charts.setOnLoadCallback(drawAllCharts);

function drawAllCharts() {
  const m = google.visualization.arrayToDataTable([['Month','Count']].concat(MONTHLY_ROWS || []));
  new google.visualization.ColumnChart(document.getElementById('barMonthly')).draw(m, { backgroundColor:'transparent' });
  const t = google.visualization.arrayToDataTable([['Top','Count']].concat(TOP_ROWS || []));
  new google.visualization.ColumnChart(document.getElementById('barTop')).draw(t, { backgroundColor:'transparent' });
  if (!IS_CALLS && (CAT_ROWS||[]).length) {
    const p = google.visualization.arrayToDataTable([['Category','Count']].concat(CAT_ROWS));
    new google.visualization.PieChart(document.getElementById('pie')).draw(p, { pieHole:0.3, backgroundColor:'transparent' });
  }
  if (!IS_CALLS && (BANK_ROWS||[]).length) {
    const b = google.visualization.arrayToDataTable([['Bank','Mentions']].concat(BANK_ROWS));
    new google.visualization.ColumnChart(document.getElementById('barBanks')).draw(b, { backgroundColor:'transparent' });
  }
  if (!IS_CALLS && (KW_ROWS||[]).length) {
    const k = google.visualization.arrayToDataTable([['Keyword','Count']].concat(KW_ROWS));
    new google.visualization.ColumnChart(document.getElementById('barCat')).draw(k, { backgroundColor:'transparent' });
  }
  if (IS_CALLS && (TOP_DUR_ROWS||[]).length) {
    const d = google.visualization.arrayToDataTable([['Name','Total Duration (s)']].concat(TOP_DUR_ROWS));
    new google.visualization.ColumnChart(document.getElementById('barTopDur')).draw(d, { backgroundColor:'transparent' });
  }
}

function setPageSize(sel) {
  pageSize = parseInt(sel.value||"100", 10);
  if (!pageSize || pageSize<1) pageSize = 100;
  currentPage = 1;
  renderTable();
}
function gotoPage(inp) {
  const p = parseInt(inp.value||"1",10);
  const totalPages = Math.max(1, Math.ceil(getFilteredSorted().length / pageSize));
  currentPage = Math.max(1, Math.min(totalPages, p));
  renderTable();
}
function changePage(delta) {
  const totalPages = Math.max(1, Math.ceil(getFilteredSorted().length / pageSize));
  currentPage = Math.max(1, Math.min(totalPages, currentPage + delta));
  renderTable();
}
function firstPage() { currentPage = 1; renderTable(); }
function lastPage()  { const totalPages = Math.max(1, Math.ceil(getFilteredSorted().length / pageSize)); currentPage = totalPages; renderTable(); }
function onSearch(inp) { currentQuery = (inp.value||"").toLowerCase().trim(); currentPage = 1; renderTable(); }
function onFilterCat() { const el = document.getElementById('catSelect'); currentCategory = el ? (el.value||'all') : 'all'; currentPage = 1; renderTable(); }

function sortBy(field) {
  if (currentSort === field) {
    currentOrder = (currentOrder==='asc') ? 'desc' : 'asc';
  } else {
    currentSort = field; currentOrder = 'desc';
  }
  currentPage = 1; renderTable();
}

function fieldContainsCall(o, q) {
  if (!q) return true;
  const hay = ((o.Date_str||'')+' '+(o.Type||'')+' '+(o.Name||'')+' '+(o.Number||'')+' '+(o.Source||'')).toLowerCase();
  return hay.indexOf(q) !== -1;
}
function fieldContainsMsg(o, q) {
  if (!q) return true;
  const hay = ((o.Category||'')+' '+(o.RiskLevel||'')+' '+String(o.RiskPct||'')+' '+(o.MeterNumbers||'')+' '+(o.MeterTypes||'')+' '+(o.Date_str||'')+' '+(o.Chat||'')+' '+(o.SnippetHtml||'')).toLowerCase();
  return hay.indexOf(q) !== -1;
}

function getFilteredSorted() {
  let rows = DATA.slice(0);
  if (IS_CALLS) {
    rows = rows.filter(r => fieldContainsCall(r, currentQuery));
  } else {
    rows = rows.filter(r => (currentCategory==='all' || r.Category===currentCategory) && fieldContainsMsg(r, currentQuery));
  }
  rows.sort((a,b) => {
    let av = a[currentSort] || '', bv = b[currentSort] || '';
    if (currentSort==='Date_str' || currentSort==='Date_iso') {
      av = new Date(a['Date_iso']||a['Date_str']);
      bv = new Date(b['Date_iso']||b['Date_str']);
    }
    if (currentSort==='DurationSec' || currentSort==='RiskPct') {
      av = parseInt(av||0,10); bv = parseInt(bv||0,10);
    }
    return currentOrder==='asc' ? (av>bv?1:-1) : (av<bv?1:-1);
  });
  return rows;
}

function pagerHTML(suffix) {
  return ''
    + '<div class="pager">'
    + '<span>Rows/page:</span>'
    + '<select class="pagesize" id="pageSize'+suffix+'" onchange="setPageSize(this)"><option>25</option><option>50</option><option selected>100</option><option>250</option><option>500</option></select>'
    + '<button class="btn" onclick="firstPage()">⏮ First</button>'
    + '<button class="btn" onclick="changePage(-1)">◀ Prev</button>'
    + '<span id="pageInfo'+suffix+'" class="muted">0–0 of 0</span>'
    + '<span>Page</span>'
    + '<input class="pagejump" id="pageNum'+suffix+'" type="number" min="1" value="1" style="width:80px" onchange="gotoPage(this)" />'
    + '<span>of <span id="pageTotal'+suffix+'">1</span></span>'
    + '<button class="btn" onclick="changePage(1)">Next ▶</button>'
    + '<button class="btn" onclick="lastPage()">Last ⏭</button>'
    + '</div>';
}

function updatePager(suffix, startIdx, endIdx, total, totalPages) {
  function Q(id) { return document.getElementById(id+suffix); }
  if (!Q('pageInfo')) return;
  Q('pageInfo').textContent = (total===0 ? '0–0 of 0' : (String(startIdx+1)+'–'+String(endIdx)+' of '+String(total)));
  Q('pageNum').value = currentPage;
  Q('pageTotal').textContent = totalPages;
}


function openRisk(el) {
  try {
    const pct = el.getAttribute('data-pct') || '0';
    const level = el.getAttribute('data-level') || '';
    let factors = [];
    try { factors = JSON.parse(decodeURIComponent(el.getAttribute('data-factors') || '[]')); } catch(e) { factors = []; }

    const bd = document.getElementById('riskBackdrop');
    const title = document.getElementById('riskTitle');
    const meta = document.getElementById('riskMeta');
    const tbody = document.getElementById('riskTbody');

    if (title) title.textContent = pct + '% ' + level + ' risk — evidence';
    if (meta) meta.textContent = 'This score is the sum of matched rules (weighted). Click an evidence snippet to search the table.';
    if (tbody) {
      tbody.innerHTML = '';
      for (let i=0;i<(factors||[]).length;i++){
        const f = factors[i] || {};
        const evid = (f.evidence || '');
        const tr = document.createElement('tr');
        const evidLink = evid ? '<a href="javascript:void(0)" onclick="applySearch(\''+escapeJS(evid)+'\')">'+escapeHTML(evid)+'</a>' : '';
        tr.innerHTML = '<td>' + escapeHTML(f.factor||'') + '</td>'
                     + '<td class="muted">' + String(f.weight||0) + '</td>'
                     + '<td>' + evidLink + '</td>';
        tbody.appendChild(tr);
      }
      if ((factors||[]).length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="3" class="muted">No matched rules for this message.</td>';
        tbody.appendChild(tr);
      }
    }
    if (bd) bd.style.display = 'flex';
  } catch (e) {}
}

function closeRisk(ev) {
  const bd = document.getElementById('riskBackdrop');
  if (!bd) return;
  if (!ev || ev.target === bd) bd.style.display = 'none';
}

function applySearch(q) {
  try {
    const box = document.querySelector('.searchbox');
    if (box) { box.value = q; }
    currentQuery = (q||'').toLowerCase().trim();
    currentPage = 1;
    renderTable();
    closeRisk();
  } catch(e) {}
}

function applyRiskLevel(level) {
  try {
    const q = String(level||'').toLowerCase();
    const box = document.querySelector('.searchbox');
    if (box) box.value = level;
    currentQuery = q;
    currentPage = 1;
    renderTable();
  } catch(e) {}
}

// basic escaping helpers for modal building
function escapeHTML(s) {
  return String(s||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
}
function escapeJS(s) {
  // keep it simple: remove newlines and backslashes
  return String(s||'').replace(/\\/g,'').replace(/\r|\n/g,' ').slice(0,120);
}

function renderTable() {
  const data = getFilteredSorted();
  const total = data.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (currentPage > totalPages) currentPage = totalPages;
  const startIdx = (currentPage-1)*pageSize;
  const endIdx = Math.min(startIdx + pageSize, total);
  const pageSlice = data.slice(startIdx, endIdx);

  const tbody = document.querySelector('#$TABLE_ID tbody');
  if (tbody) tbody.innerHTML = '';

  for (var i=0;i<pageSlice.length;i++) {
    var x = pageSlice[i];
    var tr = document.createElement('tr');
    if (IS_CALLS) {
      tr.innerHTML =
          '<td class="muted">'+(x.Date_str||'')+'</td>'
        + '<td>'+(x.Type||'')+'</td>'
        + '<td>'+(x.Name||'')+'</td>'
        + '<td>'+(x.Number||'')+'</td>'
        + '<td>'+(x.DurationSec!=null?x.DurationSec:"")+'</td>'
        + '<td>'+(x.Source||'')+'</td>';
    } else {
      tr.innerHTML =
          '<td><span class="pill">'+(x.Category||'')+'</span></td>'
        + '<td><a href="javascript:void(0)" class="risklink" data-pct="'+String(x.RiskPct||0)+'" data-level="'+(x.RiskLevel||'')+'" data-factors="'+encodeURIComponent(x.RiskFactors||'[]')+'" onclick="openRisk(this)">'+String(x.RiskPct||0)+'% '+(x.RiskLevel||'')+'</a></td>'
        + '<td>'+(x.MeterNumbers||'')+'</td>'
        + '<td class="muted">'+(x.Date_str||'')+'</td>'
        + '<td>'+(x.Chat||'')+'</td>'
        + '<td>'+(x.SnippetHtml||'')+'</td>';
    }
    tbody.appendChild(tr);
  }

  var cnt = document.getElementById('$COUNT_ID');
  if (cnt) cnt.textContent = total;

  updatePager('Top', startIdx, endIdx, total, totalPages);
  updatePager('Bottom', startIdx, endIdx, total, totalPages);
}

window.addEventListener('load', function(){
  var pt = document.getElementById('pagerTop');
  var pb = document.getElementById('pagerBottom');
  if (pt) pt.innerHTML = pagerHTML('Top');
  if (pb) pb.innerHTML = pagerHTML('Bottom');
  renderTable();
});
</script>
</head>
<body>
<div class="grid">
  <div class="card">
    <h1>$TITLE</h1>
    <p class="small">$DATE_RANGE_LINE</p>
  </div>

  <div class="card">
    <h2>📊 Key Performance Indicators</h2>
    <div class="kpis">$KPI_HTML</div>
  </div>

  <div class="two">
    <div class="card"><h2>📈 Distribution / Keywords</h2><div id="pie"></div></div>
    <div class="card"><h2>📅 Monthly</h2><div id="barMonthly"></div></div>
  </div>

  <div class="two">
    <div class="card"><h2>👤 Top</h2><div id="barTop"></div></div>
    $RIGHT_CHART_HTML
  </div>

  <div class="card">
    <h2>$SECTION_TITLE</h2>
    <div class="controls">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        $CATEGORY_FILTER_HTML
        <span class="muted">Showing <span id="$COUNT_ID">0</span></span>
      </div>
      <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
        <input class="searchbox" placeholder="Search..." oninput="onSearch(this)" />
        <span id="pagerTop"></span>
      </div>
    </div>

    <table id="$TABLE_ID" class="msg-table">
      <thead>$TABLE_HEAD</thead>
      <tbody></tbody>
    </table>

    <div class="controls" style="justify-content:flex-end;">
      <span id="pagerBottom"></span>
    </div>
  </div>
</div>

<div id="riskBackdrop" class="modal-backdrop" onclick="closeRisk(event)">
  <div class="modal" onclick="event.stopPropagation()">
    <button class="close" onclick="closeRisk(event)">Close</button>
    <h3 id="riskTitle">Risk evidence</h3>
    <div id="riskMeta" class="muted"></div>
    <table>
      <thead><tr><th>Matched rule</th><th>Weight</th><th>Evidence</th></tr></thead>
      <tbody id="riskTbody"></tbody>
    </table>
  </div>
</div>

</body>
</html>""")

    html = html_tpl.safe_substitute(
        TITLE=html_escape(title),
        IS_CALLS=str(is_calls).lower(),
        DATA_JSON=data_json,
        CAT_JSON=cat_json,
        TOP_JSON=top_json,
        MON_JSON=mon_json,
        BANK_JSON=bank_json,
        KW_JSON=kw_json,
        TOPDUR_JSON=topdur_json,
        TABLE_ID=table_id,
        COUNT_ID=count_id,
        KPI_HTML=kpi_html,
        DATE_RANGE_LINE=date_range_line,
        RIGHT_CHART_HTML=right_chart_html,
        SECTION_TITLE=section_title,
        CATEGORY_FILTER_HTML=category_filter_html,
        TABLE_HEAD=table_head,
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)