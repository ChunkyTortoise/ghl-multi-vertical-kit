"""GoHighLevel API client — stripped from Jorge, made vertical-agnostic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 502, 503)
    return False


class GHLClient:
    """Async GoHighLevel API v2 client with retry logic."""

    BASE_URL = "https://services.leadconnectorhq.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.ghl_api_key
        self.location_id = location_id or settings.ghl_location_id
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None

    # -- lifecycle -----------------------------------------------------------

    async def __aenter__(self) -> "GHLClient":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- core request --------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        client = self._get_client()

        try:
            resp = await client.request(
                method=method, url=url, headers=self.headers,
                json=data, params=params,
            )
            resp.raise_for_status()
            return {"success": True, "data": resp.json() if resp.content else {}}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 502, 503):
                raise
            logger.error("GHL HTTP %s: %s", exc.response.status_code, exc)
            return {"success": False, "error": str(exc), "status_code": exc.response.status_code}
        except (httpx.TimeoutException, httpx.NetworkError):
            raise
        except Exception as exc:
            logger.error("GHL request error: %s", exc)
            return {"success": False, "error": str(exc), "status_code": 500}

    # -- contacts ------------------------------------------------------------

    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"contacts/{contact_id}")

    async def update_contact(self, contact_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"contacts/{contact_id}", data=updates)

    async def add_tag(self, contact_id: str, tag: str) -> bool:
        r = await self._request("POST", f"contacts/{contact_id}/tags", data={"tags": [tag]})
        return r.get("success", False)

    async def remove_tag(self, contact_id: str, tag: str) -> bool:
        r = await self._request("DELETE", f"contacts/{contact_id}/tags", data={"tags": [tag]})
        return r.get("success", False)

    # -- messaging -----------------------------------------------------------

    async def send_message(
        self, contact_id: str, message: str, message_type: str = "SMS",
    ) -> Dict[str, Any]:
        return await self._request(
            "POST", "conversations/messages",
            data={"contactId": contact_id, "message": message, "type": message_type},
        )

    # -- calendar ------------------------------------------------------------

    async def get_free_slots(
        self, calendar_id: str, days_ahead: int = 7,
    ) -> List[Dict[str, str]]:
        try:
            now = datetime.now()
            result = await self._request(
                "GET", f"calendars/{calendar_id}/free-slots",
                params={
                    "startDate": int(now.timestamp() * 1000),
                    "endDate": int((now + timedelta(days=days_ahead)).timestamp() * 1000),
                    "timezone": "America/Los_Angeles",
                },
            )
            if not result.get("success"):
                return []

            slots: List[Dict[str, str]] = []
            for _date_key, date_obj in sorted(result.get("data", {}).items()):
                if not isinstance(date_obj, dict):
                    continue
                for slot in date_obj.get("slots", []):
                    start = slot if isinstance(slot, str) else (slot.get("startTime") or slot.get("start", ""))
                    if not start:
                        continue
                    try:
                        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        if 9 <= dt.hour < 17:
                            end = "" if isinstance(slot, str) else (slot.get("endTime") or slot.get("end", ""))
                            slots.append({"start": start, "end": end})
                            if len(slots) >= 3:
                                return slots
                    except (ValueError, AttributeError):
                        continue
            return slots
        except Exception as exc:
            logger.error("get_free_slots error: %s", exc)
            return []

    async def create_appointment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "calendars/events", data=data)

    # -- health --------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        try:
            r = await self._request(
                "GET", "contacts", params={"limit": 1, "locationId": self.location_id},
            )
            return {"healthy": r.get("success", False), "checked_at": datetime.now().isoformat()}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}
