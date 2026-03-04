"""Pydantic models for request/response schemas and vertical config."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Vertical YAML schema
# ---------------------------------------------------------------------------

class PersonaConfig(BaseModel):
    name: str = "Assistant"
    tone: str = "professional and friendly"
    greeting: str = "Hi there! How can I help you today?"


class VerticalConfig(BaseModel):
    """Schema for a vertical YAML file."""

    name: str
    persona: PersonaConfig
    qualification_questions: List[str] = Field(default_factory=list)
    disqualification_criteria: List[str] = Field(default_factory=list)
    booking_enabled: bool = False
    system_prompt: str = ""
    response_templates: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class DemoRequest(BaseModel):
    vertical: str = "real_estate"
    user_message: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    contact_info: Dict[str, Any] = Field(default_factory=dict)


class DemoResponse(BaseModel):
    vertical: str
    bot_name: str
    response: str
    qualification_progress: Dict[str, Any] = Field(default_factory=dict)
    model: str = ""


class WebhookPayload(BaseModel):
    """Inbound GHL webhook payload (flexible — GHL sends varying shapes)."""

    contactId: Optional[str] = Field(None, alias="contact_id")
    locationId: Optional[str] = Field(None, alias="location_id")
    body: Optional[str] = Field(None, alias="message")
    fullName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class WebhookResponse(BaseModel):
    status: str
    contact_id: Optional[str] = None
    response_sent: bool = False
    vertical: str = ""
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    vertical: str
    ghl_configured: bool
    environment: str
