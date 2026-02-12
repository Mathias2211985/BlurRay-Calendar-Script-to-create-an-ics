"""
BluRay Calendar Scraper - Web UI
Startet einen lokalen Flask-Webserver mit einer modernen Oberfläche
zum Konfigurieren und Starten des Scrapers.
"""

import json
import os
import sys
import threading
import uuid
import queue
import logging
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template_string, request, jsonify, Response, send_from_directory

app = Flask(__name__)

# Directory where this script lives (and where scraper.py / output files are)
# When running as PyInstaller bundle, bundled data files are in sys._MEIPASS,
# but we want config and output files next to the .exe (sys.executable's dir).
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BUNDLE_DIR = Path(sys._MEIPASS)  # bundled scraper.py lives here
    BASE_DIR = Path(sys.executable).resolve().parent  # config + output go here
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    BASE_DIR = BUNDLE_DIR

CONFIG_PATH = BASE_DIR / "config.json"

# Active jobs: job_id -> { "queue": Queue, "status": "running"|"done"|"error", "output_file": str }
jobs = {}

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "calendar_years": str(datetime.now().year),
    "months": "",
    "categories": "4k-uhd",
    "release_years": "",
    "production_years": "",
    "ignore_production": True,
    "output_pattern": "bluray_{year}_{months}.ics",
}

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # migrate old "category" key to "categories"
            if "category" in saved and "categories" not in saved:
                saved["categories"] = saved.pop("category")
            merged = {**DEFAULT_CONFIG, **saved}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORIES = {
    "4k-uhd": "4K UHD",
    "blu-ray-filme": "Blu-ray Filme",
    "3d-blu-ray-filme": "3D Blu-ray",
    "serien": "Serien",
    "blu-ray-importe": "Importe",
}

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BluRay Calendar Scraper</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #232733;
    --border: #2e3345;
    --text: #e4e6ed;
    --text-muted: #8b8fa3;
    --accent: #4f8cff;
    --accent-hover: #6ba0ff;
    --accent-dim: rgba(79,140,255,0.15);
    --success: #34d399;
    --error: #f87171;
    --warn: #fbbf24;
    --radius: 10px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  header {
    width: 100%;
    padding: 28px 0 18px;
    text-align: center;
    background: linear-gradient(180deg, #161926 0%, var(--bg) 100%);
    border-bottom: 1px solid var(--border);
  }
  header h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }
  header h1 span { color: var(--accent); }
  header p { color: var(--text-muted); font-size: 0.88rem; margin-top: 4px; }
  .container {
    width: 100%; max-width: 1280px; padding: 28px 20px 40px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    align-items: start;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
  }
  .card-title {
    font-size: 0.82rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 18px;
  }
  .form-row {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 16px; margin-bottom: 16px;
  }
  .form-group { display: flex; flex-direction: column; gap: 6px; }
  .form-group.full { grid-column: 1 / -1; }
  label { font-size: 0.82rem; font-weight: 500; color: var(--text-muted); }
  input[type="text"] {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 6px; padding: 9px 12px; color: var(--text);
    font-size: 0.92rem; outline: none; transition: border-color 0.15s;
  }
  input[type="text"]:focus {
    border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim);
  }
  .toggle-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
  .toggle { position: relative; width: 44px; height: 24px; cursor: pointer; }
  .toggle input { display: none; }
  .toggle .slider {
    position: absolute; inset: 0; background: var(--surface2);
    border: 1px solid var(--border); border-radius: 12px; transition: background 0.2s;
  }
  .toggle .slider::after {
    content: ''; position: absolute; top: 3px; left: 3px;
    width: 16px; height: 16px; border-radius: 50%;
    background: var(--text-muted); transition: transform 0.2s, background 0.2s;
  }
  .toggle input:checked + .slider { background: var(--accent); border-color: var(--accent); }
  .toggle input:checked + .slider::after { transform: translateX(20px); background: #fff; }

  /* Chip grid (shared by months, categories, years) */
  .chip-grid {
    display: flex; flex-wrap: wrap; gap: 6px;
  }
  .chip {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 14px; color: var(--text-muted);
    font-size: 0.8rem; cursor: pointer; text-align: center;
    transition: all 0.15s; user-select: none; white-space: nowrap;
  }
  .chip.active {
    background: var(--accent-dim); border-color: var(--accent);
    color: var(--accent); font-weight: 600;
  }
  .chip:hover { border-color: var(--accent); }

  .months-grid {
    display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px;
  }
  .cat-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
  }
  /* Multi-select year dropdown */
  .multi-select { position: relative; }
  .multi-select-btn {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 6px; padding: 9px 12px; color: var(--text);
    font-size: 0.92rem; cursor: pointer; width: 100%;
    display: flex; align-items: center; justify-content: space-between;
    transition: border-color 0.15s; user-select: none;
  }
  .multi-select-btn:hover, .multi-select.open .multi-select-btn {
    border-color: var(--accent);
  }
  .multi-select-btn .arrow {
    font-size: 0.6rem; color: var(--text-muted); transition: transform 0.2s;
  }
  .multi-select.open .arrow { transform: rotate(180deg); }
  .multi-select-btn .sel-text {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;
  }
  .multi-select-dropdown {
    display: none; position: absolute; top: calc(100% + 4px); left: 0; right: 0;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; z-index: 100; max-height: 260px;
    overflow-y: auto; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .multi-select.open .multi-select-dropdown { display: block; }
  .ms-search {
    width: 100%; padding: 8px 12px; background: var(--surface2);
    border: none; border-bottom: 1px solid var(--border);
    color: var(--text); font-size: 0.85rem; outline: none;
    border-radius: 8px 8px 0 0;
  }
  .ms-option {
    display: flex; align-items: center; gap: 10px;
    padding: 7px 12px; cursor: pointer; font-size: 0.85rem;
    color: var(--text-muted); transition: background 0.1s;
  }
  .ms-option:hover { background: var(--surface2); }
  .ms-option.checked { color: var(--accent); font-weight: 600; }
  .ms-check {
    width: 16px; height: 16px; border: 1.5px solid var(--border);
    border-radius: 4px; display: flex; align-items: center;
    justify-content: center; flex-shrink: 0; transition: all 0.15s;
  }
  .ms-option.checked .ms-check {
    background: var(--accent); border-color: var(--accent);
  }
  .ms-option.checked .ms-check::after {
    content: ''; width: 8px; height: 5px;
    border-left: 2px solid #fff; border-bottom: 2px solid #fff;
    transform: rotate(-45deg); margin-top: -2px;
  }
  .ms-option.hidden { display: none; }

  .btn-row { display: flex; gap: 10px; margin-top: 6px; }
  .btn {
    flex: 1; padding: 12px 20px; border: none; border-radius: 8px;
    font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.15s;
  }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent-hover); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary {
    background: var(--surface2); color: var(--text);
    border: 1px solid var(--border); flex: 0 0 auto;
  }
  .btn-secondary:hover { border-color: var(--accent); }

  .log-card { position: sticky; top: 20px; }
  .log-header {
    display: flex; align-items: center;
    justify-content: space-between; margin-bottom: 12px;
  }
  .status-badge {
    font-size: 0.78rem; font-weight: 600; padding: 3px 10px; border-radius: 20px;
  }
  .status-running { background: var(--accent-dim); color: var(--accent); }
  .status-done { background: rgba(52,211,153,0.15); color: var(--success); }
  .status-error { background: rgba(248,113,113,0.15); color: var(--error); }

  .progress-bar-container {
    width: 100%; height: 4px; background: var(--surface2);
    border-radius: 2px; margin-bottom: 14px; overflow: hidden;
  }
  .progress-bar {
    height: 100%; background: var(--accent); border-radius: 2px;
    width: 0%; transition: width 0.3s;
  }
  .log-output {
    background: #0d0f14; border: 1px solid var(--border); border-radius: 8px;
    padding: 14px; font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 0.78rem; line-height: 1.6; min-height: 300px; max-height: 520px;
    overflow-y: auto; white-space: pre-wrap; word-break: break-word;
    color: var(--text-muted);
  }
  .log-output .log-info { color: var(--accent); }
  .log-output .log-warn { color: var(--warn); }
  .log-output .log-error { color: var(--error); }
  .log-output .log-success { color: var(--success); }

  .download-row { display: none; margin-top: 14px; gap: 10px; flex-wrap: wrap; }
  .download-row.visible { display: flex; }
  .download-btn {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(52,211,153,0.12); color: var(--success);
    border: 1px solid rgba(52,211,153,0.3); border-radius: 8px;
    padding: 10px 20px; font-size: 0.88rem; font-weight: 600;
    cursor: pointer; text-decoration: none; transition: all 0.15s;
  }
  .download-btn:hover { background: rgba(52,211,153,0.2); }

  .section-label {
    font-size: 0.82rem; font-weight: 500; color: var(--text-muted);
    margin-bottom: 6px;
  }
  .section { margin-bottom: 16px; }

  @media (max-width: 900px) {
    .container { grid-template-columns: 1fr; max-width: 720px; }
    .log-card { position: static; }
  }
  @media (max-width: 560px) {
    .form-row { grid-template-columns: 1fr; }
    .months-grid { grid-template-columns: repeat(4, 1fr); }
    .cat-grid { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>

<header>
  <h1><span>BluRay</span> Calendar Scraper</h1>
  <p>Blu-Ray Neuerscheinungen als ICS-Kalender exportieren</p>
</header>

<div class="container">

  <div class="card">
    <div class="card-title">Einstellungen</div>

    <!-- Kalender-Jahre -->
    <div class="section">
      <div class="section-label">Kalender-Jahr(e)</div>
      <div class="multi-select" id="ms-calendar-years">
        <div class="multi-select-btn" onclick="toggleDropdown('ms-calendar-years')">
          <span class="sel-text">Auswählen...</span>
          <span class="arrow">&#9660;</span>
        </div>
        <div class="multi-select-dropdown">
          <input class="ms-search" type="text" placeholder="Suchen..." oninput="filterOptions(this)">
          {% for y in year_range %}
          <div class="ms-option" data-val="{{ y }}" onclick="toggleOption(this)">
            <div class="ms-check"></div>{{ y }}
          </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Kategorien -->
    <div class="section">
      <div class="section-label">Kategorie(n) <span style="font-weight:400;color:var(--text-muted)">(Mehrfachauswahl)</span></div>
      <div class="chip-grid cat-grid" id="categories-grid">
        {% for val, label in categories.items() %}
        <div class="chip cat-chip" data-val="{{ val }}">{{ label }}</div>
        {% endfor %}
      </div>
    </div>

    <!-- Monate -->
    <div class="section">
      <div class="section-label">Monate <span style="font-weight:400;color:var(--text-muted)">(leer = alle)</span></div>
      <div class="chip-grid months-grid" id="months-grid">
        <div class="chip month-chip" data-val="01">Jan</div>
        <div class="chip month-chip" data-val="02">Feb</div>
        <div class="chip month-chip" data-val="03">Mar</div>
        <div class="chip month-chip" data-val="04">Apr</div>
        <div class="chip month-chip" data-val="05">Mai</div>
        <div class="chip month-chip" data-val="06">Jun</div>
        <div class="chip month-chip" data-val="07">Jul</div>
        <div class="chip month-chip" data-val="08">Aug</div>
        <div class="chip month-chip" data-val="09">Sep</div>
        <div class="chip month-chip" data-val="10">Okt</div>
        <div class="chip month-chip" data-val="11">Nov</div>
        <div class="chip month-chip" data-val="12">Dez</div>
      </div>
    </div>

    <!-- Release-Jahre -->
    <div class="section">
      <div class="section-label">Release-Jahr(e) <span style="font-weight:400;color:var(--text-muted)">(leer = alle)</span></div>
      <div class="multi-select" id="ms-release-years">
        <div class="multi-select-btn" onclick="toggleDropdown('ms-release-years')">
          <span class="sel-text">Alle</span>
          <span class="arrow">&#9660;</span>
        </div>
        <div class="multi-select-dropdown">
          <input class="ms-search" type="text" placeholder="Suchen..." oninput="filterOptions(this)">
          {% for y in year_range %}
          <div class="ms-option" data-val="{{ y }}" onclick="toggleOption(this)">
            <div class="ms-check"></div>{{ y }}
          </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Produktionsjahr-Filter -->
    <div class="toggle-row">
      <label class="toggle">
        <input type="checkbox" id="use_production" {% if not config.ignore_production %}checked{% endif %} onchange="toggleProductionSection()">
        <div class="slider"></div>
      </label>
      <label for="use_production" style="cursor:pointer">Nach Produktionsjahr filtern</label>
    </div>

    <!-- Produktions-Jahre (nur sichtbar wenn Toggle aktiv) -->
    <div class="section" id="production-section" style="display:none">
      <div class="section-label">Produktions-Jahr(e) <span style="font-weight:400;color:var(--text-muted)">(leer = wie Release)</span></div>
      <div class="multi-select" id="ms-production-years">
        <div class="multi-select-btn" onclick="toggleDropdown('ms-production-years')">
          <span class="sel-text">Wie Release</span>
          <span class="arrow">&#9660;</span>
        </div>
        <div class="multi-select-dropdown">
          <input class="ms-search" type="text" placeholder="Suchen..." oninput="filterOptions(this)">
          {% for y in year_range %}
          <div class="ms-option" data-val="{{ y }}" onclick="toggleOption(this)">
            <div class="ms-check"></div>{{ y }}
          </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Ausgabedatei -->
    <div class="form-group" style="margin-bottom:20px">
      <label for="output_pattern">Ausgabedatei</label>
      <input type="text" id="output_pattern" value="{{ config.output_pattern }}" placeholder="bluray_{year}_{months}.ics">
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" id="btn-start" onclick="startScraping()">Scraping starten</button>
      <button class="btn btn-secondary" onclick="saveConfig()">Speichern</button>
    </div>
  </div>

  <!-- Log Card (rechte Spalte) -->
  <div class="card log-card" id="log-card">
    <div class="log-header">
      <div class="card-title" style="margin:0">Live-Log</div>
      <span class="status-badge" id="status-badge" style="display:none">Bereit</span>
    </div>
    <div class="progress-bar-container">
      <div class="progress-bar" id="progress-bar"></div>
    </div>
    <div class="log-output" id="log-output"><span class="log-info">Bereit. Wähle Einstellungen und klicke "Scraping starten".</span>
</div>
    <div class="download-row" id="download-row"></div>
  </div>

</div>

<script>
// ---- Multi-select dropdown logic ----
function toggleDropdown(id) {
  const el = document.getElementById(id);
  const wasOpen = el.classList.contains("open");
  // close all dropdowns first
  document.querySelectorAll(".multi-select.open").forEach(ms => ms.classList.remove("open"));
  if (!wasOpen) {
    el.classList.add("open");
    const search = el.querySelector(".ms-search");
    if (search) { search.value = ""; filterOptions(search); search.focus(); }
  }
}

function toggleOption(opt) {
  opt.classList.toggle("checked");
  updateDropdownLabel(opt.closest(".multi-select"));
}

function filterOptions(input) {
  const q = input.value.toLowerCase();
  input.closest(".multi-select-dropdown").querySelectorAll(".ms-option").forEach(o => {
    o.classList.toggle("hidden", !o.dataset.val.includes(q));
  });
}

function updateDropdownLabel(ms) {
  const checked = ms.querySelectorAll(".ms-option.checked");
  const btn = ms.querySelector(".sel-text");
  if (checked.length === 0) {
    const id = ms.id;
    if (id === "ms-release-years") btn.textContent = "Alle";
    else if (id === "ms-production-years") btn.textContent = "Wie Release";
    else btn.textContent = "Auswählen...";
  } else if (checked.length <= 4) {
    btn.textContent = Array.from(checked).map(o => o.dataset.val).join(", ");
  } else {
    btn.textContent = checked.length + " ausgewählt";
  }
}

function getDropdownValues(msId) {
  return Array.from(document.querySelectorAll("#" + msId + " .ms-option.checked"))
    .map(o => o.dataset.val).join(",");
}

function setDropdownValues(msId, csv) {
  if (!csv) return;
  csv.split(",").forEach(v => {
    v = v.trim();
    const opt = document.querySelector("#" + msId + ` .ms-option[data-val="${v}"]`);
    if (opt) opt.classList.add("checked");
  });
  const ms = document.getElementById(msId);
  if (ms) updateDropdownLabel(ms);
}

// Close dropdowns when clicking outside
document.addEventListener("click", function(e) {
  if (!e.target.closest(".multi-select")) {
    document.querySelectorAll(".multi-select.open").forEach(ms => ms.classList.remove("open"));
  }
});

// ---- Init selections from saved config ----
(function() {
  const savedCats = "{{ config.categories }}";
  const savedMonths = "{{ config.months }}";

  function activateChips(containerSel, csvString) {
    if (!csvString) return;
    csvString.split(",").forEach(v => {
      v = v.trim();
      const chip = document.querySelector(containerSel + ` .chip[data-val="${v}"]`);
      if (chip) chip.classList.add("active");
    });
  }

  activateChips("#categories-grid", savedCats);
  activateChips("#months-grid", savedMonths);

  // click handler for chips (categories + months only)
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => chip.classList.toggle("active"));
  });

  // init year dropdowns from config
  setDropdownValues("ms-calendar-years", "{{ config.calendar_years }}");
  setDropdownValues("ms-release-years", "{{ config.release_years }}");
  setDropdownValues("ms-production-years", "{{ config.production_years }}");

  // init production section visibility
  toggleProductionSection();
})();

