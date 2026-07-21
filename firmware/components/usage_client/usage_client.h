#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

typedef struct {
    char    label[8];
    int32_t remaining_pct;
    int32_t reset_minutes;
    bool    valid;
} usage_rate_window_t;

typedef struct {
    usage_rate_window_t primary;
    usage_rate_window_t secondary;
    int64_t today_tokens;
    int64_t latest_task_tokens;
    int64_t latest_context_window;
    int32_t focus_minutes;
    double  credits_balance;
    char    plan_type[16];
    char    status[16];
    bool    credits_valid;
    bool    valid;
} usage_codex_t;

typedef struct {
    double  temp_c;
    double  feels_like_c;
    double  humidity_pct;
    double  wind_kmh;
    double  aqi;
    double  pm25;
    double  rain_3h_pct;
    int32_t code;
    char    condition[16];
    char    icon[10];
    char    city[16];
    bool    rain_alert;
    bool    valid;
} usage_weather_t;

typedef struct {
    int32_t review_requests;
    int32_t failing_workflows;
    int32_t repositories;
    bool    valid;
} usage_github_t;

typedef struct {
    char            updated_at[32];
    char            updated_hm[8];
    usage_codex_t   codex;
    usage_weather_t weather;
    usage_github_t  github;
    bool            stale;
} usage_report_t;

// `token` may be NULL or empty for no auth; otherwise sent as X-RLCD-Token.
esp_err_t usage_client_fetch(const char *url, const char *token, usage_report_t *out);

#ifdef __cplusplus
}
#endif
