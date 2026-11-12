import time

from pydantic import SecretStr

from smartandcool.config import Settings
from smartandcool.integrations.http import IntegrationError, ReadTransport

MARKETPLACES = {"US": "ATVPDKIKX0DER", "CA": "A2EUQ1WTGCTBG2"}
BASE_URL = "https://sellingpartnerapi-na.amazon.com"
LWA_URL = "https://api.amazon.com/auth/o2/token"


class AmazonClient:
    """Authorization/participation proof only; no listing publisher or order access."""

    def __init__(self, settings: Settings, http: ReadTransport):
        if not all(
            (
                settings.amazon_client_id,
                settings.amazon_client_secret,
                settings.amazon_refresh_token,
            )
        ):
            raise IntegrationError("amazon", "missing self-authorized LWA credentials")
        self.settings = settings
        self.http = http
        self.token: SecretStr | None = None
        self.expires_at = 0.0

    def _access_token(self) -> SecretStr:
        if self.token and self.expires_at > time.monotonic() + 60:
            return self.token
        data = self.http.request(
            "POST",
            LWA_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self.settings.amazon_client_id.get_secret_value(),
                "client_secret": self.settings.amazon_client_secret.get_secret_value(),
                "refresh_token": self.settings.amazon_refresh_token.get_secret_value(),
            },
        )
        try:
            token = data["access_token"]
            expires = int(data["expires_in"])
            if not isinstance(token, str) or not token or expires <= 60:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise IntegrationError("amazon", "invalid LWA response") from None
        self.token = SecretStr(token)
        self.expires_at = time.monotonic() + expires
        return self.token

    def get_marketplace_participations(self):
        token = self._access_token()
        data = self.http.request(
            "GET",
            BASE_URL + "/sellers/v1/marketplaceParticipations",
            headers={"x-amz-access-token": token.get_secret_value()},
        )
        if not isinstance(data, dict) or not isinstance(data.get("payload"), list):
            raise IntegrationError("amazon", "invalid marketplace response")
        return data["payload"]
