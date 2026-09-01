"""Streaming research over sample fundamentals. Optional Claude if ANTHROPIC_API_KEY is set."""
import json
import os
import sys
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config

LABEL, ICON, SECTION, ORDER = "Research", "", "Research", 1
bp = Blueprint("research", __name__, url_prefix="/research")

_FUND_PATH = os.path.join(config.DATA_DIR, "sample_fundamentals.json")


def _fundamentals():
    with open(_FUND_PATH) as f:
        return json.load(f)


def _cache_path(key):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    return os.path.join(config.CACHE_DIR, f"{key}.json")


def _cache_get(key, ttl):
    try:
        with open(_cache_path(key)) as f:
            obj = json.load(f)
        if time.time() - obj["ts"] < ttl:
            return obj["text"]
    except Exception:
        return None
    return None


def _cache_set(key, text):
    with open(_cache_path(key), "w") as f:
        json.dump({"text": text, "ts": time.time()}, f)


def _sse(chunks):
    for chunk in chunks:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@bp.route("/")
def index():
    return _HTML


@bp.route("/api/fundamentals/<ticker>")
def api_fundamentals(ticker):
    data = _fundamentals().get(ticker.upper())
    if not data:
        return jsonify({"error": f"No sample fundamentals for {ticker}. Try NVDA or SPY."}), 404
    return jsonify(data)


@bp.route("/api/analyze/<ticker>")
def api_analyze(ticker):
    ticker = ticker.upper()
    fund = _fundamentals().get(ticker)
    if not fund:
        def err():
            yield from _sse([f"No sample row for {ticker}. Use NVDA or SPY."])
        return Response(stream_with_context(err()), mimetype="text/event-stream")

    cached = _cache_get(f"ticker_{ticker}", config.TICKER_ANALYSIS_TTL)
    if cached:
        def replay():
            for i in range(0, len(cached), 24):
                yield f"data: {json.dumps(cached[i:i+24])}\n\n"
            yield "data: [DONE]\n\n"
        return Response(stream_with_context(replay()), mimetype="text/event-stream")

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        import anthropic

        prompt = (
            f"Write a short flash note for {fund['name']} ({ticker}). "
            f"Price {fund['price']}, P/E {fund.get('pe_ratio')}, "
            f"rev growth {fund.get('revenue_growth_yoy')}%. "
            "Sections: Thesis, Risks, Verdict (BUY/HOLD/AVOID). Under 220 words."
        )

        def generate():
            acc = []
            client = anthropic.Anthropic(api_key=key)
            with client.messages.stream(
                model=config.MODEL, max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    acc.append(text)
                    yield f"data: {json.dumps(text)}\n\n"
            _cache_set(f"ticker_{ticker}", "".join(acc))
            yield "data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    canned = (
        f"## {ticker} sample note\n\n"
        f"{fund['name']} last print {fund['price']}. "
        f"This stream is canned because ANTHROPIC_API_KEY is unset. "
        f"The wiring is the same as production Cortex: parallel-ready fundamentals, "
        f"SSE tokens, TTL cache on disk.\n\n"
        f"**Verdict:** HOLD — demo data only."
    )

    def canned_stream():
        for i in range(0, len(canned), 24):
            yield f"data: {json.dumps(canned[i:i+24])}\n\n"
        _cache_set(f"ticker_{ticker}", canned)
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(canned_stream()), mimetype="text/event-stream")


_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Research</title>
<style>
  body{font-family:-apple-system,sans-serif;background:#0d1117;color:#e6edf3;padding:24px;max-width:720px;margin:0 auto}
  input,button{padding:8px 12px;border-radius:6px;border:1px solid #30363d;background:#161b22;color:#e6edf3}
  button{background:#58a6ff;color:#0d1117;font-weight:600;border:0;cursor:pointer}
  #out{margin-top:16px;white-space:pre-wrap;line-height:1.55;color:#c9d1d9}
  .meta{color:#8b949e;font-size:13px;margin:8px 0 16px}
</style></head>
<body>
<h2>Research</h2>
<p class="meta">Sample fundamentals for NVDA / SPY. Streams over SSE. Add ANTHROPIC_API_KEY for a live model.</p>
<input id="t" value="NVDA" maxlength="8">
<button onclick="go()">Generate</button>
<div id="out"></div>
<script>
async function go(){
  const ticker = document.getElementById('t').value.trim().toUpperCase();
  const out = document.getElementById('out');
  const fund = await fetch('/research/api/fundamentals/'+ticker).then(r=>r.json());
  if(fund.error){ out.textContent = fund.error; return; }
  out.textContent = JSON.stringify(fund,null,2)+'\\n\\n';
  const res = await fetch('/research/api/analyze/'+ticker);
  const reader = res.body.getReader(); const dec = new TextDecoder();
  let text = '';
  while(true){
    const {done,value} = await reader.read(); if(done) break;
    for(const line of dec.decode(value).split('\\n')){
      if(!line.startsWith('data: ')) continue;
      const d = line.slice(6);
      if(d==='[DONE]') { out.textContent = JSON.stringify(fund,null,2)+'\\n\\n'+text; return; }
      try { text += JSON.parse(d); out.textContent = JSON.stringify(fund,null,2)+'\\n\\n'+text; } catch(e){}
    }
  }
}
</script>
</body></html>
"""
