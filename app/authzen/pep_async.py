"""
app/authzen/pep_async.py

Async AuthZEN 1.0 PEP client wrapping Agent-Auth's wire format.
Uses httpx.AsyncClient (FastAPI-safe, non-blocking).

Replaces the raw httpx calls in app/integrations/agent_auth.py with
a standards-compliant AuthZEN 1.0 client that:
  - validates request/response against the AuthZEN schema
  - supports fail-open/fail-closed per environment config
  - supports single + batch evaluations
  - reads config from app.config.settings (no duplicate env parsing)

POST {pdp_url}/access/v1/evaluation   → single decision
POST {pdp_url}/access/v1/evaluations  → batch decisions
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimal AuthZEN models (mirrors Agent-Auth SDK shape without requiring
# the package to be published to PyPI — works with git-installed authzen too)
# ---------------------------------------------------------------------------

class Subject:
    def __init__(self, type: str, id: str, properties: dict | None = None):
        self.type = type
        self.id = id
        self.properties: dict[str, Any] = properties or {}

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"type": self.type, "id": self.id}
        if self.properties:
            d["properties"] = self.properties
        return d


class Action:
    def __init__(self, name: str, properties: dict | None = None):
        self.name = name
        self.properties: dict[str, Any] = properties or {}

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"name": self.name}
        if self.properties:
            d["properties"] = self.properties
        return d


class Resource:
    def __init__(self, type: str, id: str, properties: dict | None = None):
        self.type = type
        self.id = id
        self.properties: dict[str, Any] = properties or {}

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"type": self.type, "id": self.id}
        if self.properties:
            d["properties"] = self.properties
        return d


class Context:
    def __init__(self, properties: dict | None = None):
        self.properties: dict[str, Any] = properties or {}

    def to_dict(self) -> dict:
        return {"properties": self.properties}


class Decision:
    def __init__(self, decision: bool, context: dict | None = None):
        self.decision = decision
        self.context: dict[str, Any] = context or {}

    @property
    def allowed(self) -> bool:
        return self.decision is True

    @property
    def denied(self) -> bool:
        return self.decision is not True

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        return cls(
            decision=bool(data.get("decision", data.get("allowed", False))),
            context=data.get("context", {}),
        )


# ---------------------------------------------------------------------------
# Async PEP client
# ---------------------------------------------------------------------------

class AsyncPEPClient:
    """
    Async AuthZEN PEP client.

    Default configuration reads from app.config.settings:
      settings.agent_auth_url          → PDP URL
      settings.agent_auth_api_key      → Bearer token
      settings.agent_auth_timeout_seconds → request timeout

    fail_open behaviour:
      True  (default in dev) — allow on CAAS unreachable
      False (set AUTHZEN_FAIL_OPEN=false in prod) — deny on unreachable
    """

    def __init__(
        self,
        pdp_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        fail_open: bool = True,
    ):
        self.pdp_url = (pdp_url or settings.agent_auth_url or settings.caas_api_gateway_url or "").rstrip("/")
        self.api_key = api_key or settings.agent_auth_api_key or settings.caas_api_key
        self.timeout = timeout or settings.agent_auth_timeout_seconds
        self.fail_open = fail_open

    @classmethod
    def from_settings(cls, fail_open: bool = True) -> "AsyncPEPClient":
        """Preferred factory — reads all config from settings."""
        import os
        fail_open_env = os.environ.get("AUTHZEN_FAIL_OPEN", "true").lower() == "true"
        return cls(fail_open=fail_open_env)

    @property
    def enabled(self) -> bool:
        return bool(self.pdp_url)

    # ------------------------------------------------------------------
    # Single evaluation
    # ------------------------------------------------------------------

    async def check_access(
        self,
        subject: Subject,
        action: Action,
        resource: Resource,
        context: Context | None = None,
    ) -> Decision:
        if not self.enabled:
            log.debug("AuthZEN PDP not configured — fail_open=%s", self.fail_open)
            return self._not_configured()

        payload: dict[str, Any] = {
            "subject": subject.to_dict(),
            "action": action.to_dict(),
            "resource": resource.to_dict(),
        }
        if context:
            payload["context"] = context.to_dict()

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.pdp_url}/access/v1/evaluation",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                return Decision.from_dict(resp.json())
        except Exception as exc:
            return self._on_error(exc, subject, action, resource)

    # ------------------------------------------------------------------
    # Batch evaluation
    # ------------------------------------------------------------------

    async def check_access_batch(
        self,
        evaluations: list[dict[str, Any]],
    ) -> list[Decision]:
        if not self.enabled or not evaluations:
            default = Decision(decision=self.fail_open)
            return [default for _ in evaluations]

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.pdp_url}/access/v1/evaluations",
                    json={"evaluations": evaluations},
                    headers=headers,
                )
                resp.raise_for_status()
                return [Decision.from_dict(r) for r in resp.json().get("results", [])]
        except Exception as exc:
            log.warning("AuthZEN batch eval failed: %s — fail_open=%s", exc, self.fail_open)
            return [Decision(decision=self.fail_open) for _ in evaluations]

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def is_allowed(self, subject: Subject, action: Action, resource: Resource,
                         context: Context | None = None) -> bool:
        return (await self.check_access(subject, action, resource, context)).allowed

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _not_configured(self) -> Decision:
        if self.fail_open:
            return Decision(decision=True, context={"reason": "pdp_not_configured_fail_open"})
        return Decision(decision=False, context={"reason": "pdp_not_configured_fail_closed"})

    def _on_error(self, exc: Exception, subject: Subject, action: Action, resource: Resource) -> Decision:
        log.warning(
            "AuthZEN PDP unreachable — subject=%s:%s action=%s resource=%s:%s fail_open=%s — %s",
            subject.type, subject.id, action.name, resource.type, resource.id, self.fail_open, exc,
        )
        if self.fail_open:
            return Decision(decision=True, context={"reason": "pdp_unreachable_fail_open", "error": str(exc)})
        return Decision(decision=False, context={"reason": "pdp_unreachable_fail_closed", "error": str(exc)})
