"""
tests/test_authzen_integration.py

Integration tests for Agent-Auth / AuthZEN wiring across:
  1. AsyncPEPClient — wire format, fail-open/closed, batch
  2. Vocabulary — factory shapes
  3. Middleware — require_authzen, authzen_check
  4. Gate — AuthZEN pre-flight in approval flow
"""
from __future__ import annotations
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.authzen.pep_async import Action, Decision, Resource, Subject


@pytest.mark.asyncio
class TestAsyncPEPClient:

    async def test_check_access_correct_wire_format(self):
        from app.authzen.pep_async import AsyncPEPClient
        captured = {}

        async def fake_post(url, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs["json"]
            r = MagicMock()
            r.raise_for_status = MagicMock()
            r.json.return_value = {"decision": True}
            return r

        pep = AsyncPEPClient(pdp_url="https://caas.example.com")
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=fake_post)))
            mc.return_value.__aexit__ = AsyncMock(return_value=False)
            decision = await pep.check_access(
                Subject(type="agent", id="did:web:example.com"),
                Action(name="provision"),
                Resource(type="organization", id="test-org"),
            )

        assert decision.allowed is True
        body = captured["json"]
        assert body["subject"]["type"] == "agent"
        assert body["action"]["name"] == "provision"
        assert body["resource"]["id"] == "test-org"
        assert "/access/v1/evaluation" in captured["url"]

    async def test_fail_open_on_unreachable(self):
        from app.authzen.pep_async import AsyncPEPClient
        pep = AsyncPEPClient(pdp_url="https://caas.example.com", fail_open=True)
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(side_effect=Exception("refused"))))
            mc.return_value.__aexit__ = AsyncMock(return_value=False)
            d = await pep.check_access(Subject("agent","x"), Action("provision"), Resource("org","y"))
        assert d.allowed is True
        assert "fail_open" in d.context.get("reason", "")

    async def test_fail_closed_on_unreachable(self):
        from app.authzen.pep_async import AsyncPEPClient
        pep = AsyncPEPClient(pdp_url="https://caas.example.com", fail_open=False)
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(side_effect=Exception("timeout"))))
            mc.return_value.__aexit__ = AsyncMock(return_value=False)
            d = await pep.check_access(Subject("agent","x"), Action("provision"), Resource("org","y"))
        assert d.denied is True
        assert "fail_closed" in d.context.get("reason", "")

    async def test_not_configured_fail_open(self):
        from app.authzen.pep_async import AsyncPEPClient
        pep = AsyncPEPClient(pdp_url="", fail_open=True)
        d = await pep.check_access(Subject("agent","x"), Action("provision"), Resource("org","y"))
        assert d.allowed is True
        assert "not_configured" in d.context.get("reason", "")

    async def test_batch_fail_open_returns_all_allow(self):
        from app.authzen.pep_async import AsyncPEPClient
        pep = AsyncPEPClient(pdp_url="https://caas.example.com", fail_open=True)
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(side_effect=Exception("down"))))
            mc.return_value.__aexit__ = AsyncMock(return_value=False)
            results = await pep.check_access_batch([{"s":1},{"s":2}])
        assert len(results) == 2
        assert all(d.allowed for d in results)

    async def test_is_allowed_convenience(self):
        from app.authzen.pep_async import AsyncPEPClient
        pep = AsyncPEPClient(pdp_url="https://caas.example.com")
        with patch.object(pep, "check_access", new=AsyncMock(return_value=Decision(decision=True))):
            assert await pep.is_allowed(Subject("u","alice"), Action("approve"), Resource("req","r1"))


class TestVocabulary:

    def test_agent_subject_from_did(self):
        from app.authzen.vocabulary import AgentSubject
        s = AgentSubject.from_did("did:web:example.com", org="my-org")
        assert s.type == "agent" and s.id == "did:web:example.com"

    def test_agent_subject_from_record_drops_none(self):
        from app.authzen.vocabulary import AgentSubject
        class R:
            agentDid="did:web:x"; agentModel="claude"; agentProvider=None
            agentVersion="4.6"; organizationSlug="org"
        s = AgentSubject.from_record(R())
        assert "agent_provider" not in s.properties
        assert s.properties["agent_model"] == "claude"

    def test_action_constants(self):
        from app.authzen.vocabulary import AgentAction
        assert AgentAction.PROVISION.name == "provision"
        assert AgentAction.DEPROVISION.name == "deprovision"
        assert AgentAction.APPROVE.name == "approve"
        assert AgentAction.DELEGATE.name == "delegate"

    def test_resource_factories(self):
        from app.authzen.vocabulary import AgentResource
        assert AgentResource.organization("acme").type == "organization"
        r = AgentResource.agent_record("rec-1", org_slug="acme")
        assert r.properties["org_slug"] == "acme"

    def test_context_drops_empty(self):
        from app.authzen.vocabulary import AgentContext
        ctx = AgentContext.from_request(org_slug="acme")
        assert ctx.properties["org_slug"] == "acme"
        assert "request_ip" not in ctx.properties