function toggleProductionSection() {
  const on = document.getElementById("use_production").checked;
  document.getElementById("production-section").style.display = on ? "block" : "none";
}

function getActiveValues(containerId) {
  return Array.from(document.querySelectorAll("#" + containerId + " .chip.active"))
    .map(c => c.dataset.val).join(",");
}

function getFormData() {
  return {
    calendar_years: getDropdownValues("ms-calendar-years"),
    months: getActiveValues("months-grid"),
    categories: getActiveValues("categories-grid"),
    release_years: getDropdownValues("ms-release-years"),
    production_years: getDropdownValues("ms-production-years"),
    ignore_production: !document.getElementById("use_production").checked,
    output_pattern: document.getElementById("output_pattern").value.trim() || "bluray_{year}_{months}.ics",
  };
}

function saveConfig() {
  fetch("/save-config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(getFormData()),
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      const btn = document.querySelector(".btn-secondary");
      const orig = btn.textContent;
      btn.textContent = "Gespeichert!";
      setTimeout(() => btn.textContent = orig, 1500);
    }
  });
}

function startScraping() {
  const data = getFormData();
  if (!data.calendar_years) {
    alert("Bitte mindestens ein Kalender-Jahr auswählen!");
    return;
  }
  if (!data.categories) {
    alert("Bitte mindestens eine Kategorie auswählen!");
    return;
  }
  const btn = document.getElementById("btn-start");
  btn.disabled = true;
  btn.textContent = "Läuft...";

  const logCard = document.getElementById("log-card");
  const logOutput = document.getElementById("log-output");
  const progressBar = document.getElementById("progress-bar");
  const badge = document.getElementById("status-badge");
  const dlRow = document.getElementById("download-row");

  logOutput.innerHTML = "";
  progressBar.style.width = "0%";
  badge.style.display = "";
  badge.className = "status-badge status-running";
  badge.textContent = "Läuft...";
  dlRow.classList.remove("visible");
  dlRow.innerHTML = "";

  fetch("/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  }).then(r => r.json()).then(d => {
    if (!d.job_id) {
      appendLog("Fehler beim Starten: " + (d.error || "unbekannt"), "error");
      btn.disabled = false;
      btn.textContent = "Scraping starten";
      return;
    }
    const es = new EventSource("/stream/" + d.job_id);
    es.onmessage = function(ev) {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") {
        appendLog(msg.text, msg.level || "info");
      } else if (msg.type === "progress") {
        progressBar.style.width = msg.percent + "%";
      } else if (msg.type === "done") {
        es.close();
        badge.className = "status-badge status-done";
        badge.textContent = "Fertig";
        progressBar.style.width = "100%";
        btn.disabled = false;
        btn.textContent = "Scraping starten";
        if (msg.files && msg.files.length > 0) {
          msg.files.forEach(f => {
            const a = document.createElement("a");
            a.className = "download-btn";
            a.href = "/download/" + encodeURIComponent(f);
            a.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> ' + f;
            dlRow.appendChild(a);
          });
          dlRow.classList.add("visible");
        }
      } else if (msg.type === "error") {
        es.close();
        badge.className = "status-badge status-error";
        badge.textContent = "Fehler";
        btn.disabled = false;
        btn.textContent = "Scraping starten";
        appendLog(msg.text || "Unbekannter Fehler", "error");
      }
    };
    es.onerror = function() {
      es.close();
      badge.className = "status-badge status-error";
      badge.textContent = "Verbindung verloren";
      btn.disabled = false;
      btn.textContent = "Scraping starten";
    };
  }).catch(err => {
    appendLog("Netzwerkfehler: " + err, "error");
    btn.disabled = false;
    btn.textContent = "Scraping starten";
  });
}

