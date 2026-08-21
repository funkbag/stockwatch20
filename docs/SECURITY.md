# Security notes

## Authentication

StockWatch uses HTTP Basic Authentication at the FastAPI middleware layer. Every dashboard, static, and API request must authenticate.

Credentials are provided through environment variables loaded from `.env`:

```text
STOCKWATCH_USER
STOCKWATCH_PASSWORD
```

The service fails closed at startup if either value is empty.

## HTTPS is required for remote access

Basic Authentication credentials are transmitted with every request and must therefore be protected by TLS. Do not publish StockWatch over plain HTTP.

The recommended deployment is:

```text
Internet
  -> HTTPS / Cloudflare
  -> Cloudflare Tunnel or reverse proxy
  -> 127.0.0.1:8787
  -> StockWatch container
```

The provided Compose file intentionally binds only to `127.0.0.1`.

## Secrets

`.env` is gitignored. Never commit passwords, tunnel tokens, API keys, or other credentials.

Recommended permissions:

```bash
chmod 600 .env
```

If a credential appears in terminal output, screenshots, issue trackers, Git history, or chat logs, rotate it when practical.

## Git history

Before the first push, verify that no secrets are staged:

```bash
git status
git diff --cached
```

You can also search common secret names:

```bash
grep -RIn --exclude-dir=.git -E 'PASSWORD=|TOKEN=|API_KEY=' .
```

`.env.example` intentionally contains placeholders and is safe to commit.

## Public repositories

This repository contains a watchlist and research methodology. If you do not want those public, use a private repository.

No license is included by default. Without an explicit open-source license, public visibility does not automatically grant others permission to reuse the code.
