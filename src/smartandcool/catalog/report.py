"""Auditable manual-review reports; no shipping method is implicitly selected."""

import csv
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from smartandcool.catalog.eligibility import ProductReview, screen
from smartandcool.catalog.models import (
    FreightQuote,
    InventorySnapshot,
    Product,
    ShippingMethod,
    Variant,
)
from smartandcool.catalog.pricing import FX, InputModel, Money, PricingPolicy, calculate


class ServiceReview(InputModel):
    method: str
    destination: Literal["US", "CA"]
    origin: str
    source: str = Field(min_length=1)
    tracking_verified: bool = False
    eligible: bool = False
    zero_price_verified: bool = False


class ReportConfig(InputModel):
    profiles: dict[str, PricingPolicy]
    fx: FX | None = None
    product_reviews: dict[str, ProductReview] = {}
    service_reviews: list[ServiceReview] = []
    category_policies: dict[str, dict[str, PricingPolicy]] = {}
    delivery_limit_days: int = Field(default=20, ge=1, le=90)
    facts_max_age_hours: int = Field(default=24, ge=1, le=168)


def load_config(path: Path) -> ReportConfig:
    return ReportConfig.model_validate(
        json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    )


def stock_reasons(session, variant, quote, now, max_age):
    if variant.inventory_at is None:
        return ["inventory_unknown"]
    if variant.inventory_at > now or now - variant.inventory_at > max_age:
        return ["inventory_stale"]
    if quote is None:
        return ["shipping_origin_unselected"]
    rows = session.scalars(
        select(InventorySnapshot).where(
            InventorySnapshot.variant_id == variant.cj_id,
            InventorySnapshot.observed_at == variant.inventory_at,
            InventorySnapshot.country == quote.origin,
        )
    ).all()
    if quote.warehouse_ids:
        rows = [r for r in rows if r.warehouse_id in quote.warehouse_ids]
    else:
        rows = [r for r in rows if r.warehouse_id is None]
    if not rows:
        return ["origin_inventory_unknown"]
    if quote.warehouse_ids and len({r.warehouse_id for r in rows}) != len(set(quote.warehouse_ids)):
        return ["warehouse_inventory_incomplete"]
    known = [r.quantity for r in rows if r.quantity is not None]
    cj_stock = sum(r.cj_quantity or 0 for r in rows)
    if cj_stock >= quote.quantity:
        return []
    if known and len(known) == len(rows) and sum(known) < quote.quantity:
        return ["insufficient_inventory"]
    if all(r.cj_quantity == 0 and r.factory_quantity == 0 for r in rows):
        return ["insufficient_inventory"]
    return ["factory_or_unverified_inventory"]


def shipping_reasons(method, quote, config, now):
    if quote is None:
        return ["freight_not_quoted"]
    if quote.quoted_at > now or quote.expires_at <= now:
        return ["freight_stale"]
    if method is None:
        return ["no_available_shipping_methods"]
    reasons = []
    if method.price is None:
        reasons.append("shipping_price_missing")
    review = next(
        (
            r
            for r in config.service_reviews
            if r.method == method.name
            and r.destination == quote.destination
            and r.origin == quote.origin
        ),
        None,
    )
    if method.tracking is False:
        reasons.append("shipping_untracked")
    elif method.tracking is not True and not (review and review.tracking_verified):
        reasons.append("tracking_unverified")
    if not review or not review.eligible:
        reasons.append("shipping_service_eligibility_unverified")
    if method.price == 0 and not (review and review.zero_price_verified):
        reasons.append("zero_freight_requires_verification")
    if method.facts.get("error") or method.facts.get("errorEn"):
        reasons.append("provider_method_error")
    if method.max_days is None:
        reasons.append("delivery_estimate_unknown")
    elif method.max_days > config.delivery_limit_days:
        reasons.append("delivery_limit_exceeded")
    return reasons


