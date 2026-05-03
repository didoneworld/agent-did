from __future__ import annotations

from fastapi import FastAPI

from app.main import create_app
from app.routers.authorization import router as authorization_router


def create_integrated_app() -> FastAPI:
    app = create_app()
    app.include_router(authorization_router)
    return app


app = create_integrated_app()
