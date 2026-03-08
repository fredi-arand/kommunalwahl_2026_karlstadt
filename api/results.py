from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from election_source import (
    COUNCIL_TOTAL_CSV_URL,
    COUNCIL_RESULTS_URL,
    MAYOR_RESULTS_URL,
    YEAR,
    fetch_text,
    parse_council_d_block_votes_from_csv,
    parse_council_counted_area_names_from_csv,
    parse_council_counted_areas,
    parse_council_counted_areas_progress_from_csv,
    mayor_json_from_rows,
    parse_mayor_counted_areas,
    parse_council_parties_from_results,
    parse_mayor_table_csv,
)

CACHE_TTL_SECONDS = 60.0
_payload_cache: dict[str, Any] | None = None
_payload_cache_created_at = 0.0
_payload_cache_lock = Lock()
COUNCIL_MAPPING_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "csv"
    / "council_candidate_mapping_2026.json"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def party_vote_total(party: dict[str, Any]) -> int:
    candidates = party.get("candidates", [])
    if not isinstance(candidates, list):
        return 0
    return sum(int(candidate.get("votes", 0) or 0) for candidate in candidates)


def apply_council_csv_votes(
    parties: list[dict[str, Any]],
    d_block_votes: dict[int, list[int]],
) -> list[dict[str, Any]]:
    if not parties or not d_block_votes:
        return parties

    block_totals = {block_id: sum(votes) for block_id, votes in d_block_votes.items()}
    unmatched_blocks = set(d_block_votes.keys())
    party_to_block: dict[int, int] = {}

    for party_index, party in enumerate(parties):
        expected_total = party_vote_total(party)
        for block_id in sorted(unmatched_blocks):
            if block_totals.get(block_id, -1) == expected_total:
                party_to_block[party_index] = block_id
                unmatched_blocks.remove(block_id)
                break

    for party_index in range(len(parties)):
        if party_index in party_to_block:
            continue
        if not unmatched_blocks:
            break
        block_id = sorted(unmatched_blocks)[0]
        party_to_block[party_index] = block_id
        unmatched_blocks.remove(block_id)

    updated_parties: list[dict[str, Any]] = []
    for party_index, party in enumerate(parties):
        block_id = party_to_block.get(party_index)
        if block_id is None:
            updated_parties.append(party)
            continue

        block_candidate_votes = d_block_votes.get(block_id, [])
        updated_candidates: list[dict[str, Any]] = []
        for candidate_index, candidate in enumerate(party.get("candidates", [])):
            vote_value = (
                int(block_candidate_votes[candidate_index])
                if candidate_index < len(block_candidate_votes)
                else int(candidate.get("votes", 0) or 0)
            )
            updated_candidate = dict(candidate)
            updated_candidate["votes"] = vote_value
            updated_candidates.append(updated_candidate)

        updated_party = dict(party)
        updated_party["candidates"] = updated_candidates
        updated_parties.append(updated_party)

    return updated_parties


def load_council_candidate_mapping() -> dict[str, Any]:
    with COUNCIL_MAPPING_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Council candidate mapping must be a JSON object")
    return payload


def parse_d_block_id(block_value: str) -> int | None:
    if not isinstance(block_value, str):
        return None
    normalized = block_value.strip().upper()
    if not normalized.startswith("D"):
        return None
    try:
        return int(normalized[1:])
    except ValueError:
        return None


