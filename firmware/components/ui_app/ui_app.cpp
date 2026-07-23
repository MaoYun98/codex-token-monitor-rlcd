// 400x300 one-bit dashboard for Codex allowance and Beijing weather.
#include "ui_app.h"
#include "icons.h"
#include "lvgl.h"
#include <stdio.h>
#include <string.h>

LV_FONT_DECLARE(font_amt14);
#define INK lv_color_black()
#define WHITE lv_color_white()

static lv_obj_t *lbl_time, *lbl_date, *lbl_indoor;
static lv_obj_t *lbl_battery, *lbl_wifi;
static lv_obj_t *img_wx_detail;
static lv_obj_t *bar_primary, *bar_secondary;
static lv_obj_t *lbl_primary_name, *lbl_secondary_name;
static lv_obj_t *lbl_primary_pct, *lbl_secondary_pct, *lbl_reset;
static lv_obj_t *lbl_today, *lbl_focus, *lbl_work_name, *lbl_work;
static lv_obj_t *lbl_wx_temp, *lbl_wx_condition, *lbl_aqi, *lbl_pm25, *lbl_dynamic;
static lv_obj_t *img_dynamic, *lbl_status;
static char last_sync[8] = "--:--";
static int wifi_rssi;
static bool wifi_ok, bridge_stale = true;

static void fmt_tok(char *out, size_t size, int64_t tokens)
{
    if (tokens >= 1000000000LL) snprintf(out, size, "%.1fB", tokens / 1e9);
    else if (tokens >= 10000000LL) snprintf(out, size, "%.0fM", tokens / 1e6);
    else if (tokens >= 1000000LL) snprintf(out, size, "%.1fM", tokens / 1e6);
    else if (tokens >= 1000LL) snprintf(out, size, "%.0fk", tokens / 1e3);
    else snprintf(out, size, "%lld", (long long)tokens);
}

static lv_obj_t *mklabel(lv_obj_t *parent, int x, int y, const lv_font_t *font, const char *text)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, INK, 0);
    lv_obj_set_pos(label, x, y);
    lv_label_set_text(label, text);
    return label;
}

