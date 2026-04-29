from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings:
    def __init__(self) -> None:
        default_db_path = ROOT_DIR / "data" / "agent_id_protocol.db"
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")
        self.schema_path = ROOT_DIR / "schemas" / "json" / "agent-id-record.schema.json"


settings = Settings()
