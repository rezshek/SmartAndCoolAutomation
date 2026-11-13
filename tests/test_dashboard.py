"""Review boundaries use real disposable PostgreSQL; provider calls are always mocked."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from test_catalog_database import client_for, detail, envelope
from test_catalog_database import session as db_session  # noqa: F401 -- shared PostgreSQL fixture

from smartandcool.catalog.models import Product, Variant
from smartandcool.catalog.pricing import PricingPolicy
from smartandcool.catalog.report import ServiceReview
from smartandcool.catalog.service import save_quote, upsert_product
from smartandcool.config import Settings
from smartandcool.dashboard import generation, service
from smartandcool.dashboard.api import database
from smartandcool.dashboard.generation import (
    Selection,
    compose,
    generate_content,
    validate_grounding,
)
from smartandcool.dashboard.models import ReviewEvent, WooCategory
from smartandcool.dashboard.schemas import (
    CategoryReview,
    DraftEdit,
    FactReview,
    Generate,
    ListingContent,
    PricingReview,
    Transition,
)
from smartandcool.main import create_app

FACTS = {"title": "Closet organizer", "description_0": "Plastic storage for clothing."}
SOURCE = "Synthetic reviewer evidence"


@pytest.fixture
def catalog_session(request):
    session = request.getfixturevalue("db_session")
    for pid in ("dash-a", "dash-b"):
        data = detail(pid)
        upsert_product(session, data, data["variants"])
    return session


@pytest.fixture
def client(catalog_session):
    app = create_app(Settings(_env_file=None, woo_base_url="https://store.example.test"))
    app.dependency_overrides[database] = lambda: catalog_session
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
        yield client


def verify(session, pid="dash-a"):
    facts = service.product_detail(session, pid)["facts"]
    service.verify_facts(
        session,
        pid,
        FactReview(
            facts={k: v for k, v in facts.items() if k in ("title", "description_0")}, source=SOURCE
        ),
    )


def draft(session, pid="dash-a", profile="woo_us", human=False):
    verify(session, pid)
    result = generation.generate(
        session, Settings(_env_file=None), pid, profile, Generate(source=SOURCE)
    )
    if human:
        result = generation.edit(
            session,
            pid,
            profile,
            DraftEdit(
                base_version=result.version,
                content=ListingContent.model_validate(result.content),
                source=SOURCE,
            ),
        )
    return result


def woo_mapping(session):
    session.add(
        WooCategory(
            id=51,
            name="Home Storage",
            parent=0,
            store="https://store.example.test",
            retrieved_at=datetime.now(UTC),
        )
    )
    session.flush()
    return service.map_category(
        session,
        "dash-a",
        "woo_us",
        CategoryReview(category_id=51, approved=True, source=SOURCE),
        "https://store.example.test",
    )


def test_catalog_pagination_and_no_product_duplication(client):
    data = client.get("/api/products?page_size=1").json()
    assert data["total"] == 2 and len(data["items"]) == 1
    second = client.get("/api/products?page_size=1&page=2").json()
    assert second["items"][0]["cj_id"] != data["items"][0]["cj_id"]
    assert client.get("/api/products?page=9").json()["items"] == []
    assert client.get("/api/products?page_size=51").status_code == 422


def test_catalog_filters_variant_grouping_and_literal_search(client):
    assert client.get("/api/products?q=dash-a").json()["total"] == 1
    assert client.get("/api/products?q=%25").json()["total"] == 0
    assert client.get("/api/products?min_cost=4").json()["total"] == 0
    assert client.get("/api/products?origin=CN&inventory=available").json()["total"] == 2
    assert client.get("/api/products?eligibility=PASS").json()["total"] == 0
    result = client.get("/api/products/dash-a").json()
    assert len(result["variants"]) == 1
    assert result["variants"][0]["product_id"] == result["product"]["cj_id"]


@pytest.mark.parametrize(
    "profile,currency", [("woo_us", "USD"), ("amazon_us", "USD"), ("amazon_ca", "CAD")]
)
def test_channel_prices_fail_closed_without_financial_data(client, profile, currency):
    data = client.get(f"/api/products/dash-a/{profile}/pricing").json()
    assert data["selected"] is None
    assert len(data["rows"]) == 1
    assert data["rows"][0]["currency"] == currency
    assert data["rows"][0]["pricing_status"] == "UNPRICEABLE"
    assert "missing_shipping_revenue" in data["rows"][0]["reasons"]


def test_preview_never_persists_and_channel_mismatch_rejected(client, catalog_session):
    data = client.get("/api/products/dash-a/woo_us/pricing").json()
    before = catalog_session.scalar(select(func.count()).select_from(ReviewEvent))
    assert (
        client.post("/api/products/dash-a/woo_us/pricing/preview", json=data["config"]).status_code
        == 200
    )
    assert catalog_session.scalar(select(func.count()).select_from(ReviewEvent)) == before
    data["config"]["policy"]["country"] = "CA"
    assert client.put("/api/products/dash-a/woo_us/pricing", json=data["config"]).status_code == 422
    assert catalog_session.scalar(select(func.count()).select_from(ReviewEvent)) == before


def test_quote_selection_requires_matching_variant_and_market(client):
    data = client.get("/api/products/dash-a/woo_us/pricing").json()["config"]
    data.update(quote_id=99999, method_id=99999)
    assert client.put("/api/products/dash-a/woo_us/pricing", json=data).status_code == 422
    data["variant_id"] = "dash-bv"
    assert client.post("/api/products/dash-a/woo_us/pricing/preview", json=data).status_code == 422


def test_missing_woo_category_and_manual_approval(catalog_session):
    s = catalog_session
    result = service.map_category(
        s,
        "dash-a",
        "woo_us",
        CategoryReview(suggestion="New organization category", source=SOURCE),
        "https://store.example.test",
    )
    assert result["status"] == "MISSING_CATEGORY"
    with pytest.raises(ValueError, match="current category"):
        service.map_category(
            s,
            "dash-a",
            "woo_us",
            CategoryReview(category_id=999, approved=True, source=SOURCE),
            "https://store.example.test",
        )
    assert woo_mapping(s)["category_id"] == 51
    assert service.latest(s, "dash-a", "amazon_us", "category") is None


def test_stale_or_different_store_categories_cannot_be_approved(catalog_session):
    s = catalog_session
    woo_mapping(s)
    with pytest.raises(ValueError, match="current category"):
        service.map_category(
            s,
            "dash-a",
            "woo_us",
            CategoryReview(category_id=51, approved=True, source=SOURCE),
            "https://different.example.test",
        )
    s.get(WooCategory, 51).retrieved_at -= timedelta(days=2)
    s.flush()
    assert (
        service.channel(s, "dash-a", "woo_us", "https://store.example.test")["indicators"][
            "category_mapping"
        ]
        != "APPROVED"
    )


@pytest.mark.parametrize("profile", ["amazon_us", "amazon_ca"])
def test_amazon_is_provisional_with_missing_attributes(catalog_session, profile):
    request = CategoryReview(
        suggestion="STORAGE", required_attributes=["brand", "size"], source=SOURCE
    )
    result = service.map_category(catalog_session, "dash-a", profile, request, None)
    assert result["status"] == "PROVISIONAL"
    assert "gtin_or_category_brand_exemption_required" in result["blockers"]
    assert "missing_attribute_brand" in result["blockers"]
    with pytest.raises(ValueError, match="provisional"):
        service.map_category(
            catalog_session, "dash-a", profile, request.model_copy(update={"approved": True}), None
        )


def test_existing_asin_path_is_distinct(catalog_session):
    result = service.map_category(
        catalog_session,
        "dash-a",
        "amazon_us",
        CategoryReview(suggestion="STORAGE", listing_path="existing_asin", source=SOURCE),
        None,
    )
    assert "exact_asin_match_required" in result["blockers"]
    assert "gtin_or_category_brand_exemption_required" not in result["blockers"]


def test_generation_requires_verified_facts(catalog_session):
    with pytest.raises(ValueError, match="verify source facts"):
        generation.generate(
            catalog_session, Settings(_env_file=None), "dash-a", "woo_us", Generate(source=SOURCE)
        )
    with pytest.raises(ValueError, match="exact source facts"):
        service.verify_facts(
            catalog_session,
            "dash-a",
            FactReview(facts={"title": "Invented steel organizer"}, source=SOURCE),
        )


def test_regeneration_editing_and_version_history(catalog_session):
    s = catalog_session
    first = draft(s)
    second = generation.generate(
        s, Settings(_env_file=None), "dash-a", "woo_us", Generate(source=SOURCE)
    )
    assert (first.version, second.version) == (1, 2)
    edited = generation.edit(
        s,
        "dash-a",
        "woo_us",
        DraftEdit(
            base_version=2, content=ListingContent.model_validate(second.content), source=SOURCE
        ),
    )
    assert edited.version == 3 and edited.origin == "human_edit"
    assert len(service.versions(s, "dash-a", "woo_us")) == 3
    with pytest.raises(ValueError, match="reload"):
        generation.edit(
            s,
            "dash-a",
            "woo_us",
            DraftEdit(
                base_version=2, content=ListingContent.model_validate(second.content), source=SOURCE
            ),
        )
    assert first.content == second.content


def test_approval_does_not_bypass_commercial_requirements(catalog_session):
    s = catalog_session
    current = draft(s, human=True)
    woo_mapping(s)
    result = service.transition(
        s,
        "dash-a",
        "woo_us",
        Transition(
            state="CONTENT_APPROVED",
            version=current.version,
            facts_checked=True,
            images_rights_reviewed=True,
            source=SOURCE,
        ),
        "https://store.example.test",
    )
    assert result["state"] == "CONTENT_APPROVED"
    assert result["indicators"]["content"] == "APPROVED"
    assert result["indicators"]["pricing"] == "UNPRICEABLE"
    assert result["indicators"]["publishing"] == "DISABLED"
    assert "verified_saved_price_required" in result["blockers"]


def test_approval_restrictions_and_version_invalidation(catalog_session):
    s = catalog_session
    with pytest.raises(ValueError, match="Invalid workflow"):
        service.transition(
            s, "dash-a", "woo_us", Transition(state="CONTENT_APPROVED", source=SOURCE)
        )
    current = draft(s)
    with pytest.raises(ValueError, match="Mock drafts"):
        service.transition(
            s,
            "dash-a",
            "woo_us",
            Transition(
                state="CONTENT_APPROVED",
                version=1,
                facts_checked=True,
                images_rights_reviewed=True,
                source=SOURCE,
            ),
        )
    current = generation.edit(
        s,
        "dash-a",
        "woo_us",
        DraftEdit(
            base_version=current.version,
            content=ListingContent.model_validate(current.content),
            source=SOURCE,
        ),
    )
    woo_mapping(s)
    with pytest.raises(ValueError, match="Review facts"):
        service.transition(
            s,
            "dash-a",
            "woo_us",
            Transition(state="CONTENT_APPROVED", version=current.version, source=SOURCE),
        )
    service.transition(
        s,
        "dash-a",
        "woo_us",
        Transition(
            state="CONTENT_APPROVED",
            version=current.version,
            facts_checked=True,
            images_rights_reviewed=True,
            source=SOURCE,
        ),
        "https://store.example.test",
    )
    generation.edit(
        s,
        "dash-a",
        "woo_us",
        DraftEdit(
            base_version=current.version,
            content=ListingContent.model_validate(current.content),
            source=SOURCE,
        ),
    )
    assert service.channel(s, "dash-a", "woo_us")["state"] == "DRAFT_READY"


def test_fact_changes_and_source_changes_invalidate_approval(catalog_session):
    s = catalog_session
    current = draft(s, human=True)
    woo_mapping(s)
    service.transition(
        s,
        "dash-a",
        "woo_us",
        Transition(
            state="CONTENT_APPROVED",
            version=current.version,
            facts_checked=True,
            images_rights_reviewed=True,
            source=SOURCE,
        ),
        "https://store.example.test",
    )
    service.verify_facts(
        s, "dash-a", FactReview(facts={"title": "Closet organizer"}, source=SOURCE)
    )
    assert service.channel(s, "dash-a", "woo_us")["state"] == "DRAFT_READY"
    s.get(Product, "dash-a").title = "Updated source"
    s.flush()
    assert service.verified_facts(s, "dash-a")[0] == {}


def test_excluded_variant_stays_excluded_after_parent_review(catalog_session):
    s = catalog_session
    variant = s.get(Variant, "dash-av")
    variant.title = "Battery powered organizer"
    service.audit(
        s,
        "dash-a",
        "all",
        "eligibility",
        {"source": SOURCE, "safety_reviewed": True, "ip_clear": True},
        "tester",
    )
    result = service.product_detail(s, "dash-a")
    assert result["product"]["eligibility"] == "PASS"
    assert result["variants"][0]["eligibility"][0] == "EXCLUDED"
    assert result["product"]["excluded_variants"] == [variant.cj_id]


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "Certified steel organizer"),
        ("description", "Safe for babies."),
        ("seo_title", "Medical grade product"),
        ("search_terms", "BrandX"),
        ("attributes", {"material": "steel"}),
    ],
)
def test_unsupported_content_is_rejected(field, value):
    content = ListingContent(title="Closet organizer", description=FACTS["description_0"])
    content = content.model_copy(update={field: value})
    with pytest.raises(ValueError, match="Unsupported|Attributes"):
        validate_grounding(content, FACTS)


def test_markup_and_invalid_selection_are_rejected():
    with pytest.raises(ValidationError):
        ListingContent(title="<script>alert(1)</script>", description="Text")
    with pytest.raises(ValueError, match="unsupported fact"):
        compose(
            Selection(
                title_fact="invented",
                short_facts=[],
                description_facts=["title"],
                bullet_facts=[],
                keyword_facts=[],
            ),
            FACTS,
            "woo_us",
        )
    assert "<script" not in service.plain("<script>alert(1)</script><p>Product</p>")
    assert service.safe_image("javascript:alert(1)") is None


@pytest.mark.parametrize(
    "original,edited",
    [
        ("Length 10 cm", "Length 0 cm"),
        ("Not safe for children", "Safe for children"),
        ("Length 10 cm", "Length -10 cm"),
    ],
)
def test_grounding_preserves_numbers_signs_and_negations(original, edited):
    with pytest.raises(ValueError, match="Unsupported"):
        validate_grounding(
            ListingContent(title="Organizer", description=edited),
            {"title": "Organizer", "description": original},
        )


def test_mock_and_independent_channel_content():
    settings = Settings(_env_file=None)
    woo, origin, usage = generate_content(settings, FACTS, "woo_us")
    amazon, _, _ = generate_content(settings, FACTS, "amazon_us")
    assert origin == "mock" and usage["estimated_cost_usd"] == "0"
    assert woo.seo_title and not amazon.seo_title
    assert amazon.bullets and not woo.bullets
    with pytest.raises(ValueError, match="Live AI requires"):
        generate_content(settings, FACTS, "woo_us", live=True)


def test_openai_structured_request_usage_and_secret_handling():
    calls = []

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["text"]["format"]["strict"] is True
        assert "untrusted" in payload["instructions"]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "title_fact": "title",
                                        "short_facts": [],
                                        "description_facts": ["description_0"],
                                        "bullet_facts": [],
                                        "keyword_facts": [],
                                    }
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        )

    settings = Settings(
        _env_file=None,
        openai_api_key="private-test-key",
        ai_live_enabled=True,
        ai_input_usd_per_million=1,
        ai_output_usd_per_million=2,
        ai_price_source="synthetic rates",
    )
    _, origin, usage = generate_content(
        settings, FACTS, "woo_us", live=True, transport=httpx.MockTransport(handler)
    )
    assert len(calls) == 1 and origin == "openai"
    assert Decimal(usage["estimated_cost_usd"]) == Decimal("0.0002")
    assert "private-test-key" not in json.dumps(usage)


@pytest.mark.parametrize("data", [{"status": "incomplete"}, {"status": "completed", "output": []}])
def test_openai_refusal_incomplete_invalid_responses(data):
    with pytest.raises(ValueError):
        generate_content(
            Settings(_env_file=None, openai_api_key="test", ai_live_enabled=True),
            FACTS,
            "woo_us",
            live=True,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)),
        )


@pytest.mark.parametrize(
    "peer,host,origin,status",
    [
        ("192.0.2.10", "127.0.0.1", None, 403),
        ("127.0.0.1", "evil.example", None, 403),
        ("127.0.0.1", "127.0.0.1", "https://evil.example", 403),
        ("127.0.0.1", "127.0.0.1", None, 401),
    ],
)
def test_unauthorized_access(monkeypatch, peer, host, origin, status):
    monkeypatch.setattr("smartandcool.main.create_db_engine", lambda _: MagicMock())
    app = create_app(Settings(_env_file=None, dashboard_token="secret-admin"))
    with TestClient(app, base_url=f"http://{host}:8000", client=(peer, 50000)) as client:
        response = client.get("/api/settings", headers={"origin": origin} if origin else {})
        assert response.status_code == status
        assert "secret-admin" not in response.text


def test_settings_and_validation_never_expose_credentials(monkeypatch):
    monkeypatch.setattr("smartandcool.main.create_db_engine", lambda _: MagicMock())
    app = create_app(
        Settings(_env_file=None, openai_api_key="private-key", dashboard_token="secret")
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 50000),
        headers={"Authorization": "Bearer secret"},
    ) as client:
        response = client.get("/api/settings")
        assert response.status_code == 200 and "private-key" not in response.text
        invalid = client.put("/api/products/a/woo_us/category", json={"secret": "private-key"})
        assert invalid.status_code == 422 and "private-key" not in invalid.text
        assert client.post("/api/products/a/publish").status_code in (404, 405)


def test_woo_category_refresh_is_bounded_read_only(client, monkeypatch):
    client.app.state.settings.live_checks_enabled = True
    calls = []

    def request(self, method, url, **kwargs):
        calls.append((method, url, kwargs.get("params")))
        return [{"id": 45, "name": "Home Storage", "parent": 0}]

    monkeypatch.setattr("smartandcool.integrations.http.ReadTransport.request", request)
    client.app.state.settings.woo_consumer_key = Settings(
        _env_file=None, woo_consumer_key="test"
    ).woo_consumer_key
    client.app.state.settings.woo_consumer_secret = Settings(
        _env_file=None, woo_consumer_secret="test"
    ).woo_consumer_secret
    result = client.post("/api/categories/woo/refresh?live=true")
    assert result.status_code == 200 and result.json()["count"] == 1
    assert len(calls) == 1 and calls[0][0] == "GET"
    assert calls[0][1].endswith("/products/categories")
    assert client.get("/api/categories/woo").json()[0]["id"] == 45


def test_workflow_return_to_review_is_explicit(catalog_session):
    s = catalog_session
    draft(s, human=True)
    result = service.transition(
        s, "dash-a", "woo_us", Transition(state="REVIEW_REQUIRED", source=SOURCE)
    )
    assert result["state"] == "REVIEW_REQUIRED"


def test_canadian_pricing_does_not_accept_missing_fx(catalog_session):
    policy = PricingPolicy(
        channel="amazon",
        country="CA",
        currency="CAD",
        category="home",
        referral_rate="0.15",
        returns_rate="0.05",
        shipping_revenue={"amount": "0", "currency": "CAD"},
        additional_unit_cost={"amount": "0", "currency": "CAD"},
    )
    review = PricingReview(variant_id="dash-av", policy=policy, source=SOURCE)
    result = service.pricing(catalog_session, "dash-a", "amazon_ca", review)
    assert result["rows"][0]["status"] != "PASS"
    assert result["rows"][0]["selling_price"] is None


def test_dashboard_reuses_decimal_engine_and_exact_quote_approval(catalog_session):
    s = catalog_session
    provider = client_for(
        lambda _: envelope(
            [
                {
                    "logisticName": "Tracked",
                    "logisticPrice": "7",
                    "logisticAging": "5-10",
                    "trackingAvailable": True,
                }
            ]
        )
    )
    try:
        quote = save_quote(s, provider, "dash-av", "US", "10001", origin="CN")
        policy = PricingPolicy(
            channel="amazon",
            country="US",
            currency="USD",
            category="home",
            referral_rate="0.15",
            returns_rate="0.05",
            shipping_revenue={"amount": "0"},
            additional_unit_cost={"amount": "0"},
            max_price="100",
            fees_verified=True,
            shipping_revenue_verified=True,
            landed_costs_verified=True,
            fee_source=SOURCE,
            shipping_revenue_source=SOURCE,
            landed_cost_source=SOURCE,
        )
        request = PricingReview(
            variant_id="dash-av",
            policy=policy,
            source=SOURCE,
            product_review={"source": SOURCE, "safety_reviewed": True, "ip_clear": True},
        )
        row = service.pricing(s, "dash-a", "amazon_us", request)["rows"][0]
        assert row["required_price"] == "19.99" and row["profit"] == "5.000000"
        assert row["status"] == "NEEDS_REVIEW"  # no exact service review yet
        request.quote_id, request.method_id = quote.id, row["method_id"]
        request.service_reviews = [
            ServiceReview(
                quote_id=quote.id,
                method_id=row["method_id"],
                method="Tracked",
                destination="US",
                origin="CN",
                source=SOURCE,
                eligible=True,
                tracking_verified=True,
            )
        ]
        result = service.save_pricing(s, "dash-a", "amazon_us", request)
        assert result["selected"]["status"] == "PASS"
        assert service.pricing_readiness(s, "dash-a", "amazon_us") == "PASS"
        # A fresh quote supersedes the old selection; old freight evidence cannot transfer.
        save_quote(s, provider, "dash-av", "US", "10001", origin="CN")
        assert service.pricing(s, "dash-a", "amazon_us")["selected"] is None
        assert service.pricing_readiness(s, "dash-a", "amazon_us") == "UNPRICEABLE"
    finally:
        provider.http.close()


def test_pricing_decisions_are_kept_per_variant(catalog_session):
    s = catalog_session
    data = detail("dash-a")
    second = dict(data["variants"][0], vid="dash-av2", variantSellPrice="4")
    upsert_product(s, data, [*data["variants"], second])
    first_request = service.default_review("dash-av", "woo_us")
    first_request.policy.returns_rate = Decimal("0.03")
    service.save_pricing(s, "dash-a", "woo_us", first_request)
    second_request = service.default_review("dash-av2", "woo_us")
    second_request.policy.returns_rate = Decimal("0.07")
    service.save_pricing(s, "dash-a", "woo_us", second_request)
    assert (
        service.pricing(s, "dash-a", "woo_us", variant_id="dash-av")["config"]["policy"][
            "returns_rate"
        ]
        == "0.03"
    )
    assert (
        service.pricing(s, "dash-a", "woo_us", variant_id="dash-av2")["config"]["policy"][
            "returns_rate"
        ]
        == "0.07"
    )


def test_failed_category_snapshot_retains_previous_categories(client, catalog_session, monkeypatch):
    woo_mapping(catalog_session)
    client.app.state.settings.live_checks_enabled = True
    from pydantic import SecretStr

    client.app.state.settings.woo_consumer_key = SecretStr("test")
    client.app.state.settings.woo_consumer_secret = SecretStr("test")
    calls = []

    def request(self, method, url, **kwargs):
        calls.append(method)
        return [{"id": n + 100, "name": "test"} for n in range(100)]

    monkeypatch.setattr("smartandcool.integrations.http.ReadTransport.request", request)
    response = client.post("/api/categories/woo/refresh?live=true")
    assert response.status_code == 422 and len(calls) == 5
    assert catalog_session.get(WooCategory, 51) is not None
