"""Regime page — 6 indicators to a 0.5x–2.0x multiplier."""
import os
import sys
from flask import Blueprint, jsonify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lib"))

from regime import get_market_regime  # noqa: E402

LABEL, ICON, SECTION, ORDER = "Regime", "", "Risk", 2
bp = Blueprint("regime", __name__, url_prefix="/regime")


@bp.route("/")
def index():
    return _HTML


@bp.route("/api/score")
def api_score():
    try:
        return jsonify(get_market_regime())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Regime</title>
<style>
  body{font-family:-apple-system,sans-serif;background:#0d1117;color:#e6edf3;padding:24px;max-width:640px;margin:0 auto}
  .mult{font-size:42px;font-weight:700;color:#58a6ff}
  table{width:100%;border-collapse:collapse;margin-top:16px}
  td{padding:6px 0;border-bottom:1px solid #30363d;font-size:13px}
  td:last-child{text-align:right;color:#8b949e}
</style></head>
<body>
<h2>Market regime</h2>
<p id="src" style="color:#8b949e;font-size:13px">Loads sample OHLCV (or yfinance if you delete the CSV).</p>
<div class="mult" id="mult">—</div>
<div id="raw" style="color:#8b949e;margin-bottom:8px"></div>
<table id="tbl"></table>
<script>
fetch('/regime/api/score').then(r=>r.json()).then(d=>{
  if(d.error){ document.getElementById('mult').textContent = d.error; return; }
  document.getElementById('mult').textContent = d.multiplier.toFixed(2)+'x';
  document.getElementById('raw').textContent = 'raw score '+d.raw_score;
  const rows = Object.entries(d.indicators).concat(Object.entries(d.scores).map(([k,v])=>[k,v]));
  document.getElementById('tbl').innerHTML = rows.map(([k,v])=>
    `<tr><td>${k}</td><td>${typeof v==='number'?v.toFixed(3):v}</td></tr>`
  ).join('');
});
</script>
</body></html>
"""
