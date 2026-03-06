import argparse
import sys

from download_csv import main as download_main


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and store 2026 CSV results for Karlstadt elections."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Network timeout in seconds per request (default: 20).",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="How many times to poll for council CSV availability (default: 1).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Seconds between attempts (default: 30).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/csv",
        help="Directory where CSV files are written.",
    )
    parser.add_argument(
        "--json-dir",
        default=".",
        help="Directory where JSON files are written.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    print("Running 2026 CSV downloader...")
    downloader_argv = [
        "--output-dir",
        args.output_dir,
        "--json-dir",
        args.json_dir,
        "--attempts",
        str(args.attempts),
        "--interval",
        str(args.interval),
        "--timeout",
        str(args.timeout),
    ]
    return download_main(downloader_argv)


if __name__ == "__main__":
    sys.exit(main())
