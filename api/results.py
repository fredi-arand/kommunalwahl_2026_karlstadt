from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from threading import Lock
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlparse

from election_source import (
    COUNCIL_RESULTS_URL,
    MAYOR_RESULTS_URL,
    YEAR,
    fetch_text,
    mayor_json_from_rows,
    parse_council_parties_from_results,
    parse_mayor_table_csv,
)

CACHE_TTL_SECONDS = 60.0
KV_REST_API_URL = os.getenv("KV_REST_API_URL", "").strip()
KV_REST_API_TOKEN = os.getenv("KV_REST_API_TOKEN", "").strip()
KV_SNAPSHOT_KEY = os.getenv("KV_SNAPSHOT_KEY", "kommunalwahl:karlstadt:results")
_payload_cache: dict[str, Any] | None = None
_payload_cache_created_at = 0.0
_payload_cache_lock = Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _has_kv_config() -> bool:
    return bool(KV_REST_API_URL and KV_REST_API_TOKEN)


def _kv_command(command: list[str], timeout: float = 5.0) -> Any:
    payload = json.dumps(command).encode("utf-8")
    request = Request(
        KV_REST_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {KV_REST_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("result")


def persist_snapshot(payload: dict[str, Any]) -> bool:
    if not _has_kv_config():
        return False

    snapshot = {
        "savedAt": utc_now_iso(),
        "payload": payload,
    }
    _kv_command(
        ["SET", KV_SNAPSHOT_KEY, json.dumps(snapshot, ensure_ascii=False)],
        timeout=5.0,
    )
    return True


def load_persisted_snapshot() -> tuple[dict[str, Any], int] | None:
    if not _has_kv_config():
        return None

    raw_result = _kv_command(["GET", KV_SNAPSHOT_KEY], timeout=5.0)
    if not raw_result:
        return None

    parsed = json.loads(raw_result)
    if isinstance(parsed, dict) and "payload" in parsed:
        payload = parsed.get("payload")
        saved_at = _parse_iso_datetime(parsed.get("savedAt"))
    else:
        payload = parsed
        saved_at = (
            _parse_iso_datetime(payload.get("timestamp"))
            if isinstance(payload, dict)
            else None
        )

    if not isinstance(payload, dict):
        return None

    age_seconds = 0
    if saved_at is not None:
        now = datetime.now(timezone.utc)
        age_seconds = int(max(0.0, (now - saved_at).total_seconds()))

    return dict(payload), age_seconds


def build_payload(timeout: float = 20.0) -> dict[str, Any]:
    mayor_candidates: list[dict[str, Any]] = []
    parties: list[dict[str, Any]] = []

    mayor_html = fetch_text(MAYOR_RESULTS_URL, timeout=timeout)
    _, _, mayor_rows = parse_mayor_table_csv(mayor_html)
    mayor_candidates = mayor_json_from_rows(mayor_rows)

    council_html = fetch_text(COUNCIL_RESULTS_URL, timeout=timeout)
    parties = parse_council_parties_from_results(council_html)
    council_candidates_available = any(
        len(party.get("candidates", [])) > 0 for party in parties
    )

    return {
        "year": YEAR,
        "timestamp": utc_now_iso(),
        "mayorAvailable": bool(mayor_candidates),
        "councilCsvAvailable": bool(parties),
        "councilCandidatesAvailable": council_candidates_available,
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
    try:
        persist_snapshot(payload)
    except Exception:
        pass

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
            self._send_json(200, payload)
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
                self._send_json(200, stale_payload)
                return

            try:
                persisted_snapshot_with_age = load_persisted_snapshot()
            except Exception:
                persisted_snapshot_with_age = None
            if persisted_snapshot_with_age is not None:
                stale_payload, stale_cache_age_seconds = persisted_snapshot_with_age
                stale_payload["stale"] = True
                stale_payload["warning"] = (
                    "Serving persisted snapshot because upstream refresh failed"
                )
                if debug:
                    stale_payload = with_debug(
                        stale_payload,
                        0,
                        "stale-kv-snapshot",
                        stale_cache_age_seconds,
                    )
                    stale_payload["debug"]["upstreamError"] = str(exc)
                self._send_json(200, stale_payload)
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
