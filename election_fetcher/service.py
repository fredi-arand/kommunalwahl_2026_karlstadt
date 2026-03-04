from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import URLS
from .io_utils import write_json
from .network import fetch_html
from .parser import parse_council_results, parse_mayor_results


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fetch_data(
    year: str,
    *,
    output_dir: str | Path = ".",
    timeout: float = 15.0,
    retries: int = 4,
    backoff_factor: float = 1.0,
    fetch_html_fn: Callable[..., str] = fetch_html,
    write_json_fn: Callable[[str | Path, Any], None] = write_json,
    now_fn: Callable[[], datetime] = _utc_now,
    log_fn: Callable[[str], None] = print,
) -> bool:
    if year not in URLS:
        raise ValueError(f"Unsupported year: {year}")

    election_url, mayor_url = URLS[year]
    target_dir = Path(output_dir)

    candidates_output = target_dir / f"candidates_{year}.json"
    mayor_output = target_dir / f"mayor_{year}.json"
    meta_output = target_dir / f"meta_{year}.json"

    log_fn(f"Fetching council page: {election_url}")
    try:
        election_html = fetch_html_fn(
            election_url,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
        )
        council_results = parse_council_results(election_html)
        write_json_fn(candidates_output, council_results)
        log_fn(f"Saved {len(council_results)} parties to {candidates_output}")
    except Exception as exc:
        log_fn(f"Error fetching/parsing council data: {exc}")
        return False

    mayor_ok = False
    log_fn(f"Fetching mayor page: {mayor_url}")
    try:
        mayor_html = fetch_html_fn(
            mayor_url,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
        )
        mayor_results = parse_mayor_results(mayor_html)
        write_json_fn(mayor_output, mayor_results)
        log_fn(f"Saved {len(mayor_results)} mayor candidates to {mayor_output}")
        mayor_ok = True
    except Exception as exc:
        log_fn(f"Error fetching/parsing mayor data: {exc}")

    metadata = {
        "year": year,
        "timestamp": now_fn().isoformat(),
        "mayor_ok": mayor_ok,
    }
    write_json_fn(meta_output, metadata)
    log_fn(f"Saved metadata to {meta_output}")

    return True
