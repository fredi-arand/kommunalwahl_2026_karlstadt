from __future__ import annotations

import csv
import io
import re
import urllib.request
from typing import Iterable

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


def mayor_json_from_rows(rows: list[list[str]]) -> list[dict[str, object]]:
    if not rows:
        return []

    payload: list[dict[str, object]] = []
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

    payload.sort(key=lambda candidate: int(candidate["votes"]), reverse=True)
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
