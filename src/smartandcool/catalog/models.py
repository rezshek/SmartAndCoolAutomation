"""Local canonical records plus immutable supplier observations. No channel writes."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from smartandcool.db import Base

MONEY = Numeric(20, 6)
TIME = DateTime(timezone=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("supplier_price >= 0", name="ck_product_price"),)

    cj_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sku: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[str | None] = mapped_column(String(200))
    category_name: Mapped[str | None] = mapped_column(Text)
    images: Mapped[list] = mapped_column(JSONB)
    attributes: Mapped[dict] = mapped_column(JSONB)
    supplier_price: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    weight_g: Mapped[Decimal | None] = mapped_column(MONEY)
    synced_at: Mapped[datetime] = mapped_column(TIME)


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (UniqueConstraint("product_id", "digest"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.cj_id"), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(TIME)
    facts: Mapped[dict] = mapped_column(JSONB)


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (CheckConstraint("supplier_price >= 0", name="ck_variant_price"),)

    cj_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.cj_id"), index=True)
    sku: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSONB)
    image_url: Mapped[str | None] = mapped_column(Text)
    supplier_price: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    weight_g: Mapped[Decimal | None] = mapped_column(MONEY)
    length_mm: Mapped[Decimal | None] = mapped_column(MONEY)
    width_mm: Mapped[Decimal | None] = mapped_column(MONEY)
    height_mm: Mapped[Decimal | None] = mapped_column(MONEY)
    active: Mapped[bool] = mapped_column(Boolean)
    synced_at: Mapped[datetime] = mapped_column(TIME)
    inventory_at: Mapped[datetime | None] = mapped_column(TIME)


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        CheckConstraint(
            "quantity >= 0 AND cj_quantity >= 0 AND factory_quantity >= 0",
            name="ck_inventory_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("variants.cj_id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(TIME)
    country: Mapped[str | None] = mapped_column(String(2))
    area_id: Mapped[str | None] = mapped_column(String(200))
    warehouse_id: Mapped[str | None] = mapped_column(String(200))
    quantity: Mapped[int | None] = mapped_column(Integer)
    cj_quantity: Mapped[int | None] = mapped_column(Integer)
    factory_quantity: Mapped[int | None] = mapped_column(Integer)
    facts: Mapped[dict] = mapped_column(JSONB)


class FreightQuote(Base):
    __tablename__ = "freight_quotes"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quote_quantity"),
        CheckConstraint("destination IN ('US', 'CA')", name="ck_quote_destination"),
        CheckConstraint("expires_at > quoted_at", name="ck_quote_expiry"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("variants.cj_id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    destination: Mapped[str] = mapped_column(String(2))
    postal_code: Mapped[str] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(2))
    warehouse_ids: Mapped[list] = mapped_column(JSONB)
    quoted_at: Mapped[datetime] = mapped_column(TIME)
    expires_at: Mapped[datetime] = mapped_column(TIME)
    validity_source: Mapped[str] = mapped_column(String(100))
    facts: Mapped[list] = mapped_column(JSONB)


class ShippingMethod(Base):
    __tablename__ = "shipping_methods"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_shipping_price"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("freight_quotes.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    delivery_text: Mapped[str | None] = mapped_column(Text)
    min_days: Mapped[int | None] = mapped_column(Integer)
    max_days: Mapped[int | None] = mapped_column(Integer)
    tracking: Mapped[bool | None] = mapped_column(Boolean)
    facts: Mapped[dict] = mapped_column(JSONB)


class ImportRun(Base):
    __tablename__ = "catalog_import_runs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    query: Mapped[dict] = mapped_column(JSONB)
    next_page: Mapped[int] = mapped_column(Integer)
    pending: Mapped[list] = mapped_column(JSONB)
    imported_ids: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(TIME)
