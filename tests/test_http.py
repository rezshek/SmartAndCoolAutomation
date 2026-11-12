from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.utils import format_datetime

import httpx
import pytest

from smartandcool.integrations.http import IntegrationError, ReadTransport


def make_http(handler, *, attempts=3, sleeps=None, **kwargs):
    return ReadTransport(
        "test",
        attempts=attempts,
        transport=httpx.MockTransport(handler),
        sleep=(sleeps if sleeps is not None else []).append,
        **kwargs,
    )


def test_retries_429_then_transient_error_and_preserves_decimal():
    sleeps, requests = [], []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        if len(requests) == 2:
            return httpx.Response(503)
        return httpx.Response(200, text='{"price":4.71}')

    client = make_http(handler, sleeps=sleeps)
    try:
        assert client.request("GET", "https://example.test")["price"] == Decimal("4.71")
        assert sleeps == [2.0, 2]
        assert requests[0].extensions["timeout"]["connect"] == 15
    finally:
        client.close()


@pytest.mark.parametrize("status", [401, 403, 404, 302])
def test_rejects_permanent_errors_and_redirects_without_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, headers={"Location": "https://evil.test"}, text="private-body"
        )

    client = make_http(handler)
    try:
        with pytest.raises(IntegrationError) as error:
            client.request("GET", "https://example.test/?secret=sentinel")
        assert len(calls) == 1
        assert "private-body" not in str(error.value)
        assert "sentinel" not in str(error.value)
    finally:
        client.close()


def test_timeout_has_bounded_attempts_and_safe_error():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("private-secret", request=request)

    client = make_http(handler)
    try:
        with pytest.raises(IntegrationError, match="transport failure") as error:
            client.request("GET", "https://example.test")
        assert len(calls) == 3
        assert error.value.__cause__ is None
    finally:
        client.close()


def test_exhausted_5xx_stops_after_three_attempts():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    client = make_http(handler)
    try:
        with pytest.raises(IntegrationError, match="retry limit"):
            client.request("GET", "https://example.test")
        assert len(calls) == 3
    finally:
        client.close()


def test_long_retry_after_stops_instead_of_retrying_early():
    client = make_http(lambda _: httpx.Response(429, headers={"Retry-After": "600"}))
    try:
        with pytest.raises(IntegrationError, match="cooldown"):
            client.request("GET", "https://example.test")
    finally:
        client.close()


def test_retry_after_http_date_and_invalid_json():
    client = make_http(lambda _: httpx.Response(200, text="not-json"))
    try:
        future = format_datetime(datetime.now(UTC) + timedelta(seconds=15))
        assert 13 <= client._retry_delay(future, 0) <= 15
        with pytest.raises(IntegrationError, match="invalid JSON"):
            client.request("GET", "https://example.test")
    finally:
        client.close()


def test_minimum_interval_applies_between_requests_and_retries():
    now = [0.0]
    waits = []

    def sleep(delay):
        waits.append(delay)
        now[0] += delay

    client = ReadTransport(
        "cj",
        min_interval=1.1,
        clock=lambda: now[0],
        sleep=sleep,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    try:
        client.request("GET", "https://example.test")
        client.request("GET", "https://example.test")
        assert waits == [1.1]
    finally:
        client.close()
