"""Local bridge for the Codex + Beijing weather RLCD dashboard."""
from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from schema import CodexUsage, GithubStatus, RateWindow, UsageReport, Weather
from sources.codex_local import fetch_codex
from sources.github_status import fetch_github_status
from sources.weather import fetch_weather


REFRESH_INTERVAL_SEC = int(os.environ.get("RLCD_REFRESH_SEC", "45"))
AUTH_TOKEN = os.environ.get("RLCD_AUTH_TOKEN") or None

app = FastAPI(title="Codex RLCD bridge", version="1.0.0")
_cache_lock = threading.Lock()
_cache: dict[str, object] = {"report": None, "ts": 0.0, "error": None}
_zeroconf: AsyncZeroconf | None = None
_zeroconf_info: ServiceInfo | None = None
_zeroconf_task: asyncio.Task[None] | None = None
_zeroconf_address = ""


def _local_ipv4() -> str:
    configured = os.environ.get("RLCD_MDNS_IP", "").strip()
    if configured:
        return configured
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    finally:
        sock.close()


async def _start_mdns() -> None:
    global _zeroconf, _zeroconf_info, _zeroconf_task, _zeroconf_address
    hostname = os.environ.get("RLCD_MDNS_HOSTNAME", "codex-bridge").strip().removesuffix(".local")
    address = _local_ipv4()
    port = int(os.environ.get("RLCD_PORT", "7777"))
    _zeroconf_info = ServiceInfo(
        "_http._tcp.local.",
        f"{hostname}._http._tcp.local.",
        addresses=[socket.inet_aton(address)],
        port=port,
        properties={"path": "/api/usage"},
        server=f"{hostname}.local.",
    )
    _zeroconf = AsyncZeroconf()
    await _zeroconf.async_register_service(_zeroconf_info)
    _zeroconf_address = address
    _zeroconf_task = asyncio.create_task(_watch_mdns_address())
    print(f"mDNS: http://{hostname}.local:{port}/api/usage -> {address}", flush=True)


async def _watch_mdns_address() -> None:
    global _zeroconf_address
    while True:
        await asyncio.sleep(15)
        address = _local_ipv4()
        if address == _zeroconf_address or _zeroconf is None or _zeroconf_info is None:
            continue
        _zeroconf_info.addresses = [socket.inet_aton(address)]
        await _zeroconf.async_update_service(_zeroconf_info)
        _zeroconf_address = address
        print(f"mDNS: address updated -> {address}", flush=True)


async def _stop_mdns() -> None:
    global _zeroconf, _zeroconf_info, _zeroconf_task, _zeroconf_address
    if _zeroconf_task is not None:
        _zeroconf_task.cancel()
        try:
            await _zeroconf_task
        except asyncio.CancelledError:
            pass
    if _zeroconf is not None:
        if _zeroconf_info is not None:
            await _zeroconf.async_unregister_service(_zeroconf_info)
        await _zeroconf.async_close()
    _zeroconf = None
    _zeroconf_info = None
    _zeroconf_task = None
    _zeroconf_address = ""


def _build_live_report() -> UsageReport:
    now = datetime.now().astimezone()
    return UsageReport(
        updated_at=now.astimezone(timezone.utc),
        updated_hm=now.strftime("%H:%M"),
        codex=fetch_codex(),
        weather=fetch_weather(),
        github=fetch_github_status(),
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
        updated_hm=now.astimezone().strftime("%H:%M"),
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
            focus_minutes=196,
            plan_type="plus",
            credits_balance=0,
            sampled_at=now,
            status="ok",
        ),
        weather=Weather(
            temp_c=31.2, feels_like_c=33.5, humidity_pct=48, wind_kmh=12.4,
            aqi=82, pm25=28.4, rain_3h_pct=65, rain_alert=True,
            code=2, condition="Partly", icon="partly", city="BEIJING",
        ),
        github=GithubStatus(review_requests=3, failing_workflows=1, repositories=2, valid=True),
    )


@app.on_event("startup")
async def _on_startup() -> None:
    await _start_mdns()
    _start_refresher()


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    await _stop_mdns()


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
