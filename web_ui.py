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

  /* Preview table */
  .preview-section { display: none; margin-top: 16px; }
  .preview-section.visible { display: block; }
  .preview-toolbar {
    display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;
  }
  .preview-toolbar .count { color: var(--text-muted); font-size: 0.85rem; margin-left: auto; }
  .preview-btn {
    padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px;
    background: var(--surface2); color: var(--text-muted); cursor: pointer;
    font-size: 0.78rem; font-weight: 600; transition: all 0.15s;
  }
  .preview-btn:hover { border-color: var(--accent); color: var(--accent); }
  .preview-btn.primary {
    background: var(--accent); color: #fff; border-color: var(--accent);
  }
  .preview-btn.primary:hover { background: var(--accent-hover); }
  .preview-table-wrap {
    max-height: 480px; overflow-y: auto; border: 1px solid var(--border);
    border-radius: 8px; background: #0d0f14;
  }
  .preview-table {
    width: 100%; border-collapse: collapse; font-size: 0.82rem;
  }
  .preview-table th {
    position: sticky; top: 0; background: var(--surface2);
    padding: 8px 10px; text-align: left; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted);
    border-bottom: 1px solid var(--border); z-index: 2;
  }
  .preview-table td {
    padding: 7px 10px; border-bottom: 1px solid var(--border);
    color: var(--text); vertical-align: middle;
  }
  .preview-table tr:hover td { background: rgba(79,140,255,0.05); }
  .preview-table tr.unchecked td { opacity: 0.4; }
  .preview-table input[type="checkbox"] {
    width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer;
  }
  .preview-table .col-cb { width: 36px; text-align: center; }
  .preview-table .col-date { width: 100px; white-space: nowrap; }
  .preview-table .col-year { width: 60px; text-align: center; }
  .preview-table .col-cat { width: 90px; font-size: 0.75rem; color: var(--text-muted); }
  .preview-table .title-link {
    color: var(--accent); text-decoration: none;
  }
  .preview-table .title-link:hover { text-decoration: underline; }
  .preview-table tr.duplicate td { background: rgba(251,191,36,0.07); }
  .preview-table tr.duplicate .dup-badge {
    display: inline-block; font-size: 0.65rem; font-weight: 700;
    background: rgba(251,191,36,0.18); color: var(--warn); border-radius: 4px;
    padding: 1px 6px; margin-left: 8px; vertical-align: middle;
  }
  .preview-table .dup-badge { display: none; }
  .dedup-toggle { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.78rem; color: var(--text-muted); }
  .dedup-toggle input { accent-color: var(--warn); width: 14px; height: 14px; cursor: pointer; }

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
    <div class="preview-section" id="preview-section">
      <div class="preview-toolbar">
        <button class="preview-btn" onclick="selectAllPreview(true)">Alle</button>
        <button class="preview-btn" onclick="selectAllPreview(false)">Keine</button>
        <label class="dedup-toggle"><input type="checkbox" id="dedup-toggle" onchange="toggleDedup(this.checked)"> Duplikate markieren</label>
        <span class="count" id="preview-count"></span>
        <button class="preview-btn primary" onclick="generateICS()">ICS erstellen</button>
      </div>
      <div class="preview-table-wrap">
        <table class="preview-table">
          <thead><tr>
            <th class="col-cb"><input type="checkbox" id="preview-select-all" checked onchange="selectAllPreview(this.checked)"></th>
            <th>Titel</th>
            <th class="col-date">Release</th>
            <th class="col-year">Prod.</th>
            <th class="col-cat">Kategorie</th>
          </tr></thead>
          <tbody id="preview-body"></tbody>
        </table>
      </div>
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
  const previewSection = document.getElementById("preview-section");

  logOutput.innerHTML = "";
  progressBar.style.width = "0%";
  badge.style.display = "";
  badge.className = "status-badge status-running";
  badge.textContent = "Läuft...";
  dlRow.classList.remove("visible");
  dlRow.innerHTML = "";
  previewSection.classList.remove("visible");
  window._previewItems = [];

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
      } else if (msg.type === "preview") {
        es.close();
        badge.className = "status-badge status-done";
        badge.textContent = "Vorschau";
        progressBar.style.width = "100%";
        btn.disabled = false;
        btn.textContent = "Scraping starten";
        showPreview(msg.items || []);
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

// ---- Preview table logic ----
function showPreview(items) {
  window._previewItems = items;
  const body = document.getElementById("preview-body");
  body.innerHTML = "";
  items.forEach((item, idx) => {
    const tr = document.createElement("tr");
    const dateStr = item.release_date || "—";
    const prodStr = item.production_year || "—";
    const catStr = item.category || "";
    tr.innerHTML =
      '<td class="col-cb"><input type="checkbox" checked data-idx="' + idx + '" onchange="onPreviewCheck(this)"></td>' +
      '<td><a class="title-link" href="' + (item.url || '#') + '" target="_blank" rel="noopener">' + escHtml(item.title || "Unbekannt") + '</a><span class="dup-badge">Duplikat</span></td>' +
      '<td class="col-date">' + dateStr + '</td>' +
      '<td class="col-year">' + prodStr + '</td>' +
      '<td class="col-cat">' + escHtml(catStr) + '</td>';
    body.appendChild(tr);
  });
  document.getElementById("preview-select-all").checked = true;
  updatePreviewCount();
  document.getElementById("preview-section").classList.add("visible");
}

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function onPreviewCheck(cb) {
  const tr = cb.closest("tr");
  if (cb.checked) tr.classList.remove("unchecked");
  else tr.classList.add("unchecked");
  updatePreviewCount();
}

function selectAllPreview(checked) {
  document.querySelectorAll("#preview-body input[type=checkbox]").forEach(cb => {
    cb.checked = checked;
    const tr = cb.closest("tr");
    if (checked) tr.classList.remove("unchecked");
    else tr.classList.add("unchecked");
  });
  document.getElementById("preview-select-all").checked = checked;
  updatePreviewCount();
}

function updatePreviewCount() {
  const total = document.querySelectorAll("#preview-body input[type=checkbox]").length;
  const checked = document.querySelectorAll("#preview-body input[type=checkbox]:checked").length;
  document.getElementById("preview-count").textContent = checked + " / " + total + " ausgewählt";
}

// ---- Cross-category dedup logic ----
function normalizeTitle(t) {
  if (!t) return "";
  var s = t.toLowerCase();
  // normalize German umlauts
  s = s.replace(/ä/g,'ae').replace(/ö/g,'oe').replace(/ü/g,'ue').replace(/ß/g,'ss');
  // remove parenthetical and bracketed parts
  s = s.replace(/\([^)]*\)/g, ' ').replace(/\[[^\]]*\]/g, ' ');
  // remove known edition/format tokens
  var tokens = ['limited','steelbook','mediabook','wattierte','amaray','cover','edition',
    'uhd','blu-ray','blu ray','soundtrack','cd','deluxe','collector','exclusive','special'];
  tokens.forEach(function(tok) { s = s.replace(new RegExp('\\b' + tok.replace(/[.*+?^${}()|[\]\\]/g,'\\$&') + '\\b','g'), ' '); });
  // remove numeric-k tokens
  s = s.replace(/\b\d+k\b/g, ' ');
  // normalize blu-ray variants
  s = s.replace(/\bblu[\s-]?ray\b/g, ' ');
  // remove non-alphanumeric (keep - and space)
  s = s.replace(/[^a-z0-9\-\s]/g, ' ');
  // collapse whitespace
  s = s.replace(/[-\s]+/g, ' ').trim();
  return s;
}

