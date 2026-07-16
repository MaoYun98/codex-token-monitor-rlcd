#include "usage_client.h"

#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_log.h"

static const char *TAG = "usage_client";
#define MAX_RESP_BYTES (8 * 1024)

typedef struct {
    char *buf;
    int len;
    int cap;
} resp_t;

static esp_err_t http_evt(esp_http_client_event_t *ev)
{
    if (ev->event_id == HTTP_EVENT_ON_DATA) {
        resp_t *r = (resp_t *)ev->user_data;
        if (r->len + ev->data_len < r->cap) {
            memcpy(r->buf + r->len, ev->data, ev->data_len);
            r->len += ev->data_len;
            r->buf[r->len] = 0;
        }
    }
    return ESP_OK;
}

static void copy_json_string(const cJSON *obj, const char *key, char *out, size_t size)
{
    const cJSON *value = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (cJSON_IsString(value) && size > 0) {
        strncpy(out, value->valuestring, size - 1);
        out[size - 1] = 0;
    }
}

static void parse_window(const cJSON *obj, usage_rate_window_t *out)
{
    if (!cJSON_IsObject(obj)) return;
    const cJSON *remaining = cJSON_GetObjectItemCaseSensitive(obj, "remaining_percent");
    const cJSON *reset = cJSON_GetObjectItemCaseSensitive(obj, "reset_minutes");
    copy_json_string(obj, "label", out->label, sizeof(out->label));
    out->remaining_pct = cJSON_IsNumber(remaining) ? (int32_t)(remaining->valuedouble + 0.5) : -1;
    out->reset_minutes = cJSON_IsNumber(reset) ? (int32_t)reset->valueint : -1;
    out->valid = cJSON_IsNumber(remaining);
}

