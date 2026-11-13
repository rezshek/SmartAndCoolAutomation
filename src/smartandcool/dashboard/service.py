"""Product grouping, auditable decisions and commercial checks over SAL-63 records."""

import hashlib
import html
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select

from smartandcool.catalog.eligibility import screen
from smartandcool.catalog.models import (
    FreightQuote,
    InventorySnapshot,
    Product,
    ShippingMethod,
    Variant,
)
from smartandcool.catalog.pricing import PricingPolicy
from smartandcool.catalog.report import ReportConfig, build_report
from smartandcool.dashboard.models import ListingVersion, ReviewEvent, WooCategory
from smartandcool.dashboard.schemas import MARKETS, CategoryReview, PricingReview, Transition


def plain(value):
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", str(value or ""), flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", text))).strip()


def safe_image(value):
    try:
        url = urlsplit(value or "")
        return value if url.scheme == "https" and url.hostname and not url.username else None
    except ValueError:
        return None


def record(row, exclude=()):
    """Explicit callers exclude raw provider payloads; no ORM relationship serialization."""
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in exclude}


def product_or_raise(session, product_id, *, lock=False):
    query = select(Product).where(Product.cj_id == product_id)
    product = session.scalar(query.with_for_update() if lock else query)
    if product is None:
        raise LookupError("Product not found")
    return product


def events(session, pid, profile=None, kind=None):
    query = select(ReviewEvent).where(ReviewEvent.product_id == pid)
    if profile is not None:
        query = query.where(ReviewEvent.profile == profile)
    if kind is not None:
        query = query.where(ReviewEvent.kind == kind)
    return session.scalars(query.order_by(ReviewEvent.id.desc())).all()


def latest(session, pid, profile, kind):
    rows = events(session, pid, profile, kind)
    return rows[0].payload if rows else None


def audit(session, pid, profile, kind, payload, actor):
    session.add(
        ReviewEvent(product_id=pid, profile=profile, kind=kind, payload=payload, actor=actor)
    )
    session.flush()


def candidates(product, variants):
    result = {"title": plain(product.title)}
    # Descriptions are supplier claims, never automatically verified facts.
    description = plain(product.description)
    for i, sentence in enumerate(re.split(r"(?<=[.!?])\s+|[\r\n]+", description)):
        if sentence and len(sentence) <= 1500:
            result[f"description_{i}"] = sentence
    for key, value in product.attributes.items():
        if value is not None and len(str(value)) <= 1000:
            result[f"attribute_{key}"] = f"{key}: {plain(value)}"
    for i, variant in enumerate(variants):
        if variant.title:
            result[f"variant_{i}"] = plain(variant.title)
        for key, value in variant.attributes.items():
            result[f"variant_{i}_{key}"] = f"{key}: {plain(value)}"
    return {k: v for k, v in result.items() if v and len(v) <= 1500}


