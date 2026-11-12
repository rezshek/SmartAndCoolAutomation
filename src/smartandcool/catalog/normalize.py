"""Normalize documented CJ facts without treating unknown values as zero."""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit


def json_facts(value):
    # JSONB has no Decimal encoder. Preserve their exact textual representation.
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(json_facts(value), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def number(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError):
        return None  # Ranges (e.g. 2.00-5.00) are not variant prices.


def integer(value) -> int | None:
    result = number(value)
    return int(result) if result is not None and result == result.to_integral_value() else None


def image_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if (
            url.scheme in {"https", "http"}
            and url.hostname
            and not url.username
            and not url.password
        ):
            return value
    except ValueError:
        pass
    return None


def images(data: dict) -> list:
    values = data.get("productImageSet") or []
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except ValueError:
            values = [values]
    if not isinstance(values, list):
        values = []
    values = [data.get("bigImage"), data.get("productImage"), *values]
    urls = dict.fromkeys(url for value in values if (url := image_url(value)))
    return [{"url": url, "source": "CJ"} for url in urls]


def search_items(data) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("content"), list):
        raise ValueError("Unexpected CJ search shape")
    result = []
    for group in data["content"]:
        if not isinstance(group, dict) or not isinstance(group.get("productList"), list):
            raise ValueError("Unexpected CJ search group")
        for product in group["productList"]:
            if not isinstance(product, dict) or not product.get("id"):
                raise ValueError("CJ search product missing stable ID")
            result.append(product)
    return result


def product_values(data: dict, search: dict) -> dict:
    return {
        "cj_id": str(data["pid"]),
        "sku": data.get("productSku"),
        "title": data.get("productNameEn") or search.get("nameEn") or "",
        "description": data.get("description"),
        "category_id": data.get("categoryId") or search.get("categoryId"),
        "category_name": data.get("categoryName") or search.get("threeCategoryName"),
        "images": images(data),
        "attributes": json_facts(
            {
                k: data[k]
                for k in (
                    "productKeyEn",
                    "materialNameEn",
                    "materialNameEnSet",
                    "productProEnSet",
                    "productProEn",
                    "packingWeight",
                    "entryCode",
                    "supplierId",
                    "productType",
                )
                if k in data
            }
        ),
        "supplier_price": number(data.get("sellPrice")),
        "currency": "USD",
        "weight_g": number(data.get("productWeight")),
    }


def variant_values(data: dict, product_id: str) -> dict:
    if not data.get("vid") or (data.get("pid") and str(data["pid"]) != product_id):
        raise ValueError("CJ variant missing ID or belongs to another product")
    return {
        "cj_id": str(data["vid"]),
        "product_id": product_id,
        "sku": data.get("variantSku"),
        "title": data.get("variantNameEn"),
        "attributes": json_facts(
            {
                k: data[k]
                for k in (
                    "variantKey",
                    "variantProperty",
                    "variantStandard",
                    "barcode",
                    "variantUnit",
                )
                if k in data
            }
        ),
        "image_url": image_url(data.get("variantImage")),
        "supplier_price": number(data.get("variantSellPrice")),
        "currency": "USD",
        "weight_g": number(data.get("variantWeight")),
        "length_mm": number(data.get("variantLength")),
        "width_mm": number(data.get("variantWidth")),
        "height_mm": number(data.get("variantHeight")),
        "active": True,
    }


def inventory_values(data) -> list[dict]:
    if not isinstance(data, list):
        return []
    result = []
    for area in data:
        if not isinstance(area, dict):
            raise ValueError("Unexpected CJ inventory shape")
        common = {
            "country": area.get("countryCode"),
            "area_id": str(area["areaId"]) if area.get("areaId") is not None else None,
        }
        # Keep country totals and subwarehouse facts separately; never sum both.
        result.append(
            {
                **common,
                "warehouse_id": None,
                "quantity": integer(area.get("totalInventoryNum", area.get("totalInventory"))),
                "cj_quantity": integer(area.get("cjInventoryNum", area.get("cjInventory"))),
                "factory_quantity": integer(
                    area.get("factoryInventoryNum", area.get("factoryInventory"))
                ),
                "facts": json_facts(area),
            }
        )
        for stock in area.get("stock") or []:
            result.append(
                {
                    **common,
                    "warehouse_id": stock.get("stockId"),
                    "quantity": None,
                    "cj_quantity": integer(stock.get("inventory")),
                    "factory_quantity": integer(stock.get("factoryInventory")),
                    "facts": json_facts(stock),
                }
            )
    return result


def delivery_days(text) -> tuple[int | None, int | None]:
    # Preserve unparsed strings; no guesses about "fast", business days or weeks.
    match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*(?:days?)?\s*", str(text), re.I)
    if not match:
        return None, None
    low, high = int(match[1]), int(match[2] or match[1])
    return (low, high) if 0 <= low <= high <= 365 else (None, None)


def freight_price(row: dict) -> Decimal | None:
    if row.get("error") or row.get("errorEn"):
        return None
    base = number(row.get("logisticPrice"))
    extras = [
        number(row[key])
        for key in ("taxesFee", "clearanceOperationFee")
        if row.get(key) is not None
    ]
    if any(value is None for value in extras):
        return None
    known = base + sum(extras) if base is not None else None
    if row.get("totalPostageFee") is not None:
        total = number(row["totalPostageFee"])
        # A smaller total could be a placeholder or a contract change; do not underprice.
        return total if total is not None and (known is None or total >= known) else None
    return known
