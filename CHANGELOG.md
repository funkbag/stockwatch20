# Changelog

## 1.0.0 — 2026-08-21

First consolidated repository release.

- 20-symbol configurable watchlist.
- 15-minute background monitoring (configurable; minimum 5 minutes).
- EMA20/50/200, RSI, MACD, ATR, volume Z-score, 20-day breakout proximity, and benchmark-relative strength.
- Fibonacci swing retracements and cautious ZigZag/Elliott heuristic.
- Yahoo Finance headline sentiment and catalyst classification.
- Composite signal score from -100 to +100.
- Signal-label and score-movement dashboard filters.
- Per-scan score-change tracking.
- Deterministic Technical Early Alert engine with confirmation/invalidation levels.
- Bounded per-ticker technical alert history.
- HTTP Basic Authentication via environment variables.
- Localhost-only Docker port binding for use behind a reverse proxy or Cloudflare Tunnel.
- Special history cutoffs for SPCX and TRLV.
