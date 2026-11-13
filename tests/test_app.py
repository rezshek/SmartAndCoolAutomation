from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from smartandcool.main import create_app


def test_lifespan_health_and_readiness(monkeypatch, settings):
    engine = MagicMock()
    monkeypatch.setattr("smartandcool.main.create_db_engine", lambda _: engine)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").status_code == 200
        connection = engine.connect.return_value.__enter__.return_value
        assert str(connection.execute.call_args.args[0]) == "SELECT 1"
        paths = set(client.app.openapi()["paths"])
        assert "/api/products" in paths
        assert not any(word in path for path in paths for word in ("publish", "order", "payment"))
    engine.dispose.assert_called_once()


def test_unavailable_database_fails_readiness_without_leaking(monkeypatch, settings):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("secret-query", {}, Exception("private-password"))
    monkeypatch.setattr("smartandcool.main.create_db_engine", lambda _: engine)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
        assert "private-password" not in response.text
