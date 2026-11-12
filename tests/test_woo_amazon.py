from urllib.parse import parse_qs

import httpx
import pytest

from smartandcool.config import Settings
from smartandcool.integrations.amazon import AmazonClient
from smartandcool.integrations.http import IntegrationError, ReadTransport
from smartandcool.integrations.woo import WooClient, rank_math_presence


def test_woo_auth_subdirectory_pagination_metadata_and_read_only(fixtures):
    product = fixtures("woo.json")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.headers["Authorization"].startswith("Basic ")
        assert "consumer_secret" not in str(request.url)
        assert request.url.path.startswith("/shop/wp-json/wc/v3/")
        if request.url.path.endswith("/123"):
            return httpx.Response(200, json=product)
        return httpx.Response(200, json=[product])

    settings = Settings(
        _env_file=None,
        woo_base_url="https://example.test/shop",
        woo_consumer_key="synthetic-key",
        woo_consumer_secret="synthetic-secret",
    )
    http = ReadTransport("woo", transport=httpx.MockTransport(handler))
    try:
        client = WooClient(settings, http)
        client.list_products(page=2, per_page=3)
        assert calls[-1].url.params["page"] == "2"
        assert calls[-1].url.params["per_page"] == "3"
        assert all(rank_math_presence(client.get_product(123)).values())
        client.get_variations(123)
        client.get_categories()
        client.get_attributes()
        assert len(calls) == 5
        assert not any(rank_math_presence({}).values())
    finally:
        http.close()


def test_woo_missing_credentials_and_wrong_response_shape(settings):
    http = ReadTransport(
        "woo", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    )
    try:
        with pytest.raises(IntegrationError, match="missing"):
            WooClient(settings, http)
        configured = Settings(
            _env_file=None,
            woo_base_url="https://example.test",
            woo_consumer_key="synthetic",
            woo_consumer_secret="synthetic",
        )
        with pytest.raises(IntegrationError, match="shape"):
            WooClient(configured, http).list_products()
    finally:
        http.close()


def test_amazon_lwa_and_participations_cache_without_sigv4():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "api.amazon.com":
            assert request.method == "POST"
            assert parse_qs(request.content.decode())["grant_type"] == ["refresh_token"]
            return httpx.Response(200, json={"access_token": "synthetic-lwa", "expires_in": 3600})
        assert request.method == "GET"
        assert request.headers["x-amz-access-token"] == "synthetic-lwa"
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "payload": [
                    {
                        "marketplace": {"id": "ATVPDKIKX0DER"},
                        "participation": {"isParticipating": True},
                    }
                ]
            },
        )

    settings = Settings(
        _env_file=None,
        amazon_client_id="synthetic-id",
        amazon_client_secret="synthetic-secret",
        amazon_refresh_token="synthetic-refresh",
    )
    http = ReadTransport("amazon", transport=httpx.MockTransport(handler))
    try:
        client = AmazonClient(settings, http)
        assert client.get_marketplace_participations()[0]["participation"]["isParticipating"]
        client.get_marketplace_participations()
        assert len(calls) == 3
    finally:
        http.close()


@pytest.mark.parametrize("body", [{}, [], {"access_token": "", "expires_in": 3600}])
def test_invalid_amazon_auth_response_is_safe(body):
    settings = Settings(
        _env_file=None,
        amazon_client_id="synthetic-id",
        amazon_client_secret="synthetic-secret",
        amazon_refresh_token="synthetic-refresh",
    )
    http = ReadTransport(
        "amazon", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(IntegrationError, match="invalid LWA"):
            AmazonClient(settings, http).get_marketplace_participations()
    finally:
        http.close()
