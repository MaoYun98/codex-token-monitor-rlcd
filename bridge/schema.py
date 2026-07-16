from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RateWindow(BaseModel):
    label: str
    used_percent: float
    remaining_percent: float
    window_minutes: int
    resets_at: Optional[datetime] = None
    reset_minutes: Optional[int] = None


class CodexUsage(BaseModel):
    primary: Optional[RateWindow] = None
    secondary: Optional[RateWindow] = None
    today_tokens: int = 0
    latest_task_tokens: int = 0
    latest_context_window: int = 0
    plan_type: str = ""
    credits_balance: Optional[float] = None
    sampled_at: Optional[datetime] = None
    status: str = "unavailable"


class Weather(BaseModel):
    temp_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_kmh: Optional[float] = None
    code: Optional[int] = None
    condition: str = ""
    icon: str = ""
    city: str = ""


class UsageReport(BaseModel):
    updated_at: datetime
    source: str = "codex-local"
    codex: CodexUsage
    weather: Optional[Weather] = None
