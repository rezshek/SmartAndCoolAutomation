import argparse
import json

import httpx
import pytest

from smartandcool.checks import main, probe
from smartandcool.config import Settings
from smartandcool.integrations.http import IntegrationError, ReadTransport


def args(provider="woo", **kwargs):
    return argparse.Namespace(
        provider=provider,
        product_id=None,
        variant_id=None,
        postal_code=None,
        destination="US",
        origin="CN",
        warehouse_id=None,
        **kwargs,
    )


@pytest.mark.parametrize("cli_flag,env_flag", [(False, False), (True, False), (False, True)])
def test_live_checks_require_both_opt_ins(cli_flag, env_flag):
    with pytest.raises(IntegrationError, match="require --live"):
        probe(args(live=cli_flag), Settings(_env_file=None, live_checks_enabled=env_flag))


def test_cli_disabled_by_default_and_safe_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["sca-check", "cj"])
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_woo_probe_outputs_presence_only(monkeypatch, fixtures):
    product = fixtures("woo.json")

    def handler(request):
        assert request.method == "GET"
        if request.url.path.endswith("/123"):
            return httpx.Response(200, json=product)
        return httpx.Response(200, json=[product])

    monkeypatch.setattr(
        "smartandcool.checks.ReadTransport",
        lambda *a, **k: ReadTransport("woo", transport=httpx.MockTransport(handler)),
    )
    settings = Settings(
        _env_file=None,
        live_checks_enabled=True,
        woo_base_url="https://example.test",
        woo_consumer_key="synthetic-key",
        woo_consumer_secret="synthetic-secret",
    )
    arguments = args(live=True)
    arguments.product_id = "123"
    result = probe(arguments, settings)
    assert all(result["rank_math_keys_present"].values())
    assert "Synthetic SEO title" not in json.dumps(result)
    assert "synthetic_connector_hint" not in json.dumps(result)
