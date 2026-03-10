# GHL Multi-Vertical Kit

## Stack
FastAPI | PyYAML | Anthropic (claude-sonnet-4-6) | Redis | Python

## Architecture
YAML-driven bot framework — swap verticals via `ACTIVE_VERTICAL` env var. 3 built-in verticals: `real_estate` (Alex), `home_services` (Sam), `legal` (Jordan). `/demo` endpoint works without GHL credentials. Conversation persistence via Redis.
- `app/main.py` — FastAPI entry point
- `verticals/` — YAML config per vertical
- `app/services/` — bot logic, GHL client, Redis persistence
- `Dockerfile` + `render.yaml` — Render deploy blueprint

## Deploy
Not yet deployed. Blueprint: `render.yaml`. Target: Render.

## Test
```pytest tests/  # 87 tests```

## Key Env
ANTHROPIC_API_KEY, GHL_API_KEY, GHL_LOCATION_ID, ACTIVE_VERTICAL, REDIS_URL
