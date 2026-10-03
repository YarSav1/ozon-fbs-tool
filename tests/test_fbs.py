import json

import httpx
import openpyxl
import pytest

from ozon_fbs.client import OzonSeller, ship_by_numbers
from ozon_fbs.files import numbers_from_excel, postings_to_csv

POSTINGS = {
    "awaiting_packaging": [
        {"posting_number": "11111111-0001-1", "status": "awaiting_packaging",
         "products": [{"sku": 101, "quantity": 2, "name": "Чехол"}]},
        {"posting_number": "22222222-0001-1", "status": "awaiting_packaging",
         "products": [{"sku": 102, "quantity": 1, "name": "Кабель"}]},
    ],
    "awaiting_deliver": [{"posting_number": "33333333-0001-1", "status": "awaiting_deliver", "products": []}],
}


class FakeOzon:
    def __init__(self, rate_limit_first=False):
        self.shipped = []
        self.rate_limit_first = rate_limit_first

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Client-Id"] == "1" and request.headers["Api-Key"] == "k"
        if self.rate_limit_first:
            self.rate_limit_first = False
            return httpx.Response(429)
        body = json.loads(request.content)
        path = request.url.path
        if path == "/v3/posting/fbs/list":
            return httpx.Response(200, json={"result": {"postings": POSTINGS[body["filter"]["status"]],
                                                        "has_next": False}})
        if path == "/v4/posting/fbs/ship":
            if body["posting_number"] == "22222222-0001-1":
                return httpx.Response(400, json={"message": "POSTING_ALREADY_SHIPPED"})
            self.shipped.append((body["posting_number"], body["packages"][0]["products"]))
            return httpx.Response(200, json={"result": [body["posting_number"]]})
        if path == "/v2/posting/fbs/package-label":
            return httpx.Response(200, content=b"%PDF-1.4 fake")
        return httpx.Response(404)


def api(fake):
    return OzonSeller("1", "k", httpx.Client(transport=httpx.MockTransport(fake)))


@pytest.fixture
def numbers_file(tmp_path):
    path = tmp_path / "numbers.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Номер", "Комментарий"])
    ws.append(["11111111-0001-1", ""])
    ws.append(["отправление 22222222-0001-1", "дубль ниже"])
    ws.append(["22222222-0001-1", ""])
    ws.append([99999999, "не номер"])
    ws.append(["44444444-0001-1", "нет в выдаче"])
    wb.save(path)
    return str(path)


def test_numbers_are_found_anywhere_without_duplicates(numbers_file):
    assert numbers_from_excel(numbers_file) == ["11111111-0001-1", "22222222-0001-1", "44444444-0001-1"]


def test_ship_reports_each_number(numbers_file):
    fake = FakeOzon()
    results = ship_by_numbers(api(fake), numbers_from_excel(numbers_file), "2026-10-01", "2026-10-03")
    assert [(r.posting_number, r.ok) for r in results] == [
        ("11111111-0001-1", True), ("22222222-0001-1", False), ("44444444-0001-1", False)]
    assert "POSTING_ALREADY_SHIPPED" in results[1].error
    assert fake.shipped == [("11111111-0001-1", [{"product_id": 101, "quantity": 2}])]


def test_retries_after_rate_limit(monkeypatch):
    monkeypatch.setattr("ozon_fbs.client.time.sleep", lambda s: None)
    postings = api(FakeOzon(rate_limit_first=True)).postings("awaiting_deliver", "2026-10-01", "2026-10-01")
    assert postings[0]["posting_number"] == "33333333-0001-1"


def test_csv_opens_in_excel(tmp_path):
    out = tmp_path / "p.csv"
    postings_to_csv(api(FakeOzon()).postings("awaiting_packaging", "2026-10-01", "2026-10-03"), str(out))
    text = out.read_text(encoding="utf-8-sig")
    assert "11111111-0001-1;awaiting_packaging" in text and "Чехол" in text


def test_labels_are_pdf():
    assert api(FakeOzon()).labels(["33333333-0001-1"]).startswith(b"%PDF")
