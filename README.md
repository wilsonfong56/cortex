# Cortex (public slice)

Portfolio extract of a personal trading platform. The full app stays private because it talks to a live journal and brokerage.

This repo is the part that is safe to clone: a Flask shell that **auto-discovers tools**, a **streaming research** endpoint, a **6-indicator regime sizer**, and a **sample GEX** calculator.

```
superapp/run.py            # registers every modules/*.py that exports `bp`
superapp/modules/research.py
superapp/modules/regime.py
superapp/modules/gex.py
superapp/lib/regime.py     # ATR / ADX / RSI / MACD / EMA / RVOL → 0.5x–2.0x
```

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python superapp/run.py
```

Open [http://localhost:5000](http://localhost:5000).

Optional: copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` if you want live Claude tokens instead of the canned research stream.

## What this is / is not

- Is: plugin architecture, SSE + TTL cache, indicator math, dealer-gamma math on a **sample** chain
- Is not: your trades, Robinhood sync, Stripe, user accounts, job-search files

## Stack

Python · Flask · Pandas · NumPy · yfinance (regime fallback) · optional Anthropic
