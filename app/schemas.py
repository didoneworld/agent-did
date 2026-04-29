from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrganizationBootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str = Field(min_length=2, max_length=255)
    organization_slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    api_key_label: str = Field(default="bootstrap-admin", min_length=2, max_length=255)


class BootstrapResponse(BaseModel):
    organization_id: str
    organization_slug: str
    api_key: str


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime


class ApiKeySummary(BaseModel):
    id: str
    label: str
    key_prefix: str
    last_four: str
    is_active: bool
    created_at: datetime


class AgentRecordWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_id_protocol_version: str
    agent: dict[str, Any]
    authorization: dict[str, Any]
    governance: dict[str, Any]
    bindings: dict[str, Any]
    extensions: dict[str, Any] = Field(default_factory=dict)


class AgentRecordResponse(BaseModel):
    id: str
    organization_id: str
    did: str
    display_name: str
    status: str
    environment: str
    protocol_version: str
    record: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deprovisioned_at: datetime | None


class AuditEventResponse(BaseModel):
    id: int
    actor_label: str
    action: str
    reason: str | None
    metadata: dict[str, Any]
    created_at: datetime


class DeprovisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=1000)


class AuthContext(BaseModel):
    organization_id: str
    api_key_id: str
    actor_label: str


class ServiceInfoResponse(BaseModel):
    service: str
    version: str
    database_url_scheme: str
