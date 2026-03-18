"""Demo endpoint — simulated conversations without GHL."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models import DemoRequest, DemoResponse
from app.services import bot_engine, config_loader
from app.services.conversation_store import (
    append_message,
    clear_history,
    get_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/demo/ui", include_in_schema=False)
async def demo_ui() -> FileResponse:
    """Serve the interactive demo HTML page."""
    html_path = _STATIC_DIR / "demo.html"
    return FileResponse(html_path, media_type="text/html")


@router.get("/demo/config/{vertical_name}")
async def demo_config(vertical_name: str) -> Dict[str, Any]:
    """Return config and rendered system prompt for a vertical."""
    try:
        vertical = config_loader.load_vertical(vertical_name)
    except FileNotFoundError as exc:
        available = config_loader.list_verticals()
        raise HTTPException(
            status_code=404,
            detail=f"Vertical '{vertical_name}' not found. Available: {available}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "name": vertical.name,
        "bot_name": vertical.persona.name,
        "tone": vertical.persona.tone,
        "greeting": vertical.persona.greeting,
        "qualification_questions": vertical.qualification_questions,
        "disqualification_criteria": vertical.disqualification_criteria,
        "booking_enabled": vertical.booking_enabled,
        "response_templates": vertical.response_templates,
        "system_prompt_rendered": bot_engine.build_system_prompt(vertical),
    }


@router.post("/demo", response_model=DemoResponse)
async def demo_chat(req: DemoRequest) -> DemoResponse:
    """Simulate a bot conversation for any loaded vertical.

    No GHL keys required — just an Anthropic API key.

    If ``contact_id`` is provided in ``contact_info``, conversation history
    is persisted across requests (Redis or in-memory fallback).  Otherwise
    the ``conversation_history`` list from the request body is used as-is.
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

    contact_id: Optional[str] = req.contact_info.get("contact_id")

    # If a contact_id is present, load persisted history
    if contact_id:
        history = await get_history(contact_id)
        # Merge any explicitly-passed history (first call may seed it)
        if not history and req.conversation_history:
            history = list(req.conversation_history)
    else:
        history = list(req.conversation_history)

    result = await bot_engine.generate_response(
        vertical=vertical,
        user_message=req.user_message,
        conversation_history=history,
        contact_info=req.contact_info,
    )

    # Persist the new turn
    if contact_id:
        await append_message(contact_id, "user", req.user_message)
        await append_message(contact_id, "assistant", result["response"])

    return DemoResponse(
        vertical=vertical.name,
        bot_name=vertical.persona.name,
        response=result["response"],
        qualification_progress=result.get("qualification_progress", {}),
        model=result.get("model", ""),
    )


@router.delete("/demo/history/{contact_id}")
async def delete_history(contact_id: str) -> dict:
    """Clear persisted conversation history for a contact."""
    await clear_history(contact_id)
    return {"status": "cleared", "contact_id": contact_id}


@router.get("/verticals", response_model=List[str])
async def list_verticals() -> List[str]:
    """Return names of all available verticals."""
    return config_loader.list_verticals()