static lv_obj_t *mkalign(lv_obj_t *parent, int x, int y, int width, lv_text_align_t align,
                         const lv_font_t *font, const char *text)
{
    lv_obj_t *label = mklabel(parent, x, y, font, text);
    lv_obj_set_width(label, width);
    lv_obj_set_style_text_align(label, align, 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    return label;
}

static void mkdiv(lv_obj_t *parent, int x, int y, int width, int height)
{
    lv_obj_t *line = lv_obj_create(parent);
    lv_obj_remove_style_all(line);
    lv_obj_set_pos(line, x, y);
    lv_obj_set_size(line, width, height);
    lv_obj_set_style_bg_color(line, INK, 0);
    lv_obj_set_style_bg_opa(line, LV_OPA_COVER, 0);
}

static lv_obj_t *mkbar(lv_obj_t *parent, int x, int y, int width)
{
    lv_obj_t *bar = lv_bar_create(parent);
    lv_obj_set_pos(bar, x, y);
    lv_obj_set_size(bar, width, 14);
    lv_bar_set_range(bar, 0, 100);
    lv_obj_set_style_radius(bar, 6, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar, WHITE, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_color(bar, INK, LV_PART_MAIN);
    lv_obj_set_style_border_width(bar, 2, LV_PART_MAIN);
    lv_obj_set_style_radius(bar, 6, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(bar, INK, LV_PART_INDICATOR);
    lv_bar_set_value(bar, 0, LV_ANIM_OFF);
    return bar;
}


static const lv_image_dsc_t *wx_icon_large(const char *key)
{
    if (!strcmp(key, "clear")) return &icon_wx_large_clear;
    if (!strcmp(key, "partly")) return &icon_wx_large_partly;
    if (!strcmp(key, "rain")) return &icon_wx_large_rain;
    if (!strcmp(key, "snow")) return &icon_wx_large_snow;
    if (!strcmp(key, "fog")) return &icon_wx_large_fog;
    return &icon_wx_large_cloud;
}

static lv_obj_t *mkicon(lv_obj_t *parent, int x, int y, const lv_image_dsc_t *source)
{
    lv_obj_t *image = lv_image_create(parent);
    lv_image_set_src(image, source);
    lv_obj_set_pos(image, x, y);
    lv_obj_set_style_image_recolor(image, INK, 0);
    lv_obj_set_style_image_recolor_opa(image, LV_OPA_COVER, 0);
    return image;
}

void ui_app_init(void)
{
    lv_obj_t *screen = lv_screen_active();
    lv_obj_set_style_bg_color(screen, WHITE, 0);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);

    lbl_time = mklabel(screen, 10, 3, &lv_font_montserrat_28, "--:--");
    lbl_date = mklabel(screen, 108, 6, &lv_font_montserrat_14, "--- --/--");
    lbl_indoor = mklabel(screen, 108, 34, &lv_font_montserrat_14, "IN --.-\xC2\xB0""C  --%RH");
    lbl_battery = mkalign(screen, 260, 7, 130, LV_TEXT_ALIGN_RIGHT,
                          &lv_font_montserrat_14, LV_SYMBOL_BATTERY_EMPTY " --%");
    lbl_wifi = mkalign(screen, 260, 34, 130, LV_TEXT_ALIGN_RIGHT,
                       &lv_font_montserrat_14, LV_SYMBOL_WIFI " WiFi--");
    mkdiv(screen, 10, 62, 380, 2);
    mkdiv(screen, 252, 72, 2, 216);

    mkicon(screen, 12, 72, &icon_codex);
    mklabel(screen, 52, 77, &lv_font_montserrat_20, "CODEX");
    mkalign(screen, 130, 79, 108, LV_TEXT_ALIGN_RIGHT, &lv_font_montserrat_14,
            "REMAINING");

    lbl_primary_name = mklabel(screen, 12, 112, &font_amt14, "7d");
    bar_primary = mkbar(screen, 48, 113, 128);
    lbl_primary_pct = mkalign(screen, 180, 110, 60, LV_TEXT_ALIGN_RIGHT, &font_amt14, "--%");
    lbl_secondary_name = mklabel(screen, 12, 142, &font_amt14, "5h");
    bar_secondary = mkbar(screen, 48, 143, 128);
    lbl_secondary_pct = mkalign(screen, 180, 140, 60, LV_TEXT_ALIGN_RIGHT, &font_amt14, "--%");
    lbl_reset = mklabel(screen, 12, 170, &lv_font_montserrat_14, "reset --");
    mkdiv(screen, 12, 194, 228, 1);

    mklabel(screen, 12, 204, &lv_font_montserrat_14, "today");
    lbl_today = mkalign(screen, 100, 204, 138, LV_TEXT_ALIGN_RIGHT, &font_amt14, "-");
    mklabel(screen, 12, 232, &lv_font_montserrat_14, "focus");
    lbl_focus = mkalign(screen, 100, 232, 138, LV_TEXT_ALIGN_RIGHT, &font_amt14, "-");
    lbl_work_name = mklabel(screen, 12, 260, &lv_font_montserrat_14, "last task");
    lbl_work = mkalign(screen, 100, 260, 138, LV_TEXT_ALIGN_RIGHT, &font_amt14, "-");

    mklabel(screen, 264, 74, &lv_font_montserrat_20, "BEIJING");
    img_wx_detail = mkicon(screen, 264, 105, &icon_wx_large_cloud);
    lbl_wx_temp = mkalign(screen, 306, 105, 84, LV_TEXT_ALIGN_CENTER,
                          &lv_font_montserrat_28, "--\xC2\xB0""C");
    lbl_wx_condition = mkalign(screen, 260, 143, 130, LV_TEXT_ALIGN_CENTER,
                               &lv_font_montserrat_14, "--");
    mkdiv(screen, 264, 170, 122, 1);
    mkicon(screen, 264, 180, &icon_metric_air);
    mkicon(screen, 264, 210, &icon_metric_particles);
    img_dynamic = mkicon(screen, 264, 240, &icon_metric_wind);
    lbl_aqi = mklabel(screen, 288, 181, &lv_font_montserrat_14, "AQI --");
    lbl_pm25 = mklabel(screen, 288, 211, &lv_font_montserrat_14, "PM2.5 --");
    lbl_dynamic = mklabel(screen, 288, 241, &lv_font_montserrat_14, "wind --km/h");
    lbl_status = mkalign(screen, 260, 271, 130, LV_TEXT_ALIGN_RIGHT,
                         &lv_font_montserrat_14, "SYNC --:--");
}

static void render_status(void)
{
    if (!lbl_status) return;

    char text[32];
    if (bridge_stale) {
        if (wifi_ok) snprintf(text, sizeof(text), "STALE  %ddBm", wifi_rssi);
        else snprintf(text, sizeof(text), "STALE  WiFi--");
    } else if (wifi_ok) {
        snprintf(text, sizeof(text), "%s  %ddBm", last_sync, wifi_rssi);
    } else {
        snprintf(text, sizeof(text), "%s  WiFi--", last_sync);
    }
    lv_label_set_text(lbl_status, text);
}

static void update_window(const usage_rate_window_t *window, lv_obj_t *name,
                          lv_obj_t *bar, lv_obj_t *percent)
{
    if (!window->valid) return;
    lv_label_set_text(name, window->label);
    lv_bar_set_value(bar, window->remaining_pct, LV_ANIM_OFF);
    char text[16];
    snprintf(text, sizeof(text), "%ld%%", (long)window->remaining_pct);
    lv_label_set_text(percent, text);
}

void ui_app_update(const usage_report_t *report)
{
    if (!report) return;
    update_window(&report->codex.primary, lbl_primary_name, bar_primary, lbl_primary_pct);
    if (report->codex.secondary.valid) {
        lv_obj_remove_flag(lbl_secondary_name, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(bar_secondary, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(lbl_secondary_pct, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_y(lbl_reset, 170);
        update_window(&report->codex.secondary, lbl_secondary_name, bar_secondary, lbl_secondary_pct);
    } else {
        lv_obj_add_flag(lbl_secondary_name, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(bar_secondary, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(lbl_secondary_pct, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_y(lbl_reset, 142);
    }

    const usage_rate_window_t *reset_window = report->codex.secondary.valid
        ? &report->codex.secondary : &report->codex.primary;
    if (reset_window->valid && reset_window->reset_minutes >= 0) {
        int minutes = reset_window->reset_minutes;
        char text[64];
        if (minutes >= 1440) snprintf(text, sizeof(text), "%s resets in %dd %dh",
                                      reset_window->label, minutes / 1440, (minutes / 60) % 24);
        else snprintf(text, sizeof(text), "%s resets in %dh %02dm",
                      reset_window->label, minutes / 60, minutes % 60);
        lv_label_set_text(lbl_reset, text);
    }

    char value[64];
    fmt_tok(value, sizeof(value), report->codex.today_tokens);
    strncat(value, " tok", sizeof(value) - strlen(value) - 1);
    lv_label_set_text(lbl_today, value);
    snprintf(value, sizeof(value), "%ldh %02ldm", (long)(report->codex.focus_minutes / 60),
             (long)(report->codex.focus_minutes % 60));
    lv_label_set_text(lbl_focus, value);
    if (report->github.valid) {
        lv_label_set_text(lbl_work_name, "GitHub");
        snprintf(value, sizeof(value), "PR %ld  CI %ld", (long)report->github.review_requests,
                 (long)report->github.failing_workflows);
    } else {
        lv_label_set_text(lbl_work_name, "last task");
        fmt_tok(value, sizeof(value), report->codex.latest_task_tokens);
        strncat(value, " tok", sizeof(value) - strlen(value) - 1);
    }
    lv_label_set_text(lbl_work, value);

    if (report->weather.valid) {
        lv_image_set_src(img_wx_detail, wx_icon_large(report->weather.icon));
        snprintf(value, sizeof(value), "%.0f\xC2\xB0""C", report->weather.temp_c);
        lv_label_set_text(lbl_wx_temp, value);
        lv_label_set_text(lbl_wx_condition, report->weather.condition);
        if (report->weather.aqi >= 0) snprintf(value, sizeof(value), "AQI %.0f", report->weather.aqi);
        else snprintf(value, sizeof(value), "AQI --");
        lv_label_set_text(lbl_aqi, value);
        if (report->weather.pm25 >= 0) snprintf(value, sizeof(value), "PM2.5 %.0f", report->weather.pm25);
        else snprintf(value, sizeof(value), "PM2.5 --");
        lv_label_set_text(lbl_pm25, value);
        if (report->weather.rain_alert && report->weather.rain_3h_pct >= 0) {
            lv_image_set_src(img_dynamic, &icon_metric_rain);
            snprintf(value, sizeof(value), "rain3h %.0f%%", report->weather.rain_3h_pct);
        } else {
            lv_image_set_src(img_dynamic, &icon_metric_wind);
            snprintf(value, sizeof(value), "wind %.0fkm/h", report->weather.wind_kmh);
        }
        lv_label_set_text(lbl_dynamic, value);
    }

    strncpy(last_sync, report->updated_hm, sizeof(last_sync) - 1);
    last_sync[sizeof(last_sync) - 1] = 0;
    bridge_stale = report->stale;
    render_status();
}

void ui_app_set_env(float temp_c, float humidity, bool ok)
{
    char text[48];
    if (ok) snprintf(text, sizeof(text), "IN %.1f\xC2\xB0""C  %.0f%%RH", temp_c, humidity);
    else snprintf(text, sizeof(text), "IN --");
    lv_label_set_text(lbl_indoor, text);
}

void ui_app_set_time(const char *hm) { if (lbl_time) lv_label_set_text(lbl_time, hm); }
void ui_app_set_date(const char *date) { if (lbl_date) lv_label_set_text(lbl_date, date); }
void ui_app_set_wifi_status(const char *ssid, int8_t rssi, bool ok)
{
    wifi_rssi = rssi;
    wifi_ok = ok;
    char text[40];
    if (ok && ssid && ssid[0]) snprintf(text, sizeof(text), LV_SYMBOL_WIFI " %.20s", ssid);
    else snprintf(text, sizeof(text), LV_SYMBOL_WIFI " WiFi--");
    lv_label_set_text(lbl_wifi, text);
    render_status();
}
void ui_app_set_battery(int percent, bool ok, bool charging)
{
    char text[24];
    if (!ok) {
        snprintf(text, sizeof(text), LV_SYMBOL_BATTERY_EMPTY " --%%");
    } else {
        const char *symbol = percent >= 90 ? LV_SYMBOL_BATTERY_FULL
                           : percent >= 65 ? LV_SYMBOL_BATTERY_3
                           : percent >= 40 ? LV_SYMBOL_BATTERY_2
                           : percent >= 15 ? LV_SYMBOL_BATTERY_1
                                           : LV_SYMBOL_BATTERY_EMPTY;
        snprintf(text, sizeof(text), "%s%s %d%%", symbol,
                 charging ? " " LV_SYMBOL_CHARGE : "", percent);
    }
    lv_label_set_text(lbl_battery, text);
}
void ui_app_mark_stale(void)
{
    bridge_stale = true;
    render_status();
}
