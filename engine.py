from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

SENTIMENT = SentimentIntensityAnalyzer()

POSITIVE_CATALYSTS = {
    "beat", "beats", "upgrade", "upgraded", "approval", "approved", "contract",
    "partnership", "record revenue", "raises guidance", "buyback", "acquisition",
    "breakthrough", "positive trial", "dividend increase"
}
NEGATIVE_CATALYSTS = {
    "miss", "misses", "downgrade", "downgraded", "offering", "dilution", "subpoena",
    "investigation", "lawsuit", "recall", "warning", "cuts guidance", "bankruptcy",
    "delisting", "secondary offering", "clinical hold", "failed trial"
}
IMPORTANT_TERMS = {
    "earnings", "guidance", "fda", "trial", "offering", "merger", "acquisition",
    "sec", "lawsuit", "contract", "partnership", "analyst", "upgrade", "downgrade",
    "buyback", "dividend", "bankruptcy", "delisting", "investigation"
}


def _safe_float(v: Any, default: float | None = None) -> float | None:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev).abs(),
        (df["Low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def zigzag(close: pd.Series, threshold: float = 0.05) -> list[dict[str, Any]]:
    """Simple percentage ZigZag; useful for heuristic swing structure, not canonical Elliott labeling."""
    if len(close) < 3:
        return []
    vals = close.dropna()
    if len(vals) < 3:
        return []
    pivots: list[dict[str, Any]] = []
    last_idx = vals.index[0]
    last_price = float(vals.iloc[0])
    trend = 0
    extreme_idx, extreme_price = last_idx, last_price

    for idx, price_raw in vals.iloc[1:].items():
        price = float(price_raw)
        if trend >= 0:
            if price >= extreme_price:
                extreme_idx, extreme_price = idx, price
            drawdown = (price - extreme_price) / extreme_price
            if drawdown <= -threshold:
                pivots.append({"date": str(extreme_idx), "price": extreme_price, "type": "H"})
                trend = -1
                extreme_idx, extreme_price = idx, price
        if trend <= 0:
            if price <= extreme_price:
                extreme_idx, extreme_price = idx, price
            rebound = (price - extreme_price) / extreme_price
            if rebound >= threshold:
                pivots.append({"date": str(extreme_idx), "price": extreme_price, "type": "L"})
                trend = 1
                extreme_idx, extreme_price = idx, price
    pivots.append({"date": str(extreme_idx), "price": extreme_price, "type": "H" if trend >= 0 else "L"})
    # collapse same-type consecutive pivots
    out: list[dict[str, Any]] = []
    for p in pivots:
        if out and out[-1]["type"] == p["type"]:
            better = p["price"] > out[-1]["price"] if p["type"] == "H" else p["price"] < out[-1]["price"]
            if better:
                out[-1] = p
        else:
            out.append(p)
    return out[-9:]


def fib_levels(close: pd.Series) -> dict[str, float] | None:
    window = close.dropna().tail(90)
    if len(window) < 20:
        return None
    hi_i, lo_i = window.idxmax(), window.idxmin()
    hi, lo = float(window.max()), float(window.min())
    if hi <= lo:
        return None
    # Orientation follows the most recent endpoint of the dominant 90-bar swing.
    upswing = lo_i < hi_i
    rng = hi - lo
    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    levels = {}
    for x in ratios:
        level = hi - rng * x if upswing else lo + rng * x
        levels[f"{x:.3f}"] = round(level, 4)
    return {"swing_low": round(lo, 4), "swing_high": round(hi, 4), "direction": "up" if upswing else "down", **levels}


def elliott_heuristic(pivots: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign a cautious pattern label from alternating ZigZag pivots. This is intentionally heuristic."""
    if len(pivots) < 5:
        return {"label": "insufficient structure", "confidence": 0.15}
    p = pivots[-6:]
    prices = [x["price"] for x in p]
    types = [x["type"] for x in p]
    confidence = 0.25
    label = "mixed / corrective"

    if len(p) >= 6 and types == ["L", "H", "L", "H", "L", "H"]:
        higher_lows = prices[2] > prices[0] and prices[4] > prices[2]
        higher_highs = prices[3] > prices[1] and prices[5] > prices[3]
        if higher_lows and higher_highs:
            label, confidence = "bullish 5-wave candidate", 0.62
    elif len(p) >= 6 and types == ["H", "L", "H", "L", "H", "L"]:
        lower_highs = prices[2] < prices[0] and prices[4] < prices[2]
        lower_lows = prices[3] < prices[1] and prices[5] < prices[3]
        if lower_highs and lower_lows:
            label, confidence = "bearish 5-wave candidate", 0.62
    else:
        last = p[-5:]
        lp = [x["price"] for x in last]
        lt = [x["type"] for x in last]
        if lt in (["H", "L", "H", "L", "H"], ["L", "H", "L", "H", "L"]):
            label, confidence = "ABC / complex correction candidate", 0.42

    return {"label": label, "confidence": confidence, "pivots": p}


def technical_snapshot(hourly: pd.DataFrame, daily: pd.DataFrame, benchmark_daily: pd.DataFrame | None = None) -> dict[str, Any]:
    if hourly.empty or daily.empty:
        return {"error": "insufficient price data"}

    h = hourly.copy().dropna(subset=["Close"])
    d = daily.copy().dropna(subset=["Close"])
    close = h["Close"]
    daily_close = d["Close"]

    h["ema20"] = ema(close, 20)
    h["ema50"] = ema(close, 50)
    h["ema200"] = ema(close, 200)
    h["rsi14"] = rsi(close)
    macd_line = ema(close, 12) - ema(close, 26)
    macd_signal = ema(macd_line, 9)
    h["macd"] = macd_line
    h["macd_signal"] = macd_signal
    h["atr14"] = atr(h)

    last = h.iloc[-1]
    price = float(last["Close"])
    prev = float(h.iloc[-2]["Close"]) if len(h) > 1 else price
    ret_1h = (price / prev - 1) * 100 if prev else 0

    vol = h["Volume"].replace(0, np.nan)
    vol_mean = vol.tail(30).mean()
    vol_std = vol.tail(30).std()
    vol_z = (vol.iloc[-1] - vol_mean) / vol_std if vol_std and not np.isnan(vol_std) else 0

    atr_pct = float(last["atr14"] / price * 100) if price else 0
    hh20 = float(daily_close.tail(20).max()) if len(d) >= 20 else float(daily_close.max())
    ll20 = float(daily_close.tail(20).min()) if len(d) >= 20 else float(daily_close.min())
    breakout_pct = (price / hh20 - 1) * 100 if hh20 else 0
    breakdown_pct = (price / ll20 - 1) * 100 if ll20 else 0

    rel_20d = None
    if benchmark_daily is not None and not benchmark_daily.empty and len(daily_close) >= 21 and len(benchmark_daily) >= 21:
        sret = float(daily_close.iloc[-1] / daily_close.iloc[-21] - 1)
        bclose = benchmark_daily["Close"].dropna()
        bret = float(bclose.iloc[-1] / bclose.iloc[-21] - 1)
        rel_20d = (sret - bret) * 100

    pivots = zigzag(daily_close, 0.05)
    fib = fib_levels(daily_close)
    elliott = elliott_heuristic(pivots)

    spark = [round(float(x), 4) for x in close.tail(80).tolist()]
    return {
        "price": round(price, 4),
        "change_1h_pct": round(ret_1h, 2),
        "rsi14": round(_safe_float(last["rsi14"], 50) or 50, 2),
        "macd": round(_safe_float(last["macd"], 0) or 0, 4),
        "macd_signal": round(_safe_float(last["macd_signal"], 0) or 0, 4),
        "ema20": round(_safe_float(last["ema20"], price) or price, 4),
        "ema50": round(_safe_float(last["ema50"], price) or price, 4),
        "ema200": round(_safe_float(last["ema200"], price) or price, 4),
        "atr_pct": round(atr_pct, 2),
        "volume_z": round(_safe_float(vol_z, 0) or 0, 2),
        "breakout_20d_pct": round(breakout_pct, 2),
        "distance_from_20d_low_pct": round(breakdown_pct, 2),
        "relative_strength_20d_pct": round(rel_20d, 2) if rel_20d is not None else None,
        "fibonacci": fib,
        "elliott": elliott,
        "sparkline": spark,
    }


def _extract_news_item(item: dict[str, Any]) -> dict[str, Any] | None:
    content = item.get("content") if isinstance(item, dict) else None
    if isinstance(content, dict):
        title = content.get("title") or content.get("summary")
        provider = content.get("provider") or {}
        publisher = provider.get("displayName") if isinstance(provider, dict) else None
        click = content.get("clickThroughUrl") or content.get("canonicalUrl") or {}
        url = click.get("url") if isinstance(click, dict) else None
        published = content.get("pubDate") or content.get("displayTime")
    else:
        title = item.get("title") if isinstance(item, dict) else None
        publisher = item.get("publisher") if isinstance(item, dict) else None
        url = item.get("link") if isinstance(item, dict) else None
        published = item.get("providerPublishTime") if isinstance(item, dict) else None
        if isinstance(published, (int, float)):
            published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
    if not title:
        return None
    title_l = title.lower()
    sentiment = SENTIMENT.polarity_scores(title)["compound"]
    catalyst = sum(term in title_l for term in POSITIVE_CATALYSTS) - sum(term in title_l for term in NEGATIVE_CATALYSTS)
    important = any(term in title_l for term in IMPORTANT_TERMS)
    return {
        "title": re.sub(r"\s+", " ", str(title)).strip(),
        "publisher": publisher,
        "url": url,
        "published": published,
        "sentiment": round(float(sentiment), 3),
        "catalyst": catalyst,
        "important": important,
    }


def fetch_news(ticker: yf.Ticker, count: int = 8) -> list[dict[str, Any]]:
    try:
        raw = ticker.get_news(count=count, tab="news")
    except Exception:
        try:
            raw = ticker.news
        except Exception:
            raw = []
    out = []
    for item in raw or []:
        parsed = _extract_news_item(item)
        if parsed:
            out.append(parsed)
    return out[:count]


def fetch_calendar(ticker: yf.Ticker) -> list[dict[str, Any]]:
    try:
        cal = ticker.calendar
    except Exception:
        return []
    events = []
    if isinstance(cal, dict):
        for k, v in cal.items():
            if v is None:
                continue
            if isinstance(v, (list, tuple)):
                v = ", ".join(str(x) for x in v)
            events.append({"event": str(k), "date": str(v)})
    elif isinstance(cal, pd.DataFrame):
        for idx, row in cal.iterrows():
            for col, val in row.items():
                if pd.notna(val):
                    events.append({"event": f"{idx} {col}", "date": str(val)})
    return events[:8]


def score_signal(tech: dict[str, Any], news: list[dict[str, Any]]) -> dict[str, Any]:
    if "error" in tech:
        return {"score": 0, "label": "NO DATA", "reasons": [tech["error"]]}
    score = 0.0
    reasons: list[str] = []
    p = tech["price"]

    # Trend and momentum
    if p > tech["ema20"] > tech["ema50"]:
        score += 18; reasons.append("price > EMA20 > EMA50")
    elif p < tech["ema20"] < tech["ema50"]:
        score -= 18; reasons.append("price < EMA20 < EMA50")
    if p > tech["ema200"]:
        score += 6
    else:
        score -= 6

    r = tech["rsi14"]
    if 52 <= r <= 70:
        score += 10; reasons.append("constructive RSI")
    elif r >= 76:
        score -= 5; reasons.append("RSI stretched")
    elif r <= 28:
        score += 4; reasons.append("RSI oversold / bounce setup")
    elif r < 42:
        score -= 7

    if tech["macd"] > tech["macd_signal"]:
        score += 9; reasons.append("MACD positive")
    else:
        score -= 7

    # Early movement / participation
    if tech["volume_z"] >= 2:
        score += 12 if tech["change_1h_pct"] >= 0 else -12
        reasons.append(f"volume expansion z={tech['volume_z']}")
    if tech["breakout_20d_pct"] >= -1.0:
        score += 12; reasons.append("testing 20d high")
    if tech.get("relative_strength_20d_pct") is not None:
        rs = tech["relative_strength_20d_pct"]
        score += max(-10, min(10, rs / 2))
        if abs(rs) >= 5:
            reasons.append(f"20d relative strength {rs:+.1f}% vs benchmark")

    # Elliott is deliberately small weight.
    e = tech.get("elliott", {})
    if "bullish" in e.get("label", ""):
        score += 6 * e.get("confidence", 0)
        reasons.append(e["label"])
    elif "bearish" in e.get("label", ""):
        score -= 6 * e.get("confidence", 0)
        reasons.append(e["label"])

    # Headlines
    if news:
        mean_sent = float(np.mean([x["sentiment"] for x in news]))
        catalyst = sum(x["catalyst"] for x in news)
        score += max(-10, min(10, mean_sent * 14))
        score += max(-12, min(12, catalyst * 4))
        if abs(mean_sent) > 0.15:
            reasons.append(f"headline sentiment {mean_sent:+.2f}")
        if catalyst:
            reasons.append(f"news catalyst balance {catalyst:+d}")

    score = int(round(max(-100, min(100, score))))
    if score >= 55:
        label = "BULLISH ALERT"
    elif score >= 25:
        label = "BULLISH WATCH"
    elif score <= -55:
        label = "BEARISH ALERT"
    elif score <= -25:
        label = "BEARISH WATCH"
    else:
        label = "NEUTRAL"
    return {"score": score, "label": label, "reasons": reasons[:7]}
