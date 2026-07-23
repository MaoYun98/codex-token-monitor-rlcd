#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>
#include <esp_adc/adc_oneshot.h>
#include <esp_adc/adc_cali.h>
#include <esp_adc/adc_cali_scheme.h>
#include <driver/usb_serial_jtag.h>

#include "user_app.h"
#include "wifi_app.h"
#include "ntp.h"
#include "shtc3.h"
#include "usage_client.h"
#include "ui_app.h"
#include "lvgl_bsp.h"

static const char *TAG = "user_app";
static char wifi_ssid[33] = "--";
static adc_oneshot_unit_handle_t battery_adc;
static adc_cali_handle_t battery_cali;
static bool battery_ready;
static bool battery_calibrated;
static int battery_trend_mv;
static TickType_t battery_trend_tick;
static bool battery_rising;

static void battery_init(void)
{
    adc_oneshot_unit_init_cfg_t unit_cfg = {};
    unit_cfg.unit_id = ADC_UNIT_1;
    if (adc_oneshot_new_unit(&unit_cfg, &battery_adc) != ESP_OK) return;

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_oneshot_config_channel(battery_adc, ADC_CHANNEL_3, &chan_cfg) != ESP_OK) return;
    battery_ready = true;

#if ADC_CALI_SCHEME_CURVE_FITTING_SUPPORTED
    adc_cali_curve_fitting_config_t cali_cfg = {
        .unit_id = ADC_UNIT_1,
        .chan = ADC_CHANNEL_3,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    battery_calibrated = adc_cali_create_scheme_curve_fitting(&cali_cfg, &battery_cali) == ESP_OK;
#endif
}

static int battery_percent_from_mv(int mv)
{
    static const int volts[] = {3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100, 4200};
    static const int pct[] =   {   0,    5,   15,   30,   50,   65,   80,   90,  100};
    if (mv <= volts[0]) return 0;
    if (mv >= volts[8]) return 100;
    for (int i = 1; i < 9; ++i) {
        if (mv <= volts[i]) {
            return pct[i - 1] + (mv - volts[i - 1]) * (pct[i] - pct[i - 1]) /
                   (volts[i] - volts[i - 1]);
        }
    }
    return 100;
}

static bool battery_read(int *percent, int *millivolts)
{
    if (!battery_ready || !percent || !millivolts) return false;
    int sum = 0;
    for (int i = 0; i < 16; ++i) {
        int raw = 0;
        if (adc_oneshot_read(battery_adc, ADC_CHANNEL_3, &raw) != ESP_OK) return false;
        sum += raw;
    }
    int raw = sum / 16;
    int adc_mv = 0;
    if (battery_calibrated) {
        if (adc_cali_raw_to_voltage(battery_cali, raw, &adc_mv) != ESP_OK) return false;
    } else {
        adc_mv = raw * 3100 / 4095;
    }
    const int battery_mv = adc_mv * 3;
    if (battery_mv < 2500) return false;
    *millivolts = battery_mv;
    *percent = battery_percent_from_mv(battery_mv);
    static bool logged;
    if (!logged) {
        ESP_LOGI(TAG, "battery %dmV, estimated %d%%", battery_mv, *percent);
        logged = true;
    }
    return true;
}

static bool battery_is_charging(int battery_mv, int percent)
{
    TickType_t now = xTaskGetTickCount();
    if (battery_trend_tick == 0) {
        battery_trend_mv = battery_mv;
        battery_trend_tick = now;
    } else if (now - battery_trend_tick >= pdMS_TO_TICKS(60000)) {
        int delta_mv = battery_mv - battery_trend_mv;
        if (delta_mv >= 8) battery_rising = true;
        else if (delta_mv <= -3) battery_rising = false;
        battery_trend_mv = battery_mv;
        battery_trend_tick = now;
    }

    bool usb_host_power = usb_serial_jtag_is_connected();
    return percent < 100 && (usb_host_power || battery_rising);
}

typedef struct {
    char url[160];
    char token[80];
    int  poll_sec;
} poll_cfg_t;

// Clock + indoor sensor: cheap, update every 10s independent of the HTTP poll.
static void clock_task(void *arg)
{
    (void) arg;
    for (;;) {
        char hm[8];
        char date[24];
        ntp_now_hm(hm, sizeof(hm));
        ntp_now_date(date, sizeof(date));
        float t = 0, h = 0;
        bool ok = (shtc3_read(&t, &h) == ESP_OK);
        int8_t rssi = 0;
        bool wifi_ok = (wifi_app_get_rssi(&rssi) == ESP_OK);
        int battery_percent = 0;
        int battery_mv = 0;
        bool battery_ok = battery_read(&battery_percent, &battery_mv);
        bool charging = battery_ok && battery_is_charging(battery_mv, battery_percent);
        if (Lvgl_lock(-1)) {
            ui_app_set_time(hm);
            ui_app_set_date(date);
            ui_app_set_env(t, h, ok);
            ui_app_set_wifi_status(wifi_ssid, rssi, wifi_ok);
            ui_app_set_battery(battery_percent, battery_ok, charging);
            Lvgl_unlock();
        }
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}

static void usage_poll_task(void *arg)
{
    poll_cfg_t *cfg = (poll_cfg_t *) arg;
    for (;;) {
        usage_report_t rep;
        esp_err_t err = usage_client_fetch(cfg->url, cfg->token, &rep);
        if (Lvgl_lock(-1)) {
            if (err == ESP_OK) ui_app_update(&rep);
            else { ESP_LOGW(TAG, "fetch failed: %s", esp_err_to_name(err)); ui_app_mark_stale(); }
            Lvgl_unlock();
        }
        vTaskDelay(pdMS_TO_TICKS(cfg->poll_sec * 1000));
    }
}

void UserApp_AppInit(const char *ssid, const char *password)
{
    strncpy(wifi_ssid, ssid, sizeof(wifi_ssid) - 1);
    ESP_LOGI(TAG, "connecting to '%s' ...", ssid);
    wifi_app_connect_blocking(ssid, password);
    ntp_start();
    if (shtc3_init() != ESP_OK) ESP_LOGW(TAG, "shtc3 init failed");
    battery_init();
}

void UserApp_UiInit(void)
{
    ui_app_init();
}

void UserApp_TaskInit(const char *bridge_url, const char *token, int poll_sec)
{
    poll_cfg_t *cfg = (poll_cfg_t *) calloc(1, sizeof(*cfg));
    strncpy(cfg->url, bridge_url, sizeof(cfg->url) - 1);
    if (token) strncpy(cfg->token, token, sizeof(cfg->token) - 1);
    cfg->poll_sec = poll_sec > 0 ? poll_sec : 60;
    xTaskCreatePinnedToCore(usage_poll_task, "usage_poll", 6 * 1024, cfg, 4, NULL, 1);
    xTaskCreatePinnedToCore(clock_task, "clock", 4 * 1024, NULL, 3, NULL, 1);
}
