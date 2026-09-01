"""Dealer gamma on a sample options chain. No live brokerage."""
import json
import os
import sys
from collections import defaultdict

from flask import Blueprint, jsonify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import config

LABEL, ICON, SECTION, ORDER = "GEX", "", "Options", 3
bp = Blueprint("gex", __name__, url_prefix="/gex")
_CHAIN = os.path.join(config.DATA_DIR, "sample_chain.json")

# 100 share multiplier, call GEX positive / put GEX negative (dealer-short-put convention used as demo)
CONTRACT_MULT = 100


def compute_gex(payload):
    spot = payload["spot"]
    by_strike = defaultdict(float)
    for c in payload["contracts"]:
        signed = 1 if c["type"] == "call" else -1
        by_strike[c["strike"]] += signed * c["gamma"] * c["oi"] * CONTRACT_MULT * spot
    rows = [{"strike": k, "gex": v} for k, v in sorted(by_strike.items())]
    flip = None
    for a, b in zip(rows, rows[1:]):
        if a["gex"] == 0:
            flip = a["strike"]
            break
        if a["gex"] * b["gex"] < 0:
            # linear interpolate
            t = abs(a["gex"]) / (abs(a["gex"]) + abs(b["gex"]))
            flip = a["strike"] + t * (b["strike"] - a["strike"])
            break
    net = sum(r["gex"] for r in rows)
    return {"underlying": payload["underlying"], "spot": spot, "net_gex": net, "flip": flip, "by_strike": rows}


@bp.route("/")
def index():
    return _HTML


@bp.route("/api/gex")
def api_gex():
    with open(_CHAIN) as f:
        return jsonify(compute_gex(json.load(f)))


_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>GEX</title>
<style>
  body{font-family:-apple-system,sans-serif;background:#0d1117;color:#e6edf3;padding:24px;max-width:640px;margin:0 auto}
  .k{color:#8b949e;font-size:12px;text-transform:uppercase}
  .v{font-size:22px;font-weight:700;margin:0 0 12px}
  td{padding:5px 0;border-bottom:1px solid #30363d;font-size:13px}
  td:last-child{text-align:right}
</style></head>
<body>
<h2>Sample GEX</h2>
<p style="color:#8b949e;font-size:13px">Computed from <code>data/sample_chain.json</code>, not a live CBOE pull.</p>
<div class="k">Net GEX</div><div class="v" id="net">—</div>
<div class="k">Flip</div><div class="v" id="flip">—</div>
<table id="tbl"></table>
<script>
fetch('/gex/api/gex').then(r=>r.json()).then(d=>{
  document.getElementById('net').textContent = d.net_gex.toLocaleString(undefined,{maximumFractionDigits:0});
  document.getElementById('flip').textContent = d.flip==null?'n/a':d.flip.toFixed(1);
  document.getElementById('tbl').innerHTML = d.by_strike.map(r=>
    `<tr><td>${r.strike}</td><td>${r.gex.toLocaleString(undefined,{maximumFractionDigits:0})</td></tr>`
  ).join('');
});
</script>
</body></html>
"""
