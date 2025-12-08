import httpx
import time
from config import get_settings


class AmadeusAuth:
    def __init__(self):
        settings = get_settings()
        self.client_id = settings.amadeus_api_key
        self.client_secret = settings.amadeus_api_secret
        self.token = None
        self.expiry = 0

    async def get_token(self):
        if self.token and time.time() < self.expiry:
            return self.token  # still valid

        url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        # refresh 1 min early
        self.expiry = time.time() + data["expires_in"] - 60
        return self.token