function appendLog(text, level) {
  const el = document.getElementById("log-output");
  const span = document.createElement("span");
  span.className = "log-" + (level || "info");
  span.textContent = text + "\n";
  el.appendChild(span);
  el.scrollTop = el.scrollHeight;
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    cfg = load_config()
    current_year = datetime.now().year
    year_range = list(range(2028, 1949, -1))  # 2028 down to 1950, newest first
    return render_template_string(
        HTML_TEMPLATE,
        config=cfg,
        categories=CATEGORIES,
        current_year=str(current_year),
        year_range=year_range,
    )

@app.route("/save-config", methods=["POST"])
def save_config_route():
    data = request.get_json(force=True)
    save_config(data)
    return jsonify({"ok": True})

@app.route("/start", methods=["POST"])
def start_scraping():
    data = request.get_json(force=True)
    save_config(data)

    job_id = str(uuid.uuid4())[:8]
    q = queue.Queue()
    jobs[job_id] = {"queue": q, "status": "running", "output_file": None}

    t = threading.Thread(target=run_scraper, args=(job_id, data), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})

@app.route("/stream/<job_id>")
def stream(job_id):
    job = jobs.get(job_id)
    if not job:
        return "Job not found", 404

    def generate():
        while True:
            try:
                msg = job["queue"].get(timeout=30)
            except queue.Empty:
                yield "data: {}\n\n"
                continue
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            if msg.get("type") in ("done", "error"):
                break

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/download/<path:filename>")
def download(filename):
    safe_name = Path(filename).name
    if not safe_name.endswith(".ics"):
        return "Nur .ics Dateien erlaubt", 403
    return send_from_directory(str(BASE_DIR), safe_name, as_attachment=True)

