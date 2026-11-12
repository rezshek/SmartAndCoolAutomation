import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from smartandcool.config import Settings
from smartandcool.integrations.cj import CJClient, Tokens
from smartandcool.integrations.http import IntegrationError, ReadTransport


def make_client(handler, **settings):
    http = ReadTransport("cj", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    return CJClient(Settings(_env_file=None, cj_api_key="synthetic-key", **settings), http)


def test_catalog_detail_variants_inventory_and_us_ca_freight(fixtures):
    data = fixtures("cj.json")
    calls = []
    mapping = {
        "getAccessToken": "auth",
        "listV2": "search",
        "queryByVid": "stock",
        "freightCalculate": "freight",
    }

    def handler(request):
        calls.append(request)
        suffix = request.url.path.split("/")[-1]
        key = mapping.get(suffix)
        if key is None:
            key = "variants" if "/variant/" in request.url.path else "product"
        if suffix != "getAccessToken":
            assert request.headers["CJ-Access-Token"] == "synthetic-access-token"
        return httpx.Response(200, json=data[key])

    client = make_client(handler)
    try:
        assert "content" in client.search_products()
        assert client.get_product("synthetic-product")["pid"] == "synthetic-product"
        assert client.get_variants("synthetic-product")[0]["vid"] == "synthetic-variant"
        assert client.get_stock("synthetic-variant")[0]["countryCode"] == "CN"
        for country, postal in (("US", "10001"), ("CA", "M5V 1A1")):
            quote = client.quote_freight(
                "synthetic-variant", country, postal, warehouse_ids=["synthetic-warehouse"]
            )
            assert quote[0]["logisticPrice"] == Decimal("4.71")
            body = json.loads(calls[-1].content)
            assert body["startCountryCode"] == "CN"
            assert body["endCountryCode"] == country
            assert body["zip"] == postal
            assert body["storageIdList"] == ["synthetic-warehouse"]
            assert body["products"] == [{"vid": "synthetic-variant", "quantity": 1}]
        assert calls[1].url.params["keyWord"] == "organizer"
        assert calls[1].url.params["size"] == "1"
        assert sum("getAccessToken" in str(r.url) for r in calls) == 1
        assert all(
            r.method == "GET" or r.url.path.endswith(("getAccessToken", "freightCalculate"))
            for r in calls
        )
    finally:
        client.http.close()


def test_expiring_token_is_refreshed_without_reauthentication(fixtures):
    data = fixtures("cj.json")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path.endswith("refreshAccessToken")
        assert json.loads(request.content) == {"refreshToken": "old-refresh"}
        return httpx.Response(200, json=data["auth"])

    client = make_client(handler)
    client.tokens = Tokens(
        accessToken="old-token",
        accessTokenExpiryDate=datetime.now(UTC) - timedelta(seconds=1),
        refreshToken="old-refresh",
        refreshTokenExpiryDate=datetime.now(UTC) + timedelta(days=1),
    )
    try:
        assert client.authenticate().get_secret_value() == "synthetic-access-token"
        assert len(calls) == 1
    finally:
        client.http.close()


def test_missing_credentials_make_no_http_request():
    http = ReadTransport("cj", transport=httpx.MockTransport(lambda _: pytest.fail("network")))
    client = CJClient(Settings(_env_file=None), http)
    try:
        with pytest.raises(IntegrationError, match="missing"):
            client.search_products()
    finally:
        http.close()


@pytest.mark.parametrize(
    "body",
    [
        {"code": 1600100, "result": False, "message": "private-provider-message"},
        {"code": 200, "result": True, "data": {"accessToken": "private-token"}},
        [],
    ],
)
def test_envelope_and_malformed_tokens_fail_safely(body):
    client = make_client(lambda _: httpx.Response(200, json=body))
    try:
        with pytest.raises(IntegrationError) as error:
            client.authenticate()
        assert "private" not in str(error.value)
    finally:
        client.http.close()


def test_rejects_invalid_destination_before_network():
    client = make_client(lambda _: pytest.fail("network"))
    try:
        with pytest.raises(ValueError):
            client.quote_freight("synthetic-variant", "GB", "test")
        with pytest.raises(ValueError):
            client.search_products(size=101)
    finally:
        client.http.close()


def test_reuses_environment_token_pair_without_auth(fixtures):
    data = fixtures("cj.json")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path.endswith("listV2")
        return httpx.Response(200, json=data["search"])

    client = make_client(
        handler,
        cj_access_token="synthetic-access-token",
        cj_access_token_expires_at="2099-01-01T00:00:00+00:00",
        cj_refresh_token="synthetic-refresh-token",
        cj_refresh_token_expires_at="2099-02-01T00:00:00+00:00",
    )
    try:
        client.search_products()
        assert len(calls) == 1
    finally:
        client.http.close()


def test_server_cached_expiring_token_stops_without_auth_loop(fixtures):
    data = fixtures("cj.json")["auth"]
    data["data"]["accessTokenExpiryDate"] = datetime.now(UTC).isoformat()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=data)

    client = make_client(handler)
    try:
        with pytest.raises(IntegrationError, match="too close to expiry"):
            client.authenticate()
        assert len(calls) == 1
    finally:
        client.http.close()
