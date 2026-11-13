from typing import Literal

from pydantic import Field, field_validator, model_validator

from smartandcool.catalog.eligibility import ProductReview
from smartandcool.catalog.pricing import FX, InputModel, PricingPolicy
from smartandcool.catalog.report import ServiceReview

Profile = Literal["amazon_us", "amazon_ca", "woo_us"]
State = Literal["IMPORTED", "REVIEW_REQUIRED", "DRAFT_READY", "CONTENT_APPROVED"]
MARKETS = {
    "amazon_us": ("amazon", "US", "USD"),
    "amazon_ca": ("amazon", "CA", "CAD"),
    "woo_us": ("woo", "US", "USD"),
}


class Decision(InputModel):
    source: str = Field(min_length=3, max_length=1000)
    actor: str = Field(default="local-reviewer", min_length=1, max_length=100)


class PricingReview(Decision):
    variant_id: str = Field(min_length=1, max_length=200)
    policy: PricingPolicy
    fx: FX | None = None
    service_reviews: list[ServiceReview] = Field(default_factory=list, max_length=100)
    product_review: ProductReview | None = None
    quote_id: int | None = Field(default=None, ge=1)
    method_id: int | None = Field(default=None, ge=1)


class CategoryReview(Decision):
    category_id: int | None = Field(default=None, ge=1)
    suggestion: str = Field(default="", max_length=200)
    approved: bool = False
    listing_path: Literal["existing_asin", "new_catalog"] = "new_catalog"
    asin: str | None = Field(default=None, pattern=r"^[A-Z0-9]{10}$")
    required_attributes: list[str] = Field(default_factory=list, max_length=50)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=50)
    gtin: str | None = Field(default=None, max_length=30)
    gtin_exemption_source: str | None = Field(default=None, max_length=1000)
    brand_review_source: str | None = Field(default=None, max_length=1000)


class FactReview(Decision):
    facts: dict[str, str] = Field(min_length=1, max_length=30)

    @field_validator("facts")
    @classmethod
    def bounded_facts(cls, value):
        if any(not k or len(k) > 100 or not v.strip() or len(v) > 1500 for k, v in value.items()):
            raise ValueError("Facts must have short IDs and 1-1500 characters of source text")
        return value


class ListingContent(InputModel):
    title: str = Field(min_length=1, max_length=200)
    short_description: str = Field(default="", max_length=1500)
    description: str = Field(min_length=1, max_length=12000)
    headings: list[str] = Field(default_factory=list, max_length=8)
    bullets: list[str] = Field(default_factory=list, max_length=5)
    seo_title: str = Field(default="", max_length=200)
    meta_description: str = Field(default="", max_length=160)
    focus_keywords: list[str] = Field(default_factory=list, max_length=8)
    image_alt: list[str] = Field(default_factory=list, max_length=20)
    slug: str = Field(default="", max_length=200, pattern=r"^[a-z0-9-]*$")
    search_terms: str = Field(default="", max_length=249)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=40)

    @model_validator(mode="after")
    def reject_markup(self):
        import json

        text = json.dumps(self.model_dump())
        if "<" in text or ">" in text or "\u0000" in text:
            raise ValueError("Listing content must be plain text")
        return self


class DraftEdit(Decision):
    base_version: int = Field(ge=1)
    content: ListingContent


class Generate(Decision):
    live: bool = False


class Transition(Decision):
    state: State
    version: int | None = Field(default=None, ge=1)
    facts_checked: bool = False
    images_rights_reviewed: bool = False


class CatalogPage(InputModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
    categories: list[str]


class ProductDetail(InputModel):
    product: dict
    variants: list[dict]
    profiles: list[str]
    facts: dict[str, str]
    source_digest: str


class PricingView(InputModel):
    config: dict
    rows: list[dict]
    selected: dict | None
    saved: dict | None


class ChannelView(InputModel):
    profile: Profile
    state: State
    category: dict | None
    drafts: list[dict]
    indicators: dict
    blockers: list[str]
    audit: list[dict]
