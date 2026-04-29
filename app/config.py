from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings:
    def __init__(self) -> None:
        default_db_path = ROOT_DIR / "data" / "agent_id_protocol.db"
        self.root_dir = ROOT_DIR
        self.service_name = "agent-identity-saas"
        self.app_version = "0.3.0"
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")
        self.api_rate_limit_requests = int(os.getenv("API_RATE_LIMIT_REQUESTS", "120"))
        self.api_rate_limit_window_seconds = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))
        self.session_signing_secret = os.getenv("SESSION_SIGNING_SECRET", "agent-identity-dev-secret")
        self.session_ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "43200"))
        self.schema_path = ROOT_DIR / "schemas" / "json" / "agent-id-record.schema.json"


settings = Settings()