def source_digest(product, variants):
    data = {
        "facts": candidates(product, variants),
        "images": product.images,
        "variants": [record(v) for v in variants],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def verified_facts(session, pid):
    product = product_or_raise(session, pid)
    variants = session.scalars(
        select(Variant).where(Variant.product_id == pid).order_by(Variant.cj_id)
    ).all()
    review = latest(session, pid, "all", "facts")
    digest = source_digest(product, variants)
    if not review or review["digest"] != digest:
        return {}, digest
    verified_digest = hashlib.sha256(
        json.dumps({"source": digest, "facts": review["facts"]}, sort_keys=True).encode()
    ).hexdigest()
    return review["facts"], verified_digest


def verify_facts(session, pid, request):
    detail = product_detail(session, pid)
    available = detail["facts"]
    if any(k not in available or available[k] != v for k, v in request.facts.items()):
        raise ValueError("Only exact source facts may be verified; refresh the product first")
    audit(
        session,
        pid,
        "all",
        "facts",
        {"facts": request.facts, "digest": detail["source_digest"], "source": request.source},
        request.actor,
    )


def product_summary(session, product):
    variants = session.scalars(
        select(Variant).where(Variant.product_id == product.cj_id, Variant.active)
    ).all()
    review_payload = latest(session, product.cj_id, "all", "eligibility")
    from smartandcool.catalog.eligibility import ProductReview

    review = ProductReview.model_validate(review_payload) if review_payload else None
    eligible, reasons = screen(product, review)
    exclusions = [v.cj_id for v in variants if screen(product, review, variant=v)[0] == "EXCLUDED"]
    inventory = session.scalars(
        select(InventorySnapshot)
        .join(Variant, Variant.cj_id == InventorySnapshot.variant_id)
        .where(
            Variant.product_id == product.cj_id,
            InventorySnapshot.observed_at == Variant.inventory_at,
        )
    ).all()
    country_rows = [r for r in inventory if r.warehouse_id is None]
    quantities = [r.quantity for r in country_rows if r.quantity is not None]
    costs = [v.supplier_price for v in variants if v.supplier_price is not None]
    images = [safe_image(i.get("url")) for i in product.images if isinstance(i, dict)]
    missing = []
    if not any(images):
        missing.append("images")
    if not product.category_name:
        missing.append("category")
    if not variants or len(costs) != len(variants):
        missing.append("cost")
    if not inventory or any(v.inventory_at is None for v in variants):
        missing.append("inventory")
    return {
        "cj_id": product.cj_id,
        "title": plain(product.title),
        "category_name": plain(product.category_name),
        "category_id": product.category_id,
        "images": [i for i in images if i],
        "supplier_cost": min(costs) if costs else None,
        "currency": product.currency,
        "variant_count": len(variants),
        "eligibility": eligible,
        "exclusion_reasons": reasons,
        "excluded_variants": exclusions,
        "inventory": "available"
        if any(q > 0 for q in quantities)
        else "out"
        if quantities and len(quantities) == len(country_rows)
        else "unknown",
        "origins": sorted({r.country for r in inventory if r.country}),
        "inventory_observed_at": max(
            (v.inventory_at for v in variants if v.inventory_at), default=None
        ),
        "missing": missing,
        "publishing_ready": False,
        "pricing_readiness": "REVIEW_REQUIRED"
        if latest(session, product.cj_id, None, "pricing")
        else "UNPRICEABLE",
    }


def catalog(
    session,
    *,
    page=1,
    page_size=12,
    q="",
    category="",
    min_cost=None,
    max_cost=None,
    inventory="",
    origin="",
    eligibility="",
    missing="",
    profitability="",
    profile="woo_us",
):
    query = select(Product).order_by(Product.title, Product.cj_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            Product.title.ilike(f"%{escaped}%", escape="\\")
            | Product.cj_id.ilike(f"%{escaped}%", escape="\\")
        )
    if category:
        query = query.where(Product.category_name == category)
    variant_match = select(Variant.cj_id).where(Variant.product_id == Product.cj_id, Variant.active)
    if min_cost is not None:
        variant_match = variant_match.where(Variant.supplier_price >= min_cost)
    if max_cost is not None:
        variant_match = variant_match.where(Variant.supplier_price <= max_cost)
    if min_cost is not None or max_cost is not None:
        query = query.where(variant_match.exists())
    products = session.scalars(query).all()
    # SQL handles search/category/cost. Derived evidence filters are bounded to this local catalog.
    items = [product_summary(session, p) for p in products]
    if inventory:
        items = [p for p in items if p["inventory"] == inventory]
    if origin:
        items = [p for p in items if origin in p["origins"]]
    if eligibility:
        items = [p for p in items if p["eligibility"] == eligibility]
    if missing:
        items = (
            [p for p in items if p["missing"]]
            if missing == "any"
            else [p for p in items if missing in p["missing"]]
        )
    if profitability:
        items = [
            p for p in items if pricing_readiness(session, p["cj_id"], profile) == profitability
        ]
    return {
        "items": items[(page - 1) * page_size : page * page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "categories": list(
            session.scalars(
                select(Product.category_name)
                .where(Product.category_name.is_not(None))
                .distinct()
                .order_by(Product.category_name)
            )
        ),
    }


def product_detail(session, pid):
    product = product_or_raise(session, pid)
    variants = session.scalars(
        select(Variant).where(Variant.product_id == pid).order_by(Variant.cj_id)
    ).all()
    result = []
    review = latest(session, pid, "all", "eligibility")
    from smartandcool.catalog.eligibility import ProductReview

    review = ProductReview.model_validate(review) if review else None
    for variant in variants:
        inventory = session.scalars(
            select(InventorySnapshot).where(
                InventorySnapshot.variant_id == variant.cj_id,
                InventorySnapshot.observed_at == variant.inventory_at,
            )
        ).all()
        routes = {}
        for quote in session.scalars(
            select(FreightQuote)
            .where(FreightQuote.variant_id == variant.cj_id)
            .order_by(FreightQuote.quoted_at.desc(), FreightQuote.id.desc())
        ):
            key = (
                quote.destination,
                quote.postal_code,
                quote.origin,
                tuple(sorted(quote.warehouse_ids)),
                quote.quantity,
            )
            if key in routes:
                continue
            methods = session.scalars(
                select(ShippingMethod).where(ShippingMethod.quote_id == quote.id)
            ).all()
            routes[key] = {
                "destination": quote.destination,
                "postal_code": quote.postal_code,
                "origin": quote.origin,
                "warehouse_ids": quote.warehouse_ids,
                "quantity": quote.quantity,
                "expires_at": quote.expires_at,
                "quote_id": quote.id,
                "method_count": len(methods),
                "status": "STALE"
                if quote.expires_at <= datetime.now(UTC)
                else "UNVERIFIED"
                if methods
                else "UNAVAILABLE",
            }
        result.append(
            {
                **record(variant),
                "image_url": safe_image(variant.image_url),
                "eligibility": screen(product, review, variant=variant),
                "inventory": [record(r, ("facts",)) for r in inventory],
                "shipping": list(routes.values()),
            }
        )
    return {
        "product": {
            **product_summary(session, product),
            "description": plain(product.description),
            "attributes": product.attributes,
            "synced_at": product.synced_at,
            "sku": product.sku,
        },
        "variants": result,
        "profiles": list(MARKETS),
        "facts": candidates(product, variants),
        "source_digest": source_digest(product, variants),
    }


def default_review(variant, profile):
    channel, country, currency = MARKETS[profile]
    return PricingReview(
        variant_id=variant,
        policy=PricingPolicy(channel=channel, country=country, currency=currency),
        source="Pending manual review",
    )


def pricing(session, pid, profile, request=None, *, variant_id=None):
    product_or_raise(session, pid)
    variants = session.scalars(
        select(Variant).where(Variant.product_id == pid, Variant.active).order_by(Variant.cj_id)
    ).all()
    if not variants:
        return {"config": {}, "rows": [], "selected": None, "saved": None}
    selected_variant = request.variant_id if request else (variant_id or variants[0].cj_id)
    saved = next(
        (
            e.payload
            for e in events(session, pid, profile, "pricing")
            if e.payload["request"]["variant_id"] == selected_variant
        ),
        None,
    )
    request = request or (
        PricingReview.model_validate(saved["request"])
        if saved
        else default_review(selected_variant, profile)
    )
    if (request.policy.channel, request.policy.country, request.policy.currency) != MARKETS[
        profile
    ]:
        raise ValueError("Policy must match the selected channel, country and currency")
    if request.variant_id not in {v.cj_id for v in variants}:
        raise ValueError("Select an active variant of this product")
    review = latest(session, pid, "all", "eligibility")
    config = ReportConfig(
        profiles={profile: request.policy},
        fx=request.fx,
        service_reviews=request.service_reviews,
        product_reviews={pid: request.product_review or review}
        if (request.product_review or review)
        else {},
    )
    rows = build_report(session, config, product_ids=[pid], variant_ids=[request.variant_id])[
        "rows"
    ]
    selected = next(
        (
            r
            for r in rows
            if request.quote_id is not None
            and request.method_id is not None
            and r["variant_id"] == request.variant_id
            and r["quote_id"] == request.quote_id
            and r["method_id"] == request.method_id
        ),
        None,
    )
    return {
        "config": request.model_dump(mode="json"),
        "rows": rows,
        "selected": selected,
        "saved": saved,
    }


def save_pricing(session, pid, profile, request):
    result = pricing(session, pid, profile, request)
    if request.method_id is not None and result["selected"] is None:
        raise ValueError("Selected quote/method does not belong to this variant and market")
    payload = {
        "request": request.model_dump(mode="json"),
        "result": result["selected"],
        "decision": "APPROVED"
        if result["selected"] and result["selected"]["status"] == "PASS"
        else "SAVED_FOR_REVIEW",
    }
    audit(session, pid, profile, "pricing", payload, request.actor)
    result["saved"] = payload
    if request.product_review:
        audit(
            session,
            pid,
            "all",
            "eligibility",
            request.product_review.model_dump(mode="json"),
            request.actor,
        )
    return result


def pricing_readiness(session, pid, profile):
    active = session.scalars(
        select(Variant.cj_id).where(Variant.product_id == pid, Variant.active)
    ).all()
    saved = {}
    for event in events(session, pid, profile, "pricing"):
        saved.setdefault(event.payload["request"]["variant_id"], event.payload)
    if not active or any(vid not in saved for vid in active):
        return "UNPRICEABLE"
    statuses = []
    for vid in active:
        view = pricing(session, pid, profile, variant_id=vid)
        row = view["selected"]
        status = row["status"] if row else "UNPRICEABLE"
        if status == "PASS" and (
            saved[vid]["decision"] != "APPROVED" or row != saved[vid]["result"]
        ):
            status = "NEEDS_REVIEW"
        statuses.append(status)
    return next((s for s in ("REJECTED", "UNPRICEABLE", "NEEDS_REVIEW") if s in statuses), "PASS")


def map_category(session, pid, profile, request: CategoryReview, store):
    payload = request.model_dump(mode="json")
    if profile == "woo_us":
        category = session.get(WooCategory, request.category_id) if request.category_id else None
        fresh = (
            category
            and category.store == store
            and category.retrieved_at >= (datetime.now(UTC) - timedelta(hours=24))
        )
        if request.approved and not fresh:
            raise ValueError("Approval requires a current category ID from this Woo store")
        payload["status"] = (
            "APPROVED" if request.approved else ("SUGGESTED" if category else "MISSING_CATEGORY")
        )
        payload["name"] = category.name if category else request.suggestion
        payload["store"] = store
        payload["retrieved_at"] = category.retrieved_at.isoformat() if category else None
    else:
        if request.approved:
            raise ValueError(
                "Amazon mappings remain provisional without account-specific validation"
            )
        payload["status"] = "PROVISIONAL"
        blockers = [
            "account_specific_product_type_validation_unavailable",
            "brand_restrictions_unverified",
        ]
        if request.listing_path == "existing_asin" and not request.asin:
            blockers.append("exact_asin_match_required")
        if request.listing_path == "new_catalog" and not (
            request.gtin or request.gtin_exemption_source
        ):
            blockers.append("gtin_or_category_brand_exemption_required")
        blockers.extend(
            "missing_attribute_" + key
            for key in request.required_attributes
            if not request.attributes.get(key)
        )
        payload["blockers"] = blockers
    audit(session, pid, profile, "category", payload, request.actor)
    return payload


def versions(session, pid, profile):
    return session.scalars(
        select(ListingVersion)
        .where(ListingVersion.product_id == pid, ListingVersion.profile == profile)
        .order_by(ListingVersion.version.desc())
    ).all()


def channel(session, pid, profile, store=None):
    product = product_or_raise(session, pid)
    drafts = versions(session, pid, profile)
    approval = latest(session, pid, profile, "transition")
    state = approval["state"] if approval else "IMPORTED"
    facts, digest = verified_facts(session, pid)
    current_approval = bool(
        drafts
        and approval
        and state == "CONTENT_APPROVED"
        and approval["version"] == drafts[0].version
        and approval["digest"] == digest
    )
    if state == "CONTENT_APPROVED" and not current_approval:
        state = "DRAFT_READY" if drafts else "REVIEW_REQUIRED"
    mapping = latest(session, pid, profile, "category")
    category_ok = bool(mapping and mapping["status"] == "APPROVED")
    if profile == "woo_us" and category_ok:
        cached = session.get(WooCategory, mapping.get("category_id"))
        category_ok = bool(
            cached
            and cached.store == store
            and mapping.get("store") == store
            and cached.retrieved_at >= datetime.now(UTC) - timedelta(hours=24)
        )
    summary = product_summary(session, product)
    view = pricing(session, pid, profile)
    selected = view["selected"]
    indicators = {
        "eligibility": summary["eligibility"],
        "category_mapping": "APPROVED"
        if category_ok
        else (
            mapping["status"] if mapping and mapping["status"] != "APPROVED" else "REVIEW_REQUIRED"
        ),
        "shipping_verification": "VERIFIED"
        if selected
        and not any(
            x.startswith(
                (
                    "shipping_",
                    "freight_",
                    "zero_",
                    "service_",
                    "delivery_",
                    "tracking_",
                    "provider_method_",
                )
            )
            or x == "no_available_shipping_methods"
            for x in selected["reasons"]
        )
        else "REVIEW_REQUIRED",
        "pricing": pricing_readiness(session, pid, profile),
        "content": "APPROVED" if current_approval else state,
        "publishing": "DISABLED",
    }
    blockers = ["marketplace_publishing_not_implemented"]
    if summary["eligibility"] != "PASS":
        blockers.extend(summary["exclusion_reasons"])
    if summary["excluded_variants"]:
        blockers.append("excluded_variants_require_channel_selection")
    if not category_ok:
        blockers.append("category_mapping_requires_review")
    if indicators["pricing"] != "PASS":
        blockers.append("verified_saved_price_required")
    if not current_approval:
        blockers.append("current_content_approval_required")
    if not facts:
        blockers.append("verified_source_facts_required")
    if profile.startswith("amazon"):
        blockers.extend(
            ["amazon_individual_no_sp_api", "image_compliance_and_gtin_review_required"]
        )
    return {
        "profile": profile,
        "state": state,
        "category": mapping,
        "drafts": [record(v) for v in drafts],
        "indicators": indicators,
        "blockers": list(dict.fromkeys(blockers)),
        "audit": [record(e) for e in events(session, pid)[:100]],
    }


def transition(session, pid, profile, request: Transition, store=None):
    view = channel(session, pid, profile, store)
    allowed = {
        "IMPORTED": {"REVIEW_REQUIRED"},
        "REVIEW_REQUIRED": {"DRAFT_READY"},
        "DRAFT_READY": {"CONTENT_APPROVED", "REVIEW_REQUIRED"},
        "CONTENT_APPROVED": {"REVIEW_REQUIRED"},
    }
    if request.state not in allowed[view["state"]]:
        raise ValueError("Invalid workflow transition")
    drafts = versions(session, pid, profile)
    if request.state in ("DRAFT_READY", "CONTENT_APPROVED") and not drafts:
        raise ValueError("Save a validated draft first")
    facts, digest = verified_facts(session, pid)
    if request.state == "CONTENT_APPROVED":
        if not request.facts_checked or not request.images_rights_reviewed:
            raise ValueError("Review facts and image rights explicitly before approving content")
        if not facts or drafts[0].facts_digest != digest or request.version != drafts[0].version:
            raise ValueError("Approval requires the current version and current verified facts")
        if drafts[0].origin == "mock":
            raise ValueError("Mock drafts are development examples and cannot be approved")
        if not view["category"] or not view["category"].get(
            "category_id" if profile == "woo_us" else "suggestion"
        ):
            raise ValueError("Review a channel category before content approval")
        if profile == "woo_us" and view["indicators"]["category_mapping"] != "APPROVED":
            raise ValueError("Approve a current Woo category before content approval")
        if profile.startswith("amazon") and view["category"].get("blockers"):
            raise ValueError("Amazon account/category/attribute validation is still provisional")
    audit(
        session,
        pid,
        profile,
        "transition",
        {**request.model_dump(mode="json"), "digest": digest},
        request.actor,
    )
    return channel(session, pid, profile, store)
