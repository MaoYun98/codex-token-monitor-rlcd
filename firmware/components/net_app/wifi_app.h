#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include "esp_err.h"
#include <stdint.h>

// Initialize WiFi STA and block until we get an IPv4 address.
// Auto-reconnects on disconnect (handled in event_handler).
esp_err_t wifi_app_connect_blocking(const char *ssid, const char *password);
// Read current station RSSI in dBm.
esp_err_t wifi_app_get_rssi(int8_t *rssi);

#ifdef __cplusplus
}
#endif
