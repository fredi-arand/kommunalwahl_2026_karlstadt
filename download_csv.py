from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = "Mozilla/5.0"

MAYOR_RESULTS_URL = (
    "https://wahlen.osrz-akdb.de/uf-p/677148/1/20260308/"
    "buergermeisterwahl_gemeinde/ergebnisse.html"
)
COUNCIL_PRESS_URL = (
    "https://wahlen.osrz-akdb.de/uf-p/677148/2/20260308/"
    "gemeinderatswahl_gemeinde/presse.html"
)
YEAR = "2026"
META_JSON_FILENAME = "meta.json"
MAYOR_JSON_FILENAME = "mayor.json"
COUNCIL_JSON_FILENAME = "candidates.json"

PARTY_COLORS = {
    "CSU": "#000000",
    "GRÜNE": "#228b22",
    "SPD": "#e3000f",
    "FWG": "#ff8c00",
}


def fetch_text(url: str, timeout: float = 20.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return body.decode("utf-8")


def to_csv_text(rows: Iterable[list[str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def normalize_filename(value: str) -> str:
    filename = normalize_text(value).strip().replace("/", "_")
    filename = re.sub(r"\s+", "_", filename)
    if not filename.lower().endswith(".csv"):
        filename = f"{filename}.csv"
    return filename


def parse_votes(value: str) -> int:
    digits = "".join(char for char in value if char.isdigit())
    return int(digits) if digits else 0


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_mayor_table_csv(html: str) -> tuple[str, str, list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", attrs={"data-tablejigsaw-downloadable": True})
    if table is None:
        raise ValueError("Could not find downloadable mayor table in ergebnisse.html")

    filename = normalize_filename(
        table.get("data-tablejigsaw-downloadable-filename")
        or "Stimmenanteile tabellarisch"
    )

    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        columns = row.find_all(["th", "td"])
        if not columns:
            continue
        values = [
            normalize_text(column.get_text(" ", strip=True)) for column in columns
        ]
        if any(values):
            rows.append(values)

    if not rows:
        raise ValueError("Mayor table is empty")

    return filename, to_csv_text(rows), rows


def mayor_json_from_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    payload: list[dict[str, Any]] = []
    for row in rows[1:]:
        if len(row) < 3:
            continue

        party = row[0]
        candidate_name = row[1]
        if not candidate_name:
            continue

        payload.append(
            {
                "name": candidate_name,
                "party": party,
                "votes": parse_votes(row[2]),
            }
        )

    payload.sort(key=lambda candidate: candidate["votes"], reverse=True)
    for index, candidate in enumerate(payload, start=1):
        candidate["id"] = index

    return payload


def parse_council_csv_filenames(press_html: str) -> list[str]:
    soup = BeautifulSoup(press_html, "html.parser")
    filenames: list[str] = []

    for row in soup.find_all("tr"):
        columns = row.find_all("td")
        if not columns:
            continue
        candidate = normalize_text(columns[0].get_text(" ", strip=True))
        if candidate.lower().endswith(".csv") and candidate not in filenames:
            filenames.append(candidate)

    return filenames


def looks_like_html_error(payload: str) -> bool:
    start = payload.lstrip().lower()
    return start.startswith("<!doctype html") or "fehler: 404" in start


def looks_like_csv(payload: str) -> bool:
    lines = payload.splitlines()
    if not lines:
        return False
    return ";" in lines[0] or "," in lines[0]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def download_once(
    csv_output_dir: Path,
    json_output_dir: Path,
    timeout: float,
) -> tuple[Path, list[Path], list[dict[str, Any]]]:
    mayor_html = fetch_text(MAYOR_RESULTS_URL, timeout=timeout)
    mayor_filename, mayor_csv, mayor_rows = parse_mayor_table_csv(mayor_html)
    mayor_path = csv_output_dir / mayor_filename
    write_text(mayor_path, mayor_csv)
    mayor_candidates = mayor_json_from_rows(mayor_rows)
    write_json(json_output_dir / MAYOR_JSON_FILENAME, mayor_candidates)

    press_html = fetch_text(COUNCIL_PRESS_URL, timeout=timeout)
    council_filenames = parse_council_csv_filenames(press_html)
    council_paths: list[Path] = []

    council_base_url = COUNCIL_PRESS_URL.rsplit("/", 1)[0] + "/"
    for filename in council_filenames:
        csv_url = urljoin(council_base_url, filename)
        try:
            payload = fetch_text(csv_url, timeout=timeout)
        except urllib.error.URLError:
            continue

        if looks_like_html_error(payload) or not looks_like_csv(payload):
            continue

        file_path = csv_output_dir / normalize_filename(filename)
        write_text(file_path, payload)
        council_paths.append(file_path)

    council_candidates: list[dict[str, Any]] = []
    write_json(json_output_dir / COUNCIL_JSON_FILENAME, council_candidates)

    meta_payload = {
        "year": YEAR,
        "timestamp": utc_now_iso(),
        "mayorAvailable": bool(mayor_candidates),
        "councilCsvAvailable": bool(council_paths),
        "councilCandidatesAvailable": bool(council_candidates),
    }
    write_json(json_output_dir / META_JSON_FILENAME, meta_payload)

    return mayor_path, council_paths, mayor_candidates


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download 2026 mayor/council CSVs from wahlen.osrz-akdb.de"
    )
    parser.add_argument(
        "--output-dir",
        default="data/csv",
        help="Directory to write CSV files (default: data/csv)",
    )
    parser.add_argument(
        "--json-dir",
        default=".",
        help="Directory to write JSON files (default: current directory)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="How many times to poll for council CSV availability (default: 1)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Seconds between attempts (default: 30)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout per request in seconds (default: 20)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_output_dir = Path(args.output_dir)
    json_output_dir = Path(args.json_dir)

    attempts = max(args.attempts, 1)
    mayor_path: Path | None = None
    council_paths: list[Path] = []
    mayor_candidates: list[dict[str, Any]] = []

    for attempt in range(1, attempts + 1):
        print(f"Attempt {attempt}/{attempts}...")
        mayor_path, council_paths, mayor_candidates = download_once(
            csv_output_dir,
            json_output_dir,
            timeout=args.timeout,
        )
        print(f"Saved mayor CSV: {mayor_path}")
        print(f"Saved mayor JSON: {json_output_dir / MAYOR_JSON_FILENAME}")
        print(f"Saved council JSON: {json_output_dir / COUNCIL_JSON_FILENAME}")
        print(f"Saved metadata JSON: {json_output_dir / META_JSON_FILENAME}")

        if council_paths:
            for path in council_paths:
                print(f"Saved council CSV: {path}")
            return 0

        if attempt < attempts:
            print(
                "Council CSV not published yet (still 404 or non-CSV). "
                f"Retrying in {args.interval:.0f}s..."
            )
            time.sleep(max(args.interval, 0.0))

    if mayor_candidates:
        print(
            "No council CSV available yet. Mayor CSV/JSON were refreshed successfully."
        )
    else:
        print("No council CSV available yet. Mayor data is currently empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
