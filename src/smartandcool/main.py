import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from smartandcool.config import Settings
from smartandcool.db import check_database, create_db_engine
from smartandcool.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings)
        app.state.engine = create_db_engine(settings)
        logger.info("application_started")
        try:
            yield
        finally:
            app.state.engine.dispose()
            logger.info("application_stopped")

    app = FastAPI(title="SmartAndCool Automation", version="0.1.0", lifespan=lifespan)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    def ready(request: Request):
        try:
            check_database(request.app.state.engine)
        except SQLAlchemyError:
            logger.warning("database_unavailable")
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    return app
