import json

import httpx
import pytest
from sqlalchemy.engine import make_url

from smartandcool.catalog.cli import execute, main, parser, private_output
from smartandcool.catalog.service import require_local_database
from smartandcool.config import Settings
from smartandcool.integrations.cj import CJClient
from smartandcool.integrations.http import IntegrationError, ReadTransport


@pytest.mark.parametrize("live,enabled", [(False, False), (True, False), (False, True)])
def test_catalog_live_reads_need_both_existing_gates(live, enabled):
    args = parser().parse_args(["import", *(["--live"] if live else [])])
    with pytest.raises(IntegrationError, match="require --live"):
        execute(args, Settings(_env_file=None, live_checks_enabled=enabled))


def test_exports_cannot_escape_private_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        private_output("public.json")
    assert private_output("local-data/private.json").is_relative_to(tmp_path / "local-data")
    with pytest.raises(ValueError):
        private_output("local-data/../public.json")


def test_refuse_remote_database():
    with pytest.raises(ValueError, match="loopback"):
        require_local_database(make_url("postgresql+psycopg://user:pass@example.test/db"))


def test_request_and_point_budgets_include_retries_and_authentication():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    http = ReadTransport(
        "cj", max_requests=2, transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    try:
        with pytest.raises(IntegrationError, match="request budget"):
            http.request("POST", "https://example.test/authentication/getAccessToken")
        assert len(calls) == 2
    finally:
        http.close()
    http = ReadTransport(
        "cj", max_points=50, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    )
    try:
        http.request("GET", "https://example.test/product/listV2")
        with pytest.raises(IntegrationError, match="point budget"):
            http.request("GET", "https://example.test/product/query")
        assert http.request_count == 1 and http.points_used == 50
    finally:
        http.close()


def test_provider_exhausted_points_stop_without_retry_or_new_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"pointsInfo": {"remaining": 0}})

    http = ReadTransport("cj", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    try:
        with pytest.raises(IntegrationError, match="points insufficient"):
            http.request("GET", "https://example.test/product/query")
        assert len(calls) == 1
    finally:
        http.close()


def test_catalog_cli_disabled_by_default(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["sca-catalog", "import"])
    assert main() == 1
    assert "require --live" in json.loads(capsys.readouterr().out)["reason"]


def test_category_discovery_uses_read_endpoint(fixtures):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("getAccessToken"):
            return httpx.Response(200, json=fixtures("cj.json")["auth"])
        assert request.method == "GET" and request.url.path.endswith("getCategory")
        return httpx.Response(200, json={"code": 200, "result": True, "data": []})

    http = ReadTransport("cj", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    try:
        assert (
            CJClient(Settings(_env_file=None, cj_api_key="synthetic"), http).get_categories() == []
        )
        assert len(seen) == 2
    finally:
        http.close()
