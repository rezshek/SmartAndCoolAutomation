"""Real PostgreSQL persistence with mocked CJ; never a live commerce call."""

import os
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from smartandcool.catalog.eligibility import ProductReview
from smartandcool.catalog.models import (
    ImportRun,
    InventorySnapshot,
    Product,
    ProductSnapshot,
    Variant,
)
from smartandcool.catalog.pricing import PricingPolicy
from smartandcool.catalog.report import ReportConfig, ServiceReview, build_report, write_report
from smartandcool.catalog.service import import_candidates, save_quote, upsert_product
from smartandcool.config import Settings
from smartandcool.db import create_db_engine
from smartandcool.integrations.cj import CJClient
from smartandcool.integrations.http import IntegrationError, ReadTransport

NOW = datetime.now(UTC)


def detail(pid="p"):
    return {
        "pid": pid,
        "productNameEn": "Closet organizer",
        "productSku": "SKU-" + pid,
        "description": "Plastic storage for clothing",
        "categoryId": "home",
        "categoryName": "Home Storage",
        "productImageSet": ["https://example.test/image.jpg"],
        "sellPrice": "2-4",
        "variants": [
            {
                "vid": pid + "v",
                "pid": pid,
                "variantSku": "SKU-" + pid + "v",
                "variantKey": "Blue",
                "variantSellPrice": "3",
                "variantWeight": "50",
                "inventories": [
                    {
                        "countryCode": "CN",
                        "totalInventory": 10,
                        "cjInventory": 10,
                        "factoryInventory": 0,
                        "stock": None,
                    }
                ],
            }
        ],
    }


