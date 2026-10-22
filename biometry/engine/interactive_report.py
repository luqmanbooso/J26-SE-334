"""Interactive HTML report for a live-run timeline.

`run_live_adaptive.py` already writes `<out>_timeline.json` (a `records` list,
one dict per completed action) and a static `<out>_timeline.png`. This module
turns the same JSON into a self-contained, *interactive* HTML page so a reader
can explore which button taps drove the engine's cognitive stress up:

  * stress over the run as a filled line, markers coloured by cognitive state;
  * red bands shading every sustained high-stress episode;
  * hovering any tap shows the element it aimed at, the state, spatial error,
    hit/miss, UI delay and rage-tap count;
  * clicking a red band lists exactly the taps inside that episode in a table.

The page pulls Plotly from a CDN; everything else (the data, the interaction
code) is inlined, so the file is portable once opened on a networked machine.
Design-side rationale lives with C2's visualisation notes; this is tooling, so
it states no experimental result of its own.
"""
import html
import json
import os

PLOTLY_CDN = "https://cdn.jsdelivr.net/npm/plotly.js@2.35.2/dist/plotly.min.js"
# A vendored copy makes every report fully self-contained and offline-capable
# (important for a viva/defence where there may be no network). When present it
# is inlined; otherwise the report falls back to the CDN.
_VENDOR_PLOTLY = os.path.join(os.path.dirname(__file__), "_vendor", "plotly.min.js")


def _plotly_script_tag():
    try:
        with open(_VENDOR_PLOTLY, "r", encoding="utf-8") as fh:
            return "<script>\n" + fh.read() + "\n</script>"
    except Exception:
        return f'<script src="{PLOTLY_CDN}"></script>'

# A tap counts as "high stress" at or above this level; contiguous high-stress
# taps are merged into one shaded episode.
HIGH_STRESS = 0.7


def _load_records(timeline_json_path):
    with open(timeline_json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        return data, list(data.get("records", []))
    # Older/alternate shape: a bare list of records.
    return {}, list(data)


def _episodes(records, threshold=HIGH_STRESS):
    """Index ranges [start, end] of contiguous taps at/above the threshold."""
    spans = []
    start = None
    for i, r in enumerate(records):
        hot = float(r.get("stress_s", 0.0) or 0.0) >= threshold
        if hot and start is None:
            start = i
        elif not hot and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(records) - 1))
    return spans


def _reliability_banner(reliability):
    """A prominent notice at the top of the report when a replay was disrupted, so a
    stuck/relaunched run can never quietly look like a clean one. Returns "" for a
    clean ('ok') run or when there is no verdict (e.g. a map run)."""
    if not reliability:
        return ""
    level = reliability.get("level", "ok")
    if level == "ok":
        return ""
    msg = html.escape(str(reliability.get("message", "")))
    counts = "{} taps · {} relaunches · {} drifts · {} screens verified".format(
        reliability.get("taps", "—"), reliability.get("relaunches", "—"),
        reliability.get("drifts", "—"), reliability.get("verified", "—"))
    label = "⚠ Results may be unreliable" if level == "unreliable" else "⚠ Read with caution"
    return ('<div class="banner {lvl}"><div class="bt">{label}</div>'
            '<div class="bm">{msg}</div><div class="bc">{counts}</div></div>').format(
                lvl=html.escape(level), label=label, msg=msg, counts=html.escape(counts))


