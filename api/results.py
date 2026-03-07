from __future__ import annotations

import json
import time
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from election_source import (
    COUNCIL_PRESS_URL,
    MAYOR_RESULTS_URL,
    YEAR,
    fetch_text,
    looks_like_csv,
    looks_like_html_error,
    mayor_json_from_rows,
    normalize_filename,
    parse_council_csv_filenames,
    parse_mayor_table_csv,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_payload(timeout: float = 20.0) -> dict[str, Any]:
    mayor_candidates: list[dict[str, Any]] = []
    council_paths: list[str] = []

    mayor_html = fetch_text(MAYOR_RESULTS_URL, timeout=timeout)
    _, _, mayor_rows = parse_mayor_table_csv(mayor_html)
    mayor_candidates = mayor_json_from_rows(mayor_rows)

    press_html = fetch_text(COUNCIL_PRESS_URL, timeout=timeout)
    council_filenames = parse_council_csv_filenames(press_html)
    council_base_url = COUNCIL_PRESS_URL.rsplit("/", 1)[0] + "/"

    for filename in council_filenames:
        csv_url = urljoin(council_base_url, filename)
        try:
            payload = fetch_text(csv_url, timeout=timeout)
        except urllib.error.URLError:
            continue

        if looks_like_html_error(payload) or not looks_like_csv(payload):
            continue

        council_paths.append(normalize_filename(filename))

    parties: list[dict[str, Any]] = []

    return {
        "year": YEAR,
        "timestamp": utc_now_iso(),
        "mayorAvailable": bool(mayor_candidates),
        "councilCsvAvailable": bool(council_paths),
        "councilCandidatesAvailable": bool(parties),
        "mayor": mayor_candidates,
        "parties": parties,
    }


def with_debug(payload: dict[str, Any], duration_ms: int) -> dict[str, Any]:
    debug_payload = dict(payload)
    debug_payload["debug"] = {
        "generatedAt": utc_now_iso(),
        "durationMs": duration_ms,
        "sources": {
            "mayor": MAYOR_RESULTS_URL,
            "councilPress": COUNCIL_PRESS_URL,
        },
        "counts": {
            "mayor": len(payload.get("mayor", [])),
            "parties": len(payload.get("parties", [])),
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
        self.send_header("Cache-Control", "public, max-age=20, s-maxage=20")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        debug = is_truthy((query.get("debug") or [None])[0])

        try:
            started_at = time.perf_counter()
            payload = build_payload(timeout=20.0)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if debug:
                payload = with_debug(payload, duration_ms)
            self._send_json(200, payload)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            self._send_json(
                502,
                {
                    "error": "Failed to fetch official election data",
                    "details": str(exc),
                    "debug": {
                        "generatedAt": utc_now_iso(),
                        "sources": {
                            "mayor": MAYOR_RESULTS_URL,
                            "councilPress": COUNCIL_PRESS_URL,
                        },
                    },
                },
            )
