import httpx

from smartandcool.config import Settings
from smartandcool.integrations.http import IntegrationError, ReadTransport

RANK_MATH_KEYS = ("rank_math_title", "rank_math_description", "rank_math_focus_keyword")


class WooClient:
    def __init__(self, settings: Settings, http: ReadTransport):
        if not all(
            (settings.woo_base_url, settings.woo_consumer_key, settings.woo_consumer_secret)
        ):
            raise IntegrationError("woo", "missing HTTPS store URL or read-only credentials")
        self.base_url = settings.woo_base_url + "/wp-json/wc/v3/"
        self.auth = httpx.BasicAuth(
            settings.woo_consumer_key.get_secret_value(),
            settings.woo_consumer_secret.get_secret_value(),
        )
        self.http = http

    def _get(self, path: str, *, collection: bool = False, **params):
        data = self.http.request("GET", self.base_url + path, auth=self.auth, params=params)
        if not isinstance(data, list if collection else dict):
            raise IntegrationError("woo", "unexpected response shape")
        return data

    def list_products(self, *, page: int = 1, per_page: int = 1):
        if page < 1 or not 1 <= per_page <= 100:
            raise ValueError("Invalid Woo pagination")
        return self._get("products", collection=True, page=page, per_page=per_page)

    def get_product(self, product_id: int):
        if product_id < 1:
            raise ValueError("Product ID must be positive")
        return self._get(f"products/{product_id}")

    def get_variations(self, product_id: int, *, page: int = 1, per_page: int = 10):
        if product_id < 1 or page < 1 or not 1 <= per_page <= 100:
            raise ValueError("Invalid Woo product ID or pagination")
        return self._get(
            f"products/{product_id}/variations", collection=True, page=page, per_page=per_page
        )

    def get_categories(self, *, page: int = 1, per_page: int = 10):
        if page < 1 or not 1 <= per_page <= 100:
            raise ValueError("Invalid Woo pagination")
        return self._get("products/categories", collection=True, page=page, per_page=per_page)

    def get_attributes(self):
        return self._get("products/attributes", collection=True, per_page=10)


def rank_math_presence(product: dict) -> dict[str, bool]:
    """Presence only: missing metadata does not prove the site cannot support it."""
    keys = {item.get("key") for item in product.get("meta_data", [])}
    return {key: key in keys for key in RANK_MATH_KEYS}
