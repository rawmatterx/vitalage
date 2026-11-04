"""Build a self-contained HTML dashboard of blood age and Fitness Age over time.

    python -m phenoage.dashboard --born 1984-05-10 --sex male \
        --blood examples/blood_history.csv --band examples/band_history.csv \
        --out dashboard.html

Either --blood or --band may be left out. The page needs no internet access.
"""

import argparse
import json
import sys
from datetime import date

from .band import read_rows
from .citations import FITNESS, PHENOAGE
from .history import (blood_trend, change_since_previous, fitness_trend,
                      read_blood_history)

MARKER_LABELS = {
    "albumin": "Albumin",
    "creatinine": "Creatinine",
    "glucose": "Glucose",
    "crp": "CRP",
    "lymphocyte_pct": "Lymphocyte %",
    "mcv": "MCV",
    "rdw": "RDW",
    "alp": "ALP",
    "wbc": "WBC",
    "resting_hr": "Resting HR",
    "steps": "Steps",
    "sleep_hours": "Sleep",
    "vo2max": "VO₂max",
}


def build_data(born, sex, blood_points, fitness_points):
    change = change_since_previous(blood_points)
    return {
        "born": born.isoformat(),
        "sex": sex,
        "today": date.today().isoformat(),
        "labels": MARKER_LABELS,
        "blood": [{
            "date": p.date.isoformat(),
            "age": round(p.age, 2),
            "value": round(p.phenoage, 2),
            "diff": round(p.difference, 2),
            "parts": {m: round(y, 2) for m, y in p.contributions.items()},
            "warnings": p.warnings,
        } for p in blood_points],
        "fitness": [{
            "date": p.date.isoformat(),
            "age": round(p.age, 2),
            "value": round(p.fitness_age, 2),
            "diff": round(p.difference, 2),
            "parts": {m: round(y, 2) for m, y in p.components.items()},
        } for p in fitness_points],
        "change": None if change is None else {m: round(y, 2) for m, y in change.items()},
        "refs": {
            "phenoage": [{"label": l, "text": t, "doi": d} for l, t, d in PHENOAGE],
            "fitness": [{"label": l, "text": t, "doi": d} for l, t, d in FITNESS],
        },
    }


def render(data):
    # Embed as JSON; escape "</" so no value can close the script tag.
    payload = json.dumps(data).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", payload)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="phenoage.dashboard",
                                     description="Build an HTML trend dashboard.")
    parser.add_argument("--born", required=True, help="birth date, YYYY-MM-DD")
    parser.add_argument("--sex", choices=("male", "female"),
                        help="needed for the VO2max reference")
    parser.add_argument("--blood", help="blood test history CSV")
    parser.add_argument("--band", help="daily band data CSV")
    parser.add_argument("--out", default="dashboard.html")
    args = parser.parse_args(argv)
    if not args.blood and not args.band:
        parser.error("give --blood, --band or both")

    try:
        born = date.fromisoformat(args.born)
        blood = blood_trend(read_blood_history(args.blood), born) if args.blood else []
        fitness = fitness_trend(read_rows(args.band), born, args.sex) if args.band else []
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(build_data(born, args.sex, blood, fitness)))
    print("Wrote %s (%d blood tests, %d weekly fitness points)"
          % (args.out, len(blood), len(fitness)))
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VitalAge Dashboard</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --younger: #2a78d6;
  --older: #e34948;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d;
    --surface: #1a1a19;
    --ink: #f0efec;
    --ink-2: #c3c2b7;
    --muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --border: rgba(255,255,255,0.10);
    --series-1: #3987e5;
    --series-2: #d95926;
    --younger: #3987e5;
    --older: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d;
  --surface: #1a1a19;
  --ink: #f0efec;
  --ink-2: #c3c2b7;
  --muted: #898781;
  --grid: #2c2c2a;
  --axis: #383835;
  --border: rgba(255,255,255,0.10);
  --series-1: #3987e5;
  --series-2: #d95926;
  --younger: #3987e5;
  --older: #e66767;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 0 0 4px; }
