"""JSON logs; never include bodies, URLs, exception messages, or arbitrary extra fields."""

import json
import logging
import re
from datetime import UTC, datetime

from pydantic import SecretStr
from sqlalchemy.engine import make_url

from smartandcool.config import Settings


class JsonFormatter(logging.Formatter):
    def __init__(self, secrets: list[str]):
        super().__init__()
        self.secrets = sorted((value for value in secrets if value), key=len, reverse=True)

    def format(self, record: logging.LogRecord) -> str:
        # Exception tracebacks may carry response bodies or database credentials.
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        message = re.sub(r"https?://\S+|postgresql(?:\+psycopg)?://\S+", "[REDACTED_URL]", message)
        message = re.sub(
            r"(?i)(bearer|basic)\s+\S+|"
            r"(password|token|secret|api[_-]?key|authorization)\s*[=:]\s*\S+",
            "[REDACTED]",
            message,
        )
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
        )


def configure_logging(settings: Settings) -> None:
    secrets = [
        value.get_secret_value()
        for value in settings.__dict__.values()
        if isinstance(value, SecretStr)
    ]
    password = make_url(settings.database_url.get_secret_value()).password
    if password:
        secrets.append(password)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(secrets))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)
    # Third-party request logging can expose query strings, credentials and response data.
    for name in ("httpx", "httpcore", "sqlalchemy", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
