import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()


class AmadeusAuth:
    def __init__(self):
        self.client_id = os.environ["AMADEUS_API_KEY"]
        self.client_secret = os.environ["AMADEUS_API_SECRET"]
        self.token = None
        self.expiry = 0

    def get_token(self):
        if self.token and time.time() < self.expiry:
            return self.token  # still valid

        url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        self.expiry = time.time() + data["expires_in"] - 60  # refresh 1 min early
        return self.token