@pytest.fixture
def session(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable *_test PostgreSQL database")
    assert make_url(url).database.endswith("_test"), "Refusing non-test database"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_db_engine(Settings(_env_file=None))
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as value:
            yield value
        transaction.rollback()
    engine.dispose()


def client_for(handler, *, budget=100):
    http = ReadTransport(
        "cj",
        max_requests=budget,
        max_points=1000,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    return CJClient(
        Settings(
            _env_file=None,
            cj_access_token="synthetic",
            cj_refresh_token="synthetic",
            cj_access_token_expires_at="2099-01-01T00:00:00Z",
            cj_refresh_token_expires_at="2099-02-01T00:00:00Z",
        ),
        http,
    )


def envelope(data):
    return httpx.Response(200, json={"code": 200, "result": True, "data": data})


@pytest.mark.database
def test_idempotent_reimports_update_and_preserve_history(session):
    data = detail()
    upsert_product(session, data, data["variants"], now=NOW)
    upsert_product(session, data, data["variants"], now=NOW + timedelta(seconds=1))
    assert session.scalar(select(func.count()).select_from(Product)) == 1
    assert session.scalar(select(func.count()).select_from(Variant)) == 1
    assert session.scalar(select(func.count()).select_from(ProductSnapshot)) == 1
    assert session.scalar(select(func.count()).select_from(InventorySnapshot)) == 2
    changed = deepcopy(data)
    changed["variants"][0]["variantSellPrice"] = "4.25"
    upsert_product(session, changed, changed["variants"], now=NOW + timedelta(seconds=2))
    assert str(session.get(Variant, "pv").supplier_price) == "4.250000"
    assert session.scalar(select(func.count()).select_from(ProductSnapshot)) == 2


@pytest.mark.database
def test_removed_variant_is_inactive_and_missing_stock_invalidates_old_inventory(session):
    data = detail()
    other = {**data["variants"][0], "vid": "other"}
    upsert_product(session, data, [*data["variants"], other], now=NOW)
    del data["variants"][0]["inventories"]
    upsert_product(session, data, data["variants"], now=NOW + timedelta(seconds=1))
    assert session.get(Variant, "other").active is False
    assert session.get(Variant, "pv").inventory_at is None
    assert session.scalar(select(func.count()).select_from(InventorySnapshot)) == 2


@pytest.mark.database
def test_duplicate_and_reparented_variants_fail_closed(session):
    data = detail()
    upsert_product(session, data, data["variants"], now=NOW)
    session.commit()
    other = detail("other")
    other["variants"][0]["vid"] = "pv"
    with pytest.raises(ValueError, match="already belongs"):
        upsert_product(session, other, other["variants"])
    session.rollback()
    assert session.get(Variant, "pv").product_id == "p"
    assert session.get(Product, "other") is None


@pytest.mark.database
def test_budget_interrupt_resume_and_frozen_pagination(session):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("listV2"):
            page = int(request.url.params["page"])
            ids = ["p", "q"] if page == 1 else ["q", "r"]
            return envelope(
                {"content": [{"productList": [{"id": pid} for pid in ids]}], "totalPages": 2}
            )
        return envelope(detail(request.url.params["pid"]))

    client = client_for(handler, budget=2)
    try:
        with pytest.raises(IntegrationError, match="budget"):
            import_candidates(
                session, client, "resume", keyword="organizer", category_id="home", limit=3, size=2
            )
        session.rollback()
        run = session.get(ImportRun, "resume")
        assert run.imported_ids == ["p"] and len(run.pending) == 1
        assert session.scalar(select(func.count()).select_from(Product)) == 1
        assert calls[0].url.params["categoryId"] == "home"
    finally:
        client.http.close()
    client = client_for(handler)
    try:
        result = import_candidates(session, client, "resume", keyword="IGNORED", resume=True)
        assert result["status"] == "COMPLETE" and result["imported"] == 3
        assert session.scalar(select(func.count()).select_from(Variant)) == 3
        assert sum(r.url.params.get("pid") == "p" for r in calls) == 1
        assert [r.url.params["page"] for r in calls if r.url.path.endswith("listV2")] == ["1", "2"]
    finally:
        client.http.close()


@pytest.mark.database
def test_bad_product_response_leaves_resumable_checkpoint(session):
    def handler(request):
        if request.url.path.endswith("listV2"):
            return envelope({"content": [{"productList": [{"id": "p"}]}]})
        return envelope(detail("WRONG"))

    client = client_for(handler)
    try:
        with pytest.raises(IntegrationError, match="ID mismatch"):
            import_candidates(session, client, "bad")
        session.rollback()
        assert session.get(ImportRun, "bad").pending == [{"id": "p"}]
        assert session.get(Product, "p") is None
    finally:
        client.http.close()


def configured():
    return ReportConfig(
        profiles={
            "amazon_us": PricingPolicy(
                channel="amazon",
                country="US",
                currency="USD",
                category="Home",
                referral_rate=".15",
                shipping_revenue={"amount": "0"},
                returns_rate=".05",
                additional_unit_cost={"amount": "0"},
                max_price="100",
            )
        }
    )


@pytest.mark.database
def test_multiple_shipping_methods_and_unverified_service_stay_under_review(session, tmp_path):
    data = detail()
    upsert_product(session, data, data["variants"])
    client = client_for(
        lambda _: envelope(
            [
                {"logisticName": "Tracked", "logisticPrice": "7", "logisticAging": "5-10"},
                {"logisticName": "Slow", "logisticPrice": "5", "logisticAging": "30-45"},
                {"logisticName": "Missing price", "logisticAging": "5-10"},
            ]
        )
    )
    try:
        quote = save_quote(session, client, "pv", "US", "10001", origin="CN", quantity=2)
        assert len(quote.facts) == 3
        report = build_report(session, configured())
        assert len(report["rows"]) == 3
        assert {r["method"] for r in report["rows"]} == {"Tracked", "Slow", "Missing price"}
        row = next(r for r in report["rows"] if r["method"] == "Tracked")
        assert row["status"] == "NEEDS_REVIEW" and "tracking_unverified" in row["reasons"]
        assert row["freight_cost"] == "3.500000"
        assert next(r for r in report["rows"] if r["method"] == "Slow")["status"] == "REJECTED"
        path = tmp_path / "report.csv"
        write_report(report, path)
        assert path.exists() and path.with_suffix(".assumptions.json").exists()
    finally:
        client.http.close()


@pytest.mark.database
def test_unavailable_route_supersedes_old_quote_and_stale_freight_is_not_used(session):
    data = detail()
    upsert_product(session, data, data["variants"])
    client = client_for(
        lambda _: envelope(
            [{"logisticName": "Tracked", "logisticPrice": "7", "logisticAging": "5-10"}]
        )
    )
    try:
        quote = save_quote(session, client, "pv", "US", "10001", origin="CN")
        quote.quoted_at = datetime.now(UTC) - timedelta(days=2)
        quote.expires_at = datetime.now(UTC) - timedelta(days=1)
        session.commit()
        report = build_report(session, configured())
        assert report["rows"][0]["status"] == "UNPRICEABLE"
        assert report["rows"][0]["selling_price"] is None
        assert "freight_stale" in report["rows"][0]["reasons"]
    finally:
        client.http.close()
    client = client_for(lambda _: envelope([]))
    try:
        save_quote(session, client, "pv", "US", "10001", origin="CN")
        rows = build_report(session, configured())["rows"]
        assert len(rows) == 1 and rows[0]["method"] is None
        assert "no_available_shipping_methods" in rows[0]["reasons"]
    finally:
        client.http.close()


@pytest.mark.database
def test_missing_inventory_shipping_and_amazon_credit_are_reported(session):
    data = detail()
    del data["variants"][0]["inventories"]
    upsert_product(session, data, data["variants"])
    config = configured()
    config.profiles["amazon_us"].shipping_revenue = None
    row = build_report(session, config)["rows"][0]
    assert row["status"] == "UNPRICEABLE"
    assert {"inventory_unknown", "freight_not_quoted", "missing_shipping_revenue"} <= set(
        row["reasons"]
    )


@pytest.mark.database
def test_quote_origin_specific_inventory_and_no_zero_from_unknown(session):
    data = detail()
    data["variants"][0]["inventories"][0]["totalInventory"] = 0
    data["variants"][0]["inventories"][0]["cjInventory"] = 0
    upsert_product(session, data, data["variants"])
    client = client_for(
        lambda _: envelope(
            [{"logisticName": "Tracked", "logisticPrice": "7", "logisticAging": "5-10"}]
        )
    )
    try:
        save_quote(session, client, "pv", "US", "10001", origin="CN")
        save_quote(session, client, "pv", "US", "90210", origin="US", warehouse_ids=["w"])
        rows = build_report(session, configured())["rows"]
        cn = next(r for r in rows if r["origin"] == "CN")
        us = next(r for r in rows if r["origin"] == "US")
        assert cn["status"] == "REJECTED" and "insufficient_inventory" in cn["reasons"]
        assert "origin_inventory_unknown" in us["reasons"]
    finally:
        client.http.close()


@pytest.mark.database
def test_complete_verified_candidate_can_pass_but_zero_freight_requires_separate_evidence(session):
    data = detail()
    upsert_product(session, data, data["variants"])
    client = client_for(
        lambda _: envelope(
            [
                {
                    "logisticName": "Tracked",
                    "logisticPrice": "0",
                    "logisticAging": "5-10",
                    "trackingAvailable": True,
                }
            ]
        )
    )
    try:
        quote = save_quote(session, client, "pv", "US", "10001", origin="CN")
        config = configured()
        policy = config.profiles["amazon_us"]
        policy.fees_verified = policy.shipping_revenue_verified = policy.landed_costs_verified = (
            True
        )
        policy.fee_source = policy.shipping_revenue_source = policy.landed_cost_source = (
            "synthetic evidence"
        )
        config.product_reviews["p"] = ProductReview(
            source="synthetic safety/IP evidence", safety_reviewed=True, ip_clear=True
        )
        config.service_reviews = [
            ServiceReview(
                quote_id=quote.id,
                method_id=build_report(session, config)["rows"][0]["method_id"],
                method="Tracked",
                destination="US",
                origin="CN",
                source="synthetic service evidence",
                tracking_verified=True,
                eligible=True,
            )
        ]
        row = build_report(session, config)["rows"][0]
        assert row["pricing_status"] == "PASS" and row["status"] == "NEEDS_REVIEW"
        assert row["reasons"] == ["zero_freight_requires_verification"]
        config.service_reviews[0].zero_price_verified = True
        row = build_report(session, config)["rows"][0]
        assert row["status"] == "PASS" and row["reasons"] == []
        assert row["supplier_cost"] == "3.000000" and row["freight_cost"] == "0.000000"
        expired = build_report(session, config, now=quote.expires_at)["rows"][0]
        assert expired["status"] == "UNPRICEABLE" and expired["selling_price"] is None
        assert "freight_stale" in expired["reasons"]
    finally:
        client.http.close()


@pytest.mark.database
@pytest.mark.parametrize(
    "change",
    [
        {"variant_id": "qv", "postal_code": "90210"},
        {"variant_id": "qv"},
        {"postal_code": "90210"},
        {"warehouse_ids": ["w"]},
        {"quantity": 2},
        {},  # A fresh quote for the same route must also be reviewed again.
    ],
    ids=["variant-and-postal", "variant", "postal", "warehouse", "quantity", "requote"],
)
def test_shipping_review_is_scoped_to_exact_quote_and_method(session, change):
    for pid in ("p", "q"):
        data = detail(pid)
        upsert_product(session, data, data["variants"])
    method = {"logisticName": "Tracked", "logisticPrice": "0", "logisticAging": "5-10"}
    client = client_for(lambda _: envelope([method, method]))
    try:
        route = {"variant_id": "pv", "destination": "US", "postal_code": "10001", "origin": "CN"}
        quote = save_quote(session, client, **route)
        config = configured()
        rows = [r for r in build_report(session, config)["rows"] if r["quote_id"] == quote.id]
        approved_id = rows[0]["method_id"]
        config.service_reviews = [
            ServiceReview(
                quote_id=quote.id,
                method_id=approved_id,
                method="Tracked",
                destination="US",
                origin="CN",
                source="synthetic service evidence",
                tracking_verified=True,
                eligible=True,
                zero_price_verified=True,
            )
        ]
        flags = {
            "tracking_unverified",
            "shipping_service_eligibility_unverified",
            "zero_freight_requires_verification",
        }
        rows = [r for r in build_report(session, config)["rows"] if r["quote_id"] == quote.id]
        approved = next(r for r in rows if r["method_id"] == approved_id)
        sibling = next(r for r in rows if r["method_id"] != approved_id)
        assert not flags.intersection(approved["reasons"])
        assert flags <= set(sibling["reasons"])

        other = save_quote(session, client, **{**route, **change})
        rows = [r for r in build_report(session, config)["rows"] if r["quote_id"] == other.id]
        assert len(rows) == 2
        assert all(flags <= set(r["reasons"]) and r["status"] != "PASS" for r in rows)
    finally:
        client.http.close()


@pytest.mark.database
def test_report_screens_mixed_variants_despite_parent_manual_review(session):
    data = detail()
    base = data["variants"][0]
    data["variants"] = [
        {**base, "vid": "safe", "variantNameEn": "Blue organizer"},
        {**base, "vid": "battery", "variantNameEn": "Battery organizer"},
        {**base, "vid": "usb", "variantProperty": {"power": "USB"}},
    ]
    upsert_product(session, data, data["variants"])
    config = configured()
    config.product_reviews["p"] = ProductReview(
        source="synthetic safety/IP evidence", safety_reviewed=True, ip_clear=True
    )
    rows = {r["variant_id"]: r for r in build_report(session, config)["rows"]}
    assert rows["safe"]["eligibility"] == "PASS"
    assert rows["safe"]["status"] != "REJECTED"
    for vid in ("battery", "usb"):
        assert rows[vid]["eligibility"] == "EXCLUDED"
        assert rows[vid]["status"] == "REJECTED"
        assert "electrical_or_battery" in rows[vid]["reasons"]


@pytest.mark.database
def test_postgres_rejects_negative_supplier_cost(session):
    data = detail()
    upsert_product(session, data, data["variants"])
    session.commit()
    with pytest.raises(IntegrityError), session.begin_nested():
        variant = session.get(Variant, "pv")
        variant.supplier_price = -1
        session.flush()
