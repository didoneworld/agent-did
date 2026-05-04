"""
app/authzen/middleware.py

FastAPI dependency + inline check for AuthZEN enforcement.

Usage patterns:

1. Route-level Depends():
   @router.delete("/{id}")
   async def delete(id: str, _=Depends(require_authzen(
       action=AgentAction.DEPROVISION,
       resource_fn=lambda **kw: AgentResource.agent_record(kw["id"]),
   ))):

2. Inline check in service code:
   decision = await authzen_check(subject, action, resource)
   if decision.denied: raise HTTPException(403)
"""
from __future__ import annotations
import os
from typing import Callable, Any
from fastapi import HTTPException, Request, status
from app.authzen.pep_async import Action, AsyncPEPClient, Context, Decision, Resource, Subject
from app.authzen.vocabulary import AgentAction, AgentContext, AgentResource

_pep_client: AsyncPEPClient | None = None


def get_pep() -> AsyncPEPClient:
    global _pep_client
    if _pep_client is None:
        _pep_client = AsyncPEPClient.from_settings()
    return _pep_client


async def authzen_check(
    subject: Subject,
    action: Action,
    resource: Resource,
    context: Context | None = None,
) -> Decision:
    return await get_pep().check_access(subject, action, resource, context)


def require_authzen(
    action: Action,
    resource_fn: Callable[..., Resource] | None = None,
    resource: Resource | None = None,
    subject_type: str = "agent",
):
    async def _dependency(request: Request) -> None:
        subject_id = _extract_subject(request)
        if resource_fn is not None:
            res = resource_fn(**dict(request.path_params))
        elif resource is not None:
            res = resource
        else:
            res = Resource(type="unknown", id="*")

        ctx = AgentContext.from_request(
            request_ip=request.client.host if request.client else ""
        )
        decision = await authzen_check(Subject(type=subject_type, id=subject_id), action, res, ctx)

        if decision.denied and not decision.context.get("reason", "").endswith("fail_open"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "access_denied",
                    "reason": decision.context.get("reason", "policy_deny"),
                    "action": action.name,
                    "resource_type": res.type,
                    "resource_id": res.id,
                },
            )
    return _dependency


def _extract_subject(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "anonymous"
    try:
        from jose import jwt as _jwt
        return _jwt.get_unverified_claims(auth[7:]).get("sub", "anonymous")
    except Exception:
        return "anonymous"


# SCIM action map for route-level enforcement
SCIM_ACTION_MAP: dict[tuple[str, str], Action] = {
    ("POST",   "/v1/scim/v2/AgenticIdentities"):       AgentAction.PROVISION,
    ("DELETE", "/v1/scim/v2/AgenticIdentities/{id}"):  AgentAction.DEPROVISION,
    ("PATCH",  "/v1/scim/v2/AgenticIdentities/{id}"):  AgentAction.SUSPEND,
    ("PUT",    "/v1/scim/v2/AgenticIdentities/{id}"):  AgentAction.REACTIVATE,
    ("GET",    "/v1/scim/v2/AgenticIdentities"):        AgentAction.READ_DATA,
    ("GET",    "/v1/scim/v2/AgenticIdentities/{id}"):  AgentAction.READ_DATA,
}
