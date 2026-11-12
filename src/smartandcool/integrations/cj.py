from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, ValidationError

from smartandcool.config import Settings
from smartandcool.integrations.http import IntegrationError, ReadTransport

BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1/"


class Tokens(BaseModel):
    model_config = ConfigDict(populate_by_name=True, hide_input_in_errors=True)

    access_token: SecretStr = Field(alias="accessToken", min_length=1)
    access_expires_at: AwareDatetime = Field(alias="accessTokenExpiryDate")
    refresh_token: SecretStr = Field(alias="refreshToken", min_length=1)
    refresh_expires_at: AwareDatetime = Field(alias="refreshTokenExpiryDate")


class CJClient:
    """Sequential client; keep one instance per process and never run concurrent CJ checks."""

    def __init__(self, settings: Settings, http: ReadTransport):
        self.settings = settings
        self.http = http
        self.http.min_interval = max(self.http.min_interval, 1.1)
        self.tokens: Tokens | None = None
        if all(
            (
                settings.cj_access_token,
                settings.cj_access_token_expires_at,
                settings.cj_refresh_token,
                settings.cj_refresh_token_expires_at,
            )
        ):
            self.tokens = Tokens(
                access_token=settings.cj_access_token,
                access_expires_at=settings.cj_access_token_expires_at,
                refresh_token=settings.cj_refresh_token,
                refresh_expires_at=settings.cj_refresh_token_expires_at,
            )

    def _unwrap(self, payload):
        if (
            not isinstance(payload, dict)
            or payload.get("result") is not True
            or payload.get("code") != 200
            or payload.get("data") is None
        ):
            # CJ can report errors inside HTTP 200. Never retry these blindly.
            raise IntegrationError("cj", "unsuccessful API envelope")
        return payload["data"]

    def authenticate(self) -> SecretStr:
        now = datetime.now(UTC) + timedelta(minutes=5)
        if self.tokens and self.tokens.access_expires_at > now:
            return self.tokens.access_token
        if self.tokens and self.tokens.refresh_expires_at > now:
            path = "authentication/refreshAccessToken"
            body = {"refreshToken": self.tokens.refresh_token.get_secret_value()}
        elif self.settings.cj_api_key:
            path = "authentication/getAccessToken"
            body = {"apiKey": self.settings.cj_api_key.get_secret_value()}
        else:
            raise IntegrationError("cj", "missing API key or reusable token pair")
        data = self._unwrap(self.http.request("POST", BASE_URL + path, json=body))
        try:
            tokens = Tokens.model_validate(data)
        except ValidationError:
            raise IntegrationError("cj", "invalid token response") from None
        if tokens.access_expires_at <= now:
            # Server caching can return the same expiring token. Do not loop on auth.
            raise IntegrationError("cj", "returned token expired or too close to expiry")
        self.tokens = tokens
        return tokens.access_token

    def _request(self, method: str, path: str, **kwargs):
        token = self.authenticate()
        return self._unwrap(
            self.http.request(
                method,
                BASE_URL + path,
                headers={"CJ-Access-Token": token.get_secret_value()},
                **kwargs,
            )
        )

    def search_products(self, keyword: str = "organizer", *, page: int = 1, size: int = 1):
        if not 1 <= page <= 1000 or not 1 <= size <= 100:
            raise ValueError("CJ page/size outside documented range")
        return self._request(
            "GET", "product/listV2", params={"keyWord": keyword, "page": page, "size": size}
        )

    def get_product(self, product_id: str):
        return self._request("GET", "product/query", params={"pid": product_id})

    def get_variants(self, product_id: str):
        return self._request("GET", "product/variant/query", params={"pid": product_id})

    def get_stock(self, variant_id: str):
        return self._request("GET", "product/stock/queryByVid", params={"vid": variant_id})

    def quote_freight(
        self,
        variant_id: str,
        destination: str,
        postal_code: str,
        *,
        origin: str = "CN",
        quantity: int = 1,
        warehouse_ids: list[str] | None = None,
    ):
        if destination not in {"US", "CA"} or quantity < 1 or not postal_code.strip():
            raise ValueError("Require US/CA destination, postal code and positive quantity")
        body = {
            "startCountryCode": origin,
            "endCountryCode": destination,
            "zip": postal_code,
            "products": [{"vid": variant_id, "quantity": quantity}],
        }
        if warehouse_ids:
            body["storageIdList"] = warehouse_ids
        return self._request("POST", "logistic/freightCalculate", json=body)