def build_report(session: Session, config: ReportConfig, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    age = timedelta(hours=config.facts_max_age_hours)
    rows = []
    eligibility_counts = Counter()
    variants = session.scalars(select(Variant).where(Variant.active).order_by(Variant.cj_id)).all()
    for product in session.scalars(select(Product).order_by(Product.cj_id)):
        eligible, eligibility_reasons = screen(product, config.product_reviews.get(product.cj_id))
        eligibility_counts[eligible] += 1
        for variant in (v for v in variants if v.product_id == product.cj_id):
            # A newer empty/unavailable response supersedes earlier priced methods for this route.
            latest = {}
            quotes = session.scalars(
                select(FreightQuote)
                .where(FreightQuote.variant_id == variant.cj_id)
                .order_by(FreightQuote.quoted_at.desc(), FreightQuote.id.desc())
            )
            for quote in quotes:
                key = (
                    quote.destination,
                    quote.postal_code,
                    quote.origin,
                    tuple(sorted(quote.warehouse_ids)),
                    quote.quantity,
                )
                latest.setdefault(key, quote)
            for profile_name, default_policy in config.profiles.items():
                policy = config.category_policies.get(profile_name, {}).get(
                    product.category_id, default_policy
                )
                if (policy.country, policy.channel, policy.currency) != (
                    default_policy.country,
                    default_policy.channel,
                    default_policy.currency,
                ):
                    raise ValueError(
                        "Category policy must retain its profile market/channel/currency"
                    )
                market_quotes = [q for q in latest.values() if q.destination == policy.country] or [
                    None
                ]
                for quote in market_quotes:
                    methods = (
                        session.scalars(
                            select(ShippingMethod)
                            .where(ShippingMethod.quote_id == quote.id)
                            .order_by(ShippingMethod.id)
                        ).all()
                        if quote
                        else []
                    )
                    for method in methods or [None]:
                        freight_flags = shipping_reasons(method, quote, config, now)
                        stock_flags = stock_reasons(session, variant, quote, now, age)
                        stale_cost = variant.synced_at > now or now - variant.synced_at > age
                        supplier = (
                            Money(amount=variant.supplier_price, currency=variant.currency)
                            if (variant.supplier_price is not None and not stale_cost)
                            else None
                        )
                        freight = (
                            Money(amount=method.price, currency=method.currency)
                            if (
                                method
                                and method.price is not None
                                and "freight_stale" not in freight_flags
                            )
                            else None
                        )
                        result = calculate(
                            policy,
                            supplier,
                            freight,
                            fx=config.fx,
                            quantity=quote.quantity if quote else 1,
                            now=now,
                        )
                        reasons = list(
                            dict.fromkeys(
                                [
                                    *eligibility_reasons,
                                    *freight_flags,
                                    *stock_flags,
                                    *result.reasons,
                                    *(["supplier_cost_stale"] if stale_cost else []),
                                ]
                            )
                        )
                        rejection = eligible == "EXCLUDED" or any(
                            flag in reasons
                            for flag in (
                                "insufficient_inventory",
                                "shipping_untracked",
                                "delivery_limit_exceeded",
                            )
                        )
                        status = (
                            "REJECTED"
                            if rejection or result.status == "REJECTED"
                            else "UNPRICEABLE"
                            if result.status == "UNPRICEABLE"
                            else "NEEDS_REVIEW"
                            if reasons
                            else "PASS"
                        )
                        rows.append(
                            {
                                "product": product.title,
                                "product_id": product.cj_id,
                                "variant": variant.title,
                                "variant_id": variant.cj_id,
                                "supplier_sku": variant.sku,
                                "category": product.category_name,
                                "category_id": product.category_id,
                                "profile": profile_name,
                                "channel": policy.channel,
                                "country": policy.country,
                                "supplier_cost_original": str(variant.supplier_price)
                                if variant.supplier_price is not None
                                else None,
                                "supplier_currency": variant.currency,
                                "freight_total_original": str(method.price)
                                if method and method.price is not None
                                else None,
                                "freight_currency": method.currency if method else None,
                                "quote_id": quote.id if quote else None,
                                "method_id": method.id if method else None,
                                "method": method.name if method else None,
                                "quantity": quote.quantity if quote else None,
                                "postal_code": quote.postal_code if quote else None,
                                "origin": quote.origin if quote else None,
                                "warehouse_ids": quote.warehouse_ids if quote else [],
                                "quoted_at": quote.quoted_at.isoformat() if quote else None,
                                "expires_at": quote.expires_at.isoformat() if quote else None,
                                "quote_validity": quote.validity_source if quote else None,
                                "delivery_estimate": method.delivery_text if method else None,
                                "tracking_supplied": method.tracking if method else None,
                                "synced_at": variant.synced_at.isoformat(),
                                "eligibility": eligible,
                                "pricing_status": result.status,
                                **{
                                    k: v
                                    for k, v in result.model_dump(mode="json").items()
                                    if k not in {"status", "reasons"}
                                },
                                "status": status,
                                "reasons": reasons,
                            }
                        )
    priority = {"PASS": 0, "NEEDS_REVIEW": 1, "UNPRICEABLE": 2, "REJECTED": 3}
    rows.sort(
        key=lambda r: (
            priority[r["status"]],
            -(Decimal(r["profit_usd"]) if r["profit_usd"] else Decimal(0)),
            r["product_id"],
            r["variant_id"],
            r["profile"],
            r["method_id"] or 0,
        )
    )
    return {
        "generated_at": now.isoformat(),
        "assumptions": config.model_dump(mode="json"),
        "scope": "Manual candidate review; destination samples only; "
        "no method selected or listing approved",
        "products": dict(eligibility_counts),
        "scenarios": dict(Counter(r["status"] for r in rows)),
        "rows": rows,
    }


def write_report(report: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        with path.open("w", encoding="utf-8", newline="") as stream:
            rows = report["rows"]
            if rows:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                for row in rows:
                    cells = {
                        k: json.dumps(v) if isinstance(v, (list, dict)) else v
                        for k, v in row.items()
                    }
                    # Avoid spreadsheet formula execution from supplier-controlled text.
                    for key, value in cells.items():
                        if isinstance(value, str) and value.startswith(
                            ("=", "+", "-", "@", "\t", "\r")
                        ):
                            cells[key] = "'" + value
                    writer.writerow(cells)
        path.with_suffix(".assumptions.json").write_text(
            json.dumps(
                {k: v for k, v in report.items() if k != "rows"}, indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )
    else:
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
