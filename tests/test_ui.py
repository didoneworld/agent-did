from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_ui_shell_is_served(tmp_path: Path):
    db_path = tmp_path / "ui.db"
    with TestClient(create_app(database_url=f"sqlite:///{db_path}")) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Agent ID Control Plane" in response.text
        assert "/static/app.js" in response.text


def test_static_assets_are_served(tmp_path: Path):
    db_path = tmp_path / "ui.db"
    with TestClient(create_app(database_url=f"sqlite:///{db_path}")) as client:
        css = client.get("/static/app.css")
        js = client.get("/static/app.js")
        assert css.status_code == 200
        assert js.status_code == 200
