"""6-indicator market regime → 0.5x–2.0x risk multiplier."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import os

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None


@dataclass
class Config:
    market_ticker: str = "SPY"
    market_lookback: str = "1y"
    atr_period: int = 14
    adx_period: int = 14
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ema_short: int = 20
    ema_long: int = 50
    vol_avg_period: int = 20
    atr_avg_period: int = 20
    mult_min: float = 0.5
    mult_max: float = 2.0
    mult_baseline: float = 0.65
    w_atr: float = 0.40
    w_adx: float = 0.20
    w_volume: float = 0.15
    w_ema: float = 0.15
    w_momentum: float = 0.10
    adx_strong: float = 25.0
    rsi_sweet_low: float = 55.0
    rsi_sweet_high: float = 70.0
    rsi_overbought: float = 70.0
    rvol_strong: float = 1.5


def _ema(series: pd.Series, period: int) -> pd.Series:
    k = 2 / (period + 1)
    out = np.empty(len(series))
    out[0] = series.iloc[0]
    vals = series.values
    for i in range(1, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return pd.Series(out, index=series.index)


def compute_atr(high, low, close, period):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return _ema(tr.fillna(tr.iloc[0]), period)


def compute_adx(high, low, close, period):
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    atr = compute_atr(high, low, close, period)
    plus_di = 100 * _ema(pd.Series(plus_dm, index=high.index), period) / atr
    minus_di = 100 * _ema(pd.Series(minus_dm, index=high.index), period) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _ema(dx.fillna(0), period)
    return pd.DataFrame({"ADX": adx, "+DI": plus_di, "-DI": minus_di}, index=high.index)


def compute_rsi(close, period):
    delta = close.diff()
    avg_gain = _ema(delta.clip(lower=0).fillna(0), period)
    avg_loss = _ema((-delta).clip(lower=0).fillna(0), period)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def compute_macd(close, fast, slow, signal):
    line = _ema(close, fast) - _ema(close, slow)
    sig = _ema(line, signal)
    return pd.DataFrame({"MACD": line, "Signal": sig, "Histogram": line - sig}, index=close.index)


def build_indicator_table(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    out = df.copy()
    out["ATR"] = compute_atr(df["High"], df["Low"], df["Close"], cfg.atr_period)
    out["ATR_avg"] = out["ATR"].rolling(cfg.atr_avg_period).mean()
    adx = compute_adx(df["High"], df["Low"], df["Close"], cfg.adx_period)
    out["ADX"] = adx["ADX"]
    out["RSI"] = compute_rsi(df["Close"], cfg.rsi_period)
    macd = compute_macd(df["Close"], cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    out["MACD_hist"] = macd["Histogram"]
    out["EMA_short"] = _ema(df["Close"], cfg.ema_short)
    out["EMA_long"] = _ema(df["Close"], cfg.ema_long)
    out["EMA_slope"] = out["EMA_short"].diff()
    avg = df["Volume"].rolling(cfg.vol_avg_period).mean()
    out["RVOL"] = (df["Volume"] / avg.replace(0, np.nan)).fillna(1.0)
    return out


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_composite(row: pd.Series, cfg: Config) -> dict:
    atr_avg = row.get("ATR_avg")
    s_atr = 0.5 if pd.isna(atr_avg) or atr_avg == 0 else _clamp01(1.5 - row["ATR"] / atr_avg)
    adx = row.get("ADX")
    if pd.isna(adx):
        s_adx = 0.5
    elif adx < cfg.adx_strong:
        s_adx = 0.3
    else:
        s_adx = _clamp01(0.6 + (adx - cfg.adx_strong) / 62.5)
    rsi = row.get("RSI", 50)
    if pd.isna(rsi):
        s_rsi = 0.5
    elif cfg.rsi_sweet_low <= rsi <= cfg.rsi_sweet_high:
        s_rsi = 0.8
    elif rsi > cfg.rsi_overbought:
        s_rsi = 0.3
    else:
        s_rsi = 0.5
    hist = row.get("MACD_hist", 0) or 0
    s_macd = _clamp01(0.5 + float(hist) / 6.0) if not pd.isna(hist) else 0.5
    rvol = row.get("RVOL", 1.0)
    if pd.isna(rvol):
        s_vol = 0.5
    elif rvol >= cfg.rvol_strong:
        s_vol = min(1.0, 0.6 + (rvol - cfg.rvol_strong) * 0.2)
    else:
        s_vol = _clamp01(rvol / cfg.rvol_strong * 0.6)
    ema_s, ema_l, slope = row.get("EMA_short"), row.get("EMA_long"), row.get("EMA_slope")
    if pd.isna(ema_s) or pd.isna(ema_l) or pd.isna(slope):
        s_ema = 0.5
    else:
        s_ema = ((1.0 if ema_s > ema_l else 0.0) + (1.0 if slope > 0 else 0.0)) / 2.0
    s_momentum = (s_rsi + s_macd) / 2.0
    raw = (
        cfg.w_atr * s_atr + cfg.w_adx * s_adx + cfg.w_volume * s_vol
        + cfg.w_ema * s_ema + cfg.w_momentum * s_momentum
    )
    bl = cfg.mult_baseline
    if raw <= bl:
        multiplier = cfg.mult_min + (1.0 - cfg.mult_min) * (raw / bl)
    else:
        multiplier = 1.0 + (cfg.mult_max - 1.0) * ((raw - bl) / (1.0 - bl))
    multiplier = max(cfg.mult_min, min(cfg.mult_max, multiplier))
    return {
        "score_atr": s_atr, "score_adx": s_adx, "score_volume": s_vol,
        "score_ema": s_ema, "score_rsi": s_rsi, "score_macd": s_macd,
        "raw_composite": raw, "multiplier": multiplier,
    }


def load_ohlcv(cfg: Optional[Config] = None) -> pd.DataFrame:
    cfg = cfg or Config()
    sample = os.path.join(os.path.dirname(__file__), "..", "data", "sample_ohlcv.csv")
    sample = os.path.normpath(sample)
    if os.path.exists(sample):
        df = pd.read_csv(sample, parse_dates=["Date"])
        df = df.set_index("Date")
        return df
    if yf is None:
        raise RuntimeError("No sample_ohlcv.csv and yfinance is not installed")
    data = yf.download(cfg.market_ticker, period=cfg.market_lookback, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data


def get_market_regime(cfg: Optional[Config] = None) -> dict:
    cfg = cfg or Config()
    enriched = build_indicator_table(load_ohlcv(cfg), cfg)
    row = enriched.iloc[-1]
    comp = compute_composite(row, cfg)
    return {
        "multiplier": round(float(comp["multiplier"]), 2),
        "raw_score": round(float(comp["raw_composite"]), 3),
        "indicators": {
            "ATR": float(row["ATR"]),
            "ADX": float(row["ADX"]),
            "RSI": float(row["RSI"]),
            "MACD_hist": float(row["MACD_hist"]),
            "EMA_20": float(row["EMA_short"]),
            "EMA_50": float(row["EMA_long"]),
            "RVOL": float(row["RVOL"]),
        },
        "scores": {k: round(float(v), 3) for k, v in comp.items() if k not in ("raw_composite", "multiplier")},
    }