@pytest.mark.asyncio
class TestMiddleware:

    async def test_authzen_check_returns_decision(self):
        from app.authzen.middleware import authzen_check
        with patch("app.authzen.middleware.get_pep") as mgp:
            mgp.return_value.check_access = AsyncMock(return_value=Decision(decision=True))
            d = await authzen_check(Subject("agent","x"), Action("p"), Resource("o","y"))
        assert d.allowed

    async def test_require_authzen_allows(self):
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
        from app.authzen.middleware import require_authzen
        from app.authzen.vocabulary import AgentAction, AgentResource
        app = FastAPI()

        @app.delete("/agents/{record_id}")
        async def delete_agent(record_id: str,
            _=Depends(require_authzen(action=AgentAction.DEPROVISION,
                resource_fn=lambda **kw: AgentResource.agent_record(kw["record_id"])))):
            return {"deleted": record_id}

        with patch("app.authzen.middleware.get_pep") as mgp:
            mgp.return_value.check_access = AsyncMock(return_value=Decision(decision=True))
            with TestClient(app) as c:
                assert c.delete("/agents/rec-1").status_code == 200

    async def test_require_authzen_blocks_on_deny(self):
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
        from app.authzen.middleware import require_authzen
        from app.authzen.vocabulary import AgentAction
        app = FastAPI()

        @app.delete("/agents/{record_id}")
        async def delete_agent(record_id: str,
            _=Depends(require_authzen(action=AgentAction.DEPROVISION))):
            return {"deleted": record_id}

        with patch("app.authzen.middleware.get_pep") as mgp:
            mgp.return_value.check_access = AsyncMock(
                return_value=Decision(decision=False, context={"reason": "policy_deny"}))
            with TestClient(app) as c:
                r = c.delete("/agents/rec-1")
        assert r.status_code == 403
        assert r.json()["detail"]["error"] == "access_denied"


@pytest.mark.asyncio
class TestGateAuthZEN:

    async def test_create_calls_authzen_provision(self):
        from app.approval.gate import ApprovalRequest, _APPROVAL_REQUESTS, create_approval_request
        _APPROVAL_REQUESTS.clear()
        with patch("app.approval.gate._pep") as mpep, \
             patch("app.approval.gate._create_caas_decision", new=AsyncMock(return_value="cid")):
            mpep.return_value.check_access = AsyncMock(return_value=Decision(decision=True))
            rid = await create_approval_request(ApprovalRequest(
                agent_record_id=str(uuid.uuid4()), org_slug="org",
                agent_did="did:web:x", agent_display_name="A"))
        mpep.return_value.check_access.assert_awaited_once()
        assert mpep.return_value.check_access.call_args.kwargs["action"].name == "provision"
        assert rid in _APPROVAL_REQUESTS

    async def test_create_blocked_on_caas_deny(self):
        from fastapi import HTTPException
        from app.approval.gate import ApprovalRequest, _APPROVAL_REQUESTS, create_approval_request
        _APPROVAL_REQUESTS.clear()
        with patch("app.approval.gate._pep") as mpep:
            mpep.return_value.check_access = AsyncMock(
                return_value=Decision(decision=False, context={"reason": "policy_deny"}))
            with pytest.raises(HTTPException) as exc:
                await create_approval_request(ApprovalRequest(
                    agent_record_id=str(uuid.uuid4()), org_slug="org",
                    agent_did="did:web:blocked", agent_display_name="B"))
        assert exc.value.status_code == 403
        assert len(_APPROVAL_REQUESTS) == 0

    async def test_vote_calls_authzen_approve(self):
        from app.approval.gate import (ApprovalDecision, ApprovalRequest, ApprovalState,
            _APPROVAL_REQUESTS, create_approval_request, submit_approval_decision)
        _APPROVAL_REQUESTS.clear()
        with patch("app.approval.gate._pep") as mpep, \
             patch("app.approval.gate._create_caas_decision", new=AsyncMock(return_value=None)), \
             patch("app.approval.gate._sync_decision_to_caas", new=AsyncMock()), \
             patch("app.approval.gate.emit_agent_status_change", new=AsyncMock()):
            mpep.return_value.check_access = AsyncMock(return_value=Decision(decision=True))
            rid = await create_approval_request(ApprovalRequest(
                agent_record_id=str(uuid.uuid4()), org_slug="org",
                agent_did="did:web:y", agent_display_name="C", required_approvals=1))
            status = await submit_approval_decision(rid, ApprovalDecision(approver_id="alice", decision="approve"))
        assert status.state == ApprovalState.APPROVED
        assert mpep.return_value.check_access.await_count == 2
        second = mpep.return_value.check_access.call_args_list[1]
        assert second.kwargs["action"].name == "approve"

    async def test_authzen_allowed_in_status(self):
        from app.approval.gate import (ApprovalRequest, _APPROVAL_REQUESTS,
            create_approval_request, get_approval_status)
        _APPROVAL_REQUESTS.clear()
        with patch("app.approval.gate._pep") as mpep, \
             patch("app.approval.gate._create_caas_decision", new=AsyncMock(return_value=None)):
            mpep.return_value.check_access = AsyncMock(return_value=Decision(decision=True))
            rid = await create_approval_request(ApprovalRequest(
                agent_record_id=str(uuid.uuid4()), org_slug="org",
                agent_did="did:web:z", agent_display_name="D"))
        s = await get_approval_status(rid)
        assert s.authzen_allowed is True
