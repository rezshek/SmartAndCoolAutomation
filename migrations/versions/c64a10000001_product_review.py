"""SAL-64 append-only review workspace.

Revision ID: c64a10000001
Revises: 73d0224df33d
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c64a10000001"
down_revision = "73d0224df33d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.String(200), sa.ForeignKey("products.cj_id"), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_events_product_id", "review_events", ["product_id"])
    op.create_table(
        "listing_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.String(200), sa.ForeignKey("products.cj_id"), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("facts", postgresql.JSONB(), nullable=False),
        sa.Column("facts_digest", sa.String(64), nullable=False),
        sa.Column("origin", sa.String(30), nullable=False),
        sa.Column("usage", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "profile", "version"),
    )
    op.create_index("ix_listing_versions_product_id", "listing_versions", ["product_id"])
    op.create_table(
        "woo_category_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent", sa.Integer(), nullable=False),
        sa.Column("store", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    # Only for disposable test databases; never downgrade the working catalog.
    op.drop_table("woo_category_cache")
    op.drop_index("ix_listing_versions_product_id", table_name="listing_versions")
    op.drop_table("listing_versions")
    op.drop_index("ix_review_events_product_id", table_name="review_events")
    op.drop_table("review_events")
