from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from smartandcool.catalog.pricing import FX, Money, PricingPolicy, calculate, convert

NOW = datetime(2026, 11, 12, 18, tzinfo=UTC)


def amazon(**changes):
    return PricingPolicy.model_validate(
        {
            "channel": "amazon",
            "country": "US",
            "currency": "USD",
            "category": "Home",
            "referral_rate": "0.15",
            "fee_source": "synthetic verified schedule",
            "fees_verified": True,
            "shipping_revenue": {"amount": "0", "currency": "USD"},
            "shipping_revenue_source": "synthetic credit",
            "shipping_revenue_verified": True,
            "returns_rate": "0.05",
            "additional_unit_cost": {"amount": "0", "currency": "USD"},
            "landed_cost_source": "synthetic landed costs",
            "landed_costs_verified": True,
            "max_price": "100",
            **changes,
        }
    )


def test_amazon_hand_checked_cent_rounded_economics():
    result = calculate(amazon(), Money(amount="3"), Money(amount="7"), now=NOW)
    assert result.status == "PASS"
    assert result.selling_price == D("19.99")
    assert result.referral_fee == D("3.00")
    assert result.individual_fee == D("0.99")
    assert result.returns_reserve == D("1.00")
    assert result.profit == D("5.00")
    assert result.margin == D("5") / D("19.99")


def test_known_shipping_credit_reduces_item_price_but_is_fee_bearing():
    result = calculate(
        amazon(shipping_revenue={"amount": "4.49"}), Money(amount="3"), Money(amount="7"), now=NOW
    )
    assert result.selling_price == D("15.50")
    assert result.total_revenue == D("19.99")
    assert result.referral_fee == D("3")
    assert result.profit == D("5.00")


def test_quantity_divides_total_freight_only():
    result = calculate(amazon(), Money(amount="3"), Money(amount="14"), quantity=2, now=NOW)
    assert result.freight_cost == D("7")
    assert result.supplier_cost == D("3")
    assert result.individual_fee == D("0.99")
    assert result.selling_price == D("19.99")


def test_woo_processing_and_different_fee_structure():
    policy = amazon(channel="woo", processing_rate="0.029", processing_fixed="0.30")
    result = calculate(policy, Money(amount="3"), Money(amount="7"), now=NOW)
    assert result.status == "PASS"
    assert result.individual_fee == result.referral_fee == 0
    assert result.payment_fee == (result.total_revenue * D("0.029") + D("0.30")).quantize(
        D(".01"), rounding="ROUND_CEILING"
    )
    assert result.profit >= 5 and result.margin >= D(".25")
    assert result.selling_price < 20


def test_cad_costs_fx_and_usd_minimum_profit_are_distinct():
    fx = FX(usd_to_cad="1.40", source="synthetic fixture", observed_at=NOW, verified=True)
    result = calculate(
        amazon(country="CA", currency="CAD", shipping_revenue={"amount": "0", "currency": "CAD"}),
        Money(amount="3"),
        Money(amount="7"),
        fx=fx,
        now=NOW,
    )
    assert result.status == "PASS"
    assert result.supplier_cost == D("4.2") and result.freight_cost == D("9.8")
    assert result.individual_fee == D("1.39")
    assert result.profit >= 7 and result.profit_usd >= 5
    assert result.margin >= D(".25")
    assert convert(Money(amount="14", currency="CAD"), "USD", fx) == 10


@pytest.mark.parametrize("age", [timedelta(days=2), timedelta(seconds=-1)])
def test_stale_or_future_fx_is_unpriceable(age):
    fx = FX(usd_to_cad="1.4", source="synthetic", observed_at=NOW - age)
    result = calculate(
        amazon(country="CA", currency="CAD"), Money(amount="3"), Money(amount="7"), fx=fx, now=NOW
    )
    assert result.status == "UNPRICEABLE"
    assert result.selling_price is None


def test_cad_has_no_invented_fx():
    result = calculate(
        amazon(country="CA", currency="CAD"), Money(amount="3"), Money(amount="7"), now=NOW
    )
    assert result.status == "UNPRICEABLE" and "missing_usd_cad_fx" in result.reasons


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"shipping_revenue": None}, "missing_shipping_revenue"),
        ({"returns_rate": None}, "missing_returns_reserve"),
        ({"referral_rate": None}, "missing_amazon_category_or_referral_rate"),
        ({"additional_unit_cost": None}, "missing_additional_variable_costs"),
        ({"channel": "woo"}, "missing_woo_processing_fees"),
    ],
)
def test_missing_critical_assumptions_never_recommend_profit(changes, reason):
    result = calculate(amazon(**changes), Money(amount="3"), Money(amount="7"), now=NOW)
    assert result.status == "UNPRICEABLE" and result.selling_price is None
    assert reason in result.reasons


def test_unprofitable_at_competitor_price_is_rejected():
    result = calculate(amazon(competitor_price="8"), Money(amount="3"), Money(amount="7"), now=NOW)
    assert result.status == "REJECTED" and result.profit < 0
    assert result.selling_price == 8 and result.required_price == D("19.99")


def test_referral_minimum_and_ad_scenario_recheck_actual_thresholds():
    base = calculate(amazon(), Money(amount="3"), Money(amount="7"), now=NOW)
    result = calculate(
        amazon(referral_minimum="5", advertising_rate=".10", advertising_unit_cost={"amount": "1"}),
        Money(amount="3"),
        Money(amount="7"),
        now=NOW,
    )
    assert result.selling_price > base.selling_price
    assert result.referral_fee >= 5 and result.advertising_cost >= 1
    assert result.profit >= 5 and result.margin >= D(".25")


def test_provisional_rates_credits_costs_fx_and_cap_are_labeled():
    result = calculate(
        amazon(
            fees_verified=False,
            shipping_revenue_verified=False,
            landed_costs_verified=False,
            max_price=None,
        ),
        Money(amount="3"),
        Money(amount="7"),
        now=NOW,
    )
    assert result.status == "NEEDS_REVIEW"
    assert set(result.reasons) == {
        "provisional_fee_assumptions",
        "unverified_shipping_revenue",
        "unverified_duties_taxes_or_variable_costs",
        "commercial_price_cap_missing",
    }


def test_impossible_fee_schedule_and_missing_freight():
    result = calculate(
        amazon(referral_rate=".6", returns_rate=".2"), Money(amount="3"), Money(amount="7"), now=NOW
    )
    assert result.status == "UNPRICEABLE"
    assert calculate(amazon(), Money(amount="3"), None, now=NOW).status == "UNPRICEABLE"


@pytest.mark.parametrize("value", [3.25, "NaN", "Infinity", "-1"])
def test_invalid_or_float_money_rejected(value):
    with pytest.raises(ValidationError):
        Money(amount=value)


def test_configurable_profit_and_margin():
    result = calculate(
        amazon(min_profit_usd="8", min_margin=".35"), Money(amount="3"), Money(amount="7"), now=NOW
    )
    assert result.profit >= 8 and result.margin >= D(".35")
