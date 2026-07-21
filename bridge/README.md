# Codex RLCD Bridge

FastAPI service that exposes a compact workbench payload for the ESP32 display:

- local Codex allowance, token totals, and estimated focus time;
- Beijing weather, AQI, PM2.5, and 3-hour rain probability;
- optional GitHub review-request and failing-workflow counts.

Endpoints:

- `GET /api/usage` — cached live workbench data;
- `GET /api/usage?mock=1` — deterministic UI bring-up data;
- `GET /healthz` — liveness and cache age.

Copy `.env.example` to `.env`. The Windows launcher loads it automatically;
systemd uses it as an `EnvironmentFile`.

The GitHub module is disabled unless both `GITHUB_TOKEN` and
`RLCD_GITHUB_REPOS` are set. Use a fine-grained, read-only token limited to the
selected repositories, with metadata, pull-request, and Actions read access.
The token is used only by the bridge and is never returned to the ESP32.