# ---------------------------------------------------------------------------
# Scraper runner (in background thread)
# ---------------------------------------------------------------------------

def run_scraper(job_id, data):
    job = jobs[job_id]
    q = job["queue"]

    try:
        calendar_years = data.get("calendar_years", str(datetime.now().year))
        months = data.get("months", "")
        categories_csv = data.get("categories", "4k-uhd")
        release_years = data.get("release_years", "")
        production_years = data.get("production_years", "")
        ignore_production = data.get("ignore_production", True)
        output_pattern = data.get("output_pattern", "bluray_{year}_{months}.ics")

        year_list = [y.strip() for y in calendar_years.split(",") if y.strip()]
        if not year_list:
            year_list = [str(datetime.now().year)]

        cat_list = [c.strip() for c in categories_csv.split(",") if c.strip()]
        if not cat_list:
            cat_list = ["4k-uhd"]

        total_steps = len(year_list) * len(cat_list)
        step = 0
        output_files = []

        for y in year_list:
            for cat in cat_list:
                tpl_url = f"https://bluray-disc.de/{cat}/kalender?id={{year}}-{{month:02d}}"
                prod_arg = production_years if production_years else (release_years if release_years else y)

                months_token = months.replace(",", "-") if months else "all"
                release_slug = release_years.replace(",", "-") if release_years else "ALL"

                out_name = output_pattern
                out_name = out_name.replace("{year}", y)
                out_name = out_name.replace("{months}", months_token)
                out_name = out_name.replace("{release_years}", release_slug)
                out_name = out_name.replace("{slug}", cat)
                if not out_name.endswith(".ics"):
                    out_name += ".ics"

                # Append disambiguating parts if not in pattern
                base, ext = os.path.splitext(out_name)
                append_parts = []
                if "{slug}" not in output_pattern:
                    append_parts.append(cat)
                if "{release_years}" not in output_pattern and release_years:
                    append_parts.append(release_slug)
                if append_parts:
                    out_name = f"{base}_{'_'.join(append_parts)}{ext}"

                cat_label = CATEGORIES.get(cat, cat)
                cmd = [sys.executable, "-u", str(BUNDLE_DIR / "scraper.py")]
                cmd += ["--year", prod_arg]
                cmd += ["--calendar-year", y]
                cmd += ["--calendar-template", tpl_url]
                if months:
                    cmd += ["--months", months]
                if release_years:
                    cmd += ["--release-years", release_years]
                if ignore_production:
                    cmd += ["--ignore-production"]
                cmd += ["--category", cat]
                cmd += ["--out", out_name]

                q.put({"type": "log", "text": f"--- Starte: Jahr {y}, Kategorie: {cat_label} ---", "level": "info"})
                q.put({"type": "log", "text": f"Ausgabedatei: {out_name}", "level": "info"})

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(BASE_DIR),
                )

                for line in proc.stdout:
                    line = line.rstrip("\n\r")
                    if not line:
                        continue
                    level = "info"
                    if "WARNING" in line or "Fehler" in line:
                        level = "warn"
                    elif "ERROR" in line:
                        level = "error"
                    elif "Fertig." in line or "Added event" in line:
                        level = "success"
                    q.put({"type": "log", "text": line, "level": level})

                proc.wait()
                step += 1
                percent = int((step / total_steps) * 100)
                q.put({"type": "progress", "percent": percent})

                if proc.returncode != 0:
                    q.put({"type": "log", "text": f"Scraper beendet mit Exit-Code {proc.returncode}", "level": "error"})

                output_files.append(out_name)

        job["status"] = "done"
        job["output_file"] = output_files[-1] if output_files else None
        q.put({"type": "log", "text": f"Alle Aufgaben abgeschlossen! ({len(output_files)} Datei(en) erzeugt)", "level": "success"})
        q.put({"type": "done", "files": output_files})

    except Exception as e:
        job["status"] = "error"
        q.put({"type": "log", "text": f"Fehler: {e}", "level": "error"})
        q.put({"type": "error", "text": str(e)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"BluRay Calendar Scraper Web-UI startet auf http://localhost:{port}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
