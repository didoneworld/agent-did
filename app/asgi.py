"""
app/asgi.py

Integrated ASGI application entry-point.

Wires all Phase 1-3 routers into create_app() following the incremental
safety order from issue #3:
  1. Discovery + session endpoints (stateless, no IdP config needed)
  2. SCIM + SSF + approvals
  3. SAML (requires SAML_SP_CERT + SAML_SP_KEY in env)
  4. OIDC callback replacement (requires real IdP config in DB)

Routers 3-4 are registered but guarded: the underlying route handlers
return 501 if the required env/DB config is absent, rather than crashing
at startup. This lets the app run in dev without SAML/OIDC configured.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.main import create_app
from app.routers.authorization import router as authorization_router

# Phase 1 — hardened identity flows
from app.routers.discovery import router as discovery_router
from app.routers.oidc_router import router as oidc_router
from app.routers.saml_router import router as saml_router
from app.routers.session_router import router as session_router

# Phase 2 — SCIM lifecycle + SSF + approvals
from app.routers.scim_router import router as scim_router
from app.ssf.emitter import ssf_router
from app.approval.gate import approval_router


def create_integrated_app() -> FastAPI:
    app = create_app()

    # Existing authorization bridge (unchanged)
    app.include_router(authorization_router)

    # ── Step 1: Discovery + session (safe to enable immediately) ──────────
    # discovery_router has no prefix — must serve /.well-known/* at root
    app.include_router(discovery_router, tags=["Discovery"])
    app.include_router(session_router, prefix="/v1", tags=["Sessions"])

    # ── Step 2: SCIM + SSF + approvals ────────────────────────────────────
    app.include_router(scim_router,     prefix="/v1/scim/v2",  tags=["SCIM"])
    app.include_router(ssf_router,      prefix="/v1/ssf",      tags=["SSF"])
    app.include_router(approval_router, prefix="/v1/approvals",tags=["Approvals"])

    # ── Step 3: SAML SP (requires SAML_SP_CERT + SAML_SP_KEY) ────────────
    app.include_router(saml_router, prefix="/v1/sso/saml", tags=["SSO – SAML"])

    # ── Step 4: OIDC callback replacement ────────────────────────────────
    # NOTE: do not replace the existing /v1/sso/oidc/callback until
    # real IdP config loading is wired to identity_providers DB table.
    # The stub DB loaders in oidc_router.py return 422 when OIDC_ISSUER
    # env is empty, which is safe for dev.
    app.include_router(oidc_router, prefix="/v1/sso/oidc", tags=["SSO – OIDC"])

    return app


app = create_integrated_app()
