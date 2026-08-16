"""Build the live observability dashboard from the run history.

Reads models/metrics_history.json and writes docs/index.html (self-contained,
data inlined) so it can be served by GitHub Pages. Also opens it locally when
run by hand. Runs automatically in the pipeline, so the published URL always
reflects the latest run.
"""
from __future__ import annotations

import json
import os
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "models", "metrics_history.json")
OUT_DIR = os.path.join(ROOT, "docs")
OUT = os.path.join(OUT_DIR, "index.html")

history = json.load(open(HIST)) if os.path.exists(HIST) else []

HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Self-Distilling Classifier — Observability</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root{
    --bg:#fbeef0; --bg2:#f6e2e8; --panel:#ffffff; --panel-2:#fdf5f7;
    --line:#f0d6de; --line-soft:#f5e3e8;
    --ink:#3a2530; --muted:#9c7684; --faint:#c0a3ad;
    --agree:#c0567e;      /* deep rose — student agreement */
    --drift:#c98a3c;      /* warm ochre — drift */
    --up:#4e9c86;         /* muted green — promoted */
    --hold:#a98a97;       /* dusty mauve — kept */
    --mono:'JetBrains Mono',ui-monospace,monospace;
    --disp:'Space Grotesk',system-ui,sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{
    background:
      radial-gradient(1100px 480px at 85% -12%, #fadfe6 0%, transparent 62%),
      linear-gradient(180deg,var(--bg),var(--bg2));
    color:var(--ink); font-family:var(--disp);
    padding:32px 24px 56px; min-height:100vh;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:1000px;margin:0 auto}

  .top{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;
       flex-wrap:wrap;margin-bottom:28px;border-bottom:1px solid var(--line);padding-bottom:20px}
  .brand .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.22em;
       text-transform:uppercase;color:var(--muted);margin-bottom:8px}
  .brand h1{font-family:var(--disp);font-weight:600;font-size:clamp(24px,4vw,34px);
       letter-spacing:-.02em;margin:0;color:var(--ink)}
  .status{display:flex;align-items:center;gap:10px;font-family:var(--mono);font-size:12px;color:var(--muted)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--up);
       box-shadow:0 0 0 0 rgba(78,156,134,.6);animation:pulse 2.4s infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(78,156,134,.45)}70%{box-shadow:0 0 0 8px rgba(78,156,134,0)}100%{box-shadow:0 0 0 0 rgba(78,156,134,0)}}
  @media(prefers-reduced-motion:reduce){.dot{animation:none}}

  .tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
  .tile{background:linear-gradient(180deg,var(--panel),var(--panel-2));
        border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px;position:relative;overflow:hidden;
        box-shadow:0 1px 2px rgba(160,110,130,.06)}
  .tile .k{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
  .tile .v{font-family:var(--disp);font-weight:600;font-size:32px;margin-top:10px;letter-spacing:-.01em;line-height:1;color:var(--ink)}
  .tile .sub{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:8px}
  .tile.agree .v{color:var(--agree)} .tile.drift .v{color:var(--drift)}
  .tile .bar{position:absolute;left:0;bottom:0;height:3px;width:100%;background:var(--line-soft)}
  .tile.agree .bar{background:var(--agree)} .tile.drift .bar{background:var(--drift)}
  @media(max-width:760px){.tiles{grid-template-columns:repeat(2,1fr)}}

  .panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;
         padding:20px 20px 14px;margin-bottom:20px;box-shadow:0 1px 3px rgba(160,110,130,.06)}
  .panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
  .panel-head h2{font-family:var(--disp);font-weight:500;font-size:15px;margin:0;letter-spacing:.01em;color:var(--ink)}
  .legend{display:flex;gap:16px;font-family:var(--mono);font-size:11px;color:var(--muted)}
  .legend i{display:inline-block;width:18px;height:3px;border-radius:2px;margin-right:7px;vertical-align:middle}
  .legend .a{background:var(--agree)} .legend .d{background:var(--drift)}

  table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}
  th{color:var(--muted);font-weight:500;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;
     text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
  td{padding:12px;border-bottom:1px solid var(--line-soft);color:var(--ink)}
  tr:last-child td{border-bottom:none}
  td.num{color:var(--faint)}
  .pill{font-family:var(--mono);font-size:11px;padding:3px 10px;border-radius:100px;font-weight:500}
  .pill.up{background:rgba(78,156,134,.14);color:var(--up)}
  .pill.hold{background:rgba(169,138,151,.16);color:var(--hold)}
  .empty{color:var(--muted);text-align:center;padding:48px;font-family:var(--mono);font-size:13px}
  .foot{font-family:var(--mono);font-size:11px;color:var(--faint);text-align:center;margin-top:26px}
</style></head>
<body><div class="wrap">
  <div class="top">
    <div class="brand">
      <div class="eyebrow">Model Observability</div>
      <h1>Self-Distilling Classifier</h1>
    </div>
    <div class="status"><span class="dot"></span><span id="status">live · updated on each run</span></div>
  </div>
  <div id="app"></div>
  <div class="foot">Teacher: Gemini · Student: TF-IDF + Logistic Regression · Auto-retrained via GitHub Actions</div>
</div>
<script>
const H = __DATA__;
const pct = x => (x*100).toFixed(1) + '%';
const app = document.getElementById('app');

if(!H.length){
  app.innerHTML = '<div class="panel"><div class="empty">No runs recorded yet. The dashboard fills in after the pipeline runs.</div></div>';
} else {
  const last = H[H.length-1];
  const promotions = H.filter(r=>r.promoted).length;
  const trained = H.filter(r=>r.can_train);
  const lastAgree = trained.length ? pct(trained[trained.length-1].challenger_agreement) : '—';

  document.getElementById('status').textContent =
    'live · last run ' + (last.timestamp||'').replace('T',' ').replace('Z',' UTC');

  app.innerHTML = `
    <div class="tiles">
      <div class="tile agree">
        <div class="k">Student agreement</div>
        <div class="v">${lastAgree}</div>
        <div class="sub">latest vs. teacher</div><div class="bar"></div>
      </div>
      <div class="tile drift">
        <div class="k">Vocabulary drift</div>
        <div class="v">${pct(last.vocabulary_drift)}</div>
        <div class="sub">new terms this batch</div><div class="bar"></div>
      </div>
      <div class="tile">
        <div class="k">Papers labeled</div>
        <div class="v">${last.total_labeled}</div>
        <div class="sub">by the teacher, cumulative</div><div class="bar"></div>
      </div>
      <div class="tile">
        <div class="k">Runs · promotions</div>
        <div class="v">${H.length} · ${promotions}</div>
        <div class="sub">champions accepted</div><div class="bar"></div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>Agreement & drift over time</h2>
        <div class="legend"><span><i class="a"></i>Agreement</span><span><i class="d"></i>Drift</span></div>
      </div>
      <canvas id="chart" height="118"></canvas>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Run ledger</h2></div>
      <table><thead><tr>
        <th>Run</th><th>Labeled</th><th>Teacher yes</th><th>Agreement</th><th>Drift</th><th>Decision</th>
      </tr></thead><tbody>
      ${H.map((r,i)=>`<tr>
        <td class="num">#${String(i+1).padStart(2,'0')}</td>
        <td>${r.total_labeled}</td>
        <td>${pct(r.positive_rate)}</td>
        <td>${r.can_train?pct(r.challenger_agreement):'—'}</td>
        <td>${pct(r.vocabulary_drift)}</td>
        <td>${r.promoted?'<span class="pill up">promoted</span>':'<span class="pill hold">kept</span>'}</td>
      </tr>`).join('')}
      </tbody></table>
    </div>`;

  const gridC = 'rgba(160,110,130,0.12)', tick = '#9c7684';
  new Chart(document.getElementById('chart'), {
    type:'line',
    data:{ labels:H.map((_,i)=>'Run '+(i+1)),
      datasets:[
        {label:'Student agreement', data:H.map(r=>r.can_train?r.challenger_agreement:null),
         borderColor:'#c0567e', backgroundColor:'rgba(192,86,126,.10)', fill:true,
         tension:.35, spanGaps:true, pointRadius:4, pointBackgroundColor:'#c0567e', borderWidth:2},
        {label:'Vocabulary drift', data:H.map(r=>r.vocabulary_drift),
         borderColor:'#c98a3c', backgroundColor:'rgba(201,138,60,.10)', fill:true,
         tension:.35, pointRadius:4, pointBackgroundColor:'#c98a3c', borderWidth:2},
      ]},
    options:{ responsive:true, maintainAspectRatio:true,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>c.dataset.label+': '+(c.parsed.y*100).toFixed(1)+'%'}}},
      scales:{
        y:{min:0,max:1,grid:{color:gridC},ticks:{color:tick,callback:v=>(v*100)+'%'}},
        x:{grid:{color:gridC},ticks:{color:tick}}
      }}
  });
}
</script></body></html>"""

os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML.replace("__DATA__", json.dumps(history)))

print(f"Dashboard written to {OUT}")
if os.environ.get("CI") != "true":
    try:
        webbrowser.open("file://" + OUT)
    except Exception:
        pass
