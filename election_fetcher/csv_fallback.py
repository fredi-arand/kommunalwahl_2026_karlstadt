from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

PARTY_CODE_PATTERN = re.compile(r"^D\d+$")
CANDIDATE_CODE_PATTERN = re.compile(r"^(D\d+)_(\d+)$")


def _parse_int(value: str | None) -> int:
    if value is None:
        return 0
    normalized = "".join(ch for ch in str(value) if ch.isdigit() or ch == "-")
    if normalized in {"", "-"}:
        return 0
    return int(normalized)


def _read_csv_rows(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")

    headers = [header.strip() for header in reader.fieldnames]
    rows = [
        row for row in reader if any((value or "").strip() for value in row.values())
    ]
    if not rows:
        raise ValueError("CSV has no data rows")
    return headers, rows


def _extract_vote_columns(
    headers: list[str],
) -> tuple[list[str], dict[str, list[str]], list[str]]:
    party_codes: list[str] = []
    candidate_codes_by_party: dict[str, list[str]] = {}
    candidate_code_order: list[str] = []

    for header in headers:
        if PARTY_CODE_PATTERN.fullmatch(header):
            party_codes.append(header)
            candidate_codes_by_party.setdefault(header, [])
            continue

        match = CANDIDATE_CODE_PATTERN.fullmatch(header)
        if not match:
            continue
        party_code = match.group(1)
        candidate_codes_by_party.setdefault(party_code, []).append(header)
        candidate_code_order.append(header)

    party_codes.sort(key=lambda code: int(code[1:]))
    for party_code, candidate_codes in candidate_codes_by_party.items():
        candidate_codes.sort(key=lambda code: int(code.split("_", 1)[1]))
        candidate_codes_by_party[party_code] = candidate_codes

    candidate_code_order.sort(
        key=lambda code: (
            int(code.split("_", 1)[0][1:]),
            int(code.split("_", 1)[1]),
        )
    )

    return party_codes, candidate_codes_by_party, candidate_code_order


def _find_total_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    for row in rows:
        raw_area_number = (row.get("gebiet-nr") or "").strip()
        if not raw_area_number:
            continue
        if raw_area_number.lstrip("0") == "":
            return row
    return None


def _extract_csv_votes(
    csv_text: str,
) -> tuple[dict[str, int], list[str], dict[str, list[str]]]:
    headers, rows = _read_csv_rows(csv_text)
    party_codes, candidate_codes_by_party, candidate_code_order = _extract_vote_columns(
        headers
    )

    if not party_codes:
        raise ValueError("CSV does not contain any D* party columns")

    vote_columns = [*party_codes, *candidate_code_order]
    total_row = _find_total_row(rows)
    if total_row is not None:
        return (
            {column: _parse_int(total_row.get(column)) for column in vote_columns},
            party_codes,
            candidate_codes_by_party,
        )

    aggregated_votes: dict[str, int] = {column: 0 for column in vote_columns}
    for row in rows:
        for column in vote_columns:
            aggregated_votes[column] += _parse_int(row.get(column))

    return aggregated_votes, party_codes, candidate_codes_by_party


def build_council_csv_mapping(
    year: str,
    council_results: list[dict[str, Any]],
    csv_text: str,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    csv_votes, party_codes, candidate_codes_by_party = _extract_csv_votes(csv_text)

    remaining_codes = set(party_codes)
    mapped_parties: list[dict[str, Any]] = []

    for party in council_results:
        candidates = list(party.get("candidates", []))
        candidate_votes = [int(candidate.get("votes", 0)) for candidate in candidates]
        party_total = sum(candidate_votes)
        expected_candidate_count = len(candidates)

        exact_matches: list[str] = []
        loose_matches: list[str] = []

        for party_code in sorted(remaining_codes, key=lambda code: int(code[1:])):
            if csv_votes.get(party_code, 0) != party_total:
                continue

            csv_candidate_codes = candidate_codes_by_party.get(party_code, [])
            if len(csv_candidate_codes) != expected_candidate_count:
                continue

            loose_matches.append(party_code)
            csv_candidate_votes = [
                csv_votes.get(candidate_code, 0)
                for candidate_code in csv_candidate_codes
            ]
            if csv_candidate_votes == candidate_votes:
                exact_matches.append(party_code)

        if len(exact_matches) == 1:
            selected_party_code = exact_matches[0]
        elif not exact_matches and len(loose_matches) == 1:
            selected_party_code = loose_matches[0]
        else:
            raise ValueError(
                f"Could not uniquely map party '{party.get('name', 'Unknown')}' to a CSV D-code"
            )

        remaining_codes.remove(selected_party_code)
        selected_candidate_codes = candidate_codes_by_party.get(selected_party_code, [])

        mapped_candidates: list[dict[str, str]] = []
        for candidate, candidate_code in zip(candidates, selected_candidate_codes):
            mapped_candidates.append(
                {
                    "csvCode": candidate_code,
                    "name": str(candidate.get("name", "Unknown")),
                }
            )

        mapped_parties.append(
            {
                "csvCode": selected_party_code,
                "id": str(party.get("id", party.get("name", selected_party_code))),
                "name": str(party.get("name", selected_party_code)),
                "color": str(party.get("color", "#CCCCCC")),
                "totalVotesPercent": float(party.get("totalVotesPercent", 0.0)),
                "candidates": mapped_candidates,
            }
        )

    return {
        "year": year,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "parties": mapped_parties,
    }


def parse_council_results_from_csv(
    csv_text: str,
    mapping: dict[str, Any],
) -> list[dict[str, Any]]:
    csv_votes, _, _ = _extract_csv_votes(csv_text)

    mapped_parties = mapping.get("parties")
    if not isinstance(mapped_parties, list) or not mapped_parties:
        raise ValueError("Mapping is missing a non-empty 'parties' list")

    total_mapped_votes = sum(
        csv_votes.get(str(party.get("csvCode", "")), 0) for party in mapped_parties
    )

    results: list[dict[str, Any]] = []
    for mapped_party in mapped_parties:
        party_code = str(mapped_party.get("csvCode", "")).strip()
        if not party_code:
            raise ValueError("Mapping contains a party without csvCode")

        party_votes = csv_votes.get(party_code, 0)

        mapped_candidates = mapped_party.get("candidates", [])
        candidates_payload: list[dict[str, Any]] = []
        for index, mapped_candidate in enumerate(mapped_candidates, start=1):
            candidate_code = str(mapped_candidate.get("csvCode", "")).strip()
            if not candidate_code:
                raise ValueError("Mapping contains a candidate without csvCode")

            candidates_payload.append(
                {
                    "id": index,
                    "name": str(mapped_candidate.get("name", "Unknown")),
                    "votes": csv_votes.get(candidate_code, 0),
                }
            )

        raw_percent = mapped_party.get("totalVotesPercent")
        if isinstance(raw_percent, (int, float)):
            percent = float(raw_percent)
        elif total_mapped_votes > 0:
            percent = round((party_votes / total_mapped_votes) * 100, 2)
        else:
            percent = 0.0

        results.append(
            {
                "id": str(mapped_party.get("id", mapped_party.get("name", party_code))),
                "name": str(mapped_party.get("name", party_code)),
                "color": str(mapped_party.get("color", "#CCCCCC")),
                "totalVotesPercent": percent,
                "candidates": candidates_payload,
            }
        )

    return results