var CAT_PRIORITY = {"4K UHD":0, "Blu-ray Filme":1, "3D Blu-ray":2, "Serien":3, "Importe":4};

function toggleDedup(on) {
  if (on) markDuplicates();
  else clearDuplicateMarks();
}

function markDuplicates() {
  var items = window._previewItems;
  if (!items || items.length === 0) return;
  // Group by normalized title
  var groups = {};
  items.forEach(function(item, idx) {
    var key = normalizeTitle(item.title);
    if (!groups[key]) groups[key] = [];
    groups[key].push(idx);
  });
  var rows = document.querySelectorAll("#preview-body tr");
  // For each group with >1 entry, keep the best and mark the rest as duplicates
  Object.keys(groups).forEach(function(key) {
    var idxs = groups[key];
    if (idxs.length <= 1) return;
    // Find the best: lowest category priority, then earliest date
    idxs.sort(function(a, b) {
      var catA = CAT_PRIORITY[items[a].category] !== undefined ? CAT_PRIORITY[items[a].category] : 99;
      var catB = CAT_PRIORITY[items[b].category] !== undefined ? CAT_PRIORITY[items[b].category] : 99;
      if (catA !== catB) return catA - catB;
      var dA = items[a].release_date || "9999";
      var dB = items[b].release_date || "9999";
      return dA < dB ? -1 : dA > dB ? 1 : 0;
    });
    // First is best, rest are duplicates
    for (var i = 1; i < idxs.length; i++) {
      var row = rows[idxs[i]];
      if (!row) continue;
      row.classList.add("duplicate");
      var cb = row.querySelector("input[type=checkbox]");
      if (cb) { cb.checked = false; row.classList.add("unchecked"); }
    }
  });
  updatePreviewCount();
}

