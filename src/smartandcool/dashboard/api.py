"""Typed local-only admin endpoints. No publisher, order or payment routes exist."""

import secrets
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from smartandcool.dashboard import generation, service
from smartandcool.dashboard.models import WooCategory
from smartandcool.dashboard.schemas import (
    CatalogPage,
    CategoryReview,
    ChannelView,
    DraftEdit,
    FactReview,
    Generate,
    PricingReview,
    PricingView,
    ProductDetail,
    Profile,
    Transition,
)
from smartandcool.integrations.http import IntegrationError, ReadTransport
from smartandcool.integrations.woo import WooClient

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def local_origin(value):
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "http"
            and parsed.hostname in LOOPBACK
            and parsed.port in (3000, 3001, 8000)
        )
    except ValueError:
        return False


def authorize(request: Request):
    settings = request.app.state.settings
    if not request.client or request.client.host not in LOOPBACK:
        raise HTTPException(403, "Dashboard is restricted to this computer")
    if request.url.hostname not in LOOPBACK:
        raise HTTPException(403, "Invalid local host")
    origin = request.headers.get("origin")
    if origin and not local_origin(origin):
        raise HTTPException(403, "Cross-origin admin requests are blocked")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site admin requests are blocked")
    if settings.dashboard_token and not secrets.compare_digest(
        request.headers.get("authorization", ""),
        "Bearer " + settings.dashboard_token.get_secret_value(),
    ):
        raise HTTPException(401, "Admin authentication required")


router = APIRouter(prefix="/api", dependencies=[Depends(authorize)], tags=["Product review"])


def database(request: Request):
    with Session(request.app.state.engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


DB = Annotated[Session, Depends(database)]


@router.get("/settings")
def capabilities(request: Request):
    settings = request.app.state.settings
    return {
        "ai_mode": "available" if settings.openai_api_key and settings.ai_live_enabled else "mock",
        "model": settings.openai_model,
        "woo_read_enabled": settings.live_checks_enabled,
        "publishing_enabled": False,
        "ai_price_configured": bool(
            settings.ai_price_source
            and settings.ai_input_usd_per_million is not None
            and settings.ai_output_usd_per_million is not None
        ),
    }


@router.get("/products", response_model=CatalogPage)
def products(
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    q: str = Query("", max_length=200),
    category: str = Query("", max_length=200),
    min_cost: Annotated[Decimal | None, Query(ge=0)] = None,
    max_cost: Annotated[Decimal | None, Query(ge=0)] = None,
    inventory: str = Query("", pattern="^(|available|out|unknown)$"),
    origin: str = Query("", pattern="^(|[A-Z]{2})$"),
    eligibility: str = Query("", pattern="^(|PASS|NEEDS_REVIEW|EXCLUDED)$"),
    missing: str = Query("", pattern="^(|any|images|cost|category|inventory)$"),
    profitability: str = Query("", pattern="^(|PASS|UNPRICEABLE|NEEDS_REVIEW|REJECTED)$"),
    profile: Profile = "woo_us",
):
    return service.catalog(
        db,
        page=page,
        page_size=page_size,
        q=q,
        category=category,
        min_cost=min_cost,
        max_cost=max_cost,
        inventory=inventory,
        origin=origin,
        eligibility=eligibility,
        missing=missing,
        profitability=profitability,
        profile=profile,
    )


@router.get("/products/{pid}", response_model=ProductDetail)
def detail(pid: str, db: DB):
    return service.product_detail(db, pid)


@router.put("/products/{pid}/facts")
def facts(pid: str, body: FactReview, db: DB):
    service.product_or_raise(db, pid, lock=True)
    service.verify_facts(db, pid, body)
    return {"verified": len(body.facts)}


@router.get("/products/{pid}/{profile}/pricing", response_model=PricingView)
def prices(
    pid: str, profile: Profile, db: DB, variant_id: str | None = Query(None, max_length=200)
):
    return service.pricing(db, pid, profile, variant_id=variant_id)


@router.post("/products/{pid}/{profile}/pricing/preview", response_model=PricingView)
def preview(pid: str, profile: Profile, body: PricingReview, db: DB):
    return service.pricing(db, pid, profile, body)


@router.put("/products/{pid}/{profile}/pricing", response_model=PricingView)
def save_price(pid: str, profile: Profile, body: PricingReview, db: DB):
    service.product_or_raise(db, pid, lock=True)
    return service.save_pricing(db, pid, profile, body)


@router.get("/products/{pid}/{profile}/review", response_model=ChannelView)
def review(pid: str, profile: Profile, request: Request, db: DB):
    return service.channel(db, pid, profile, request.app.state.settings.woo_base_url)


@router.put("/products/{pid}/{profile}/category")
def mapping(pid: str, profile: Profile, body: CategoryReview, request: Request, db: DB):
    service.product_or_raise(db, pid, lock=True)
    return service.map_category(db, pid, profile, body, request.app.state.settings.woo_base_url)


@router.post("/products/{pid}/{profile}/generate")
def generate(pid: str, profile: Profile, body: Generate, request: Request, db: DB):
    service.product_or_raise(db, pid, lock=True)
    row = generation.generate(db, request.app.state.settings, pid, profile, body)
    return service.record(row)


@router.put("/products/{pid}/{profile}/draft")
def edit(pid: str, profile: Profile, body: DraftEdit, db: DB):
    service.product_or_raise(db, pid, lock=True)
    return service.record(generation.edit(db, pid, profile, body))


@router.post("/products/{pid}/{profile}/transition", response_model=ChannelView)
def transition(pid: str, profile: Profile, body: Transition, request: Request, db: DB):
    service.product_or_raise(db, pid, lock=True)
    return service.transition(db, pid, profile, body, request.app.state.settings.woo_base_url)


@router.get("/categories/woo")
def categories(request: Request, db: DB):
    store = request.app.state.settings.woo_base_url
    return [
        service.record(r)
        for r in db.scalars(
            select(WooCategory).where(WooCategory.store == store).order_by(WooCategory.name)
        )
    ]


@router.post("/categories/woo/refresh")
def refresh_categories(request: Request, db: DB, live: bool = False):
    settings = request.app.state.settings
    if not live or not settings.live_checks_enabled:
        raise ValueError("Read-only Woo refresh requires live=true and LIVE_CHECKS_ENABLED=true")
    http = ReadTransport("woo", timeout=settings.http_timeout_seconds, attempts=1, max_requests=5)
    try:
        client = WooClient(settings, http)
        rows = []
        for page in range(1, 6):
            batch = client.get_categories(page=page, per_page=100)
            rows.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError("Category read cap reached; no partial snapshot saved")
        now = datetime.now(UTC)
        validated = [
            WooCategory(
                id=int(r["id"]),
                name=service.plain(r["name"]),
                parent=int(r.get("parent", 0)),
                store=settings.woo_base_url,
                retrieved_at=now,
            )
            for r in rows
        ]
        db.execute(delete(WooCategory))
        db.add_all(validated)
        return {"count": len(rows), "retrieved_at": now, "read_only": True}
    except (KeyError, TypeError):
        raise ValueError("Woo category response is invalid; previous snapshot retained") from None
    except IntegrationError:
        raise HTTPException(
            502, "Woo read failed; check server configuration and read-only access"
        ) from None
    finally:
        http.close()