def build_report(timeline_json_path, out_html_path=None, threshold=HIGH_STRESS,
                 reliability=None):
    """Write an interactive HTML report next to the timeline JSON.

    Returns the path written. `out_html_path` defaults to the JSON path with
    `_timeline.json` / `.json` swapped for `_report.html`.

    `reliability` is the replay verdict dict (level/message/counts). If not passed,
    a sibling `<base>_reliability.json` (written by a replay run) is auto-loaded, so
    the banner appears whoever calls build_report. A map run leaves no sidecar and so
    gets no banner.
    """
    meta, records = _load_records(timeline_json_path)
    base = timeline_json_path
    for suffix in ("_timeline.json", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if out_html_path is None:
        out_html_path = base + "_report.html"
    if reliability is None:
        try:
            with open(base + "_reliability.json", "r", encoding="utf-8") as fh:
                reliability = json.load(fh)
        except Exception:
            reliability = None

    spans = _episodes(records, threshold)
    n = len(records)
    stresses = [float(r.get("stress_s", 0.0) or 0.0) for r in records]
    misses = sum(1 for r in records if not r.get("hit_flag", True))
    rage_episodes = sum(1 for r in records if (r.get("rage_taps", 0) or 0) > 0)
    peak = max(stresses) if stresses else 0.0
    mean = (sum(stresses) / n) if n else 0.0

    summary = {
        "run_id": meta.get("run_id", "—"),
        "persona_id": meta.get("persona_id", "—"),
        "taps": n,
        "miss_rate": (100.0 * misses / n) if n else 0.0,
        "mean_stress": mean,
        "peak_stress": peak,
        "rage_episodes": rage_episodes,
        "hot_episodes": len(spans),
        "source": os.path.basename(timeline_json_path),
    }

    payload = json.dumps(
        {"records": records, "spans": spans, "threshold": threshold, "summary": summary},
        ensure_ascii=False,
    )

    title = f"C2 Stress Report · {html.escape(str(summary['run_id']))}"
    doc = _TEMPLATE.replace("__TITLE__", title)
    doc = doc.replace("__PLOTLY_SCRIPT__", _plotly_script_tag())
    doc = doc.replace("__BANNER__", _reliability_banner(reliability))
    doc = doc.replace("__PAYLOAD__", payload)

    with open(out_html_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return out_html_path


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
__PLOTLY_SCRIPT__
<style>
  /* Always light. The report deliberately does NOT follow the OS/browser dark
     preference: when the page went dark the KPI tiles (white bg, light text) and
     the Plotly chart (dark axis text on a dark card) became unreadable. Pin it
     light so it matches the HEART app and reads correctly everywhere. */
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
         background: #f8fafc; color: #0f172a; }
  header { padding: 18px 20px 6px; }
  h1 { margin: 0 0 2px; font-size: 18px; }
  .sub { color: #64748b; font-size: 12px; }
  .wrap { padding: 12px 16px 40px; max-width: 1100px; margin: 0 auto; }
  .kpis { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 14px; }
  .kpi { flex: 1 1 120px; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
         padding: 10px 12px; }
  .kpi .v { font-size: 20px; font-weight: 700; color: #0f172a; }
  .kpi .l { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 8px; }
  #chart, #chart2 { width: 100%; height: 460px; }
  .chart-toggle { display: flex; margin: 2px 2px 8px; }
  .chart-toggle .tab { border: 1px solid #e2e8f0; background: #fff; color: #475569;
      font-size: 12px; font-weight: 600; padding: 5px 12px; cursor: pointer; }
  .chart-toggle .tab:first-child { border-radius: 8px 0 0 8px; }
  .chart-toggle .tab:last-child { border-radius: 0 8px 8px 0; border-left: none; }
  .chart-toggle .tab.active { background: #6366f1; color: #fff; border-color: #6366f1; }
  .hint { font-size: 12px; color: #64748b; margin: 8px 2px; }
  h2 { font-size: 14px; margin: 18px 2px 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }
  th { position: sticky; top: 0; background: #f1f5f9; }
  td.miss { color: #dc2626; font-weight: 600; }
  td.hit { color: #059669; }
  .tblwrap { max-height: 340px; overflow: auto; border: 1px solid #e2e8f0; border-radius: 10px; }
  .pill { display:inline-block; padding:1px 7px; border-radius:999px; font-size:11px; font-weight:600; }
  .banner { border-radius: 10px; padding: 12px 14px; margin: 10px 0 4px; border: 1px solid; }
  .banner .bt { font-weight: 700; font-size: 14px; }
  .banner .bm { font-size: 12.5px; margin-top: 3px; line-height: 1.45; }
  .banner .bc { font-size: 11px; margin-top: 6px; opacity: .8; font-variant-numeric: tabular-nums; }
  .banner.unreliable { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
  .banner.caution { background: #fffbeb; border-color: #fde68a; color: #92400e; }
</style>
</head>
<body>
<header>
  <h1>Human Stress-Aware Input — Live Run Report</h1>
  <div class="sub" id="subtitle"></div>
</header>
<div class="wrap">
  __BANNER__
  <div class="kpis" id="kpis"></div>
  <div class="card">
    <div class="chart-toggle">
      <button id="tab-stress" class="tab active" onclick="showChart('stress')">Stress over taps</button>
      <button id="tab-spatial" class="tab" onclick="showChart('spatial')">Where taps landed</button>
    </div>
    <div id="chart"></div>
    <div id="chart2" style="display:none"></div>
  </div>
  <div class="hint">Hover a tap to see what it aimed at and why stress moved.
     Click a <b style="color:#dc2626">red stress band</b> (or any marker) to list the taps that drove that episode.</div>
  <h2 id="tbl-title">Taps driving stress</h2>
  <div class="tblwrap">
    <table id="tbl"><thead><tr>
      <th>#</th><th>t (s)</th><th>Target element</th><th>Scog</th><th>State</th>
      <th>Error px</th><th>Hit?</th><th>UI ms</th><th>Rage</th><th>Hesitation s</th>
    </tr></thead><tbody id="tbody"></tbody></table>
  </div>
</div>
<script>
const DATA = __PAYLOAD__;
const R = DATA.records, SPANS = DATA.spans, TH = DATA.threshold, S = DATA.summary;
const idx = R.map((_, i) => i);

const stateColor = s => ({
  calm: "#059669", impatient: "#d97706", frustrated: "#dc2626", static: "#2563eb"
}[(s || "").toLowerCase()] || "#64748b");

function fmt(v, d = 2) { return (v === undefined || v === null || isNaN(v)) ? "—" : (+v).toFixed(d); }

// KPIs
const kpis = [
  ["Taps", S.taps], ["Peak Scog", fmt(S.peak_stress)], ["Mean Scog", fmt(S.mean_stress)],
  ["Miss rate", fmt(S.miss_rate, 1) + "%"], ["Stress episodes", S.hot_episodes],
  ["Rage taps", S.rage_episodes], ["Persona", S.persona_id],
];
document.getElementById("kpis").innerHTML = kpis.map(
  ([l, v]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
document.getElementById("subtitle").textContent =
  `run ${S.run_id} · persona ${S.persona_id} · ${S.taps} taps · source ${S.source}`;

const hover = R.map((r, i) =>
  `<b>Tap #${i}</b> — ${(r.target_element_id||"?")}` +
  `<br>Scog <b>${fmt(r.stress_s)}</b> · state ${r.cognitive_state||"?"}` +
  `<br>error ${fmt(r.error_px,1)} px · ${r.hit_flag ? "HIT" : "MISS"}` +
  `<br>UI ${fmt(r.ui_delay_ms,0)} ms · rage ${r.rage_taps||0} · hesitation ${fmt(r.hesitation_s,2)} s`);

const traceStress = {
  x: idx, y: R.map(r => r.stress_s), type: "scatter", mode: "lines+markers",
  name: "Cognitive stress (Scog)", line: { color: "#6366f1", width: 2 },
  fill: "tozeroy", fillcolor: "rgba(99,102,241,0.12)",
  marker: { size: 7, color: R.map(r => stateColor(r.cognitive_state)),
            line: { width: 1, color: "#fff" } },
  text: hover, hovertemplate: "%{text}<extra></extra>",
};
const traceErr = {
  x: idx, y: R.map(r => r.error_px), type: "scatter", mode: "lines", yaxis: "y2",
  name: "Spatial error (px)", line: { color: "#f59e0b", width: 1.5, dash: "dot" },
  hoverinfo: "skip",
};
const traceUi = {
  x: idx, y: R.map(r => r.ui_delay_ms), type: "scatter", mode: "lines", yaxis: "y3",
  name: "UI delay (ms)", line: { color: "#0ea5e9", width: 1.5, dash: "dot" },
  hoverinfo: "skip",
};

const shapes = SPANS.map(([a, b]) => ({
  type: "rect", xref: "x", yref: "paper", x0: a - 0.5, x1: b + 0.5, y0: 0, y1: 1,
  fillcolor: "rgba(220,38,38,0.10)", line: { width: 0 }, layer: "below",
}));
shapes.push({ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: TH, y1: TH,
  line: { color: "#dc2626", width: 1, dash: "dash" } });

const AXIS = "#334155", GRID = "rgba(148,163,184,0.25)";
const ERR = "#f59e0b", UI = "#0ea5e9";   // each metric axis is coloured to match its line
const layout = {
  margin: { t: 10, r: 78, b: 40, l: 48 }, hovermode: "closest",
  paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
  // Pin the chart to the light theme so axes/ticks/legend never render
  // dark-on-dark (the page itself is forced light in CSS).
  font: { color: AXIS },
  // Scog on the left; spatial error (px) and UI delay (ms) each get their OWN
  // right axis — different units, so they must not share one numeric scale.
  xaxis: { title: "Tap index", domain: [0, 0.86], color: AXIS, gridcolor: GRID, zerolinecolor: GRID },
  yaxis: { title: "Scog", range: [0, 1.02], color: AXIS, gridcolor: GRID, zerolinecolor: GRID },
  yaxis2: { title: "Spatial error (px)", overlaying: "y", side: "right", anchor: "x",
            rangemode: "tozero", showgrid: false, color: ERR },
  yaxis3: { title: "UI delay (ms)", overlaying: "y", side: "right", anchor: "free",
            position: 1.0, rangemode: "tozero", showgrid: false, color: UI },
  legend: { orientation: "h", y: 1.12, font: { color: AXIS } }, shapes,
};

function rows(indices) {
  const tb = document.getElementById("tbody");
  if (!indices.length) { tb.innerHTML =
     `<tr><td colspan="10" style="color:#64748b">No taps in this selection.</td></tr>`; return; }
  tb.innerHTML = indices.map(i => { const r = R[i]; return `<tr>
    <td>${i}</td><td>${fmt((r.t_ms||0)/1000,2)}</td>
    <td>${(r.target_element_id||"?")}</td>
    <td><span class="pill" style="background:${stateColor(r.cognitive_state)}22;color:${stateColor(r.cognitive_state)}">${fmt(r.stress_s)}</span></td>
    <td>${r.cognitive_state||"?"}</td><td>${fmt(r.error_px,1)}</td>
    <td class="${r.hit_flag?'hit':'miss'}">${r.hit_flag?'hit':'MISS'}</td>
    <td>${fmt(r.ui_delay_ms,0)}</td><td>${r.rage_taps||0}</td><td>${fmt(r.hesitation_s,2)}</td>
  </tr>`; }).join("");
}

function spanFor(i) { for (const [a, b] of SPANS) if (i >= a && i <= b) return [a, b]; return null; }

function showTapsFor(i) {
  const sp = spanFor(i);
  const title = document.getElementById("tbl-title");
  if (sp) {
    const list = []; for (let k = sp[0]; k <= sp[1]; k++) list.push(k);
    title.textContent = `Taps in stress episode #${sp[0]}–${sp[1]} (${list.length} taps ≥ ${TH})`;
    rows(list);
  } else {
    title.textContent = `Tap #${i} (below the stress threshold)`;
    rows([i]);
  }
  document.querySelector(".tblwrap").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// Populate the table up front with EVERY tap (calm ones included), independent of
// Plotly so the report is useful even if the CDN is unreachable (offline). Clicking
// a red stress band still filters the table down to that high-stress episode.
(function () {
  document.getElementById("tbl-title").textContent =
    R.length ? `All taps (${R.length})` : "No taps recorded";
  rows(R.map((_, i) => i));
})();

// The chart is a progressive enhancement: guard every Plotly call so a missing
// or slow CDN degrades to "KPIs + table" instead of a blank page.
function drawChart() {
  const gd = document.getElementById("chart");
  if (typeof Plotly === "undefined") {
    gd.innerHTML = '<div style="padding:48px 16px;text-align:center;color:#64748b">' +
      'Interactive chart needs Plotly.js (offline / CDN blocked). ' +
      'The stress table below is fully populated.</div>';
    return;
  }
  Plotly.newPlot("chart", [traceStress, traceErr, traceUi], layout,
                 { responsive: true, displaylogo: false });
  if (gd.on) {
    gd.on("plotly_click", ev => { showTapsFor(ev.points[0].x); });
  }
}

// Second view: where each tap landed on the screen, coloured by stress, misses
// ringed in red (y reversed + equal aspect so it reads like a phone screen).
let spatialDrawn = false;
function drawSpatial() {
  const gd = document.getElementById("chart2");
  if (typeof Plotly === "undefined") {
    gd.innerHTML = '<div style="padding:48px 16px;text-align:center;color:#64748b">' +
      'Interactive chart needs Plotly.js (offline / CDN blocked).</div>';
    return;
  }
  const traceSpatial = {
    x: R.map(r => r.x), y: R.map(r => r.y), type: "scatter", mode: "markers",
    marker: {
      size: 11, color: R.map(r => r.stress_s), colorscale: "Viridis", cmin: 0, cmax: 1,
      colorbar: { title: "Scog", thickness: 12, len: 0.9 },
      line: { width: R.map(r => r.hit_flag ? 0.6 : 2.6),
              color: R.map(r => r.hit_flag ? "#ffffff" : "#dc2626") },
    },
    text: R.map((r, i) =>
      `<b>Tap #${i}</b> — ${(r.target_element_id||"?")}` +
      `<br>Scog ${fmt(r.stress_s)} · ${r.hit_flag ? "HIT" : "MISS"}` +
      `<br>error ${fmt(r.error_px,1)} px`),
    hovertemplate: "%{text}<extra></extra>",
  };
  const layoutSpatial = {
    margin: { t: 10, r: 10, b: 40, l: 54 }, hovermode: "closest",
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: AXIS },
    xaxis: { title: "screen x (px)", color: AXIS, gridcolor: GRID, zeroline: false },
    yaxis: { title: "screen y (px)", autorange: "reversed", scaleanchor: "x", scaleratio: 1,
             color: AXIS, gridcolor: GRID, zeroline: false },
  };
  Plotly.newPlot("chart2", [traceSpatial], layoutSpatial, { responsive: true, displaylogo: false });
  const gg = document.getElementById("chart2");
  if (gg.on) { gg.on("plotly_click", ev => { showTapsFor(ev.points[0].pointNumber); }); }
}

// Toggle which chart is shown. Plotly mis-sizes in a hidden div, so draw the
// spatial chart lazily on first open and resize whichever becomes visible.
function showChart(which) {
  const cS = document.getElementById("chart"), cP = document.getElementById("chart2");
  const spatial = (which === "spatial");
  cS.style.display = spatial ? "none" : "block";
  cP.style.display = spatial ? "block" : "none";
  document.getElementById("tab-stress").classList.toggle("active", !spatial);
  document.getElementById("tab-spatial").classList.toggle("active", spatial);
  if (typeof Plotly === "undefined") return;
  if (spatial) {
    if (!spatialDrawn) { drawSpatial(); spatialDrawn = true; }
    else Plotly.Plots.resize(cP);
  } else {
    Plotly.Plots.resize(cS);
  }
}

if (document.readyState === "complete") drawChart();
else window.addEventListener("load", drawChart);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "results/live_run_timeline.json"
    print(build_report(src))
