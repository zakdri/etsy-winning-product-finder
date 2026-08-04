from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://openapi.etsy.com/v3/application"


class EtsyAPIError(RuntimeError):
    """Raised when Etsy returns a non-retryable API error."""


@dataclass
class EtsyClient:
    api_key: str
    shared_secret: str
    access_token: str | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    max_retries: int = 5
    minimum_interval_seconds: float = 0.12

    def __post_init__(self) -> None:
        self.session = requests.Session()
        headers = {
            "x-api-key": f"{self.api_key}:{self.shared_secret}",
            "Accept": "application/json",
            "User-Agent": os.getenv(
                "ETSY_USER_AGENT", "seller-trend-product-research/0.1"
            ),
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers.update(headers)
        self._last_request_at = 0.0
        self.last_rate_limits: dict[str, str] = {}

    @property
    def auth_mode(self) -> str:
        return "oauth" if self.access_token else "api_key"

    @classmethod
    def from_env(cls) -> "EtsyClient":
        load_dotenv()
        api_key = os.getenv("ETSY_API_KEY", "").strip()
        shared_secret = os.getenv("ETSY_SHARED_SECRET", "").strip()
        access_token = os.getenv("ETSY_ACCESS_TOKEN", "").strip() or None
        if not api_key or not shared_secret:
            raise RuntimeError(
                "Missing ETSY_API_KEY or ETSY_SHARED_SECRET. "
                "Copy .env.example to .env and add the rotated credentials."
            )
        return cls(
            api_key=api_key,
            shared_secret=shared_secret,
            access_token=access_token,
            base_url=os.getenv("ETSY_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=float(os.getenv("ETSY_TIMEOUT_SECONDS", "30")),
        )

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait_for = self.minimum_interval_seconds - elapsed
        if wait_for > 0:
            time.sleep(wait_for)

    def _request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self.max_retries + 1):
            self._pace()
            try:
                response = self.session.get(
                    url, params=params, timeout=self.timeout_seconds
                )
            except requests.RequestException as exc:
                self._last_request_at = time.monotonic()
                if attempt >= self.max_retries:
                    raise EtsyAPIError(f"Request failed after retries: {exc}") from exc
                time.sleep(min(30.0, (2**attempt) + random.random()))
                continue

            self._last_request_at = time.monotonic()
            self.last_rate_limits = {
                key: value
                for key in (
                    "x-limit-per-second",
                    "x-remaining-this-second",
                    "x-remaining-this-secon",
                    "x-limit-per-day",
                    "x-remaining-today",
                    "retry-after",
                )
                if (value := response.headers.get(key)) is not None
            }

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt >= self.max_retries:
                    raise EtsyAPIError(
                        f"Etsy API returned {response.status_code}: "
                        f"{response.text[:500]}"
                    )
                retry_after = response.headers.get("retry-after")
                try:
                    delay = max(1.0, float(retry_after)) if retry_after else min(
                        60.0, (2**attempt) + random.random()
                    )
                except ValueError:
                    delay = min(60.0, 2**attempt)
                time.sleep(delay)
                continue

            if not response.ok:
                raise EtsyAPIError(
                    f"Etsy API returned {response.status_code} for {path}: "
                    f"{response.text[:1000]}"
                )

            payload = response.json()
            if not isinstance(payload, dict):
                raise EtsyAPIError(
                    "Unexpected Etsy API response: expected a JSON object"
                )
            return payload

        raise EtsyAPIError("Unexpected retry loop termination")

    def find_active_listings(
        self,
        *,
        keywords: str,
        limit: int = 100,
        offset: int = 0,
        sort_on: str = "created",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not 0 <= offset <= 12000:
            raise ValueError("offset must be between 0 and 12000")
        return self._request(
            "listings/active",
            params={
                "keywords": keywords,
                "limit": limit,
                "offset": offset,
                "sort_on": sort_on,
                "sort_order": sort_order,
            },
        )

    def get_shop(self, shop_id: int) -> dict[str, Any]:
        if shop_id < 1:
            raise ValueError("shop_id must be positive")
        return self._request(f"shops/{shop_id}")
