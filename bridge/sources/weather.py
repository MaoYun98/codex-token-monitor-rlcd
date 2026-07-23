"""Beijing weather, 3-hour rain risk, and air quality.

Caiyun may provide the current weather when configured. Open-Meteo supplies
the no-key fallback, hourly precipitation probability, US AQI, and PM2.5.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from schema import Weather

CAIYUN_KEY = os.environ.get("CAIYUN_API_KEY") or None
LAT = float(os.environ.get("RLCD_WEATHER_LAT", "39.9042"))
LON = float(os.environ.get("RLCD_WEATHER_LON", "116.4074"))
CITY = os.environ.get("RLCD_WEATHER_CITY", "BEIJING")
TTL = int(os.environ.get("RLCD_WEATHER_TTL", "600"))
AIR_TTL = int(os.environ.get("RLCD_AIR_TTL", "600"))
AIR_RETRY_SEC = int(os.environ.get("RLCD_AIR_RETRY_SEC", "60"))
RAIN_ALERT_PCT = float(os.environ.get("RLCD_RAIN_ALERT_PCT", "30"))

_SKYCON: dict[str, tuple[str, str]] = {
    "CLEAR_DAY": ("Clear", "clear"), "CLEAR_NIGHT": ("Clear", "clear"),
    "PARTLY_CLOUDY_DAY": ("Partly", "partly"),
    "PARTLY_CLOUDY_NIGHT": ("Partly", "partly"),
    "CLOUDY": ("Cloudy", "cloud"), "LIGHT_RAIN": ("Rain", "rain"),
    "MODERATE_RAIN": ("Rain", "rain"), "HEAVY_RAIN": ("Heavy", "rain"),
    "STORM_RAIN": ("Storm", "rain"), "FOG": ("Fog", "fog"),
    "LIGHT_SNOW": ("Snow", "snow"), "MODERATE_SNOW": ("Snow", "snow"),
    "HEAVY_SNOW": ("Snow", "snow"), "STORM_SNOW": ("Snow", "snow"),
    "DUST": ("Haze", "fog"), "SAND": ("Haze", "fog"),
    "WIND": ("Windy", "cloud"),
}

_cache: dict[str, object] = {"weather": None, "ts": 0.0}
_air_cache: dict[str, object] = {
    "aqi": None, "pm25": None, "ts": 0.0, "attempt_ts": 0.0,
}


def _json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "codex-token-monitor-rlcd"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def _condition(code: int, cloud_cover: float, precipitation: float) -> tuple[str, str]:
    if code in (45, 48):
        return "Fog", "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow", "snow"
    if precipitation >= 2.0:
        return "Heavy", "rain"
    if precipitation >= 0.3:
        return "Rain", "rain"
    if precipitation > 0:
        return "Drizzle", "rain"
    if cloud_cover < 20:
        return "Clear", "clear"
    if cloud_cover < 50:
        return "Partly", "partly"
    if cloud_cover < 85:
        return "Cloudy", "cloud"
    return "Overcast", "cloud"


def _rain_probability() -> float | None:
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
        "&hourly=precipitation_probability&forecast_hours=3&timezone=Asia/Shanghai"
    )
    values = (_json(url).get("hourly") or {}).get("precipitation_probability") or []
    numeric = [float(value) for value in values if value is not None]
    return max(numeric) if numeric else None


def _air_quality() -> tuple[float | None, float | None]:
    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}"
        "&current=us_aqi,pm2_5&timezone=Asia/Shanghai"
    )
    current = _json(url).get("current") or {}
    aqi = current.get("us_aqi")
    pm25 = current.get("pm2_5")
    return (float(aqi) if aqi is not None else None,
            float(pm25) if pm25 is not None else None)


def _cached_air_quality() -> tuple[float | None, float | None]:
    now = time.time()
    have_value = _air_cache["aqi"] is not None or _air_cache["pm25"] is not None
    if have_value and now - float(_air_cache["ts"]) < AIR_TTL:
        return _air_cache["aqi"], _air_cache["pm25"]  # type: ignore[return-value]
    if now - float(_air_cache["attempt_ts"]) < AIR_RETRY_SEC:
        return _air_cache["aqi"], _air_cache["pm25"]  # type: ignore[return-value]

    _air_cache["attempt_ts"] = now
    try:
        aqi, pm25 = _air_quality()
        if aqi is not None:
            _air_cache["aqi"] = aqi
        if pm25 is not None:
            _air_cache["pm25"] = pm25
        if aqi is not None or pm25 is not None:
            _air_cache["ts"] = now
    except Exception:
        pass
    return _air_cache["aqi"], _air_cache["pm25"]  # type: ignore[return-value]


def _apply_air_quality(weather: Weather) -> Weather:
    aqi, pm25 = _cached_air_quality()
    if aqi is not None:
        weather.aqi = aqi
    if pm25 is not None:
        weather.pm25 = pm25
    return weather


def _fetch_caiyun() -> Weather:
    data = _json(f"https://api.caiyunapp.com/v2.6/{CAIYUN_KEY}/{LON},{LAT}/realtime")
    current = data["result"]["realtime"]
    label, icon = _SKYCON.get(current.get("skycon", ""), ("Cloudy", "cloud"))
    return Weather(
        temp_c=round(float(current["temperature"]), 1),
        feels_like_c=round(float(current.get("apparent_temperature", current["temperature"])), 1),
        humidity_pct=round(float(current.get("humidity", 0)) * 100),
        wind_kmh=round(float((current.get("wind") or {}).get("speed", 0)) * 3.6, 1),
        code=0, condition=label, icon=icon, city=CITY,
    )


def _fetch_openmeteo() -> Weather:
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,cloud_cover,precipitation,wind_speed_10m"
        "&hourly=precipitation_probability&forecast_hours=3&timezone=Asia/Shanghai"
    )
    data = _json(url)
    current = data["current"]
    code = int(current["weather_code"])
    label, icon = _condition(
        code, float(current.get("cloud_cover") or 0), float(current.get("precipitation") or 0)
    )
    probabilities = (data.get("hourly") or {}).get("precipitation_probability") or []
    numeric = [float(value) for value in probabilities if value is not None]
    return Weather(
        temp_c=round(float(current["temperature_2m"]), 1),
        feels_like_c=round(float(current["apparent_temperature"]), 1),
        humidity_pct=round(float(current["relative_humidity_2m"])),
        wind_kmh=round(float(current["wind_speed_10m"]), 1),
        rain_3h_pct=max(numeric) if numeric else None,
        code=code, condition=label, icon=icon, city=CITY,
    )


def _fetch_weather() -> Weather:
    weather = _fetch_caiyun() if CAIYUN_KEY else _fetch_openmeteo()
    if weather.rain_3h_pct is None:
        try:
            weather.rain_3h_pct = _rain_probability()
        except Exception:
            pass
    weather.rain_alert = bool(
        weather.rain_3h_pct is not None and weather.rain_3h_pct >= RAIN_ALERT_PCT
    )
    return weather


def fetch_weather() -> Weather | None:
    now = time.time()
    if _cache["weather"] is not None and now - float(_cache["ts"]) < TTL:
        return _apply_air_quality(_cache["weather"])  # type: ignore[arg-type]
    try:
        weather = _fetch_weather()
        _cache.update(weather=weather, ts=now)
        return _apply_air_quality(weather)
    except Exception:
        cached = _cache["weather"]
        return _apply_air_quality(cached) if isinstance(cached, Weather) else None
