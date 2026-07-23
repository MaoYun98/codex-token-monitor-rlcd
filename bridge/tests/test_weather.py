import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import weather


class WeatherTests(unittest.TestCase):
    def setUp(self):
        weather._cache.update(weather=None, ts=0.0)
        weather._air_cache.update(aqi=None, pm25=None, ts=0.0, attempt_ts=0.0)

    def test_openmeteo_weather_includes_air_and_rain_alert(self):
        forecast = {
            "current": {
                "temperature_2m": 31.2,
                "apparent_temperature": 35.0,
                "relative_humidity_2m": 60,
                "weather_code": 2,
                "cloud_cover": 40,
                "precipitation": 0,
                "wind_speed_10m": 9.5,
            },
            "hourly": {"precipitation_probability": [10, 45, 30]},
        }
        air = {"current": {"us_aqi": 88, "pm2_5": 27.4}}
        with patch.object(weather, "_json", side_effect=[forecast, air]):
            value = weather.fetch_weather()
        self.assertEqual(value.rain_3h_pct, 45)
        self.assertTrue(value.rain_alert)
        self.assertEqual(value.aqi, 88)
        self.assertEqual(value.pm25, 27.4)

    def test_low_rain_probability_keeps_alert_off(self):
        forecast = {
            "current": {
                "temperature_2m": 20,
                "apparent_temperature": 20,
                "relative_humidity_2m": 40,
                "weather_code": 0,
                "cloud_cover": 5,
                "precipitation": 0,
                "wind_speed_10m": 12,
            },
            "hourly": {"precipitation_probability": [0, 10, 20]},
        }
        with patch.object(weather, "_json", side_effect=[forecast, {"current": {}}]):
            value = weather.fetch_weather()
        self.assertFalse(value.rain_alert)

    def test_air_quality_retries_separately_and_keeps_last_valid_values(self):
        forecast = weather.Weather(temp_c=20, condition="Clear", icon="clear", city="BEIJING")
        with patch.object(weather, "_fetch_openmeteo", return_value=forecast), \
             patch.object(weather, "_air_quality", side_effect=[OSError("temporary"), (88, 27.4)]):
            with patch.object(weather.time, "time", return_value=100):
                first = weather.fetch_weather()
            self.assertIsNone(first.aqi)

            with patch.object(weather.time, "time", return_value=161):
                second = weather.fetch_weather()
        self.assertEqual(second.aqi, 88)
        self.assertEqual(second.pm25, 27.4)

        weather._air_cache.update(ts=0.0, attempt_ts=0.0)
        with patch.object(weather, "_air_quality", side_effect=OSError("temporary")), \
             patch.object(weather.time, "time", return_value=1000):
            third = weather.fetch_weather()
        self.assertEqual(third.aqi, 88)
        self.assertEqual(third.pm25, 27.4)

if __name__ == "__main__":
    unittest.main()
