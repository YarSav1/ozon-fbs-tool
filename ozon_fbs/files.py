from __future__ import annotations

import csv
import re

import openpyxl

# Ozon posting number: 12345678-0001-1
POSTING_NUMBER = re.compile(r"\b\d{5,}-\d{4,}-\d+\b")


def numbers_from_excel(path: str) -> list[str]:
    """Posting numbers from any cell of any sheet, in order, without duplicates.
    Warehouse staff paste them wherever they like, so we do not rely on a column name."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    seen: dict[str, None] = {}
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for value in row:
                for number in POSTING_NUMBER.findall(str(value or "")):
                    seen.setdefault(number, None)
    return list(seen)


def postings_to_csv(postings: list[dict], path: str) -> None:
    # utf-8-sig + ';' so that Excel opens Cyrillic product names correctly on double click
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["posting_number", "status", "in_process_at", "shipment_date", "products", "items"])
        for p in postings:
            products = p.get("products", [])
            writer.writerow([
                p["posting_number"], p.get("status", ""), p.get("in_process_at", ""), p.get("shipment_date", ""),
                ", ".join(x.get("name", "") for x in products), sum(x.get("quantity", 0) for x in products),
            ])
