"""Ozon FBS from the command line.

  python -m ozon_fbs list   --status awaiting_packaging --since 2026-10-01 --to 2026-10-03 --csv out.csv
  python -m ozon_fbs ship   --excel numbers.xlsx
  python -m ozon_fbs labels --since 2026-10-03 --pdf labels.pdf

Credentials: OZON_CLIENT_ID and OZON_API_KEY environment variables.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from .client import AWAITING_DELIVER, AWAITING_PACKAGING, OzonSeller, ship_by_numbers
from .files import numbers_from_excel, postings_to_csv


def main(argv=None) -> int:
    today = date.today().isoformat()
    parser = argparse.ArgumentParser(prog="ozon_fbs")
    parser.add_argument("command", choices=["list", "ship", "labels"])
    parser.add_argument("--status", default=AWAITING_PACKAGING, choices=[AWAITING_PACKAGING, AWAITING_DELIVER])
    parser.add_argument("--since", default=today)
    parser.add_argument("--to", default=today)
    parser.add_argument("--excel", help="file with posting numbers, any layout")
    parser.add_argument("--csv", default="postings.csv")
    parser.add_argument("--pdf", default="labels.pdf")
    args = parser.parse_args(argv)

    try:
        api = OzonSeller(os.environ["OZON_CLIENT_ID"], os.environ["OZON_API_KEY"])
    except KeyError as missing:
        print(f"set {missing} first", file=sys.stderr)
        return 2

    if args.command == "list":
        postings = api.postings(args.status, args.since, args.to)
        postings_to_csv(postings, args.csv)
        print(f"{len(postings)} postings -> {args.csv}")

    elif args.command == "ship":
        numbers = (numbers_from_excel(args.excel) if args.excel else
                   [p["posting_number"] for p in api.postings(AWAITING_PACKAGING, args.since, args.to)])
        results = ship_by_numbers(api, numbers, args.since, args.to)
        print(f"shipped {sum(r.ok for r in results)} of {len(results)}")
        for r in results:
            if not r.ok:
                print(f"  {r.posting_number}: {r.error}")

    else:
        numbers = (numbers_from_excel(args.excel) if args.excel else
                   [p["posting_number"] for p in api.postings(AWAITING_DELIVER, args.since, args.to)])
        with open(args.pdf, "wb") as f:
            f.write(api.labels(numbers))
        print(f"labels for {len(numbers)} postings -> {args.pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
