"""Minimal Dealroom API client with automatic OAuth2 token refresh.

Requires: pip install authlib requests python-dotenv

Usage:
    from dealroom import client
    data = client.get("/entities", params={"limit": 10, "sort": "-launch_date"}).json()
"""

import os
from authlib.integrations.requests_client import OAuth2Session
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["DEALROOM_CLIENT_ID"]
CLIENT_SECRET = os.environ["DEALROOM_CLIENT_SECRET"]
USER_AGENT = os.environ["DEALROOM_USER_AGENT"]
API_BASE = os.environ.get("DEALROOM_API_BASE", "https://api-next.beta.dealroom.co")
AUTH_URL = os.environ.get(
    "DEALROOM_AUTH_URL", "https://accounts.beta.dealroom.co/oauth/token"
)
AUDIENCE = os.environ.get("DEALROOM_AUDIENCE", "https://api-next.beta.dealroom.co")


class DealroomClient:
    def __init__(self):
        self._session = OAuth2Session(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            token_endpoint=AUTH_URL,
        )
        self._session.headers.update(
            {"User-Agent": USER_AGENT, "X-Client-Id": CLIENT_ID}
        )
        self._fetch_token()

    def _fetch_token(self):
        self._session.fetch_token(
            url=AUTH_URL, grant_type="client_credentials", audience=AUDIENCE
        )

    def get(self, path: str, **kwargs):
        url = f"{API_BASE}/api{path}"
        response = self._session.get(url, **kwargs)
        if response.status_code == 401:
            self._fetch_token()
            response = self._session.get(url, **kwargs)
        return response


client = DealroomClient()


if __name__ == "__main__":
    # Sanity check
    response = client.get("/entities", params={"limit": 1})
    response.raise_for_status()
    print(response.json())