esp_err_t usage_client_fetch(const char *url, const char *token, usage_report_t *out)
{
    memset(out, 0, sizeof(*out));
    char *buf = (char *)malloc(MAX_RESP_BYTES);
    if (!buf) return ESP_ERR_NO_MEM;
    resp_t response = {.buf = buf, .len = 0, .cap = MAX_RESP_BYTES};
    buf[0] = 0;

    esp_http_client_config_t cfg = {
        .url = url,
        .event_handler = http_evt,
        .user_data = &response,
        .timeout_ms = 15000,
    };
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (token && token[0]) esp_http_client_set_header(client, "X-RLCD-Token", token);
    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    if (err != ESP_OK || status / 100 != 2) {
        ESP_LOGW(TAG, "GET failed err=%s status=%d", esp_err_to_name(err), status);
        free(buf);
        return ESP_FAIL;
    }

    cJSON *root = cJSON_Parse(buf);
    free(buf);
    if (!root) return ESP_ERR_INVALID_RESPONSE;

    copy_json_string(root, "updated_at", out->updated_at, sizeof(out->updated_at));
    copy_json_string(root, "updated_hm", out->updated_hm, sizeof(out->updated_hm));
    out->stale = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root, "stale"));

    const cJSON *codex = cJSON_GetObjectItemCaseSensitive(root, "codex");
    if (!cJSON_IsObject(codex)) {
        cJSON_Delete(root);
        return ESP_ERR_INVALID_RESPONSE;
    }
    parse_window(cJSON_GetObjectItemCaseSensitive(codex, "primary"), &out->codex.primary);
    parse_window(cJSON_GetObjectItemCaseSensitive(codex, "secondary"), &out->codex.secondary);
    const cJSON *today = cJSON_GetObjectItemCaseSensitive(codex, "today_tokens");
    const cJSON *task = cJSON_GetObjectItemCaseSensitive(codex, "latest_task_tokens");
    const cJSON *context = cJSON_GetObjectItemCaseSensitive(codex, "latest_context_window");
    const cJSON *focus = cJSON_GetObjectItemCaseSensitive(codex, "focus_minutes");
    const cJSON *credits = cJSON_GetObjectItemCaseSensitive(codex, "credits_balance");
    out->codex.today_tokens = cJSON_IsNumber(today) ? (int64_t)today->valuedouble : 0;
    out->codex.latest_task_tokens = cJSON_IsNumber(task) ? (int64_t)task->valuedouble : 0;
    out->codex.latest_context_window = cJSON_IsNumber(context) ? (int64_t)context->valuedouble : 0;
    out->codex.focus_minutes = cJSON_IsNumber(focus) ? (int32_t)focus->valueint : 0;
    out->codex.credits_balance = cJSON_IsNumber(credits) ? credits->valuedouble : 0;
    out->codex.credits_valid = cJSON_IsNumber(credits);
    copy_json_string(codex, "plan_type", out->codex.plan_type, sizeof(out->codex.plan_type));
    copy_json_string(codex, "status", out->codex.status, sizeof(out->codex.status));
    out->codex.valid = out->codex.primary.valid || out->codex.secondary.valid;

    const cJSON *weather = cJSON_GetObjectItemCaseSensitive(root, "weather");
    if (cJSON_IsObject(weather)) {
        const cJSON *temp = cJSON_GetObjectItemCaseSensitive(weather, "temp_c");
        const cJSON *feels = cJSON_GetObjectItemCaseSensitive(weather, "feels_like_c");
        const cJSON *humidity = cJSON_GetObjectItemCaseSensitive(weather, "humidity_pct");
        const cJSON *wind = cJSON_GetObjectItemCaseSensitive(weather, "wind_kmh");
        const cJSON *aqi = cJSON_GetObjectItemCaseSensitive(weather, "aqi");
        const cJSON *pm25 = cJSON_GetObjectItemCaseSensitive(weather, "pm25");
        const cJSON *rain = cJSON_GetObjectItemCaseSensitive(weather, "rain_3h_pct");
        const cJSON *code = cJSON_GetObjectItemCaseSensitive(weather, "code");
        out->weather.temp_c = cJSON_IsNumber(temp) ? temp->valuedouble : 0;
        out->weather.feels_like_c = cJSON_IsNumber(feels) ? feels->valuedouble : 0;
        out->weather.humidity_pct = cJSON_IsNumber(humidity) ? humidity->valuedouble : 0;
        out->weather.wind_kmh = cJSON_IsNumber(wind) ? wind->valuedouble : 0;
        out->weather.aqi = cJSON_IsNumber(aqi) ? aqi->valuedouble : -1;
        out->weather.pm25 = cJSON_IsNumber(pm25) ? pm25->valuedouble : -1;
        out->weather.rain_3h_pct = cJSON_IsNumber(rain) ? rain->valuedouble : -1;
        out->weather.code = cJSON_IsNumber(code) ? code->valueint : 0;
        copy_json_string(weather, "condition", out->weather.condition, sizeof(out->weather.condition));
        copy_json_string(weather, "icon", out->weather.icon, sizeof(out->weather.icon));
        copy_json_string(weather, "city", out->weather.city, sizeof(out->weather.city));
        out->weather.rain_alert = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(weather, "rain_alert"));
        out->weather.valid = cJSON_IsNumber(temp);
    }

    const cJSON *github = cJSON_GetObjectItemCaseSensitive(root, "github");
    if (cJSON_IsObject(github)) {
        const cJSON *reviews = cJSON_GetObjectItemCaseSensitive(github, "review_requests");
        const cJSON *failures = cJSON_GetObjectItemCaseSensitive(github, "failing_workflows");
        const cJSON *repositories = cJSON_GetObjectItemCaseSensitive(github, "repositories");
        out->github.review_requests = cJSON_IsNumber(reviews) ? reviews->valueint : 0;
        out->github.failing_workflows = cJSON_IsNumber(failures) ? failures->valueint : 0;
        out->github.repositories = cJSON_IsNumber(repositories) ? repositories->valueint : 0;
        out->github.valid = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(github, "valid"));
    }

    cJSON_Delete(root);
    return ESP_OK;
}