def build_parties_from_csv_mapping(
    csv_text: str,
    mapping_payload: dict[str, Any],
    fallback_parties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    d_block_votes = parse_council_d_block_votes_from_csv(csv_text)
    if not d_block_votes:
        return []

    mapping_parties = mapping_payload.get("parties", {})
    if not isinstance(mapping_parties, dict):
        return []

    fallback_by_name = {
        str(party.get("name")): party
        for party in fallback_parties
        if isinstance(party, dict) and party.get("name")
    }

    built_parties: list[dict[str, Any]] = []
    for party_name, entry in mapping_parties.items():
        if not isinstance(entry, dict):
            continue
        block_id = parse_d_block_id(str(entry.get("block") or ""))
        if block_id is None:
            continue

        votes_by_index = d_block_votes.get(block_id)
        if not votes_by_index:
            continue

        candidate_names = entry.get("candidates", [])
        if not isinstance(candidate_names, list):
            continue

        candidates: list[dict[str, Any]] = []
        for index, name in enumerate(candidate_names):
            if not isinstance(name, str) or not name.strip():
                continue
            votes = votes_by_index[index] if index < len(votes_by_index) else 0
            candidates.append({"id": index + 1, "name": name.strip(), "votes": votes})

        fallback_party = fallback_by_name.get(party_name, {})
        built_parties.append(
            {
                "id": party_name,
                "name": party_name,
                "color": fallback_party.get("color", "#CCCCCC"),
                "seats": int(fallback_party.get("seats", 0) or 0),
                "totalVotesPercent": float(
                    fallback_party.get("totalVotesPercent", 0.0) or 0.0
                ),
                "candidates": candidates,
            }
        )

    if built_parties:
        return built_parties
    return []


def compare_csv_and_html_party_totals(
    csv_parties: list[dict[str, Any]],
    html_parties: list[dict[str, Any]],
) -> bool:
    if not csv_parties or not html_parties:
        return False

    html_totals = {
        str(party.get("name")): party_vote_total(party) for party in html_parties
    }
    for party in csv_parties:
        name = str(party.get("name"))
        if name not in html_totals:
            continue
        if party_vote_total(party) != html_totals[name]:
            return False
    return True


def build_payload(timeout: float = 20.0) -> dict[str, Any]:
    mayor_candidates: list[dict[str, Any]] = []
    parties: list[dict[str, Any]] = []
    mayor_counted_areas: str | None = None
    council_counted_areas: str | None = None
    council_counted_areas_list: list[str] = []
    council_csv_html_sync: bool | None = None

    mayor_html = fetch_text(MAYOR_RESULTS_URL, timeout=timeout)
    mayor_counted_areas = parse_mayor_counted_areas(mayor_html)
    _, _, mayor_rows = parse_mayor_table_csv(mayor_html)
    mayor_candidates = mayor_json_from_rows(mayor_rows)

    council_csv_text = fetch_text(COUNCIL_TOTAL_CSV_URL, timeout=timeout)
    council_counted_areas = parse_council_counted_areas_progress_from_csv(
        council_csv_text
    )
    council_counted_areas_list = parse_council_counted_area_names_from_csv(
        council_csv_text
    )

    fallback_html_parties: list[dict[str, Any]] = []
    try:
        council_html = fetch_text(COUNCIL_RESULTS_URL, timeout=timeout)
        fallback_html_parties = parse_council_parties_from_results(council_html)
        if not council_counted_areas:
            council_counted_areas = parse_council_counted_areas(council_html)
    except Exception:
        fallback_html_parties = []

    try:
        mapping_payload = load_council_candidate_mapping()
        csv_parties = build_parties_from_csv_mapping(
            council_csv_text,
            mapping_payload,
            fallback_html_parties,
        )
    except Exception:
        csv_parties = []

    if csv_parties:
        parties = csv_parties
        council_csv_html_sync = compare_csv_and_html_party_totals(
            csv_parties, fallback_html_parties
        )
    else:
        parties = fallback_html_parties

    if not council_counted_areas and council_counted_areas_list:
        council_counted_areas = f"{len(council_counted_areas_list)}/25"

    council_candidates_available = any(
        len(party.get("candidates", [])) > 0 for party in parties
    )

    return {
        "year": YEAR,
        "timestamp": utc_now_iso(),
        "mayorAvailable": bool(mayor_candidates),
        "councilCsvAvailable": bool(parties),
        "councilCandidatesAvailable": council_candidates_available,
        "countedAreas": mayor_counted_areas or council_counted_areas,
        "mayorCountedAreas": mayor_counted_areas,
        "councilCountedAreas": council_counted_areas,
        "councilCountedAreasList": council_counted_areas_list,
        "councilCsvHtmlInSync": council_csv_html_sync,
        "mayor": mayor_candidates,
        "parties": parties,
    }


def get_payload_cached(timeout: float = 20.0) -> tuple[dict[str, Any], str, int]:
    global _payload_cache, _payload_cache_created_at

    now = time.time()
    with _payload_cache_lock:
        if (
            _payload_cache is not None
            and (now - _payload_cache_created_at) < CACHE_TTL_SECONDS
        ):
            age_seconds = int(max(0.0, now - _payload_cache_created_at))
            return dict(_payload_cache), "runtime-cache", age_seconds

    payload = build_payload(timeout=timeout)

    with _payload_cache_lock:
        _payload_cache = dict(payload)
        _payload_cache_created_at = time.time()

    return dict(payload), "origin-refresh", 0


def get_any_cached_payload() -> tuple[dict[str, Any], int] | None:
    with _payload_cache_lock:
        if _payload_cache is None:
            return None
        age_seconds = int(max(0.0, time.time() - _payload_cache_created_at))
        return dict(_payload_cache), age_seconds


def council_sync_status_from_payload(payload: dict[str, Any]) -> str:
    in_sync = payload.get("councilCsvHtmlInSync")
    if in_sync is True:
        return "ok"
    if in_sync is False:
        return "mismatch"
    return "unknown"


def sanitize_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    cleaned.pop("councilCsvHtmlInSync", None)
    return cleaned


def with_debug(
    payload: dict[str, Any],
    duration_ms: int,
    cache_source: str,
    cache_age_seconds: int,
) -> dict[str, Any]:
    debug_payload = dict(payload)
    debug_payload["debug"] = {
        "generatedAt": utc_now_iso(),
        "durationMs": duration_ms,
        "cache": {
            "source": cache_source,
            "ageSeconds": cache_age_seconds,
            "ttlSeconds": int(CACHE_TTL_SECONDS),
        },
        "sources": {
            "mayor": MAYOR_RESULTS_URL,
            "councilResults": COUNCIL_RESULTS_URL,
        },
        "counts": {
            "mayor": len(payload.get("mayor", [])),
            "parties": len(payload.get("parties", [])),
        },
        "councilCandidates": {
            "syncStatus": council_sync_status_from_payload(payload),
            "inSync": payload.get("councilCsvHtmlInSync"),
        },
    }
    return debug_payload


def is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Cache-Control",
            "public, max-age=60, s-maxage=60, stale-while-revalidate=30",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        debug = is_truthy((query.get("debug") or [None])[0])

        try:
            started_at = time.perf_counter()
            payload, cache_source, cache_age_seconds = get_payload_cached(timeout=20.0)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if debug:
                payload = with_debug(
                    payload,
                    duration_ms,
                    cache_source,
                    cache_age_seconds,
                )
            self._send_json(200, sanitize_public_payload(payload))
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            stale_payload_with_age = get_any_cached_payload()
            if stale_payload_with_age is not None:
                stale_payload, stale_cache_age_seconds = stale_payload_with_age
                stale_payload["stale"] = True
                stale_payload["warning"] = (
                    "Serving cached data because upstream refresh failed"
                )
                if debug:
                    stale_payload = with_debug(
                        stale_payload,
                        0,
                        "stale-fallback",
                        stale_cache_age_seconds,
                    )
                    stale_payload["debug"]["upstreamError"] = str(exc)
                self._send_json(200, sanitize_public_payload(stale_payload))
                return

            self._send_json(
                502,
                {
                    "error": "Failed to fetch official election data",
                    "details": str(exc),
                    "debug": {
                        "generatedAt": utc_now_iso(),
                        "sources": {
                            "mayor": MAYOR_RESULTS_URL,
                            "councilResults": COUNCIL_RESULTS_URL,
                        },
                    },
                },
            )
