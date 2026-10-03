# ozon-fbs-tool

Command-line helper for Ozon sellers working with FBS (seller's own warehouse): list postings,
ship a batch from an Excel list of numbers, print package labels. Uses the official Seller API.

![tests](https://github.com/YarSav1/ozon-fbs-tool/actions/workflows/tests.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## Why

In the seller cabinet, moving dozens of postings from "Awaiting packaging" to "Awaiting shipment"
means clicking them one by one. Warehouses usually already have the numbers in a spreadsheet,
so the tool takes that spreadsheet and does the clicking through the API — with a report of
what went through and what did not.

## Features

- `list` — postings by status and date range, saved as CSV that Excel opens correctly (Cyrillic, `;`).
- `ship` — ships postings from an Excel file. Numbers are found in any cell of any sheet, so
  the file can be a raw export or a hand-made list; duplicates are ignored.
- `labels` — one PDF with package labels for a list or a date range.
- Every number gets a result: shipped, rejected by Ozon (with Ozon's message), or not found.
- Retries with backoff when Ozon answers 429 (rate limit).

## Quick start

```bash
git clone https://github.com/YarSav1/ozon-fbs-tool.git
cd ozon-fbs-tool
pip install -e .
export OZON_CLIENT_ID=...     # Seller cabinet → Settings → Seller API
export OZON_API_KEY=...
```

```
$ python -m ozon_fbs list --status awaiting_packaging --since 2026-10-01 --to 2026-10-03 --csv today.csv
48 postings -> today.csv

$ python -m ozon_fbs ship --excel picked.xlsx
shipped 45 of 47
  22222222-0001-1: 400: POSTING_ALREADY_SHIPPED
  44444444-0001-1: not in 'awaiting packaging' for this period

$ python -m ozon_fbs labels --since 2026-10-03 --pdf labels.pdf
labels for 45 postings -> labels.pdf
```

(Output above is illustrative; the tests reproduce these cases against a mocked API.)

## Project layout

```
ozon_fbs/
  client.py     # Seller API: postings, ship, labels, retry on 429
  files.py      # posting numbers from Excel, CSV export
  __main__.py   # CLI
tests/          # Seller API replaced with httpx.MockTransport
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Limitations

- Each posting is shipped as a single box. Splitting into several packages needs the box contents
  as input and is not implemented.
- Ozon changes Seller API method versions from time to time; the paths live in constants at the top
  of `client.py` and should be checked against the current documentation before production use.
- The date filter works on whole days.

## License

MIT
