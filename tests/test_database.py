"""Runs only against an explicitly supplied disposable *_test PostgreSQL database."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from smartandcool.config import Settings
from smartandcool.db import check_database, create_db_engine, session_factory
from smartandcool.main import create_app


@pytest.mark.database
def test_postgres_migrations_and_app(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    assert make_url(url).database.endswith("_test"), "Refusing non-test database"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    settings = Settings(_env_file=None)
    engine = create_db_engine(settings)
    try:
        command.upgrade(config, "head")
        check_database(engine)
        with session_factory(engine)() as session:
            assert (
                session.scalar(text("SELECT version_num FROM alembic_version")) == "0001_foundation"
            )
        command.check(config)
        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 0
        command.upgrade(config, "head")
        assert "alembic_version" in inspect(engine).get_table_names()
        with TestClient(create_app(settings)) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/ready").json() == {"status": "ready"}
    finally:
        engine.dispose()
