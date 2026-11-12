import json
import logging

import pytest
from pydantic import SecretStr, ValidationError

from smartandcool.config import Settings
from smartandcool.logging import JsonFormatter, configure_logging


def test_example_env_is_parseable():
    settings = Settings(_env_file=".env.example")
    assert settings.live_checks_enabled is False
    assert settings.cj_api_key is None
    assert settings.woo_base_url is None


@pytest.mark.parametrize(
    "url",
    [
        "http://store.example",
        "https://key:secret@store.example",
        "https://store.example?consumer_key=secret",
        "https://store.example/#secret",
    ],
)
def test_rejects_insecure_or_credential_bearing_store_url(url):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, woo_base_url=url)
    assert url not in str(error.value)


def test_rejects_wrong_database_driver():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///local.db")


def test_secret_settings_are_masked():
    settings = Settings(_env_file=None, cj_api_key="sentinel-never-print")
    assert isinstance(settings.cj_api_key, SecretStr)
    assert "sentinel-never-print" not in repr(settings)
    assert "sentinel-never-print" not in settings.model_dump_json()


def test_json_logging_redacts_secrets_urls_and_exception_payloads():
    formatter = JsonFormatter(["sentinel-never-print"])
    try:
        raise RuntimeError("sensitive-provider-body")
    except RuntimeError:
        import sys

        record = logging.LogRecord(
            "test",
            logging.ERROR,
            "",
            0,
            "key=%s token=other-value https://user:pass@example.test/?secret=abc",
            ("sentinel-never-print",),
            sys.exc_info(),
        )
    rendered = formatter.format(record)
    assert json.loads(rendered)["level"] == "ERROR"
    for secret in ("sentinel-never-print", "other-value", "user:pass", "sensitive-provider-body"):
        assert secret not in rendered


def test_third_party_request_logging_is_disabled(settings):
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    configure_logging(settings)
    try:
        assert not logging.getLogger("httpx").propagate
        assert not logging.getLogger("uvicorn.access").propagate
    finally:
        root.handlers, root.level = old_handlers, old_level


def test_configured_database_password_is_redacted_when_logged_alone(capsys):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:db-sentinel-password@localhost/test",
    )
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    configure_logging(settings)
    try:
        logging.getLogger("test").warning("diagnostic %s", "db-sentinel-password")
        assert "db-sentinel-password" not in capsys.readouterr().err
    finally:
        root.handlers, root.level = old_handlers, old_level
