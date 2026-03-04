"""GHL webhook handler — generic, vertical-driven."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.models import WebhookResponse
from app.services import bot_engine, config_loader
from app.services.ghl_client import GHLClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])

_ghl: Optional[GHLClient] = None


def _get_ghl() -> Optional[GHLClient]:
    global _ghl
    if _ghl is None and settings.ghl_api_key and settings.ghl_location_id:
        _ghl = GHLClient()
    return _ghl


def verify_signature(payload: bytes, signature: Optional[str]) -> bool:
    """Verify GHL webhook HMAC signature when a secret is configured."""
    if not settings.ghl_webhook_secret:
        return True  # No secret configured — skip verification
    if not signature:
        return False
    expected = hmac.new(
        settings.ghl_webhook_secret.encode(), payload, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/api/ghl/webhook", response_model=WebhookResponse)
async def ghl_webhook(request: Request) -> WebhookResponse:
    """Receive a GHL webhook, generate a bot response, and reply via SMS."""
    payload_bytes = await request.body()
    sig = request.headers.get("x-wh-signature") or request.headers.get("X-HighLevel-Signature")

    if not verify_signature(payload_bytes, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    payload: Dict[str, Any] = json.loads(payload_bytes)

    contact_id = payload.get("contactId") or payload.get("contact_id") or payload.get("id")
    message_body = payload.get("body") or payload.get("message") or ""

    if not contact_id:
        return WebhookResponse(status="error", detail="missing contactId")

    if not message_body.strip():
        return WebhookResponse(status="skipped", contact_id=contact_id, detail="empty message")

    # Truncate overly long messages
    if len(message_body) > 2000:
        message_body = message_body[:2000]

    # Load the active vertical
    try:
        vertical = config_loader.load_vertical(settings.active_vertical)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load vertical: %s", exc)
        return WebhookResponse(status="error", detail=str(exc))

    contact_info = {
        "name": payload.get("fullName") or payload.get("name"),
        "email": payload.get("email"),
        "phone": payload.get("phone"),
    }

    result = await bot_engine.generate_response(
        vertical=vertical,
        user_message=message_body,
        contact_info=contact_info,
    )

    response_text: str = result["response"]
    sent = False

    ghl = _get_ghl()
    if ghl and response_text:
        try:
            await ghl.send_message(contact_id, response_text, "SMS")
            sent = True
        except Exception as exc:
            logger.error("Failed to send GHL SMS to %s: %s", contact_id, exc)

    return WebhookResponse(
        status="processed",
        contact_id=contact_id,
        response_sent=sent,
        vertical=vertical.name,
    )
