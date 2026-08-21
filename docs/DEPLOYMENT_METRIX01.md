# Deployment on metrix01

This guide assumes Docker Compose is already installed and application stacks are stored below `/opt`.

## 1. Clone or copy the repository

Recommended location:

```bash
cd /opt
sudo git clone <YOUR-REPOSITORY-URL> stockwatch
sudo chown -R "$USER":"$USER" /opt/stockwatch
cd /opt/stockwatch
```

If the directory already exists and contains the manually deployed version, use the migration procedure in the **Existing installation** section below instead of cloning over it.

## 2. Create credentials

```bash
cp .env.example .env
nano .env
```

Set:

```text
STOCKWATCH_USER=<username>
STOCKWATCH_PASSWORD=<strong-password>
```

Then:

```bash
chmod 600 .env
```

Never commit `.env`.

## 3. Review the watchlist

```bash
nano config.yaml
```

The default scan interval is 15 minutes.

## 4. Create persistent state directory

```bash
mkdir -p data
```

`docker-compose.yml` bind-mounts this directory to `/app/data`, so `state.json` survives image rebuilds.

## 5. Build and start

```bash
docker compose up -d --build
```

Verify:

```bash
docker compose ps
docker logs stockwatch20 --tail 100
```

Expected port binding:

```text
127.0.0.1:8787->8787/tcp
```

## 6. Test locally

Unauthenticated access should return `401`:

```bash
curl -i http://127.0.0.1:8787/ | head
```

Authenticated API access:

```bash
curl -u "$USER" http://127.0.0.1:8787/api/state | head -c 500
```

`curl` will prompt for the Basic Auth password if you do not put it on the command line.

## 7. Publish through Cloudflare Tunnel

If `cloudflared` on the server uses a remotely managed tunnel, add a Public Hostname in the Cloudflare dashboard:

```text
Hostname: stockwatch.medialimon.com
Service:  http://localhost:8787
```

Do not expose port 8787 directly to the Internet. The Compose file intentionally binds it to localhost only.

After the hostname is saved, open:

```text
https://stockwatch.medialimon.com
```

The browser should show an HTTP Basic Authentication prompt and then the dashboard.

## Existing installation: convert `/opt/stockwatch` to Git-managed code

Do not delete your current working deployment first. Back it up:

```bash
cd /opt
sudo cp -a stockwatch stockwatch-pre-git-$(date +%Y%m%d-%H%M)
```

Preserve the two runtime files that must not be lost:

```bash
cp /opt/stockwatch/.env /tmp/stockwatch.env
cp -a /opt/stockwatch/data /tmp/stockwatch-data
```

Then replace only the tracked source files with the repository version. A safe approach is to clone into a temporary directory:

```bash
cd /opt
git clone <YOUR-REPOSITORY-URL> stockwatch-git
```

Stop the current container:

```bash
cd /opt/stockwatch
docker compose down
```

Copy the repository source into place while retaining `.env` and `data/`:

```bash
rsync -av --delete \
  --exclude '.env' \
  --exclude 'data/' \
  /opt/stockwatch-git/ /opt/stockwatch/

cp /tmp/stockwatch.env /opt/stockwatch/.env
rm -rf /opt/stockwatch/data
cp -a /tmp/stockwatch-data /opt/stockwatch/data
chmod 600 /opt/stockwatch/.env
```

Finally:

```bash
cd /opt/stockwatch
docker compose up -d --build
```

Verify the dashboard before removing the backup directories.
