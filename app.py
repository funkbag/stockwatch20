from __future__ import annotations

import base64
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from monitor import run_monitor

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "state.json"
CONFIG = BASE / "config.yaml"
scheduler = BackgroundScheduler()

AUTH_USER = os.environ.get("STOCKWATCH_USER", "").strip()
AUTH_PASSWORD = os.environ.get("STOCKWATCH_PASSWORD", "")

if not AUTH_USER or not AUTH_PASSWORD:
    raise RuntimeError(
        "StockWatch authentication is not configured. "
        "Set STOCKWATCH_USER and STOCKWATCH_PASSWORD in .env."
    )


def poll_minutes() -> int:
    try:
        cfg = yaml.safe_load(CONFIG.read_text()) or {}
        return max(5, int(cfg.get("poll_minutes", 15)))
    except Exception:
        return 15


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_monitor,
        "interval",
        minutes=poll_minutes(),
        id="stock-monitor",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    # Run the first scan asynchronously so the HTTP server can start immediately.
    scheduler.add_job(run_monitor, id="initial-refresh")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="StockWatch 20", lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StockWatch 20"'},
        )

    try:
        encoded = auth.split(" ", 1)[1]
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StockWatch 20"'},
        )

    user_ok = secrets.compare_digest(username, AUTH_USER)
    password_ok = secrets.compare_digest(password, AUTH_PASSWORD)
    if not (user_ok and password_ok):
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StockWatch 20"'},
        )

    response = await call_next(request)
    # State is dynamic and should not be cached by browsers/proxies.
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/state")
def state():
    if not DATA.exists():
        return {"updated_at": None, "watchlist": [], "items": [], "status": "initializing"}
    return json.loads(DATA.read_text())


@app.post("/api/refresh")
def refresh():
    try:
        result = run_monitor()
        return {"ok": True, "updated_at": result.get("updated_at")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
