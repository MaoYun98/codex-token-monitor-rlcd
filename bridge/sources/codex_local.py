"""Read Codex usage snapshots from local session JSONL files.

Codex writes a ``token_count`` event after model turns. The event contains the
same rate-window percentages shown by the app, plus per-task token totals. This
reader never opens auth files and never sends Codex credentials over the
network.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from schema import CodexUsage, RateWindow


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _session_files(home: Path) -> Iterable[Path]:
    yield from (home / "sessions").glob("**/*.jsonl")
    yield from (home / "archived_sessions").glob("*.jsonl")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _last_snapshot(path: Path) -> tuple[datetime, dict[str, Any]] | None:
    latest: tuple[datetime, dict[str, Any]] | None = None
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                payload = event.get("payload") or {}
                if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                    continue
                timestamp = _parse_time(event.get("timestamp"))
                if timestamp is not None:
                    latest = timestamp, payload
    except OSError:
        return None
    return latest


def _window_label(minutes: int) -> str:
    if minutes == 300:
        return "5h"
    if minutes == 1440:
        return "24h"
    if minutes == 10080:
        return "7d"
    if minutes and minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes and minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m" if minutes else "limit"


def _rate_window(raw: Any, now: datetime) -> RateWindow | None:
    if not isinstance(raw, dict) or raw.get("used_percent") is None:
        return None
    used = max(0.0, min(100.0, float(raw["used_percent"])))
    minutes = int(raw.get("window_minutes") or 0)
    reset_epoch = raw.get("resets_at")
    resets_at = datetime.fromtimestamp(float(reset_epoch), tz=now.tzinfo) if reset_epoch else None
    reset_minutes = max(0, int((resets_at - now).total_seconds() // 60)) if resets_at else None
    return RateWindow(
        label=_window_label(minutes),
        used_percent=used,
        remaining_percent=round(100.0 - used, 1),
        window_minutes=minutes,
        resets_at=resets_at,
        reset_minutes=reset_minutes,
    )


def fetch_codex(home: Path | None = None, now: datetime | None = None) -> CodexUsage:
    root = home or _codex_home()
    local_now = now or datetime.now().astimezone()
    snapshots: list[tuple[datetime, dict[str, Any]]] = []
    for path in _session_files(root):
        snapshot = _last_snapshot(path)
        if snapshot is not None:
            snapshots.append(snapshot)

    if not snapshots:
        return CodexUsage(status="unavailable")

    snapshots.sort(key=lambda item: item[0])
    sampled_at, latest = snapshots[-1]
    today_tokens = 0
    for timestamp, payload in snapshots:
        if timestamp.astimezone().date() != local_now.date():
            continue
        usage = ((payload.get("info") or {}).get("total_token_usage") or {})
        today_tokens += int(usage.get("total_tokens") or 0)

    info = latest.get("info") or {}
    total = info.get("total_token_usage") or {}
    rate_limits = latest.get("rate_limits") or {}
    credits = rate_limits.get("credits") or {}
    balance = credits.get("balance")
    try:
        credits_balance = float(balance) if balance is not None else None
    except (TypeError, ValueError):
        credits_balance = None

    return CodexUsage(
        primary=_rate_window(rate_limits.get("primary"), local_now),
        secondary=_rate_window(rate_limits.get("secondary"), local_now),
        today_tokens=today_tokens,
        latest_task_tokens=int(total.get("total_tokens") or 0),
        latest_context_window=int(info.get("model_context_window") or 0),
        plan_type=str(rate_limits.get("plan_type") or ""),
        credits_balance=credits_balance,
        sampled_at=sampled_at,
        status="ok",
    )
