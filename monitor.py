from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
import yfinance as yf

from engine import technical_snapshot, fetch_news, fetch_calendar, score_signal

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.yaml"
DATA = BASE / "data" / "state.json"
LOCK = threading.Lock()


def load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text()) or {}


def _download(symbol: str, period: str | None, interval: str, prepost: bool = False, start: str | None = None) -> pd.DataFrame:
    kwargs = {
        "tickers": symbol,
        "interval": interval,
        "auto_adjust": True,
        "repair": False,
        "progress": False,
        "prepost": prepost,
        "threads": False,
    }
    if start:
        kwargs["start"] = start
    elif period:
        kwargs["period"] = period
    return yf.download(**kwargs)


def _normalize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance may return either (Price, Ticker) or (Ticker, Price)
        if symbol in df.columns.get_level_values(-1):
            df = df.xs(symbol, axis=1, level=-1, drop_level=True)
        elif symbol in df.columns.get_level_values(0):
            df = df.xs(symbol, axis=1, level=0, drop_level=True)
    return df


def _num(v: Any, default: float | None = None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _news_balance(news: list[dict[str, Any]]) -> tuple[float, int]:
    if not news:
        return 0.0, 0
    sentiments = [_num(n.get("sentiment"), 0.0) or 0.0 for n in news]
    catalysts = [int(_num(n.get("catalyst"), 0) or 0) for n in news]
    return sum(sentiments) / len(sentiments), sum(catalysts)


def _levels(tech: dict[str, Any]) -> tuple[list[float], list[float]]:
    """Return candidate support and resistance levels around the current price."""
    price = _num(tech.get("price"))
    if not price or price <= 0:
        return [], []
    vals: list[float] = []
    for key in ("ema20", "ema50", "ema200"):
        v = _num(tech.get(key))
        if v and v > 0:
            vals.append(v)
    fib = tech.get("fibonacci") or {}
    if isinstance(fib, dict):
        for key, value in fib.items():
            if key == "direction":
                continue
            v = _num(value)
            if v and v > 0:
                vals.append(v)
    # Reconstruct 20-day high/low from the stored percentage distances.
    bo = _num(tech.get("breakout_20d_pct"))
    if bo is not None and abs(1 + bo / 100) > 1e-9:
        vals.append(price / (1 + bo / 100))
    dl = _num(tech.get("distance_from_20d_low_pct"))
    if dl is not None and abs(1 + dl / 100) > 1e-9:
        vals.append(price / (1 + dl / 100))
    vals = sorted({round(v, 6) for v in vals if 0.25 * price < v < 4 * price})
    supports = [v for v in vals if v < price * 0.999]
    resistances = [v for v in vals if v > price * 1.001]
    return supports, resistances


def build_technical_alert(
    symbol: str,
    tech: dict[str, Any],
    signal: dict[str, Any],
    news: list[dict[str, Any]],
    previous_item: dict[str, Any] | None,
    now_iso: str,
) -> dict[str, Any]:
    """Build a deterministic early-movement assessment and bounded history."""
    score = int(_num(signal.get("score"), 0) or 0)
    delta = _num(signal.get("score_change"))
    price = _num(tech.get("price"))
    change_1h = _num(tech.get("change_1h_pct"), 0) or 0
    volume_z = _num(tech.get("volume_z"), 0) or 0
    rs = _num(tech.get("relative_strength_20d_pct"))
    breakout = _num(tech.get("breakout_20d_pct"))
    dist_low = _num(tech.get("distance_from_20d_low_pct"))
    mean_sent, catalyst = _news_balance(news)

    bullish_points = 0
    bearish_points = 0
    bullish_reasons: list[str] = []
    bearish_reasons: list[str] = []

    if score >= 25:
        bullish_points += min(35, 10 + int((score - 25) * 0.45))
        bullish_reasons.append(f"composite signal {score:+d}")
    elif score <= -25:
        bearish_points += min(35, 10 + int((abs(score) - 25) * 0.45))
        bearish_reasons.append(f"composite signal {score:+d}")

    if delta is not None:
        if delta >= 10:
            bullish_points += min(25, 12 + int((delta - 10) * 0.8))
            bullish_reasons.append(f"signal accelerated {delta:+.1f} since prior scan")
        elif delta <= -10:
            bearish_points += min(25, 12 + int((abs(delta) - 10) * 0.8))
            bearish_reasons.append(f"signal deteriorated {delta:+.1f} since prior scan")

    if volume_z >= 2:
        if change_1h > 0.15:
            bullish_points += min(16, 8 + int((volume_z - 2) * 3))
            bullish_reasons.append(f"up-move on volume expansion z={volume_z:.1f}")
        elif change_1h < -0.15:
            bearish_points += min(16, 8 + int((volume_z - 2) * 3))
            bearish_reasons.append(f"down-move on volume expansion z={volume_z:.1f}")

    atr_pct = _num(tech.get("atr_pct"), 0) or 0
    move_gate = max(1.0, min(4.0, atr_pct * 0.75))
    if change_1h >= move_gate:
        bullish_points += 10
        bullish_reasons.append(f"1h acceleration {change_1h:+.2f}%")
    elif change_1h <= -move_gate:
        bearish_points += 10
        bearish_reasons.append(f"1h acceleration {change_1h:+.2f}%")

    if breakout is not None and breakout >= -1.0:
        bullish_points += 10
        bullish_reasons.append(f"within {abs(breakout):.1f}% of 20d high")
    if dist_low is not None and dist_low <= 1.0:
        bearish_points += 10
        bearish_reasons.append(f"within {max(0.0, dist_low):.1f}% of 20d low")

    if rs is not None and rs >= 5:
        bullish_points += min(10, int(5 + rs / 4))
        bullish_reasons.append(f"relative strength {rs:+.1f}% vs benchmark")
    elif rs is not None and rs <= -5:
        bearish_points += min(10, int(5 + abs(rs) / 4))
        bearish_reasons.append(f"relative weakness {rs:+.1f}% vs benchmark")

    if catalyst > 0 or mean_sent >= 0.20:
        bullish_points += min(10, max(catalyst * 3, int(mean_sent * 20)))
        bullish_reasons.append(f"constructive headline flow ({mean_sent:+.2f}, catalysts {catalyst:+d})")
    elif catalyst < 0 or mean_sent <= -0.20:
        bearish_points += min(10, max(abs(catalyst) * 3, int(abs(mean_sent) * 20)))
        bearish_reasons.append(f"negative headline flow ({mean_sent:+.2f}, catalysts {catalyst:+d})")

    prev_label = str((previous_item or {}).get("signal", {}).get("label", ""))
    label_changed = bool(prev_label and prev_label != signal.get("label"))
    if label_changed:
        if score > 0:
            bullish_points += 8
            bullish_reasons.append(f"signal label changed {prev_label} → {signal.get('label')}")
        elif score < 0:
            bearish_points += 8
            bearish_reasons.append(f"signal label changed {prev_label} → {signal.get('label')}")

    if bullish_points > bearish_points:
        direction = "BULLISH"
        strength = bullish_points
        reasons = bullish_reasons
    elif bearish_points > bullish_points:
        direction = "BEARISH"
        strength = bearish_points
        reasons = bearish_reasons
    else:
        direction = "NEUTRAL"
        strength = max(bullish_points, bearish_points)
        reasons = bullish_reasons[:2] + bearish_reasons[:2]

    active = strength >= 22 and direction != "NEUTRAL"
    if not active:
        alert_label = "NO ACTIVE EARLY ALERT"
    elif strength >= 52 or abs(score) >= 55:
        alert_label = f"{direction} TRIGGER"
    else:
        alert_label = f"EARLY {direction} SETUP"

    confidence = int(max(0, min(95, 35 + strength * 0.85))) if active else int(max(0, min(55, 20 + strength * 0.65)))

    supports, resistances = _levels(tech)
    confirm = None
    invalidate = None
    if price:
        if direction == "BULLISH":
            confirm = resistances[0] if resistances else price * (1 + max(0.01, (atr_pct or 1.5) / 100))
            invalidate = supports[-1] if supports else price * (1 - max(0.015, (atr_pct or 1.5) * 1.2 / 100))
        elif direction == "BEARISH":
            confirm = supports[-1] if supports else price * (1 - max(0.01, (atr_pct or 1.5) / 100))
            invalidate = resistances[0] if resistances else price * (1 + max(0.015, (atr_pct or 1.5) * 1.2 / 100))

    current = {
        "active": active,
        "label": alert_label,
        "direction": direction,
        "confidence": confidence,
        "reasons": reasons[:6],
        "confirm_direction": "above" if direction == "BULLISH" else "below" if direction == "BEARISH" else None,
        "confirm_level": round(confirm, 4) if confirm else None,
        "invalidate_direction": "below" if direction == "BULLISH" else "above" if direction == "BEARISH" else None,
        "invalidate_level": round(invalidate, 4) if invalidate else None,
        "generated_at": now_iso,
    }

    previous_alert = (previous_item or {}).get("technical_alert") or {}
    history = list((previous_item or {}).get("alert_history") or [])[-19:]
    should_record = False
    if active:
        if not previous_alert.get("active"):
            should_record = True
        elif previous_alert.get("label") != alert_label:
            should_record = True
        elif previous_alert.get("direction") != direction:
            should_record = True
        elif abs(int(previous_alert.get("confidence", 0)) - confidence) >= 10:
            should_record = True
        elif delta is not None and abs(delta) >= 15:
            # Strong acceleration merits a new history point even if the label did not change.
            last_hist_delta = _num(history[-1].get("score_change")) if history else None
            if last_hist_delta is None or abs(delta - last_hist_delta) >= 5:
                should_record = True

    if should_record:
        history.append({
            "timestamp": now_iso,
            "label": alert_label,
            "direction": direction,
            "confidence": confidence,
            "score": score,
            "score_change": delta,
            "price": price,
            "confirm_direction": current["confirm_direction"],
            "confirm_level": current["confirm_level"],
            "invalidate_direction": current["invalidate_direction"],
            "invalidate_level": current["invalidate_level"],
            "reasons": reasons[:4],
        })
    return {"technical_alert": current, "alert_history": history[-20:]}


def run_monitor() -> dict[str, Any]:
    if not LOCK.acquire(blocking=False):
        return {"status": "already running"}
    try:
        cfg = load_config()
        symbols = [str(s).strip().upper() for s in cfg.get("watchlist", []) if str(s).strip()][:20]
        benchmark = str(cfg.get("benchmark", "SPY")).upper()
        news_count = int(cfg.get("news_items_per_ticker", 8))
        alert_threshold = int(cfg.get("alert_threshold", 55))
        history_start = {str(k).upper(): str(v) for k, v in (cfg.get("history_start", {}) or {}).items()}

        if not symbols:
            state = {"updated_at": datetime.now(timezone.utc).isoformat(), "watchlist": [], "items": [], "error": "No symbols configured"}
            DATA.write_text(json.dumps(state, indent=2))
            return state

        try:
            bench = _normalize(_download(benchmark, "6mo", "1d"), benchmark)
        except Exception:
            bench = pd.DataFrame()

        # Load the previous persisted scan so we can calculate score momentum.
        previous_state: dict[str, Any] = {}
        if DATA.exists():
            try:
                previous_state = json.loads(DATA.read_text())
            except Exception:
                previous_state = {}
        previous_updated_at = previous_state.get("updated_at")
        previous_items = {
            str(x.get("symbol", "")).upper(): x
            for x in previous_state.get("items", [])
            if isinstance(x, dict) and x.get("symbol")
        }
        now_iso = datetime.now(timezone.utc).isoformat()

        items = []
        for symbol in symbols:
            item: dict[str, Any] = {"symbol": symbol}
            try:
                start = history_start.get(symbol)
                hourly = _normalize(_download(symbol, "1mo", "1h", prepost=True), symbol)
                daily = _normalize(_download(symbol, None if start else "1y", "1d", start=start), symbol)
                tk = yf.Ticker(symbol)
                tech = technical_snapshot(hourly, daily, bench)
                news = fetch_news(tk, news_count)
                calendar = fetch_calendar(tk)
                signal = score_signal(tech, news)
                signal["is_alert"] = abs(signal["score"]) >= alert_threshold

                prev_signal = previous_items.get(symbol, {}).get("signal", {})
                prev_score = prev_signal.get("score") if isinstance(prev_signal, dict) else None
                if isinstance(prev_score, (int, float)):
                    signal["previous_score"] = prev_score
                    signal["score_change"] = round(float(signal["score"]) - float(prev_score), 1)
                else:
                    signal["previous_score"] = None
                    signal["score_change"] = None

                alert_data = build_technical_alert(
                    symbol, tech, signal, news, previous_items.get(symbol), now_iso
                )
                item.update({"technical": tech, "news": news, "calendar": calendar, "signal": signal, **alert_data})
                if start:
                    item["history_start"] = start
                    item["history_limited"] = True
            except Exception as exc:
                item["error"] = str(exc)
                prev_signal = previous_items.get(symbol, {}).get("signal", {})
                prev_score = prev_signal.get("score") if isinstance(prev_signal, dict) else None
                item["signal"] = {
                    "score": 0,
                    "label": "ERROR",
                    "reasons": [str(exc)],
                    "is_alert": False,
                    "previous_score": prev_score if isinstance(prev_score, (int, float)) else None,
                    "score_change": None,
                }
                item["technical_alert"] = {
                    "active": False, "label": "NO ACTIVE EARLY ALERT", "direction": "NEUTRAL",
                    "confidence": 0, "reasons": [str(exc)], "confirm_direction": None,
                    "confirm_level": None, "invalidate_direction": None, "invalidate_level": None,
                    "generated_at": now_iso,
                }
                item["alert_history"] = list(previous_items.get(symbol, {}).get("alert_history") or [])[-20:]
            items.append(item)

        items.sort(key=lambda x: abs(x.get("signal", {}).get("score", 0)), reverse=True)
        state = {
            "updated_at": now_iso,
            "previous_updated_at": previous_updated_at,
            "benchmark": benchmark,
            "watchlist": symbols,
            "items": items,
            "method_note": "Signals are heuristic research indicators, not trading advice. Elliott labels are low-weight ZigZag pattern candidates.",
        }
        DATA.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str))
        tmp.replace(DATA)
        return state
    finally:
        LOCK.release()


if __name__ == "__main__":
    s = run_monitor()
    print(json.dumps({"updated_at": s.get("updated_at"), "count": len(s.get("items", []))}, indent=2))
