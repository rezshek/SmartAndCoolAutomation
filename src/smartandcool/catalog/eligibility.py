"""Conservative candidate screening, never a legal certification of compliance."""

import html
import re

from smartandcool.catalog.models import Product, Variant
from smartandcool.catalog.pricing import InputModel


class ProductReview(InputModel):
    source: str
    safety_reviewed: bool = False
    ip_clear: bool = False
    food_contact_documents: bool = False
    regulatory_documents: bool = False


EXCLUSIONS = {
    "electrical_or_battery": (
        r"\b(batter(?:y|ies)|electric(?:al)?|electronic|usb|"
        r"rechargeable|powered|led light|uv lamp)\b"
    ),
    "food_supplement_medication_cosmetic": (
        r"\b(supplements?|vitamins?|medications?|medicine|drugs?|cosmetics?|serum|"
        r"shampoo|pills?|pet food|dog food|cat food|kibble|edible|snacks?|treats?)\b"
    ),
    "child_safety": (
        r"\b(baby|infant|toddler|child safety|children'?s safety|car seat|"
        r"pacifier|crib|stroller|teething)\b"
    ),
    "replica_or_ip_conflict": (
        r"\b(replica|counterfeit|knockoff|disney|pokemon|marvel|"
        r"nike|adidas|gucci)\b"
    ),
}
FOOD_CONTACT = (
    r"\b(food|dish|dishes|bowl|bowls|utensil|cutlery|spoon|fork|knife|knives|cup|"
    r"cups|plate|plates|cutting board|baking|cookware|lunch box|bottle|colander|strainer)\b"
)
REGULATED = (
    r"\b(medical|therapeutic|antibacterial|sterili[sz]|pesticide|insecticide|"
    r"protective|ppe|safety harness)\b"
)


def screen(
    product: Product, review: ProductReview | None = None, *, variant: Variant | None = None
) -> tuple[str, list[str]]:
    text = html.unescape(
        re.sub(
            r"<[^>]*>",
            " ",
            " ".join(
                str(value or "")
                for value in (
                    product.title,
                    product.description,
                    product.category_name,
                    product.attributes,
                    variant.title if variant else None,
                    variant.attributes if variant else None,
                )
            ),
        )
    ).lower()
    exclusions = [name for name, pattern in EXCLUSIONS.items() if re.search(pattern, text)]
    if exclusions:
        return "EXCLUDED", exclusions
    reasons = []
    if (
        not product.title
        or not product.description
        or not product.category_name
        or not product.images
    ):
        reasons.append("insufficient_product_facts")
    if re.search(FOOD_CONTACT, text) and not (
        review and review.source and review.food_contact_documents
    ):
        reasons.append("food_contact_documentation_required")
    if re.search(REGULATED, text) and not (
        review and review.source and review.regulatory_documents
    ):
        reasons.append("regulatory_documentation_required")
    if not review or not review.source or not review.safety_reviewed:
        reasons.append("manual_safety_review_required")
    if not review or not review.source or not review.ip_clear:
        reasons.append("brand_and_ip_review_required")
    return ("NEEDS_REVIEW", reasons) if reasons else ("PASS", [])
