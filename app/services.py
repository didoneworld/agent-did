from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db_models import AgentRecord, ApiKey, AuditEvent, Organization, utc_now
from app.schemas import AgentRecordWrite, AuthContext
from app.security import generate_api_key, hash_api_key


class ProtocolValidationError(Exception):
    pass


class BootstrapConflictError(Exception):
    pass


class SaaSService:
    def __init__(self, schema_path: Path) -> None:
        schema = json.loads(schema_path.read_text())
        self.validator = Draft202012Validator(schema)

    def validate_record(self, record: dict[str, Any]) -> None:
        try:
            self.validator.validate(record)
        except Exception as exc:  # jsonschema ValidationError
            raise ProtocolValidationError(str(exc)) from exc

    def bootstrap_organization(self, db: Session, name: str, slug: str, api_key_label: str) -> tuple[Organization, str]:
        if db.scalar(select(Organization.id).limit(1)) is not None:
            raise BootstrapConflictError("bootstrap has already been completed")

        organization = Organization(name=name, slug=slug)
        raw_key = generate_api_key()
        api_key = ApiKey(
            organization=organization,
            label=api_key_label,
            key_hash=hash_api_key(raw_key),
            key_prefix=raw_key[:12],
            last_four=raw_key[-4:],
        )
        db.add_all([organization, api_key])
        db.flush()
        self._audit(db, organization_id=organization.id, actor_label="bootstrap", action="organization_bootstrapped")
        db.commit()
        db.refresh(organization)
        return organization, raw_key

    def authenticate(self, db: Session, raw_key: str) -> AuthContext | None:
        hashed = hash_api_key(raw_key)
        api_key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hashed, ApiKey.is_active.is_(True)))
        if api_key is None:
            return None
        return AuthContext(
            organization_id=api_key.organization_id,
            api_key_id=api_key.id,
            actor_label=f"api-key:{api_key.label}",
        )

    def list_organizations(self, db: Session, organization_id: str) -> list[Organization]:
        return list(db.scalars(select(Organization).where(Organization.id == organization_id)))

    def list_api_keys(self, db: Session, organization_id: str) -> list[ApiKey]:
        return list(db.scalars(select(ApiKey).where(ApiKey.organization_id == organization_id).order_by(ApiKey.created_at)))

    def list_records(self, db: Session, organization_id: str) -> list[AgentRecord]:
        stmt = select(AgentRecord).where(AgentRecord.organization_id == organization_id).order_by(AgentRecord.created_at)
        return list(db.scalars(stmt))

    def get_record_by_id(self, db: Session, organization_id: str, record_id: str) -> AgentRecord | None:
        stmt = select(AgentRecord).where(AgentRecord.organization_id == organization_id, AgentRecord.id == record_id)
        return db.scalar(stmt)

    def get_record_by_did(self, db: Session, organization_id: str, did: str) -> AgentRecord | None:
        stmt = select(AgentRecord).where(AgentRecord.organization_id == organization_id, AgentRecord.did == did)
        return db.scalar(stmt)

    def upsert_record(
        self,
        db: Session,
        organization_id: str,
        actor_label: str,
        payload: AgentRecordWrite,
    ) -> AgentRecord:
        record = payload.model_dump()
        self.validate_record(record)
        did = record["agent"]["did"]
        existing = self.get_record_by_did(db, organization_id, did)
        now = utc_now()
        if existing is None:
            existing = AgentRecord(
                organization_id=organization_id,
                did=did,
                display_name=record["agent"]["display_name"],
                status=record["agent"]["status"],
                environment=record["agent"]["environment"],
                protocol_version=record["agent_id_protocol_version"],
                record_json=record,
                created_at=now,
                updated_at=now,
            )
            db.add(existing)
            action = "agent_record_created"
        else:
            existing.display_name = record["agent"]["display_name"]
            existing.status = record["agent"]["status"]
            existing.environment = record["agent"]["environment"]
            existing.protocol_version = record["agent_id_protocol_version"]
            existing.record_json = record
            existing.updated_at = now
            action = "agent_record_updated"

        db.flush()
        self._audit(
            db,
            organization_id=organization_id,
            actor_label=actor_label,
            action=action,
            agent_record_id=existing.id,
            metadata={"did": did, "status": existing.status},
        )
        db.commit()
        db.refresh(existing)
        return existing

    def deprovision_record(
        self,
        db: Session,
        organization_id: str,
        actor_label: str,
        record_id: str,
        reason: str,
    ) -> AgentRecord | None:
        record = self.get_record_by_id(db, organization_id, record_id)
        if record is None:
            return None
        record.record_json["agent"]["status"] = "disabled"
        record.status = "disabled"
        record.updated_at = utc_now()
        record.deprovisioned_at = utc_now()
        self._audit(
            db,
            organization_id=organization_id,
            agent_record_id=record.id,
            actor_label=actor_label,
            action="agent_record_deprovisioned",
            reason=reason,
            metadata={"did": record.did},
        )
        db.commit()
        db.refresh(record)
        return record

    def list_audit_events(self, db: Session, organization_id: str, agent_record_id: str | None = None) -> list[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.organization_id == organization_id).order_by(AuditEvent.created_at)
        if agent_record_id is not None:
            stmt = stmt.where(AuditEvent.agent_record_id == agent_record_id)
        return list(db.scalars(stmt))

    def _audit(
        self,
        db: Session,
        organization_id: str,
        actor_label: str,
        action: str,
        agent_record_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        db.add(
            AuditEvent(
                organization_id=organization_id,
                agent_record_id=agent_record_id,
                actor_label=actor_label,
                action=action,
                reason=reason,
                metadata_json=metadata or {},
            )
        )