.sub { color: var(--ink-2); margin: 0 0 20px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
.tile .label { color: var(--ink-2); font-size: 13px; }
.tile .value { font-size: 32px; font-weight: 600; line-height: 1.2; }
.tile .delta { font-size: 14px; color: var(--ink-2); }
.tile .key { display: inline-block; width: 14px; height: 2px; vertical-align: middle; margin-right: 6px; }
section.card { margin-bottom: 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: var(--ink-2); margin: 8px 0; }
.legend span::before { content: ""; display: inline-block; width: 16px; height: 2px; vertical-align: middle; margin-right: 6px; background: var(--c); }
.legend .bar::before { width: 10px; height: 10px; border-radius: 2px; }
.chart { position: relative; }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.tick { fill: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.dlabel { fill: var(--ink-2); font-size: 12px; }
.tip {
  position: absolute; pointer-events: none; background: var(--surface); color: var(--ink);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 13px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12); white-space: nowrap; display: none; z-index: 2;
}
.tip .row { display: flex; align-items: center; gap: 8px; }
.tip .row i { width: 12px; height: 2px; background: var(--c); display: inline-block; }
.tip strong { font-variant-numeric: tabular-nums; }
.tip .when { color: var(--ink-2); margin-bottom: 4px; }
.note { color: var(--ink-2); font-size: 13px; margin: 8px 0 0; }
.empty { color: var(--muted); padding: 24px 0; }
details { margin-top: 12px; }
summary { cursor: pointer; color: var(--ink-2); font-size: 14px; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; font-size: 13px; margin-top: 8px; font-variant-numeric: tabular-nums; }
th, td { padding: 4px 10px; text-align: right; border-bottom: 1px solid var(--grid); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--ink-2); font-weight: 600; }
footer { color: var(--muted); font-size: 13px; }
.refs ol { font-size: 13px; color: var(--ink-2); padding-left: 20px; margin: 8px 0; }
.refs li { margin-bottom: 4px; }
a { color: var(--series-1); }
</style>
</head>
<body>
<main>
  <h1>VitalAge</h1>
  <p class="sub" id="sub"></p>
  <div class="tiles" id="tiles"></div>

  <section class="card">
    <h2>Years older or younger than your calendar age</h2>
    <div class="legend" id="trend-legend"></div>
    <div class="chart" id="trend"></div>
    <p class="note">Below zero means your body measures younger than your age. Single blood tests are
      noisy (a cold can raise CRP and WBC), so look at the direction over several tests.</p>
    <details><summary>Show as a table</summary><div class="tablewrap" id="trend-table"></div></details>
  </section>

  <section class="card">
    <h2 id="parts-title">What drives your latest blood age</h2>
    <p class="sub" id="parts-sub" style="margin:0"></p>
    <div class="legend">
      <span class="bar" style="--c: var(--older)">Adds years</span>
      <span class="bar" style="--c: var(--younger)">Removes years</span>
    </div>
    <div class="chart" id="parts"></div>
    <details><summary>Show as a table</summary><div class="tablewrap" id="parts-table"></div></details>
  </section>

  <section class="card">
    <h2>What drives your latest Fitness Age</h2>
    <p class="sub" style="margin:0">Compared with the reference values in the README</p>
    <div class="chart" id="fit-parts"></div>
  </section>

  <section class="card refs">
    <h2>Scientific basis</h2>
    <p class="note" style="margin-top:0">Blood age is <strong>Phenotypic Age (PhenoAge)</strong>, developed by
      Levine et al. (2018) on US NHANES III data and validated in NHANES IV by Liu et al. (2018). The published
      coefficients are used unchanged. It has not been validated for Indian populations.</p>
    <ol id="refs-pheno"></ol>
    <p class="note">Fitness Age combines effects from separate meta-analyses; it is a literature-based score,
      not a validated clock.</p>
    <ol id="refs-fit"></ol>
  </section>

  <footer>VitalAge is an independent implementation, not affiliated with or endorsed by the authors cited.
    Not a diagnostic tool.</footer>
</main>

