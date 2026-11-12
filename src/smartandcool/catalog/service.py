"""Small sequential import/quote workflows. Commit one complete product at a time."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from smartandcool.catalog.models import (
    FreightQuote,
    ImportRun,
    InventorySnapshot,
    Product,
    ProductSnapshot,
    ShippingMethod,
    Variant,
)
from smartandcool.catalog.normalize import (
    delivery_days,
    digest,
    freight_price,
    inventory_values,
    json_facts,
    product_values,
    search_items,
    variant_values,
)
from smartandcool.integrations.cj import CJClient
from smartandcool.integrations.http import IntegrationError


def require_local_database(url):
    if url.host not in {"127.0.0.1", "localhost", "::1"} or not url.database:
        raise ValueError("Catalog workflow permits only a loopback local development database")


def upsert_product(
    session: Session,
    detail: dict,
    variants: list,
    *,
    search: dict | None = None,
    now: datetime | None = None,
) -> Product:
    now = now or datetime.now(UTC)
    if not isinstance(detail, dict) or not detail.get("pid") or not isinstance(variants, list):
        raise ValueError("CJ product missing stable ID or complete variant list")
    search = search or {}
    values = {**product_values(detail, search), "synced_at": now}
    # Parent upsert serializes concurrent imports of this product in PostgreSQL.
    session.execute(
        insert(Product)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[Product.cj_id],
            set_={k: v for k, v in values.items() if k != "cj_id"},
        )
    )
    product_id = values["cj_id"]
    facts = json_facts(
        {
            "detail": detail,
            "variants": variants,
            "search": search,
            "source": "CJ product/query; product/variant/query fallback",
            "currency_basis": "CJ documented USD",
            "units": "g; mm",
        }
    )
    session.execute(
        insert(ProductSnapshot)
        .values(
            product_id=product_id,
            digest=digest(facts),
            observed_at=now,
            facts=facts,
        )
        .on_conflict_do_nothing(index_elements=["product_id", "digest"])
    )
    session.execute(update(Variant).where(Variant.product_id == product_id).values(active=False))
    seen = set()
    for item in variants:
        values = variant_values(item, product_id)
        if values["cj_id"] in seen:
            raise ValueError("Duplicate CJ variant in product response")
        seen.add(values["cj_id"])
        existing = session.get(Variant, values["cj_id"])
        if existing and existing.product_id != product_id:
            raise ValueError("CJ variant ID already belongs to another product")
        values.update(synced_at=now, inventory_at=now if "inventories" in item else None)
        changed = session.execute(
            insert(Variant)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[Variant.cj_id],
                set_={k: v for k, v in values.items() if k != "cj_id"},
                where=Variant.product_id == product_id,
            )
            .returning(Variant.cj_id)
        )
        if changed.scalar_one_or_none() is None:
            raise ValueError("CJ variant ID already belongs to another product")
        if "inventories" in item:
            record_inventory(session, values["cj_id"], item["inventories"], now)
    session.flush()
    session.expire_all()
    return session.get(Product, product_id)


def record_inventory(session: Session, variant_id: str, data, now: datetime):
    rows = inventory_values(data)
    for row in rows or [{"country": None, "quantity": None, "facts": {"missing": True}}]:
        session.add(InventorySnapshot(variant_id=variant_id, observed_at=now, **row))
    session.execute(update(Variant).where(Variant.cj_id == variant_id).values(inventory_at=now))


def refresh_inventory(session: Session, client: CJClient, variant_id: str):
    if session.get(Variant, variant_id) is None:
        raise ValueError("Import the variant before refreshing inventory")
    data = client.get_stock(variant_id)
    if not isinstance(data, list):
        raise ValueError("Unexpected CJ stock response")
    record_inventory(session, variant_id, data, datetime.now(UTC))
    session.commit()


def import_candidates(
    session: Session,
    client: CJClient,
    run_id: str,
    *,
    keyword: str = "organizer",
    category_id: str | None = None,
    limit: int = 50,
    size: int = 25,
    max_pages: int = 4,
    resume: bool = False,
) -> dict:
    if not 1 <= limit <= 100 or not 1 <= size <= 100 or not 1 <= max_pages <= 20:
        raise ValueError("Import limit/size must be 1..100 and max-pages 1..20")
    run = session.get(ImportRun, run_id)
    if run is None:
        if resume:
            raise ValueError("Import run does not exist")
        run = ImportRun(
            id=run_id,
            query={
                "keyword": keyword,
                "category_id": category_id,
                "limit": limit,
                "size": size,
                "max_pages": max_pages,
            },
            next_page=1,
            pending=[],
            imported_ids=[],
            status="RUNNING",
            updated_at=datetime.now(UTC),
        )
        session.add(run)
        session.commit()
    elif not resume:
        raise ValueError("Run ID already exists; use --resume to continue its frozen query")
    while True:
        # One invocation per run; row lock prevents two workers losing cursor updates.
        run = session.scalar(
            select(ImportRun)
            .where(ImportRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        query = run.query
        if len(run.imported_ids) >= query["limit"] or run.status == "COMPLETE":
            run.status = "COMPLETE"
            session.commit()
            break
        if not run.pending:
            if run.next_page > query["max_pages"]:
                run.status = "COMPLETE"
                session.commit()
                break
            page = client.search_products(
                query["keyword"],
                page=run.next_page,
                size=query["size"],
                category_id=query["category_id"],
            )
            items = search_items(page)
            run.pending = json_facts([p for p in items if str(p["id"]) not in run.imported_ids])
            run.next_page += 1
            total_pages = page.get("totalPages")
            if not items or (isinstance(total_pages, int) and run.next_page > total_pages):
                run.next_page = query["max_pages"] + 1
            run.updated_at = datetime.now(UTC)
            session.commit()  # Save discovery before consuming any detail-call budget.
            continue
        candidate = run.pending[0]
        product_id = str(candidate["id"])
        if product_id not in run.imported_ids:
            detail = client.get_product(product_id)
            if not isinstance(detail, dict) or str(detail.get("pid")) != product_id:
                raise IntegrationError("cj", "product response ID mismatch")
            variants = detail.get("variants")
            if variants is None:
                variants = client.get_variants(product_id)
            upsert_product(session, detail, variants, search=candidate)
            # upsert_product expires loaded state; the same locked row is reloaded.
            run.imported_ids = [*run.imported_ids, product_id]
        run.pending = run.pending[1:]
        run.updated_at = datetime.now(UTC)
        session.commit()  # Catalog + checkpoint are atomic. Interrupted reads replay safely.
    return {
        "run_id": run.id,
        "status": run.status,
        "imported": len(run.imported_ids),
        "next_page": run.next_page,
        "pending": len(run.pending),
    }


def save_quote(
    session: Session,
    client: CJClient,
    variant_id: str,
    destination: str,
    postal_code: str,
    *,
    origin: str,
    quantity: int = 1,
    warehouse_ids: list[str] | None = None,
    ttl_hours: int = 24,
) -> FreightQuote:
    if not 1 <= ttl_hours <= 24 or len(origin) != 2 or not 1 <= quantity <= 1000:
        raise ValueError("Quote requires two-letter origin, quantity 1..1000 and TTL 1..24 hours")
    if session.get(Variant, variant_id) is None:
        raise ValueError("Import the variant before quoting freight")
    data = client.quote_freight(
        variant_id,
        destination,
        postal_code,
        origin=origin,
        quantity=quantity,
        warehouse_ids=warehouse_ids,
    )
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("Unexpected CJ freight response")
    now = datetime.now(UTC)
    quote = FreightQuote(
        variant_id=variant_id,
        quantity=quantity,
        destination=destination,
        postal_code=postal_code.strip().upper(),
        origin=origin.upper(),
        warehouse_ids=warehouse_ids or [],
        quoted_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
        validity_source="local_policy_not_provider_guarantee",
        facts=json_facts(data),
    )
    session.add(quote)
    session.flush()
    for row in data:
        low, high = delivery_days(row.get("logisticAging"))
        price = freight_price(row)
        session.add(
            ShippingMethod(
                quote_id=quote.id,
                name=row.get("logisticName") or "Unknown",
                price=price,
                currency="USD",
                delivery_text=str(row.get("logisticAging") or ""),
                min_days=low,
                max_days=high,
                tracking=row.get("trackingAvailable")
                if isinstance(row.get("trackingAvailable"), bool)
                else None,
                facts=json_facts(row),
            )
        )
    session.commit()
    return quote
