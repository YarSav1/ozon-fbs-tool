from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

import httpx

BASE_URL = "https://api-seller.ozon.ru"
# Ozon bumps method versions from time to time; keep them in one place.
LIST_POSTINGS = "/v3/posting/fbs/list"
SHIP_POSTING = "/v4/posting/fbs/ship"
PACKAGE_LABELS = "/v2/posting/fbs/package-label"

AWAITING_PACKAGING = "awaiting_packaging"
AWAITING_DELIVER = "awaiting_deliver"


@dataclass
class ShipResult:
    posting_number: str
    ok: bool
    error: str = ""


def day_range(since: str, to: str) -> tuple[str, str]:
    start = datetime.strptime(since, "%Y-%m-%d").strftime("%Y-%m-%dT00:00:00Z")
    end = datetime.strptime(to, "%Y-%m-%d").strftime("%Y-%m-%dT23:59:59Z")
    return start, end


class OzonSeller:
    def __init__(self, client_id: str, api_key: str, http: httpx.Client | None = None, max_retries: int = 3):
        self.http = http or httpx.Client(timeout=60)
        self.headers = {"Client-Id": client_id, "Api-Key": api_key}
        self.max_retries = max_retries

    def _post(self, path: str, body: dict) -> httpx.Response:
        for attempt in range(self.max_retries):
            response = self.http.post(BASE_URL + path, json=body, headers=self.headers)
            if response.status_code != 429 or attempt == self.max_retries - 1:
                return response
            time.sleep(2 ** attempt)  # rate limited, back off and retry
        return response

    def postings(self, status: str, since: str, to: str) -> list[dict]:
        start, end = day_range(since, to)
        found, offset = [], 0
        while True:
            response = self._post(LIST_POSTINGS, {
                "dir": "ASC", "limit": 1000, "offset": offset,
                "filter": {"since": start, "to": end, "status": status},
            })
            response.raise_for_status()
            result = response.json()["result"]
            found.extend(result["postings"])
            if not result.get("has_next"):
                return found
            offset += 1000

    def ship(self, posting: dict) -> ShipResult:
        """Pack the whole posting into one box, which moves it to 'awaiting_deliver'."""
        products = [{"product_id": p["sku"], "quantity": p["quantity"]} for p in posting.get("products", [])]
        number = posting["posting_number"]
        response = self._post(SHIP_POSTING, {"posting_number": number, "packages": [{"products": products}]})
        if response.status_code == 200:
            return ShipResult(number, True)
        try:
            message = response.json().get("message", response.text)
        except ValueError:
            message = response.text
        return ShipResult(number, False, f"{response.status_code}: {message}"[:200])

    def labels(self, posting_numbers: list[str]) -> bytes:
        response = self._post(PACKAGE_LABELS, {"posting_number": posting_numbers})
        response.raise_for_status()
        return response.content


def ship_by_numbers(api: OzonSeller, numbers: list[str], since: str, to: str) -> list[ShipResult]:
    waiting = {p["posting_number"]: p for p in api.postings(AWAITING_PACKAGING, since, to)}
    return [
        api.ship(waiting[n]) if n in waiting else ShipResult(n, False, "not in 'awaiting packaging' for this period")
        for n in numbers
    ]
