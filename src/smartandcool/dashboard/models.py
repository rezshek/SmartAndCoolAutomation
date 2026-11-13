"""Append-only review decisions and content versions; supplier tables stay authoritative."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from smartandcool.db import Base


def utcnow():
    return datetime.now(UTC)


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.cj_id"), index=True)
    profile: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSONB)
    actor: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ListingVersion(Base):
    __tablename__ = "listing_versions"
    __table_args__ = (UniqueConstraint("product_id", "profile", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.cj_id"), index=True)
    profile: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSONB)
    facts: Mapped[dict] = mapped_column(JSONB)
    facts_digest: Mapped[str] = mapped_column(String(64))
    origin: Mapped[str] = mapped_column(String(30))
    usage: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WooCategory(Base):
    __tablename__ = "woo_category_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text)
    parent: Mapped[int] = mapped_column(Integer)
    store: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
