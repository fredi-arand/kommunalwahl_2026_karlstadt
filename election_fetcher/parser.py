from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup


def _parse_name_and_party(value: str) -> tuple[str, str]:
    if ", " in value:
        candidate_name, party_short = value.rsplit(", ", 1)
        return candidate_name.strip(), party_short.strip()
    return value.strip(), "Unknown"


def _extract_vote_count(value: str) -> int | None:
    if "%" in value:
        return None
    digits_only = "".join(char for char in value if char.isdigit())
    if not digits_only:
        return None
    return int(digits_only)


def _new_party(
    name: str, color: str = "#CCCCCC", percent: float = 0.0
) -> dict[str, Any]:
    return {
        "id": name,
        "name": name,
        "color": color,
        "totalVotesPercent": percent,
        "candidates": [],
    }


def _parse_parties_from_chart(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    parties: dict[str, dict[str, Any]] = {}

    chart_div = soup.find("div", class_="darstellung-balkendiagramm")
    if not chart_div:
        chart_div = soup.find("div", class_="darstellung-saeulendiagramm")

    if not chart_div or not chart_div.has_attr("data-array"):
        return parties

    try:
        chart_data = json.loads(chart_div["data-array"])
    except (TypeError, json.JSONDecodeError):
        return parties

    for item in chart_data:
        if "balken" in item:
            for grouped in item["balken"]:
                party_name = grouped.get("name", "Unknown")
                parties[party_name] = _new_party(
                    party_name,
                    color=grouped.get("color", "#CCCCCC"),
                    percent=grouped.get("y", 0.0),
                )
        else:
            party_name = item.get("name", "Unknown")
            parties[party_name] = _new_party(
                party_name,
                color=item.get("color", "#CCCCCC"),
                percent=item.get("y", 0.0),
            )

    return parties


def _find_votes_in_row(columns: list[BeautifulSoup]) -> int:
    for column in columns:
        nobr = column.find("nobr")
        if not nobr:
            continue
        votes = _extract_vote_count(nobr.get_text(strip=True))
        if votes is not None:
            return votes
    return 0


def _match_party_key(
    parties: dict[str, dict[str, Any]], party_short: str
) -> str | None:
    for key in parties:
        if key.lower() == party_short.lower():
            return key

    for key in parties:
        key_l = key.lower()
        short_l = party_short.lower()
        if short_l in key_l or key_l in short_l:
            return key

    return None


def parse_council_results(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    parties = _parse_parties_from_chart(soup)

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            columns = row.find_all(["td", "th"])
            if len(columns) < 3:
                continue

            abbr = row.find("abbr")
            if not abbr:
                continue

            candidate_text = abbr.get_text(strip=True)
            candidate_name, party_short = _parse_name_and_party(candidate_text)
            if candidate_name in parties:
                continue

            party_key = _match_party_key(parties, party_short)
            if not party_key:
                party_key = party_short or "Unknown"
                parties.setdefault(party_key, _new_party(party_key))

            candidate_list = parties[party_key]["candidates"]
            exists = any(
                candidate["name"] == candidate_name for candidate in candidate_list
            )
            if exists:
                continue

            candidate_list.append(
                {
                    "id": len(candidate_list) + 1,
                    "name": candidate_name,
                    "votes": _find_votes_in_row(columns),
                }
            )

    return list(parties.values())


def parse_mayor_results(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    mayor_candidates: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            abbr = row.find("abbr")
            if not abbr:
                continue

            candidate_text = abbr.get_text(strip=True)
            candidate_name, party_short = _parse_name_and_party(candidate_text)
            if candidate_name == party_short:
                continue

            votes = 0
            nobr = row.find("nobr")
            if nobr:
                parsed_votes = _extract_vote_count(nobr.get_text(strip=True))
                votes = parsed_votes if parsed_votes is not None else 0
            else:
                columns = row.find_all(["td", "th"])
                for column in reversed(columns):
                    parsed_votes = _extract_vote_count(column.get_text(" ", strip=True))
                    if parsed_votes is not None:
                        votes = parsed_votes
                        break

            mayor_candidates.append(
                {
                    "name": candidate_name,
                    "party": party_short if party_short != "Unknown" else None,
                    "votes": votes,
                }
            )

    by_candidate: dict[tuple[str, str | None], dict[str, Any]] = {}
    for candidate in mayor_candidates:
        key = (candidate["name"], candidate["party"])
        existing = by_candidate.get(key)
        if existing is None or candidate["votes"] > existing["votes"]:
            by_candidate[key] = candidate

    results = sorted(
        by_candidate.values(), key=lambda candidate: candidate["votes"], reverse=True
    )
    for index, candidate in enumerate(results, start=1):
        candidate["id"] = index

    return results
