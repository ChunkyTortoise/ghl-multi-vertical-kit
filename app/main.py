"""FastAPI entry point for the GHL Multi-Vertical AI Bot Kit."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import settings
from app.models import HealthResponse
from app.routes.demo import router as demo_router
from app.routes.webhook import router as webhook_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="GHL Multi-Vertical AI Bot",
    description="A configurable GHL AI bot framework — swap verticals by changing a YAML file.",
    version="1.0.0",
)

app.include_router(webhook_router)
app.include_router(demo_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        vertical=settings.active_vertical,
        ghl_configured=bool(settings.ghl_api_key and settings.ghl_location_id),
        environment=settings.environment,
    )