<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById("data").textContent);
  var NS = "http://www.w3.org/2000/svg";
  var css = getComputedStyle(document.documentElement);
  function v(name) { return css.getPropertyValue(name).trim(); }
  function el(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function h(tag, text, parent, cls) {
    var n = document.createElement(tag);
    if (text != null) n.textContent = text;
    if (cls) n.className = cls;
    if (parent) parent.appendChild(n);
    return n;
  }
  function signed(x) {
    var r = Math.round(x * 10) / 10;   // sign follows the shown value, so no "-0.0"
    return (r > 0 ? "+" : r < 0 ? "−" : "±") + Math.abs(r).toFixed(1);
  }
  function fmtDate(s) {
    var d = new Date(s + "T00:00:00");
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }
  function label(key) { return D.labels[key] || key; }
  function last(a) { return a[a.length - 1]; }

  var series = [
    { key: "blood", name: "Blood age (PhenoAge)", color: "--series-1", points: D.blood, dots: true },
    { key: "fitness", name: "Fitness Age (band)", color: "--series-2", points: D.fitness, dots: false }
  ].filter(function (s) { return s.points.length; });

  // Subtitle and tiles
  var today = new Date(D.today + "T00:00:00");
  var age = (today - new Date(D.born + "T00:00:00")) / (365.2425 * 864e5);
  document.getElementById("sub").textContent =
    "Calendar age " + age.toFixed(1) + " · updated " + fmtDate(D.today);
  var tiles = document.getElementById("tiles");
  function tile(title, value, delta, color) {
    var c = h("div", null, tiles, "card tile");
    var l = h("div", null, c, "label");
    if (color) { var k = h("span", null, l, "key"); k.style.background = "var(" + color + ")"; }
    l.appendChild(document.createTextNode(title));
    h("div", value, c, "value");
    h("div", delta, c, "delta");
  }
  tile("Calendar age", age.toFixed(1), "years");
  if (D.blood.length) {
    var b = last(D.blood);
    tile("Blood age", b.value.toFixed(1), signed(b.diff) + " yrs · test of " + fmtDate(b.date), "--series-1");
  }
  if (D.fitness.length) {
    var f = last(D.fitness);
    tile("Fitness Age", f.value.toFixed(1), signed(f.diff) + " yrs · 30 days to " + fmtDate(f.date), "--series-2");
  }

  // Legend for the trend chart (always present for 2+ series)
  var legend = document.getElementById("trend-legend");
  series.forEach(function (s) {
    var sp = h("span", s.name, legend);
    sp.style.setProperty("--c", "var(" + s.color + ")");
  });

  function niceStep(span, target) {
    var raw = span / target, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var n = raw / mag;
    return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
  }

  function drawTrend() {
    var box = document.getElementById("trend");
    box.textContent = "";
    if (!series.length) { h("p", "No data yet.", box, "empty"); return; }
    var W = Math.max(box.clientWidth, 300), H = 280;
    var m = { l: 40, r: W < 520 ? 16 : 120, t: 12, b: 28 };
    var all = [];
    series.forEach(function (s) { s.points.forEach(function (p) { all.push(p); }); });
    var t0 = Math.min.apply(null, all.map(function (p) { return Date.parse(p.date); }));
    var t1 = Math.max.apply(null, all.map(function (p) { return Date.parse(p.date); }));
    if (t1 === t0) { t0 -= 15 * 864e5; t1 += 15 * 864e5; }
    var ymax = Math.max(2, Math.max.apply(null, all.map(function (p) { return Math.abs(p.diff); })));
    var step = niceStep(2 * ymax, 4);
    ymax = Math.ceil(ymax / step) * step;
    function x(d) { return m.l + (Date.parse(d) - t0) / (t1 - t0) * (W - m.l - m.r); }
    function y(val) { return m.t + (ymax - val) / (2 * ymax) * (H - m.t - m.b); }

    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Trend of years older or younger than calendar age" }, box);
    for (var g = -ymax; g <= ymax + 1e-9; g += step) {
      el("line", { x1: m.l, x2: W - m.r, y1: y(g), y2: y(g),
        stroke: v(g === 0 ? "--axis" : "--grid"), "stroke-width": 1 }, svg);
      el("text", { x: m.l - 6, y: y(g) + 4, "text-anchor": "end", "class": "tick" }, svg)
        .textContent = (g > 0 ? "+" : "") + g;
    }
    // Month ticks
    var start = new Date(t0), months = [];
    var d0 = new Date(start.getFullYear(), start.getMonth() + 1, 1);
    for (var d = d0; d.getTime() <= t1; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) months.push(d);
    var every = Math.max(1, Math.ceil(months.length / Math.floor((W - m.l - m.r) / 70)));
    months.forEach(function (d, i) {
      if (i % every) return;
      var iso = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-01";
      el("text", { x: x(iso), y: H - 8, "text-anchor": "middle", "class": "tick" }, svg).textContent =
        d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
    });

    series.forEach(function (s) {
      var color = v(s.color);
      var dpath = s.points.map(function (p, i) { return (i ? "L" : "M") + x(p.date) + "," + y(p.diff); }).join("");
      el("path", { d: dpath, fill: "none", stroke: color, "stroke-width": 2,
        "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      if (s.dots) s.points.forEach(function (p) {
        el("circle", { cx: x(p.date), cy: y(p.diff), r: 4.5, fill: color, stroke: v("--surface"), "stroke-width": 2 }, svg);
      });
      if (m.r > 40) {
        var lp = last(s.points);
        el("text", { x: x(lp.date) + 8, y: y(lp.diff) + 4, "class": "dlabel" }, svg)
          .textContent = (s.key === "blood" ? "Blood " : "Fitness ") + signed(lp.diff);
      }
    });

    // Crosshair + one tooltip listing every series
    var cross = el("line", { y1: m.t, y2: H - m.b, stroke: v("--axis"), "stroke-width": 1, visibility: "hidden" }, svg);
    var tip = h("div", null, box, "tip");
    var hit = el("rect", { x: m.l, y: 0, width: W - m.l - m.r + 8, height: H, fill: "transparent", tabindex: 0 }, svg);
    function nearest(points, t) {
      var best = null, bd = Infinity;
      points.forEach(function (p) { var dd = Math.abs(Date.parse(p.date) - t); if (dd < bd) { bd = dd; best = p; } });
      return best;
    }
    function show(t) {
      var anchor = nearest(all, t);
      var xx = x(anchor.date);
      cross.setAttribute("x1", xx); cross.setAttribute("x2", xx);
      cross.setAttribute("visibility", "visible");
      tip.textContent = "";
      h("div", fmtDate(anchor.date), tip, "when");
      series.forEach(function (s) {
        var p = nearest(s.points, Date.parse(anchor.date));
        var row = h("div", null, tip, "row");
        row.style.setProperty("--c", "var(" + s.color + ")");
        h("i", null, row);
        h("strong", signed(p.diff) + " yrs", row);
        h("span", (s.key === "blood" ? "Blood, " : "Fitness, ") + fmtDate(p.date), row);
      });
      tip.style.display = "block";
      var left = xx / W * box.clientWidth + 12;
      if (left + tip.offsetWidth > box.clientWidth) left = xx / W * box.clientWidth - tip.offsetWidth - 12;
      tip.style.left = Math.max(0, left) + "px";
      tip.style.top = "8px";
    }
    function hide() { cross.setAttribute("visibility", "hidden"); tip.style.display = "none"; }
    hit.addEventListener("pointermove", function (e) {
      var r = svg.getBoundingClientRect();
      var px = (e.clientX - r.left) / r.width * W;
      show(t0 + (px - m.l) / (W - m.l - m.r) * (t1 - t0));
    });
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", function () { show(t1); });
    hit.addEventListener("blur", hide);
  }

  function drawBars(boxId, parts, emptyText) {
    var box = document.getElementById(boxId);
    box.textContent = "";
    var keys = Object.keys(parts || {});
    if (!keys.length) { h("p", emptyText, box, "empty"); return; }
    keys.sort(function (a, b) { return parts[b] - parts[a]; });
    var W = Math.max(box.clientWidth, 300), row = 28, H = keys.length * row + 8;
    var lw = W < 480 ? 92 : 104, vw = 40;   // label column, room for the value text
    var span = Math.max(1, Math.max.apply(null, keys.map(function (k) { return Math.abs(parts[k]); })));
    var mid = lw + (W - lw) / 2, half = (W - lw) / 2 - vw;
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Years per marker" }, box);
    el("line", { x1: mid, x2: mid, y1: 0, y2: H, stroke: v("--axis"), "stroke-width": 1 }, svg);
    var tip = h("div", null, box, "tip");
    keys.forEach(function (k, i) {
      var val = parts[k], cy = i * row + 4, bh = row - 10;
      var w = Math.abs(val) / span * half;
      var x0 = val >= 0 ? mid + 1 : mid - 1 - w;
      el("text", { x: 0, y: cy + bh / 2 + 4, "class": "dlabel" }, svg).textContent = label(k);
      if (w >= 0.5) el("rect", { x: x0, y: cy, width: w, height: bh, rx: 4,
        fill: v(val >= 0 ? "--older" : "--younger") }, svg);
      var tx = val >= 0 ? mid + w + 6 : mid - w - 6;
      el("text", { x: tx, y: cy + bh / 2 + 4, "class": "tick", "text-anchor": val >= 0 ? "start" : "end" }, svg)
        .textContent = signed(val);
      var hit = el("rect", { x: 0, y: cy - 4, width: W, height: row, fill: "transparent", tabindex: 0 }, svg);
      function show() {
        tip.textContent = "";
        h("strong", signed(val) + " yrs", tip);
        tip.appendChild(document.createTextNode(" " + label(k)));
        tip.style.display = "block";
        tip.style.left = Math.min(box.clientWidth - tip.offsetWidth, mid / W * box.clientWidth) + "px";
        tip.style.top = ((cy + row) / H * box.clientHeight) + "px";
      }
      hit.addEventListener("pointerenter", show);
      hit.addEventListener("focus", show);
      hit.addEventListener("pointerleave", function () { tip.style.display = "none"; });
      hit.addEventListener("blur", function () { tip.style.display = "none"; });
    });
  }

  function table(boxId, head, rows) {
    var box = document.getElementById(boxId);
    box.textContent = "";
    var t = h("table", null, box), tr = h("tr", null, h("thead", null, t));
    head.forEach(function (c) { h("th", c, tr); });
    var body = h("tbody", null, t);
    rows.forEach(function (r) {
      var row = h("tr", null, body);
      r.forEach(function (c) { h("td", c, row); });
    });
  }

  function drawAll() {
    drawTrend();
    var lb = D.blood.length ? last(D.blood) : null;
    if (lb) {
      var markerSum = Object.keys(lb.parts).reduce(function (s, k) { return s + lb.parts[k]; }, 0);
      var baseline = lb.value - markerSum;
      document.getElementById("parts-sub").textContent =
        "Test of " + fmtDate(lb.date) + ". A typical healthy adult your age (reference values) scores " +
        baseline.toFixed(1) + " (" + signed(baseline - lb.age) + " yrs); your markers move that by " +
        signed(markerSum) + " yrs to " + lb.value.toFixed(1) + ".";
    }
    drawBars("parts", lb && lb.parts, "Add a blood test history to see this.");
    drawBars("fit-parts", D.fitness.length ? last(D.fitness).parts : null, "Add band data to see this.");
  }

  // Tables (built once)
  var trendRows = [];
  D.blood.forEach(function (p) { trendRows.push([p.date, "Blood", p.age.toFixed(1), p.value.toFixed(1), signed(p.diff)]); });
  D.fitness.forEach(function (p) { trendRows.push([p.date, "Fitness", p.age.toFixed(1), p.value.toFixed(1), signed(p.diff)]); });
  trendRows.sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0; });
  table("trend-table", ["Date", "Measure", "Calendar age", "Body age", "Difference"], trendRows);

  if (D.blood.length) {
    var mk = Object.keys(D.blood[0].parts);
    var head = ["Marker"].concat(D.blood.map(function (p) { return p.date; }));
    if (D.change) head.push("Change");
    var rows = mk.map(function (k) {
      var r = [label(k)].concat(D.blood.map(function (p) { return signed(p.parts[k]); }));
      if (D.change) r.push(signed(D.change[k]));
      return r;
    });
    table("parts-table", head, rows);
  }

  function refs(id, list) {
    var ol = document.getElementById(id);
    list.forEach(function (r) {
      var li = h("li", r.text + " ", ol);
      var a = h("a", "doi:" + r.doi, li);
      a.href = "https://doi.org/" + r.doi;
      a.rel = "noopener";
    });
  }
  refs("refs-pheno", D.refs.phenoage);
  refs("refs-fit", D.refs.fitness);

  drawAll();
  var timer;
  window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(drawAll, 150); });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      css = getComputedStyle(document.documentElement); drawAll();
    });
  }
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
