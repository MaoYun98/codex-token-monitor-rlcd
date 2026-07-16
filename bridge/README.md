# Codex RLCD Bridge

FastAPI service that reads local Codex session JSONL files and exposes a small,
credential-free payload for the ESP32 display.

Endpoints:

- `GET /api/usage` — cached live Codex and Beijing weather data;
- `GET /api/usage?mock=1` — deterministic UI bring-up data;
- `GET /healthz` — liveness and cache age.

Important environment variables are documented in `.env.example`. The server
does not load that file itself; export the variables in your shell or service
manager before starting it.
