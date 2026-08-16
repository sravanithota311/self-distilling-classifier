"""Build a visual dashboard from the run history.

    python scripts/make_dashboard.py

Reads models/metrics_history.json and writes dashboard.html with the data
baked in, then you just open dashboard.html in your browser. No server needed.
"""
from __future__ import annotations

import json
import os
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "models", "metrics_history.json")
OUT = os.path.join(ROOT, "dashboard.html")

history = json.load(open(HIST)) if os.path.exists(HIST) else []

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Self-Distilling Classifier — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root{--ink:#17201b;--accent:#1e5a4c;--gold:#b07d14;--line:#d0d4cb;--paper:#eceee8;--slate:#57615a}
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);
       font-family:'Space Grotesk',system-ui,sans-serif;padding:32px}
  h1{font-weight:500;letter-spacing:-.02em;margin:0 0 4px}
  .sub{color:var(--slate);margin:0 0 28px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px}
  .card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px}
  .card .k{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--gold)}
  .card .v{font-size:30px;font-weight:600;margin-top:6px}
  .panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:24px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
  th{color:var(--slate);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
  .badge{padding:2px 9px;border-radius:100px;font-size:12px;font-weight:600}
  .yes{background:#e2efe9;color:var(--accent)}
  .no{background:#efe7e2;color:#8a5a2a}
  .empty{color:var(--slate);padding:40px;text-align:center}
</style></head><body>
<h1>Self-Distilling Classifier</h1>
<p class="sub">Live view of the model teaching itself. Regenerate after each run.</p>
<div id="app"></div>
<script>
const H = __DATA__;

function pct(x){return (x*100).toFixed(1)+'%';}
const app = document.getElementById('app');

if(!H.length){
  app.innerHTML = '<div class="panel empty">No runs yet. Run the pipeline, then regenerate this dashboard.</div>';
} else {
  const last = H[H.length-1];
  const promotions = H.filter(r=>r.promoted).length;
  app.innerHTML = `
    <div class="cards">
      <div class="card"><div class="k">Latest agreement</div><div class="v">${pct(last.challenger_agreement)}</div></div>
      <div class="card"><div class="k">Total labeled</div><div class="v">${last.total_labeled}</div></div>
      <div class="card"><div class="k">Runs</div><div class="v">${H.length}</div></div>
      <div class="card"><div class="k">Promotions</div><div class="v">${promotions}</div></div>
    </div>
    <div class="panel"><canvas id="chart" height="110"></canvas></div>
    <div class="panel">
      <table><thead><tr>
        <th>Run</th><th>Labeled</th><th>Teacher 'yes'</th>
        <th>Student agreement</th><th>Vocab drift</th><th>Decision</th>
      </tr></thead><tbody>
      ${H.map((r,i)=>`<tr>
        <td>#${i+1}</td>
        <td>${r.total_labeled}</td>
        <td>${pct(r.positive_rate)}</td>
        <td>${r.can_train?pct(r.challenger_agreement):'—'}</td>
        <td>${pct(r.vocabulary_drift)}</td>
        <td>${r.promoted?'<span class="badge yes">promoted</span>':'<span class="badge no">kept</span>'}</td>
      </tr>`).join('')}
      </tbody></table>
    </div>`;

  new Chart(document.getElementById('chart'), {
    type:'line',
    data:{
      labels:H.map((_,i)=>'Run '+(i+1)),
      datasets:[
        {label:'Student–teacher agreement',data:H.map(r=>r.can_train?r.challenger_agreement:null),
         borderColor:'#1e5a4c',backgroundColor:'#1e5a4c22',tension:.3,spanGaps:true},
        {label:'New-vocabulary rate (drift)',data:H.map(r=>r.vocabulary_drift),
         borderColor:'#b07d14',backgroundColor:'#b07d1422',tension:.3}
      ]
    },
    options:{scales:{y:{min:0,max:1,ticks:{callback:v=>(v*100)+'%'}}},
             plugins:{legend:{position:'bottom'}}}
  });
}
</script></body></html>"""

with open(OUT, "w") as f:
    f.write(HTML.replace("__DATA__", json.dumps(history)))

print(f"Dashboard written to {OUT}")
try:
    webbrowser.open("file://" + OUT)
    print("Opening it in your browser...")
except Exception:
    print("Open that file in your browser to view it.")
