"""
app/authzen/vocabulary.py

Canonical AuthZEN Subject / Action / Resource factories for every
agent-did enforcement point. Centralising here means every PEP call
uses the same string literals as the CAAS SpiceDB schema.
"""
from __future__ import annotations
from typing import Any
from app.authzen.pep_async import Action, Context, Resource, Subject


class AgentSubject:
    @staticmethod
    def from_did(did: str, **props: Any) -> Subject:
        return Subject(type="agent", id=did, properties=props or None)

    @staticmethod
    def from_record(record: Any, **props: Any) -> Subject:
        properties = {
            k: v for k, v in {
                "agent_model": getattr(record, "agentModel", None),
                "agent_provider": getattr(record, "agentProvider", None),
                "agent_version": getattr(record, "agentVersion", None),
                "org_slug": getattr(record, "organizationSlug", None),
                **props,
            }.items() if v is not None
        }
        return Subject(type="agent", id=record.agentDid, properties=properties or None)

    @staticmethod
    def human(user_id: str, org_slug: str = "") -> Subject:
        props = {"org_slug": org_slug} if org_slug else None
        return Subject(type="user", id=user_id, properties=props)

    @staticmethod
    def service(service_id: str) -> Subject:
        return Subject(type="service", id=service_id)


class AgentAction:
    PROVISION       = Action(name="provision")
    DEPROVISION     = Action(name="deprovision")
    SUSPEND         = Action(name="suspend")
    REACTIVATE      = Action(name="reactivate")
    USE_TOOL        = Action(name="use_tool")
    CALL_API        = Action(name="call_api")
    READ_DATA       = Action(name="read_data")
    WRITE_DATA      = Action(name="write_data")
    DELETE_DATA     = Action(name="delete_data")
    DELEGATE        = Action(name="delegate")       # Phase 3 OBO
    IMPERSONATE     = Action(name="impersonate")    # Phase 3 OBO
    REVOKE_SESSION  = Action(name="revoke_session")
    APPROVE         = Action(name="approve")
    REJECT          = Action(name="reject")

    @staticmethod
    def use_tool(tool_name: str) -> Action:
        return Action(name="use_tool", properties={"tool": tool_name})

    @staticmethod
    def call_api(method: str, path: str) -> Action:
        return Action(name="call_api", properties={"method": method, "path": path})


class AgentResource:
    @staticmethod
    def organization(org_slug: str) -> Resource:
        return Resource(type="organization", id=org_slug)

    @staticmethod
    def agent_record(record_id: str, org_slug: str = "") -> Resource:
        props = {"org_slug": org_slug} if org_slug else None
        return Resource(type="agent_record", id=record_id, properties=props)

    @staticmethod
    def approval_request(request_id: str) -> Resource:
        return Resource(type="approval_request", id=request_id)

    @staticmethod
    def tool(tool_name: str) -> Resource:
        return Resource(type="tool", id=tool_name)

    @staticmethod
    def delegation_scope(scope: str) -> Resource:
        return Resource(type="delegation_scope", id=scope)


class AgentContext:
    @staticmethod
    def from_request(org_slug: str = "", request_ip: str = "",
                     risk_score: float | None = None) -> Context:
        props = {
            k: v for k, v in {
                "org_slug": org_slug or None,
                "request_ip": request_ip or None,
                "risk_score": risk_score,
            }.items() if v is not None
        }
        return Context(properties=props or None)
