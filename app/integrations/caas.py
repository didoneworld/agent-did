from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import settings


class CaaSDecisionForwardRequest(BaseModel):
    subject: dict[str, Any]
    action: dict[str, Any]
    resource: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    decision: bool
    decision_id: str
    obligations: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None


class CaaSClient:
    """Optional bridge from Agent DID decisions into the CAAS runtime/federation plane."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.caas_api_gateway_url).rstrip("/")
        self.api_key = api_key or settings.caas_api_key
        self.timeout_seconds = timeout_seconds or settings.caas_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def forward_decision(self, payload: CaaSDecisionForwardRequest) -> bool:
        if not self.enabled:
            return False

        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/v1/authorization/decisions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload.model_dump(), headers=headers)
                response.raise_for_status()
        except httpx.HTTPError:
            return False
        return True