function clearDuplicateMarks() {
  document.querySelectorAll("#preview-body tr.duplicate").forEach(function(row) {
    row.classList.remove("duplicate");
    var cb = row.querySelector("input[type=checkbox]");
    if (cb) { cb.checked = true; row.classList.remove("unchecked"); }
  });
  updatePreviewCount();
}

function generateICS() {
  const checkboxes = document.querySelectorAll("#preview-body input[type=checkbox]:checked");
  const selected = [];
  checkboxes.forEach(cb => {
    const idx = parseInt(cb.dataset.idx, 10);
    if (window._previewItems && window._previewItems[idx]) {
      selected.push(window._previewItems[idx]);
    }
  });
  if (selected.length === 0) {
    alert("Bitte mindestens einen Eintrag auswählen!");
    return;
  }
  const outputPattern = document.getElementById("output_pattern").value.trim() || "bluray_{year}_{months}.ics";
  appendLog("Erstelle ICS mit " + selected.length + " Einträgen...", "info");

  fetch("/generate-ics", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({items: selected, output_pattern: outputPattern}),
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      appendLog("ICS erstellt: " + d.file + " (" + d.count + " Einträge)", "success");
      const badge = document.getElementById("status-badge");
      badge.className = "status-badge status-done";
      badge.textContent = "Fertig";
      const dlRow = document.getElementById("download-row");
      dlRow.innerHTML = "";
      const a = document.createElement("a");
      a.className = "download-btn";
      a.href = "/download/" + encodeURIComponent(d.file);
      a.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> ' + d.file;
      dlRow.appendChild(a);
      dlRow.classList.add("visible");
    } else {
      appendLog("Fehler: " + (d.error || "unbekannt"), "error");
    }
  }).catch(err => {
    appendLog("Netzwerkfehler: " + err, "error");
  });
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
            if msg.get("type") in ("done", "error", "preview"):
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
        all_preview_items = []

        for y in year_list:
            for cat in cat_list:
                tpl_url = f"https://bluray-disc.de/{cat}/kalender?id={{year}}-{{month:02d}}"
                prod_arg = production_years if production_years else (release_years if release_years else y)

                cat_label = CATEGORIES.get(cat, cat)
                if getattr(sys, 'frozen', False):
                    # Frozen exe: call ourselves with --run-scraper flag
                    cmd = [sys.executable, "--run-scraper"]
                else:
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
                cmd += ["--preview"]
                cmd += ["--out", "preview_temp.ics"]

                q.put({"type": "log", "text": f"--- Starte: Jahr {y}, Kategorie: {cat_label} ---", "level": "info"})

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
                    # Intercept PREVIEW_JSON lines
                    if line.startswith("PREVIEW_JSON:"):
                        json_str = line[len("PREVIEW_JSON:"):]
                        try:
                            preview_data = json.loads(json_str)
                            for item in preview_data.get("items", []):
                                item["category"] = cat_label
                            all_preview_items.extend(preview_data.get("items", []))
                        except Exception:
                            pass
                        continue
                    level = "info"
                    if "WARNING" in line or "Fehler" in line:
                        level = "warn"
                    elif "ERROR" in line:
                        level = "error"
                    elif "Vorschau:" in line or "Candidate added" in line:
                        level = "success"
                    q.put({"type": "log", "text": line, "level": level})

                proc.wait()
                step += 1
                percent = int((step / total_steps) * 100)
                q.put({"type": "progress", "percent": percent})

                if proc.returncode != 0:
                    q.put({"type": "log", "text": f"Scraper beendet mit Exit-Code {proc.returncode}", "level": "error"})

        # Sort all items by release_date
        all_preview_items.sort(key=lambda x: x.get("release_date") or "9999-99-99")

        # Store items in job for later ICS generation
        job["preview_items"] = all_preview_items
        job["form_data"] = data
        job["status"] = "preview"
        q.put({"type": "log", "text": f"Scraping abgeschlossen! {len(all_preview_items)} Eintraege gefunden.", "level": "success"})
        q.put({"type": "preview", "items": all_preview_items})

    except Exception as e:
        job["status"] = "error"
        q.put({"type": "log", "text": f"Fehler: {e}", "level": "error"})
        q.put({"type": "error", "text": str(e)})


