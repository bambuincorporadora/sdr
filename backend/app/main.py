from fastapi import FastAPI

from app.routes import webhook


def create_app() -> FastAPI:
    app = FastAPI(title="SDR-IA")
    app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
    return app


app = create_app()
