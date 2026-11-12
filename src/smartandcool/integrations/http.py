"""Small bounded transport shared by the isolated provider adapters."""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime

import httpx


class IntegrationError(Exception):
    """Safe to display: never wraps provider response bodies or credential-bearing URLs."""

    def __init__(self, provider: str, reason: str, status: int | None = None):
        self.provider = provider
        self.reason = reason
        self.status = status
        super().__init__(f"{provider}: {reason}" + (f" (HTTP {status})" if status else ""))


class ReadTransport:
    def __init__(
        self,
        provider: str,
        *,
        timeout: float = 15,
        attempts: int = 3,
        min_interval: float = 0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        max_requests: int | None = None,
        max_points: int | None = None,
    ):
        if not 1 <= attempts <= 3 or not 0 < timeout <= 60:
            raise ValueError("Invalid timeout or attempt count")
        self.provider = provider
        self.attempts = attempts
        self.min_interval = min_interval
        self.sleep = sleep
        self.clock = clock
        self.last_request: float | None = None
        if max_requests is not None and not 1 <= max_requests <= 1000:
            raise ValueError("Request budget must be between 1 and 1000")
        if max_points is not None and not 1 <= max_points <= 10000:
            raise ValueError("Point budget must be between 1 and 10000")
        self.max_requests = max_requests
        self.max_points = max_points
        self.request_count = 0
        self.points_used = 0
        self.points_remaining: int | None = None
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def request(self, method: str, url: str, **kwargs):
        # POST is used only by provider-specific auth and quote operations.
        # Callers must never pass arbitrary write endpoints to this internal transport.
        for attempt in range(self.attempts):
            # Budget actual HTTP attempts, including authentication and retries.
            path = httpx.URL(url).path
            points = 0
            if self.provider == "cj":
                if path.endswith("/product/listV2"):
                    points = 50
                elif "/product/" in path or "/logistic/" in path:
                    points = 10
            if self.max_requests is not None and self.request_count >= self.max_requests:
                raise IntegrationError(self.provider, "HTTP request budget exhausted; resume later")
            if self.max_points is not None and self.points_used + points > self.max_points:
                raise IntegrationError(self.provider, "point budget exhausted; resume later")
            if self.points_remaining is not None and self.points_remaining < points:
                raise IntegrationError(self.provider, "provider points insufficient; resume later")
            if self.last_request is not None:
                remaining = self.min_interval - (self.clock() - self.last_request)
                if remaining > 0:
                    self.sleep(remaining)
            self.last_request = self.clock()
            self.request_count += 1
            self.points_used += points
            try:
                response = self.client.request(method, url, **kwargs)
            except httpx.TransportError:
                if attempt + 1 == self.attempts:
                    raise IntegrationError(self.provider, "transport failure") from None
                self.sleep(2**attempt)
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                # CJ point exhaustion will not be rescued with rapid retries.
                if response.status_code == 429 and self.provider == "cj":
                    try:
                        info = response.json().get("pointsInfo", {})
                        if info.get("remaining", points) < points:
                            raise IntegrationError(
                                "cj", "provider points insufficient; resume later"
                            )
                    except (ValueError, AttributeError, TypeError):
                        pass
                if attempt + 1 == self.attempts:
                    raise IntegrationError(
                        self.provider, "retry limit reached", response.status_code
                    )
                delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
                self.sleep(delay)
                continue
            if not 200 <= response.status_code < 300:
                raise IntegrationError(self.provider, "request rejected", response.status_code)
            try:
                # Preserve decimal money returned by catalog/quote endpoints.
                payload = json.loads(response.content, parse_float=Decimal)
                if self.provider == "cj" and isinstance(payload, dict):
                    remaining = (payload.get("pointsInfo") or {}).get("remaining")
                    if isinstance(remaining, int) and remaining >= 0:
                        self.points_remaining = remaining
                return payload
            except (ValueError, UnicodeDecodeError):
                raise IntegrationError(self.provider, "invalid JSON response") from None
        raise AssertionError("unreachable")

    def _retry_delay(self, header: str | None, attempt: int) -> float:
        delay = float(2**attempt)
        if header is not None:
            try:
                delay = float(header)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    pass
        # Stop instead of retrying earlier than a provider's long cooldown.
        if not 0 <= delay <= 30:
            raise IntegrationError(self.provider, "provider cooldown requires a later manual check")
        return delay
