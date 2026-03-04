import argparse
import sys
from election_fetcher.config import URLS
from election_fetcher.service import fetch_data


def parse_args(argv: list[str]) -> argparse.Namespace:
    years = sorted(URLS.keys())
    default_year = years[-1]

    parser = argparse.ArgumentParser(
        description="Fetch council and mayor results for Karlstadt elections."
    )
    parser.add_argument(
        "year",
        nargs="?",
        choices=years,
        default=default_year,
        help=f"Election year (default: {default_year})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Network timeout in seconds per request (default: 15).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retry attempts for transient network failures (default: 4).",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=1.0,
        help="Exponential backoff base in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where candidates_*.json, mayor_*.json and meta_*.json are written.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    print(f"Running fetcher for year {args.year}...")

    ok = fetch_data(
        args.year,
        output_dir=args.output_dir,
        timeout=args.timeout,
        retries=args.retries,
        backoff_factor=args.backoff,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
