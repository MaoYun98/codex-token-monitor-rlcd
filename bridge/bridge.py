"""Local bridge for the Codex + Beijing weather RLCD dashboard."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from schema import CodexUsage, RateWindow, UsageReport, Weather
from sources.codex_local import fetch_codex
from sources.weather import fetch_weather


REFRESH_INTERVAL_SEC = int(os.environ.get("RLCD_REFRESH_SEC", "45"))
AUTH_TOKEN = os.environ.get("RLCD_AUTH_TOKEN") or None

app = FastAPI(title="Codex RLCD bridge", version="1.0.0")
_cache_lock = threading.Lock()
_cache: dict[str, object] = {"report": None, "ts": 0.0, "error": None}


def _build_live_report() -> UsageReport:
    return UsageReport(
        updated_at=datetime.now(timezone.utc),
        codex=fetch_codex(),
        weather=fetch_weather(),
    )


def _get_cached() -> tuple[UsageReport | None, str | None]:
    with _cache_lock:
        return _cache.get("report"), _cache.get("error")


def _refresh_once() -> None:
    try:
        report = _build_live_report()
        with _cache_lock:
            _cache.update(report=report, ts=time.time(), error=None)
    except Exception as exc:
        with _cache_lock:
            _cache["error"] = f"{type(exc).__name__}: {exc}"


def _refresher_loop() -> None:
    while True:
        _refresh_once()
        time.sleep(REFRESH_INTERVAL_SEC)


_refresher_started = False


def _start_refresher() -> None:
    global _refresher_started
    if _refresher_started:
        return
    _refresher_started = True
    threading.Thread(target=_refresher_loop, name="usage-refresher", daemon=True).start()


def _mock_report() -> UsageReport:
    now = datetime.now(timezone.utc)
    return UsageReport(
        updated_at=now,
        source="mock",
        codex=CodexUsage(
            primary=RateWindow(
                label="7d", used_percent=36, remaining_percent=64,
                window_minutes=10080, resets_at=now + timedelta(days=3, hours=8),
                reset_minutes=4800,
            ),
            secondary=RateWindow(
                label="5h", used_percent=18, remaining_percent=82,
                window_minutes=300, resets_at=now + timedelta(hours=2, minutes=14),
                reset_minutes=134,
            ),
            today_tokens=382_000,
            latest_task_tokens=127_400,
            latest_context_window=258_400,
            plan_type="plus",
            credits_balance=0,
            sampled_at=now,
            status="ok",
        ),
        weather=Weather(
            temp_c=31.2, feels_like_c=33.5, humidity_pct=48, wind_kmh=12.4,
            code=2, condition="Partly", icon="partly", city="BEIJING",
        ),
    )


@app.on_event("startup")
def _on_startup() -> None:
    _start_refresher()


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"ok": True, "cache_age_sec": int(time.time() - float(_cache.get("ts", 0.0) or 0))}


def _check_auth(token_header: str | None, token_query: str | None) -> None:
    if AUTH_TOKEN is not None and (token_header or token_query) != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="invalid or missing token")


@app.get("/api/usage")
def get_usage(
    mock: int = Query(0),
    token: str | None = Query(None),
    x_rlcd_token: str | None = Header(None),
):
    _check_auth(x_rlcd_token, token)
    if mock:
        return _mock_report().model_dump(mode="json")
    report, error = _get_cached()
    if report is None:
        return JSONResponse(status_code=503, content={"error": error or "no data yet"})
    payload = report.model_dump(mode="json")
    if error:
        payload.update(stale=True, error=error)
    return payload


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("RLCD_HOST", "0.0.0.0"),
        port=int(os.environ.get("RLCD_PORT", "7777")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
