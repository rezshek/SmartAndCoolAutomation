import json
from pathlib import Path

import httpx
import pytest

from smartandcool.config import Settings


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)

    def refuse_unmocked_http(*args, **kwargs):
        raise AssertionError("Automated tests must mock external HTTP calls")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse_unmocked_http)


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def fixtures():
    def load(name):
        return json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))

    return load