@app.route("/generate-ics", methods=["POST"])
def generate_ics():
    """Generate an ICS file from user-selected preview items."""
    from icalendar import Calendar, Event
    data = request.get_json(force=True)
    items = data.get("items", [])
    output_pattern = data.get("output_pattern", "bluray_selected.ics")

    if not items:
        return jsonify({"ok": False, "error": "Keine Eintraege ausgewaehlt"}), 400

    cal = Calendar()
    cal.add('prodid', '-//BlurayDisc Scraper//de//')
    cal.add('version', '2.0')

    for item in items:
        ev = Event()
        ev.add('summary', item.get('title', 'Unbekannt'))
        ev.add('dtstamp', datetime.now())
        if item.get('release_date'):
            try:
                from datetime import date
                rd = date.fromisoformat(item['release_date'])
                ev.add('dtstart', rd)
            except Exception:
                pass
        url = item.get('url', '')
        ev.add('description', f"Quelle: {url}")
        ev['uid'] = f"{abs(hash(url))}@bluray-disc.de"
        cal.add_component(ev)

    # Build output filename
    out_name = output_pattern
    if not out_name.endswith(".ics"):
        out_name += ".ics"
    # Simple replacements
    out_name = out_name.replace("{year}", str(datetime.now().year))
    out_name = out_name.replace("{months}", "all")
    out_name = out_name.replace("{release_years}", "ALL")
    out_name = out_name.replace("{slug}", "selected")
    safe_name = Path(out_name).name

    out_path = BASE_DIR / safe_name
    with open(out_path, 'wb') as f:
        f.write(cal.to_ical())

    return jsonify({"ok": True, "file": safe_name, "count": len(items)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # When running as frozen exe, subprocess calls use sys.executable which
    # points back to this exe.  The "--run-scraper" flag lets us forward the
    # call to scraper.py's main() instead of starting the web UI again.
    if getattr(sys, 'frozen', False) and len(sys.argv) > 1 and sys.argv[1] == "--run-scraper":
        # Strip the --run-scraper flag and forward remaining args to scraper
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        import scraper  # bundled by PyInstaller
        scraper.main()
        sys.exit(0)

    port = int(os.environ.get("PORT", 5000))
    print(f"BluRay Calendar Scraper Web-UI startet auf http://localhost:{port}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
