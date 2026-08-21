# StockWatch 20

Self-hosted research dashboard for continuously monitoring up to 20 securities for early technical movement, news/catalyst changes, and heuristic market-structure signals.

StockWatch runs as a small FastAPI service in Docker. A background monitor refreshes the configured watchlist, persists the latest state to JSON, and serves a responsive HTML dashboard. The current deployment is designed to sit behind a reverse proxy or Cloudflare Tunnel and uses HTTP Basic Authentication at the application layer.

> **Research use only.** Automated technical indicators, headline sentiment, Fibonacci levels, and Elliott-wave heuristics can be wrong. This project does not provide investment advice or execution functionality.

## Features

- Configurable watchlist of up to 20 symbols.
- Automatic refresh every 15 minutes by default (minimum 5 minutes).
- Technical indicators: EMA20/50/200, RSI(14), MACD, ATR, abnormal-volume Z-score, 20-day high/low proximity.
- 20-day relative strength versus a configurable benchmark (default `SPY`).
- Fibonacci retracement levels from the dominant recent swing.
- Low-weight ZigZag/Elliott-wave pattern heuristic.
- Yahoo Finance headlines, VADER headline sentiment, and simple catalyst classification.
- Composite signal score from `-100` to `+100`.
- Labels: `BULLISH ALERT`, `BULLISH WATCH`, `NEUTRAL`, `BEARISH WATCH`, `BEARISH ALERT`.
- Score-change tracking between scans.
- Movement filters: fast improving (`>= +10`), stable, fast deteriorating (`<= -10`).
- Deterministic Technical Early Alerts with confidence, reasons, confirmation/invalidation levels, and bounded alert history.
- Per-ticker detail panel with technical structure, Fibonacci, Elliott heuristic, calendar items, and news.
- HTTP Basic Authentication from `.env`.
- Localhost-only Docker exposure (`127.0.0.1:8787`) for safe use behind a tunnel/proxy.

## Repository layout

```text
stockwatch20/
├── app.py                 # FastAPI web app, scheduler, Basic Auth
├── monitor.py             # data collection, score momentum, early-alert engine
├── engine.py              # indicators, Fibonacci/Elliott heuristics, news scoring
├── config.yaml            # watchlist and monitoring configuration
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── static/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/
│   └── .gitkeep           # state.json is runtime data and is gitignored
├── scripts/
│   └── inspect_state.py
└── docs/
    ├── DEPLOYMENT_METRIX01.md
    ├── OPERATIONS.md
    ├── METHODOLOGY.md
    └── SECURITY.md
```

## Quick start

```bash
git clone <YOUR-REPOSITORY-URL> stockwatch
cd stockwatch
cp .env.example .env
nano .env
mkdir -p data
docker compose up -d --build
```

The default Compose configuration exposes StockWatch only on:

```text
http://127.0.0.1:8787
```

Use a reverse proxy or Cloudflare Tunnel to publish it over HTTPS.

### Authentication

`.env` must contain:

```text
STOCKWATCH_USER=your-user
STOCKWATCH_PASSWORD=your-long-random-password
```

StockWatch intentionally fails to start if either value is missing. `.env` is excluded from Git.

Generate a password on Linux with:

```bash
openssl rand -hex 24
```

### Current watchlist

The repository currently contains:

```text
AAOI, ABCL, FSLR, CRWD, WYFI, SNOW, SHOP, ASO, APPS, COIN,
NBIX, SPCX, NVAX, TRLV, CORZ, ISRG, NEE, SBUX, SPIR, ADUR
```

Edit `config.yaml` to change the list.

### Special ticker-history cutoffs

`config.yaml` includes explicit start dates for tickers whose earlier symbol history would be misleading:

```yaml
history_start:
  SPCX: 2026-06-12
  TRLV: 2026-06-10
```

Do not remove these cutoffs unless you deliberately want older symbol history included.

## Configuration

Key options in `config.yaml`:

```yaml
poll_minutes: 15
news_items_per_ticker: 8
benchmark: SPY
alert_threshold: 55
timezone: Europe/Vienna
```

The application enforces a minimum polling interval of 5 minutes.

## Deployment

For the current metrix01-style Docker deployment, see [docs/DEPLOYMENT_METRIX01.md](docs/DEPLOYMENT_METRIX01.md).

For routine management, backup, updates, and troubleshooting, see [docs/OPERATIONS.md](docs/OPERATIONS.md).

For signal construction and thresholds, see [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

For credential and exposure guidance, see [docs/SECURITY.md](docs/SECURITY.md).

## Data-source caveats

The prototype uses `yfinance`/Yahoo Finance for market data, news, and calendar information. This is convenient for personal research, but availability, schemas, rate limits, corrections, and licensing can change. For production or commercial deployment, replace the data adapter with a licensed market/news provider appropriate to the intended use.

The scanner writes only the latest state and bounded technical-alert history to `data/state.json`; it is not a full tick/trade database.

## License

No open-source license is included yet. Add the license you want before publishing the repository publicly.
