"""Deterministic per-unit contribution economics. All monetary inputs use Decimal."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

D = Decimal
CENT = D("0.01")
Currency = Literal["USD", "CAD"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    @field_validator("*", mode="before")
    @classmethod
    def no_float(cls, value):
        if isinstance(value, float):
            raise ValueError("Use Decimal or decimal strings, never float")
        return value


class Money(InputModel):
    amount: Decimal = Field(ge=0, allow_inf_nan=False)
    currency: Currency = "USD"


class FX(InputModel):
    usd_to_cad: Decimal = Field(gt=0, allow_inf_nan=False)
    source: str = Field(min_length=1)
    observed_at: AwareDatetime
    verified: bool = False
    max_age_hours: int = Field(default=24, ge=1, le=168)


class PricingPolicy(InputModel):
    channel: Literal["amazon", "woo"]
    country: Literal["US", "CA"]
    currency: Currency
    category: str | None = None
    referral_rate: Decimal | None = Field(default=None, ge=0, lt=1)
    referral_minimum: Decimal = Field(default=D("0"), ge=0)
    fee_source: str | None = None
    fees_verified: bool = False
    # Owner-requested provisional Individual fee, USD. Override separately for CA.
    individual_fee: Money = Money(amount=D("0.99"), currency="USD")
    processing_rate: Decimal | None = Field(default=None, ge=0, lt=1)
    processing_fixed: Decimal | None = Field(default=None, ge=0)
    shipping_revenue: Money | None = None  # Explicit zero is different from unknown.
    shipping_revenue_source: str | None = None
    shipping_revenue_verified: bool = False
    returns_rate: Decimal | None = Field(default=None, ge=0, lt=1)
    additional_unit_cost: Money | None = None  # Duties/tax/packaging etc., explicit zero allowed.
    landed_cost_source: str | None = None
    landed_costs_verified: bool = False
    advertising_rate: Decimal = Field(default=D("0"), ge=0, lt=1)
    advertising_unit_cost: Money = Money(amount=D("0"))
    min_margin: Decimal = Field(default=D("0.25"), ge=0, lt=1)
    min_profit_usd: Decimal = Field(default=D("5"), ge=0)
    max_price: Decimal | None = Field(default=None, gt=0)
    competitor_price: Decimal | None = Field(default=None, gt=0)


class PricingResult(InputModel):
    status: Literal["PASS", "NEEDS_REVIEW", "UNPRICEABLE", "REJECTED"]
    currency: Currency
    reasons: list[str] = []
    required_price: Decimal | None = None
    selling_price: Decimal | None = None
    shipping_revenue: Decimal | None = None
    total_revenue: Decimal | None = None
    supplier_cost: Decimal | None = None
    freight_cost: Decimal | None = None
    referral_fee: Decimal | None = None
    individual_fee: Decimal | None = None
    payment_fee: Decimal | None = None
    returns_reserve: Decimal | None = None
    advertising_cost: Decimal | None = None
    additional_cost: Decimal | None = None
    profit: Decimal | None = None
    profit_usd: Decimal | None = None
    margin: Decimal | None = None


def convert(money: Money, currency: Currency, fx: FX | None) -> Decimal:
    if money.currency == currency:
        return money.amount
    if fx is None:
        raise ValueError("missing_usd_cad_fx")
    return money.amount * fx.usd_to_cad if currency == "CAD" else money.amount / fx.usd_to_cad


def ceil_cent(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_CEILING)


def calculate(
    policy: PricingPolicy,
    supplier: Money | None,
    freight: Money | None,
    *,
    fx: FX | None = None,
    quantity: int = 1,
    now: datetime | None = None,
) -> PricingResult:
    """Freight is for the quoted batch; every other cost and credit is per unit.

    R = item price + actual shipping revenue. Profit = R - supplier - freight/q
    - max(referral_rate*R, referral_minimum) - Individual fee - processing
    - returns_rate*R - ads_rate*R - fixed ads - additional costs.
    Margin = profit/R. Sales taxes collected/remitted are outside merchant revenue.
    """
    now = now or datetime.now(UTC)
    currency = policy.currency
    missing = []
    if quantity < 1:
        raise ValueError("Quantity must be positive")
    for name, value in (
        ("supplier_cost", supplier),
        ("freight", freight),
        ("shipping_revenue", policy.shipping_revenue),
        ("returns_reserve", policy.returns_rate),
        ("additional_variable_costs", policy.additional_unit_cost),
    ):
        if value is None:
            missing.append("missing_" + name)
    if policy.channel == "amazon":
        if policy.referral_rate is None or not policy.category:
            missing.append("missing_amazon_category_or_referral_rate")
    elif policy.processing_rate is None or policy.processing_fixed is None:
        missing.append("missing_woo_processing_fees")
    if policy.currency != ("USD" if policy.country == "US" else "CAD"):
        missing.append("market_currency_mismatch")
    if missing:
        return PricingResult(status="UNPRICEABLE", currency=currency, reasons=missing)
    try:
        with localcontext() as ctx:
            ctx.prec = 28
            product_cost = convert(supplier, currency, fx)
            shipping_cost = convert(freight, currency, fx) / D(quantity)
            credit = convert(policy.shipping_revenue, currency, fx)
            additional = convert(policy.additional_unit_cost, currency, fx)
            fixed_ads = convert(policy.advertising_unit_cost, currency, fx)
            minimum_profit = convert(Money(amount=policy.min_profit_usd), currency, fx)
            individual = (
                convert(policy.individual_fee, currency, fx) if policy.channel == "amazon" else D(0)
            )
    except ValueError as error:
        return PricingResult(status="UNPRICEABLE", currency=currency, reasons=[str(error)])
    uses_fx = (
        currency == "CAD"
        or any(
            m.currency != currency
            for m in (
                supplier,
                freight,
                policy.shipping_revenue,
                policy.additional_unit_cost,
                policy.advertising_unit_cost,
            )
        )
        or (policy.channel == "amazon" and policy.individual_fee.currency != currency)
    )
    if uses_fx and (
        fx is None
        or fx.observed_at > now
        or now - fx.observed_at > timedelta(hours=fx.max_age_hours)
    ):
        return PricingResult(
            status="UNPRICEABLE", currency=currency, reasons=["stale_or_missing_fx"]
        )
    referral_rate = policy.referral_rate if policy.channel == "amazon" else D(0)
    referral_min = policy.referral_minimum if policy.channel == "amazon" else D(0)
    payment_rate = policy.processing_rate if policy.channel == "woo" else D(0)
    payment_fixed = policy.processing_fixed if policy.channel == "woo" else D(0)
    other_rate = payment_rate + policy.returns_rate + policy.advertising_rate
    denominator = D(1) - other_rate - referral_rate
    if denominator <= policy.min_margin:
        return PricingResult(
            status="UNPRICEABLE",
            currency=currency,
            reasons=["fees_and_reserves_exceed_margin_capacity"],
        )
    fixed = product_cost + shipping_cost + additional + fixed_ads + individual + payment_fixed
    required_revenue = max(
        (fixed + minimum_profit) / denominator,
        fixed / (denominator - policy.min_margin),
        (fixed + referral_min + minimum_profit) / (D(1) - other_rate),
        (fixed + referral_min) / (D(1) - other_rate - policy.min_margin),
    )

    def evaluate(price):
        revenue = price + credit
        referral = ceil_cent(max(revenue * referral_rate, referral_min))
        payment = ceil_cent(revenue * payment_rate + payment_fixed)
        reserve = ceil_cent(revenue * policy.returns_rate)
        ads = ceil_cent(revenue * policy.advertising_rate + fixed_ads)
        unit_fee = ceil_cent(individual)
        profit = (
            revenue
            - product_cost
            - shipping_cost
            - additional
            - referral
            - unit_fee
            - payment
            - reserve
            - ads
        )
        return {
            "selling_price": price,
            "shipping_revenue": credit,
            "total_revenue": revenue,
            "supplier_cost": product_cost,
            "freight_cost": shipping_cost,
            "referral_fee": referral,
            "individual_fee": unit_fee,
            "payment_fee": payment,
            "returns_reserve": reserve,
            "advertising_cost": ads,
            "additional_cost": additional,
            "profit": profit,
            "profit_usd": convert(Money(amount=max(D(0), profit), currency=currency), "USD", fx)
            if profit >= 0
            else -convert(Money(amount=-profit, currency=currency), "USD", fx),
            "margin": profit / revenue if revenue else D(0),
        }

    price = ceil_cent(max(CENT, required_revenue - credit))
    # Round fees up conservatively, then recheck thresholds at actual cent precision.
    for _ in range(1000):
        values = evaluate(price)
        if values["profit"] >= minimum_profit and values["margin"] >= policy.min_margin:
            break
        price += CENT
    else:
        return PricingResult(
            status="UNPRICEABLE", currency=currency, reasons=["cent_rounding_did_not_converge"]
        )
    cap = min(
        (x for x in (policy.max_price, policy.competitor_price) if x is not None), default=None
    )
    if cap is not None and cap < price:
        return PricingResult(
            status="REJECTED",
            currency=currency,
            required_price=price,
            reasons=["required_price_exceeds_commercial_cap"],
            **evaluate(cap),
        )
    review = []
    if not policy.fees_verified or not policy.fee_source:
        review.append("provisional_fee_assumptions")
    if not policy.shipping_revenue_verified or not policy.shipping_revenue_source:
        review.append("unverified_shipping_revenue")
    if not policy.landed_costs_verified or not policy.landed_cost_source:
        review.append("unverified_duties_taxes_or_variable_costs")
    if uses_fx and not fx.verified:
        review.append("provisional_fx")
    if cap is None:
        review.append("commercial_price_cap_missing")
    return PricingResult(
        status="NEEDS_REVIEW" if review else "PASS",
        currency=currency,
        required_price=price,
        reasons=review,
        **values,
    )
