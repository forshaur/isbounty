"""CLI entry point for isBounty.

Usage:
    isbounty <url> [url2 ...]
    isbounty --json <url>          # emit full evidence as JSON
"""
from __future__ import annotations

import sys
import argparse
import requests

from .pipeline import Pipeline
from .utils.evidence import to_human_readable, to_json
from . import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="isbounty",
        description="Scan and classify bug bounty and vulnerability disclosure policies.",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more target policy URLs to analyze",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit full evidence and breakdown as JSON",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.urls:
        print("Error: At least one URL must be provided.\n", file=sys.stderr)
        parse_args(["--help"])
        return 1

    pipeline = Pipeline()
    exit_code = 0

    for url in args.urls:
        try:
            result = pipeline.run(url)
        except requests.RequestException as e:
            print(f"{url}: FETCH_ERROR ({e})", file=sys.stderr)
            exit_code = 2
            continue

        if args.as_json:
            print(to_json(result))
        else:
            print(to_human_readable(result))
        print("-" * 70)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
