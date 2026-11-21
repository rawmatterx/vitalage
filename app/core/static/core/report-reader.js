/* Reads a lab report (PDF or CSV) in the browser and fills the Add report form.
   The file never leaves the device: only the numbers the participant confirms
   are sent when they press "Review values".

   The reading rules are copied from web/vitalage.html (the standalone
   calculator) so both give the same results. If you change one, change both. */
(function () {
  "use strict";
  var MARKERS = ["albumin", "creatinine", "glucose", "crp", "lymphocyte_pct", "mcv", "rdw", "alp", "wbc"];

  var FACTORS = {
    albumin: { "g/l": 1, "g/dl": 10 },
    creatinine: { "umol/l": 1, "mg/dl": 88.42 },
    glucose: { "mmol/l": 1, "mg/dl": 1 / 18.016 },
    crp: { "mg/dl": 1, "mg/l": 0.1 },
    lymphocyte_pct: { "%": 1 },
    mcv: { "fl": 1 },
    rdw: { "%": 1 },
    alp: { "u/l": 1, "iu/l": 1 },
    wbc: { "10^3/ul": 1, "10^9/l": 1, "thou/ul": 1, "cells/ul": 0.001, "cells/cumm": 0.001, "/cumm": 0.001, "/ul": 0.001 }
  };
  var PLAUSIBLE = {
    albumin: [15, 60], creatinine: [20, 1500], glucose: [2, 35], crp: [0.001, 30],
    lymphocyte_pct: [1, 80], mcv: [50, 130], rdw: [9, 30], alp: [10, 1000], wbc: [0.5, 50]
  };

  function normalise(unit) {
    var u = String(unit).trim().toLowerCase().replace(/ /g, "");
    u = u.replace(/µ/g, "u").replace(/μ/g, "u");
    u = u.replace("mm3", "cumm").replace("cu.mm", "cumm");
    u = u.replace("x10^3", "10^3").replace("x10^9", "10^9");
    return u;
  }
  function factor(marker, unit) {
    var f = FACTORS[marker][normalise(unit)];
    if (f === undefined) throw new Error("Unit " + unit + " is not supported for " + marker);
    return f;
  }
  function toCanonical(marker, value, unit) {
    var f = factor(marker, unit);
    if (!(value > 0)) throw new Error("Must be greater than 0. For CRP below the detection limit, enter the limit.");
    var c = value * f, r = PLAUSIBLE[marker];
    if (c < r[0] || c > r[1]) throw new Error("Outside the plausible range; check the unit on your report.");
    return c;
  }

  // Unit choices offered on the form; the first is the usual one on Indian reports.
  var UNIT_OPTIONS = {
    albumin: ["g/dL", "g/L"], creatinine: ["mg/dL", "µmol/L"], glucose: ["mg/dL", "mmol/L"],
    crp: ["mg/L", "mg/dL"], lymphocyte_pct: ["%"], mcv: ["fL"], rdw: ["%"], alp: ["U/L", "IU/L"],
    wbc: ["cells/cumm", "10^3/µL", "10^9/L"]
  };
  // [marker, names on reports, lines to skip]
  var REPORT_NAMES = [
    ["albumin", /\balbumin\b/i, /globulin|ratio|urine|micro/i],
    ["creatinine", /\bcreatinine\b/i, /urine|clearance|ratio|egfr|kinase|\bcpk\b|\bck\b/i],
    ["glucose", /\b(glucose|blood sugar|fbs|fbg|fpg)\b/i, /post|\bpp\b|ppbs|random|\brbs\b|urine|hba1c|mean|estimated|\beag\b/i],
    ["crp", /\b(hs[\s-]*crp|c[\s-]*reactive\s+protein|crp)\b/i, null],
    ["lymphocyte_pct", /\blymphocytes?\b/i, /absolute|\babs\b|count|atypical/i],
    ["mcv", /\b(mcv|mean\s+corpuscular\s+volume|mean\s+cell\s+volume)\b/i, null],
    ["rdw", /\b(rdw|red\s+cell\s+distribution\s+width)\b/i, /\bsd\b/i],
    ["alp", /\b(alkaline\s+phosphatase|alk\.?\s*phos\w*|alp)\b/i, /bone|isoenzyme/i],
    ["wbc", /\b(total\s+leu[ck]ocyte\s+count|tlc|total\s+wbc|wbc|white\s+blood\s+cells?|total\s+count|leu[ck]ocytes?)\b/i, /urine|differential|\bdlc\b|absolute/i]
  ];
  var UNIT_PATTERNS = [
    [/\bmg\s*\/\s*dl\b/i, "mg/dL"], [/\bg\s*\/\s*dl\b/i, "g/dL"], [/\bmg\s*\/\s*l\b/i, "mg/L"],
    [/\bg\s*\/\s*l\b/i, "g/L"], [/(µ|μ|\bu)mol\s*\/\s*l\b/i, "µmol/L"], [/\bmmol\s*\/\s*l\b/i, "mmol/L"],
    [/\bf\s*l\b/i, "fL"], [/\biu\s*\/\s*l\b/i, "IU/L"], [/\bu\s*\/\s*l\b/i, "U/L"],
    [/(10\s*\^?\s*3|10³|thou)\s*\/\s*(µ|μ|u|mc)l/i, "10^3/µL"], [/(10\s*\^?\s*9|10⁹)\s*\/\s*l\b/i, "10^9/L"],
    [/\/\s*(cumm|cu\.?\s*mm|mm3|mm³|µl|μl|ul)\b/i, "cells/cumm"], [/%/, "%"]
  ];
  var NUMBER = /(^|[^\d.])([<>]\s*)?(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)/;

  function plausibleUnits(marker, value) {
    return UNIT_OPTIONS[marker].filter(function (u) {
      try { toCanonical(marker, value, u); return true; } catch (e) { return false; }
    });
  }

  // One line of a report, e.g. "Albumin  4.3  g/dL  3.5 - 5.2".
  function parseLine(line) {
    var hits = [];
    REPORT_NAMES.forEach(function (spec) {
      var m = spec[1].exec(line);
      if (!m || (spec[2] && spec[2].test(line))) return;
      var rest = line.slice(m.index + m[0].length);
      var n = NUMBER.exec(rest);
      if (!n) return;
      var value = Number(n[3].replace(/,/g, ""));
      var after = rest.slice(n.index + n[0].length);
      var unit = null;
      for (var i = 0; i < UNIT_PATTERNS.length; i++) {
        if (UNIT_PATTERNS[i][0].test(after)) { unit = UNIT_PATTERNS[i][1]; break; }
      }
      var guessed = false, ok = plausibleUnits(spec[0], value);
      if (unit === null) {
        // No unit on the line: take the first unit that gives a plausible value.
        if (!ok.length) return;
        unit = ok[0]; guessed = true;
      } else if (ok.indexOf(unit) < 0) {
        // A unit that does not fit this marker (e.g. an absolute count) or an
        // implausible value: skip the line rather than guess.
        return;
      }
      hits.push({ marker: spec[0], value: value, unit: unit, guessed: guessed,
        belowLimit: !!(n[2] && n[2].trim() === "<"), fasting: /fasting|\bfbs\b|\bfbg\b|\bfpg\b/i.test(line),
        line: line.trim() });
    });
    // A line names one test; if several matched (e.g. "WBC" inside a heading), keep the earliest name.
    return hits.length ? hits.sort(function (a, b) {
      return line.search(nameRe(a.marker)) - line.search(nameRe(b.marker));
    })[0] : null;
  }
  function nameRe(marker) {
    for (var i = 0; i < REPORT_NAMES.length; i++) if (REPORT_NAMES[i][0] === marker) return REPORT_NAMES[i][1];
  }

  // Whole report text -> {found: {marker: hit}, missing: [markers]}
  function parseReportText(text) {
    var found = {};
    String(text).split(/\r?\n/).forEach(function (line) {
      var hit = parseLine(line);
      if (!hit) return;
      var prev = found[hit.marker];
      // First result wins, except a fasting glucose replaces a non-fasting one.
      if (!prev || (hit.marker === "glucose" && hit.fasting && !prev.fasting)) found[hit.marker] = hit;
    });
    return { found: found, missing: MARKERS.filter(function (m) { return !(m in found); }),
      patient: parsePatient(String(text)) };
  }

  // "Age/Sex: 42 Y / M", "Age: 42 Years  Sex: Female", "42Y/F"
  function parsePatient(text) {
    var out = {}, m;
    if ((m = /\bage\s*(?:\/\s*(?:sex|gender))?\s*[:\-]?\s*(\d{1,3})(?:\.\d+)?\s*(?:y\b|yr|yrs|years?)/i.exec(text)) ||
        (m = /\b(\d{1,3})\s*(?:y|yrs?|years?)\s*\/\s*[mf]\b/i.exec(text))) {
      var a = Number(m[1]);
      if (a >= 18 && a <= 100) out.age = a;
    }
    if ((m = /\b(?:sex|gender)\s*[:\-]\s*(male|female|m|f)\b/i.exec(text)) ||
        (m = /\d\s*(?:y|yrs?|years?)\s*\/\s*(male|female|m|f)\b/i.exec(text))) {
      out.sex = /^m/i.test(m[1]) ? "male" : "female";
    }
    return out;
  }

  function parseCsv(text) {
    var rows = [], row = [], cell = "", q = false, s = String(text).replace(/^﻿/, "");
    var delim = (s.split("\n")[0].indexOf(",") < 0 && s.indexOf("\t") >= 0) ? "\t" : ",";
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (q) {
        if (ch === '"' && s[i + 1] === '"') { cell += '"'; i++; }
        else if (ch === '"') q = false;
        else cell += ch;
      } else if (ch === '"') q = true;
      else if (ch === delim) { row.push(cell); cell = ""; }
      else if (ch === "\n" || ch === "\r") {
        if (ch === "\r" && s[i + 1] === "\n") i++;
        row.push(cell); cell = "";
        if (row.some(function (c) { return c.trim() !== ""; })) rows.push(row);
        row = [];
      } else cell += ch;
    }
    row.push(cell);
    if (row.some(function (c) { return c.trim() !== ""; })) rows.push(row);
    return rows;
  }

  function parseDate(text) {
    var t = String(text).trim(), m;
    if ((m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(t))) return Date.UTC(+m[1], m[2] - 1, +m[3]);
    if ((m = /^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})/.exec(t))) return Date.UTC(+m[3], m[2] - 1, +m[1]);  // day first
    return null;
  }
  function isoDate(ms) { return new Date(ms).toISOString().slice(0, 10); }

  // Blood CSV: the dashboard's history layout ("albumin (g/dL)" columns, newest
  // row used) or any list of test, value, unit rows.
  function bloodFromCsv(text) {
    var rows = parseCsv(text);
    if (!rows.length) throw new Error("The file is empty.");
    var head = rows[0].map(function (h) { return h.trim(); });
    var dateCol = head.findIndex(function (h) { return /^date$/i.test(h); });
    var cols = {};
    head.forEach(function (h, i) {
      var m = /^([a-z_]+)\s*\(([^)]+)\)$/i.exec(h);
      if (m && MARKERS.indexOf(m[1].toLowerCase()) >= 0) cols[m[1].toLowerCase()] = { i: i, unit: m[2].trim() };
    });
    if (dateCol >= 0 && Object.keys(cols).length) {
      var best = null;
      rows.slice(1).forEach(function (r) {
        var d = parseDate(r[dateCol] || "");
        if (d !== null && (best === null || d > best.d)) best = { d: d, r: r };
      });
      if (!best) throw new Error("No dated rows found.");
      var found = {};
      Object.keys(cols).forEach(function (mk) {
        var t = (best.r[cols[mk].i] || "").trim();
        if (!t) return;
        var unit = cols[mk].unit, value = Number(t.replace(/,/g, ""));
        var options = UNIT_OPTIONS[mk].map(normalise);
        var k = options.indexOf(normalise(unit));
        found[mk] = { marker: mk, value: value, unit: k >= 0 ? UNIT_OPTIONS[mk][k] : unit, guessed: false,
          line: head[cols[mk].i] + " = " + t };
      });
      return { found: found, missing: MARKERS.filter(function (m) { return !(m in found); }), date: isoDate(best.d) };
    }
    return parseReportText(rows.map(function (r) { return r.join("  "); }).join("\n"));
  }

  // ---- PDF text (pdf.js, loaded only when a PDF is picked) ----
  // pdf.js is served by this app (core/static/core/vendor/), not a CDN, so no
  // other website learns that someone opened a report. The page's script tag
  // gives the two file addresses in data-pdfjs and data-pdfjs-worker.
  var pdfReady = null;
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src; s.onload = resolve;
      s.onerror = function () { reject(new Error("Could not load the PDF reader. Reload the page, or type the values in.")); };
      document.head.appendChild(s);
    });
  }
  var THIS_SCRIPT = document.currentScript;
  function pdfLib() {
    if (!pdfReady) pdfReady = loadScript(THIS_SCRIPT.dataset.pdfjs).then(function () {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = THIS_SCRIPT.dataset.pdfjsWorker;
      return window.pdfjsLib;
    });
    return pdfReady;
  }
  function pdfToText(buffer) {
    return pdfLib().then(function (lib) {
      return lib.getDocument({ data: new Uint8Array(buffer), isEvalSupported: false }).promise;
    }).then(function (doc) {
      var pages = [];
      for (var i = 1; i <= doc.numPages; i++) pages.push(doc.getPage(i).then(function (p) { return p.getTextContent(); }));
      return Promise.all(pages);
    }).then(function (contents) {
      // Rebuild lines: group text pieces that share a baseline, left to right.
      var lines = [];
      contents.forEach(function (c) {
        var rows = [];
        c.items.forEach(function (it) {
          if (!it.str || !it.str.trim()) return;
          var y = it.transform[5], x = it.transform[4];
          var row = rows.find(function (r) { return Math.abs(r.y - y) < 3; });
          if (!row) { row = { y: y, parts: [] }; rows.push(row); }
          row.parts.push({ x: x, s: it.str });
        });
        rows.sort(function (a, b) { return b.y - a.y; });
        rows.forEach(function (r) {
          r.parts.sort(function (a, b) { return a.x - b.x; });
          lines.push(r.parts.map(function (p) { return p.s; }).join("  "));
        });
      });
      return lines.join("\n");
    });
  }

  // ---- Fill the Add report form ----
  function $(id) { return document.getElementById(id); }

  function setUnit(select, unit) {
    var want = normalise(unit);
    for (var i = 0; i < select.options.length; i++) {
      if (normalise(select.options[i].value) === want) { select.selectedIndex = i; return true; }
    }
    return false;
  }

  function showStatus(title, items, isError) {
    var box = $("import-result");
    box.hidden = false;
    box.classList.toggle("error", !!isError);
    $("import-summary").textContent = title;
    var ul = $("import-list");
    ul.textContent = "";
    (items || []).forEach(function (t) {
      var li = document.createElement("li");
      li.textContent = t;
      ul.appendChild(li);
    });
  }

  function apply(result) {
    var notes = [];
    MARKERS.forEach(function (m) {
      var hit = result.found[m];
      var input = $("id_v_" + m), select = $("id_u_" + m);
      input.classList.remove("imported");
      if (!hit) return;
      input.value = hit.value;
      input.classList.add("imported");
      if (!setUnit(select, hit.unit)) notes.push(m + ": unit " + hit.unit + " is not on the list; please pick it.");
      if (hit.guessed) notes.push(m + ": no unit printed, assumed " + hit.unit + ". Please check.");
      if (hit.belowLimit) notes.push(m + ": the report says below " + hit.value + "; the limit was used.");
    });
    if (result.patient && result.patient.age && !$("id_age").value) $("id_age").value = result.patient.age;
    if (result.date && !$("id_test_date").value) $("id_test_date").value = result.date;
    if (result.found.glucose && result.found.glucose.fasting) $("id_fasting").value = "yes";
    var n = MARKERS.length - result.missing.length;
    if (result.missing.length) notes.push("Not found: " + result.missing.join(", ") + ". Type these in if they are on your report.");
    notes.push("Check every value against your report before you continue.");
    showStatus("Found " + n + " of 9 markers.", notes, n === 0);
  }

  function readFile(file) {
    if (!file) return;
    showStatus("Reading " + file.name + " on this phone...", []);
    var isPdf = /\.pdf$/i.test(file.name) || file.type === "application/pdf";
    var reader = new FileReader();
    reader.onerror = function () { showStatus("Could not open the file.", [], true); };
    reader.onload = function () {
      var work = isPdf ? pdfToText(reader.result).then(parseReportText)
                       : Promise.resolve(bloodFromCsv(reader.result));
      work.then(apply).catch(function (e) {
        showStatus("Could not read this file.", [e.message || String(e),
          "Scanned photos of reports cannot be read. Please type the values in."], true);
      });
    };
    if (isPdf) reader.readAsArrayBuffer(file); else reader.readAsText(file);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var picker = $("report-file");
    if (picker) picker.addEventListener("change", function () { readFile(picker.files[0]); });
  });

  // Exposed for tests in the browser console.
  window.VitalAgeReader = { parseReportText: parseReportText, bloodFromCsv: bloodFromCsv };
})();
