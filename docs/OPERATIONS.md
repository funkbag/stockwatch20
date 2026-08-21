# Operations guide

## Service status

```bash
cd /opt/stockwatch
docker compose ps
```

## Recent logs

```bash
docker logs stockwatch20 --tail 100
```

Follow logs live:

```bash
docker logs -f stockwatch20
```

## Inspect current state

```bash
cd /opt/stockwatch
python3 scripts/inspect_state.py
```

The helper prints scan time, errors, scores, score deltas, signal labels, and active technical alerts.

## Manual refresh

Through the authenticated API:

```bash
curl -u <username> -X POST http://127.0.0.1:8787/api/refresh
```

Or run the scanner directly inside the container:

```bash
docker compose exec stockwatch python monitor.py
```

Avoid triggering repeated concurrent refreshes. `monitor.py` includes an in-process lock and returns `already running` if a scan is active in the same application process.

## Change the watchlist

Edit:

```bash
nano /opt/stockwatch/config.yaml
```

Then restart StockWatch so the scheduler rereads `poll_minutes` and the next scan uses the new configuration:

```bash
docker compose restart stockwatch
```

For source-code changes, rebuild instead:

```bash
docker compose up -d --build
```

## Check whether scans are continuing

```bash
watch -n 30 'stat -c "%y %s bytes" /opt/stockwatch/data/state.json'
```

With `poll_minutes: 15`, the modification timestamp should normally move about every 15 minutes, allowing for scan duration and temporary upstream failures.

## Backup

The important local runtime files are:

```text
.env
config.yaml
data/state.json
```

The source code should be recoverable from Git.

Example local backup:

```bash
cd /opt
tar --exclude='stockwatch/.git' \
    -czf stockwatch-runtime-$(date +%Y%m%d-%H%M).tar.gz \
    stockwatch/.env stockwatch/config.yaml stockwatch/data
```

Store backups outside `/opt/stockwatch`.

## Update from Git

Before updating:

```bash
cd /opt/stockwatch
git status
```

If clean:

```bash
git pull --ff-only
docker compose up -d --build
```

Then verify:

```bash
docker compose ps
docker logs stockwatch20 --tail 50
python3 scripts/inspect_state.py
```

## Roll back

View recent commits:

```bash
git log --oneline -10
```

For a controlled rollback, create a branch first and restore the desired version:

```bash
git switch -c rollback-safety
git checkout <GOOD-COMMIT> -- .
docker compose up -d --build
```

Do not delete `.env` or `data/state.json` during source rollback.

## Common problems

### Cloudflare shows 502

First test the local application:

```bash
curl -i http://127.0.0.1:8787/ | head
```

- `401 Unauthorized` means StockWatch is listening and authentication is working; inspect Cloudflare routing.
- `Connection refused` means the application/container is not listening. Check `docker compose ps -a` and logs.

### Container is restarting

```bash
docker compose ps -a
docker logs stockwatch20 --tail 150
```

Typical causes are Python syntax/import errors or missing `.env` credentials.

### `scipy` / `sklearn` errors from yfinance

The repository deliberately uses:

```python
"repair": False
```

in the Yahoo Finance download call. Do not re-enable yfinance repair unless you also intend to add its optional scientific dependencies.

### A symbol has `NO DATA` or `ERROR`

Market-data availability can temporarily fail. Check the per-symbol error with:

```bash
python3 scripts/inspect_state.py
```

Also verify that the ticker is valid for the upstream data provider and that any required `history_start` cutoff is configured.
