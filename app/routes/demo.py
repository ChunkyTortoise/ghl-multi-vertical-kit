"""Demo endpoint — simulated conversations without GHL."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.models import DemoRequest, DemoResponse
from app.services import bot_engine, config_loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])


@router.post("/demo", response_model=DemoResponse)
async def demo_chat(req: DemoRequest) -> DemoResponse:
    """Simulate a bot conversation for any loaded vertical.

    No GHL keys required — just an Anthropic API key.
    """
    try:
        vertical = config_loader.load_vertical(req.vertical)
    except FileNotFoundError as exc:
        available = config_loader.list_verticals()
        raise HTTPException(
            status_code=404,
            detail=f"Vertical '{req.vertical}' not found. Available: {available}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = await bot_engine.generate_response(
        vertical=vertical,
        user_message=req.user_message,
        conversation_history=req.conversation_history,
        contact_info=req.contact_info,
    )

    return DemoResponse(
        vertical=vertical.name,
        bot_name=vertical.persona.name,
        response=result["response"],
        qualification_progress=result.get("qualification_progress", {}),
        model=result.get("model", ""),
    )


@router.get("/verticals", response_model=List[str])
async def list_verticals() -> List[str]:
    """Return names of all available verticals."""
    return config_loader.list_verticals()
