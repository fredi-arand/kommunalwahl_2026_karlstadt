from __future__ import annotations

import csv
import json
import io
import re
import urllib.request
from html import unescape
from typing import Iterable

from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = "Mozilla/5.0"

MAYOR_RESULTS_URL = (
    "https://wahlen.osrz-akdb.de/uf-p/677148/1/20260308/"
    "buergermeisterwahl_gemeinde/ergebnisse.html"
)
COUNCIL_RESULTS_URL = (
    "https://wahlen.osrz-akdb.de/uf-p/677148/2/20260308/"
    "gemeinderatswahl_gemeinde/ergebnisse.html"
)
COUNCIL_TOTAL_CSV_URL = (
    "https://wahlen.osrz-akdb.de/uf-p/677148/2/20260308/"
    "gemeinderatswahl_gemeinde/gesamtergebnis.csv"
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


def parse_percent(value: str) -> float:
    normalized = normalize_text(value).replace("%", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def parse_hex_color(style: str) -> str | None:
    match = re.search(r"color\s*:\s*(#[0-9a-fA-F]{3,8})", style)
    if not match:
        return None
    return match.group(1)


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


def parse_counted_areas(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for stand_entry in soup.select("p.stand"):
        stand_text = normalize_text(stand_entry.get_text(" ", strip=True))
        match = re.search(
            r"Ausgez(?:ä|ae)hlte\s+Gebiete:\s*(\d+)\s+von\s+(\d+)",
            stand_text,
            flags=re.IGNORECASE,
        )
        if match:
            return f"{match.group(1)}/{match.group(2)}"

    return None


def parse_mayor_counted_areas(html: str) -> str | None:
    return parse_counted_areas(html)


def parse_council_counted_areas(html: str) -> str | None:
    return parse_counted_areas(html)


def parse_recent_counted_areas(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    for heading in soup.find_all(["h2", "h3"]):
        heading_text = normalize_text(heading.get_text(" ", strip=True)).lower()
        if "ankunftstafel" not in heading_text:
            continue

        table = heading.find_next("table")
        if table is None:
            continue

        areas: list[str] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            area_name = normalize_text(cells[0].get_text(" ", strip=True))
            if not area_name:
                continue
            lowered = area_name.lower()
            if lowered in {"gebiet", "wahlbezirk", "bezirk"}:
                continue

            if area_name not in areas:
                areas.append(area_name)

        return areas

    return []


def parse_mayor_recent_counted_areas(html: str) -> list[str]:
    return parse_recent_counted_areas(html)


def parse_council_recent_counted_areas(html: str) -> list[str]:
    return parse_recent_counted_areas(html)


def parse_council_party_overview(
    soup: BeautifulSoup,
) -> dict[str, dict[str, object]]:
    overview: dict[str, dict[str, object]] = {}

    for table in soup.find_all("table"):
        if table.select_one(".partei__name") is None:
            continue

        for row in table.select("tbody tr"):
            party_name_element = row.select_one(".partei__name")
            if party_name_element is None:
                continue

            party_name = normalize_text(party_name_element.get_text(" ", strip=True))
            cells = row.find_all(["th", "td"])
            votes = (
                parse_votes(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else 0
            )
            percent = (
                parse_percent(cells[2].get_text(" ", strip=True))
                if len(cells) > 2
                else 0.0
            )

            color_element = row.select_one(".partei__farbe")
            color_style = color_element.get("style", "") if color_element else ""
            color = parse_hex_color(color_style) or "#CCCCCC"

            overview[party_name] = {
                "votes": votes,
                "percent": percent,
                "color": color,
            }

    return overview


def parse_council_seat_overview(soup: BeautifulSoup) -> dict[str, int]:
    seats_by_party: dict[str, int] = {}

    for chart in soup.select(".js-d3chart"):
        options_raw = chart.get("data-chartoptions") or ""
        options_text = unescape(options_raw)
        if '"type":"sitze"' not in options_text:
            continue

        chart_data_raw = chart.get("data-chartdata") or ""
        if not chart_data_raw:
            continue

        try:
            chart_data = json.loads(unescape(chart_data_raw))
        except json.JSONDecodeError:
            continue

        datasets = chart_data.get("dataSets")
        if not isinstance(datasets, list):
            continue

        for entry in datasets:
            if not isinstance(entry, dict):
                continue
            label = normalize_text(str(entry.get("label") or ""))
            if not label:
                continue
            try:
                seats = int(float(entry.get("value") or 0))
            except (TypeError, ValueError):
                seats = 0
            seats_by_party[label] = max(0, seats)

        if seats_by_party:
            break

    return seats_by_party


def parse_council_parties_from_results(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    overview = parse_council_party_overview(soup)
    seat_overview = parse_council_seat_overview(soup)

    candidate_cards: list[BeautifulSoup] = []
    candidate_section_titles = {
        "kandidaten",
        "ergebnisse aller bewerberinnen und bewerber",
    }

    for card in soup.select("div.card"):
        title_element = card.select_one(".card_header")
        title = (
            normalize_text(title_element.get_text(" ", strip=True))
            if title_element
            else ""
        )
        normalized_title = title.lower()
        has_candidate_title = (
            normalized_title in candidate_section_titles
            or "bewerber" in normalized_title
        )
        if has_candidate_title and card.select_one("article.accordion-item"):
            candidate_cards.append(card)

    if not candidate_cards:
        raise ValueError(
            "Could not find council candidates accordion in ergebnisse.html"
        )

    parties: list[dict[str, object]] = []
    candidate_card = candidate_cards[0]

    for article in candidate_card.select("article.accordion-item"):
        party_name_element = article.select_one(".partei__name")
        if party_name_element is None:
            continue

        party_name = normalize_text(party_name_element.get_text(" ", strip=True))

        color_element = article.select_one(".partei__farbe")
        color_style = color_element.get("style", "") if color_element else ""
        party_color = parse_hex_color(color_style)

        table = article.select_one("table")
        if table is None:
            continue

        header_cells = [
            normalize_text(cell.get_text(" ", strip=True)).lower()
            for cell in table.select("thead th")
        ]

        name_col_index = 1
        for index, header_text in enumerate(header_cells):
            if "name" in header_text:
                name_col_index = index
                break

        id_col_index = 0
        for index, header_text in enumerate(header_cells):
            if "nr" in header_text:
                id_col_index = index
                break

        votes_col_index: int | None = None
        for index, header_text in enumerate(header_cells):
            if "stimmen" in header_text:
                votes_col_index = index
                break

        if votes_col_index is None:
            votes_col_index = (
                3 if len(header_cells) > 3 else (2 if len(header_cells) > 2 else None)
            )

        candidates: list[dict[str, object]] = []
        for index, row in enumerate(table.select("tbody tr"), start=1):
            cells = [
                normalize_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"])
            ]
            if len(cells) <= max(name_col_index, id_col_index):
                continue

            candidate_name = cells[name_col_index]
            if not candidate_name:
                continue

            candidate_id = (
                parse_votes(cells[id_col_index]) if cells[id_col_index] else index
            )

            candidate_votes = 0
            if votes_col_index is not None and len(cells) > votes_col_index:
                candidate_votes = parse_votes(cells[votes_col_index])

            candidates.append(
                {
                    "id": candidate_id if candidate_id > 0 else index,
                    "name": candidate_name,
                    "votes": candidate_votes,
                }
            )

        party_overview = overview.get(party_name, {})
        parties.append(
            {
                "id": party_name,
                "name": party_name,
                "color": party_color or party_overview.get("color") or "#CCCCCC",
                "seats": int(seat_overview.get(party_name) or 0),
                "totalVotesPercent": float(party_overview.get("percent") or 0.0),
                "candidates": candidates,
            }
        )

    return parties


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


def parse_council_counted_area_names_from_csv(csv_text: str) -> list[str]:
    rows = list(csv.DictReader(io.StringIO(csv_text), delimiter=";"))
    if not rows:
        return []

    counted_areas: list[str] = []
    for row in rows:
        if normalize_text(row.get("Gebietsart", "")).upper() not in {
            "STIMMBEZIRK",
            "BRIEFWAHLBEZIRK",
        }:
            continue

        area_name = normalize_text(row.get("Gebietsname", ""))
        if not area_name:
            continue

        valid_votes = parse_votes(row.get("Stimmen gueltige (D)", ""))
        voters = parse_votes(row.get("Waehler gesamt (B)", ""))
        if valid_votes <= 0 and voters <= 0:
            continue

        if area_name not in counted_areas:
            counted_areas.append(area_name)

    return counted_areas


def parse_council_counted_areas_progress_from_csv(csv_text: str) -> str | None:
    rows = list(csv.DictReader(io.StringIO(csv_text), delimiter=";"))
    if not rows:
        return None

    total = 0
    counted = 0
    for row in rows:
        if normalize_text(row.get("Gebietsart", "")).upper() not in {
            "STIMMBEZIRK",
            "BRIEFWAHLBEZIRK",
        }:
            continue
        total += 1

        valid_votes = parse_votes(row.get("Stimmen gueltige (D)", ""))
        voters = parse_votes(row.get("Waehler gesamt (B)", ""))
        if valid_votes > 0 or voters > 0:
            counted += 1

    if total <= 0:
        return None
    return f"{counted}/{total}"


def _parse_csv_int(value: str | None) -> int:
    return parse_votes(value or "")


def parse_council_d_block_votes_from_csv(csv_text: str) -> dict[int, list[int]]:
    rows = list(csv.DictReader(io.StringIO(csv_text), delimiter=";"))
    if not rows:
        return {}

    municipality_row = next(
        (
            row
            for row in rows
            if normalize_text(row.get("Gebietsart", "")).upper() == "GEMEINDE"
        ),
        rows[0],
    )
    if municipality_row is None:
        return {}

    d_block_ids: list[int] = []
    for column_name in municipality_row.keys():
        match = re.fullmatch(r"D(\d+)", column_name or "")
        if match:
            d_block_ids.append(int(match.group(1)))

    d_block_votes: dict[int, list[int]] = {}
    for block_id in d_block_ids:
        candidate_votes = [
            _parse_csv_int(municipality_row.get(f"D{block_id}_{index}"))
            for index in range(1, 25)
        ]
        if sum(candidate_votes) <= 0:
            continue
        d_block_votes[block_id] = candidate_votes

    return d_block_votes
