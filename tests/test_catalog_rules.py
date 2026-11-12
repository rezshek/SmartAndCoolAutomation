from decimal import Decimal

import pytest

from smartandcool.catalog.eligibility import ProductReview, screen
from smartandcool.catalog.models import Product
from smartandcool.catalog.normalize import (
    delivery_days,
    freight_price,
    images,
    inventory_values,
    number,
    search_items,
    variant_values,
)


def product(title="Closet organizer", **changes):
    return Product(
        title=title,
        description="Plastic drawer storage for clothing",
        category_name="Home Storage",
        images=[{"url": "https://example.test/organizer.jpg"}],
        attributes={},
        **changes,
    )


@pytest.mark.parametrize(
    "title",
    [
        "Battery organizer lamp",
        "USB pet toy",
        "Dog food",
        "Pet medication",
        "Baby safety lock",
        "Disney replica rack",
        "Cosmetics serum",
        "Electric tool",
    ],
)
def test_excluded_products(title):
    assert screen(product(title))[0] == "EXCLUDED"


def test_facts_alone_are_not_compliance():
    assert screen(product())[0] == "NEEDS_REVIEW"
    review = ProductReview(source="synthetic review", safety_reviewed=True, ip_clear=True)
    assert screen(product(), review) == ("PASS", [])


def test_food_contact_and_regulatory_documents_and_missing_facts():
    review = ProductReview(source="synthetic", safety_reviewed=True, ip_clear=True)
    assert (
        "food_contact_documentation_required"
        in screen(product("Kitchen food container"), review)[1]
    )
    assert (
        "regulatory_documentation_required" in screen(product("Antibacterial storage"), review)[1]
    )
    item = product()
    item.description = None
    assert screen(item, review)[0] == "NEEDS_REVIEW"


def test_normalize_variant_units_ids_attributes_and_missing_price():
    value = variant_values(
        {
            "vid": "v",
            "pid": "p",
            "variantSku": "SKU",
            "variantWeight": "125.5",
            "variantLength": 100,
            "variantSellPrice": "2.15",
            "variantKey": "Blue-Large",
            "barcode": "123",
        },
        "p",
    )
    assert value["supplier_price"] == Decimal("2.15") and value["currency"] == "USD"
    assert value["weight_g"] == Decimal("125.5") and value["length_mm"] == 100
    assert value["attributes"]["variantKey"] == "Blue-Large"
    assert value["height_mm"] is None
    assert variant_values({"vid": "v"}, "p")["supplier_price"] is None
    with pytest.raises(ValueError):
        variant_values({"vid": "v", "pid": "other"}, "p")


def test_images_keep_urls_without_fetching_and_reject_credential_urls():
    assert images(
        {
            "bigImage": "https://example.test/a.jpg",
            "productImageSet": '["https://example.test/a.jpg","https://example.test/b.jpg","file:///bad"]',
        }
    ) == [
        {"url": "https://example.test/a.jpg", "source": "CJ"},
        {"url": "https://example.test/b.jpg", "source": "CJ"},
    ]
    assert images({"bigImage": "https://secret:private@example.test/a"}) == []


def test_country_total_and_subwarehouse_are_not_added_together():
    rows = inventory_values(
        [
            {
                "countryCode": "CN",
                "totalInventoryNum": 12,
                "cjInventoryNum": 2,
                "factoryInventoryNum": 10,
                "stock": [{"stockId": "w", "inventory": 2, "factoryInventory": 10}],
            }
        ]
    )
    assert rows[0]["warehouse_id"] is None and rows[0]["quantity"] == 12
    assert rows[1]["warehouse_id"] == "w" and rows[1]["quantity"] is None
    assert inventory_values(None) == []
    assert inventory_values([{"countryCode": "CN", "stock": None}])[0]["quantity"] is None


@pytest.mark.parametrize("value", [None, "1.00-2.00", "NaN", "Infinity", -1, True])
def test_unknown_numbers_do_not_become_zero(value):
    assert number(value) is None


def test_delivery_estimates_only_parse_explicit_day_ranges():
    assert delivery_days("5-12") == (5, 12)
    assert delivery_days("3 days") == (3, 3)
    assert delivery_days("1-2 weeks") == (None, None)
    assert delivery_days("12-5") == (None, None)


def test_search_shape_fails_closed_and_keeps_multiple_groups():
    assert (
        len(
            search_items(
                {"content": [{"productList": [{"id": "a"}]}, {"productList": [{"id": "b"}]}]}
            )
        )
        == 2
    )
    with pytest.raises(ValueError):
        search_items({"content": [{"unexpected": []}]})


def test_freight_totals_error_rows_and_explicit_extra_fees():
    assert freight_price(
        {"logisticPrice": "7", "taxesFee": "1", "clearanceOperationFee": ".5"}
    ) == Decimal("8.5")
    assert freight_price({"logisticPrice": "7", "totalPostageFee": "9"}) == 9
    assert freight_price({"logisticPrice": "7", "totalPostageFee": "0"}) is None
    assert freight_price({"logisticPrice": "7", "taxesFee": "unknown"}) is None
    assert freight_price({"logisticPrice": "0", "error": "unavailable"}) is None
    assert freight_price({"logisticPrice": "0", "totalPostageFee": "0"}) == 0
