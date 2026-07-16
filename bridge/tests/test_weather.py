import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import weather


class WeatherTests(unittest.TestCase):
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
            value = weather._fetch_weather()
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
            value = weather._fetch_weather()
        self.assertFalse(value.rain_alert)


if __name__ == "__main__":
    unittest.main()
