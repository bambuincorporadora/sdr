from fastapi import FastAPI

from app.routes import webhook
from app.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="SDR-IA")
    app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
    app.include_router(health.router, tags=["health"])
    return app


app = create_app()
