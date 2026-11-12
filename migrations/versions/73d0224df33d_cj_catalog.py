"""cj_catalog

Revision ID: 73d0224df33d
Revises: 0001_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "73d0224df33d"
down_revision: str | Sequence[str] | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed additive schema; SAL-62 history is preserved.
    op.create_table(
        "catalog_import_runs",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("query", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_page", sa.Integer(), nullable=False),
        sa.Column("pending", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("imported_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "products",
        sa.Column("cj_id", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=200), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.String(length=200), nullable=True),
        sa.Column("category_name", sa.Text(), nullable=True),
        sa.Column("images", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supplier_price", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("weight_g", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("cj_id"),
    )
    op.create_table(
        "product_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=200), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.cj_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "digest"),
    )
    op.create_index(
        op.f("ix_product_snapshots_product_id"), "product_snapshots", ["product_id"], unique=False
    )
    op.create_table(
        "variants",
        sa.Column("cj_id", sa.String(length=200), nullable=False),
        sa.Column("product_id", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=200), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("supplier_price", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("weight_g", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("length_mm", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("width_mm", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("height_mm", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inventory_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.cj_id"],
        ),
        sa.PrimaryKeyConstraint("cj_id"),
    )
    op.create_index(op.f("ix_variants_product_id"), "variants", ["product_id"], unique=False)
    op.create_table(
        "freight_quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("warehouse_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validity_source", sa.String(length=100), nullable=False),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.cj_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_freight_quotes_variant_id"), "freight_quotes", ["variant_id"], unique=False
    )
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.String(length=200), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("area_id", sa.String(length=200), nullable=True),
        sa.Column("warehouse_id", sa.String(length=200), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("cj_quantity", sa.Integer(), nullable=True),
        sa.Column("factory_quantity", sa.Integer(), nullable=True),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.cj_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventory_snapshots_variant_id"),
        "inventory_snapshots",
        ["variant_id"],
        unique=False,
    )
    op.create_table(
        "shipping_methods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("delivery_text", sa.Text(), nullable=True),
        sa.Column("min_days", sa.Integer(), nullable=True),
        sa.Column("max_days", sa.Integer(), nullable=True),
        sa.Column("tracking", sa.Boolean(), nullable=True),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["freight_quotes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_shipping_methods_quote_id"), "shipping_methods", ["quote_id"], unique=False
    )
    op.create_check_constraint("ck_product_price", "products", "supplier_price >= 0")
    op.create_check_constraint("ck_variant_price", "variants", "supplier_price >= 0")
    op.create_check_constraint(
        "ck_inventory_nonnegative",
        "inventory_snapshots",
        "quantity >= 0 AND cj_quantity >= 0 AND factory_quantity >= 0",
    )
    op.create_check_constraint("ck_quote_quantity", "freight_quotes", "quantity > 0")
    op.create_check_constraint(
        "ck_quote_destination", "freight_quotes", "destination IN ('US', 'CA')"
    )
    op.create_check_constraint("ck_quote_expiry", "freight_quotes", "expires_at > quoted_at")
    op.create_check_constraint("ck_shipping_price", "shipping_methods", "price >= 0")


def downgrade() -> None:
    # Destructive downgrade is for disposable tests, never the imported dev catalog.
    op.drop_index(op.f("ix_shipping_methods_quote_id"), table_name="shipping_methods")
    op.drop_table("shipping_methods")
    op.drop_index(op.f("ix_inventory_snapshots_variant_id"), table_name="inventory_snapshots")
    op.drop_table("inventory_snapshots")
    op.drop_index(op.f("ix_freight_quotes_variant_id"), table_name="freight_quotes")
    op.drop_table("freight_quotes")
    op.drop_index(op.f("ix_variants_product_id"), table_name="variants")
    op.drop_table("variants")
    op.drop_index(op.f("ix_product_snapshots_product_id"), table_name="product_snapshots")
    op.drop_table("product_snapshots")
    op.drop_table("products")
    op.drop_table("catalog_import_runs")
