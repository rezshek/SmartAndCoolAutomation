"""Bounded CJ reads and local PostgreSQL candidate workflow. No publishing endpoints."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from smartandcool.catalog.models import ImportRun, InventorySnapshot, Product, Variant
from smartandcool.catalog.normalize import search_items
from smartandcool.catalog.report import build_report, load_config, write_report
from smartandcool.catalog.service import (
    import_candidates,
    refresh_inventory,
    require_local_database,
    save_quote,
)
from smartandcool.config import Settings
from smartandcool.db import create_db_engine, session_factory
from smartandcool.integrations.cj import CJClient
from smartandcool.integrations.http import IntegrationError, ReadTransport
from smartandcool.logging import configure_logging


def private_output(value: str) -> Path:
    root = (Path.cwd() / "local-data").resolve()
    path = Path(value).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Keep private catalog exports under the ignored local-data directory")
    return path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("categories", "search", "import", "stock", "quote"):
        sub = commands.add_parser(name)
        sub.add_argument("--live", action="store_true")
        sub.add_argument("--call-budget", type=int, default=10)
        sub.add_argument("--point-budget", type=int, default=1000)
        if name in {"search", "import"}:
            sub.add_argument("--keyword", default="organizer")
            sub.add_argument("--category-id")
            sub.add_argument("--size", type=int, default=25)
        if name == "search":
            sub.add_argument("--page", type=int, default=1)
        if name in {"categories", "search"}:
            sub.add_argument("--output", required=True)
        if name == "import":
            sub.add_argument("--run-id", default=None)
            sub.add_argument("--resume", action="store_true")
            sub.add_argument("--limit", type=int, default=50)
            sub.add_argument("--max-pages", type=int, default=4)
        if name in {"stock", "quote"}:
            sub.add_argument("--variant-id", required=True)
        if name == "quote":
            sub.add_argument("--destination", choices=("US", "CA"), required=True)
            sub.add_argument("--postal-code", required=True)
            sub.add_argument("--origin", required=True)
            sub.add_argument("--warehouse-id", action="append")
            sub.add_argument("--quantity", type=int, default=1)
            sub.add_argument("--ttl-hours", type=int, default=24)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--product-id")
    inspect.add_argument("--output", required=True)
    runs = commands.add_parser("runs")
    runs.add_argument("--run-id")
    report = commands.add_parser("report")
    report.add_argument("--config", type=Path, required=True)
    report.add_argument("--output", required=True)
    return result


def execute(args, settings: Settings) -> dict:
    live = args.command in {"categories", "search", "import", "stock", "quote"}
    if live and (not args.live or not settings.live_checks_enabled):
        raise IntegrationError("cj", "checks require --live and LIVE_CHECKS_ENABLED=true")
    output = private_output(args.output) if hasattr(args, "output") else None
    engine = create_db_engine(settings)
    http = None
    try:
        require_local_database(engine.url)
        with session_factory(engine)() as session:
            if live:
                http = ReadTransport(
                    "cj",
                    timeout=settings.http_timeout_seconds,
                    attempts=settings.http_max_attempts,
                    max_requests=args.call_budget,
                    max_points=args.point_budget,
                )
                client = CJClient(settings, http)
            if args.command in {"categories", "search"}:
                data = (
                    client.get_categories()
                    if args.command == "categories"
                    else search_items(
                        client.search_products(
                            args.keyword,
                            page=args.page,
                            size=args.size,
                            category_id=args.category_id,
                        )
                    )
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
                result = {"records": len(data), "output": str(output)}
            elif args.command == "import":
                if args.resume and not args.run_id:
                    raise ValueError("--resume requires --run-id")
                run_id = args.run_id or str(uuid4())
                print(json.dumps({"run_id": run_id, "event": "starting"}), flush=True)
                result = import_candidates(
                    session,
                    client,
                    run_id,
                    keyword=args.keyword,
                    category_id=args.category_id,
                    size=args.size,
                    limit=args.limit,
                    max_pages=args.max_pages,
                    resume=args.resume,
                )
            elif args.command == "stock":
                refresh_inventory(session, client, args.variant_id)
                result = {"inventory_refreshed": True}
            elif args.command == "quote":
                quote = save_quote(
                    session,
                    client,
                    args.variant_id,
                    args.destination,
                    args.postal_code,
                    origin=args.origin,
                    quantity=args.quantity,
                    warehouse_ids=args.warehouse_id,
                    ttl_hours=args.ttl_hours,
                )
                result = {
                    "quote_id": quote.id,
                    "destination": quote.destination,
                    "methods": len(quote.facts),
                    "expires_at": quote.expires_at.isoformat(),
                }
            elif args.command == "runs":
                query = select(ImportRun)
                if args.run_id:
                    query = query.where(ImportRun.id == args.run_id)
                result = {
                    "runs": [
                        {
                            "run_id": r.id,
                            "status": r.status,
                            "imported": len(r.imported_ids),
                            "pending": len(r.pending),
                            "next_page": r.next_page,
                            "query": r.query,
                        }
                        for r in session.scalars(query)
                    ]
                }
            elif args.command == "inspect":
                query = select(Product)
                if args.product_id:
                    query = query.where(Product.cj_id == args.product_id)
                products = []
                for product in session.scalars(query.order_by(Product.cj_id)):
                    variants = session.scalars(
                        select(Variant).where(Variant.product_id == product.cj_id)
                    ).all()
                    products.append(
                        {
                            **columns(product),
                            "variants": [
                                {
                                    **columns(v),
                                    "inventory": [
                                        columns(s)
                                        for s in session.scalars(
                                            select(InventorySnapshot).where(
                                                InventorySnapshot.variant_id == v.cj_id,
                                                InventorySnapshot.observed_at == v.inventory_at,
                                            )
                                        )
                                    ],
                                }
                                for v in variants
                            ],
                        }
                    )
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(products, default=str, indent=2), encoding="utf-8")
                result = {"products": len(products), "output": str(output)}
            else:
                report = build_report(session, load_config(args.config))
                write_report(report, output)
                result = {
                    "products": report["products"],
                    "scenarios": report["scenarios"],
                    "rows": len(report["rows"]),
                    "output": str(output),
                }
            if http:
                result.update(http_requests=http.request_count, estimated_points=http.points_used)
            return result
    finally:
        if http:
            http.close()
        engine.dispose()


def columns(record):
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


def main() -> int:
    args = parser().parse_args()
    try:
        settings = Settings()
        configure_logging(settings)
        result = execute(args, settings)
    except IntegrationError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}))
        return 1
    except (ValidationError, ValueError, OSError, SQLAlchemyError):
        # Never print validation inputs, SQL parameters, connection strings or provider bodies.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "invalid catalog input or local database/file operation; "
                    "check configuration and migrations",
                }
            )
        )
        return 1
    print(json.dumps({"status": "ok", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
