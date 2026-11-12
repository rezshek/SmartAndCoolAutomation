"""Explicitly enabled read-only probes; print aggregates only, never raw provider payloads."""

import argparse
import json

from pydantic import ValidationError

from smartandcool.config import Settings
from smartandcool.integrations.amazon import MARKETPLACES, AmazonClient
from smartandcool.integrations.cj import CJClient
from smartandcool.integrations.http import IntegrationError, ReadTransport
from smartandcool.integrations.woo import WooClient, rank_math_presence
from smartandcool.logging import configure_logging


def probe(args, settings: Settings) -> dict:
    if not args.live or not settings.live_checks_enabled:
        raise IntegrationError(args.provider, "checks require --live and LIVE_CHECKS_ENABLED=true")
    if args.provider == "cj" and bool(args.variant_id) != bool(args.postal_code):
        raise IntegrationError("cj", "freight requires both --variant-id and --postal-code")
    if args.provider == "woo" and args.product_id:
        try:
            if int(args.product_id) < 1:
                raise ValueError
        except ValueError:
            raise IntegrationError("woo", "--product-id must be a positive integer") from None
    http = ReadTransport(
        args.provider,
        timeout=settings.http_timeout_seconds,
        attempts=settings.http_max_attempts,
        min_interval=1.1 if args.provider == "cj" else 0,
    )
    try:
        if args.provider == "cj":
            client = CJClient(settings, http)
            client.search_products()
            result = {"provider": "cj", "catalog_read": True, "detail_read": False}
            if args.product_id:
                client.get_product(args.product_id)
                client.get_variants(args.product_id)
                result["detail_read"] = True
            if args.variant_id:
                client.get_stock(args.variant_id)
                quotes = client.quote_freight(
                    args.variant_id,
                    args.destination,
                    args.postal_code,
                    origin=args.origin,
                    warehouse_ids=args.warehouse_id,
                )
                if not isinstance(quotes, list):
                    raise IntegrationError("cj", "unexpected quote response")
                result["freight_destination"] = args.destination
                result["freight_options"] = len(quotes)
                result["freight_available"] = bool(quotes)
            return result
        if args.provider == "woo":
            client = WooClient(settings, http)
            products = client.list_products()
            client.get_categories()
            client.get_attributes()
            result = {"provider": "woo", "connection_read": True, "sample_count": len(products)}
            if args.product_id:
                product = client.get_product(int(args.product_id))
                variations = client.get_variations(int(args.product_id))
                result["sample_variations"] = len(variations)
                result["rank_math_keys_present"] = rank_math_presence(product)
            return result
        client = AmazonClient(settings, http)
        participation = client.get_marketplace_participations()
        markets = {}
        for country, market_id in MARKETPLACES.items():
            entry = next(
                (
                    item
                    for item in participation
                    if item.get("marketplace", {}).get("id") == market_id
                ),
                None,
            )
            markets[country] = {
                "returned": entry is not None,
                "participating": bool(
                    entry and entry.get("participation", {}).get("isParticipating")
                ),
            }
        return {"provider": "amazon", "authorization_read": True, "marketplaces": markets}
    finally:
        http.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("cj", "woo", "amazon"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--product-id")
    parser.add_argument("--variant-id")
    parser.add_argument("--destination", choices=("US", "CA"), default="US")
    parser.add_argument("--origin", default="CN")
    parser.add_argument("--postal-code")
    parser.add_argument("--warehouse-id", action="append")
    args = parser.parse_args()
    try:
        settings = Settings()
        configure_logging(settings)
        result = probe(args, settings)
    except ValidationError:
        print(json.dumps({"status": "failed", "reason": "invalid environment configuration"}))
        return 1
    except IntegrationError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}))
        return 1
    print(json.dumps({"status": "ok", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
