# Firmware

ESP-IDF 5.x + LVGL 9 firmware for the 400x300 Waveshare
ESP32-S3-RLCD-4.2.

The display has three update paths:

- HTTP every `RLCD_POLL_SEC`: Codex limits and Beijing weather;
- SNTP every 10 seconds: local Beijing time and date;
- onboard SHTC3 every 10 seconds: indoor temperature and humidity.

Build from an ESP-IDF PowerShell:

```powershell
Copy-Item main\secrets.h.example main\secrets.h
notepad main\secrets.h
idf.py set-target esp32s3
idf.py build flash monitor
```

Use `?mock=1` on `RLCD_BRIDGE_URL` for the first flash. The device only needs
2.4 GHz Wi-Fi and LAN access to the bridge host.

Vendor pin assignments remain in `main/user_config.h`; the panel and LVGL BSP
remain under `components/port_bsp` and `components/app_bsp`.
